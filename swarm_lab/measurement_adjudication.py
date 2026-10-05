"""Frozen bounded message samples and declared measurement judgments.

No provider, behavioral-library, source-file, or classifier adapter is invoked.
Exact Store pins authenticate retained registry bodies, not raw exported bytes.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import math
import random
import re
import sys
import uuid
from pathlib import Path

from swarm_lab import discovery
from swarm_lab.store import clean, fingerprint, now

SAMPLE_VERSION = 'measurement-sample-v1'
REVIEW_VERSION = 'measurement-review-v1'
PACKET_VERSION = 'measurement-review-packet-v1'
REPORT_VERSION = 'measurement-review-report-v1'
LABELS = ('yes', 'no', 'uncertain')
REVIEWER_MODES = ('manual_operator', 'agent_assisted', 'synthetic_fixture')
MAX_SAMPLE = 32
MAX_POPULATION = 10000
MAX_EVENTS = 256
MAX_EXCERPT = 2000
MAX_SEED = 2**53-1
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}\Z')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_DISCOVERY_PATH = Path(discovery.__file__).resolve()
_DISCOVERY_LOADED_SHA = hashlib.sha256(_DISCOVERY_PATH.read_bytes()).hexdigest()
_DEFINITIONS_LOADED = copy.deepcopy(discovery.DETECTOR_DEFINITIONS)
_DETECTOR_VERSION_LOADED = discovery.DETECTOR_VERSION
_POPULATION_SCOPE = 'All retained messages in this exact dataset, including declared speaker categories; not the complete export.'
_DEFINITION_SCOPE = 'Regex definition is separate from the authored operational construct; equivalence is not established.'
_LABEL_POLICY = 'Latest accepted declaration per sampled message; not consensus or authenticated human truth.'
_PROVENANCE = 'Reviewer identity and mode are declared, not independently authenticated.'
_SCOPE = ('Sample-level comparisons against latest accepted declared labels only; '
          'not consensus, authenticated human truth, representative independent adjudication, '
          'calibration, population accuracy, prevalence, novelty, or causal evidence. '
          'No model calls or behavior/library status changes. Retained registry sources '
          'are checked; raw source bytes are not reread. A current pinned regex may '
          'be recomputed cheaply to check saved prediction consistency; this does '
          'not attest historical execution or semantic correctness.')


def _json(value, maximum=1024*1024):
    nodes = 0
    def walk(row, depth):
        nonlocal nodes
        nodes += 1
        if depth > 48 or nodes > 250000:
            raise ValueError('bounded_json_depth_or_nodes_exceeded')
        if row is None or type(row) in (str, bool, int):
            return
        if type(row) is float and math.isfinite(row):
            return
        if type(row) is list:
            for child in row: walk(child, depth+1)
            return
        if type(row) is dict and all(type(key) is str for key in row):
            for child in row.values(): walk(child, depth+1)
            return
        raise ValueError('finite_typed_json_required')
    walk(value, 0)
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(encoded) > maximum:
        raise ValueError('accepted_json_byte_budget_exceeded')
    return encoded


def _sha(value):
    return hashlib.sha256(_json(value, 8*1024*1024)).hexdigest()


def _text(value, name, maximum, *, empty=False):
    if type(value) is not str or len(value)>maximum or (not empty and not value.strip()):
        raise ValueError('invalid_'+name)
    return value


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid_'+name)
    return value


def _identity(value):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError('bounded_identity_required')
    return value


def _ref(value):
    if (type(value) is not dict or set(value)!={'id','version','hash'} or
            type(value.get('hash')) is not str or not _SHA.fullmatch(value['hash'])):
        raise ValueError('exact_three_field_reference_required')
    _identity(value['id']); _integer(value['version'],'reference_version',1,10**9)
    return copy.deepcopy(value)


def _pin(obj):
    return {key: obj[key] for key in ('id','version','hash')}


def _load(store, ref, kind):
    ref = _ref(ref)
    try: obj = store.get(ref['id'],ref['version'])
    except RecursionError: raise ValueError('registry_decode_depth_unavailable') from None
    if (type(obj) is not dict or obj.get('kind')!=kind or _ref(_pin(obj))!=ref or
            _json(obj.get('payload'),8*1024*1024) is None or fingerprint(obj['payload'])!=obj['hash']):
        raise ValueError('exact_'+kind+'_body_required')
    return obj


def _clean_identity(body):
    if _json(clean(body)) != _json(body):
        raise ValueError('persistence_redaction_would_change_frozen_data')


def _timestamp(value):
    _text(value,'timestamp',100)
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise ValueError('aware_source_timestamp_required') from None
    if parsed.tzinfo is None:
        raise ValueError('aware_source_timestamp_required')
    return parsed.astimezone(dt.timezone.utc)


def _source_record(message):
    if type(message) is not dict:
        raise ValueError('source_message_object_required')
    for key in ('id','room_id','speaker_id'):
        _identity(message.get(key))
    _timestamp(message.get('timestamp'))
    _text(message.get('content'),'source_content',256*1024,empty=True)
    _text(message.get('agent_name'),'source_agent_name',1000)
    _text(message.get('speaker_type'),'speaker_type',40)
    source = message.get('source')
    if type(source) is not dict:
        raise ValueError('original_source_coordinates_required')
    _text(source.get('file'),'source_file',1024)
    _integer(source.get('line'),'source_line',1,10**12)
    if 'table' in source: _text(source['table'],'source_table',100)
    if type(message.get('content_hash')) is not str or not _SHA.fullmatch(message['content_hash']):
        raise ValueError('declared_source_content_hash_required')
    _json(source,4096)
    content = message['content']
    return {'id':message['id'],'timestamp':message['timestamp'],'room_id':message['room_id'],
            'agent_name':message['agent_name'],'speaker_type':message['speaker_type'],
            'source':{key:copy.deepcopy(source[key]) for key in ('file','line','table') if key in source},'source_sha256':_sha(source),
            'source_record_sha256':_sha(message),
            'declared_message_content_hash':message['content_hash'],
            'full_content_utf8_sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'content':content[:MAX_EXCERPT],'content_characters':len(content),
            'content_truncated':len(content)>MAX_EXCERPT}


def _population(dataset):
    messages=dataset.get('messages')
    if type(messages) is not list or not 1 <= len(messages) <= MAX_POPULATION:
        raise ValueError('bounded_nonempty_population_required')
    records={}; by_room={}; types={}
    for row in messages:
        bounded=_source_record(row)
        if row['id'] in records: raise ValueError('duplicate_source_message_identity')
        records[row['id']]=(row,bounded)
        by_room.setdefault(row['room_id'],[]).append(row['id'])
        types[row['speaker_type']]=types.get(row['speaker_type'],0)+1
    for identities in by_room.values():
        identities.sort(key=lambda identity:(_timestamp(records[identity][0]['timestamp']),identity))
    return records,by_room,dict(sorted(types.items()))


def _items(records,by_room,draw_order,neighbors):
    result=[]
    for identity in draw_order:
        row,bounded=records[identity]; room=by_room[row['room_id']]; position=room.index(identity)
        result.append({'message_id':identity,'source_record':copy.deepcopy(bounded),
            'context':{'before':[copy.deepcopy(records[x][1]) for x in room[max(0,position-neighbors):position]],
                       'after':[copy.deepcopy(records[x][1]) for x in room[position+1:position+1+neighbors]]}})
    return result


def _construct(question,positive_definition,negative_definition,exclusions):
    _text(question,'question',4000);_text(positive_definition,'positive_definition',2000)
    _text(negative_definition,'negative_definition',2000)
    if type(exclusions) is not list or len(exclusions)>16:
        raise ValueError('bounded_exclusions_required')
    for row in exclusions: _text(row,'exclusion',500)
    if len(set(exclusions))!=len(exclusions): raise ValueError('duplicate_exclusion')
    return {'question':question,'positive_definition':positive_definition,
            'negative_definition':negative_definition,'exclusions':copy.deepcopy(exclusions)}


def _current_instrument(instrument):
    result=copy.deepcopy(instrument)
    result['current_code_matches']=None if instrument['detector_id'] is None else hashlib.sha256(_DISCOVERY_PATH.read_bytes()).hexdigest()==instrument['discovery_sha256']
    result['loaded_code_matches']=None if instrument['detector_id'] is None else _DISCOVERY_LOADED_SHA==instrument['discovery_sha256']
    result['predictions_scope']='unavailable_no_instrument' if instrument.get('detector_id') is None else 'frozen_historical_regex'
    result.update(cheap_operator_check_performed=False,saved_predictions_match_current_operator=None,
                  prediction_attestation='not_applicable_no_instrument' if instrument['detector_id'] is None else 'historical_saved_predictions_unverified',
                  historical_execution_attested=False)
    return result


def _predictions(instrument,items,records):
    if instrument['detector_id'] is None:
        return {row['message_id']:{'available':False,'value':None,'label':None,'spans':[],
                'reason':'no_detector_selected'} for row in items}
    current=hashlib.sha256(_DISCOVERY_PATH.read_bytes()).hexdigest()
    if current!=_DISCOVERY_LOADED_SHA or _json(discovery.DETECTOR_DEFINITIONS)!=_json(_DEFINITIONS_LOADED) or discovery.DETECTOR_VERSION!=_DETECTOR_VERSION_LOADED:
        raise ValueError('detector_source_changed_before_sample_creation')
    outputs=discovery.detect_behaviors([records[row['message_id']][0] for row in items])
    predictions={}
    for output in outputs:
        label=instrument['detector_id'] in output['labels']
        spans=output['spans'].get(instrument['detector_id'],[])
        if len(spans)>128:raise ValueError('detector_span_budget_exceeded')
        predictions[output['message_id']]={'available':True,'value':label,'label':'yes' if label else 'no',
                'spans':copy.deepcopy(spans),'reason':None}
    if hashlib.sha256(_DISCOVERY_PATH.read_bytes()).hexdigest()!=current:
        raise ValueError('detector_source_changed_during_sample_creation')
    return predictions


def create_sample(store,dataset_ref,*,question,positive_definition,negative_definition,
                  exclusions=None,sample_size=16,seed=42,detector_id=None,context_neighbors=1):
    dataset=_load(store,dataset_ref,'dataset');construct=_construct(question,positive_definition,negative_definition,[] if exclusions is None else exclusions)
    _integer(sample_size,'sample_size',1,MAX_SAMPLE);_integer(seed,'seed',0,MAX_SEED)
    _integer(context_neighbors,'context_neighbors',0,2)
    if detector_id is not None and (type(detector_id) is not str or detector_id not in discovery.DETECTOR_DEFINITIONS):
        raise ValueError('unknown_predeclared_detector')
    records,rooms,types=_population(dataset['payload']);population_ids=sorted(records)
    if sample_size>len(population_ids):raise ValueError('sample_size_exceeds_population')
    draw_order=random.Random(seed).sample(population_ids,sample_size)
    items=_items(records,rooms,draw_order,context_neighbors)
    instrument={'detector_id':detector_id,'definition':None if detector_id is None else copy.deepcopy(discovery.DETECTOR_DEFINITIONS[detector_id]),
                'detector_version':None if detector_id is None else discovery.DETECTOR_VERSION,
                'discovery_sha256':None if detector_id is None else _DISCOVERY_LOADED_SHA,
                'question':question,'definition_scope':_DEFINITION_SCOPE}
    predictions=_predictions(instrument,items,records)
    identity=uuid.uuid4().hex[:12];sample_id='measurement_sample-'+identity;review_id='measurement_review-'+identity
    body={'sample_version':SAMPLE_VERSION,'name':question[:120],'dataset_ref':_ref(dataset_ref),'review_id':review_id,
          'construct':construct,'population_ids':population_ids,
          'design':{'population_size':len(population_ids),'sample_size':sample_size,'seed':seed,
                    'sampling':'python_random_sample_canonical_ids_without_replacement_v1',
                    'python_version':sys.version.split()[0],'population_ids_sha256':_sha(population_ids),
                    'draw_order':draw_order,'inclusion_probability':sample_size/len(population_ids),
                    'population_speaker_type_counts':types,'context_neighbors':context_neighbors,
                    'population_scope':_POPULATION_SCOPE},
          'instrument':instrument,'items':items,'predictions':predictions,'predictions_sha256':_sha(predictions),
          'labels':list(LABELS),'reviewer_modes':list(REVIEWER_MODES),'model_calls':0,
          'raw_source_reread':False,'calibration_established':False,'scope':_SCOPE}
    _clean_identity(body);sample=store.put('measurement_sample',body,sample_id)
    review={'review_version':REVIEW_VERSION,'sample_ref':_pin(sample),'judgments':[],
            'latest_label_policy':_LABEL_POLICY,'reviewer_provenance':_PROVENANCE,
            'model_calls':0,'calibration_established':False,'scope':_SCOPE}
    _clean_identity(review);store.put('measurement_review',review,review_id)
    return sample


def _sample(store,sample_ref):
    obj=_load(store,sample_ref,'measurement_sample');p=obj['payload']
    if set(p)!={'sample_version','name','dataset_ref','review_id','construct','population_ids','design','instrument','items','predictions','predictions_sha256','labels','reviewer_modes','model_calls','raw_source_reread','calibration_established','scope'} or p['sample_version']!=SAMPLE_VERSION:
        raise ValueError('supported_frozen_sample_required')
    if p['model_calls']!=0 or type(p['model_calls']) is not int or p['raw_source_reread'] is not False or p['calibration_established'] is not False or p['labels']!=list(LABELS) or p['reviewer_modes']!=list(REVIEWER_MODES) or p['scope']!=_SCOPE:
        raise ValueError('sample_scope_changed')
    _identity(p['review_id']);_construct(**p['construct'])
    if p['name']!=p['construct']['question'][:120]:raise ValueError('sample_title_changed')
    dataset=_load(store,p['dataset_ref'],'dataset');records,rooms,types=_population(dataset['payload']);ids=sorted(records);d=p['design']
    if type(d) is not dict or set(d)!={'population_size','sample_size','seed','sampling','python_version','population_ids_sha256','draw_order','inclusion_probability','population_speaker_type_counts','context_neighbors','population_scope'}:
        raise ValueError('frozen_design_shape_required')
    _integer(d['sample_size'],'sample_size',1,min(MAX_SAMPLE,len(ids)));_integer(d['seed'],'seed',0,MAX_SEED);_integer(d['context_neighbors'],'context_neighbors',0,2)
    if (p['population_ids']!=ids or d['population_size']!=len(ids) or type(d['population_size']) is not int or
            d['population_ids_sha256']!=_sha(ids) or type(d['inclusion_probability']) is not float or
            d['inclusion_probability']!=d['sample_size']/len(ids) or _json(d['population_speaker_type_counts'])!=_json(types) or
            d['population_scope']!=_POPULATION_SCOPE or type(d['python_version']) is not str or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',d['python_version']) or
            d['sampling']!='python_random_sample_canonical_ids_without_replacement_v1' or d['draw_order']!=random.Random(d['seed']).sample(ids,d['sample_size']) or
            _json(p['items'])!=_json(_items(records,rooms,d['draw_order'],d['context_neighbors']))):
        raise ValueError('frozen_population_draw_or_source_changed')
    instrument=p['instrument'];detector_id=instrument['detector_id']
    if set(instrument)!={'detector_id','definition','detector_version','discovery_sha256','question','definition_scope'} or instrument['question']!=p['construct']['question'] or instrument['definition_scope']!=_DEFINITION_SCOPE:
        raise ValueError('frozen_instrument_contract_changed')
    if detector_id is None:
        if any(instrument[key] is not None for key in ('definition','detector_version','discovery_sha256')):raise ValueError('no_detector_cannot_claim_instrument')
    elif (type(detector_id) is not str or detector_id not in discovery.DETECTOR_DEFINITIONS or
          type(instrument['definition']) is not dict or set(instrument['definition'])!={'description','non_examples'} or
          any(type(v) is not str for v in instrument['definition'].values()) or
          type(instrument['discovery_sha256']) is not str or not _SHA.fullmatch(instrument['discovery_sha256']) or type(instrument['detector_version']) is not str):
        raise ValueError('malformed_frozen_detector')
    if detector_id is not None and instrument['discovery_sha256']==_DISCOVERY_LOADED_SHA and (_json(instrument['definition'])!=_json(_DEFINITIONS_LOADED[detector_id]) or instrument['detector_version']!=_DETECTOR_VERSION_LOADED):
        raise ValueError('definition_disagrees_with_pinned_loaded_detector')
    predictions=p['predictions']
    if type(predictions) is not dict or set(predictions)!=set(d['draw_order']) or p['predictions_sha256']!=_sha(predictions):
        raise ValueError('frozen_prediction_digest_changed')
    for identity,row in predictions.items():
        if type(row) is not dict or set(row)!={'available','value','label','spans','reason'} or type(row['available']) is not bool or type(row['spans']) is not list or len(row['spans'])>128:
            raise ValueError('typed_frozen_prediction_required')
        if detector_id is None:
            if row!={'available':False,'value':None,'label':None,'spans':[],'reason':'no_detector_selected'}:raise ValueError('unselected_prediction_must_be_unknown')
        elif row['available'] is not True or type(row['value']) is not bool or row['label']!=('yes' if row['value'] else 'no') or row['reason'] is not None or bool(row['spans'])!=row['value']:
            raise ValueError('frozen_prediction_label_changed')
        for span in row['spans']:
            if type(span) is not dict or set(span)!={'start','end','text'}:raise ValueError('invalid_frozen_span')
            start=_integer(span['start'],'span_start',0,len(records[identity][0]['content']));end=_integer(span['end'],'span_end',start+1,len(records[identity][0]['content']))
            if span['text']!=records[identity][0]['content'][start:end]:raise ValueError('frozen_span_source_changed')
    status=_current_instrument(instrument)
    if detector_id is not None and status['current_code_matches'] is True and status['loaded_code_matches'] is True:
        recomputed=_predictions(instrument,p['items'],records)
        if _json(recomputed)!=_json(predictions):
            raise ValueError('saved_predictions_disagree_with_current_pinned_regex')
        status.update(cheap_operator_check_performed=True,saved_predictions_match_current_operator=True,
                      prediction_attestation='matches_current_pinned_regex')
    obj['_instrument_status']=status  # Read-only status, never persisted into the frozen sample.
    return obj


def _review(store,sample,review_ref):
    obj=_load(store,review_ref,'measurement_review');p=obj['payload']
    if obj['id']!=sample['payload']['review_id'] or p.get('review_version')!=REVIEW_VERSION or _ref(p.get('sample_ref'))!=_pin(sample):
        raise ValueError('review_exact_sample_binding_required')
    if set(p)!={'review_version','sample_ref','judgments','latest_label_policy','reviewer_provenance','model_calls','calibration_established','scope'} or p['model_calls']!=0 or type(p['model_calls']) is not int or p['calibration_established'] is not False or p['scope']!=_SCOPE or p['latest_label_policy']!=_LABEL_POLICY or p['reviewer_provenance']!=_PROVENANCE:
        raise ValueError('review_contract_changed')
    rows=p['judgments']
    if type(rows) is not list or len(rows)>MAX_EVENTS or obj['version']!=len(rows)+1:
        raise ValueError('bounded_sequenced_review_required')
    for sequence,row in enumerate(rows,1):
        if type(row) is not dict or set(row)!={'sequence','message_id','label','reason','reviewer_id','reviewer_mode','recorded_at','predictions_visible'} or row['sequence']!=sequence or type(row['sequence']) is not int or type(row['predictions_visible']) is not bool:
            raise ValueError('judgment_sequence_changed')
        _judgment(sample,row['message_id'],row['label'],row['reason'],row['reviewer_id'],row['reviewer_mode']);_timestamp(row['recorded_at'])
    return obj


def _judgment(sample,message_id,label,reason,reviewer_id,reviewer_mode):
    _identity(message_id);_identity(reviewer_id);_text(reviewer_id,'reviewer_id',80)
    if message_id not in sample['payload']['design']['draw_order']:raise ValueError('judgment_requires_sampled_message')
    if type(label) is not str or label not in LABELS:raise ValueError('yes_no_or_uncertain_required')
    if type(reviewer_mode) is not str or reviewer_mode not in REVIEWER_MODES:raise ValueError('declared_reviewer_mode_required')
    _text(reason,'reason',1000)


def record_judgment(store,sample_ref,message_id,label,reason,reviewer_id,reviewer_mode,expected_review_version,*,predictions_visible=False):
    _integer(expected_review_version,'expected_review_version',1,MAX_EVENTS+1)
    if type(predictions_visible) is not bool:raise ValueError('typed_declared_prediction_visibility_required')
    sample=_sample(store,sample_ref);review_id=sample['payload']['review_id']
    expected=store.get(review_id,expected_review_version);review=_review(store,sample,_pin(expected))
    if len(review['payload']['judgments'])>=MAX_EVENTS:raise ValueError('judgment_event_budget_exceeded')
    _judgment(sample,message_id,label,reason,reviewer_id,reviewer_mode)
    body=copy.deepcopy(review['payload']);body['judgments'].append({'sequence':len(body['judgments'])+1,'message_id':message_id,
        'label':label,'reason':reason,'reviewer_id':reviewer_id,'reviewer_mode':reviewer_mode,'recorded_at':now(),'predictions_visible':predictions_visible})
    _clean_identity(body)
    return store.compare_and_put('measurement_review',body,review_id,
              expected_version=review['version'],expected_hash=review['hash'])


def sample_packet(store,sample_ref,review_ref,*,include_predictions=False):
    if type(include_predictions) is not bool:raise ValueError('typed_prediction_visibility_required')
    sample=_sample(store,sample_ref);review=_review(store,sample,review_ref);p=sample['payload'];rows=review['payload']['judgments'];items=[]
    for item in p['items']:
        judgments=[copy.deepcopy(row) for row in rows if row['message_id']==item['message_id']]
        items.append({**copy.deepcopy(item),'prediction':copy.deepcopy(p['predictions'][item['message_id']]) if include_predictions else None,
                      'current_judgment':judgments[-1] if judgments else None,'prior_judgments':judgments[:-1]})
    return {'packet_version':PACKET_VERSION,'sample_ref':_pin(sample),'review_ref':_pin(review),'dataset_ref':p['dataset_ref'],
            'construct':p['construct'],'design':p['design'],'instrument':sample['_instrument_status'],
            'items':items,'predictions_included':include_predictions,'blinding_authenticated':False,
            'labels':list(LABELS),'reviewer_modes':list(REVIEWER_MODES),'model_calls':0,'calibration_established':False,
            'latest_label_policy':review['payload']['latest_label_policy'],'scope':_SCOPE}


def review_report(store,sample_ref,review_ref):
    sample=_sample(store,sample_ref);review=_review(store,sample,review_ref);p=sample['payload'];rows=review['payload']['judgments'];latest={}
    for row in rows:latest[row['message_id']]=row
    counts={key:0 for key in (*LABELS,'missing')};modes={mode:{key:0 for key in LABELS} for mode in REVIEWER_MODES}
    confusion={key:0 for key in ('true_positive','false_positive','false_negative','true_negative')};compared=0;available=0;conflicts=[]
    for identity in p['design']['draw_order']:
        current=latest.get(identity);label=current['label'] if current else 'missing';counts[label]+=1
        if current:modes[current['reviewer_mode']][label]+=1
        prediction=p['predictions'][identity];available+=prediction['available'] is True
        if label in ('yes','no') and prediction['available'] is True:
            compared+=1; key=('true_positive' if prediction['value'] else 'false_negative') if label=='yes' else ('false_positive' if prediction['value'] else 'true_negative');confusion[key]+=1
        history=[row for row in rows if row['message_id']==identity];labels=sorted({row['label'] for row in history})
        if len(labels)>1:conflicts.append({'message_id':identity,'labels':labels,'reviewer_ids':sorted({row['reviewer_id'] for row in history})})
    metrics={'available':compared>0,'reason':None if compared else 'no_known_label_and_available_prediction_pairs',
             'confusion':confusion if compared else None,'agreement':None,'precision':None,'recall':None}
    if compared:
        tp,fp,fn,tn=(confusion[key] for key in ('true_positive','false_positive','false_negative','true_negative'))
        metrics.update(agreement={'numerator':tp+tn,'denominator':compared,'fraction':(tp+tn)/compared},
                       precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None)
    return {'report_version':REPORT_VERSION,'sample_ref':_pin(sample),'review_ref':_pin(review),'dataset_ref':p['dataset_ref'],
            'totals':{'sample_size':p['design']['sample_size'],'known_labels':counts['yes']+counts['no'],'uncertain_labels':counts['uncertain'],
                      'missing_labels':counts['missing'],'available_predictions':available,
                      'unavailable_predictions':p['design']['sample_size']-available,'compared_messages':compared},
            'current_label_counts':counts,'current_labels_by_mode':modes,'conflicting_declarations':conflicts,
            'metrics':metrics,'instrument':sample['_instrument_status'],'model_calls':0,'calibration_established':False,
            'prediction_visibility':{'current_declarations':{'visible':sum(row['predictions_visible'] for row in latest.values()),'hidden':sum(not row['predictions_visible'] for row in latest.values())},
                'all_declarations':{'visible':sum(row['predictions_visible'] for row in rows),'hidden':sum(not row['predictions_visible'] for row in rows)},
                'scope':'Reviewer-declared UI exposure only; not authenticated blinding or evidence of independence.'},
            'reviewer_provenance':review['payload']['reviewer_provenance'],
            'latest_label_policy':review['payload']['latest_label_policy'],'scope':_SCOPE}

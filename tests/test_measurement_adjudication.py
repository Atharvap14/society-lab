"""Temporary CPU-only measurement review workflow and adversarial boundaries."""
import concurrent.futures
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm_lab.dataset import normalize_message
from swarm_lab.store import Store, StoreConflictError

from swarm_lab import measurement_adjudication as a


def pin(obj):return {key:obj[key] for key in ('id','version','hash')}


class MeasurementAdjudicationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=Store(self.root/'lab.sqlite3')
        texts=['I am waiting for the export.', "Another agent said: 'I am waiting for the export.'",
               'We can proceed.', 'The owner needs another day.', 'We are waiting for a file.', 'Unrelated new task.']
        self.messages=[normalize_message({'id':f'm{i}','agent_id':'agent1','agent_name':'Fixture agent',
            'speaker_type':'agent' if i<5 else 'user','timestamp':f'2025-04-18T18:0{i}:00Z',
            'room_id':'room1' if i!=5 else 'room2','content':text,
            'source':{'file':'fixture.jsonl','line':i+1,'table':'chat_messages'}}) for i,text in enumerate(texts)]
        self.dataset=self.store.put('dataset',{'messages':self.messages})
        self.options={'question':'Does the speaker explicitly report a dependency blocker?',
            'positive_definition':'A stated inability to proceed on an explicit dependency.',
            'negative_definition':'No speaker-owned stated obstruction.', 'exclusions':['Quoted claims of another agent are excluded.'],
            'sample_size':6,'seed':42,'detector_id':'blocker_report','context_neighbors':1}

    def create(self,**changes):return a.create_sample(self.store,pin(self.dataset),**{**self.options,**changes})
    def review(self,sample):return self.store.get(sample['payload']['review_id'])
    def judge(self,sample,identity,label,mode='synthetic_fixture',expected=None,**extra):
        review=self.review(sample)
        return a.record_judgment(self.store,pin(sample),identity,label,'Authored fixture declaration.',
            'fixture-reviewer',mode,review['version'] if expected is None else expected,**extra)

    def test_canonical_sampling_is_reproducible_and_context_never_crosses_room(self):
        first=self.create(sample_size=3,context_neighbors=2)
        reversed_dataset=self.store.put('dataset',{'messages':list(reversed(self.messages))})
        other=a.create_sample(self.store,pin(reversed_dataset),**{**self.options,'sample_size':3,'context_neighbors':2})
        self.assertEqual(first['payload']['design']['draw_order'],other['payload']['design']['draw_order'])
        self.assertEqual(first['payload']['population_ids'],sorted(row['id'] for row in self.messages))
        self.assertEqual(first['payload']['design']['inclusion_probability'],.5)
        self.assertEqual(first['payload']['design']['population_speaker_type_counts'],{'agent':5,'user':1})
        for item in first['payload']['items']:
            for row in item['context']['before']+item['context']['after']:
                self.assertEqual(row['room_id'],item['source_record']['room_id'])
                self.assertNotEqual(row['id'],item['message_id'])
        self.assertEqual(first['version'],1);self.assertEqual(self.review(first)['version'],1)

    def test_known_uncertain_and_missing_labels_have_distinct_denominators(self):
        sample=self.create()
        for identity,label in [('m0','yes'),('m1','no'),('m2','no'),('m3','yes'),('m4','uncertain')]:
            self.judge(sample,identity,label)
        review=self.review(sample);report=a.review_report(self.store,pin(sample),pin(review))
        self.assertEqual(report['totals'],{'sample_size':6,'known_labels':4,'uncertain_labels':1,'missing_labels':1,
            'available_predictions':6,'unavailable_predictions':0,'compared_messages':4})
        self.assertEqual(report['metrics']['confusion'],{'true_positive':1,'false_positive':1,'false_negative':1,'true_negative':1})
        self.assertEqual(report['metrics']['agreement'],{'numerator':2,'denominator':4,'fraction':.5})
        self.assertEqual(report['metrics']['precision'],.5);self.assertEqual(report['metrics']['recall'],.5)
        self.assertFalse(report['calibration_established']);self.assertEqual(report['model_calls'],0)
        self.assertTrue(report['instrument']['cheap_operator_check_performed'])
        self.assertTrue(report['instrument']['saved_predictions_match_current_operator'])
        self.assertFalse(report['instrument']['historical_execution_attested'])
        self.assertIn('not consensus',report['scope']);self.assertIn('population accuracy',report['scope'])
        packet=a.sample_packet(self.store,pin(sample),pin(review))
        self.assertTrue(all(row['prediction'] is None for row in packet['items']))
        visible=a.sample_packet(self.store,pin(sample),pin(review),include_predictions=True)
        self.assertTrue(all(type(row['prediction']['value']) is bool for row in visible['items']))
        self.assertFalse(visible['blinding_authenticated']);self.assertEqual(self.store.usage()['calls'],0)
        self.assertEqual(self.store.list('behavior'),[])

    def test_free_binary_question_is_useful_without_predictions(self):
        with patch.object(a.discovery,'detect_behaviors',side_effect=AssertionError('No detector call')):
            sample=self.create(detector_id=None);review=self.judge(sample,'m0','yes','manual_operator')
            report=a.review_report(self.store,pin(sample),pin(review))
        self.assertEqual(report['totals']['known_labels'],1);self.assertEqual(report['totals']['unavailable_predictions'],6)
        self.assertFalse(report['metrics']['available']);self.assertIsNone(report['metrics']['confusion'])
        self.assertIsNone(report['metrics']['agreement']);self.assertIsNone(report['instrument']['current_code_matches'])

    def test_latest_declaration_preserves_disagreement_provenance_and_old_exact_review(self):
        sample=self.create();old=self.judge(sample,'m0','yes','manual_operator')
        current=self.judge(sample,'m0','no','agent_assisted',predictions_visible=True)
        report=a.review_report(self.store,pin(sample),pin(current))
        self.assertEqual(report['current_label_counts'],{'yes':0,'no':1,'uncertain':0,'missing':5})
        self.assertEqual(report['current_labels_by_mode']['manual_operator']['yes'],0)
        self.assertEqual(report['current_labels_by_mode']['agent_assisted']['no'],1)
        self.assertEqual(report['conflicting_declarations'][0]['labels'],['no','yes'])
        self.assertEqual(report['prediction_visibility']['all_declarations'],{'visible':1,'hidden':1})
        packet=a.sample_packet(self.store,pin(sample),pin(current));row=next(x for x in packet['items'] if x['message_id']=='m0')
        self.assertEqual(row['current_judgment']['label'],'no');self.assertEqual(row['prior_judgments'][0]['label'],'yes')
        historical=a.review_report(self.store,pin(sample),pin(old))
        self.assertEqual(historical['current_label_counts']['yes'],1)
        self.assertIn('declared',report['reviewer_provenance']);self.assertIn('not consensus',report['latest_label_policy'])

    def test_cas_rejects_stale_and_concurrent_writers_without_lost_updates(self):
        sample=self.create()
        def writer(identity):
            try:return self.judge(sample,identity,'yes',expected=1)
            except StoreConflictError:return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as workers:
            results=list(workers.map(writer,['m0','m1']))
        self.assertEqual(sum(x=='conflict' for x in results),1)
        self.assertEqual(self.review(sample)['version'],2)
        self.assertEqual(len(self.review(sample)['payload']['judgments']),1)
        with self.assertRaises(StoreConflictError):self.judge(sample,'m2','no',expected=1)
        self.assertEqual(self.store.get(sample['id'])['version'],1)

    def test_strict_typed_creation_and_source_failures_leave_no_samples(self):
        for changes in [{'seed':True},{'seed':2**53},{'sample_size':True},{'sample_size':7},
                        {'context_neighbors':3},{'exclusions':False},{'detector_id':'made_up'},
                        {'question':''},{'positive_definition':'x'*2001}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.create(**changes)
        for defect in ['duplicate','source','naive_timestamp','content_hash']:
            rows=copy.deepcopy(self.messages)
            if defect=='duplicate':rows[1]['id']=rows[0]['id']
            elif defect=='source':rows[0].pop('source')
            elif defect=='naive_timestamp':rows[0]['timestamp']='2025-04-18T18:00:00'
            else:rows[0]['content_hash']='wrong'
            bad=self.store.put('dataset',{'messages':rows})
            with self.subTest(defect=defect),self.assertRaises(ValueError):a.create_sample(self.store,pin(bad),**self.options)
        self.assertEqual(self.store.list('measurement_sample'),[]);self.assertEqual(self.store.list('measurement_review'),[])

    def test_exact_refs_forged_source_context_predictions_and_flags_reject(self):
        sample=self.create();review=self.review(sample)
        for changes in [{'version':True},{'hash':'f'*64},{'extra':'no'}]:
            bad={**pin(sample),**changes}
            with self.assertRaises(ValueError):a.sample_packet(self.store,bad,pin(review))
        attacks=[lambda p:p['items'][0]['source_record'].__setitem__('content','Forged excerpt'),
            lambda p:p['design'].__setitem__('inclusion_probability',True),
            lambda p:p['design'].__setitem__('extra','unregistered'),
            lambda p:p['predictions'][p['design']['draw_order'][0]].__setitem__('value',None),
            lambda p:p.__setitem__('model_calls',False),
            lambda p:p['instrument']['definition'].__setitem__('description','Changed definition')]
        for attack in attacks:
            body=copy.deepcopy(sample['payload']);attack(body);forged=self.store.put('measurement_sample',body)
            with self.assertRaises(ValueError):a.sample_packet(self.store,pin(forged),pin(review))
        wrong_review=self.store.put('measurement_review',review['payload'])
        with self.assertRaises(ValueError):a.review_report(self.store,pin(sample),pin(wrong_review))

    def test_historical_predictions_survive_code_drift_without_detector_reexecution(self):
        sample=self.create();review=self.judge(sample,'m0','yes');producer=self.root/'changed_discovery.py';producer.write_text('Changed producer bytes',encoding='utf-8')
        with patch.object(a,'_DISCOVERY_PATH',producer),patch.object(a.discovery,'detect_behaviors',side_effect=AssertionError('No rerun')):
            report=a.review_report(self.store,pin(sample),pin(review))
            self.assertFalse(report['instrument']['current_code_matches'])
            self.assertEqual(report['instrument']['predictions_scope'],'frozen_historical_regex')
            self.assertEqual(report['instrument']['prediction_attestation'],'historical_saved_predictions_unverified')
            self.assertFalse(report['instrument']['cheap_operator_check_performed'])
            self.assertIsNone(report['instrument']['saved_predictions_match_current_operator'])
            self.assertEqual(report['metrics']['agreement']['fraction'],1)
            self.judge(sample,'m2','no')
            with self.assertRaises(ValueError):self.create()

    def test_resealed_predictions_cannot_borrow_current_pinned_operator_identity(self):
        for identity,label,prediction in [
            ('m0','yes',{'available':True,'value':False,'label':'no','spans':[],'reason':None}),
            ('m2','no',{'available':True,'value':True,'label':'yes','spans':[{'start':0,'end':2,'text':'We'}],'reason':None})]:
            sample=self.create();initial=self.review(sample);body=copy.deepcopy(sample['payload'])
            body['predictions'][identity]=prediction;body['predictions_sha256']=a._sha(body['predictions'])
            forged=self.store.put('measurement_sample',body,sample['id'])
            review_body=copy.deepcopy(initial['payload']);review_body['sample_ref']=pin(forged)
            review_body['judgments']=[{'sequence':1,'message_id':identity,'label':label,'reason':'Synthetic declared label.',
                'reviewer_id':'fixture','reviewer_mode':'synthetic_fixture','recorded_at':'2026-10-04T06:00:00+00:00','predictions_visible':False}]
            review=self.store.put('measurement_review',review_body,initial['id'])
            with self.subTest(identity=identity),self.assertRaisesRegex(ValueError,'current_pinned_regex'):
                a.review_report(self.store,pin(forged),pin(review))

    def test_bounded_excerpts_keep_full_hash_and_only_source_coordinates(self):
        rows=copy.deepcopy(self.messages);rows[0]['content']='x'*2001+' waiting for an export.'
        rows[0]['source']['provider_response']={'private':'UNNECESSARY_PROVIDER_PAYLOAD'}
        source=self.store.put('dataset',{'messages':rows})
        sample=a.create_sample(self.store,pin(source),**self.options)
        record=next(x['source_record'] for x in sample['payload']['items'] if x['message_id']=='m0')
        self.assertEqual(len(record['content']),2000);self.assertTrue(record['content_truncated'])
        self.assertEqual(record['source'],{'file':'fixture.jsonl','line':1,'table':'chat_messages'})
        self.assertNotIn('UNNECESSARY_PROVIDER_PAYLOAD',json.dumps(sample))
        self.assertTrue(sample['payload']['predictions']['m0']['value'])
        self.assertGreater(sample['payload']['predictions']['m0']['spans'][0]['start'],2000)

    def test_judgment_unknown_types_visibility_and_redaction_stop_before_write(self):
        sample=self.create();before=self.review(sample)
        for args in [('outside','yes','manual_operator',1,False),('m0','unknown','manual_operator',1,False),
                     ('m0','yes','human_ground_truth',1,False),('m0','yes','manual_operator',True,False),
                     ('m0','yes','manual_operator',1,1)]:
            with self.assertRaises(ValueError):a.record_judgment(self.store,pin(sample),args[0],args[1],
                'Reason','reviewer',args[2],args[3],predictions_visible=args[4])
        with self.assertRaises(ValueError):a.record_judgment(self.store,pin(sample),'m0','yes',
            'Synthetic token shape hf_'+'X'*25,'reviewer','synthetic_fixture',1)
        self.assertEqual(self.review(sample),before)
        with self.assertRaises(ValueError):a.sample_packet(self.store,pin(sample),pin(before),include_predictions=1)


if __name__=='__main__':unittest.main()

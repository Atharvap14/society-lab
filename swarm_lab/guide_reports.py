"""Script-free visual reports from an exact saved analysis, never model HTML."""
import html
import math
import re
import base64
import hashlib
import json
from pathlib import Path
import struct

KINDS = {'dataset', 'village_access_experiment','village_recovery_experiment'}
MAX_PLOT_BYTES = 800 * 1024
MAX_PLOT_METADATA_BYTES = 128 * 1024


def _bounded_read(path, maximum):
    with path.open('rb') as stream:
        value = stream.read(maximum + 1)
    if len(value) > maximum:
        raise ValueError('Cached figure exceeds its bound.')
    return value


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Ambiguous plot metadata.')
        value[key] = item
    return value


def _cached_plot(ref, cache_root, *, dataset_plot=None):
    """Display only a bounded, exact-source PNG cache; missing caches are optional."""
    try:
        if cache_root is None or not isinstance(ref, dict) or set(ref) != {'id', 'version', 'hash'} or type(ref['version']) is not int or type(ref['hash']) is not str or not re.fullmatch(r'[a-f0-9]{64}', ref['hash']):
            return ''
        directory = Path(cache_root) / ref['hash']
        if dataset_plot not in (None, 'activity', 'names'):
            return ''
        metadata_name = 'source.json' if dataset_plot is None else 'source-' + dataset_plot + '.json'
        image_name = 'analysis.png' if dataset_plot is None else dataset_plot + '.png'
        expected_schema = 'societylab.experiment-plots.v1' if dataset_plot is None else 'societylab.dataset-plots.v1'
        raw = _bounded_read(directory / metadata_name, MAX_PLOT_METADATA_BYTES)
        metadata = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite metadata.')))
        source = metadata.get('source_ref') if isinstance(metadata, dict) else None
        if not isinstance(source, dict) or set(source) != set(ref) or type(source.get('id')) is not str or type(source.get('version')) is not int or type(source.get('hash')) is not str or source != ref or metadata.get('schema') != expected_schema:
            return ''
        caption = metadata.get('caption')
        if type(caption) is not str or not 1 <= len(caption) <= 2000:
            return ''
        png = _bounded_read(directory / image_name, MAX_PLOT_BYTES)
        if len(png) < 45 or not png.startswith(b'\x89PNG\r\n\x1a\n') or png[8:16] != b'\x00\x00\x00\rIHDR' or png[-12:] != b'\x00\x00\x00\x00IEND\xaeB`\x82' or hashlib.sha256(png).hexdigest() != metadata.get('image_sha256'):
            return ''
        width, height = struct.unpack('>II', png[16:24])
        if not 1 <= width <= 6000 or not 1 <= height <= 4000 or width * height > 20_000_000:
            return ''
        image = base64.b64encode(png).decode('ascii')
        if dataset_plot:
            title = 'When agents posted' if dataset_plot == 'activity' else 'Names appearing together'
            return '<section><h2>' + title + '</h2><figure style="margin:0"><img style="width:100%;height:auto" alt="' + title + ' in the exact retained source" src="data:image/png;base64,' + image + '"><figcaption>' + html.escape(caption, quote=True) + '</figcaption></figure><small>Source-bound cached Matplotlib figure. It describes retained posts, not confirmed receipt, influence or causation.</small></section>'
        return '<section><h2>Recorded action sequences and outcomes</h2><figure style="margin:0"><img style="width:100%;height:auto" alt="Exact saved-study effect intervals, recorded team action sequences and outcome measures" src="data:image/png;base64,' + image + '"><figcaption>' + html.escape(caption, quote=True) + '</figcaption></figure><small>Cached Matplotlib figure; exact saved source and PNG byte hash checked. This is not a fresh execution or source-data reread.</small></section>'
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, struct.error):
        return ''

def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _exact_ref(value):
    return (isinstance(value, dict) and set(value) == {'id', 'version', 'hash'}
            and type(value.get('id')) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', value['id'])
            and type(value.get('version')) is int and 1 <= value['version'] <= 10**9
            and type(value.get('hash')) is str and re.fullmatch(r'[a-f0-9]{64}', value['hash']))


def _village_contract(payload, *, recovery=False):
    if (not isinstance(payload, dict) or payload.get('agent_mode') != 'live'
            or any(not isinstance(payload.get(key), dict) for key in ('protocol', 'source_refs', 'fidelity', 'hypothesis'))):
        raise ValueError('A Village result requires its saved live source and fidelity contract.')
    protocol = payload.get('protocol', {}); grounding = protocol.get('grounding', {})
    source = payload.get('source_refs', {}).get('dataset_ref')
    fidelity = payload.get('fidelity', {}); hypothesis = payload.get('hypothesis', {})
    if any(not isinstance(protocol.get(key), dict) for key in ('environment', 'grounding', 'hypothesis', 'fidelity')):
        raise ValueError('The source-grounded protocol contract is incomplete.')
    evidence = grounding.get('evidence_ids')
    if (protocol.get('environment', {}).get('kind') != ('single_document_reference_repair' if recovery else 'village_document_access_repair')
            or (recovery and protocol.get('primary_outcome')!='verified_repaired_reference')
            or not _exact_ref(source) or not _exact_ref(grounding.get('source_ref'))
            or source != grounding['source_ref'] or not isinstance(evidence, list) or not 1 <= len(evidence) <= 64
            or any(type(v) is not str or not 1 <= len(v) <= 200 for v in evidence)
            or type(hypothesis.get('statement')) is not str or not 1 <= len(hypothesis['statement']) <= 4000
            or protocol.get('hypothesis', {}).get('statement') != hypothesis['statement']
            or fidelity.get('historical_equivalence') is not False
            or protocol.get('fidelity', {}).get('historical_equivalence') is not False):
        raise ValueError('This Village study requires a complete exact source, hypothesis and fidelity contract.')
    for field in ('represented', 'approximated', 'omitted'):
        values = fidelity.get(field)
        if (not isinstance(values, list) or len(values) > 64
                or any(type(v) is not str or not 1 <= len(v) <= 4000 for v in values)
                or values != protocol['fidelity'].get(field)):
            raise ValueError('The saved fidelity contract is inconsistent.')
    if not fidelity['represented']:
        raise ValueError('The represented mechanism must be declared.')
    escape = lambda value: html.escape(str(value), quote=True)
    task=('Verified repaired-reference outcomes: the assigned auditor must actually open the current one correct original, under a canonical-reference check versus a neutral note. Both arms share this explicit common goal; queued references and inspections are secondary process measures.' if recovery else 'Verified usable-project outcomes under canonical project checking versus a neutral note, across whole teams in the saved access world. Avoidable recreations are a separate process measure.')
    parts = '<section><h2>Source, hypothesis and simulator fidelity</h2><p><strong>Source episode:</strong> ' + escape(source['id']) + ' · version ' + str(source['version']) + '<br><small>' + escape(source['hash']) + '</small></p><p><strong>Hypothesis:</strong> ' + escape(hypothesis['statement']) + '</p><p><strong>Task and estimand:</strong> ' + escape(task) + '</p>'
    parts += '<details><summary>Cited source records</summary><p>' + ' · '.join(escape(v) for v in evidence) + '</p></details>'
    for field, title in [('represented', 'Represented mechanisms'), ('approximated', 'Approximated state and tools'), ('omitted', 'Omitted state')]:
        parts += '<h3>' + title + '</h3>' + ('<ul>' + ''.join('<li>' + escape(v) + '</li>' for v in fidelity[field]) + '</ul>' if fidelity[field] else '<p>None declared in this contract. Do not infer additional capabilities.</p>')
    return parts + '<p>Historical equivalence is unestablished. Source observations motivate this task; replay and outcome checks do not establish the historical explanation or simulator fidelity.</p></section>'

def report_ref(query):
    if set(query) != {'object_id', 'version', 'hash'} or any(len(v) != 1 for v in query.values()):
        raise ValueError('Supply one exact object_id, version and hash.')
    object_id, version, digest = (query[k][0] for k in ('object_id', 'version', 'hash'))
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', object_id) or not re.fullmatch(r'[1-9][0-9]{0,8}', version) or not re.fullmatch(r'[a-f0-9]{64}', digest):
        raise ValueError('Use an exact saved report reference.')
    return {'id': object_id, 'version': int(version), 'hash': digest}

def render_report(store, ref):
    if not isinstance(ref, dict) or set(ref) != {'id', 'version', 'hash'}:
        raise ValueError('Use one exact saved reference.')
    report_ref({'object_id': [ref['id']], 'version': [str(ref['version'])], 'hash': [ref['hash']]})
    record = store.get(ref['id'], ref['version'])
    if record['hash'] != ref['hash']:
        raise ValueError('The report fingerprint does not match this saved result.')
    if record['kind'] not in KINDS:
        raise ValueError('Choose AI Village observations or a source-grounded Village experiment.')
    e = lambda value: html.escape(str(value), quote=True)
    store_path = getattr(store, 'path', None)
    if record['kind'] == 'dataset':
        cache_root = Path(store_path).parent / 'plots' if store_path is not None else None
        figures = ''.join(_cached_plot(ref, cache_root, dataset_plot=kind) for kind in ('activity', 'names'))
        messages = record['payload'].get('messages', [])
        if not isinstance(messages, list):
            messages = []
        return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AI Village observational analytics</title><style>body{font:15px/1.6 system-ui;background:#f9faf5;color:#283f3b;margin:0;padding:20px}h1{font-size:23px}h2{font-size:18px}img{width:100%;height:auto}figcaption,small,footer{font-size:12px;overflow-wrap:anywhere}section{margin:20px 0}</style></head><body><h1>Observational analytics: what the logs show</h1><p>' + str(len(messages)) + ' retained messages. These observations are not an intervention experiment.</p>' + (figures or '<p>No scientific figure is cached for this source yet. Its exact messages remain available in replay.</p>') + '<p>Missing audience and tool state stay unknown. A name appearing in a post does not prove that agent received or read it.</p><footer>Source: ' + e(record['id']) + ' · version ' + str(record['version']) + '<br>Fingerprint: ' + e(record['hash']) + '</footer></body></html>'
    recovery=record['kind']=='village_recovery_experiment'
    plot_html = _village_contract(record['payload'],recovery=recovery)
    plot_html += _cached_plot(ref, Path(store_path).parent / 'plots' if store_path is not None else None)
    metric_label = 'Verified repaired reference' if recovery else 'Verified usable project'
    payload = record['payload']
    analysis = payload.get('analysis', {})
    arms = analysis.get('arms', {})
    if not isinstance(arms, dict):
        arms = {}
    labels = {'neutral_note': 'Neutral note', 'canonical_check': 'Canonical reference check' if recovery else 'Canonical project check'}
    rows, bars = [], []
    for index, (arm, stats) in enumerate((arm, arms[arm]) for arm in ('neutral_note', 'canonical_check') if arm in arms):
        if not isinstance(stats, dict):
            continue
        n, rate = stats.get('n'), stats.get('success_rate' if recovery else 'success')
        name = labels.get(arm, str(arm).replace('_', ' ')[:120])
        if type(n) is not int or n < 1 or not _number(rate) or not 0 <= rate <= 1:
            continue
        y = 42 + len(rows) * 48
        color = ['#8d9f86', '#997fa6', '#2b827a'][index % 3]
        rows.append(f'<tr><th>{e(name)}</th><td>{n}</td><td>{rate:.1%}</td></tr>')
        bars.append(f'<text x="8" y="{y+15}">{e(name)}</text><rect x="185" y="{y}" width="260" height="22" rx="5" fill="#e8eee5"/><rect x="185" y="{y}" width="{rate*260:.3f}" height="22" rx="5" fill="{color}"/><text x="458" y="{y+15}">{rate:.0%}</text>')
    primary = analysis.get('primary_effect', {})
    if not isinstance(primary, dict):
        primary = {}
    diff, interval = primary.get('difference'), primary.get('ci95')
    effect_html = ''
    if _number(diff) and isinstance(interval, list) and len(interval) == 2 and all(_number(v) for v in interval) and -1 <= interval[0] <= interval[1] <= 1 and -1 <= diff <= 1:
        x = lambda value: 40 + (value + 1) * 230
        effect_html = f'<section><h2>What changed?</h2><p>{"Canonical reference check" if recovery else "Canonical project check"} minus neutral note: <b>{diff*100:+.1f} percentage points</b>.</p><svg viewBox="0 0 540 100" role="img" aria-label="Difference {diff*100:+.1f} percentage points; 95 percent interval {interval[0]*100:+.1f} to {interval[1]*100:+.1f}"><line x1="270" y1="10" x2="270" y2="65" stroke="#8c998c" stroke-dasharray="4 4"/><line x1="{x(interval[0]):.3f}" y1="35" x2="{x(interval[1]):.3f}" y2="35" stroke="#2b827a" stroke-width="5"/><circle cx="{x(diff):.3f}" cy="35" r="7" fill="#2b827a"/><text x="40" y="88">−100 points</text><text x="270" y="88" text-anchor="middle">No change</text><text x="500" y="88" text-anchor="end">+100 points</text></svg><p>95% interval: {interval[0]*100:+.1f} to {interval[1]*100:+.1f} points. {"The interval includes no change. This pilot is inconclusive." if interval[0] <= 0 <= interval[1] else "This interval excludes no change within this tested environment."}</p><small>Saved interval method: {e(primary.get("interval_method", "unspecified"))}. Effects use matched whole-team differences; individual agents are not independent trials.</small></section>'
    chart = f'<svg viewBox="0 0 540 {max(100,42+len(rows)*48)}" role="img" aria-label="{metric_label} rate by condition">{"".join(bars)}</svg><table><thead><tr><th>Condition</th><th>Team runs</th><th>{metric_label}</th></tr></thead><tbody>{"".join(rows)}</tbody></table>' if rows else '<p>This result has no compatible success rates. Open the saved result to inspect its own measurements.</p>'
    warnings = analysis.get('warnings', [])
    warning_html = ''.join(f'<li>{e(w[:1000])}</li>' for w in warnings[:8] if isinstance(w, str)) if isinstance(warnings, list) else ''
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Saved experiment analysis</title><style>body{{font:15px/1.6 system-ui;color:#283f3b;background:#f9faf5;margin:0;padding:22px}}h1{{font-size:23px;line-height:1.2}}h2{{font-size:18px}}svg{{width:100%;height:auto}}svg text{{font:12px system-ui;fill:#41544b}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;border-bottom:1px solid #dce5d8;padding:8px;font-size:12px}}section{{margin-top:24px}}small,footer{{font-size:11px;overflow-wrap:anywhere;color:#586c61}}p{{margin:10px 0}}.tag{{color:#2b827a;font-size:11px;font-weight:bold;letter-spacing:.1em}}@media(max-width:420px){{body{{padding:12px}}}}</style></head><body><span class="tag">SAVED EXPERIMENT · VERSION {record["version"]}</span><h1>What happened in the test?</h1><p>Rates below come from the saved analysis. Execution mode and evidence remain in the exact source record.</p>{plot_html}{chart}{effect_html}<section><h2>What this tells us</h2><p>These measurements apply to the saved document-access world and fresh agent teams. They do not establish the historical cause of the AI Village episode.</p><ul>{warning_html}</ul></section><footer>Source: {e(record["id"])} · version {record["version"]}<br>Fingerprint: {e(record["hash"])}</footer></body></html>'

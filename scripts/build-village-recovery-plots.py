"""Read-only, exact-source Matplotlib figures for completed single-document Village reference-recovery studies."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_lab.guide_reports import _exact_ref, _village_contract
from swarm_lab.store import Store, fingerprint

FAMILY = 'single_document_reference_repair'
PRIMARY = 'verified_repaired_reference'
ARMS = ('neutral_note', 'canonical_check')
LABELS = {'neutral_note': 'Neutral note', 'canonical_check': 'Canonical access check'}
COLORS = {'neutral_note': '#87688e', 'canonical_check': '#227b75'}
SECONDARY = ('canonical_reference_queued_to_checker', 'reference_failures', 'failed_actions', 'auditor_opened_current_original', 'auditor_inspected_current_content')
GROUPS = {
    'Navigate / session': ('#799aca', {'open_url', 'type_url', 'navigate', 'copy_current_url', 'set_clipboard', 'paste_url', 'switch_session'}),
    'Search / inspect': ('#227b75', {'drive_search', 'inspect_document'}),
    'Access control': ('#a881ba', {'request_access', 'grant_access', 'share_document', 'revoke_access'}),
    'Edit / local draft': ('#c38b3d', {'edit_document', 'restore_version', 'draft_local_document'}),
    'Recreate': ('#b95f50', {'recreate_document'}),
    'Message / report': ('#608b5a', {'send_message', 'report_status'}),
    'Wait': ('#a2a8a8', {'wait'}),
    'Other / invalid': ('#484e50', set()),
}
CAPTION = ('AI Village source-motivated single-document reference-recovery experiment. '
    'Both arms share the same explicit goal: the auditor must actually open the current correct original. '
    'Content, viewer ACL and starting profiles are held fixed; one checker reference starts broken. '
    'Lines link matched generated starting worlds and isolated two-role teams. The primary outcome and '
    'bounded-pair Hoeffding interval are taken from the exact saved result. Queued reference and failure counts '
    'are descriptive; a queued message does not prove receipt or reading. Decision indices are ordinal, not '
    'durations. This proxy does not reconstruct historical Google state or identify a behavioral mechanism.')


def count(value):
    return value if type(value) is int and 0 <= value <= 10000 else None


def group(action):
    return next((name for name, (_, actions) in GROUPS.items() if action in actions), 'Other / invalid')


def extract(record):
    """Export only typed public measures, not requests, contents, notes or provider envelopes."""
    if type(record) is not dict or record.get('kind') != 'village_recovery_experiment':
        raise ValueError('Only a source-grounded village_recovery_experiment can be plotted.')
    ref = {key: record.get(key) for key in ('id', 'version', 'hash')}
    if not _exact_ref(ref): raise ValueError('An exact typed result reference is required.')
    p = record.get('payload')
    json.dumps(p, allow_nan=False)
    if fingerprint(p) != ref['hash']: raise ValueError('The saved payload fingerprint differs.')
    _village_contract(p, recovery=True)
    if p.get('status') != 'complete': raise ValueError('Incomplete executions have no outcome plot.')
    protocol = p['protocol']; n = protocol.get('design', {}).get('trials_per_arm')
    if type(n) is not int or not 2 <= n <= 8 or protocol.get('primary_outcome') != PRIMARY:
        raise ValueError('The saved bounded matched-team design and oracle are required.')
    runs = p.get('runs')
    if type(runs) is not list or len(runs) != 2*n: raise ValueError('Every registered pair must be present.')
    rows = []; seen = set(); cells = set()
    for run in runs:
        if type(run) is not dict or run.get('status') != 'complete': raise ValueError('Every team must be complete.')
        rid, arm, pair, seed = (run.get(key) for key in ('run_id', 'arm', 'pair_id', 'environment_seed'))
        if (type(rid) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,200}', rid) or rid in seen
                or type(arm) is not str or arm not in ARMS or type(pair) is not int or not 1 <= pair <= n
                or (pair, arm) in cells or type(seed) is not int or not 0 <= seed < 2**53):
            raise ValueError('Unique exact pair, arm, run and seed identities are required.')
        seen.add(rid); cells.add((pair, arm))
        outcomes = run.get('outcomes'); turns = run.get('turns')
        if type(outcomes) is not dict or type(outcomes.get(PRIMARY)) is not int or outcomes[PRIMARY] not in (0, 1):
            raise ValueError('The primary oracle must be an explicit integer zero or one.')
        if type(turns) is not list or not 1 <= len(turns) <= 20: raise ValueError('Recorded decisions exceed this world bound.')
        actions = []
        for index, turn in enumerate(turns):
            if type(turn) is not dict or type(turn.get('step')) is not int or turn['step'] != index:
                raise ValueError('Recorded decision indices must preserve the executed ordinal order.')
            name = turn.get('action', {}).get('action') if type(turn.get('action')) is dict else None
            name = name if type(name) is str and re.fullmatch(r'[a-z_]{1,80}', name) else None
            ok = turn.get('tool_result', {}).get('ok') if type(turn.get('tool_result')) is dict else None
            actions.append({'turn_index': index, 'action': name, 'group': group(name), 'tool_ok': ok if type(ok) is bool else None})
        rows.append({'run_id': rid, 'pair_id': pair, 'arm': arm, 'environment_seed': seed,
            'primary': outcomes[PRIMARY], 'secondary': {key: count(outcomes.get(key)) for key in SECONDARY}, 'actions': actions})
    rows.sort(key=lambda row: (row['pair_id'], ARMS.index(row['arm'])))
    pairs = []
    for pair in range(1, n+1):
        matched = {row['arm']: row for row in rows if row['pair_id'] == pair}
        if len({row['environment_seed'] for row in matched.values()}) != 1: raise ValueError('Matched starting-world seeds differ.')
        pairs.append({'pair_id': pair, **{arm: matched[arm]['primary'] for arm in ARMS},
            'difference': matched['canonical_check']['primary'] - matched['neutral_note']['primary']})
    effect = p.get('analysis', {}).get('primary_effect', {}); arm_stats = p.get('analysis', {}).get('arms', {})
    differences = [pair['difference'] for pair in pairs]; difference = sum(differences)/n
    means = {arm: sum(row['primary'] for row in rows if row['arm'] == arm)/n for arm in ARMS}
    finite = lambda value: type(value) in (int, float) and math.isfinite(value)
    interval = effect.get('ci95'); radius = math.sqrt(2*math.log(40)/n)
    expected_interval = [max(-1, difference-radius), min(1, difference+radius)]
    if (type(effect) is not dict or effect.get('unit') != 'whole_two_role_team' or type(effect.get('n_pairs')) is not int
            or effect['n_pairs'] != n or effect.get('interval_method') != 'bounded_pair_Hoeffding_95'
            or type(effect.get('pair_differences')) is not list or any(type(v) is not int for v in effect['pair_differences'])
            or effect['pair_differences'] != differences or not finite(effect.get('difference')) or abs(effect['difference']-difference) > 1e-12
            or not finite(effect.get('mean_treatment')) or abs(effect['mean_treatment']-means['canonical_check']) > 1e-12
            or not finite(effect.get('mean_control')) or abs(effect['mean_control']-means['neutral_note']) > 1e-12
            or type(interval) is not list or len(interval) != 2 or any(not finite(v) for v in interval)
            or any(abs(a-b)>1e-12 for a,b in zip(interval, expected_interval))):
        raise ValueError('Saved primary analysis does not agree with the matched outcome ledger.')
    for arm in ARMS:
        stats = arm_stats.get(arm, {})
        if type(stats.get('n')) is not int or stats['n'] != n or not finite(stats.get('success_rate')) or abs(stats['success_rate']-means[arm]) > 1e-12:
            raise ValueError('Saved arm counts or rates disagree with the outcome ledger.')
    return {'schema': 'societylab.experiment-plots.v1', 'study_kind': FAMILY, 'source_ref': ref,
        'dataset_ref': dict(p['source_refs']['dataset_ref']), 'agent_mode': 'live', 'n_pairs': n,
        'team_count': len(rows), 'subject_decisions': sum(len(row['actions']) for row in rows), 'rows': rows, 'pairs': pairs,
        'primary_effect': {'difference': difference, 'ci95': list(interval), 'interval_method': effect['interval_method'], 'unit': 'whole_two_role_team'},
        'caption': CAPTION, 'scope': 'Exact saved result; descriptive secondary panels; no study pooling, historical equivalence or mediation inference.'}


def read_record(database, ref):
    if not _exact_ref(ref): raise ValueError('Use an exact typed saved reference.')
    path = Path(database).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        size = connection.execute('SELECT length(CAST(payload AS BLOB)) FROM objects WHERE id=? AND version=?', (ref['id'], ref['version'])).fetchone()
        if size is None: raise ValueError('The exact result version is unavailable.')
        if not 1 <= size[0] <= 32*1024**2: raise ValueError('Result payload exceeds the read bound.')
        row = connection.execute('SELECT * FROM objects WHERE id=? AND version=? AND length(CAST(payload AS BLOB))<=?', (ref['id'], ref['version'], 32*1024**2)).fetchone()
        if row is None: raise ValueError('The bounded exact result is unavailable.')
        if row['hash'] != ref['hash']: raise ValueError('The requested result fingerprint differs.')
        return Store._decode(row)


def draw(data, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 13})
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), gridspec_kw={'height_ratios': [1, 1.35]})
    fig.patch.set_facecolor('#f9faf6'); paired, forest, scatter, raster = axes.flatten()
    for pair in data['pairs']:
        paired.plot([0, 1], [pair[arm] for arm in ARMS], color='#a5aaa6', lw=1.5, alpha=.75)
        # Small fixed display offsets reveal overlapping outcomes; they are not data changes.
        offset = (pair['pair_id']-(data['n_pairs']+1)/2)*.055
        for x, arm in enumerate(ARMS): paired.scatter(x+offset, pair[arm], color=COLORS[arm], s=70, zorder=3)
    paired.set(xticks=[0, 1], xticklabels=[LABELS[arm] for arm in ARMS], yticks=[0, 1],
        yticklabels=['Not opened', 'Peer opened original'], ylim=(-.15, 1.15), xlim=(-.35, 1.35), title='Primary outcome · matched starting worlds')
    paired.text(0, -.25, f"{data['n_pairs']} matched pairs / {data['team_count']} fresh teams\nDots offset horizontally to reveal overlap; lines link paired worlds.", transform=paired.transAxes, fontsize=9)
    effect = data['primary_effect']; lo, hi = effect['ci95']; point = effect['difference']
    forest.axvline(0, color='#87948c', ls='--', lw=1)
    forest.plot([lo*100, hi*100], [0, 0], color=COLORS['canonical_check'], lw=4)
    forest.scatter([point*100], [0], color=COLORS['canonical_check'], s=90, zorder=3)
    forest.set(xlim=(-105, 105), ylim=(-.5, .5), yticks=[], xlabel='Canonical check − neutral (percentage points)', title='Saved primary effect · 95% interval')
    forest.text(.5, .72, f'{point*100:+.1f} pp  [{lo*100:+.1f}, {hi*100:+.1f}]', transform=forest.transAxes, ha='center', fontsize=12)
    forest.text(0, -.35, 'Method: bounded_pair_Hoeffding_95\nUnit: matched whole-team difference; no pooled studies.', transform=forest.transAxes, fontsize=9)
    forest.grid(axis='x', alpha=.15)
    missing = 0
    for row in data['rows']:
        x, y = (row['secondary'][key] for key in ('auditor_inspected_current_content', 'failed_actions'))
        if x is None or y is None: missing += 1; continue
        scatter.scatter(x, y, s=95, color=COLORS[row['arm']], marker='o' if row['arm'] == ARMS[0] else 'D', edgecolors='white', linewidths=.8)
        scatter.annotate('P'+str(row['pair_id']), (x, y), xytext=(5, 5 if row['arm']==ARMS[0] else -14), textcoords='offset points', fontsize=9)
    scatter.set(xlabel='Auditor inspection receipt (0/1)', ylabel='Unsuccessful tool receipts', title='Secondary team counts · descriptive, not a mediator')
    scatter.grid(alpha=.15); scatter.legend(handles=[Patch(facecolor=COLORS[arm], label=LABELS[arm]) for arm in ARMS], loc='upper left', frameon=False, fontsize=9)
    scatter.text(0, -.28, f'P labels pair IDs; coincident points can overlap.\n{missing} team(s) have unknown counts and are not plotted.', transform=scatter.transAxes, fontsize=9)
    rows = data['rows']
    unknown = 0
    for y, row in enumerate(rows):
        for action in row['actions']:
            x=action['turn_index']; raster.scatter(x, y, s=42, marker='s', color=GROUPS[action['group']][0], edgecolors='white', linewidths=.25)
            if action['tool_ok'] is False: raster.scatter(x, y, s=20, marker='x', color='#111111', linewidths=.75)
            elif action['tool_ok'] is None: unknown+=1
    raster.set(yticks=range(len(rows)), yticklabels=[f"P{row['pair_id']} · {'neutral' if row['arm']==ARMS[0] else 'check'}" for row in rows], xlabel='Recorded decision index (zero based)', title='Tool progression · actions executed in the local access world')
    raster.invert_yaxis(); raster.grid(axis='x', alpha=.1)
    raster.legend(handles=[Patch(facecolor=color, label=name) for name, (color, _) in GROUPS.items() if any(action['group']==name for row in rows for action in row['actions'])], loc='upper center', bbox_to_anchor=(.5, -.19), ncol=3, frameon=False, fontsize=8)
    fig.suptitle('AI Village reference-recovery study · '+data['source_ref']['id']+' · version '+str(data['source_ref']['version']), fontsize=16, color='#253f39')
    fig.text(.03, .025, f"{data['subject_decisions']} recorded decisions · {unknown} unknown tool-status receipts · live model teams, local executable proxy; historical hidden state remains unknown.", fontsize=10, color='#405a50')
    fig.subplots_adjust(left=.09, right=.97, bottom=.17, top=.91, wspace=.3, hspace=.8)
    destination=Path(destination); destination.mkdir(parents=True, exist_ok=True)
    png=destination/'analysis.png'; fig.savefig(png, dpi=140, facecolor=fig.get_facecolor(), bbox_inches='tight', pad_inches=.2); plt.close(fig)
    if png.stat().st_size > 800*1024: raise ValueError('PNG exceeds the report-cache bound.')
    manifest={**data, 'image_sha256': hashlib.sha256(png.read_bytes()).hexdigest(),
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'matplotlib_version': matplotlib.__version__}
    encoded=json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode('utf-8')
    if len(encoded)>128*1024: raise ValueError('Manifest exceeds the report-cache bound.')
    (destination/'source.json').write_bytes(encoded)
    return png


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object-id', required=True); parser.add_argument('--version', type=int, required=True)
    parser.add_argument('--hash', required=True); parser.add_argument('--database', type=Path, default=ROOT/'.runtime'/'lab.sqlite3')
    args=parser.parse_args(); ref={'id': args.object_id, 'version': args.version, 'hash': args.hash}
    data=extract(read_record(args.database, ref)); image=draw(data, ROOT/'.runtime'/'plots'/ref['hash'])
    print(json.dumps({'source_ref': ref, 'team_count': data['team_count'], 'matched_pairs': data['n_pairs'],
        'subject_decisions': data['subject_decisions'], 'success_counts': {arm: sum(row['primary'] for row in data['rows'] if row['arm']==arm) for arm in ARMS},
        'primary_effect': data['primary_effect'], 'image': str(image)}, sort_keys=True, allow_nan=False))


if __name__=='__main__': main()

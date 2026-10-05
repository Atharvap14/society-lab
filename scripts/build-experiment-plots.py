"""Offline Matplotlib plots of exact saved shared-artifact experiments; no model calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from swarm_lab.store import fingerprint

LABELS = {'baseline': 'No reminder', 'placebo': 'Neutral note', 'evidence_thought': 'File-check reminder'}
ACTIONS = {'inspect_artifact': '#357f88', 'repair_artifact': '#e49a38', 'publish_artifact': '#8a64a1', 'send_message': '#559462', 'wait': '#9ca5ae', 'other': '#c55454'}
METRICS = [('success', 'Correct publication'), ('inspected_publication', 'Any agent inspected\npublished version'), ('incorrect_publication', 'Incorrect publication')]

def binary(value):
    """Unknown, booleans and non-binary values stay unknown rather than zero."""
    return value if type(value) in (int, float) and math.isfinite(value) and value in (0, 1) else None

def extract(record):
    if record.get('kind') != 'experiment' or type(record.get('version')) is not int or record['version'] < 1 or fingerprint(record['payload']) != record.get('hash'):
        raise ValueError('An exact saved shared-artifact experiment is required.')
    p = record['payload']; runs = p.get('runs')
    if p.get('status') != 'complete' or not isinstance(runs, list) or not 1 <= len(runs) <= 120:
        raise ValueError('Only completed bounded studies are plotted.')
    rows = []
    for run in runs:
        turns = run.get('turns', [])
        if not isinstance(turns, list) or len(turns) > 1000:
            raise ValueError('Turn bounds exceeded.')
        actions = []
        for index, turn in enumerate(turns):
            action = turn.get('action', {}).get('action') if isinstance(turn.get('action'), dict) else None
            actions.append({'turn_index': index, 'step': turn.get('step'), 'action': action if action in ACTIONS else 'other', 'tool_ok': turn.get('tool_result', {}).get('ok') if isinstance(turn.get('tool_result'), dict) else None})
        outcomes = run.get('outcomes', {})
        rows.append({'run_id': run['run_id'], 'arm': run['arm'], 'actions': actions, 'metrics': {key: binary(outcomes.get(key)) for key, _ in METRICS}})
    effects = []
    for contrast in ['evidence_thought_vs_placebo', 'evidence_thought_vs_baseline']:
        effect = p.get('analysis', {}).get('effects', {}).get(contrast, {}).get('success', {})
        difference, interval = effect.get('difference'), effect.get('ci95')
        valid = type(difference) in (int, float) and math.isfinite(difference) and isinstance(interval, list) and len(interval) == 2 and all(type(x) in (int, float) and math.isfinite(x) for x in interval) and -1 <= interval[0] <= difference <= interval[1] <= 1
        effects.append({'contrast': contrast, 'difference': difference if valid else None, 'ci95': interval if valid else None, 'interval_method': effect.get('interval_method'), 'unit': effect.get('unit')})
    return {'schema': 'societylab.experiment-plots.v1', 'source_ref': {key: record[key] for key in ('id', 'version', 'hash')}, 'agent_mode': p.get('agent_mode'), 'rows': rows, 'effects': effects, 'caption': 'Separate saved study; no pooling. Timeline is recorded turn order, not elapsed time. Heatmap uses saved oracle and any-agent published-version inspection fields; white/hatched cells are unknown. No claims about original AI Village behavior or causal inspection mechanisms.'}

def draw(data, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch, Rectangle
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 13, 'axes.labelsize': 10})
    fig, axes = plt.subplots(1, 3, figsize=(17, 6), gridspec_kw={'width_ratios': [1.1, 1.8, 1.15]})
    fig.patch.set_facecolor('#fafbf7')
    a, b, c = axes
    a.axvline(0, color='#777777', ls='--', lw=1)
    for y, effect in enumerate(data['effects']):
        if effect['difference'] is not None:
            lo, hi = effect['ci95']; point = effect['difference']
            a.plot([lo*100, hi*100], [y, y], color='#287e79', lw=3)
            a.scatter([point*100], [y], color='#287e79', s=65, zorder=3)
            a.text(point*100, y+.17, f'{point*100:+.0f} pp [{lo*100:+.0f}, {hi*100:+.0f}]', ha='center', fontsize=9)
        else: a.text(0, y, 'Unknown', ha='center')
    a.set(yticks=[0,1], yticklabels=['Reminder −\nneutral', 'Reminder −\nbaseline'], xlim=(-105,105), ylim=(-.45,1.5), xlabel='Correct publication difference (percentage points)', title='Saved effect intervals · 95%')
    a.grid(axis='x', alpha=.15)
    a.text(.02, -.23, 'Method: '+str(data['effects'][0]['interval_method'])+'\nUnit: whole team run; one study only', transform=a.transAxes, fontsize=9)
    rows = data['rows']; labels = [r['run_id']+' · '+LABELS.get(r['arm'],r['arm']) for r in rows]
    for y, row in enumerate(rows):
        for event in row['actions']:
            x = event['turn_index']
            b.scatter(x, y, s=100, marker='s', color=ACTIONS[event['action']], edgecolors='white', linewidths=.8)
            if event['tool_ok'] is False: b.scatter(x,y,s=45,marker='x',color='#222222')
    b.set(yticks=range(len(rows)), yticklabels=labels, xlabel='Recorded decision index (zero based)', title='Observed actions by team')
    b.invert_yaxis(); b.grid(axis='x', alpha=.12)
    b.legend(handles=[Patch(facecolor=color,label=name.replace('_artifact','').replace('_',' ')) for name,color in ACTIONS.items()], loc='upper center', bbox_to_anchor=(.5,-.16), ncol=3, frameon=False, fontsize=9)
    matrix = np.array([[r['metrics'][key] if r['metrics'][key] is not None else np.nan for key,_ in METRICS] for r in rows], dtype=float)
    cmap=ListedColormap(['#ead5ce','#64aaa0']); cmap.set_bad('#ffffff')
    c.imshow(np.ma.masked_invalid(matrix), cmap=cmap, vmin=0, vmax=1, aspect='auto')
    for y in range(len(rows)):
        for x in range(len(METRICS)):
            unknown=np.isnan(matrix[y,x]); c.text(x,y,'?' if unknown else str(int(matrix[y,x])),ha='center',va='center',fontsize=12,color='#223a36')
            if unknown: c.add_patch(Rectangle((x-.5,y-.5),1,1,fill=False,hatch='///',edgecolor='#aaaaaa',lw=.4))
    c.set(xticks=range(len(METRICS)),xticklabels=['Correct\npublication','Any agent inspected\npublished version','Incorrect\npublication'],yticks=range(len(rows)),yticklabels=[r['run_id'] for r in rows],title='Saved outcome / inspection measures')
    c.tick_params(axis='x',labelsize=9)
    c.text(.02,-.23,'1 = recorded yes · 0 = recorded no\n? / hatching = unknown, not zero',transform=c.transAxes,fontsize=9)
    fig.suptitle('Shared-file coordination · '+data['source_ref']['id']+' · version '+str(data['source_ref']['version']),fontsize=16,color='#233e3a')
    fig.text(.02,.02,'Recorded agent mode: '+str(data['agent_mode'])+' · No durations inferred; action order is not a delivery or reasoning measure.',fontsize=10,color='#465b54')
    fig.subplots_adjust(left=.08,right=.98,bottom=.29,top=.86,wspace=.65)
    destination.mkdir(parents=True,exist_ok=True)
    png=destination/'analysis.png'; fig.savefig(png,dpi=160,facecolor=fig.get_facecolor(),bbox_inches='tight',pad_inches=.2); plt.close(fig)
    data['image_sha256']=hashlib.sha256(png.read_bytes()).hexdigest()
    data['generator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    data['matplotlib_version']=matplotlib.__version__
    (destination/'source.json').write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False),encoding='utf-8')
    return png

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object-id',action='append',required=True); parser.add_argument('--version',type=int,default=1)
    parser.add_argument('--base-url',default='http://127.0.0.1:8765'); args=parser.parse_args()
    from urllib.parse import quote
    for object_id in args.object_id:
        with urlopen(args.base_url+'/api/object/'+quote(object_id,safe='')+'?version='+str(args.version),timeout=30) as response:
            raw=response.read(8*1024*1024+1)
        if len(raw)>8*1024*1024: raise ValueError('Record exceeds plot input bound.')
        record=json.loads(raw); data=extract(record)
        print(draw(data,ROOT/'.runtime'/'plots'/record['hash']))

if __name__ == '__main__': main()

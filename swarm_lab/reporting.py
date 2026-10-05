"""Authoritative plain-language numbers, rendered from executed outcomes."""
def quantitative_summary(result):
    if result.get('status')!='complete':return {'status':'incomplete','conclusion':'No effects estimated; execution did not complete.'}
    analysis=result['analysis'];arms={}
    for arm,values in analysis['arms'].items():
        runs=[r for r in result['runs'] if r['arm']==arm]
        count=sum(int(r['outcomes']['success']) for r in runs)
        arms[arm]={'correct':count,'total':len(runs),'rate':count/len(runs) if runs else None}
    effect=analysis['primary_effect'];low,high=effect['ci95']
    conclusion='inconclusive' if low<=0<=high else 'positive_in_registered_environment' if low>0 else 'negative_in_registered_environment'
    labels={'baseline':'Baseline','placebo':'Neutral note','evidence_thought':'Evidence reminder'}
    counts='; '.join(f"{labels.get(a,a)}: {v['correct']}/{v['total']} correct publications" for a,v in arms.items())
    narrative=(f"{counts}. The registered reminder-versus-neutral-note difference is {effect['difference']*100:+.1f} percentage points "
        f"(95% interval {low*100:+.1f} to {high*100:+.1f}; two-sided randomization p={effect['p_two_sided']:.3g}). "
        +('The interval includes zero; this pilot does not distinguish a benefit from no effect or harm. ' if conclusion=='inconclusive' else 'The interval excludes zero in this registered task; replication and external validation remain necessary. ')
        +'Each team is one experimental unit. Historical causation and transfer to other tasks are unestablished.')
    return {'status':'complete','arms':arms,'primary_conclusion':conclusion,'difference':effect['difference'],'ci95':effect['ci95'],'p_two_sided':effect['p_two_sided'],'unit':'whole_swarm_run','plain_language':narrative}

def numeric_free_commentary(value):
    """Model prose may explain; executed quantities come from code alone."""
    import re
    def visit(x):
        if isinstance(x,str):return not re.search(r'\d',x)
        if isinstance(x,list):return all(visit(v) for v in x)
        if isinstance(x,dict):return all(visit(v) for v in x.values())
        return True
    return bool(visit(value))

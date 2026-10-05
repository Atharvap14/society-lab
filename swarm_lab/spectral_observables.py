"""Graph-frequency descriptions of explicitly measured message rates.

The signal is a regex-hit proportion, not a belief, coordination quality, or
latent behavior. A referenced nonauthor has an unknown rate, never a zero.
"""
from collections import Counter,defaultdict
from .discovery import DETECTOR_DEFINITIONS
from .graph_discovery import graph_signal_summary
from .network import spectral_basis


def describe_observable_signals(discovery):
    exposure=Counter();positive=defaultdict(Counter);evidence=defaultdict(lambda:defaultdict(list))
    for row in discovery.get('signals',[]):
        agent=row.get('agent_id')
        if not agent or row.get('speaker_type')!='agent':continue
        exposure[agent]+=1
        for label in row.get('labels',[]):
            positive[label][agent]+=1;evidence[label][agent].append(row['message_id'])
    result={}
    for channel,projection in discovery.get('network',{}).get('projections',{}).items():
        nodes=[n['id'] for n in projection.get('nodes',[])]
        missing=[identity for identity in nodes if exposure[identity]==0]
        measured_nodes=[identity for identity in nodes if exposure[identity]>0]
        induced=None
        if missing and measured_nodes:
            edges=[edge for edge in projection.get('edges',[]) if edge['source'] in measured_nodes and edge['target'] in measured_nodes]
            induced={'nodes':[node for node in projection['nodes'] if node['id'] in measured_nodes],
                     'spectral':spectral_basis(measured_nodes,edges)}
        signals={}
        for label in DETECTOR_DEFINITIONS:
            metadata={'observable':label,'measurement':'deterministic_regex_positive_messages_per_authored_message',
                'detector_version':discovery.get('detector_version'),'denominators':{node:exposure[node] for node in nodes},
                'positive_message_ids':{node:evidence[label][node] for node in nodes},
                'units':'Proportion of retained authored messages with a regex hit; zero hits is not proof of absent behavior.',
                'limitations':['Uncalibrated screening labels may include quotations, boilerplate and false positives.',
                               'Rates and graph edges derive from the same selected message window.',
                               'Similarity may reflect shared tasks, roles, timing or measurement artifacts; no causal influence is identified.']}
            if missing:
                signals[label]={**metadata,'available':False,'reason':'Referenced nodes have no authored-message denominator; no zero imputation.',
                                'missing_signal_nodes':missing}
                if induced:
                    rates={node:positive[label][node]/exposure[node] for node in measured_nodes}
                    signals[label]['induced_author_subgraph']={**graph_signal_summary(induced,rates),'rates':rates,
                        'included_nodes':measured_nodes,'excluded_nodes':missing,
                        'scope':'Recomputed operator on the induced subgraph of observed authors; it describes a different selected graph, without imputing missing rates.'}
            else:
                rates={node:positive[label][node]/exposure[node] for node in nodes}
                signals[label]={**metadata,'rates':rates,**graph_signal_summary(projection,rates)}
        result[channel]=signals
    return result

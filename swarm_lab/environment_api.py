"""Capability-first factory for executable environments; no arbitrary code eval."""
from typing import Protocol

class Environment(Protocol):
    def reset(self,seed:int)->dict:...
    def observe(self,agent_id:str)->dict:...
    def step(self,agent_id:str,action:dict)->dict:...
    def inject_context(self,agent_id:str,text:str)->None:...
    def snapshot(self)->dict:...
    def evaluate(self)->dict:...

def capabilities():
    from .environments import environment_capabilities
    from .diffusion_environment import diffusion_environment_capabilities
    from .complementary_environment import complementary_environment_capabilities
    from .resource_environment import resource_environment_capabilities
    return {'api_version':'1.0','implementations':{'shared_artifact_coordination':environment_capabilities(),'provenance_diffusion':diffusion_environment_capabilities(),'complementary_information':complementary_environment_capabilities(),'exclusive_resource_tasks':resource_environment_capabilities()},
        'fidelity_policy':'Dimensions are capability declarations, not an ordered fidelity ladder. Unsupported combinations fail.',
        'extension_contract':['Reset independent state','Scope subject observations and context','Validate action permissions and budgets','Evaluate executed outcomes independently','Audit leak boundaries and reproducibility','Version implementation and freeze experiments before outcome calls']}

def create(spec,seed):
    if spec.get('kind')=='shared_artifact_coordination':
        from .environments import create_environment
        return create_environment(spec,seed)
    if spec.get('kind')=='provenance_diffusion':
        from .diffusion_environment import create_diffusion_environment
        return create_diffusion_environment(spec,seed)
    if spec.get('kind')=='complementary_information':
        from .complementary_environment import create_complementary_environment
        return create_complementary_environment(spec,seed)
    if spec.get('kind')=='exclusive_resource_tasks':
        from .resource_environment import create_resource_environment
        return create_resource_environment(spec,seed)
    raise ValueError('Unsupported environment kind; implement and validate a new environment before declaring it executable')

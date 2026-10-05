"""Read exact allowlisted implementation sections for research-role adjudication.

This reads AST source ranges; it never imports or evaluates a generated program.
Privileged reset/oracle code is research evidence and never enters subject inputs.
"""
import ast
import hashlib
from pathlib import Path

SECTIONS=('factory','observation','actions','oracle','contract','capabilities')
TARGETS={
    'shared_artifact_coordination':('environments.py',{'factory':'environment_spec','observation':'ArtifactCoordinationEnvironment.observe',
        'actions':'ArtifactCoordinationEnvironment.step','oracle':'ArtifactCoordinationEnvironment.evaluate',
        'contract':'check_environment_contract','capabilities':'environment_capabilities'}),
    'provenance_diffusion':('diffusion_environment.py',{'factory':'create_diffusion_spec','observation':'ProvenanceDiffusionEnvironment.observe',
        'actions':'ProvenanceDiffusionEnvironment.step','oracle':'ProvenanceDiffusionEnvironment.evaluate',
        'contract':'check_diffusion_contract','capabilities':'diffusion_environment_capabilities'}),
    'complementary_information':('complementary_environment.py',{'factory':'create_complementary_spec','observation':'ComplementaryInformationEnvironment.observe',
        'actions':'ComplementaryInformationEnvironment.step','oracle':'ComplementaryInformationEnvironment.evaluate',
        'contract':'check_complementary_contract','capabilities':'complementary_environment_capabilities'}),
    'exclusive_resource_tasks':('resource_environment.py',{'factory':'create_resource_spec','observation':'ResourceTaskEnvironment.observe',
        'actions':'ResourceTaskEnvironment.step','oracle':'ResourceTaskEnvironment.evaluate',
        'contract':'check_resource_contract','capabilities':'resource_environment_capabilities'}),
}


def read_environment_source(template,section,expected_sha256=''):
    if template not in TARGETS or section not in SECTIONS:raise ValueError('Unknown allowlisted implementation or section')
    filename,targets=TARGETS[template];path=Path(__file__).with_name(filename);raw=path.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    if expected_sha256 and expected_sha256!=digest:raise ValueError('Implementation hash differs from the pinned world source')
    text=raw.decode('utf-8');tree=ast.parse(text);parts=targets[section].split('.');nodes=tree.body;node=None
    for part in parts:
        node=next((n for n in nodes if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==part),None)
        if node is None:raise ValueError('Declared implementation section is unavailable')
        nodes=node.body
    excerpt='\n'.join(text.splitlines()[node.lineno-1:node.end_lineno]);limit=16000
    return {'template':template,'section':section,'source_file':filename,'source_sha256':digest,
        'symbol':targets[section],'line_start':node.lineno,'line_end':node.end_lineno,
        'text':excerpt[:limit],'truncated':len(excerpt)>limit,
        'interpretation':'Exact local implementation source, not historical observations or proof of semantic correctness.',
        'boundary':'Research-only inspection. Privileged oracle/control source must never be copied into subject contexts.'}

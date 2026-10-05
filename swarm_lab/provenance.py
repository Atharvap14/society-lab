"""Verify local HF cache metadata without attributing revisions from path names."""
import hashlib
import re
from pathlib import Path

def source_revision(source):
    source=Path(source)
    file=source if source.is_file() else next((source/n for n in ('chat_messages.jsonl.gz','chat_messages.jsonl') if (source/n).is_file()),None)
    if file is None:return {'revision':'fixture_or_user_source','revision_verification':'not_available'}
    metadata=file.parent/'.cache'/'huggingface'/'download'/(file.name+'.metadata')
    if not metadata.is_file():return {'revision':'fixture_or_user_source','revision_verification':'not_available','note':'Directory names and user-provided revision claims do not verify source bytes.'}
    lines=metadata.read_text(encoding='utf-8').splitlines()
    if len(lines)<2 or not re.fullmatch(r'[0-9a-f]{40}',lines[0]) or not re.fullmatch(r'[0-9a-f]{64}',lines[1]):
        return {'revision':'unknown','revision_verification':'metadata_not_supported'}
    digest=hashlib.sha256()
    with file.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    matched=digest.hexdigest()==lines[1]
    return {'revision':lines[0] if matched else 'unknown','claimed_revision':lines[0],
        'revision_verification':'hf_cache_metadata_and_compressed_sha256_match' if matched else 'source_hash_mismatch',
        'source_sha256':digest.hexdigest(),'expected_sha256':lines[1],'metadata_file':str(metadata)}

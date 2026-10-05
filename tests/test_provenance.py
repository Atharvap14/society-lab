import hashlib
import tempfile
import unittest
from pathlib import Path
from swarm_lab.provenance import source_revision

class ProvenanceTests(unittest.TestCase):
    def test_directory_name_cannot_establish_revision(self):
        with tempfile.TemporaryDirectory(prefix='ai-village-') as d:
            p=Path(d);(p/'chat_messages.jsonl.gz').write_bytes(b'data')
            self.assertEqual(source_revision(p)['revision_verification'],'not_available')
    def test_cache_claim_requires_matching_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);data=b'data';(p/'chat_messages.jsonl.gz').write_bytes(data)
            cache=p/'.cache/huggingface/download';cache.mkdir(parents=True)
            (cache/'chat_messages.jsonl.gz.metadata').write_text('a'*40+'\n'+hashlib.sha256(data).hexdigest()+'\n123')
            self.assertEqual(source_revision(p)['revision'],'a'*40)
            (p/'chat_messages.jsonl.gz').write_bytes(b'changed')
            self.assertEqual(source_revision(p)['revision'],'unknown')
            self.assertEqual(source_revision(p)['revision_verification'],'source_hash_mismatch')

if __name__=='__main__':unittest.main()

import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from swarm_lab.guide_reports import render_report, _cached_plot, MAX_PLOT_BYTES, MAX_PLOT_METADATA_BYTES
from swarm_lab.store import Store

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aP1sAAAAASUVORK5CYII=')

class GuideReportPlotCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name)/'lab.sqlite3')
        self.record = self.store.put('experiment', {'analysis': {}})
        self.ref = {key:self.record[key] for key in ('id','version','hash')}
        self.directory = Path(self.tmp.name)/'plots'/self.ref['hash']; self.directory.mkdir(parents=True)
        self.metadata = {'schema':'societylab.experiment-plots.v1','source_ref':self.ref,'caption':'Saved <script>unsafe</script> caption','image_sha256':hashlib.sha256(PNG).hexdigest()}
        self.write()

    def write(self):
        (self.directory/'source.json').write_text(json.dumps(self.metadata),encoding='utf-8')
        (self.directory/'analysis.png').write_bytes(PNG)

    def test_valid_exact_image_is_embedded_with_escaped_caption_and_no_write(self):
        with self.store.connect() as connection:
            objects = connection.execute('SELECT id,version,hash FROM objects').fetchall()
        usage = self.store.usage()
        doc = render_report(self.store,self.ref)
        self.assertIn('data:image/png;base64,',doc)
        self.assertIn('&lt;script&gt;unsafe&lt;/script&gt;',doc)
        self.assertNotIn('<script>',doc)
        self.assertIn('not a fresh execution',doc)
        with self.store.connect() as connection:
            self.assertEqual(objects,connection.execute('SELECT id,version,hash FROM objects').fetchall())
        self.assertEqual(usage,self.store.usage())

    def test_missing_ref_mismatch_bool_version_and_image_hash_fall_back(self):
        for change in [{'source_ref':{**self.ref,'id':'another'}},{'source_ref':{**self.ref,'version':True}},{'source_ref':{**self.ref,'hash':'b'*64}},{'image_sha256':'c'*64}]:
            with self.subTest(change=change):
                original=self.metadata.copy();self.metadata.update(change);self.write()
                self.assertNotIn('data:image/png',render_report(self.store,self.ref));self.metadata=original
        (self.directory/'source.json').unlink()
        doc=render_report(self.store,self.ref)
        self.assertNotIn('data:image/png',doc);self.assertIn('What happened',doc)

    def test_signatures_bounds_ambiguous_and_nonfinite_metadata_refused(self):
        (self.directory/'analysis.png').write_bytes(b'not png')
        self.metadata['image_sha256']=hashlib.sha256(b'not png').hexdigest();self.write()
        (self.directory/'analysis.png').write_bytes(b'not png')
        self.assertNotIn('data:image/png',render_report(self.store,self.ref))
        self.metadata['image_sha256']=hashlib.sha256(PNG).hexdigest();self.write()
        (self.directory/'analysis.png').write_bytes(PNG+b'x'*MAX_PLOT_BYTES)
        self.assertNotIn('data:image/png',render_report(self.store,self.ref))
        self.write();(self.directory/'source.json').write_bytes(b' '* (MAX_PLOT_METADATA_BYTES+1))
        self.assertNotIn('data:image/png',render_report(self.store,self.ref))
        for text in ['{"source_ref":null,"source_ref":{}}','{"extra":NaN}']:
            (self.directory/'source.json').write_text(text)
            self.assertNotIn('data:image/png',render_report(self.store,self.ref))

    def test_reads_are_bounded_even_when_input_grows(self):
        observed=[]
        original=Path.open
        class Reader:
            def __init__(self, stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def read(self,n=-1):observed.append(n);return self.stream.read(n)
        def bounded(path,*args,**kwargs):return Reader(original(path,*args,**kwargs))
        with patch.object(Path,'open',bounded):
            self.assertIn('data:image/png',_cached_plot(self.ref,self.directory.parent))
        self.assertEqual(observed,[MAX_PLOT_METADATA_BYTES+1,MAX_PLOT_BYTES+1])

    def test_dataset_figures_are_source_bound_and_not_experiment_outcomes(self):
        record=self.store.put('dataset',{'messages':[{'id':'m'}]})
        reference={k:record[k] for k in ('id','version','hash')}
        directory=Path(self.tmp.name)/'plots'/reference['hash'];directory.mkdir()
        metadata={**self.metadata,'schema':'societylab.dataset-plots.v1','source_ref':reference,'caption':'Recorded posts; recipients unknown.'}
        (directory/'source-activity.json').write_text(json.dumps(metadata),encoding='utf-8')
        (directory/'activity.png').write_bytes(PNG)
        doc=render_report(self.store,reference)
        self.assertIn('What the logs show',doc);self.assertIn('1 retained messages',doc)
        self.assertIn('data:image/png',doc);self.assertIn('not confirmed receipt',doc)
        self.assertNotIn('Correct publication',doc);self.assertNotIn('<script>',doc)

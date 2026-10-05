"""Prepare a reviewed source bundle; this never publishes to GitHub."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / 'output' / 'code'
    output.mkdir(parents=True, exist_ok=True)
    eligible = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    blocked = {'.runtime', '.secrets', '.git', 'ai-village', 'research-sources', 'output', 'tmp', '.download-benchmark', '__pycache__'}
    secrets = set()
    for p in (ROOT / '.secrets').glob('*'):
        if p.is_file() and p.stat().st_size < 1024 * 1024:
            secrets.update(re.findall(r'(?:sk-proj-|sk-|hf_)[A-Za-z0-9_-]{15,}', p.read_text(encoding='utf-8', errors='ignore')))
    entries = []
    for relative in sorted(set(eligible)):
        if not relative:
            continue
        p = ROOT / relative
        if any(part in blocked for part in p.relative_to(ROOT).parts) or relative == 'examples/village-window.json' or p.is_symlink() or not p.is_file():
            continue
        if not p.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Source path escaped the project.')
        data = p.read_bytes()
        text = data.decode('utf-8', errors='ignore')
        if any(secret in text for secret in secrets):
            raise ValueError('A configured credential appears in candidate file: ' + relative)
        entries.append({'path': relative.replace('\\', '/'), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    target = output / 'society-lab-source.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            archive.write(ROOT / entry['path'], 'society-lab/' + entry['path'])
    manifest = {'target_repository': 'Atharvap14/society-lab', 'publication_status': 'Prepared for user review; not published', 'files': entries, 'file_count': len(entries), 'source_bytes': sum(row['bytes'] for row in entries), 'archive_sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'excluded': sorted(blocked) + ['examples/village-window.json'], 'credential_check': 'No configured OpenAI/HF credential string in included files; not an exhaustive privacy audit.'}
    (output / 'source-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({key: manifest[key] for key in ('target_repository', 'publication_status', 'file_count', 'source_bytes', 'archive_sha256')}))


if __name__ == '__main__':
    main()

"""Explicitly configure the local guide allowance; no credentials or API calls."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile


MAX_CALLS = 100000
CHECKOUT_ROOT = Path(__file__).resolve().parents[1]


def _budget(value, name):
    if type(value) is not int or not 0 <= value <= MAX_CALLS:
        raise ValueError(name + ' must be an integer from 0 to 100000')
    return value


def _argument(value):
    if not re.fullmatch(r'0|[1-9][0-9]{0,5}', value):
        raise argparse.ArgumentTypeError('Use a canonical integer from 0 to 100000')
    try: return _budget(int(value), 'Call allowance')
    except ValueError as error: raise argparse.ArgumentTypeError(str(error)) from None


class _ExplicitOnce(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(option_string + ' must be supplied exactly once')
        setattr(namespace, self.dest, values)


def configure_guide(root, *, research_calls, guide_calls):
    """Replace only guide-config.json; cumulative call and science ledgers persist."""
    _budget(research_calls, 'Research allowance'); _budget(guide_calls, 'Guide allowance')
    root = Path(root).expanduser().resolve()
    if not root.is_dir(): raise ValueError('Choose an existing checkout root')
    runtime = root / '.runtime'
    runtime.mkdir(exist_ok=True)
    target = runtime / 'guide-config.json'
    text = json.dumps({'baseline_calls': research_calls, 'max_additional_calls': guide_calls},
                      indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    # Readers see the old complete configuration or the new complete one.
    handle, name = tempfile.mkstemp(prefix='guide-config-', suffix='.tmp', dir=runtime)
    temporary = Path(name)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists(): temporary.unlink()
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description='Configure a guide-only allowance without calling a provider.')
    parser.add_argument('--research-calls', required=True, type=_argument, action=_ExplicitOnce,
        help='Cumulative research cap; must match serve --max-calls (0–100000).')
    parser.add_argument('--guide-calls', required=True, type=_argument, action=_ExplicitOnce,
        help='Explicit guide-only allowance (0–100000); existing usage is not reset.')
    parser.add_argument('--root', type=Path, default=CHECKOUT_ROOT,
        help='Existing checkout root; defaults to this script\'s parent checkout.')
    args = parser.parse_args(argv)
    try: configure_guide(args.root, research_calls=args.research_calls, guide_calls=args.guide_calls)
    except (ValueError, OSError): parser.error('Could not save the requested guide configuration; check the root and allowance values')
    print('Saved .runtime/guide-config.json. No API calls were made; existing usage is unchanged.')
    print('Start from the same checkout with:')
    print('python -m swarm_lab.cli --max-calls ' + str(args.research_calls) + ' serve --port 8765')
    return 0


if __name__ == '__main__': raise SystemExit(main())

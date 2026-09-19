"""Read USB restart JSONL offline; never opens COM or restarts devices."""
import argparse
import json
from pathlib import Path
import sys

DEFAULT_INPUT = Path(__file__).resolve().parents[1] / 'usb-restart-events.jsonl'


def read_events(path):
    with Path(path).open(encoding='utf-8-sig') as source:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            if line.startswith('JSON '):
                line = line[5:]
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or event.get('schema') != 1 or event.get('type') != 'usb_restart_event':
                    raise ValueError('unsupported event schema/type')
                for key in ('utc', 'launch_id', 'action', 'level'):
                    if not isinstance(event.get(key), str) or not event[key]:
                        raise ValueError('missing or invalid ' + key)
                if type(event.get('sequence')) is not int or event['sequence'] < 1:
                    raise ValueError('invalid sequence')
                if not isinstance(event.get('data'), dict):
                    raise ValueError('invalid data')
                if event.get('error') is not None and not isinstance(event['error'], dict):
                    raise ValueError('invalid error')
                if event['action'] == 'ERROR' and (not event.get('error') or not event['error'].get('message')):
                    raise ValueError('ERROR event has no error message')
            except (ValueError, TypeError) as error:
                raise ValueError(f'{path}:{number}: {error}') from error
            yield event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--last-launch', action='store_true')
    group.add_argument('--launch-id')
    parser.add_argument('--errors', action='store_true', help='Only ERROR events')
    args = parser.parse_args()
    try:
        events = list(read_events(args.input))
        launch_id = events[-1]['launch_id'] if args.last_launch and events else args.launch_id
        for event in events:
            if launch_id and event['launch_id'] != launch_id:
                continue
            if args.errors and event['action'] != 'ERROR':
                continue
            print(json.dumps(event, ensure_ascii=True, separators=(',', ':')))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'type': 'usb_restart_reader_error', 'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Progress of the Hakone map round, from docs/hakone_progress.json.

python tools/hakone_progress.py            summary by area and by owner
python tools/hakone_progress.py --todo     also list what is left
python tools/hakone_progress.py --json     machine-readable summary

Every task is counted in units of the same size (unit_minutes of work). The
percentage counts finished units only; units in progress are shown apart and
earn nothing until they are done. Totals move when estimates change or new
work is found; that is expected and is written in each task's note.
"""
import argparse
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FILE = ROOT / 'docs' / 'hakone_progress.json'
STATES = ('done', 'doing', 'todo')


def load(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    tasks = data.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise SystemExit('no tasks in ' + str(path))
    seen = set()
    for t in tasks:
        for key in ('id', 'area', 'title', 'units', 'status'):
            if key not in t:
                raise SystemExit('task without %s: %r' % (key, t))
        if t['id'] in seen:
            raise SystemExit('duplicate task id ' + t['id'])
        seen.add(t['id'])
        if t['status'] not in STATES:
            raise SystemExit('unknown status %r in %s' % (t['status'], t['id']))
        if not isinstance(t['units'], (int, float)) or t['units'] <= 0:
            raise SystemExit('units must be positive in ' + t['id'])
    return data, tasks


def group(tasks, key):
    out = collections.OrderedDict()
    for t in tasks:
        g = out.setdefault(t.get(key, '?'), {'tasks': 0, 'units': 0, 'done': 0, 'doing': 0})
        g['tasks'] += 1
        g['units'] += t['units']
        if t['status'] != 'todo':
            g[t['status']] += t['units']
    return out


def pct(part, whole):
    return round(100 * part / whole, 1) if whole else 0.0


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', type=pathlib.Path, default=FILE)
    ap.add_argument('--todo', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    data, tasks = load(a.file)
    areas, owners = group(tasks, 'area'), group(tasks, 'owner')
    total = sum(g['units'] for g in areas.values())
    done = sum(g['done'] for g in areas.values())
    doing = sum(g['doing'] for g in areas.values())
    minutes = data.get('unit_minutes', 30)
    if a.json:
        print(json.dumps({'updated': data.get('updated'), 'unit_minutes': minutes, 'units': total, 'done': done,
                          'doing': doing, 'percent': pct(done, total), 'tasks': len(tasks),
                          'areas': {k: dict(v, percent=pct(v['done'], v['units'])) for k, v in areas.items()},
                          'owners': {k: dict(v, percent=pct(v['done'], v['units'])) for k, v in owners.items()}},
                         ensure_ascii=False, indent=1))
        return
    print('Hakone map round, updated %s' % data.get('updated', '?'))
    print('%.1f%% done: %g of %g units finished, %g more in progress (%d tasks, 1 unit = about %d minutes of work)'
          % (pct(done, total), done, total, doing, len(tasks), minutes))
    print('left: %g units, about %.0f hours of work' % (total - done, (total - done) * minutes / 60))
    for title, groups in (('by area', areas), ('by owner', owners)):
        print()
        print(title)
        width = max(len(str(k)) for k in groups)
        for name, v in groups.items():
            p = pct(v['done'], v['units'])
            bar = '#' * int(p / 5) + '.' * (20 - int(p / 5))
            print('  %-*s %s %5.1f%%  %g/%g units, %g in progress' % (width, name, bar, p, v['done'], v['units'], v['doing']))
    if a.todo:
        print()
        for t in tasks:
            if t['status'] != 'done':
                print('%-6s %-14s %-4g %s' % (t['status'], t['id'], t['units'], t['title']))


if __name__ == '__main__':
    sys.exit(main())

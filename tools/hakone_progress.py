#!/usr/bin/env python3
"""Progress of the Hakone map round, from docs/hakone_progress.json.

python tools/hakone_progress.py            summary by area
python tools/hakone_progress.py --todo     also list what is left
python tools/hakone_progress.py --json     machine-readable summary

Every task is counted in units of the same size (unit_minutes of work), so
the percentage is done units over all units. A unit in progress counts as
half done. Totals move when estimates change or new work is found; that is
expected and is written in each task's note.
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


def credit(t):
    return t['units'] if t['status'] == 'done' else t['units'] / 2 if t['status'] == 'doing' else 0


def summary(tasks):
    areas = collections.OrderedDict()
    for t in tasks:
        a = areas.setdefault(t['area'], {'tasks': 0, 'units': 0, 'done': 0.0, 'left': 0})
        a['tasks'] += 1
        a['units'] += t['units']
        a['done'] += credit(t)
        a['left'] += 0 if t['status'] == 'done' else 1
    total = sum(a['units'] for a in areas.values())
    done = sum(a['done'] for a in areas.values())
    return total, done, areas


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', type=pathlib.Path, default=FILE)
    ap.add_argument('--todo', action='store_true')
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    data, tasks = load(a.file)
    total, done, areas = summary(tasks)
    minutes = data.get('unit_minutes', 30)
    if a.json:
        print(json.dumps({'updated': data.get('updated'), 'unit_minutes': minutes, 'units': total, 'done': done,
                          'percent': round(100 * done / total, 1), 'tasks': len(tasks),
                          'areas': {k: dict(v, percent=round(100 * v['done'] / v['units'], 1)) for k, v in areas.items()}},
                         ensure_ascii=False, indent=1))
        return
    print('Hakone map round, updated %s' % data.get('updated', '?'))
    print('%.1f%% done: %g of %g units (%d tasks, 1 unit = about %d minutes of work)'
          % (100 * done / total, done, total, len(tasks), minutes))
    left = total - done
    print('left: %g units, about %.0f hours of work' % (left, left * minutes / 60))
    print()
    width = max(len(k) for k in areas)
    for name, v in areas.items():
        pct = 100 * v['done'] / v['units']
        bar = '#' * int(pct / 5) + '.' * (20 - int(pct / 5))
        print('%-*s %s %5.1f%%  %g/%g units, %d tasks left' % (width, name, bar, pct, v['done'], v['units'], v['left']))
    if a.todo:
        print()
        for t in tasks:
            if t['status'] != 'done':
                print('%-6s %-14s %-4g %s' % (t['status'], t['id'], t['units'], t['title']))


if __name__ == '__main__':
    sys.exit(main())

"""Collect every cell other sessions' pending plans write, for E13_SKIP.

other_cells.py <out.json> <plan file> [plan file ...]

A plan file is either a rows list ([x, y, z, before, after, ...]) or a TrafficCraft patch
({"edits": [{"pos": [x, y, z], ...}]}). Missing files are reported and skipped.
"""
import json, os, sys


def cells(path):
    data = json.load(open(path, encoding='utf8'))
    if isinstance(data, dict):
        return [tuple(e['pos']) for e in data['edits']]
    return [tuple(r[:3]) for r in data]


def main(out, files):
    found = set()
    for f in files:
        if not os.path.exists(f):
            print('missing', f)
            continue
        c = cells(f)
        found.update(c)
        print(len(c), f)
    json.dump(sorted(found), open(out, 'w'))
    print('cells', len(found))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])

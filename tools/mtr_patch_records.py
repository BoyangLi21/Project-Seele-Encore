"""Apply a reviewed patch to MTR 4 record files in an ISOLATED world copy (never the formal world).

Records live at <world>/mtr/<ns>/<dim>/<kind>/<last two hex digits>/<16 hex digits of the id> as
MessagePack maps. Operations (JSON list), each checked against what is on disk first:
  {"op": "delete", "kind": "routes", "id": 123, "expect_name": "..."}
  {"op": "set", "kind": "stations", "id": 123, "expect": {"name": "old"}, "fields": {"name": "new", "exits": [...]}}
  {"op": "add", "kind": "stations", "record": {...full record with a new id...}}
Writes the changed files, then reads every touched file back and compares. Prints a summary and writes
<out>/applied.json with the before and after of each record (the before copies are the undo).
usage: mtr_patch_records.py <world-mtr-dimension-dir> <patch.json> <out-dir>"""
import json
import os
import struct
import sys
from pathlib import Path

from mtr_dump_records import unpack


def pack(v):
    if v is None:
        return b'\xc0'
    if v is True:
        return b'\xc3'
    if v is False:
        return b'\xc2'
    if isinstance(v, int):
        if 0 <= v <= 0x7f:
            return bytes([v])
        if -32 <= v < 0:
            return struct.pack('b', v)
        if 0 <= v <= 0xff:
            return b'\xcc' + struct.pack('>B', v)
        if 0 <= v <= 0xffff:
            return b'\xcd' + struct.pack('>H', v)
        if 0 <= v <= 0xffffffff:
            return b'\xce' + struct.pack('>I', v)
        if 0 <= v <= 0xffffffffffffffff:
            return b'\xcf' + struct.pack('>Q', v)
        if -0x80 <= v:
            return b'\xd0' + struct.pack('>b', v)
        if -0x8000 <= v:
            return b'\xd1' + struct.pack('>h', v)
        if -0x80000000 <= v:
            return b'\xd2' + struct.pack('>i', v)
        return b'\xd3' + struct.pack('>q', v)
    if isinstance(v, float):
        return b'\xcb' + struct.pack('>d', v)
    if isinstance(v, str):
        b = v.encode('utf8')
        n = len(b)
        if n < 32:
            return bytes([0xa0 | n]) + b
        if n < 0x100:
            return b'\xd9' + bytes([n]) + b
        if n < 0x10000:
            return b'\xda' + struct.pack('>H', n) + b
        return b'\xdb' + struct.pack('>I', n) + b
    if isinstance(v, list):
        n = len(v)
        head = bytes([0x90 | n]) if n < 16 else (b'\xdc' + struct.pack('>H', n) if n < 0x10000 else b'\xdd' + struct.pack('>I', n))
        return head + b''.join(pack(x) for x in v)
    if isinstance(v, dict):
        n = len(v)
        head = bytes([0x80 | n]) if n < 16 else (b'\xde' + struct.pack('>H', n) if n < 0x10000 else b'\xdf' + struct.pack('>I', n))
        return head + b''.join(pack(str(k)) + pack(x) for k, x in v.items())
    raise TypeError(type(v))


def path_of(root, kind, rid):
    h = '%016X' % (rid & 0xffffffffffffffff)
    return Path(root) / kind / h[-2:] / h


def rail_path(root, rec):
    """Rails have no id: the file is named after both endpoints, the smaller one (x, y, z) first."""
    a, b = rec['position1'], rec['position2']
    p, q = sorted([(a['x'], a['y'], a['z']), (b['x'], b['y'], b['z'])])
    name = '-'.join('%016X' % (v & 0xffffffffffffffff) for v in p + q)
    return Path(root) / 'rails' / name[-2:] / name


def load(p):
    return unpack(Path(p).read_bytes())[0]


def main():
    root, patch, out = sys.argv[1], json.load(open(sys.argv[2], encoding='utf8')), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=False)
    plan = []
    for op in patch:
        kind = op['kind']
        if op['op'] == 'add':
            rec = op['record']
            p = rail_path(root, rec) if kind == 'rails' else path_of(root, kind, rec['id'])
            if p.exists():
                raise SystemExit(f'add: {p} already exists')
            plan.append((op, p, None, rec))
            continue
        if kind == 'rails':
            e = op['ends']
            p = rail_path(root, {'position1': dict(zip('xyz', e[0])), 'position2': dict(zip('xyz', e[1]))})
        else:
            p = path_of(root, kind, op['id'])
        if not p.exists():
            raise SystemExit(f'{op["op"]}: no record {p}')
        cur = load(p)
        if kind != 'rails' and cur.get('id') != op['id']:
            raise SystemExit(f'{p}: id {cur.get("id")} is not {op["id"]}')
        if op['op'] == 'delete':
            if 'expect_name' in op and cur.get('name') != op['expect_name']:
                raise SystemExit(f'delete {p}: name {cur.get("name")!r} is not {op["expect_name"]!r}')
            plan.append((op, p, cur, None))
        elif op['op'] == 'set':
            for k, v in op.get('expect', {}).items():
                if cur.get(k) != v:
                    raise SystemExit(f'set {p}: {k} is {cur.get(k)!r}, expected {v!r}')
            new = dict(cur)
            new.update(op['fields'])
            plan.append((op, p, cur, new))
        else:
            raise SystemExit('unknown op ' + op['op'])
    applied = []
    for op, p, before, after in plan:
        if after is None:
            p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(pack(after))
        applied.append(dict(op=op['op'], kind=op['kind'], file=str(p.relative_to(root)), before=before, after=after))
    bad = 0
    for a in applied:
        p = Path(root) / a['file']
        if a['after'] is None:
            bad += p.exists()
        else:
            bad += load(p) != a['after']
    json.dump(applied, open(out / 'applied.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(json.dumps({'operations': len(applied), 'readback_wrong': bad, 'kinds': sorted({a['kind'] for a in applied})}, ensure_ascii=False))


if __name__ == '__main__':
    main()

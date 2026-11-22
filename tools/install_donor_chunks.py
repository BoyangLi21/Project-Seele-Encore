"""Put whole chunks from a donor world into empty chunk slots of a stopped world.

For ground that the target world never saved (the outer ring is generated when someone first walks there), a cell
list cannot help: there is no chunk to write into. This copies verified chunks instead, record for record.

  pack:    install_donor_chunks.py pack --donor <world> --chunk-file <[[cx, cz], ...].json> --out <package-dir>
           Each chunk's raw region record (and its entities / poi records, if any) is saved with sha256 in
           package.json. The donor chunk must be FULL and carry its own coordinates.
  install: install_donor_chunks.py install --world <world> --package <package-dir> --backup <new-dir>
           Every target slot (region, entities, poi) must be empty, or nothing is written. Touched region files are
           copied to <backup>; the records are appended at the end of each file and read back byte for byte.
Only the projectseele:geofront dimension is handled; oversized (external .mcc) records are refused."""
import argparse
import hashlib
import json
import os
import shutil
import struct
import time
import zlib
from collections import defaultdict
from pathlib import Path

import nbtlib

DIM = Path('dimensions/projectseele/geofront')
KINDS = ('region', 'entities', 'poi')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def slot(cx, cz):
    return (cx & 31) + (cz & 31) * 32


def read_record(path, cx, cz):
    """Raw record (4-byte length + compression byte + payload) or None when the slot is empty."""
    if not path.exists():
        return None
    data = path.read_bytes()
    if len(data) < 8192:
        return None
    loc = struct.unpack('>I', data[slot(cx, cz) * 4:slot(cx, cz) * 4 + 4])[0]
    off, count = loc >> 8, loc & 255
    if off == 0 and count == 0:
        return None
    length = struct.unpack('>I', data[off * 4096:off * 4096 + 4])[0]
    record = data[off * 4096:off * 4096 + 4 + length]
    if record[4] & 128:
        raise SystemExit(f'{path.name} {cx},{cz}: oversized external record, not handled')
    return record


def decode(record):
    kind, payload = record[4], record[5:]
    raw = zlib.decompress(payload) if kind == 2 else (__import__('gzip').decompress(payload) if kind == 1 else payload)
    import io
    return nbtlib.File.parse(io.BytesIO(raw))


def region_name(cx, cz):
    return f'r.{cx >> 5}.{cz >> 5}.mca'


def pack(a):
    out = a.out
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(dimension='projectseele:geofront', chunks=[])
    for cx, cz in json.loads(a.chunk_file.read_text('utf8')):
        entry = dict(cx=cx, cz=cz)
        for kind in KINDS:
            rec = read_record(a.donor / DIM / kind / region_name(cx, cz), cx, cz)
            if kind == 'region':
                if rec is None:
                    raise SystemExit(f'{cx},{cz}: donor has no chunk')
                tag = decode(rec)
                root = tag.get('', tag)
                status = str(root.get('Status', '')).removeprefix('minecraft:')
                if status != 'full' or int(root['xPos']) != cx or int(root['zPos']) != cz:
                    raise SystemExit(f'{cx},{cz}: donor chunk is {status} at {int(root["xPos"])},{int(root["zPos"])}')
            if rec is None:
                continue
            name = f'{kind}.{cx}.{cz}.bin'
            (out / name).write_bytes(rec)
            entry[kind] = dict(file=name, sha256=sha(rec))
        manifest['chunks'].append(entry)
    (out / 'package.json').write_text(json.dumps(manifest, indent=1), 'utf8')
    print(json.dumps(dict(chunks=len(manifest['chunks']), entities=sum('entities' in c for c in manifest['chunks']),
                          poi=sum('poi' in c for c in manifest['chunks']))))


def append(path, records):
    """records: [(cx, cz, raw)] appended at the end of an existing or new region file; returns the new bytes."""
    data = bytearray(path.read_bytes()) if path.exists() else bytearray(8192)
    if len(data) < 8192:
        data.extend(bytes(8192 - len(data)))
    if len(data) % 4096:
        data.extend(bytes(4096 - len(data) % 4096))
    now = int(time.time())
    for cx, cz, raw in records:
        off = len(data) // 4096
        count = (len(raw) + 4095) // 4096
        if count > 255:
            raise SystemExit(f'{cx},{cz}: record of {count} sectors')
        data.extend(raw)
        data.extend(bytes(count * 4096 - len(raw)))
        i = slot(cx, cz)
        data[i * 4:i * 4 + 4] = struct.pack('>I', (off << 8) | count)
        data[4096 + i * 4:4096 + i * 4 + 4] = struct.pack('>I', now)
    return bytes(data)


def install(a):
    from install_r53_carrier_trays import stopped_world
    manifest = json.loads((a.package / 'package.json').read_text('utf8'))
    plan, problems = defaultdict(list), []
    for c in manifest['chunks']:
        for kind in KINDS:
            if kind not in c:
                continue
            raw = (a.package / c[kind]['file']).read_bytes()
            if sha(raw) != c[kind]['sha256']:
                problems.append(f"{c['cx']},{c['cz']} {kind}: package file changed")
            target = a.world / DIM / kind / region_name(c['cx'], c['cz'])
            if read_record(target, c['cx'], c['cz']) is not None:
                problems.append(f"{c['cx']},{c['cz']} {kind}: target slot is not empty")
            plan[target].append((c['cx'], c['cz'], raw))
    if problems:
        raise SystemExit('Preflight refused, nothing written:\n' + '\n'.join(problems[:30]))
    a.backup.mkdir(parents=True, exist_ok=False)
    with stopped_world(a.world):
        for target, records in plan.items():
            dest = a.backup / target.relative_to(a.world)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                shutil.copy2(target, dest)
            else:
                (dest.parent / (dest.name + '.absent')).write_text('', 'utf8')
            new = append(target, records)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + '.chunks-installing')
            tmp.write_bytes(new)
            os.replace(tmp, target)
    wrong = []
    for target, records in plan.items():
        for cx, cz, raw in records:
            if read_record(target, cx, cz) != raw:
                wrong.append([str(target.relative_to(a.world)), cx, cz])
    result = dict(status='installed', records=sum(len(r) for r in plan.values()), files=len(plan), readback_wrong=wrong)
    (a.backup / 'installation.json').write_text(json.dumps(result, indent=1), 'utf8')
    print(json.dumps(result))
    if wrong:
        raise SystemExit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    k = sub.add_parser('pack')
    k.add_argument('--donor', type=Path, required=True)
    k.add_argument('--chunk-file', type=Path, required=True)
    k.add_argument('--out', type=Path, required=True)
    i = sub.add_parser('install')
    i.add_argument('--world', type=Path, required=True)
    i.add_argument('--package', type=Path, required=True)
    i.add_argument('--backup', type=Path, required=True)
    a = p.parse_args()
    pack(a) if a.cmd == 'pack' else install(a)


if __name__ == '__main__':
    main()

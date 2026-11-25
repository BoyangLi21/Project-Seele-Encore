"""R65: replace a few entries of the shipped zips and copy every other entry's compressed record unchanged, so the
world, far view and minimap stay byte-identical (the R63r method). The output goes to --out; the delivery stays.

  python tools/r65_swap.py --date 20261125 --docs <checkout>/docs --docs-only --out <dir>
  python tools/r65_swap.py --date 20261125 --docs <checkout>/docs --jar <installed jar> --compare-build <public jar> --out <dir>
  ... --server-file SEELE_R53_WORLD/battlefield_r21.json=<file>   (server zip only, repeatable)

Writes <out>/<same zip names> and <out>/R65_<date>_receipt.json (the old receipt plus a "swaps" record), then checks
every copied record (name, order, CRC, sizes, method), the replaced entries against their sources, and a full CRC pass.
"""
import argparse, datetime, hashlib, json, sys, zlib, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_r60 import copy_zip_record, STORED  # noqa: E402

JAR = 'mods/projectseele-0.1.0-all.jar'
DOCS = ('R65_QUICKSTART.zh.md', 'R65_RELEASE.zh.md')
OUTER_RING = {'data/projectseele/worldgen/playtest_landscape_r64/': 213, 'data/projectseele/worldgen/playtest_floats_r64/': 130,
              'data/projectseele/worldgen/playtest_shores_r64/': 7}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def crc(path):
    value = 0
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            value = zlib.crc32(block, value)
    return value


def swap(source, target, replace, level):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'x', allowZip64=True) as dst:
        names = [i.filename for i in src.infolist()]
        assert set(replace) <= set(names), sorted(set(replace) - set(names))
        for info in src.infolist():
            if info.filename in replace:
                method = zipfile.ZIP_STORED if info.filename.lower().endswith(STORED) else zipfile.ZIP_DEFLATED
                dst.write(replace[info.filename], info.filename, compress_type=method, compresslevel=level)
            else:
                copy_zip_record(src, dst, info)
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target) as out:
        a, b = src.infolist(), out.infolist()
        assert [i.filename for i in a] == [i.filename for i in b]
        for x, y in zip(a, b):
            if x.filename in replace:
                assert y.CRC == crc(replace[x.filename]) and y.file_size == Path(replace[x.filename]).stat().st_size, x.filename
            else:
                assert (x.CRC, x.file_size, x.compress_size, x.compress_type) == (y.CRC, y.file_size, y.compress_size, y.compress_type), x.filename
        bad = out.testzip()
        assert bad is None, ('CRC failure', bad)
    return dict(file=str(target), bytes=target.stat().st_size, sha256=sha(target), entries=len(b),
                replaced={n: dict(bytes=Path(p).stat().st_size, sha256=sha(p)) for n, p in replace.items()})


def jar_facts(jar, compare):
    with zipfile.ZipFile(jar) as z:
        classes = {i.filename: i.CRC for i in z.infolist() if i.filename.startswith('com/projectseele/') and i.filename.endswith('.class')}
        ring = {p: sum(1 for i in z.infolist() if i.filename.startswith(p) and not i.filename.endswith('/')) for p in OUTER_RING}
    with zipfile.ZipFile(compare) as z:
        built = {i.filename: i.CRC for i in z.infolist() if i.filename.startswith('com/projectseele/') and i.filename.endswith('.class')}
    differ = sorted(n for n in classes.keys() | built.keys() if classes.get(n) != built.get(n))
    assert not differ, ('Jar classes differ from the build', differ[:10])
    assert all(ring[p] == n for p, n in OUTER_RING.items()), ('Outer-ring resources missing', ring)
    return dict(bytes=Path(jar).stat().st_size, sha256=sha(jar), classes=len(classes), compared_with=str(compare),
                outer_ring_files={p.rsplit('/', 2)[1]: n for p, n in ring.items()})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--date', required=True)
    p.add_argument('--delivery', type=Path, default=Path('F:/eva/delivery'))
    p.add_argument('--jar', type=Path)
    p.add_argument('--docs', type=Path, required=True, help='docs folder of a checkout at the commit the documents come from')
    p.add_argument('--compare-build', type=Path)
    p.add_argument('--docs-only', action='store_true', help='replace only the two documents; the shipped jar stays as it is')
    p.add_argument('--server-file', action='append', default=[], metavar='INNER=SOURCE',
                   help='also replace this entry of the server zip only (e.g. SEELE_R53_WORLD/battlefield_r21.json)')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert a.docs_only or (a.jar and a.compare_build), '--jar and --compare-build, or --docs-only'
    a.out.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((a.delivery / f'R65_{a.date}_receipt.json').read_bytes())
    jar = receipt['main_jar'] if a.docs_only else jar_facts(a.jar, a.compare_build)
    docs = {n: a.docs / n for n in DOCS}
    assert all(d.is_file() for d in docs.values())
    outputs = []
    for kind, prefix, level in (('Client_PCL', 'overrides/', 9), ('Server', '', 3)):
        name = f'Project_SEELE_Encore_R65_{a.date}_{kind}.zip'
        replace = ({} if a.docs_only else {prefix + JAR: a.jar}) | {prefix + n: d for n, d in docs.items()}
        if kind == 'Server':
            for item in a.server_file:
                inner, _, source = item.partition('=')
                assert Path(source).is_file() and not inner.startswith(('/', 'overrides/')), item
                replace[inner] = Path(source)
        print('Writing ' + name, flush=True)
        outputs.append(swap(a.delivery / name, a.out / name, replace, level))
    receipt.setdefault('swaps', []).append(dict(at=datetime.datetime.now().isoformat(timespec='seconds'), main_jar=jar,
                                                docs_only=a.docs_only, docs_from=str(a.docs), server_files=a.server_file,
                                                previous_outputs=receipt.get('outputs'), outputs=outputs,
                                                method='raw record copy of every other entry (world, far view, minimap unchanged)'))
    receipt['main_jar'], receipt['outputs'] = jar, outputs
    (a.out / f'R65_{a.date}_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=1), 'utf8')
    print('swapped: ' + ', '.join(o['file'] for o in outputs), flush=True)


if __name__ == '__main__':
    main()

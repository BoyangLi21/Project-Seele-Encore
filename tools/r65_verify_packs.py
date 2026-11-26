"""R65: zip-level checks of the two shipped archives against what they were made from (no extraction).

  python tools/r65_verify_packs.py --delivery F:/eva/delivery --date 20261125 \
      --lod <geofront_lod.sqlite> --area <SEELE_GeoFront_Area_Maps.zip> --xaero <projectseele$geofront source folder>

Checks: zip CRCs; both mod jars equal the receipt's jar, which is the main client's installed jar or (--jar-add) that
jar plus baked files only; the 350 outer-ring worldgen files; the client's far view, minimap and area-map pack equal
the hand-over; resource-pack order; PCL heap; both DistantHorizons.toml; view distances; the server's
projectseele-local-maps against the main client's. Writes <out>/verify_<date>.json; exit 1 on any failure.
"""
import argparse, hashlib, io, json, re, sys, zipfile
from pathlib import Path

MAIN = Path('F:/eva/artifacts/r53_repair_20261015/client')
JAR = 'mods/projectseele-0.1.0-all.jar'
RING = ('data/projectseele/worldgen/playtest_landscape_r64/', 'data/projectseele/worldgen/playtest_floats_r64/',
        'data/projectseele/worldgen/playtest_shores_r64/')
DH_KEYS = ('enableDistantGeneration', 'distantGeneratorMode', 'numberOfThreads', 'threadRunTimeRatio', 'dataCompression',
           'horizontalQuality', 'verticalQuality')
# What the packer writes (tools/package_r60.py): keep in step with client_dh_config, server_dh_config, FAR_VIEW_CHUNKS.
WANT_CLIENT_DH = {'enableDistantGeneration': 'true', 'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'numberOfThreads': '8',
                  'horizontalQuality': '"HIGH"', 'dataCompression': '"LZ4"'}
WANT_SERVER_DH = {'enableDistantGeneration': 'true', 'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'numberOfThreads': '2',
                  'dataCompression': '"LZ4"'}
FAR_VIEW = '20'


def sha_stream(f):
    h = hashlib.sha256()
    for block in iter(lambda: f.read(1 << 20), b''):
        h.update(block)
    return h.hexdigest()


def sha_file(p):
    with open(p, 'rb') as f:
        return sha_stream(f)


def ring(jar_file):
    with zipfile.ZipFile(jar_file) as z:
        return {i.filename: hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist()
                if i.filename.startswith(RING) and not i.filename.endswith('/')}


def dh_keys(text):
    return {k: m[1].strip() for k in DH_KEYS for m in [re.search(r'(?m)^\s*' + k + r'\s*=\s*(.*)$', text)] if m}


def line_value(text, prefix):
    hits = [l.strip()[len(prefix):] for l in text.splitlines() if l.startswith(prefix)]
    return hits[0] if len(hits) == 1 else hits


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--delivery', type=Path, required=True)
    p.add_argument('--date', required=True)
    p.add_argument('--lod', type=Path, required=True)
    p.add_argument('--area', type=Path, required=True)
    p.add_argument('--xaero', type=Path, required=True, help='the packer --xaero-map source folder')
    p.add_argument('--client-mod', type=Path, action='append', default=[],
                   help='a client-only mod the client pack must carry and the server pack must not (repeatable)')
    p.add_argument('--out', type=Path, default=Path('F:/eva/.claude/r63-pack-work'))
    a = p.parse_args()
    client_mods = {'mods/' + m.name: sha_file(m) for m in a.client_mod}
    client_zip = a.delivery / f'Project_SEELE_Encore_R65_{a.date}_Client_PCL.zip'
    server_zip = a.delivery / f'Project_SEELE_Encore_R65_{a.date}_Server.zip'
    out, fails = {}, []
    check = lambda ok, what: ok or fails.append(what)

    main_jar = MAIN / JAR
    main_sha, main_ring = sha_file(main_jar), ring(main_jar)
    check(len(main_ring) == 350, 'main client jar has %d outer-ring files' % len(main_ring))
    lod_sha, area_sha = sha_file(a.lod), sha_file(a.area)
    zips = [q.as_posix() for q in (a.xaero / 'cm$converted').rglob('*.zip')]
    xaero_count = dict(surface=sum('/caves/' not in q for q in zips), caves=sum('/caves/' in q for q in zips))
    out['inputs'] = dict(lod=str(a.lod), lod_sha256=lod_sha, area=str(a.area), area_sha256=area_sha, xaero=str(a.xaero),
                         xaero_regions=xaero_count, main_jar_sha256=main_sha)
    receipt = json.loads((a.delivery / f'R65_{a.date}_receipt.json').read_bytes())['main_jar']
    want_sha, additions = receipt['sha256'], receipt.get('jar_additions') or {}
    if additions:
        check(receipt['base_jar']['sha256'] == main_sha, 'the main client jar changed since the pack was made')
        with zipfile.ZipFile(main_jar) as z:
            base_entries = {i.filename: (i.CRC, i.file_size) for i in z.infolist()}
    else:
        check(want_sha == main_sha, 'receipt jar is not the main client jar')
    out['shipped_jar'] = dict(sha256=want_sha, additions=sorted(additions))

    for label, path, prefix in (('client', client_zip, 'overrides/'), ('server', server_zip, '')):
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            check(bad is None, f'{label} zip CRC error at {bad}')
            names = set(z.namelist())
            with z.open(prefix + JAR) as f:
                jar_bytes = io.BytesIO(f.read())
            jar_sha = sha_stream(io.BytesIO(jar_bytes.getvalue()))
            check(jar_sha == want_sha, f'{label} mod jar is not the jar the receipt records')
            r = ring(jar_bytes)
            check(r == main_ring, f'{label} outer-ring files differ from the main client jar ({len(r)} files)')
            if additions:
                with zipfile.ZipFile(jar_bytes) as j:
                    entries = {i.filename: (i.CRC, i.file_size) for i in j.infolist()}
                    changed = sorted(n for n in base_entries.keys() | entries.keys() if base_entries.get(n) != entries.get(n))
                    check(set(changed) <= set(additions), f'{label} jar differs from the installed one outside the baked files: {changed[:5]}')
                    for inner, meta in additions.items():
                        check(hashlib.sha256(j.read(inner)).hexdigest() == meta['sha256'], f'{label} jar: baked {inner} is not its source')
            entry = dict(bytes=path.stat().st_size, sha256=sha_file(path), entries=len(names), jar_sha256=jar_sha, outer_ring_files=len(r))
            dh = dh_keys(z.read(prefix + 'config/DistantHorizons.toml').decode('utf8'))
            entry['dh'] = dh
            want = WANT_CLIENT_DH if label == 'client' else WANT_SERVER_DH
            check(all(dh.get(k) == v for k, v in want.items()), f'{label} DH settings: {dh}')
            if label == 'client':
                opts = z.read('overrides/options.txt').decode('utf8')
                packs = json.loads(next(l for l in opts.splitlines() if l.startswith('resourcePacks:')).split(':', 1)[1])
                entry['resource_packs'] = packs
                entry['render_distance'] = line_value(opts, 'renderDistance:')
                check(entry['render_distance'] == FAR_VIEW, 'client renderDistance is %r' % entry['render_distance'])
                check(packs[-2:] == ['file/SEELE_GeoFront_Area_Maps.zip', 'file/SEELE_GreenGrassSide.zip'], 'resource pack order')
                for pack in packs:
                    if pack.startswith('file/'):
                        check('overrides/resourcepacks/' + pack[5:] in names, 'enabled pack missing: ' + pack)
                with z.open('overrides/resourcepacks/SEELE_GeoFront_Area_Maps.zip') as f:
                    check(sha_stream(f) == area_sha, 'area-map pack differs from the hand-over')
                setup = z.read('overrides/PCL/Setup.ini').decode('utf8')
                check('VersionRamType:1' in setup and 'VersionRamCustom:21' in setup, 'PCL Setup.ini lacks the 6 GB heap')
                lods = [n for n in names if n.startswith('overrides/Distant_Horizons_server_data/') and 'geofront' in n and n.endswith('.sqlite')]
                check(len(lods) == 1, 'client GeoFront LOD entries: %r' % lods)
                if lods:
                    with z.open(lods[0]) as f:
                        entry['geofront_lod_sha256'] = sha_stream(f)
                    check(entry['geofront_lod_sha256'] == lod_sha, 'client GeoFront LOD differs from the hand-over')
                xa = [n for n in names if '/xaero/' in n and n.endswith('.zip') and 'geofront' in n]
                entry['xaero_region_zips'] = dict(surface=sum('/caves/' not in n for n in xa), caves=sum('/caves/' in n for n in xa))
                check(entry['xaero_region_zips'] == xaero_count, 'minimap region count differs from the hand-over')
                check(not any(n.startswith('overrides/saves/') for n in names), 'client contains a save')
                for inner, want in client_mods.items():
                    present = 'overrides/' + inner in names
                    check(present, 'client mod missing: ' + inner)
                    if present:
                        with z.open('overrides/' + inner) as f:
                            check(sha_stream(f) == want, 'client mod differs from its source: ' + inner)
                entry['client_mods'] = sorted(client_mods)
            else:
                check('SEELE_R53_WORLD/level.dat' in names and 'server.jar' in names, 'server world or launcher missing')
                props = z.read('server.properties').decode('utf8')
                entry['view_distance'] = line_value(props, 'view-distance=')
                check(entry['view_distance'] == FAR_VIEW, 'server view-distance is %r' % entry['view_distance'])
                check(not any(n.startswith('mods/xaero') and 'lib' not in n for n in names), 'Xaero map mod on the server')
                check(not any(inner in names for inner in client_mods), 'a client-only mod is in the server pack')
                local = MAIN / 'projectseele-local-maps'
                want_maps = {('projectseele-local-maps/' + q.relative_to(local).as_posix()): sha_file(q) for q in local.rglob('*') if q.is_file()}
                have = {}
                for n in names:
                    if n.startswith('projectseele-local-maps/') and not n.endswith('/'):
                        with z.open(n) as f:
                            have[n] = sha_stream(f)
                differ = sorted(n for n in have if want_maps.get(n) != have[n])
                check(not differ, 'server projectseele-local-maps differs: %r' % differ[:5])
                check(set(have) == {n for n in want_maps if not n.lower().endswith(('.bak', '.old', '.backup', '.log', '.tmp', '.pyc'))},
                      'server projectseele-local-maps file set differs from the main client')
                entry['local_maps'] = dict(shipped=len(have), source=len(want_maps), differ=len(differ))
            out[label] = entry
    out['failures'] = fails
    text = json.dumps(out, ensure_ascii=False, indent=1)
    print(text)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f'verify_{a.date}.json').write_text(text, 'utf8')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()

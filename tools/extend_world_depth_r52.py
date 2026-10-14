"""Extend the fresh R52 save downwards without translating any old content.

The delivered archive is the exact inverse; do not create another whole-world
backup. Default mode checks detached native NBT fixtures and writes no save.
"""
from pathlib import Path
import argparse, copy, hashlib, json, math, msvcrt, os, time, zipfile
import nbtlib
import numpy as np
from r52_spatial_plan import BASE
from transplant_s22_authority import read_region, parse_chunk, build_region
from apply_s20_approved_semantic_repairs import atomic_replace, chunk_blob, encode_indices

WORLD = BASE/'WORLD_R52'
ARCHIVE = Path('D:/eva/delivery/Project_SEELE_Encore_R51_20261009_Server.zip')
PREFIX = 'SEELE_R50_WORLD/'
OLD_MIN, NEW_MIN, MAX_Y = -672, -960, 320
ADDED = (OLD_MIN-NEW_MIN)//16
REGION = Path('dimensions/projectseele/geofront/region')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def acquire_world_lock():
    path = WORLD/'session.lock'
    try:
        with path.open('xb') as created:
            created.write(bytes((0xe2,0x98,0x83)))
    except FileExistsError:
        pass
    lock = path.open('r+b')
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    return lock


def unpack_heights(raw, bits):
    per_long = 64//bits
    assert len(raw) == math.ceil(256/per_long), 'Unexpected native heightmap width'
    words = [int(v) & ((1 << 64)-1) for v in raw]
    return [((words[i//per_long] >> ((i % per_long)*bits)) & ((1 << bits)-1)) for i in range(256)]


def pack_heights(values, bits):
    per_long = 64//bits
    words = [0]*math.ceil(256/per_long)
    for i, value in enumerate(values):
        assert 0 <= value < 1 << bits
        words[i//per_long] |= value << ((i % per_long)*bits)
    return nbtlib.LongArray([v if v < 1 << 63 else v-(1 << 64) for v in words])


DEEPSLATE = nbtlib.Compound(Name=nbtlib.String('minecraft:deepslate'),
                          Properties=nbtlib.Compound(axis=nbtlib.String('y')))
BEDROCK = nbtlib.Compound(Name=nbtlib.String('minecraft:bedrock'))
FLOOR_IDS = np.zeros(4096, dtype=np.int32)
FLOOR_IDS[:256] = 1
FLOOR_DATA = encode_indices(FLOOR_IDS, 2)


def extend_chunk(root, old_min=OLD_MIN, new_min=NEW_MIN, max_y=MAX_Y):
    assert new_min<old_min<max_y and new_min%16==old_min%16==max_y%16==0
    added_count=(old_min-new_min)//16
    old_bits=math.ceil(math.log2(max_y-old_min+1));new_bits=math.ceil(math.log2(max_y-new_min+1))
    assert int(root.get('yPos', old_min//16)) == old_min//16
    sections = root.get('sections', nbtlib.List[nbtlib.Compound]())
    assert len({int(s['Y']) for s in sections}) == len(sections)
    assert not any(int(s['Y']) < old_min//16 and 'block_states' in s for s in sections), 'Existing deep geology needs a separate migration'
    old_real = [s for s in sections if int(s['Y']) >= old_min//16]
    biome_source = next((s['biomes'] for s in sorted(old_real, key=lambda s:int(s['Y'])) if 'biomes' in s),
                        nbtlib.Compound(palette=nbtlib.List[nbtlib.String]([nbtlib.String('minecraft:plains')])))
    added = []
    for sy in range(new_min//16, old_min//16):
        palette = [copy.deepcopy(DEEPSLATE)]
        states = nbtlib.Compound(palette=nbtlib.List[nbtlib.Compound](palette))
        if sy == new_min//16:
            states['palette'].append(copy.deepcopy(BEDROCK))
            states['data'] = FLOOR_DATA.copy()
        added.append(nbtlib.Compound(Y=nbtlib.Byte(sy), block_states=states,
                                    biomes=copy.deepcopy(biome_source)))
    root['sections'] = nbtlib.List[nbtlib.Compound](added+old_real)
    root['yPos'] = nbtlib.Int(new_min//16)
    for name in ('PostProcessing', 'Lights'):
        if name not in root:
            continue
        original = root[name]
        assert len(original) in (0, (max_y-old_min)//16), (name, len(original))
        if original:
            padding = [nbtlib.List[nbtlib.Short]() for _ in range(added_count)]
            root[name] = type(original)(padding+list(original))
    for name, raw in list(root.get('Heightmaps', {}).items()):
        values = unpack_heights(raw, old_bits)
        assert max(values) <= max_y-old_min
        root['Heightmaps'][name] = pack_heights([v+old_min-new_min for v in values], new_bits)
    for name, raw in list(root.get('CarvingMasks', {}).items()):
        assert isinstance(raw, nbtlib.LongArray)
        if len(raw):
            root['CarvingMasks'][name] = nbtlib.LongArray(np.concatenate((np.zeros(added_count*64,dtype=np.int64), np.asarray(raw))))
    # Absolute section Y and all old light arrays are retained. Lighting is
    # derived and must be recomputed under the new section bounds at load.
    root['isLightOn'] = nbtlib.Byte(0)
    return root


def verify_fixture(root, old_min=OLD_MIN, new_min=NEW_MIN, max_y=MAX_Y):
    before = copy.deepcopy(root)
    after = extend_chunk(copy.deepcopy(root),old_min,new_min,max_y)
    for key in set(before)-{'sections','yPos','Heightmaps','PostProcessing','Lights','CarvingMasks','isLightOn'}:
        assert before[key].snbt() == after[key].snbt(), ('Unrelated typed NBT changed',key)
    old = {int(s['Y']):s.snbt() for s in before['sections'] if int(s['Y']) >= old_min//16}
    new = {int(s['Y']):s.snbt() for s in after['sections']}
    assert all(new[y] == value for y,value in old.items()), 'Original section or biome altered'
    assert all(y in new for y in range(new_min//16,old_min//16))
    old_bits=math.ceil(math.log2(max_y-old_min+1));new_bits=math.ceil(math.log2(max_y-new_min+1))
    for name, raw in before.get('Heightmaps',{}).items():
        assert [v+old_min-new_min for v in unpack_heights(raw,old_bits)] == unpack_heights(after['Heightmaps'][name],new_bits)
    return after


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--rollback-interrupted',action='store_true')
    args = parser.parse_args()
    baseline = json.loads((BASE/'BASELINE.json').read_text('utf8'))
    original = {r['path']:r for r in baseline['files']}
    paths = sorted((WORLD/REGION).glob('r.*.mca'))
    assert all(not p.is_symlink() and not p.is_junction() for p in (WORLD, WORLD/REGION, *paths))
    report = BASE/'depth_extension'
    report.mkdir(exist_ok=True)
    journal = report/'REGION_JOURNAL.jsonl'
    if args.rollback_interrupted:
        assert not args.apply and not (report/'APPLIED.json').exists()
        rows = [json.loads(line) for line in journal.read_text('utf8').splitlines()]
        lock = acquire_world_lock()
        try:
            with zipfile.ZipFile(ARCHIVE) as archive:
                for row in reversed(rows):
                    target = (WORLD/row['path']).resolve()
                    assert target.is_relative_to(WORLD.resolve())
                    assert digest(target.read_bytes()) in (row['before_sha256'],row['after_sha256']), 'External change after interruption'
                    raw = archive.read(PREFIX+row['path'])
                    assert digest(raw) == row['before_sha256']
                    atomic_replace(target,raw)
            journal.rename(report/('ROLLED_BACK_'+str(time.time_ns())+'.jsonl'))
        finally:
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1); lock.close()
        print('Recovered original region bytes after interrupted migration',len(rows))
        return
    # Real frozen FULL and unfinished chunks exercise the same serializer.
    checked = set()
    for path in paths:
        if path.stat().st_size == 0:
            continue
        for blob in read_region(path)[1]:
            if blob is None:
                continue
            root = parse_chunk(blob)
            kind = (str(root['Status']),bool(root.get('Heightmaps')),bool(root.get('CarvingMasks')))
            if kind in checked:
                continue
            value = verify_fixture(root)
            roundtrip = parse_chunk(chunk_blob(value))
            assert value.snbt() == roundtrip.snbt()
            checked.add(kind)
        if len(checked) >= 9:
            break
    fixture = dict(kinds=sorted(checked),save_written=False,old_absolute_sections_unchanged=True,
                   old_actor_inventory_and_ticks_unchanged=True,heightmap_offset=288,
                   old_heightmap_bits=10,new_heightmap_bits=11)
    mask_fixture = copy.deepcopy(root)
    mask_fixture['CarvingMasks'] = nbtlib.Compound(AIR=nbtlib.LongArray([1, -(1 << 63), 3]))
    shifted_mask = verify_fixture(mask_fixture)['CarvingMasks']['AIR']
    assert len(shifted_mask) == ADDED*64+3
    assert not np.any(np.asarray(shifted_mask[:ADDED*64]))
    assert list(map(int,shifted_mask[ADDED*64:])) == [1,-(1 << 63),3]
    fixture['synthetic_nonempty_carving_mask_bit_offset_preserved'] = True
    (report/'FIXTURE.json').write_text(json.dumps(fixture,indent=2),'utf8')
    print('Detached NBT fixtures:',len(checked),flush=True)
    if not args.apply:
        return
    receipt = report/'APPLIED.json'
    assert not receipt.exists(), 'Already extended; do not replay'
    assert not journal.exists(), 'Unfinished transaction: inspect journal and explicitly roll it back'
    resource = Path(__file__).resolve().parents[1]/'src/main/resources/data/projectseele/dimension_type/geofront.json'
    assert json.loads(resource.read_text())['min_y'] == NEW_MIN
    lock = acquire_world_lock()
    touched = []; total = 0; started = time.monotonic()
    with zipfile.ZipFile(ARCHIVE) as archive, journal.open('x',encoding='utf8') as log:
        try:
            # All region preconditions are checked before the first write.
            for path in paths:
                key = path.relative_to(WORLD).as_posix()
                assert digest(path.read_bytes()) == original[key]['sha256'], ('World changed since original baseline',key)
                assert archive.getinfo(PREFIX+key).file_size == original[key]['bytes']
                with archive.open(PREFIX+key) as inverse:
                    assert hashlib.file_digest(inverse,'sha256').hexdigest() == original[key]['sha256'], 'Archive inverse changed'
            for path in paths:
                if path.stat().st_size == 0:
                    continue
                key = path.relative_to(WORLD).as_posix()
                stamps, blobs = read_region(path)
                count = 0
                for i, blob in enumerate(blobs):
                    if blob is not None:
                        blobs[i] = chunk_blob(extend_chunk(parse_chunk(blob)))
                        count += 1
                if not count:
                    continue
                raw = build_region(stamps,blobs)
                # Record the archive inverse before an atomic replacement.
                touched.append(dict(path=key,before_sha256=original[key]['sha256'],after_sha256=digest(raw),chunks=count))
                log.write(json.dumps(touched[-1])+'\n'); log.flush(); os.fsync(log.fileno())
                atomic_replace(path,raw)
                assert digest(path.read_bytes()) == touched[-1]['after_sha256']
                total += count
                if len(touched)%10 == 0:
                    print('Extended regions',len(touched),'chunks',total,flush=True)
            receipt.write_text(json.dumps(dict(world=str(WORLD),new_min_y=NEW_MIN,max_y=MAX_Y,
                original_archive=str(ARCHIVE),archive_prefix=PREFIX,regions=touched,chunks=total,
                old_absolute_blocks_and_biomes_unchanged=True,entity_player_mtr_files_written=False,
                elapsed_seconds=time.monotonic()-started,native_accepted=False),indent=2),'utf8')
        except BaseException:
            for row in touched:
                raw = archive.read(PREFIX+row['path'])
                assert digest(raw) == row['before_sha256']
                atomic_replace(WORLD/row['path'],raw)
            raise
        finally:
            msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            lock.close()
    print('Complete depth extension',total,'chunks; native load pending',flush=True)


if __name__ == '__main__':
    main()

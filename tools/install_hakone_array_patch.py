"""Install composed measured map arrays, preserving unrelated chunks and progress.

All staging and the final write happen while the actual world's lock is held.
Inputs carry exact inverse states; no save is replaced by an authoring snapshot.
The existing query_blocks reader and region writer own the Anvil format.
"""
from pathlib import Path
from collections import defaultdict
import argparse, copy, io, json, shutil, time, zipfile
import nbtlib
import numpy as np
from concurrent.futures import ProcessPoolExecutor,as_completed
from query_blocks import iter_selected_sections, dimension_dir
from regional_voxels import canonical_state
from transplant_s22_authority import read_region, parse_chunk, build_region
from apply_s20_approved_semantic_repairs import parse_state, encode_indices, chunk_blob, atomic_replace
from install_r53_carrier_trays import stopped_world
from map_pipeline.install.invariants import assert_chunk_preserved
from map_pipeline.launch_protection import load as launch_protection, check_candidate

DIM = 'projectseele:geofront'
DATA = Path('dimensions/projectseele/geofront/data')
Y0 = -128


class Palette:
    def __init__(self):
        self.names = ['minecraft:air']; self.ids = {self.names[0]: 0}

    def codes(self, names):
        result = []
        for raw in names:
            name = canonical_state(str(raw))
            if name not in self.ids:
                self.ids[name] = len(self.names); self.names.append(name)
            result.append(self.ids[name])
        return np.asarray(result, np.int32)


def compose(files, palette):
    chunks = {}
    for file in files:
        with np.load(file) as a:
            remap = palette.codes(a['palette'])
            coordinates, ranges, indices, old, new = (a[k] for k in ('coordinates','ranges','indices','before','after'))
            for i, coordinate in enumerate(coordinates):
                key = tuple(map(int, coordinate)); left, right = ranges[i:i+2]
                at = indices[left:right].astype(np.int32); before = remap[old[left:right]]; after = remap[new[left:right]]
                if key in chunks:
                    old_at, old_before, old_after = chunks[key]
                    common, ai, bi = np.intersect1d(old_at, at, return_indices=True)
                    if np.any(old_before[ai] != before[bi]):
                        raise ValueError(f'Candidates disagree about original states in {key}')
                    conflicting = np.flatnonzero(old_after[ai] != after[bi])
                    if len(conflicting):
                        offset = int(common[int(conflicting[0])])
                        pos = (key[0]*16+offset%16, Y0+offset//256, key[1]*16+(offset//16)%16)
                        raise ValueError(f'Conflicting final states at {pos}; resolve geometry before installation')
                    all_at = np.union1d(old_at, at)
                    all_before = np.empty(len(all_at), np.int32); all_after = all_before.copy()
                    oi = np.searchsorted(all_at, old_at); ni = np.searchsorted(all_at, at)
                    all_before[oi] = old_before; all_after[oi] = old_after
                    all_before[ni] = before; all_after[ni] = after
                    at, before, after = all_at, all_before, all_after
                keep = before != after
                chunks[key] = (at[keep], before[keep], after[keep])
    return chunks


def selected(chunks):
    return {p: set(map(int, np.unique(at//4096 + Y0//16))) for p, (at, _, _) in chunks.items() if len(at)}


def prepare_region(world, region_key, chunks, devices, palette, destination, expected_statuses=None):
    rx, rz = region_key; path = dimension_dir(world, DIM)/'region'/f'r.{rx}.{rz}.mca'
    times, raw = read_region(path)
    decoded = {(cx, cz, sy): (palette.codes(names), ids) for cx, cz, sy, names, ids
               in iter_selected_sections(world, DIM, selected(chunks),expected_statuses=expected_statuses)}
    for cx, cz in chunks.keys() | devices.keys():
        slot = (cz % 32)*32 + cx % 32
        if raw[slot] is None: raise ValueError(f'Missing chunk {(cx,cz)}')
        root = parse_chunk(raw[slot])
        original = copy.deepcopy(root)
        expected='full' if expected_statuses is None else expected_statuses.get((cx,cz),'full')
        if str(root.get('Status', '')).removeprefix('minecraft:') != expected:
            raise ValueError(f'Changed chunk generation status {(cx,cz)}')
        sections = {int(s['Y']): s for s in root['sections']}
        at, before, after = chunks.get((cx, cz), (np.array([], dtype=int),)*3)
        for tag in root.get('block_entities', []):
            pos = tuple(int(tag[k]) for k in ('x','y','z'))
            offset = (pos[1]-Y0)*256+(pos[2]%16)*16+pos[0]%16
            if np.any(at == offset) and pos not in devices.get((cx, cz), {}):
                raise ValueError(f'Undeclared device host edit at {pos}')
        for sy in np.unique(at//4096 + Y0//16):
            mask = at//4096 + Y0//16 == sy; offsets = at[mask] % 4096
            remap, ids = decoded.get((cx, cz, int(sy)), (np.array([0]), np.zeros(4096, np.int32)))
            values = remap[ids]
            mismatch = np.flatnonzero(values[offsets] != before[mask])
            if len(mismatch):
                i = int(mismatch[0]); off = int(offsets[i])
                pos = (cx*16+off%16, int(sy)*16+off//256, cz*16+(off//16)%16)
                raise ValueError(f'Changed source at {pos}: {palette.names[values[off]]}; expected {palette.names[before[mask][i]]}')
            values[offsets] = after[mask]
            used, encoded = np.unique(values, return_inverse=True)
            state = nbtlib.Compound({'palette': nbtlib.List[nbtlib.Compound]([parse_state(palette.names[v]) for v in used])})
            if len(used) > 1: state['data'] = encode_indices(encoded, len(used))
            if int(sy) not in sections:
                reference = min(sections, key=lambda y: abs(y-int(sy)))
                section = nbtlib.Compound({'Y': nbtlib.Byte(sy), 'biomes': copy.deepcopy(sections[reference]['biomes'])})
                root['sections'].append(section); sections[int(sy)] = section
            sections[int(sy)]['block_states'] = state
        bes = {tuple(int(b[k]) for k in ('x','y','z')): b for b in root.get('block_entities', [])}
        for pos, change in devices.get((cx, cz), {}).items():
            if bes.get(pos) != change.get('Before'):
                raise ValueError(f'Changed device contents at {pos}')
            if 'After' in change: bes[pos] = copy.deepcopy(change['After'])
            else: bes.pop(pos, None)
        root['block_entities'] = nbtlib.List[nbtlib.Compound](bes.values())
        for key in ('Heightmaps', 'isLightOn', 'starlight.light_version'): root.pop(key, None)
        for section in root['sections']:
            for key in ('BlockLight','SkyLight','starlight.blocklight_state','starlight.skylight_state'): section.pop(key, None)
        serialized = chunk_blob(root)
        assert_chunk_preserved(original, parse_chunk(serialized),
            set(map(int, np.unique(at//4096 + Y0//16))), devices.get((cx, cz), {}))
        raw[slot] = serialized
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_replace(destination, build_region(times, raw))


def prepare_jar(installed, compiled, target, resources_only=False, terrain_consumer_only=False):
    # The live distribution has large authored models absent from the small
    # code build. Keep authored assets, but carry the mixin declarations and
    # mappings with their new classes so newly added compatibility fixes load.
    with zipfile.ZipFile(installed) as old, zipfile.ZipFile(compiled) as new:
        if resources_only or terrain_consumer_only:
            resource='data/projectseele/worldgen/hakone_surface.bin.gz'
            if resource not in new.namelist():raise ValueError('Missing compiled terrain resource')
            replace={resource}
            blend='data/projectseele/worldgen/hakone_surface_blend.bin.gz'
            if blend in new.namelist():replace.add(blend)
            class_count=0
            if terrain_consumer_only:
                if blend not in replace:raise ValueError('Terrain consumer requires its matching blend field')
                for suffix in ('','\u0024Field','\u0024Surface'):
                    name='com/projectseele/world/HakoneSurfaceField'+suffix+'.class'
                    if name not in new.namelist():raise ValueError('Missing selected terrain consumer '+name)
                    replace.add(name);class_count+=1
            # Map-only deliveries must not replace a collaborator's entity,
            # animation or renderer classes from a separate working copy.
            with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1)as out:
                # Retain the original compressed records verbatim. Large
                # collaborator models need neither decoding nor recompression
                # to replace one small map resource. ZipFile writes fresh
                # central-directory offsets when the archive closes.
                entries=sorted(old.infolist(),key=lambda entry:entry.header_offset)
                if len({entry.filename for entry in entries})!=len(entries):
                    raise ValueError('Installed JAR has ambiguous duplicate entries')
                for i,entry in enumerate(entries):
                    if entry.filename in replace:continue
                    end=entries[i+1].header_offset if i+1<len(entries)else old.start_dir
                    start=entry.header_offset;updated=copy.copy(entry);updated.header_offset=out.fp.tell()
                    # Central ZIP64 offsets refer to the old archive. Sizes
                    # and new offsets are regenerated from ZipInfo below.
                    extra=bytearray();offset=0
                    while offset<len(updated.extra):
                        kind=int.from_bytes(updated.extra[offset:offset+2],'little')
                        size=int.from_bytes(updated.extra[offset+2:offset+4],'little');limit=offset+4+size
                        if limit>len(updated.extra):raise ValueError('Malformed installed ZIP extra record')
                        if kind!=1:extra.extend(updated.extra[offset:limit])
                        offset=limit
                    updated.extra=bytes(extra);old.fp.seek(start);remaining=end-start
                    while remaining:
                        block=old.fp.read(min(1024*1024,remaining))
                        if not block:raise ValueError('Truncated installed JAR record')
                        out.fp.write(block);remaining-=len(block)
                    out.filelist.append(updated);out.NameToInfo[updated.filename]=updated
                out.start_dir=out.fp.tell();out.comment=old.comment
                for name in sorted(replace):out.writestr(name,new.read(name))
            return class_count
        names = [n for n in new.namelist() if n.startswith('com/projectseele/') and n.endswith('.class')]
        if 'com/projectseele/world/CityRigidGenerationR45.class' not in names: raise ValueError('Missing native city generation class')
        class_count=len(names)
        for name in ('projectseele.mixins.json','projectseele.refmap.json','data/projectseele/worldgen/hakone_surface.bin.gz'):
            if name not in new.namelist():raise ValueError('Missing compiled mixin resource '+name)
            names.append(name)
        blend='data/projectseele/worldgen/hakone_surface_blend.bin.gz'
        if blend in new.namelist():names.append(blend)
        new_names = set(names)
        with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as out:
            for entry in old.infolist():
                if entry.filename in new_names or (entry.filename.startswith('com/projectseele/') and entry.filename.endswith('.class')):
                    continue
                out.writestr(entry, old.read(entry.filename))
            for name in names: out.writestr(name, new.read(name))
    return class_count


def encode_device_changes(devices):
    """Carry typed inventory/sign NBT across spawn workers as NBT bytes.

    nbtlib's generated List[String]/List[Compound] classes cannot be pickled
    reliably. JSON would lose tag types and large integer identity values.
    """
    rows=[]
    for chunk,changes in sorted(devices.items()):
        for pos,change in sorted(changes.items()):
            rows.append(nbtlib.Compound({'Chunk':nbtlib.IntArray(chunk),'Pos':nbtlib.IntArray(pos),'Change':copy.deepcopy(change)}))
    stream=io.BytesIO();nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](rows)}).write(stream)
    return stream.getvalue()


def decode_device_changes(payload):
    result=defaultdict(dict)
    for row in nbtlib.File.parse(io.BytesIO(payload))['Changes']:
        result[tuple(map(int,row['Chunk']))][tuple(map(int,row['Pos']))]=row['Change']
    return dict(result)


def stage_region_job(world,region_key,inputs,device_payload,stage,expected_statuses):
    devices=decode_device_changes(device_payload)
    palette=Palette();chunks=compose(inputs,palette)
    relative=DATA.parent/'region'/f'r.{region_key[0]}.{region_key[1]}.mca'
    prepare_region(world,region_key,chunks,devices,palette,stage/relative,expected_statuses)
    return world/relative,stage/relative,sum(len(v[0])for v in chunks.values()),{(cx//4,cz//4)for cx,cz in chunks}


def install(a):
    if a.backup.exists(): raise ValueError('Choose a fresh installation directory; never replay automatically')
    manifests = [json.loads((c/'manifest.json').read_text('utf8')) for c in a.candidate]
    expected_statuses={}
    for m in manifests:
        for cx,cz,status in m.get('preserved_generation_statuses',[]):
            if status not in ('noise','surface','carvers','features','initialize_light','light','spawn','full'):
                raise ValueError('Boundary repair requires an already generated terrain column')
            if(cx,cz)in expected_statuses and expected_statuses[cx,cz]!=status:raise ValueError('Conflicting generation states')
            expected_statuses[cx,cz]=status
    if any(Path(m['world']).resolve() != a.world.resolve() for m in manifests): raise ValueError('Wrong actual world')
    protection = launch_protection(a.world)
    launch_checks = [check_candidate(protection, candidate) for candidate in a.candidate]
    for candidate in a.candidate:
        check = json.loads((candidate/'functional-check.json').read_text('utf8'))
        if check['errors']: raise ValueError('Unresolved authored path errors: '+str(candidate))
        manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
        if 'legacy_water_banks' in manifest:
            banks=json.loads((candidate/'water-bank-check.json').read_text('utf8'))
            if banks['errors'] or banks['exposed_Y62_water_faces']:
                raise ValueError('Unclosed legacy water bank candidate')
        if 'terrain_inputs' in manifest:
            if not a.compiled_jar:raise ValueError('Pending-terrain candidate requires its matching terrain delivery')
            with zipfile.ZipFile(a.compiled_jar)as bundle:
                for name,relative in manifest['terrain_inputs'].items():
                    if name not in ('data/projectseele/worldgen/hakone_surface.bin.gz','data/projectseele/worldgen/hakone_surface_blend.bin.gz'):
                        raise ValueError('Unrecognized terrain dependency')
                    path=(candidate/relative).resolve()
                    if not path.is_relative_to(candidate.resolve()):raise ValueError('Invalid terrain dependency path')
                    if bundle.read(name)!=path.read_bytes():raise ValueError('Compiled terrain differs from the pending-chunk candidate input')
        if 'streets' in manifest:
            verified=json.loads((candidate/'independent-check.json').read_text('utf8'))
            expected={r['id']:r['walk_columns'] for r in manifest['streets'] if r['status']=='prepared'}
            observed={r['id']:r['full_width_columns'] for r in verified['streets']}
            if verified['errors'] or expected!=observed:
                raise ValueError('Incomplete independent corridor verification: '+str(candidate))
            design=json.loads((candidate/'authored-design.json').read_text('utf8'))
            tunnels={r['id']for r in design['streets']if r.get('tunnel')}
            if tunnels:
                tunnel_check=json.loads((candidate/'tunnel-check.json').read_text('utf8'))
                if tunnel_check['errors'] or {r['id']for r in tunnel_check['tunnels']}!=tunnels:
                    raise ValueError('Incomplete independent tunnel verification: '+str(candidate))
    for candidate in a.candidate:
        for preserved in (candidate/'preserved').glob('*control*.dat'):
            old = nbtlib.load(preserved)['data']; current = nbtlib.load(a.world/DATA/preserved.name)['data']
            for key in ('WorldUUID','Phase','Depth','Target','Journey','WorldTouched'):
                if current.get(key) != old.get(key): raise ValueError(f'City moved since authoring: {key}')
    files = defaultdict(list)
    for candidate in a.candidate:
        for file in (candidate/'delta').glob('*.npz'):
            _, rx, rz, _ = file.name.split('.'); files[int(rx), int(rz)].append(file)
    devices = defaultdict(lambda: defaultdict(dict))
    for candidate in a.candidate:
        file=candidate/'block-entities.dat'
        if not file.exists():continue
        for r in nbtlib.load(file)['Changes']:
            tag = r.get('Before', r.get('After')); x,y,z = (int(tag[k]) for k in ('x','y','z'))
            previous=devices[x//512,z//512][x//16,z//16].get((x,y,z))
            if previous is not None and previous!=r:raise ValueError(f'Conflicting device changes at {(x,y,z)}')
            devices[x//512, z//512][x//16, z//16][x,y,z] = r
            files.setdefault((x//512,z//512), [])
    metadata = []
    metadata_targets=set()
    for candidate in a.candidate:
        for after in (candidate/'after').rglob('*.dat'):
            relative = after.relative_to(candidate/'after'); current = a.world/relative; prior = candidate/'before'/relative
            if current in metadata_targets:raise ValueError(f'Overlapping metadata candidates: {relative}')
            if prior.exists():
                if not current.exists():raise ValueError(f'Missing current metadata: {relative}')
                # Captured recipe files are normally byte-identical copies.
                # Decode potentially large NBT only if their bytes changed;
                # semantic equality still accepts harmless recompression.
                if prior.read_bytes()!=current.read_bytes() and nbtlib.load(prior)!=nbtlib.load(current):
                    raise ValueError(f'Changed metadata: {relative}')
            elif current.exists(): raise ValueError(f'New metadata already exists: {relative}')
            metadata.append((current, after));metadata_targets.add(current)
        manifest=json.loads((candidate/'manifest.json').read_text('utf8'))
        for name in manifest.get('native_members',[]):
            relative=Path(name)
            if relative.is_absolute()or'..'in relative.parts or relative.parts[:3]!=('mtr','projectseele','geofront'):
                raise ValueError('Unexpected native member destination')
            current=a.world/relative;prior=candidate/'before'/relative;after=candidate/'after'/relative
            if current in metadata_targets:raise ValueError('Overlapping native member repair')
            if current.read_bytes()!=prior.read_bytes():raise ValueError('Native service changed after repair preparation')
            metadata.append((current,after));metadata_targets.add(current)
    a.backup.mkdir(parents=True)
    stage = a.backup/'prepared'; original = a.backup/'original'; stage.mkdir(); original.mkdir()
    journal = dict(status='preparing', world=str(a.world), candidates=[str(c) for c in a.candidate], files=[], progress_files_written=[], launch_protection=launch_checks)
    receipt = a.backup/'installation.json'
    def save(): atomic_replace(receipt, json.dumps(journal, indent=2).encode())
    save(); start = time.monotonic(); total = 0; tile_set = set(); plans = []
    # Workers only prepare separate region files. The parent retains the world
    # lock; backup, publication and rollback stay serialized below.
    try:
        with ProcessPoolExecutor(max_workers=getattr(a,'workers',1))as pool:
            jobs=[pool.submit(stage_region_job,a.world,key,inputs,encode_device_changes(devices[key]),stage,expected_statuses)for key,inputs in sorted(files.items())]
            for future in as_completed(jobs):
                target,prepared,cells,tiles=future.result()
                plans.append((target,prepared));total+=cells;tile_set.update(tiles)
                print(f'Prepared {len(plans)}/{len(files)} regions; {total:,} changed cells; {round(time.monotonic()-start)} s',flush=True)
    except BaseException as error:
        journal.update(status='staging-failed',actual_files_written=0,error_type=type(error).__name__);save()
        raise
    plans.sort(key=lambda row:str(row[0]))
    plans.extend(metadata)
    jar_classes = 0
    def jar_version():
        info=a.installed_jar.stat();return info.st_size,info.st_mtime_ns
    def unchanged_jar():
        if a.installed_jar and jar_version()!=original_jar_version:
            raise ValueError('Installed JAR changed during map staging; retain the collaborator update and rebuild the resource-only merge')
    if a.installed_jar:
        original_jar_version=jar_version()
        prepared_jar = stage/'projectseele-0.1.0-all.jar'
        jar_classes = prepare_jar(a.installed_jar, a.compiled_jar, prepared_jar,getattr(a,'terrain_resource_only',False),getattr(a,'terrain_consumer_only',False))
        unchanged_jar()
        plans.append((a.installed_jar, prepared_jar))
    for i, (target, source) in enumerate(plans):
        backup = original/str(i)
        if target.exists(): shutil.copy2(target, backup)
        journal['files'].append(dict(target=str(target), staged=str(source), backup=str(backup) if backup.exists() else None))
    journal.update(status='prepared', cells=total, regions=len(files), metadata_files=len(metadata), jar_classes=jar_classes, tiles=sorted(tile_set)); save()
    written = []
    try:
        unchanged_jar()
        for item in journal['files']:
            target = Path(item['target']); target.parent.mkdir(parents=True, exist_ok=True)
            if a.installed_jar and target==a.installed_jar:unchanged_jar()
            atomic_replace(target, Path(item['staged']).read_bytes()); written.append(item)
        journal['status'] = 'written'; save()
        # Read back changed sections, not untouched regions or whole-save data.
        for region_key, inputs in sorted(files.items()):
            palette = Palette(); chunks = compose(inputs, palette); pending = selected(chunks)
            for cx,cz,sy,names,ids in iter_selected_sections(a.world, DIM, pending,expected_statuses=expected_statuses):
                at, _, after = chunks[cx,cz]; mask = at//4096 + Y0//16 == sy
                actual = palette.codes(names)[ids[at[mask]%4096]]
                if np.any(actual != after[mask]): raise ValueError(f'Installed section mismatch {(cx,cz,sy)}')
                pending[cx,cz].discard(sy)
            if any(pending.values()): raise ValueError(f'Missing written sections {region_key}')
        device_count=0
        for (rx,rz),chunks in devices.items():
            _,raw=read_region(dimension_dir(a.world,DIM)/'region'/f'r.{rx}.{rz}.mca')
            for (cx,cz),changes in chunks.items():
                root=parse_chunk(raw[(cz%32)*32+cx%32])
                actual={tuple(int(tag[k])for k in('x','y','z')):tag for tag in root.get('block_entities',[])}
                for pos,change in changes.items():
                    if actual.get(pos)!=change.get('After'):raise ValueError(f'Installed device NBT mismatch {pos}')
                    device_count+=1
        journal.update(status='installed', seconds=round(time.monotonic()-start), changed_section_readback=True,
            changed_device_nbt_readback=device_count,lod='required'); save()
        print(json.dumps({k:v for k,v in journal.items() if k not in ('files','tiles')}), flush=True)
    except BaseException:
        for item in reversed(written):
            target = Path(item['target'])
            if item['backup']: atomic_replace(target, Path(item['backup']).read_bytes())
            else: target.unlink(missing_ok=True)
        journal['status'] = 'rolled-back'; save(); raise


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ('world','backup'): p.add_argument('--'+name, type=Path, required=True)
    for name in ('installed-jar','compiled-jar'): p.add_argument('--'+name, type=Path)
    p.add_argument('--terrain-resource-only',action='store_true',help='Replace only the compiled terrain resource; retain all installed code and assets')
    p.add_argument('--terrain-consumer-only',action='store_true',help='Replace only HakoneSurfaceField and its two data records plus both matching terrain resources')
    p.add_argument('--candidate', type=Path, action='append', required=True, help='Compatible arrays; conflicting final states are rejected')
    p.add_argument('--workers',type=int,choices=range(1,5),default=1,help='Parallel staging only; publication stays under the parent world lock')
    a = p.parse_args()
    if bool(a.installed_jar)!=bool(a.compiled_jar):p.error('Supply both JAR paths or neither')
    if a.terrain_resource_only and not a.installed_jar:p.error('Terrain resource mode requires both JAR paths')
    if a.terrain_consumer_only and not a.installed_jar:p.error('Terrain consumer mode requires both JAR paths')
    if a.terrain_resource_only and a.terrain_consumer_only:p.error('Choose one terrain delivery mode')
    with stopped_world(a.world): install(a)


if __name__ == '__main__': main()

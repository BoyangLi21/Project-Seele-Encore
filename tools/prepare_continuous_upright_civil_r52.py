"""Root-owned continuous upright civil replacement, with reversible deltas.

The three original loading galleries and bank-two vertical section stay in
place. Only withdrawn R52 launch excavation is restored, before the final
full-assembly envelope is lined. This is not runtime route admission.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
import argparse, gzip, hashlib, json, msvcrt
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import regional_voxels as vox
from query_blocks import iter_selected_sections, iter_block_entities
from r52_spatial_plan import BASE
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock

ROOT = Path(__file__).resolve().parents[1]
WORLD = BASE / 'WORLD_R52'
OUT = BASE / 'continuous_upright/civil_replacement'
MEASURE = BASE / 'continuous_upright/civil_measurement'
LOCAL = np.indices((16, 16, 16)).reshape(3, -1).T[:, [2, 0, 1]]
STAGE = 'final_continuous_upright_lining'
RETIRED = [
    'fixed_foot_rail_foundations/connectors/selected_37_finite_structural_connections',
    'fixed_foot_rail_foundations/existing_shell_native_sockets',
    'bank3_outlet_final/final_parallel_full_assembly_civil',
    'bank1_outlet/bank1_foot_bearing_surface_connection',
]


def slot(p):
    x, y, z = map(int, p)
    return (x // 16, z // 16, y // 16), (y % 16) * 256 + (z % 16) * 16 + x % 16


def xyz_for(key):
    return LOCAL + np.array(key)[[0, 2, 1]] * 16


def cuboids(painter, lo, before, after, palette, owner):
    """Losslessly merge equal exact row runs, then adjacent full Z strips."""
    rectangles = []
    for y in range(before.shape[0]):
        active = {}
        for z in range(before.shape[1] + 1):
            row = {}
            if z < before.shape[1]:
                old, new = before[y,z], after[y,z]
                changed = np.flatnonzero(old != new)
                if len(changed):
                    cuts=np.flatnonzero((np.diff(changed)!=1)|(old[changed[1:]]!=old[changed[:-1]])|(new[changed[1:]]!=new[changed[:-1]]))+1
                    for run in np.split(changed,cuts):
                        a,b=int(run[0]),int(run[-1]);key=(a,b,int(old[a]),int(new[a]))
                        row[key]=active.get(key,z)
            for key,start in active.items():
                if key not in row: rectangles.append((y,start,z-1,*key))
            active=row
    by_key=defaultdict(list)
    for y,z,Z,x,X,old,new in rectangles: by_key[z,Z,x,X,old,new].append(y)
    count=0
    for (z,Z,x,X,old,new),ys in by_key.items():
        for group in np.split(np.array(ys),np.flatnonzero(np.diff(ys)!=1)+1):
            y,Y=int(group[0]),int(group[-1]);volume=(X-x+1)*(Y-y+1)*(Z-z+1)
            # The compact representation must still assert every old cell.
            assert np.all(before[y:Y+1,z:Z+1,x:X+1]==old)
            assert np.all(after[y:Y+1,z:Z+1,x:X+1]==new)
            painter.exact((lo[0]+x,lo[1]+y,lo[2]+z,lo[0]+X,lo[1]+Y,lo[2]+Z),palette[old],palette[new],owner)
            count+=volume
    assert count==int((before!=after).sum())
    return count


def plan():
    OUT.mkdir(parents=True, exist_ok=True)
    assert not list((OUT / STAGE).glob('applied_*')), 'Already applied; inspect the receipt'
    src = np.load(MEASURE / 'MEASURED_SOURCE.npz')
    report = json.loads((MEASURE / 'MEASURED_REPORT.json').read_text())
    assert report['directory_sha256'] == hashlib.sha256((BASE / 'continuous_upright/GROUND_CONTINUOUS_DESIGN.json').read_bytes()).hexdigest()
    names = list(map(str, src['palette']))
    ids = {s: i for i, s in enumerate(names)}
    def code(s):
        if s not in ids:
            ids[s] = len(names); names.append(s)
        return ids[s]
    keys = [tuple(map(int, k)) for k in src['section_keys']]
    before = {k: a.copy() for k, a in zip(keys, src['before'])}
    core = {k: a.copy() for k, a in zip(keys, src['core'])}
    shell = {k: a.copy() for k, a in zip(keys, src['shell'])}
    banks = {k: a.copy() for k, a in zip(keys, src['banks'])}
    deltas = []
    wanted = defaultdict(set)
    for stem in RETIRED:
        receipts = list((BASE / stem).glob('applied_*'))
        assert len(receipts) == 1, (stem, receipts)
        for path in sorted((receipts[0] / 'delta').glob('*.npz')):
            data = np.load(path)
            _, cx, cz = path.stem.split('.'); cx, cz = int(cx), int(cz)
            offsets = data['offsets'].astype(np.int64)
            y = offsets // 256 + int(data['minimum'])
            local_index = (y % 16) * 256 + offsets % 256
            for sy in np.unique(y // 16):
                if (cx, cz, int(sy)) not in before: wanted[cx, cz].add(int(sy))
            mapping = np.array([code(str(s)) for s in data['palette']], np.uint16)
            deltas.append((stem, cx, cz, y // 16, local_index, mapping[data['before']], mapping[data['after']]))
    for cx, cz, sy, pal, values in iter_selected_sections(WORLD, 'projectseele:geofront', wanted):
        before[cx, cz, sy] = np.array([code(s) for s in pal], np.uint16)[values]
    missing = [(cx, cz, sy) for (cx, cz), yy in wanted.items() for sy in yy if (cx, cz, sy) not in before]
    assert not missing, ('Unmeasured old delta sections', missing[:30], len(missing))
    after = {k: a.copy() for k, a in before.items()}
    protected = {k: np.zeros(4096, bool) for k in before}
    gates = json.loads((BASE / 'runtime_directory/gates/ROOT_GATES.json').read_text())['gates']
    for gate in gates:
        positions = [r['position'] for r in gate['supports']]
        phases = json.loads(gzip.decompress((BASE / 'runtime_directory/gates' / gate['collision_steps']['cells_file']).read_bytes()))
        positions.extend(r['position'] for phase in phases for r in phase)
        for p in positions:
            key, j = slot(p)
            if key in protected: protected[key][j] = True
    selected = defaultdict(set)
    for cx, cz, sy in before: selected[cx, cz].add(sy)
    kk = np.array(list(before)); lower = (kk[:, [0, 2, 1]] * 16).min(0); upper = (kk[:, [0, 2, 1]] * 16 + 15).max(0)
    devices = dict(iter_block_entities(WORLD, 'projectseele:geofront', lower, upper, selected_chunks=selected))
    for p in devices:
        key, j = slot(p)
        if key in protected: protected[key][j] = True
    restored = Counter(); later_kept = Counter()
    old_guide_cells = {k: np.zeros(4096, bool) for k in before}
    for stem, cx, cz, ys, jj, original, installed in deltas:
        for sy in np.unique(ys):
            key = cx, cz, int(sy); which = ys == sy; indices = jj[which]
            old, made = original[which], installed[which]
            same = after[key][indices] == made
            # Later gates, support seats, retained laboratories and original
            # sealed faces have independent ownership and are not undone.
            take = same & ~protected[key][indices]
            after[key][indices[take]] = old[take]
            if stem.startswith('fixed_foot_rail_foundations'):
                old_guide_cells[key][indices[take]] = True
            restored[stem] += int(take.sum())
            later_kept[stem] += int((~same | protected[key][indices]).sum())
    air = code('minecraft:air'); panel = code('projectseele:nerv_shaft_panel')
    edge = code('projectseele:nerv_machine_edge'); light = code('projectseele:nerv_strip_light[lit=true]')
    retained_ids = [i for i, s in enumerate(names) if 'glass' in s or s.startswith('minecraft:ladder[')
                    or s in ('minecraft:barrier', 'minecraft:structure_void', 'minecraft:lodestone')]
    material_counts = Counter(); protected_padding = Counter()
    for key in before:
        xyz = xyz_for(key); x, y, z = xyz.T; current = before[key]
        restored_layer = after[key].copy()
        # Existing loading bank/ramp geometry below this section is copied
        # verbatim, including its windows and personnel landings.
        keep = (y <= -584) | np.isin(current, retained_ids) | protected[key]
        # Bank two remains its original straight shaft. Bank one's original
        # upper shaft retains the original 31m opening and access equipment.
        keep |= (x >= -54) & (x <= 110) & (z >= -355) & (z <= -300)
        existing_upper = (x >= -54) & (x <= 110) & (z >= -58) & (z <= -15) & (y >= -473)
        keep |= existing_upper
        keep |= (x >= 89) & (z >= -56) & (z <= -46)
        keep |= (y >= -470) & (x >= -54) & (x <= 110) & (z <= -55) & (z >= -190)
        if key in core:
            # Above-grade sweeps certify headroom; they never author towers
            # or remove streets, trees or original surface receiving aprons.
            active = shell[key] & (y <= 67)
            active &= ~((banks[key] & 1 != 0) & (y >= -473))
            active &= ~((banks[key] & 2 != 0) & (y >= -584))
            ring = active & ~core[key] & ~keep
            after[key][ring] = panel
            ribs = ring & (y % 24 == 0)
            after[key][ribs] = edge
            lamps = ring & (y % 24 == 1) & (x % 12 == 0) & (z % 12 == 0)
            after[key][lamps] = light
            after[key][active & core[key] & ~keep] = air
            for v, n in zip(*np.unique(current[active & core[key] & keep], return_counts=True)):
                protected_padding[names[int(v)]] += int(n)
        after[key][keep] = restored_layer[keep]
        after[key][existing_upper] = current[existing_upper]
        old_upper_guide = existing_upper & old_guide_cells[key]
        after[key][old_upper_guide] = restored_layer[old_upper_guide]
        changed = current != after[key]
        for v, n in zip(*np.unique(current[changed], return_counts=True)):
            material_counts[names[int(v)]] += int(n)
    # Preserve actual survey sources independently from the construction
    # palette. This catches unintended edits to doors, MTR and furnishings.
    allowed = {'minecraft:air', 'minecraft:cave_air', 'minecraft:void_air', 'minecraft:stone',
        'minecraft:deepslate', 'minecraft:deepslate[axis=y]', 'minecraft:deepslate_bricks',
        'minecraft:black_concrete', 'minecraft:polished_basalt[axis=y]', 'minecraft:iron_block',
        'minecraft:dirt', 'minecraft:grass_block[snowy=false]', 'minecraft:sea_lantern'}
    unknown = {s: n for s, n in material_counts.items() if s not in allowed and not s.startswith('projectseele:nerv_')}
    if unknown:
        for key, values in before.items():
            for state in unknown:
                hit = (values == ids[state]) & (values != after[key])
                if hit.any(): print('UNKNOWN', state, xyz_for(key)[hit].tolist(), flush=True)
    assert not unknown, ('Unclassified current construction', unknown)
    for p in devices:
        key, j = slot(p)
        if key in before: assert before[key][j] == after[key][j], ('Device modified', p)
    out_keys = sorted(before)
    np.savez_compressed(OUT / 'CIVIL_CANDIDATE.npz', section_keys=np.array(out_keys, np.int32),
        before=np.array([before[k] for k in out_keys]), after=np.array([after[k] for k in out_keys]), palette=names)
    result = dict(world_written=False, runtime_admitted=False, directory_sha256=report['directory_sha256'],
        assembly_hulls_sha256=report['hulls_sha256'], changed_cells=sum(int((before[k] != after[k]).sum()) for k in before),
        sections=len(before), restored_withdrawn_stages=restored, later_owned_cells_preserved=later_kept,
        protected_devices=len(devices), replaced_materials=material_counts, protected_envelope_padding=protected_padding,
        loading_galleries_and_bank_two_unchanged=True, original_upper_bank_one_unchanged=True,
        engineering_margin_is_not_a_permission_to_remove_original_windows=True)
    (OUT / 'CANDIDATE.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


def apply():
    assert not list((OUT / STAGE).glob('applied_*')), 'Never replay an applied map stage'
    data = np.load(OUT / 'CIVIL_CANDIDATE.npz'); names = list(map(str, data['palette']))
    before, after, keys = data['before'], data['after'], data['section_keys']
    vox.WORLD = WORLD; vox.OUT = OUT; vox.DIM = 'projectseele:geofront'
    painter = vox.Painter(vertical_bounds=(-960, 320)); count = 0
    for i, (cx, cz, sy) in enumerate(keys):
        count += cuboids(painter, (int(cx)*16, int(sy)*16, int(cz)*16), before[i].reshape(16,16,16),
                      after[i].reshape(16,16,16), names, 'R52_continuous_upright_civil_replacement')
    report = json.loads((OUT / 'CANDIDATE.json').read_text('utf8'))
    assert count == report['changed_cells']
    painter.meta.update(root_author=True, upright_only=True, original_ramp_and_bank_two_preserved=True,
                        candidate_sha256=hashlib.sha256((OUT / 'CIVIL_CANDIDATE.npz').read_bytes()).hexdigest(),
                        directory_sha256=report['directory_sha256'], runtime_admitted=False)
    lock = acquire_world_lock()
    try:
        report.update(receipt=painter.apply(STAGE, session_lock=lock), world_written=True)
    finally:
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1); lock.close()
    (OUT / STAGE / 'PLAN.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--apply', action='store_true'); args=ap.parse_args()
    apply() if args.apply else plan()

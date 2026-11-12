"""R63 far view (Distant Horizons) and minimap (Xaero) re-bake, on copies of the formal world only.

The formal world is never opened or written here. Its GeoFront LOD database is still the one built for R62
(batch 378); this tool builds the R63 one on a mirror and hands it to package_r60.py --geofront-lod.

Steps, in order (each is resumable and writes WORK/logs/<step>.json):
  check     read-only: inputs, world lock, junctions, disk, slot status, changed chunks, estimates
  instance  copy the shipped client (no saves) into WORK/client and give it a bake config
  mirror    mirror the stopped formal world to WORK/client/saves/MAP_REVIEW (holds session.lock while copying)
  prepare   on the mirror's GeoFront LOD database: drop rows of changed chunks and of the deleted outer ring,
            add the outer ring that map-edges baked on E:, flag rows whose parent must be rebuilt, write viewpoints
  core      client run (slot, probe jar, PRE_EXISTING_ONLY): DH rebuilds the dropped sections from saved chunks
            and the flagged parents; then coverage gate, an optional fill pass, export WORK/out/geofront_lod.sqlite
  xaero     fresh mirror, final jar without DH and Oculus, -Dprojectseele.xaeroBake=true; WORK/out has the baked map
  report    the package_r60.py command for these outputs

Changed chunks are found by comparing every GeoFront chunk with the world inside the R62 server zip, which is
exactly the world the current LOD database was built from. The map writer does not update chunk timestamps.
Run with a Python whose executable name does not start with "python" while the phone tool is running.
"""
from contextlib import contextmanager
from pathlib import Path
import argparse
import datetime
import json
import math
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORMAL = Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025')
SHIP = Path('F:/eva/artifacts/r53_repair_20261015/client')
R62_SERVER_ZIP = Path('F:/eva/delivery/Project_SEELE_Encore_R62_20261110_Server.zip')
RING_DB = Path('E:/eva-map-edges/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite')
WORK = Path('E:/eva-r63-rebake')
ARGS_TEMPLATE = Path('F:/eva/.claude/map-work/run17.args')
TEMPLATE_GAME_DIR = 'F:/eva/.claude/map-work/client'
PROBE_CLASS = Path('F:/eva/.claude/map-edges-work/f12/probe/MapProbeLocal.class')
JAVAW = Path('E:/Users/liboy/jdks/jdk-17.0.19+10/bin/javaw.exe')
SLOT = Path('F:/eva/.claude/client-slots/slot.py')
SLOT_NAME = 'r63-pack'
COPY = 'MAP_REVIEW'  # MapProbeLocal and the args template open this save
GEO = 'dimensions/projectseele/geofront'
R62_PREFIX = 'SEELE_R53_WORLD/' + GEO + '/region/'
JAR = 'mods/projectseele-0.1.0-all.jar'
# Classes that must be in the jar the bake and the pack use (outer boundary, perf 1-2, Fable 3-5, MTR ride sync).
R63_CLASSES = ('world/OuterBoundaryTerrain', 'world/SbwIdlePause', 'physics/GiantInsideBlocks', 'physics/TerrainPruningBroadphase',
               'client/render/EntityShadowRange', 'client/render/EvaRackReleaseR63', 'client/render/EvaKneeHingeR63',
               'client/render/EvaArmClearanceR63', 'mixin/client/MtrRideSyncR63Mixin')
INSTANCE_SKIP = ('saves', 'logs', 'crash-reports', 'screenshots', 'xaero', 'Distant_Horizons_server_data', 'local-review-updates',
                 'backups', 'backup', 'debug', 'pose-captures', '.codex', 'resourcepacks-off', 'mods-off', 'replay_recordings')
SECTION_REACH = 40        # level-0 sections a viewpoint fills around itself (2,560 blocks; DH radius is 192 chunks)
SECTIONS_PER_MINUTE = 110  # saved-chunk LOD rebuild, 4 DH threads (R62 morning run: about 170 with 6 threads)
CLIENT_START_MIN = 4
DH_BAKE = {'enableDistantGeneration': 'true', 'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'numberOfThreads': '4',
           'threadRunTimeRatio': '"1.0"'}


def log_path(step):
    path = WORK / 'logs' / (step + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save(step, data):
    data = dict(step=step, at=datetime.datetime.now().isoformat(timespec='seconds'), **data)
    log_path(step).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', 'utf8')
    print(json.dumps(data, ensure_ascii=False, indent=1), flush=True)
    return data


def guard(path):
    path = Path(path).resolve()
    if WORK.resolve() not in path.parents and path != WORK.resolve():
        raise SystemExit('Only files under ' + str(WORK) + ' may be written: ' + str(path))
    return path


def free_gb(path):
    anchor = Path(path).anchor or str(path)
    return round(shutil.disk_usage(anchor).free / 2**30, 1)


def tree_bytes(root, skip=()):
    total, count, links = 0, 0, []
    stack = [Path(root)]
    while stack:
        here = stack.pop()
        with os.scandir(here) as entries:
            for e in entries:
                st = e.stat(follow_symlinks=False)
                if e.is_symlink() or getattr(st, 'st_file_attributes', 0) & 0x400:
                    links.append(e.path)
                elif e.is_dir(follow_symlinks=False):
                    if e.name not in skip:
                        stack.append(Path(e.path))
                else:
                    total += st.st_size
                    count += 1
    return total, count, links


def world_lock_free(world):
    import msvcrt
    try:
        with (world / 'session.lock').open('r+b') as handle:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return True
    except OSError:
        return False


@contextmanager
def held_world(world, wait_min=60):
    import msvcrt
    deadline = time.time() + wait_min * 60
    handle = (world / 'session.lock').open('r+b')
    while True:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError:
            if time.time() > deadline:
                handle.close()
                raise SystemExit('Formal world stayed locked for %d minutes' % wait_min)
            time.sleep(20)
    try:
        yield
    finally:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


def slot(*args):
    py = sys.executable
    out = subprocess.run([py, str(SLOT), *args], capture_output=True, text=True, encoding='utf8', errors='replace')
    return out.returncode, (out.stdout or '') + (out.stderr or '')


def exclusive_holder():
    rc, text = slot('status')
    if rc != 0 or 'exclusive:' not in text:
        raise SystemExit('slot.py status failed (rc %d): %s' % (rc, text.strip()[:300]))
    line = next(l for l in text.splitlines() if l.startswith('exclusive:'))
    return None if line.strip() == 'exclusive: none' else line.strip()


def wait_no_exclusive(what):
    while True:
        holder = exclusive_holder()
        if not holder:
            return
        print('waiting before %s: %s' % (what, holder), flush=True)
        time.sleep(60)


# ---- chunks and sections -------------------------------------------------------------------------------

def region_chunks(data):
    """{index: compressed payload} of one region file's bytes."""
    found = {}
    if len(data) < 8192:
        return found
    for i in range(1024):
        loc = struct.unpack('>I', data[i * 4:i * 4 + 4])[0]
        if loc:
            off = (loc >> 8) * 4096
            size = struct.unpack('>I', data[off:off + 4])[0]
            found[i] = data[off + 4:off + 4 + size]
    return found


def saved_chunks(world):
    saved = set()
    for path in (world / GEO / 'region').glob('r.*.*.mca'):
        _, rx, rz, _ = path.name.split('.')
        rx, rz = int(rx), int(rz)
        head = path.open('rb').read(4096)
        if len(head) < 4096:
            continue
        for i in range(1024):
            if struct.unpack('>I', head[i * 4:i * 4 + 4])[0]:
                saved.add((rx * 32 + (i & 31), rz * 32 + (i >> 5)))
    return saved


def chunk_changes(world, server_zip=R62_SERVER_ZIP):
    """Chunks that differ from the R62 world: changed payload, added, removed."""
    changed, added, removed = set(), set(), set()
    with zipfile.ZipFile(server_zip) as z:
        old = {n[len(R62_PREFIX):] for n in z.namelist() if n.startswith(R62_PREFIX) and n.endswith('.mca')}
        new = {p.name for p in (world / GEO / 'region').glob('r.*.*.mca')}
        for name in sorted(old | new):
            _, rx, rz, _ = name.split('.')
            rx, rz = int(rx), int(rz)
            a = region_chunks(z.read(R62_PREFIX + name)) if name in old else {}
            b = region_chunks((world / GEO / 'region' / name).read_bytes()) if name in new else {}
            for i in set(a) | set(b):
                pos = (rx * 32 + (i & 31), rz * 32 + (i >> 5))
                if i not in a:
                    added.add(pos)
                elif i not in b:
                    removed.add(pos)
                elif a[i] != b[i]:
                    changed.add(pos)
    return changed, added, removed


class Grid:
    """Counts of a chunk set inside any square, by a summed-area table."""

    def __init__(self, chunks, span):
        import numpy as np
        self.x0, self.z0, x1, z1 = span
        grid = np.zeros((x1 - self.x0 + 2, z1 - self.z0 + 2), dtype=np.int32)
        for x, z in chunks:
            grid[x - self.x0 + 1, z - self.z0 + 1] = 1
        self.sum = grid.cumsum(0).cumsum(1)
        self.nx, self.nz = grid.shape

    def count(self, x, z, n):
        a = min(max(x - self.x0, 0), self.nx - 1)
        b = min(max(z - self.z0, 0), self.nz - 1)
        c = min(max(x + n - self.x0, 0), self.nx - 1)
        d = min(max(z + n - self.z0, 0), self.nz - 1)
        s = self.sum
        return int(s[c, d] - s[a, d] - s[c, b] + s[a, b])


def span_of(rows, *chunk_sets):
    xs, zs = [], []
    for level, x, z in rows:
        n = 4 << level
        xs += [x * n, x * n + n]
        zs += [z * n, z * n + n]
    for chunks in chunk_sets:
        if chunks:
            xs += [min(c[0] for c in chunks), max(c[0] for c in chunks) + 1]
            zs += [min(c[1] for c in chunks), max(c[1] for c in chunks) + 1]
    return min(xs) - 1, min(zs) - 1, max(xs) + 1, max(zs) + 1


def classify(level, x, z, saved_grid):
    n = 4 << level
    hit = saved_grid.count(x * n, z * n, n)
    return 'core' if hit == n * n else 'ring' if hit == 0 else 'mixed'


def rows_of(db):
    c = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        return {(l, x, z): (n or 0) for l, x, z, n in c.execute('select DetailLevel,PosX,PosZ,length(Data) from FullData')}
    finally:
        c.close()


def snapshot(src, dst):
    """Consistent copy of a live SQLite database, read-only on the source; the copy has no WAL."""
    guard(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    s = sqlite3.connect(Path(src).resolve().as_uri() + '?mode=ro', uri=True, timeout=60)
    d = sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        s.close()
        d.close()
    return dst


def plan_merge(core_rows, ring_rows, saved, changed):
    """Which rows of the copy's database to drop, which ring rows to take, from the classification alone."""
    span = span_of(list(core_rows) + list(ring_rows), saved, changed)
    sg, cg = Grid(saved, span), Grid(changed, span)
    drop, keep_core, take = [], [], []
    why = dict(changed=0, ring=0, mixed=0)
    for key in core_rows:
        level, x, z = key
        kind = classify(level, x, z, sg)
        if kind == 'core' and not (level == 0 and cg.count(x * 4, z * 4, 4)):
            keep_core.append(key)
            continue
        drop.append(key)
        why['changed' if kind == 'core' else kind] += 1
    for key, size in ring_rows.items():
        level, x, z = key
        kind = classify(level, x, z, sg)
        if size <= 64:
            continue
        if kind == 'ring' or (kind == 'mixed' and level == 0 and not cg.count(x * 4, z * 4, 4)):
            take.append(key)
    merged = set(keep_core) | set(take)
    # The pyramid goes as high as either source had it (level 9 in R62): rows under a missing parent rebuild it.
    top = max(l for l, _, _ in list(core_rows) + list(ring_rows))
    flag = [k for k in merged if k[0] < top and (k[0] + 1, k[1] >> 1, k[2] >> 1) not in merged]
    # Every level-0 section holding a saved chunk and no row after the merge: DH rebuilds it from saved chunks.
    rebuild = []
    for x in range(min(c[0] for c in saved) // 4, max(c[0] for c in saved) // 4 + 1):
        for z in range(min(c[1] for c in saved) // 4, max(c[1] for c in saved) // 4 + 1):
            if (0, x, z) not in merged and sg.count(x * 4, z * 4, 4):
                rebuild.append((x, z))
    return dict(drop=drop, take=take, flag=flag, rebuild=rebuild, why=why, top=top, span=span, saved_grid=sg)


def viewpoints(sections, reach=SECTION_REACH, minimum=1):
    left, points = set(sections), []
    while left:
        best = max(left, key=lambda s: sum(1 for t in left if abs(t[0] - s[0]) <= reach and abs(t[1] - s[1]) <= reach))
        cover = {t for t in left if abs(t[0] - best[0]) <= reach and abs(t[1] - best[1]) <= reach}
        if len(cover) < minimum:
            break
        points.append((best[0] * 64 + 32, best[1] * 64 + 32, len(cover)))
        left -= cover
    return points


def probe_script(points, path, total_minutes_cap=None):
    steps = [dict(op='cmd', text=t, wait=5) for t in ('gamerule doDaylightCycle false', 'time set 6000', 'weather clear 1000000',
                                                      'gamerule doMobSpawning false', 'gamemode spectator')]
    plan = []
    for i, (x, z, count) in enumerate(points):
        minutes = min(25, max(6, math.ceil(count / SECTIONS_PER_MINUTE) + 2))
        plan.append(dict(x=x, z=z, sections=count, minutes=minutes))
        # tp gives up after 1200 ticks whatever its wait says; a cmd step waits as long as asked (map-edges, 2026-11-11).
        steps += [dict(op='tp', x=x, y=300, z=z, yaw=0, pitch=0, wait=100, fly=True),
                  dict(op='cmd', text='time set 6000', wait=minutes * 1200), dict(op='shot', name='r63-dh-%d' % i)]
    guard(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(steps), 'utf8')
    done_log = Path(str(path) + '.log')
    if done_log.exists():
        done_log.unlink()
    return plan


# ---- instance and client runs --------------------------------------------------------------------------

def robocopy(src, dst, *extra):
    cmd = ['robocopy', str(src), str(dst), '/XJ', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NP', *extra]
    rc = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if rc.returncode >= 8:
        raise SystemExit('robocopy failed (%d): %s' % (rc.returncode, rc.stdout[-800:]))
    return rc.stdout.strip().splitlines()[-6:]


def set_toml(path, settings):
    text = path.read_text('utf8')
    for key, value in settings.items():
        text, n = re.subn(r'(?m)^(\s*' + re.escape(key) + r'\s*=\s*)[^\r\n]*', lambda m: m[1] + value, text)
        if not n:
            raise SystemExit('No %s in %s' % (key, path))
    guard(path).write_text(text, 'utf8')


def client_args(game, extra_props, out_name):
    text = ARGS_TEMPLATE.read_text('utf8')
    assert TEMPLATE_GAME_DIR in text and '"--quickPlaySingleplayer"' in text
    text = text.replace(TEMPLATE_GAME_DIR, game.as_posix()).replace('"-Xmx8G"', '"-Xmx6G"')
    text = re.sub(r'"-Dprojectseele\.mapProbe=[^"]*"\s*', '', text)
    text = re.sub(r'("--quickPlaySingleplayer"\s+)"[^"]*"', lambda m: m[1] + '"' + COPY + '"', text)
    props = ' '.join('"-D%s=%s"' % kv for kv in extra_props.items())
    text = text.replace('"-Xms512m"', '"-Xms512m" ' + props, 1)
    assert '-Xmx6G' in text and all(k in text for k in extra_props)
    path = guard(WORK / 'logs' / out_name)
    path.write_text(text, 'ascii')
    return path


def run_client(args_file, minutes, purpose):
    """One client under a slot; returns the exit text. Never starts without an 'ok:' from slot.py."""
    wait_no_exclusive('a client')
    rc, text = slot('acquire', SLOT_NAME, str(minutes + 10), purpose)
    if not re.search(r'(?m)^(ok|extended):', text):
        raise SystemExit('No slot (rc %d): %s' % (rc, text.strip()[-400:]))
    try:
        p = subprocess.Popen([str(JAVAW), '@' + str(args_file)], cwd=str(WORK / 'client'))
        try:
            code = p.wait(minutes * 60)
            return 'exit=%d' % code
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(60)
            return 'TIMEOUT'
    finally:
        slot('release', SLOT_NAME)


def hold_mods(game, patterns, held):
    held.mkdir(parents=True, exist_ok=True)
    moved = []
    for pattern in patterns:
        for jar in (game / 'mods').glob(pattern):
            shutil.move(str(jar), str(held / jar.name))
            moved.append(jar.name)
    return moved


def restore_mods(game, held):
    for jar in held.glob('*.jar'):
        shutil.move(str(jar), str(game / 'mods' / jar.name))


def probe_jar(final_jar, out):
    """The final jar plus the local probe class (never committed): same private assets, one extra class."""
    guard(out)
    shutil.copyfile(final_jar, out)
    with zipfile.ZipFile(out, 'a') as z:
        name = 'com/projectseele/client/MapProbeLocal.class'
        if name not in z.namelist():
            z.write(PROBE_CLASS, name)
    return out


def jar_classes(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    return [c for c in R63_CLASSES if 'com/projectseele/' + c + '.class' not in names]


# ---- steps ---------------------------------------------------------------------------------------------

def step_check(a):
    problems, notes = [], []
    for name, path in (('formal world', FORMAL / 'level.dat'), ('shipped client jar', SHIP / JAR), ('R62 server zip', R62_SERVER_ZIP),
                       ('outer ring LOD database', RING_DB), ('args template', ARGS_TEMPLATE), ('probe class', PROBE_CLASS),
                       ('javaw', JAVAW), ('slot tool', SLOT)):
        if not path.exists():
            problems.append('missing ' + name + ': ' + str(path))
    missing = jar_classes(SHIP / JAR) if (SHIP / JAR).exists() else list(R63_CLASSES)
    if missing:
        problems.append('shipped jar lacks R63 classes: ' + ', '.join(missing))
    jar_time = datetime.datetime.fromtimestamp((SHIP / JAR).stat().st_mtime).isoformat(timespec='minutes')
    lock_free = world_lock_free(FORMAL)
    if not lock_free:
        notes.append('formal world is locked now (a writer or a game has it open); mirror waits for it')
    world_bytes, world_files, links = tree_bytes(FORMAL)
    if links:
        problems.append('formal world contains links: ' + ', '.join(links[:5]))
    inst_bytes, _, inst_links = tree_bytes(SHIP, INSTANCE_SKIP)
    holder = exclusive_holder()
    if holder:
        notes.append('slot status: ' + holder)

    t = time.time()
    saved = saved_chunks(FORMAL)
    changed, added, removed = chunk_changes(FORMAL)
    newest = max(p.stat().st_mtime for p in (FORMAL / GEO / 'region').glob('*.mca'))
    formal_db = FORMAL / GEO / 'data/DistantHorizons.sqlite'
    core_rows, ring_rows = rows_of(formal_db), rows_of(RING_DB)
    plan = plan_merge(core_rows, ring_rows, saved, changed | added)
    points = viewpoints(plan['rebuild'])
    sg = plan['saved_grid']
    ring_l0 = {(x, z) for (l, x, z), n in ring_rows.items() if l == 0 and n > 64 and classify(0, x, z, sg) == 'ring'}
    # The map-edges ring: x -6464..7584, z -5408..5920 in level-0 sections, minus what is saved.
    ring_want = {(x, z) for x in range(-6464 // 64, 7584 // 64 + 1) for z in range(-5408 // 64, 5920 // 64 + 1)
                 if classify(0, x, z, sg) == 'ring'}
    core_minutes = sum(min(25, max(6, math.ceil(c / SECTIONS_PER_MINUTE) + 2)) for _, _, c in points) + CLIENT_START_MIN
    estimate = dict(
        mirror_min=8, prepare_min=3, core_client_min=core_minutes, fill_pass_min=25, xaero_min=12, pack_min=5,
        total_hours=round((8 + 3 + core_minutes + 25 + 12 + 5) / 60, 1),
        ring_left_sections=len(ring_want - ring_l0), ring_left_hours_at_63_per_min=round(len(ring_want - ring_l0) / 63 / 60, 1))
    disk = dict(work_drive=str(WORK.drive), work_free_gb=free_gb(WORK.drive + '/'), f_free_gb=free_gb('F:/'), e_free_gb=free_gb('E:/'),
                instance_gb=round(inst_bytes / 2**30, 2), world_gb=round(world_bytes / 2**30, 2),
                work_need_gb=round((inst_bytes + 2 * world_bytes) / 2**30 + 2.0, 1),
                delivery_need_gb=4.5, note='WORK: instance + mirror (+ second mirror state for xaero reuses the same folder) + LOD copies; '
                                           'delivery: two zips about 3.2 GB plus the aged LOD temp copy')
    if disk['work_free_gb'] < disk['work_need_gb'] + 5:
        problems.append('not enough free space for WORK on ' + str(WORK.drive))
    if disk['f_free_gb'] < disk['delivery_need_gb'] + 5:
        problems.append('not enough free space on F: for the zips')
    data = dict(
        problems=problems, notes=notes, formal_world=str(FORMAL), world_lock_free=lock_free, world_files=world_files,
        newest_region=datetime.datetime.fromtimestamp(newest).isoformat(timespec='seconds'),
        shipped_jar=dict(path=str(SHIP / JAR), modified=jar_time, bytes=(SHIP / JAR).stat().st_size, r63_classes_missing=missing),
        chunks=dict(saved=len(saved), changed_since_r62=len(changed), added=len(added), removed=len(removed)),
        lod=dict(formal_rows=len(core_rows), ring_rows=len(ring_rows), drop=len(plan['drop']), drop_by_reason=plan['why'],
                 take_from_ring=len(plan['take']), flag_parent_rebuild=len(plan['flag']), rebuild_level0=len(plan['rebuild']),
                 viewpoints=[dict(x=x, z=z, sections=c) for x, z, c in points],
                 ring_level0_have=len(ring_l0), ring_level0_want=len(ring_want),
                 ring_coverage=round(len(ring_l0 & ring_want) / max(1, len(ring_want)), 3)),
        estimate=estimate, disk=disk, seconds=round(time.time() - t, 1))
    save('check', data)
    if problems:
        raise SystemExit('check found %d problem(s)' % len(problems))


def step_instance(a):
    game = WORK / 'client'
    wait_no_exclusive('copying the client')
    tail = robocopy(SHIP, game, '/E', '/XD', *INSTANCE_SKIP, '/XF', 'session.lock', '*.log')
    missing = jar_classes(game / JAR)
    if missing:
        raise SystemExit('jar in the instance lacks ' + ', '.join(missing))
    set_toml(game / 'config/DistantHorizons.toml', DH_BAKE)
    options = (game / 'options.txt').read_text('utf8')
    options = re.sub(r'(?m)^soundCategory_master:.*$', 'soundCategory_master:0.0', options)
    guard(game / 'options.txt').write_text(options, 'utf8')
    shutil.copyfile(SHIP / JAR, guard(WORK / 'jars/final.jar'))
    probe_jar(SHIP / JAR, WORK / 'jars/probe.jar')
    save('instance', dict(game=str(game), robocopy=tail, dh=DH_BAKE, final_jar_bytes=(WORK / 'jars/final.jar').stat().st_size))


def mirror_world():
    game = WORK / 'client'
    target = guard(game / 'saves' / COPY)
    _, _, links = tree_bytes(FORMAL)
    if links:
        raise SystemExit('Formal world contains links, refusing to mirror: ' + ', '.join(links[:5]))
    wait_no_exclusive('mirroring the world')
    with held_world(FORMAL):
        tail = robocopy(FORMAL, target, '/MIR', '/XF', 'session.lock')
        src = {p.relative_to(FORMAL).as_posix(): p.stat().st_size for p in (FORMAL / GEO / 'region').glob('*.mca')}
        dst = {p.relative_to(target).as_posix(): p.stat().st_size for p in (target / GEO / 'region').glob('*.mca')}
        newest = max(p.stat().st_mtime for p in (FORMAL / GEO / 'region').glob('*.mca'))
    if src != dst:
        raise SystemExit('Mirror differs from the formal world in the GeoFront regions')
    return dict(target=str(target), robocopy=tail, regions=len(src),
                formal_newest_region=datetime.datetime.fromtimestamp(newest).isoformat(timespec='seconds'))


def step_mirror(a):
    save('mirror', mirror_world())


def step_prepare(a):
    world = Path(a.world) if a.world else WORK / 'client/saves' / COPY
    db = guard(Path(a.db) if a.db else world / GEO / 'data/DistantHorizons.sqlite')
    for suffix in ('-wal', '-shm'):
        if Path(str(db) + suffix).exists() and Path(str(db) + suffix).stat().st_size:
            raise SystemExit('Database has an unmerged ' + suffix + ': ' + str(db))
    ring = snapshot(Path(a.ring_db or RING_DB), WORK / 'lod/ring_snapshot.sqlite')
    t = time.time()
    saved = saved_chunks(world)
    changed, added, removed = chunk_changes(world)
    plan = plan_merge(rows_of(db), rows_of(ring), saved, changed | added)
    c = sqlite3.connect(db)
    try:
        c.execute('attach database ? as ring', (str(ring),))
        cols = [r[1] for r in c.execute('pragma table_info(FullData)')]
        c.execute('create temp table pick(DetailLevel int, PosX int, PosZ int, primary key (DetailLevel, PosX, PosZ))')
        c.executemany('insert into pick values (?,?,?)', plan['drop'])
        c.execute('delete from FullData where (DetailLevel, PosX, PosZ) in (select DetailLevel, PosX, PosZ from pick)')
        c.execute('delete from pick')
        c.executemany('insert into pick values (?,?,?)', plan['take'])
        c.execute('insert or replace into FullData (%s) select %s from ring.FullData r where (r.DetailLevel, r.PosX, r.PosZ) in '
                  '(select DetailLevel, PosX, PosZ from pick)' % (','.join(cols), ','.join('r.' + x for x in cols)))
        c.execute('delete from pick')
        c.executemany('insert into pick values (?,?,?)', plan['flag'])
        c.execute('update FullData set ApplyToParent = 1 where (DetailLevel, PosX, PosZ) in (select DetailLevel, PosX, PosZ from pick)')
        # Chunk hashes let DH skip chunks it thinks it has seen: forget the changed ones, take the ring's own.
        c.execute('create temp table ch(x int, z int, primary key (x, z))')
        c.executemany('insert or ignore into ch values (?,?)', list(changed | added | removed))
        c.execute('delete from ChunkHash where (ChunkPosX, ChunkPosZ) in (select x, z from ch)')
        hcols = [r[1] for r in c.execute('pragma table_info(ChunkHash)')]
        sg = plan['saved_grid']
        ring_hash = [(x, z) for x, z in c.execute('select ChunkPosX, ChunkPosZ from ring.ChunkHash') if not sg.count(x, z, 1)]
        c.execute('delete from ch')
        c.executemany('insert or ignore into ch values (?,?)', ring_hash)
        c.execute('insert or replace into ChunkHash (%s) select %s from ring.ChunkHash r where (r.ChunkPosX, r.ChunkPosZ) in (select x, z from ch)'
                  % (','.join(hcols), ','.join('r.' + x for x in hcols)))
        c.commit()
        c.execute('detach database ring')
        c.execute('vacuum')
        levels = c.execute('select DetailLevel, count(*), sum(ApplyToParent) from FullData group by DetailLevel').fetchall()
        check = c.execute('pragma integrity_check').fetchone()[0]
        rows = c.execute('select count(*) from FullData').fetchone()[0]
    finally:
        c.close()
    if check != 'ok':
        raise SystemExit('Prepared database failed integrity_check: ' + check)
    points = viewpoints(plan['rebuild'])
    plan_steps = probe_script(points, WORK / 'scripts/r63-dh-core.json')
    json.dump(plan['rebuild'], guard(WORK / 'lod/rebuild_sections.json').open('w'))
    save('prepare', dict(database=str(db), ring_snapshot=str(ring), rows=rows, levels=levels, integrity=check,
                         chunks=dict(saved=len(saved), changed=len(changed), added=len(added), removed=len(removed)),
                         dropped=len(plan['drop']), dropped_by_reason=plan['why'], taken_from_ring=len(plan['take']),
                         flagged_for_parent_rebuild=len(plan['flag']), level0_to_rebuild=len(plan['rebuild']),
                         viewpoints=plan_steps, client_minutes=sum(p['minutes'] for p in plan_steps) + CLIENT_START_MIN,
                         seconds=round(time.time() - t, 1)))


def coverage(world, db):
    saved = saved_chunks(world)
    rows = rows_of(db)
    span = span_of(list(rows), saved)
    sg = Grid(saved, span)
    have = {(x, z) for (l, x, z), n in rows.items() if l == 0 and n > 64}
    want = set()
    for x in range(min(c[0] for c in saved) // 4, max(c[0] for c in saved) // 4 + 1):
        for z in range(min(c[1] for c in saved) // 4, max(c[1] for c in saved) // 4 + 1):
            if sg.count(x * 4, z * 4, 4) == 16:
                want.add((x, z))
    c = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        pending = c.execute('select count(*) from FullData where ApplyToParent = 1').fetchone()[0]
        check = c.execute('pragma quick_check').fetchone()[0]
    finally:
        c.close()
    return dict(core_level0=len(want), core_missing=sorted(want - have), pending_parent_updates=pending, quick_check=check,
                rows=len(rows))


def step_core(a):
    game = WORK / 'client'
    world = game / 'saves' / COPY
    db = world / GEO / 'data/DistantHorizons.sqlite'
    script = WORK / 'scripts/r63-dh-core.json'
    if not script.exists():
        raise SystemExit('Run prepare first')
    shutil.copyfile(WORK / 'jars/probe.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['oculus-*.jar'], held)
    try:
        prep = json.loads(log_path('prepare').read_text('utf8'))
        minutes = a.minutes or prep['client_minutes'] + 10
        args = client_args(game, {'projectseele.mapProbe': script.as_posix()}, 'core.args')
        result = run_client(args, minutes, 'R63 DH core rebake')
        done = Path(str(script) + '.log').exists() and Path(str(script) + '.log').read_text('utf8', 'replace').rstrip().endswith('done')
        cover = coverage(world, db)
        fill = None
        if cover['core_missing'] and len(cover['core_missing']) > a.fill_threshold:
            points = viewpoints(cover['core_missing'], minimum=20)[:8]
            plan = probe_script(points, WORK / 'scripts/r63-dh-fill.json')
            args = client_args(game, {'projectseele.mapProbe': (WORK / 'scripts/r63-dh-fill.json').as_posix()}, 'fill.args')
            fill = dict(points=plan, result=run_client(args, sum(p['minutes'] for p in plan) + CLIENT_START_MIN + 10, 'R63 DH fill'))
            cover = coverage(world, db)
    finally:
        restore_mods(game, held)
        shutil.copyfile(WORK / 'jars/final.jar', game / JAR)
    out = snapshot(db, WORK / 'out/geofront_lod.sqlite')
    gate = dict(script_done=done, client=result, quick_check=cover['quick_check'], core_missing=len(cover['core_missing']),
                pending_parent_updates=cover['pending_parent_updates'])
    ok = done and cover['quick_check'] == 'ok' and len(cover['core_missing']) <= a.fill_threshold
    save('core', dict(ok=ok, gate=gate, held_mods=moved, fill=fill, output=str(out), output_bytes=out.stat().st_size,
                      core_level0=cover['core_level0'], missing_sample=cover['core_missing'][:20]))
    if not ok:
        raise SystemExit('Core rebake did not pass its gate')


def step_xaero(a):
    game = WORK / 'client'
    info = mirror_world()
    baked = game / 'xaero/world-map' / COPY.replace('_', '^us^') / 'projectseele$geofront'
    if baked.exists():
        shutil.move(str(baked), str(guard(baked.with_name('projectseele$geofront.before-' + time.strftime('%H%M%S')))))
    shutil.copyfile(WORK / 'jars/final.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['DistantHorizons-*.jar', 'oculus-*.jar'], held)
    try:
        args = client_args(game, {'projectseele.xaeroBake': 'true'}, 'xaero.args')
        result = run_client(args, 25, 'R63 Xaero minimap bake')
    finally:
        restore_mods(game, held)
    logtext = (game / 'logs/latest.log').read_text('utf8', 'replace')
    finished = 'Xaero map bake finished' in logtext
    zips = sorted(baked.rglob('*.zip')) if baked.exists() else []
    out = WORK / 'out/xaero/projectseele$geofront'
    if finished and zips:
        if out.exists():
            shutil.rmtree(guard(out))
        shutil.copytree(baked, guard(out))
    save('xaero', dict(ok=finished and bool(zips), client=result, finished=finished, region_zips=len(zips), held_mods=moved,
                       mirror=info, output=str(out)))
    if not (finished and zips):
        raise SystemExit('Minimap bake did not finish')


def step_report(a):
    core = json.loads(log_path('core').read_text('utf8'))
    xaero = json.loads(log_path('xaero').read_text('utf8'))
    cmd = ['<frpy>', 'tools/package_r60.py', '--date', time.strftime('%Y%m%d'), '--map-note', '"<一行地图状态>"',
           '--server-address', '<服务器地址>', '--xaero-map', '"%s"' % xaero['output'], '--geofront-lod', '"%s"' % core['output']]
    save('report', dict(check_first=' '.join(cmd + ['--check']), then_pack=' '.join(cmd + ['--pack'])))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('step', choices=['check', 'instance', 'mirror', 'prepare', 'core', 'xaero', 'report'])
    p.add_argument('--world', help='prepare: world whose saved chunks count (default: the mirror)')
    p.add_argument('--db', help='prepare: database to change in place (default: the mirror\'s GeoFront database); must be under WORK')
    p.add_argument('--ring-db', help='prepare: outer ring database (default: the map-edges copy on E:)')
    p.add_argument('--minutes', type=int, help='core: client time limit (default: the plan plus 10)')
    p.add_argument('--fill-threshold', type=int, default=50, help='core: missing core sections tolerated without a fill pass')
    p.add_argument('--work', help='work folder (default E:/eva-r63-rebake)')
    a = p.parse_args()
    if a.work:
        globals()['WORK'] = Path(a.work)
    globals()['step_' + a.step](a)


if __name__ == '__main__':
    main()

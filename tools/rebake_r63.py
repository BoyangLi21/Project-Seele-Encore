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
from contextlib import contextmanager, nullcontext
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
# Probe classes (MapProbeLocal and inner classes) come from the jar map-edges bakes the outer ring with.
PROBE_JAR = Path('E:/eva-map-edges/client/mods/projectseele-0.1.0-all.jar')
# Public build of main (b5ef09c1 or later) for the DH bake client; the pack still ships the private jar.
PUBLIC_JAR = Path('F:/eva/.claude/worktrees/motion/build/libs/projectseele-0.1.0-all.jar')
JAVAW_FALLBACK = Path('E:/Users/liboy/jdks/jdk-17.0.19+10/bin/javaw.exe')


def find_javaw():
    """javaw.exe of JAVA_HOME when it is set and has one, otherwise the JDK 17 this machine's bakes have used."""
    home = os.environ.get('JAVA_HOME')
    if home and (Path(home) / 'bin/javaw.exe').is_file():
        return Path(home) / 'bin/javaw.exe'
    return JAVAW_FALLBACK


JAVAW = find_javaw()
SLOT = Path('F:/eva/.claude/client-slots/slot.py')
SLOT_NAME = 'r63-pack'
COPY = 'MAP_REVIEW'  # MapProbeLocal and the args template open this save
XAERO_COPY = 'R63_XAERO'  # the minimap bake's own mirror (Xaero names its folder R63^us^XAERO)
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
SECTIONS_PER_MINUTE = 80  # saved-chunk rebuild per hover minute: about 50 in the 6 GB trial (OOM), about 170 in R62 (8 GB, 6 threads)
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
    line = next(l for l in text.splitlines() if l.startswith('exclusive:')).strip()
    # Our own window does not block us.
    return None if line == 'exclusive: none' or line.startswith('exclusive: %s ' % SLOT_NAME) else line


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


def open_ro(db, live=False):
    """A read-only connection. Even mode=ro leaves -wal and -shm files beside a WAL database, so a database
    nobody is writing (the formal world's, our own outputs) is opened immutable, which creates nothing.
    Only the map-edges copy, which its client may be writing, is opened live."""
    return sqlite3.connect(Path(db).resolve().as_uri() + ('?mode=ro' if live else '?mode=ro&immutable=1'), uri=True, timeout=60)


def rows_of(db, live=False):
    c = open_ro(db, live)
    try:
        return {(l, x, z): (n or 0) for l, x, z, n in c.execute('select DetailLevel,PosX,PosZ,length(Data) from FullData')}
    finally:
        c.close()


def snapshot(src, dst, live=False):
    """Consistent copy of a SQLite database, read-only on the source; the copy has no WAL."""
    guard(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    s = open_ro(src, live)
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


def client_args(game, extra_props, out_name, heap='6G', world=COPY):
    text = ARGS_TEMPLATE.read_text('utf8')
    assert TEMPLATE_GAME_DIR in text and '"--quickPlaySingleplayer"' in text and '"-Xmx8G"' in text
    text = text.replace(TEMPLATE_GAME_DIR, game.as_posix()).replace('"-Xmx8G"', '"-Xmx%s"' % heap)
    text = re.sub(r'"-Dprojectseele\.mapProbe=[^"]*"\s*', '', text)
    text = re.sub(r'("--quickPlaySingleplayer"\s+)"[^"]*"', lambda m: m[1] + '"' + world + '"', text)
    props = ' '.join('"-D%s=%s"' % kv for kv in extra_props.items())
    text = text.replace('"-Xms512m"', '"-Xms512m" ' + props, 1)
    assert '-Xmx' + heap in text and all(k in text for k in extra_props)
    path = guard(WORK / 'logs' / out_name)
    path.write_text(text, 'ascii')
    return path


def client_log():
    """What the last client run's log says: a broken mod load still exits with code 0."""
    text = (WORK / 'client/logs/latest.log').read_text('utf8', 'replace')
    bad = [m for m in ('Failed to register automatic subscribers', 'Unhandled game exception', 'broken mod state',
                       'Missing required mod', 'Registry Object not present', 'Hand joint missing', 'missing registry entries',
                       'Encountered an unexpected exception', 'This crash report has been saved') if m.lower() in text.lower()]
    world = 'logged in with entity id' in text or 'Preparing start region' in text
    return dict(seele_initialized='Project SEELE initialized' in text, world_opened=world, failures=bad,
                out_of_memory=text.count('OutOfMemoryError'), ok='Project SEELE initialized' in text and world and not bad)


def run_client(args_file, minutes, purpose, exclusive=False):
    """One client under a slot, or with the whole machine (slot.py exclusive, which waits for running clients
    to end); returns the exit text. Never starts without an 'ok:' from slot.py."""
    while True:
        wait_no_exclusive('a client')
        rc, text = slot('exclusive' if exclusive else 'acquire', SLOT_NAME, str(minutes + 10), purpose)
        if re.search(r'(?m)^(ok|extended):', text):
            break
        if exclusive and re.search(r'(?m)^refused:', text):
            print('exclusive refused, retrying in a minute: ' + text.strip()[-200:], flush=True)
            time.sleep(60)
            continue
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


def probe_classes(source=None):
    """MapProbeLocal and its inner classes from the probe jar map-edges bakes with (never committed)."""
    with zipfile.ZipFile(source or PROBE_JAR) as z:
        found = {n: z.read(n) for n in z.namelist() if n.startswith('com/projectseele/client/MapProbeLocal') and n.endswith('.class')}
    if not {'com/projectseele/client/MapProbeLocal.class', 'com/projectseele/client/MapProbeLocal$ProbeInput.class'} <= set(found):
        raise SystemExit('Probe classes incomplete in ' + str(source or PROBE_JAR) + ': ' + ', '.join(sorted(found)))
    return found


def probe_jar(final_jar, out):
    """The final jar plus the local probe classes: same private assets, the probe and its inner classes added."""
    guard(out)
    classes = probe_classes()
    shutil.copyfile(final_jar, out)
    with zipfile.ZipFile(out, 'a') as z:
        present = set(z.namelist())
        for name, data in classes.items():
            if name not in present:
                z.writestr(name, data)
    return out


def jar_classes(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    return [c for c in R63_CLASSES if 'com/projectseele/' + c + '.class' not in names]


# ---- steps ---------------------------------------------------------------------------------------------

def step_check(a):
    problems, notes = [], []
    for name, path in (('formal world', FORMAL / 'level.dat'), ('shipped client jar', SHIP / JAR), ('R62 server zip', R62_SERVER_ZIP),
                       ('outer ring LOD database', RING_DB), ('args template', ARGS_TEMPLATE), ('probe jar', PROBE_JAR),
                       ('javaw', JAVAW), ('slot tool', SLOT)):
        if not path.exists():
            problems.append('missing ' + name + ': ' + str(path))
    missing = jar_classes(SHIP / JAR) if (SHIP / JAR).exists() else list(R63_CLASSES)
    if missing:
        problems.append('shipped jar lacks R63 classes: ' + ', '.join(missing))
    jar_time = datetime.datetime.fromtimestamp((SHIP / JAR).stat().st_mtime).isoformat(timespec='minutes')
    java = JAVAW.with_name('java.exe')
    version = subprocess.run([str(java), '-version'], capture_output=True, text=True, errors='replace').stderr.splitlines()[:1] \
        if java.is_file() else []
    if not version or '"17.' not in version[0]:
        problems.append('Forge 1.20.1 needs Java 17; %s reports %s' % (java, version))
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
    core_rows, ring_rows = rows_of(formal_db), rows_of(RING_DB, live=True)
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
        javaw=dict(path=str(JAVAW), from_java_home=JAVAW != JAVAW_FALLBACK, version=version[:1]),
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
    guard(WORK / 'jars').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SHIP / JAR, guard(WORK / 'jars/final.jar'))
    # The private jar's 821 MB Unit-00 prototype mesh filled most of a heap on its own (map-edges' server OOM,
    # 2026-11-13 06:26), but the public build cannot open the world: the server reads the three units' private
    # meshes, hands and GEO before it loads (dry start 07:17). So the bake jar is the shipped jar with only the
    # heavy client-render meshes swapped for the public build's placeholders.
    bake = slim_jar(SHIP / JAR, Path(a.bake_jar), WORK / 'jars/bake.jar')
    missing = jar_classes(bake)
    if missing:
        raise SystemExit('Bake jar lacks R63 classes: ' + ', '.join(missing))
    probe_jar(bake, WORK / 'jars/probe.jar')
    save('instance', dict(game=str(game), robocopy=tail, dh=DH_BAKE, final_jar_bytes=(WORK / 'jars/final.jar').stat().st_size,
                          bake_jar=dict(path=str(bake), bytes=bake.stat().st_size, sha256=sha256_file(bake),
                                        modified=datetime.datetime.fromtimestamp(bake.stat().st_mtime).isoformat(timespec='seconds')),
                          probe_jar_bytes=(WORK / 'jars/probe.jar').stat().st_size))


HEAVY_RENDER_MESHES = ('assets/projectseele/mesh/eva_prototype.mesh.json',)  # only EvaUnit01Renderer reads it


def slim_jar(private, public, out):
    """private with each HEAVY_RENDER_MESHES entry taken from public; every class and other asset unchanged."""
    guard(out)
    partial = out.with_suffix('.partial')
    with zipfile.ZipFile(public) as pub, zipfile.ZipFile(private) as src, \
            zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as dst:
        for name in HEAVY_RENDER_MESHES:
            if name not in pub.namelist():
                raise SystemExit('Public build has no placeholder for ' + name)
        for info in src.infolist():
            source = pub if info.filename in HEAVY_RENDER_MESHES else src
            entry = source.getinfo(info.filename)
            target = zipfile.ZipInfo(entry.filename, entry.date_time)
            target.compress_type = entry.compress_type  # ZipInfo defaults to stored
            with source.open(entry) as reader, dst.open(target, 'w', force_zip64=True) as writer:
                shutil.copyfileobj(reader, writer, 1 << 20)
    with zipfile.ZipFile(partial) as check, zipfile.ZipFile(private) as src:
        same = [n for n in src.namelist() if n not in HEAVY_RENDER_MESHES and check.getinfo(n).CRC != src.getinfo(n).CRC]
        if same or check.namelist() != src.namelist():
            raise SystemExit('Slim bake jar differs from the shipped jar beyond the swapped meshes: %s' % same[:5])
    os.replace(partial, out)
    return out


def sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def step_drystart(a):
    """Open the mirror with the bake jar for a few minutes, DH on, and read the log. Changes the mirror's LOD
    database, so run mirror and prepare again before core."""
    game = WORK / 'client'
    script = WORK / 'scripts/r63-dry.json'
    minutes = a.minutes or 3
    steps = [dict(op='cmd', text='gamerule doDaylightCycle false', wait=5), dict(op='cmd', text='time set 6000', wait=minutes * 1200)]
    guard(script).parent.mkdir(parents=True, exist_ok=True)
    script.write_text(json.dumps(steps), 'utf8')
    Path(str(script) + '.log').unlink(missing_ok=True)
    started = time.time()
    shutil.copyfile(WORK / 'jars/probe.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['oculus-*.jar'], held)
    try:
        set_toml(game / 'config/DistantHorizons.toml', {'numberOfThreads': str(a.dh_threads)})
        args = client_args(game, {'projectseele.mapProbe': script.as_posix()}, 'dry.args', a.heap)
        result = run_client(args, minutes + 10, 'R63 bake jar dry start', a.exclusive)
    finally:
        restore_mods(game, held)
        shutil.copyfile(WORK / 'jars/final.jar', game / JAR)
    log = client_log()
    done = Path(str(script) + '.log').exists() and Path(str(script) + '.log').read_text('utf8', 'replace').rstrip().endswith('done')
    crashes = [p.name for p in (game / 'crash-reports').glob('*.txt') if p.stat().st_mtime > started] if (game / 'crash-reports').exists() else []
    ok = log['ok'] and done and not crashes
    save('drystart', dict(ok=ok, client=result, client_log=log, script_done=done, crash_reports=crashes, heap=a.heap,
                          dh_threads=a.dh_threads, held_mods=moved, note='the mirror LOD database was used: run mirror and prepare before core'))
    if not ok:
        raise SystemExit('Dry start failed')


BATCH_LOG = ROOT / 'docs/HAKONE_EXECUTION_ORDER_20261105.zh.md'
MIRROR_SKIP = ('session.lock',)


def latest_batch():
    """Highest batch number in the map session's batch table (rows like '| 455 | ...')."""
    numbers = [int(m) for m in re.findall(r'(?m)^\|\s*(\d{3,4})\s*\|', BATCH_LOG.read_text('utf8'))]
    return max(numbers) if numbers else None


def manifest(root):
    """sha256 of every file the mirror copies, and one digest over all of them (sorted paths)."""
    import hashlib
    files = {}
    for path in sorted(Path(root).rglob('*')):
        if path.is_file() and path.name not in MIRROR_SKIP and not path.name.endswith('.sqlite-shm'):
            digest = hashlib.sha256()
            with path.open('rb') as handle:
                for block in iter(lambda: handle.read(1 << 20), b''):
                    digest.update(block)
            files[path.relative_to(root).as_posix()] = digest.hexdigest()
    whole = hashlib.sha256(''.join(f'{k}\t{v}\n' for k, v in files.items()).encode()).hexdigest()
    region = hashlib.sha256(''.join(f'{k}\t{v}\n' for k, v in files.items() if k.startswith(GEO + '/region/')).encode()).hexdigest()
    return files, whole, region


def region_fingerprint(world):
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns] for p in sorted((world / GEO / 'region').glob('*.mca'))}


def mirror_world(locked=True, name=COPY):
    game = WORK / 'client'
    target = guard(game / 'saves' / name)
    _, _, links = tree_bytes(FORMAL)
    if links:
        raise SystemExit('Formal world contains links, refusing to mirror: ' + ', '.join(links[:5]))
    wait_no_exclusive('mirroring the world')
    with held_world(FORMAL) if locked else nullcontext():
        t = time.time()
        wal = FORMAL / GEO / 'data/DistantHorizons.sqlite-wal'
        if wal.exists() and wal.stat().st_size:
            raise SystemExit('The formal GeoFront LOD database has an unmerged WAL; someone has the world open')
        tail = robocopy(FORMAL, target, '/MIR', '/XF', *MIRROR_SKIP, '*.sqlite-shm')
        src, whole, region = manifest(FORMAL) if locked else ({}, None, None)
        fingerprint = region_fingerprint(FORMAL)
        newest = max(p.stat().st_mtime for p in (FORMAL / GEO / 'region').glob('*.mca'))
    if locked:
        dst, mirror_whole, _ = manifest(target)
        if dst != src:
            differ = sorted(k for k in src.keys() | dst.keys() if src.get(k) != dst.get(k))
            raise SystemExit('Mirror differs from the formal world in %d files, e.g. %s' % (len(differ), differ[:5]))
        json.dump(dict(files=src), guard(WORK / 'logs' / ('manifest-%s.json' % name)).open('w'), indent=0)
    return dict(target=str(target), robocopy=tail, files=len(src), sha256_all_files=whole, sha256_geofront_regions=region,
                region_fingerprint=fingerprint, recorded_batch=latest_batch(), seconds_locked=round(time.time() - t),
                formal_newest_region=datetime.datetime.fromtimestamp(newest).isoformat(timespec='seconds'))


def step_mirror(a):
    # --no-lock is for trial runs only: a writer may change the world while it is copied.
    data = mirror_world(not a.no_lock)
    if a.batch and data['recorded_batch'] != a.batch:
        raise SystemExit('Batch table says %s, expected %s' % (data['recorded_batch'], a.batch))
    fingerprint = data.pop('region_fingerprint')
    save('mirror', dict(locked=not a.no_lock, **data))
    json.dump(fingerprint, guard(WORK / 'logs/mirror-fingerprint.json').open('w'))


def world_unchanged_since_mirror():
    path = WORK / 'logs/mirror-fingerprint.json'
    return path.exists() and json.load(path.open()) == region_fingerprint(FORMAL)


def step_prepare(a):
    world = Path(a.world) if a.world else WORK / 'client/saves' / COPY
    db = guard(Path(a.db) if a.db else world / GEO / 'data/DistantHorizons.sqlite')
    wal = Path(str(db) + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise SystemExit('Database has an unmerged WAL: ' + str(db))
    Path(str(db) + '-shm').unlink(missing_ok=True)  # only an index; the copy is ours
    ring = snapshot(Path(a.ring_db or RING_DB), WORK / 'lod/ring_snapshot.sqlite', live=True)
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
    points = viewpoints(plan['rebuild'])[:a.points or None]
    plan_steps = probe_script(points, WORK / 'scripts/r63-dh-core.json')
    json.dump(plan['rebuild'], guard(WORK / 'lod/rebuild_sections.json').open('w'))
    # The bake client saves outer chunks around its viewpoints; coverage counts only what the world had now.
    json.dump(sorted(fully_saved(saved)), guard(WORK / 'lod/core_sections.json').open('w'))
    mirror = json.loads(log_path('mirror').read_text('utf8')) if log_path('mirror').exists() and not a.db else {}
    save('prepare', dict(database=str(db), ring_snapshot=str(ring), rows=rows, levels=levels, integrity=check,
                         mirror=dict((k, mirror.get(k)) for k in ('at', 'locked', 'recorded_batch', 'sha256_all_files', 'sha256_geofront_regions')),
                         world_unchanged_since_mirror=world_unchanged_since_mirror(),
                         chunks=dict(saved=len(saved), changed=len(changed), added=len(added), removed=len(removed)),
                         dropped=len(plan['drop']), dropped_by_reason=plan['why'], taken_from_ring=len(plan['take']),
                         flagged_for_parent_rebuild=len(plan['flag']), level0_to_rebuild=len(plan['rebuild']),
                         viewpoints=plan_steps, client_minutes=sum(p['minutes'] for p in plan_steps) + CLIENT_START_MIN,
                         seconds=round(time.time() - t, 1)))


def fully_saved(saved):
    """Level-0 sections whose 16 chunks are all saved."""
    count = {}
    for x, z in saved:
        count[(x >> 2, z >> 2)] = count.get((x >> 2, z >> 2), 0) + 1
    return {s for s, n in count.items() if n == 16}


def coverage(world, db):
    rows = rows_of(db, live=True)
    have = {(x, z) for (l, x, z), n in rows.items() if l == 0 and n > 64}
    recorded = WORK / 'lod/core_sections.json'
    want = {tuple(s) for s in json.load(recorded.open())} if recorded.exists() else fully_saved(saved_chunks(world))
    c = open_ro(db, live=True)
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
    if not world_unchanged_since_mirror():
        raise SystemExit('The formal world changed since the mirror (or was never mirrored): run mirror and prepare again')
    shutil.copyfile(WORK / 'jars/probe.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['oculus-*.jar'], held)
    try:
        prep = json.loads(log_path('prepare').read_text('utf8'))
        minutes = a.minutes or prep['client_minutes'] + 10
        # 4 threads in a 6 GB heap lost the first, nearest tasks to OutOfMemoryError in the 2026-11-13 trial.
        set_toml(game / 'config/DistantHorizons.toml', {'numberOfThreads': str(a.dh_threads)})
        args = client_args(game, {'projectseele.mapProbe': script.as_posix()}, 'core.args', a.heap)
        result = run_client(args, minutes, 'R63 DH core rebake', a.exclusive)
        log = client_log()
        done = Path(str(script) + '.log').exists() and Path(str(script) + '.log').read_text('utf8', 'replace').rstrip().endswith('done')
        cover = coverage(world, db)
        fill = None
        if log['ok'] and cover['core_missing'] and len(cover['core_missing']) > a.fill_threshold:
            points = viewpoints(cover['core_missing'], minimum=20)[:8]
            plan = probe_script(points, WORK / 'scripts/r63-dh-fill.json')
            args = client_args(game, {'projectseele.mapProbe': (WORK / 'scripts/r63-dh-fill.json').as_posix()}, 'fill.args', a.heap)
            fill = dict(points=plan, result=run_client(args, sum(p['minutes'] for p in plan) + CLIENT_START_MIN + 10, 'R63 DH fill', a.exclusive))
            cover = coverage(world, db)
    finally:
        restore_mods(game, held)
        shutil.copyfile(WORK / 'jars/final.jar', game / JAR)
    out = snapshot(db, WORK / 'out/geofront_lod.sqlite', live=True)
    gate = dict(script_done=done, client=result, client_log=log, quick_check=cover['quick_check'], core_missing=len(cover['core_missing']),
                pending_parent_updates=cover['pending_parent_updates'])
    ok = log['ok'] and done and cover['quick_check'] == 'ok' and len(cover['core_missing']) <= a.fill_threshold
    save('core', dict(ok=ok, gate=gate, held_mods=moved, fill=fill, output=str(out), output_bytes=out.stat().st_size,
                      core_level0=cover['core_level0'], missing_sample=cover['core_missing'][:20]))
    if not ok:
        raise SystemExit('Core rebake did not pass its gate')


def step_xaero(a):
    # Its own mirror, so a minimap redo never wipes the prepared LOD database in MAP_REVIEW.
    game = WORK / 'client'
    info = mirror_world(name=XAERO_COPY)
    info.pop('region_fingerprint')
    baked = game / 'xaero/world-map' / XAERO_COPY.replace('_', '^us^') / 'projectseele$geofront'
    if baked.exists():
        shutil.move(str(baked), str(guard(baked.with_name('projectseele$geofront.before-' + time.strftime('%H%M%S')))))
    shutil.copyfile(WORK / 'jars/final.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['DistantHorizons-*.jar', 'oculus-*.jar'], held)
    try:
        args = client_args(game, {'projectseele.xaeroBake': 'true'}, 'xaero.args', world=XAERO_COPY)
        result = run_client(args, 25, 'R63 Xaero minimap bake', a.exclusive)
    finally:
        restore_mods(game, held)
    logtext = (game / 'logs/latest.log').read_text('utf8', 'replace')
    finished = 'Xaero map bake finished' in logtext and client_log()['ok']
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
    p.add_argument('step', choices=['check', 'instance', 'mirror', 'prepare', 'drystart', 'core', 'xaero', 'report'])
    p.add_argument('--bake-jar', default=str(PUBLIC_JAR), help='instance: public build of main whose placeholder meshes replace the heavy render meshes in the bake jar')
    p.add_argument('--world', help='prepare: world whose saved chunks count (default: the mirror)')
    p.add_argument('--db', help='prepare: database to change in place (default: the mirror\'s GeoFront database); must be under WORK')
    p.add_argument('--ring-db', help='prepare: outer ring database (default: the map-edges copy on E:)')
    p.add_argument('--minutes', type=int, help='core: client time limit (default: the plan plus 10)')
    p.add_argument('--fill-threshold', type=int, default=50, help='core: missing core sections tolerated without a fill pass')
    p.add_argument('--points', type=int, help='prepare: keep only the first N viewpoints (trial runs)')
    p.add_argument('--exclusive', action='store_true', help='core, xaero: run with the whole machine (slot.py exclusive); core then defaults to 8G and 4 DH threads')
    p.add_argument('--heap', help='core: client heap (default 8G with --exclusive, else 6G)')
    p.add_argument('--dh-threads', type=int, help='core: DH worker threads (default 4 with --exclusive, else 3: 4 at 6G ran out of heap in the trial)')
    p.add_argument('--no-lock', action='store_true', help='mirror: copy without holding session.lock (trial runs only, never for packing)')
    p.add_argument('--batch', type=int, help='mirror: the batch the formal world should be at; refuse if the batch table says otherwise')
    p.add_argument('--work', help='work folder (default E:/eva-r63-rebake)')
    a = p.parse_args()
    # Review session, 2026-11-13: with the machine to ourselves R62's 8 GB / 4 threads; shared, 6 GB / 3 threads.
    a.heap = a.heap or ('8G' if a.exclusive else '6G')
    a.dh_threads = a.dh_threads or (4 if a.exclusive else 3)
    if a.work:
        globals()['WORK'] = Path(a.work)
    globals()['step_' + a.step](a)


if __name__ == '__main__':
    main()

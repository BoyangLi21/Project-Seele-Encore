"""R63 far view (Distant Horizons) and minimap (Xaero) re-bake, on copies of the formal world only.

The formal world is never opened or written here. Its GeoFront LOD database is still the one built for R62
(batch 378); this tool builds the R63 one on a mirror and hands it to package_r60.py --geofront-lod.

Steps, in order (each is resumable and writes WORK/logs/<step>.json):
  check     read-only: inputs, world lock, junctions, disk, slot status, changed chunks, estimates
  instance  copy the shipped client (no saves) into WORK/client and give it a bake config
  mirror    mirror the stopped formal world to WORK/client/saves/MAP_REVIEW (holds session.lock while copying)
  raise     R64: raise Tokyo-3 on the mirror (one short client run, render distance 2, no DH), so the towers are in
            the saved chunks; prepare then finds the city chunks changed and core bakes the far view with the city up
  prepare   on the mirror's GeoFront LOD database: drop rows of changed chunks and of the deleted outer ring,
            add the outer ring that map-edges baked on D:, flag rows whose parent must be rebuilt, write viewpoints;
            --v6 then runs dh_v6_prepare.py on the rebuild list so DH rebuilds those sections from far away too
  core      client run (slot, probe jar, PRE_EXISTING_ONLY): DH rebuilds the dropped sections from saved chunks
            and the flagged parents; then coverage gate, an optional fill pass, export WORK/out/geofront_lod.sqlite
  xaero     fresh mirror, final jar without DH and Oculus, -Dprojectseele.xaeroBake=true; WORK/out has the baked map;
            --city-raised raises the city on that mirror first, --xaero-pregen generates the outer ring first
  report    the package_r60.py command for these outputs

Changed chunks are found by comparing every GeoFront chunk with the world inside the reference server zip
(REFERENCE_SERVER_ZIP), which must be exactly the world the starting LOD database was built from: for R64 the
R63r server zip (batch 455), whose GeoFront database is passed to prepare with --db. The map writer does not update chunk timestamps.
Run with a Python whose executable name does not start with "python" while the phone tool is running.
"""
from contextlib import contextmanager, nullcontext
from pathlib import Path
import argparse
import datetime
import gzip
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
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
FORMAL = Path('F:/eva/artifacts/r53_repair_20261015/client/saves/HOTFIX_20261025')
SHIP = Path('F:/eva/artifacts/r53_repair_20261015/client')
# The world the starting LOD database was built from. R64 starts from R63r's (batch 455, the R63 far view).
REFERENCE_SERVER_ZIP = Path('F:/eva/delivery/Project_SEELE_Encore_R63r_20261115_Server_Fix1.zip')
# The R64 outer ring map-edges baked with the R64 generator on its D: copy (2026-11-17, 39,160 sections, LZ4 rows).
RING_DB = Path('D:/eva-ringbake/client/saves/MAP_REVIEW/dimensions/projectseele/geofront/data/DistantHorizons.sqlite')
WORK = Path('E:/eva-r63-rebake')
ARGS_TEMPLATE = Path('F:/eva/.claude/map-work/run17.args')
TEMPLATE_GAME_DIR = 'F:/eva/.claude/map-work/client'
# Probe classes (MapProbeLocal and inner classes) come from the jar map-edges bakes the outer ring with.
PROBE_JAR = Path('D:/eva-ringbake/client/mods/projectseele-0.1.0-all.jar')
# Tokyo-3's fixed origin in the GeoFront dimension (IntegratedNervMapBuilder.tokyo3Origin) and its R45 lift state file.
CITY_ORIGIN = (30, 80, 220)
CITY_CONTROL = 'data/projectseele_city_rigid_control_r45_8246338109520.dat'
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
# R64: rows the bake writes use LZ4 (perf: LZMA2 keeps 1.1 GB of compressors resident); older rows keep their own mode.
DH_BAKE = {'enableDistantGeneration': 'true', 'distantGeneratorMode': '"PRE_EXISTING_ONLY"', 'numberOfThreads': '4',
           'threadRunTimeRatio': '"1.0"', 'dataCompression': '"LZ4"'}


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


def chunk_changes(world, server_zip=None):
    """Chunks that differ from the reference server zip's world: changed payload, added, removed."""
    changed, added, removed = set(), set(), set()
    with zipfile.ZipFile(server_zip or REFERENCE_SERVER_ZIP) as z:
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


def probe_script(points, path, total_minutes_cap=None, hover=None):
    steps = [dict(op='cmd', text=t, wait=5) for t in ('gamerule doDaylightCycle false', 'time set 6000', 'weather clear 1000000',
                                                      'gamerule doMobSpawning false', 'gamemode spectator')]
    plan = []
    for i, (x, z, count) in enumerate(points):
        minutes = hover or min(25, max(6, math.ceil(count / SECTIONS_PER_MINUTE) + 2))
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


def client_log(game=None):
    """What the last client run's log says: a broken mod load still exits with code 0."""
    text = ((game or WORK / 'client') / 'logs/latest.log').read_text('utf8', 'replace')
    bad = [m for m in ('Failed to register automatic subscribers', 'Unhandled game exception', 'broken mod state',
                       'Missing required mod', 'Registry Object not present', 'Hand joint missing', 'missing registry entries',
                       'Encountered an unexpected exception', 'This crash report has been saved') if m.lower() in text.lower()]
    world = 'logged in with entity id' in text or 'Preparing start region' in text
    return dict(seele_initialized='Project SEELE initialized' in text, world_opened=world, failures=bad,
                out_of_memory=text.count('OutOfMemoryError'), ok='Project SEELE initialized' in text and world and not bad)


def wait_for_segment(p, seconds, commit_floor):
    """Give a constrained Windows host time for Minecraft's normal world and SQLite shutdown."""
    deadline = time.monotonic() + seconds
    low = 0
    while True:
        try:
            return 'exit=%d' % p.wait(max(0, min(12, deadline - time.monotonic())))
        except subprocess.TimeoutExpired:
            if time.monotonic() >= deadline:
                raise
        rc, status = slot('status')
        match = re.search(r'free commit ([\d.]+) GB', status)
        if rc or not match:
            continue
        free = float(match[1])
        low = low + 1 if free <= commit_floor else 0
        if low < 2 and free >= commit_floor - 1.5:
            continue
        close = subprocess.run(['powershell', '-NoProfile', '-Command', '(Get-Process -Id %d).CloseMainWindow()' % p.pid],
                               capture_output=True, text=True, errors='replace')
        if close.returncode == 0 and close.stdout.strip() == 'True':
            print('Closing the current LOD client normally with %.1f GiB host commit available' % free, flush=True)
            return 'saved-for-commit=%.1f,exit=%d' % (free, p.wait(90))


def run_client(args_file, minutes, purpose, exclusive=False, commit_floor=None, game=None):
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
        p = subprocess.Popen([str(JAVAW), '@' + str(args_file)], cwd=str(game or WORK / 'client'))
        try:
            if commit_floor is not None:
                return wait_for_segment(p, minutes * 60, commit_floor)
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


def city_state(world):
    """Depth, Target and Phase of the R45 rigid city lift (Depth 0 = raised, 312 = lowered)."""
    data = gzip.decompress((world / GEO / CITY_CONTROL).read_bytes())
    out = {}
    for key in ('Depth', 'Target'):
        tag = b'\x03' + struct.pack('>H', len(key)) + key.encode()
        i = data.find(tag)
        out[key] = struct.unpack_from('>i', data, i + len(tag))[0] if i >= 0 else None
    tag = b'\x08\x00\x05Phase'
    i = data.find(tag)
    if i >= 0:
        n = struct.unpack_from('>H', data, i + len(tag))[0]
        out['Phase'] = data[i + len(tag) + 2:i + len(tag) + 2 + n].decode('utf8', 'replace')
    return out


def raise_city(name, heap='6G', exclusive=False, game=None, label=None):
    """Raise Tokyo-3 on one of our mirrors with a short client run: /seele city raise needs a player, so the probe
    runs it through execute as @p. Render distance 2 and no DH, so the run saves no extra outer chunks and writes
    no LOD rows; the R45 lift saves the moved chunks itself before it commits."""
    game = game or WORK / 'client'
    label = label or name
    world = game / 'saves' / name
    before = city_state(world)
    if before.get('Depth') == 0 and before.get('Phase') == 'IDLE':
        return dict(skipped='already raised', before=before)
    x, y, z = CITY_ORIGIN
    steps = [dict(op='cmd', text=t, wait=5) for t in ('gamerule doDaylightCycle false', 'time set 6000', 'weather clear 1000000',
                                                      'gamerule doMobSpawning false', 'execute as @p run gamemode creative')]
    steps += [dict(op='cmd', text='execute in projectseele:geofront run tp @p %d %d %d' % (x, y + 60, z), wait=400),
              dict(op='cmd', text='execute as @p at @p run seele city raise', wait=20),
              # A raise took 99-112 s on the R64 copies (2026-11-17); wait well past it, then save.
              dict(op='cmd', text='time set 6000', wait=6000),
              dict(op='cmd', text='save-all flush', wait=400)]
    script = guard(WORK / ('scripts/city-raise-%s.json' % label))
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(json.dumps(steps), 'utf8')
    Path(str(script) + '.log').unlink(missing_ok=True)
    options = game / 'options.txt'
    kept = options.read_text('utf8')
    held = WORK / 'mods-held-raise'
    shutil.copyfile(WORK / 'jars/probe.jar', guard(game / JAR))
    moved = hold_mods(game, ['DistantHorizons-*.jar', 'oculus-*.jar'], held)
    try:
        guard(options).write_text(re.sub(r'(?m)^renderDistance:\d+', 'renderDistance:2', kept), 'utf8')
        args = client_args(game, {'projectseele.mapProbe': script.as_posix()}, 'raise-%s.args' % label, heap, world=name)
        result = run_client(args, 20, 'R64 bake: raise Tokyo-3 on the mirror ' + label, exclusive, game=game)
    finally:
        options.write_text(kept, 'utf8')
        restore_mods(game, held)
        shutil.copyfile(WORK / 'jars/final.jar', game / JAR)
    log = client_log(game)
    text = (game / 'logs/latest.log').read_text('utf8', 'replace')
    after = city_state(world)
    ok = log['ok'] and after.get('Depth') == 0 and after.get('Target') == 0 and after.get('Phase') == 'IDLE'
    return dict(ok=ok, before=before, after=after, client=result, client_log=log, held_mods=moved,
                endpoint_lines=[l[-200:] for l in text.splitlines() if 'R45 rigid city endpoint' in l][-2:])


# ---- steps ---------------------------------------------------------------------------------------------

def step_check(a):
    problems, notes = [], []
    ring_db = Path(a.ring_db or RING_DB)
    for name, path in (('formal world', FORMAL / 'level.dat'), ('shipped client jar', SHIP / JAR), ('reference server zip', REFERENCE_SERVER_ZIP),
                       ('outer ring LOD database', ring_db), ('args template', ARGS_TEMPLATE), ('probe jar', PROBE_JAR),
                       ('javaw', JAVAW), ('slot tool', SLOT)):
        if not path.exists():
            problems.append('missing ' + name + ': ' + str(path))
    if problems:
        save('check', dict(problems=problems))
        raise SystemExit('Required bake inputs are missing')
    missing = jar_classes(SHIP / JAR)
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
    core_rows, ring_rows = rows_of(formal_db), rows_of(ring_db, live=True)
    plan = plan_merge(core_rows, ring_rows, saved, changed | added)
    points = viewpoints(plan['rebuild'])
    sg = plan['saved_grid']
    ring_l0 = {(x, z) for (l, x, z), n in ring_rows.items() if l == 0 and n > 64 and classify(0, x, z, sg) == 'ring'}
    # The map-edges ring: x -6464..7584, z -5408..5920 in level-0 sections, minus what is saved.
    ring_want = {(x, z) for x in range(-6464 // 64, 7584 // 64 + 1) for z in range(-5408 // 64, 5920 // 64 + 1)
                 if classify(0, x, z, sg) == 'ring'}
    core_minutes = sum(min(25, max(6, math.ceil(c / SECTIONS_PER_MINUTE) + 2)) for _, _, c in points) + CLIENT_START_MIN
    # The four-reader R64 manifest checked 80,724 files in 307 s. Each mirror checks source and copy.
    mirror_minutes = 2 + math.ceil(2 * world_files / 15750)
    stages = dict(mirror_min=mirror_minutes, xaero_mirror_min=mirror_minutes, prepare_min=3, core_client_min=core_minutes, fill_pass_min=25,
                  city_raises_min=16 if a.city_raised else 0, xaero_min=12,
                  xaero_pregen_min=math.ceil(a.pregen_chunks / 42 / 60), pack_min=5)
    estimate = dict(
        **stages, xaero_pregen_chunks=a.pregen_chunks, reference_pregen_chunks_per_second=42,
        total_hours=round(sum(stages.values()) / 60, 1),
        ring_left_sections=len(ring_want - ring_l0), ring_left_hours_at_63_per_min=round(len(ring_want - ring_l0) / 63 / 60, 1))
    with zipfile.ZipFile(REFERENCE_SERVER_ZIP) as reference:
        seed_bytes = reference.getinfo('SEELE_R53_WORLD/' + GEO + '/data/DistantHorizons.sqlite').file_size
    ring_bytes = ring_db.stat().st_size
    lod_bytes = seed_bytes + ring_bytes
    # Budget full-size copies: ring snapshot, mutable core, export, SQLite journal, two ZIPs and aged LOD.
    work_bytes = (2 if a.city_raised else 1) * inst_bytes + 2 * world_bytes + ring_bytes + 3 * lod_bytes + a.pregen_chunks * 10 * 1024
    delivery_bytes = world_bytes + 2 * inst_bytes + 3 * lod_bytes
    disk = dict(work_drive=str(WORK.drive), work_free_gb=free_gb(WORK.drive + '/'), delivery_drive=str(a.delivery.resolve().drive), delivery_free_gb=free_gb(a.delivery),
                instance_gb=round(inst_bytes / 2**30, 2), world_gb=round(world_bytes / 2**30, 2),
                seed_bytes=seed_bytes, ring_bytes=ring_bytes, work_need_gb=round(work_bytes / 2**30, 1),
                delivery_need_gb=round(delivery_bytes / 2**30, 1),
                note='Work includes two mirrors, ring snapshot, mutable/export/journal LOD and estimated chunk generation. '
                     'Delivery budgets both archives and the aged database. Unpacked join-test copies are additional.')
    if WORK.resolve().drive.lower() == a.delivery.resolve().drive.lower():
        disk['work_need_gb'] += disk['delivery_need_gb']
    if disk['work_free_gb'] < disk['work_need_gb'] + 5:
        problems.append('not enough free space for WORK on ' + str(WORK.drive))
    if disk['delivery_free_gb'] < disk['delivery_need_gb'] + 5:
        problems.append('not enough free space on ' + disk['delivery_drive'] + ' for the zips')
    data = dict(
        problems=problems, notes=notes, formal_world=str(FORMAL), world_lock_free=lock_free, world_files=world_files,
        newest_region=datetime.datetime.fromtimestamp(newest).isoformat(timespec='seconds'),
        shipped_jar=dict(path=str(SHIP / JAR), modified=jar_time, bytes=(SHIP / JAR).stat().st_size, r63_classes_missing=missing),
        javaw=dict(path=str(JAVAW), from_java_home=JAVAW != JAVAW_FALLBACK, version=version[:1]),
        chunks=dict(saved=len(saved), changed_since_reference=len(changed), added=len(added), removed=len(removed)),
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
    # The bake client runs on the jar the pack ships; in the 8 GB exclusive window its 821 MB Unit-00 prototype
    # mesh fits (review session, 2026-11-13). The public build cannot open the world at all: the server reads the
    # three units' private meshes, hands and GEO before it loads (dry starts 07:17 and map-edges 07:30).
    # --slim-bake swaps only that client-render mesh for the public placeholder (dry start passed at 6 GB, 07:33).
    bake = slim_jar(SHIP / JAR, Path(a.bake_jar), WORK / 'jars/bake.jar') if a.slim_bake else SHIP / JAR
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
    def fail(error):
        raise error

    root = Path(root)
    paths = sorted(Path(base) / name for base, _, names in os.walk(root, onerror=fail) for name in names
                   if name not in MIRROR_SKIP and not name.endswith('.sqlite-shm'))
    files = {}
    # R64 has over 75,000 tiny rigid-city files. Overlap their opens while preserving the original digest order.
    with ThreadPoolExecutor(max_workers=4) as readers:
        for start in range(0, len(paths), 512):
            batch = paths[start:start + 512]
            for path, digest in zip(batch, readers.map(sha256_file, batch)):
                files[path.relative_to(root).as_posix()] = digest
    whole = hashlib.sha256(''.join(f'{k}\t{v}\n' for k, v in files.items()).encode()).hexdigest()
    region = hashlib.sha256(''.join(f'{k}\t{v}\n' for k, v in files.items() if k.startswith(GEO + '/region/')).encode()).hexdigest()
    return files, whole, region


def region_fingerprint(world):
    return {p.name: [p.stat().st_size, p.stat().st_mtime_ns] for p in sorted((world / GEO / 'region').glob('*.mca'))}


def mirror_world(locked=True, name=COPY, game=None, label=None):
    game = game or WORK / 'client'
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
        locked_seconds = round(time.time() - t) if locked else 0
    if locked:
        dst, mirror_whole, _ = manifest(target)
        if dst != src:
            differ = sorted(k for k in src.keys() | dst.keys() if src.get(k) != dst.get(k))
            raise SystemExit('Mirror differs from the formal world in %d files, e.g. %s' % (len(differ), differ[:5]))
        json.dump(dict(files=src), guard(WORK / 'logs' / ('manifest-%s.json' % (label or name))).open('w'), indent=0)
    return dict(target=str(target), robocopy=tail, files=len(src), sha256_all_files=whole, sha256_geofront_regions=region,
                region_fingerprint=fingerprint, recorded_batch=latest_batch(), seconds_locked=locked_seconds, seconds_total=round(time.time() - t),
                formal_newest_region=datetime.datetime.fromtimestamp(newest).isoformat(timespec='seconds'))


def step_mirror(a):
    # --no-lock is for trial runs only: a writer may change the world while it is copied.
    data = mirror_world(not a.no_lock)
    if a.batch and data['recorded_batch'] != a.batch:
        raise SystemExit('Batch table says %s, expected %s' % (data['recorded_batch'], a.batch))
    fingerprint = data.pop('region_fingerprint')
    save('mirror', dict(locked=not a.no_lock, **data))
    json.dump(fingerprint, guard(WORK / 'logs/mirror-fingerprint.json').open('w'))


def step_raise(a):
    """R64: the far view shows Tokyo-3 raised. Run after mirror and before prepare: the raised towers then count
    as changed chunks, so prepare drops their R63r rows and core bakes them from the raised city."""
    if not log_path('mirror').exists():
        raise SystemExit('Run mirror first')
    if log_path('prepare').exists() and log_path('prepare').stat().st_mtime > log_path('mirror').stat().st_mtime:
        raise SystemExit('prepare already ran on this mirror: run mirror again, then raise, then prepare')
    result = raise_city(COPY, a.raise_heap, a.exclusive)
    save('raise', result)
    if not (result.get('ok') or result.get('skipped')):
        raise SystemExit('The city did not reach the raised state on the mirror: ' + json.dumps(result.get('after')))


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
                         city=city_state(world), seconds=round(time.time() - t, 1)))
    if a.v6:
        # V6 (approved 2026-11-15): drop the L1-L3 ancestors of the rebuilt sections and flag their kept children,
        # so DH also rebuilds sections far from every viewpoint.
        run = subprocess.run([sys.executable, str(ROOT / 'tools/dh_v6_prepare.py'), str(db), str(WORK / 'lod/rebuild_sections.json')],
                             capture_output=True, text=True, errors='replace')
        if run.returncode or not run.stdout.rstrip().endswith('done'):
            raise SystemExit('dh_v6_prepare failed: ' + (run.stdout + run.stderr)[-600:])
        data = json.loads(log_path('prepare').read_text('utf8'))
        data.pop('step', None)
        data.pop('at', None)
        data['v6'] = run.stdout.strip().splitlines()
        save('prepare', data)


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


def segmented_core(a, game, world, db):
    """Resume the prepared database in short clients. Each pass starts from the sections actually missing."""
    runs, stalled = [], set()
    before = coverage(world, db)
    if before['quick_check'] != 'ok':
        raise SystemExit('The prepared LOD database failed quick_check')
    cover = before
    while len(cover['core_missing']) > a.fill_threshold:
        points = viewpoints(cover['core_missing'], minimum=1)
        point = next((p for p in points if p[:2] not in stalled), None)
        if point is None:
            break
        number = len(runs) + 1
        script = WORK / 'scripts' / ('r63-dh-resume-%02d.json' % number)
        plan = probe_script([point], script, hover=a.segment_minutes)
        args = client_args(game, {'projectseele.mapProbe': script.as_posix()}, 'resume-%02d.args' % number, a.heap)
        started = time.time()
        result = run_client(args, a.segment_minutes + CLIENT_START_MIN + 10, 'R64 DH resume at %s,%s' % point[:2], a.exclusive, a.commit_floor_gib)
        native_log = guard(WORK / 'logs' / ('resume-%02d-%d.log' % (number, started)))
        shutil.copyfile(game / 'logs/latest.log', native_log)
        log = client_log()
        script_log = Path(str(script) + '.log')
        done = script_log.is_file() and script_log.read_text('utf8', 'replace').rstrip().endswith('done')
        saved = (result.startswith('saved-for-commit=') and result.endswith('exit=0')
                 and 'All dimensions are saved' in native_log.read_text('utf8', 'replace'))
        previous = len(cover['core_missing'])
        cover = coverage(world, db)
        remaining = len(cover['core_missing'])
        runs.append(dict(viewpoint=plan[0], seconds=round(time.time() - started, 1), client=result, script_done=done, pressure_saved=saved,
                         client_log=log, native_log=str(native_log), missing_before=previous, missing_after=remaining))
        save('core-progress', dict(started_missing=len(before['core_missing']), missing=remaining, runs=runs))
        if not (result == 'exit=0' and done or saved) or not log['ok'] or log['out_of_memory'] or cover['quick_check'] != 'ok':
            raise SystemExit('Interrupted LOD segment; the saved database can be resumed with core --segment-minutes')
        if remaining >= previous:
            stalled.add(point[:2])
    missing = len(cover['core_missing'])
    if missing > a.fill_threshold:
        raise SystemExit('LOD coverage stalled with %d missing sections; see core-progress.json' % missing)
    out = snapshot(db, WORK / 'out/geofront_lod.sqlite', live=True)
    gate = dict(script_done=all(r['script_done'] for r in runs), pressure_saves=sum(r['pressure_saved'] for r in runs),
                quick_check=cover['quick_check'], core_missing=missing,
                pending_parent_updates=cover['pending_parent_updates'])
    save('core', dict(ok=True, segmented=True, resumed_missing=len(before['core_missing']), segments=runs, gate=gate,
                      output=str(out), output_bytes=out.stat().st_size, core_level0=cover['core_level0'],
                      missing_sample=cover['core_missing'][:20]))


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
        if a.segment_minutes:
            return segmented_core(a, game, world, db)
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


def step_fill(a):
    """Another pass over the core sections still missing after core, with a fixed hover per viewpoint. With
    --backfill-old, sections DH still has not built take their R62 rows (batch 378 content) and are flagged so
    DH folds them into the levels above: a slightly old far view instead of a hole."""
    game = WORK / 'client'
    world = game / 'saves' / COPY
    db = world / GEO / 'data/DistantHorizons.sqlite'
    if not world_unchanged_since_mirror():
        raise SystemExit('The formal world changed since the mirror: run mirror, prepare and core again')
    before = coverage(world, db)
    points = viewpoints(before['core_missing'], minimum=a.min_sections)[:8]
    plan, result, log = [], None, None
    if points and a.hover != 0:
        plan = probe_script(points, WORK / 'scripts/r63-dh-fill2.json', hover=a.hover or 20)
        shutil.copyfile(WORK / 'jars/probe.jar', guard(game / JAR))
        held = WORK / 'mods-held'
        hold_mods(game, ['oculus-*.jar'], held)
        try:
            set_toml(game / 'config/DistantHorizons.toml', {'numberOfThreads': str(a.dh_threads)})
            args = client_args(game, {'projectseele.mapProbe': (WORK / 'scripts/r63-dh-fill2.json').as_posix()}, 'fill2.args', a.heap)
            result = run_client(args, sum(p['minutes'] for p in plan) + CLIENT_START_MIN + 10, 'R63 DH second fill', a.exclusive)
        finally:
            restore_mods(game, held)
            shutil.copyfile(WORK / 'jars/final.jar', game / JAR)
        log = client_log()
    script_log = Path(str(WORK / 'scripts/r63-dh-fill2.json') + '.log')
    done = not plan or (script_log.exists() and script_log.read_text('utf8', 'replace').rstrip().endswith('done'))
    after = coverage(world, db)
    missing_after_pass = len(after['core_missing'])
    after_pass = list(after['core_missing'])
    backfilled = 0
    # 2026-11-13 11:39 the client was closed after 23 s and old rows went in anyway: backfill only after a full pass.
    if a.backfill_old and after['core_missing'] and not done:
        raise SystemExit('The fill client did not finish its viewpoints; refusing to backfill R62 rows')
    if a.backfill_old and after['core_missing']:
        old = (FORMAL / GEO / 'data/DistantHorizons.sqlite').resolve().as_uri() + '?mode=ro&immutable=1'
        c = sqlite3.connect(guard(db).as_uri(), uri=True)
        try:
            c.execute('attach database ? as old', (old,))
            cols = [r[1] for r in c.execute('pragma table_info(FullData)')]
            c.execute('create temp table pick(PosX int, PosZ int, primary key (PosX, PosZ))')
            c.executemany('insert into pick values (?,?)', after['core_missing'])
            before_rows = c.execute('select count(*) from FullData').fetchone()[0]
            c.execute('insert or ignore into FullData (%s) select %s from old.FullData o where o.DetailLevel = 0 and (o.PosX, o.PosZ) in '
                      '(select PosX, PosZ from pick)' % (','.join(cols), ','.join('o.' + x for x in cols)))
            c.execute('update FullData set ApplyToParent = 1 where DetailLevel = 0 and (PosX, PosZ) in (select PosX, PosZ from pick)')
            c.commit()
            backfilled = c.execute('select count(*) from FullData').fetchone()[0] - before_rows
            c.execute('detach database old')
        finally:
            c.close()
        after = coverage(world, db)
    out = snapshot(db, WORK / 'out/geofront_lod.sqlite', live=True)
    ok = after['quick_check'] == 'ok' and len(after['core_missing']) <= a.fill_threshold and (log is None or log['ok']) and done
    save('fill', dict(ok=ok, missing_before=len(before['core_missing']), points=plan, client=result, client_log=log, script_done=done,
                      missing_after_pass=missing_after_pass, backfilled_sections=after_pass if backfilled else [],
                      backfilled_from_r62=backfilled, missing_after=len(after['core_missing']),
                      pending_parent_updates=after['pending_parent_updates'], quick_check=after['quick_check'],
                      output=str(out), output_bytes=out.stat().st_size))
    if not ok:
        raise SystemExit('Fill did not pass its gate')


def step_xaero(a):
    # Its own mirror, so a minimap redo never wipes the prepared LOD database in MAP_REVIEW.
    game = WORK / 'client'
    starts = {'mirror': time.time()}
    name = XAERO_COPY
    if a.city_raised:
        # The map probe only opens MAP_REVIEW. Give Xaero its own client and canonical review save.
        game = guard(WORK / 'xaero-client')
        wait_no_exclusive('copying the Xaero client')
        robocopy(WORK / 'client', game, '/E', '/XD', *INSTANCE_SKIP, '/XF', 'session.lock', '*.log')
        name = COPY
    info = mirror_world(name=name, game=game, label=XAERO_COPY)
    info.pop('region_fingerprint')
    raised = None
    if a.city_raised:
        # The minimap shows the same city as the far view.
        starts['raise_city'] = time.time()
        raised = raise_city(name, a.raise_heap, a.exclusive, game=game, label=XAERO_COPY)
        if (game / 'logs/latest.log').is_file():
            shutil.copyfile(game / 'logs/latest.log', guard(WORK / 'logs/xaero-raise-native.log'))
        if not (raised.get('ok') or raised.get('skipped')):
            save('xaero', dict(ok=False, raise_city=raised, mirror=info))
            raise SystemExit('The city did not reach the raised state on the minimap mirror')
    baked = game / 'xaero/world-map' / name.replace('_', '^us^') / 'projectseele$geofront'
    if baked.exists():
        shutil.move(str(baked), str(guard(baked.with_name('projectseele$geofront.before-' + time.strftime('%H%M%S')))))
    shutil.copyfile(WORK / 'jars/final.jar', guard(game / JAR))
    held = WORK / 'mods-held'
    moved = hold_mods(game, ['DistantHorizons-*.jar', 'oculus-*.jar'], held)
    pregen = None
    pregen_result = None
    try:
        if a.xaero_pregen:
            # The outer ring was never saved as chunks; generate them on this mirror only, in a run of its own.
            starts['pregen'] = time.time()
            args = client_args(game, {'projectseele.xaeroBakePregen': a.xaero_pregen}, 'xaero-pregen.args', world=name)
            pregen = run_client(args, a.pregen_minutes, 'Xaero bake outer ring pregeneration', a.exclusive, game=game)
            native_log = WORK / 'logs/xaero-pregen-native.log'
            shutil.copyfile(game / 'logs/latest.log', guard(native_log))
            text = native_log.read_text('utf8', 'replace')
            match = re.search(r'Xaero bake pregeneration finished: (\d+) chunks in (\d+) s', text)
            pregen_result = dict(expected=a.pregen_chunks, generated=int(match[1]) if match else None,
                                 seconds=int(match[2]) if match else None, log=str(native_log))
            if pregen_result['generated'] != a.pregen_chunks or not client_log(game)['ok'] or pregen != 'exit=0':
                save('xaero', dict(ok=False, pregen=pregen, pregen_result=pregen_result, pregen_finished=False, mirror=info))
                raise SystemExit('Outer ring pregeneration did not finish')
        starts['bake_maps'] = time.time()
        args = client_args(game, {'projectseele.xaeroBake': 'true'}, 'xaero.args', world=name)
        result = run_client(args, 25 if not a.xaero_pregen else 90, 'R63 Xaero minimap bake', a.exclusive, game=game)
    finally:
        restore_mods(game, held)
    logtext = (game / 'logs/latest.log').read_text('utf8', 'replace')
    zips = sorted(baked.rglob('*.zip')) if baked.exists() else []
    caves = sum('caves' in p.relative_to(baked).parts for p in zips)
    surface = len(zips) - caves
    finished = (result == 'exit=0' and client_log(game)['ok'] and 'Xaero map bake finished' in logtext
                and 'Xaero map bake surface finished, full cave layer started' in logtext and surface > 0 and caves > 0)
    out = WORK / 'out/xaero/projectseele$geofront'
    if finished and zips:
        if out.exists():
            shutil.rmtree(guard(out))
        shutil.copytree(baked, guard(out))
    start_times = list(starts.values())
    phases = {name: dict(start=start, end=end, seconds=round(end - start, 1))
              for (name, start), end in zip(starts.items(), start_times[1:] + [time.time()])}
    save('xaero', dict(ok=finished and bool(zips), client=result, pregen=pregen, finished=finished, region_zips=len(zips), held_mods=moved,
                       pregen_result=pregen_result, surface_region_zips=surface, cave_region_zips=caves,
                       mirror=info, raise_city=raised, phases=phases, output=str(out)))
    if not (finished and zips):
        raise SystemExit('Minimap bake did not finish')


def step_report(a):
    core = json.loads(log_path('core').read_text('utf8'))
    xaero = json.loads(log_path('xaero').read_text('utf8'))
    cmd = [sys.executable, '-I', str(ROOT / 'tools/package_r60.py'), '--date', time.strftime('%Y%m%d'),
           '--world', str(FORMAL), '--client', str(SHIP), '--delivery', str(a.delivery), '--server-template', str(REFERENCE_SERVER_ZIP),
           '--map-note', '<一行地图状态>', '--server-address', '<服务器地址>', '--xaero-map', xaero['output'], '--geofront-lod', core['output']]
    if a.client_template:
        cmd += ['--client-template', str(a.client_template)]
    if a.compare_build:
        cmd += ['--compare-build', str(a.compare_build)]
    if a.release_source:
        cmd += ['--release-source', str(a.release_source)]
    if a.logged_world_folder:
        cmd += ['--logged-world-folder', a.logged_world_folder]
    save('report', dict(check_first=subprocess.list2cmdline(cmd + ['--check', str(WORK / 'logs/package-check.json')]),
                        then_pack=subprocess.list2cmdline(cmd + ['--pack'])))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('step', choices=['check', 'instance', 'mirror', 'raise', 'prepare', 'drystart', 'core', 'fill', 'xaero', 'report'])
    p.add_argument('--v6', action='store_true', help='prepare: then run dh_v6_prepare.py on the rebuild list (R64)')
    p.add_argument('--city-raised', action='store_true', help='xaero: raise Tokyo-3 on the minimap mirror before baking (R64)')
    p.add_argument('--raise-heap', default='6G', help='raise, xaero --city-raised: client heap for the city raise run')
    p.add_argument('--hover', type=int, help='fill: minutes per viewpoint (default 20; 0 skips the client pass)')
    p.add_argument('--min-sections', type=int, default=1, help='fill: smallest group of missing sections worth a viewpoint')
    p.add_argument('--backfill-old', action='store_true', help='fill: give sections still missing their R62 rows, flagged for the levels above')
    p.add_argument('--slim-bake', action='store_true', help='instance: bake on the shipped jar minus the 821 MB prototype mesh (default: the shipped jar as is)')
    p.add_argument('--bake-jar', default=str(PUBLIC_JAR), help='instance --slim-bake: public build of main whose placeholder replaces the prototype mesh')
    p.add_argument('--world', help='prepare: world whose saved chunks count (default: the mirror)')
    p.add_argument('--db', help='prepare: database to change in place (default: the mirror\'s GeoFront database); must be under WORK')
    p.add_argument('--ring-db', help='prepare: outer ring database (default: the map-edges R64 ring copy on D:)')
    p.add_argument('--minutes', type=int, help='core: client time limit (default: the plan plus 10)')
    p.add_argument('--segment-minutes', type=int, help='core: resume the prepared LOD database with one viewpoint per fresh client, hovering this many minutes')
    p.add_argument('--commit-floor-gib', type=float, default=6.5, help='core --segment-minutes: save and close if available Windows commit falls below this reserve')
    p.add_argument('--fill-threshold', type=int, default=50, help='core: missing core sections tolerated without a fill pass')
    p.add_argument('--points', type=int, help='prepare: keep only the first N viewpoints (trial runs)')
    p.add_argument('--exclusive', action='store_true', help='core, xaero: run with the whole machine (slot.py exclusive); core then defaults to 8G and 4 DH threads')
    p.add_argument('--heap', help='core: client heap (default 8G with --exclusive, else 6G)')
    p.add_argument('--dh-threads', type=int, help='core: DH worker threads (default 4 with --exclusive, else 3: 4 at 6G ran out of heap in the trial)')
    p.add_argument('--no-lock', action='store_true', help='mirror: copy without holding session.lock (trial runs only, never for packing)')
    p.add_argument('--batch', type=int, help='mirror: the batch the formal world should be at; refuse if the batch table says otherwise')
    p.add_argument('--client-template', type=Path, help='report: PCL ZIP to pass to the packager')
    p.add_argument('--compare-build', type=Path, help='report: compiled jar to pass to the packager')
    p.add_argument('--release-source', type=Path, help='report: source checkout matching the jar to be packaged')
    p.add_argument('--logged-world-folder', help='report: source folder name in the shipped client DH logs for renamed mirrors')
    p.add_argument('--source-world', type=Path, default=FORMAL, help='Stopped world used for checks and every mirror')
    p.add_argument('--source-client', type=Path, default=SHIP, help='Client instance supplying the exact jar and assets to ship')
    p.add_argument('--reference-server', type=Path, default=REFERENCE_SERVER_ZIP, help='Server zip whose world matches the starting LOD database')
    p.add_argument('--batch-log', type=Path, default=BATCH_LOG, help='Execution order table corresponding to --source-world')
    p.add_argument('--delivery', type=Path, default=Path('F:/eva/delivery'), help='Volume used for package disk estimates')
    p.add_argument('--work', help='work folder (default E:/eva-r63-rebake)')
    p.add_argument('--slot-name', help='slot.py name for the client runs (default r63-pack; trial runs by another session use their own)')
    p.add_argument('--xaero-pregen', help='check, xaero: inclusive x0,z0,x1,z1 block bounds to pregenerate (outer ring: -6464,-5408,7584,5920)')
    p.add_argument('--pregen-minutes', type=int, default=360, help='xaero --xaero-pregen: client time limit for the pregeneration run (the R64 outer ring takes over four hours)')
    a = p.parse_args()
    if a.segment_minutes is not None and a.segment_minutes < 1:
        p.error('--segment-minutes must be at least 1')
    if a.commit_floor_gib <= 0:
        p.error('--commit-floor-gib must be positive')
    a.pregen_chunks = 0
    if a.xaero_pregen is not None:
        try:
            x0, z0, x1, z1 = map(int, a.xaero_pregen.split(','))
        except ValueError:
            p.error('--xaero-pregen requires four integer coordinates x0,z0,x1,z1')
        if x0 > x1 or z0 > z1:
            p.error('--xaero-pregen requires x0 <= x1 and z0 <= z1')
        # Match XaeroMapBake's inclusive chunk rectangle, including already saved chunks.
        a.pregen_chunks = ((x1 >> 4) - (x0 >> 4) + 1) * ((z1 >> 4) - (z0 >> 4) + 1)
    # Review session, 2026-11-13: with the machine to ourselves R62's 8 GB / 4 threads; shared, 6 GB / 3 threads.
    a.heap = a.heap or ('8G' if a.exclusive else '6G')
    a.dh_threads = a.dh_threads or (4 if a.exclusive else 3)
    globals().update(FORMAL=a.source_world.resolve(), SHIP=a.source_client.resolve(),
                     REFERENCE_SERVER_ZIP=a.reference_server.resolve(), BATCH_LOG=a.batch_log.resolve())
    if a.work:
        globals()['WORK'] = Path(a.work)
    if FORMAL == WORK.resolve() or WORK.resolve().is_relative_to(FORMAL) or FORMAL.is_relative_to((WORK / 'client').resolve()):
        raise SystemExit('The source world and working client must be separate')
    if a.step == 'instance':
        target_client = (WORK / 'client').resolve()
        if SHIP.is_relative_to(target_client) or target_client.is_relative_to(SHIP):
            raise SystemExit('The source client and working client must be separate')
    if a.slot_name:
        globals()['SLOT_NAME'] = a.slot_name
    globals()['step_' + a.step](a)


if __name__ == '__main__':
    main()

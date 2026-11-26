"""R65 join test of the shipped pair on this machine: extract both zips, start the pinned server, join with the packed
client, check what a release needs, and stop the way the quickstart tells server owners to (players gone, DH idle).

  python tools/r65_smoke.py prepare --delivery F:/eva/delivery --date 20261125 --out <empty dir>
  python tools/r65_smoke.py run     --delivery F:/eva/delivery --date 20261125 --out <same dir>
  python tools/r65_smoke.py lower   --delivery F:/eva/delivery --date 20261125 --out <same dir>

run: boot, join, GeoFront heartbeat rounds with memory samples, the R21 street-fixture recount when the save asks for
one, the GeoFront dome far view inside the cavity, the EVA body profile from projectseele-local-maps, no "lost
original bones", the baked minimap kept on join. lower: lowers Tokyo-3, waits for the R21 cover count (must be 0)
and reads the Sachiel sortie briefing. Each step takes its slots from F:/eva/.claude/client-slots/slot.py.
Test-only local changes: loopback address, offline profile, EULA, muted client, the baked minimap copied under the
loopback address. The shipped zips are never written.
"""
import argparse, ctypes, hashlib, json, re, shutil, subprocess, sys, time, uuid, zipfile
from ctypes import wintypes
from pathlib import Path, PurePosixPath

PY = 'F:/eva/.claude/fable-review/pyfr/Scripts/frpy.exe'
SLOT = 'F:/eva/.claude/client-slots/slot.py'
JAVA = Path('E:/Users/liboy/jdks/jdk-17.0.19+10/bin')
MAIN_JAR = Path('F:/eva/artifacts/r53_repair_20261015/client/mods/projectseele-0.1.0-all.jar')
ARGS_TEMPLATE = Path('F:/eva/.claude/map-work/run17.args')
NAME, IP, PORT = 'PackR65User', '127.0.0.2', 25565
JAR = 'mods/projectseele-0.1.0-all.jar'


def digest(p):
    with open(p, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def stamp():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def slot(name, purpose, acquire):
    args = [PY, '-I', SLOT, 'acquire', name, '60', purpose] if acquire else [PY, '-I', SLOT, 'release', name]
    while True:
        r = subprocess.run(args, capture_output=True, text=True, errors='replace')
        if not acquire or re.search(r'(?m)^(ok|extended):', r.stdout):
            return
        if 'refused:' not in r.stdout:
            raise RuntimeError((args, r.stderr, r.stdout))
        time.sleep(45)


def unzip(path, into, prefix=''):
    into.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if info.is_dir() or not info.filename.startswith(prefix):
                continue
            rel = PurePosixPath(info.filename[len(prefix):])
            assert rel.parts and '..' not in rel.parts and not rel.is_absolute(), info.filename
            target = into.joinpath(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, 'wb') as dst:
                shutil.copyfileobj(src, dst, 1 << 22)


def read(p, encoding='utf8'):
    try:
        return p.read_bytes().decode(encoding, errors='replace')
    except FileNotFoundError:
        return ''


def wait(p, log, needle, seconds):
    start = time.monotonic()
    while time.monotonic() - start < seconds:
        text = read(log)
        match = re.search(needle, text, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(0)[-450:]
        if p.poll() is not None:
            raise RuntimeError(f'{log} exited {p.returncode}, waiting for {needle}')
        if 'This crash report has been saved' in text:
            raise RuntimeError(f'Crash in {log}')
        time.sleep(3)
    raise TimeoutError((str(log), needle))


def close_window(p):
    if not p or p.poll() is not None:
        return
    api = ctypes.windll.user32
    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def close(hwnd, _):
        pid = ctypes.c_ulong()
        api.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == p.pid:
            api.PostMessageW(hwnd, 0x10, 0, 0)
        return True
    api.EnumWindows(callback(close), 0)


def send(p, cmd):
    p.stdin.write((cmd + '\n').encode('utf8'))
    p.stdin.flush()


class _Entry(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG), ('dwFlags', wintypes.DWORD),
                ('szExeFile', wintypes.WCHAR * 260)]


class _Mem(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(k, ctypes.c_size_t) for k in (
        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


def processes(root):
    """root and its descendants: {pid: (exe, private bytes)}."""
    kernel, ps = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.OpenProcess.restype = wintypes.HANDLE
    children = {}
    snap = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = _Entry(); entry.dwSize = ctypes.sizeof(_Entry)
    ok = kernel.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        children.setdefault(int(entry.th32ParentProcessID), []).append((int(entry.th32ProcessID), entry.szExeFile))
        ok = kernel.Process32NextW(snap, ctypes.byref(entry))
    kernel.CloseHandle(snap)
    out, stack = {}, [(root, '')]
    while stack:
        pid, exe = stack.pop()
        if pid in out:
            continue
        stack.extend(children.get(pid, []))
        h = kernel.OpenProcess(0x410, False, pid)
        if h:
            m = _Mem(); m.cb = ctypes.sizeof(_Mem)
            if ps.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb):
                out[pid] = (exe, int(m.PrivateUsage))
            kernel.CloseHandle(h)
    return out


def wait_dh_idle(out, server):
    """No DH worker processing queued chunk updates in three samples in a row (the quickstart's half-minute wait)."""
    java = [pid for pid, (exe, _) in processes(server.pid).items() if pid != server.pid and exe.lower() == 'java.exe']
    if len(java) != 1:
        raise RuntimeError(('packaged server child', java))
    observations, stable = [], 0
    for i in range(30):
        time.sleep(10)
        dump = subprocess.run([str(JAVA / 'jcmd.exe'), str(java[0]), 'Thread.print'], capture_output=True, check=True).stdout.decode('utf8', 'replace')
        busy = [b for b in re.split(r'\n(?=")', dump) if b.startswith('"DH-PriorityTaskPicker') and 'SharedApi.processQueuedChunkUpdate' in b]
        observations.append(dict(at=stamp(), pending_workers=len(busy)))
        (out / 'idle-before-stop.json').write_text(json.dumps(observations, indent=1), 'utf8')
        stable = 0 if busy else stable + 1
        if i >= 4 and stable >= 3:
            return observations
    raise RuntimeError('DH chunk updates still active after the idle hold')


def r21_saved(world):
    """The street-fixture state the save carries and the manifest it should have been counted against (8778ee81)."""
    import gzip, struct
    raw = gzip.decompress((world / 'dimensions/projectseele/geofront/data/projectseele_battlefield_r21.dat').read_bytes())

    def find(kind, name):
        k = raw.find(kind + struct.pack('>H', len(name)) + name.encode())
        return -1 if k < 0 else k + 3 + len(name)
    j = find(b'\x08', 'Manifest')
    saved = None if j < 0 else raw[j + 2:j + 2 + struct.unpack('>H', raw[j:j + 2])[0]].decode()
    j = find(b'\x03', 'Conflicts'); conflicts = None if j < 0 else struct.unpack('>i', raw[j:j + 4])[0]
    j = find(b'\x01', 'Hidden'); hidden = None if j < 0 else bool(raw[j])
    now = digest(world / 'battlefield_r21.json')
    return dict(saved_manifest=saved, manifest_now=now, conflicts=conflicts, hidden=hidden, recount_due=saved != now)


def minimap_census(client):
    root = client / 'xaero' / 'world-map'
    out = {}
    for server in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        for dim in sorted(p for p in server.iterdir() if p.is_dir()):
            for mw in sorted(p for p in dim.iterdir() if p.is_dir()):
                zips = [q.relative_to(mw).as_posix() for q in mw.rglob('*.zip')]
                out[f'{server.name}/{dim.name}/{mw.name}'] = dict(surface=sum('caves/' not in z for z in zips), caves=sum('caves/' in z for z in zips))
    return out


def zips(a):
    return (a.delivery / f'Project_SEELE_Encore_R65_{a.date}_Client_PCL.zip', a.delivery / f'Project_SEELE_Encore_R65_{a.date}_Server.zip',
            json.loads((a.delivery / f'R65_{a.date}_receipt.json').read_bytes())['main_jar'])


def prepare(a):
    out, (client_zip, server_zip, jar) = a.out, zips(a)
    server, client = out / 'server', out / 'client'
    out.mkdir(parents=True, exist_ok=True)
    unzip(server_zip, server); unzip(client_zip, client, 'overrides/')
    assert digest(client / JAR) == digest(server / JAR) == jar['sha256']
    assert digest(MAIN_JAR) == (jar['base_jar']['sha256'] if jar.get('jar_additions') else jar['sha256']), 'main client jar changed since the pack'
    assert not (client / 'saves').exists() and (server / 'SEELE_R53_WORLD/level.dat').is_file() and (client / 'PCL/Setup.ini').is_file()
    boot = subprocess.run([str(JAVA / 'java.exe'), '-jar', 'server.jar', '--check'], cwd=server, capture_output=True, text=True)
    assert boot.returncode == 0 and '47.4.10' in boot.stdout, boot.stdout + boot.stderr
    props = read(server / 'server.properties')
    assert next((v.partition('=')[2] for v in props.splitlines() if v.startswith('max-tick-time=')), '60000') == '60000'
    opts = client / 'options.txt'
    text = re.sub(r'(?m)^pauseOnLostFocus:\w+', 'pauseOnLostFocus:false', opts.read_text('utf8'))
    text = re.sub(r'(?m)^soundCategory_master:[0-9.]+', 'soundCategory_master:0.0', text)  # test clients stay muted
    opts.write_text(text, 'utf8')
    overrides = {'server-ip': IP, 'server-port': str(PORT), 'online-mode': 'false', 'enforce-secure-profile': 'false'}
    props = '\n'.join(l for l in props.splitlines() if l.partition('=')[0] not in overrides) + '\n' + ''.join(f'{k}={v}\n' for k, v in overrides.items())
    (server / 'server.properties').write_text(props, 'utf8'); (server / 'eula.txt').write_text('eula=true\n', 'ascii')
    args = ARGS_TEMPLATE.read_text('utf8').replace('F:/eva/.claude/map-work/client', client.as_posix()).replace('"-Xmx8G"', '"-Xmx6G"')
    args = re.sub(r'"-Dprojectseele\.mapProbe=[^"]*"\s*', '', args)
    args = re.sub(r'("--username"\s+)"[^"]*"', '"--username" "' + NAME + '"', args)
    offline = uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + NAME).encode()).digest(), version=3)
    args = re.sub(r'("--uuid"\s+)"[^"]*"', '"--uuid" "' + offline.hex + '"', args)
    args = re.sub(r'"--quickPlaySingleplayer"\s+"[^"]*"', '"--quickPlayMultiplayer" "' + IP + ':' + str(PORT) + '"', args)
    for item in ('--quickPlayMultiplayer', client.as_posix(), NAME, '-Xmx6G'):
        assert item in args, item
    (out / 'client.args').write_text(args, 'ascii')
    # The pack keys the baked minimap to the release address; give Xaero the same folder under the loopback name.
    maps = client / 'xaero' / 'world-map'
    baked = [p for p in maps.iterdir() if p.is_dir() and p.name.startswith('Multiplayer_')]
    assert len(baked) == 1, baked
    shutil.copytree(baked[0], maps / ('Multiplayer_' + IP))
    (out / 'minimap_before.json').write_text(json.dumps(minimap_census(client), indent=1), 'utf8')
    print('prepared', out, flush=True)


def start(out, receipts, purpose):
    server, client = out / 'server', out / 'client'
    for log in (server / 'logs/latest.log', client / 'logs/latest.log'):
        if log.exists():  # an earlier run's log would satisfy every wait at once
            log.replace(log.with_name('latest.%s.log' % time.strftime('%H%M%S')))
    slot('r63-pack', 'R65 packaged dedicated server: ' + purpose, True); receipts['_slots'] = ['r63-pack']
    with (out / 'server.stdout').open('ab') as o:
        sp = subprocess.Popen([str(JAVA / 'java.exe'), '-jar', 'server.jar', 'nogui'], cwd=server, stdin=subprocess.PIPE,
                              stdout=o, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    receipts['_server'] = sp
    receipts['boot'] = wait(sp, server / 'logs/latest.log', r'^.*Done \([0-9.,]+s\)!.*$', 600)
    slot('r63-pack-cli', 'R65 packaged client (6G, muted): ' + purpose, True); receipts['_slots'].append('r63-pack-cli')
    with (out / 'client.stdout').open('ab') as o:
        cp = subprocess.Popen([str(JAVA / 'javaw.exe'), '@' + str(out / 'client.args')], cwd=client, stdout=o,
                              stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    receipts['_client'] = cp
    receipts['login'] = wait(sp, server / 'logs/latest.log', r'^.*' + NAME + r' joined the game.*$', 600)
    return sp, cp


def stop(out, receipts):
    # A boot or login timeout can interrupt start() before it returns the process handles.
    sp, cp = receipts.pop('_server', None), receipts.pop('_client', None)
    logS = out / 'server/logs/latest.log'
    if cp and cp.poll() is None:
        close_window(cp)
        try:
            cp.wait(90)
        except subprocess.TimeoutExpired:
            cp.terminate(); cp.wait(30); receipts['client_forced_exit'] = True
    if sp and sp.poll() is None:
        try:
            if receipts.get('ok'):
                wait(sp, logS, r'^.*' + NAME + r' left the game.*$', 60)
                send(sp, 'list')
                receipts['empty'] = wait(sp, logS, r'^.*There are 0 of a max.*players online.*$', 60)
                receipts['background_idle'] = wait_dh_idle(out, sp)
            send(sp, 'stop'); sp.wait(300)
        except Exception as e:
            receipts['ok'] = False; receipts['stop_issue'] = repr(e)
            if sp.poll() is None:
                send(sp, 'stop'); sp.wait(300)
    for name in reversed(receipts.pop('_slots', [])):
        slot(name, '', False)
    receipts.update(end=stamp(), server_exit=sp.returncode if sp else None, client_exit=cp.returncode if cp else None)


def run(a):
    out = a.out; server, client = out / 'server', out / 'client'
    logS, logC = server / 'logs/latest.log', client / 'logs/latest.log'
    r = {'start': stamp(), 'mods_sha256': zips(a)[2]['sha256']}
    r21_before = r21_saved(server / 'SEELE_R53_WORLD')
    try:
        sp, cp = start(out, r, 'join test')
        marker = 'R65-PACK-HEARTBEAT-' + time.strftime('%H%M%S')
        send(sp, 'execute in projectseele:geofront run teleport ' + NAME + ' -729 124 1205')
        where = marker + '-GEOFRONT'
        send(sp, 'execute as ' + NAME + ' at @s if dimension projectseele:geofront run tellraw @s ' + json.dumps({'text': where}))
        r['dimension_confirmed'] = wait(cp, logC, r'^.*' + where + r'.*$', 75)
        beats = []
        for i in range(6):  # six game-level replies over 150 s with the default 60 s watchdog
            time.sleep(25)
            token = marker + '-round-' + str(i + 1)
            send(sp, 'list'); send(sp, 'say ' + token)
            seen = wait(cp, logC, r'^.*' + token + r'.*$', 75)
            mem = processes(sp.pid); cmem = processes(cp.pid).get(cp.pid)
            beats.append(dict(at=stamp(), reply=seen, client_private_gb=round(cmem[1] / 2**30, 2) if cmem else None,
                              server_private_gb=round(max((v[1] for v in mem.values() if v[0].lower() == 'java.exe'), default=0) / 2**30, 2)))
        r['sustained_packet_rounds'] = beats
        r['r21_saved'] = r21_before
        if r21_before['recount_due']:
            r['r21_recount'] = wait(sp, logS, r'^.*R21 BATTLEFIELD RECOUNTED.*$', 600)
            if not re.search(r'conflicts=0\b', r['r21_recount']):
                raise RuntimeError(('R21 recount left conflicts', r['r21_recount']))
        else:
            r['r21_recount'] = 'not due (conflicts=%s)' % r21_before['conflicts']
        # Inside the GeoFront cavity the client draws the baked dome silhouette and logs its quads.
        send(sp, 'gamemode spectator ' + NAME)
        send(sp, 'execute in projectseele:geofront run teleport ' + NAME + ' 32 -300 320')
        r['dome_far_view'] = wait(cp, logC, r'^.*GeoFront far view R65: (?:[1-9]\d* cells, )?[1-9]\d* quads\b.*$', 120)
        off = [l for l in read(logC).splitlines() if 'GeoFront far view R65 off' in l]
        if off:
            raise RuntimeError(('GeoFront far view switched itself off', off[:3]))
        time.sleep(20)
        send(sp, 'save-all flush')
        r['saved'] = wait(sp, logS, r'^.*Saved the game.*$', 180)
        log = read(logS)
        body = [l for l in log.splitlines() if 'EVA body profile resolved: file=' in l]
        r['body_profile'] = body[:1]
        if not body or 'projectseele-local-maps' not in body[0]:
            raise RuntimeError(('EVA body profile not from projectseele-local-maps', body[:1]))
        lost = [l for l in log.splitlines() if 'lost original bones' in l]
        if lost:
            raise RuntimeError(('Server dropped a held Unit body', lost[:3]))
        r['ok'] = True
    except Exception as e:
        r['ok'] = False; r['error'] = repr(e)
    finally:
        stop(out, r)
        if r.get('ok'):
            before = json.loads((out / 'minimap_before.json').read_text('utf8')); after = minimap_census(client)
            key = 'Multiplayer_' + IP + '/projectseele$geofront/mw$default'
            r['minimap'] = dict(before=before.get(key), after=after.get(key), folders=sorted(after))
            if not after.get(key) or after[key] != before.get(key) or any(
                    k.startswith('Multiplayer_' + IP + '/projectseele$geofront/') and k != key for k in after):
                r['ok'] = False; r['error'] = 'baked minimap not kept on join'
        (out / 'receipt.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps({k: r.get(k) for k in ('ok', 'error', 'r21_recount', 'dome_far_view', 'server_exit', 'client_exit')}, ensure_ascii=False, indent=1))
    return r


def lower(a):
    out = a.out; server, client = out / 'server', out / 'client'
    logS, logC = server / 'logs/latest.log', client / 'logs/latest.log'
    r = {'start': stamp()}
    lines_after = lambda log, mark, pattern: [l for l in read(log).splitlines()[mark:] if re.search(pattern, l)]
    count = lambda log: len(read(log).splitlines())
    try:
        sp, cp = start(out, r, 'lowered-city cover count')
        send(sp, 'gamemode spectator ' + NAME)
        send(sp, 'execute in projectseele:geofront run teleport ' + NAME + ' -729 124 1205')
        time.sleep(15)
        mark = count(logS)
        send(sp, 'execute as ' + NAME + ' at @s run seele city lower')
        time.sleep(5)
        r['lower_reply'] = lines_after(logS, mark, r'/INFO\]')[-3:]
        began = time.monotonic(); cover = None
        while time.monotonic() - began < 45 * 60:
            found = lines_after(logS, mark, r'R21 BATTLEFIELD COVERED\b')
            if found:
                cover = found[-1]; break
            if sp.poll() is not None or 'This crash report has been saved' in read(logS):
                raise RuntimeError('server stopped or crashed while the city was lowering')
            time.sleep(20)
        if cover is None:
            raise TimeoutError('no R21 BATTLEFIELD COVERED line within 45 minutes')
        r['cover'], r['cover_seconds'] = cover, round(time.monotonic() - began)
        mark = count(logS)
        send(sp, 'execute as ' + NAME + ' at @s run seele city status')
        time.sleep(3)
        r['status_after'] = lines_after(logS, mark, r'/INFO\]')[-3:]
        markC = len(read(logC, 'gbk').splitlines())
        send(sp, 'execute as ' + NAME + ' at @s run seele sortie select sachiel')
        time.sleep(3)
        send(sp, 'execute as ' + NAME + ' at @s run seele sortie status')
        time.sleep(6)
        r['briefing'] = [l[l.find('[CHAT]'):][:700] for l in read(logC, 'gbk').splitlines()[markC:] if '[CHAT]' in l][-3:]
        send(sp, 'save-all flush')
        r['saved'] = wait(sp, logS, r'^.*Saved the game.*$', 180)
        r['ok'] = bool(re.search(r'conflicts=0\b', cover))
        if not r['ok']:
            r['error'] = 'R21 cover left conflicts: ' + cover
    except Exception as e:
        r['ok'] = False; r['error'] = repr(e)
    finally:
        stop(out, r)
        (out / 'lower-receipt.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), 'utf8')
    print(json.dumps({k: r.get(k) for k in ('ok', 'error', 'cover', 'cover_seconds', 'server_exit', 'client_exit')}, ensure_ascii=False, indent=1))
    return r


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('step', choices=['prepare', 'run', 'lower'])
    p.add_argument('--delivery', type=Path, required=True)
    p.add_argument('--date', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out = a.out.resolve()
    assert a.out.is_relative_to(Path('F:/eva/.claude/r63-pack-work')), 'test copies live under F:/eva/.claude/r63-pack-work'
    if a.step == 'prepare':
        prepare(a)
        return
    r = run(a) if a.step == 'run' else lower(a)
    sys.exit(0 if r.get('ok') and r.get('server_exit') == 0 and r.get('client_exit') == 0 and not r.get('client_forced_exit') else 1)


if __name__ == '__main__':
    main()

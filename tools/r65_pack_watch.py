"""Run tools/package_r60.py --pack at below-normal priority and suspend it (never kill it) while any session holds an
exclusive window in F:/eva/.claude/client-slots/slot.py, so a release pack never spoils someone's clean measurement.

  python tools/r65_pack_watch.py --log <dir> -- <package_r60.py arguments after --pack>
"""
import ctypes, re, subprocess, sys, time
from pathlib import Path

PY = 'F:/eva/.claude/fable-review/pyfr/Scripts/frpy.exe'
SLOT = 'F:/eva/.claude/client-slots/slot.py'
ROOT = Path(__file__).resolve().parent.parent


def window():
    r = subprocess.run([PY, '-I', SLOT, 'status'], capture_output=True, text=True, errors='replace')
    m = re.search(r'(?m)^exclusive: (.*)$', r.stdout)
    return bool(m and not m[1].startswith('none')), (m[1] if m else '?')


def main():
    args = sys.argv[1:]
    assert len(args) >= 3 and args[0] == '--log' and args[2] == '--', __doc__
    logs = Path(args[1]); logs.mkdir(parents=True, exist_ok=True)
    note = open(logs / 'pack_watch.log', 'a', encoding='utf8')
    say = lambda m: (note.write(time.strftime('%H:%M:%S ') + m + '\n'), note.flush())
    while True:
        busy, who = window()
        if not busy:
            break
        say('waiting before start: exclusive ' + who); time.sleep(20)
    p = subprocess.Popen([PY, 'tools/package_r60.py', '--pack'] + args[3:], cwd=ROOT,
                         stdout=open(logs / 'pack.log', 'w', encoding='utf8'), stderr=subprocess.STDOUT,
                         creationflags=0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
    say('started pid %d' % p.pid)
    ntdll, kernel = ctypes.WinDLL('ntdll'), ctypes.WinDLL('kernel32')
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(0x0800, False, p.pid)  # PROCESS_SUSPEND_RESUME; frpy runs Python in-process
    suspended, paused, since = False, 0.0, 0.0
    while p.poll() is None:
        time.sleep(5)
        busy, who = window()
        if busy and not suspended:
            ntdll.NtSuspendProcess(ctypes.c_void_p(handle)); suspended, since = True, time.time(); say('suspended: exclusive ' + who)
        elif not busy and suspended:
            ntdll.NtResumeProcess(ctypes.c_void_p(handle)); suspended = False; paused += time.time() - since
            say('resumed after %.0f s' % (time.time() - since))
    say('exit %s, paused %.0f s in total' % (p.returncode, paused))
    sys.exit(p.returncode)


if __name__ == '__main__':
    main()

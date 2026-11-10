"""Do the offline tools pose the same meshes the game draws?  python mesh_check.py [game.jar]

The renderer takes each unit's body from assets/projectseele/mesh/eva_unitNN.mesh.json
(EvaUnit01Renderer.meshResourceForVariant) inside the installed jar; scene.py and the bend
tools read the same names from the private pack (SEELE_PRIVATE).  When the two drift apart an
offline review passes a mesh nobody sees: in November 2026 the game drew a separate
eva_unitNN_skin_r55 copy for a week while every fix went into the file checked here.

Exit code 1 when a file differs or is missing on one side.  A jar that still carries
*_skin_r55 copies gets a warning: the renderer no longer reads them.
"""
import os
import sys
import zipfile
import zlib

import scene as S

GAME_JAR = os.environ.get('SEELE_GAME_JAR', 'F:/eva/.claude/motion-work/review_client/mods/projectseele-0.1.0-all.jar')
# what the renderer and the tools both load, relative to assets/projectseele
SHARED = ['mesh/eva_unit00.mesh.json', 'mesh/eva_unit01.mesh.json', 'mesh/eva_unit02.mesh.json', 'mesh/sachiel.mesh.json',
          'geo/eva_unit00.geo.json', 'geo/eva_unit01.geo.json', 'geo/eva_unit02.geo.json', 'geo/sachiel.geo.json']


def file_crc(path):
    crc = 0
    with open(path, 'rb') as f:
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            crc = zlib.crc32(block, crc)
    return os.path.getsize(path), crc & 0xffffffff


def compare(jar_path=GAME_JAR, private=S.PRIVATE):
    """[(name, state)] with state in same | differs | missing in jar | missing in pack, plus stale copies."""
    rows, stale = [], []
    with zipfile.ZipFile(jar_path) as jar:
        entries = {i.filename: (i.file_size, i.CRC) for i in jar.infolist()}
    for name in SHARED:
        in_jar = entries.get('assets/projectseele/' + name)
        local = private + '/' + name
        if in_jar is None:
            rows.append((name, 'missing in jar'))
        elif not os.path.exists(local):
            rows.append((name, 'missing in pack'))
        else:
            rows.append((name, 'same' if file_crc(local) == in_jar else 'differs'))
    for entry in entries:
        if entry.endswith('_skin_r55.mesh.json'):
            stale.append(entry)
    return rows, stale


def report(jar_path=GAME_JAR, private=S.PRIVATE, out=sys.stdout):
    """Print the comparison; True when the tools and the game read the same files."""
    if not os.path.exists(jar_path):
        print('mesh check skipped: no game jar at %s (set SEELE_GAME_JAR)' % jar_path, file=out)
        return True
    rows, stale = compare(jar_path, private)
    bad = [r for r in rows if r[1] != 'same']
    print('mesh check: %s  against  %s' % (jar_path, private), file=out)
    for name, state in rows:
        print('  %-28s %s' % (name, state), file=out)
    for entry in stale:
        print('  warning: %s is still in the jar; the renderer no longer reads it, drop it from the pack' % entry, file=out)
    if bad:
        print('MESH MISMATCH: the offline tools are not posing what the game draws (%d file%s)' % (len(bad), '' if len(bad) == 1 else 's'), file=out)
    return not bad


if __name__ == '__main__':
    sys.exit(0 if report(sys.argv[1] if len(sys.argv) > 1 else GAME_JAR) else 1)

"""Patch the user's private Complementary derivative, without redistributing it.

DH terrain precedes vanilla terrain. The latter writes the actual visible
surfaces; a distance-only alpha hole in the former assumes those chunks have
already uploaded. That assumption fails during GeoFront streaming.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def patch(source, destination):
    if source.resolve() == destination.resolve():
        raise ValueError('Write a separate candidate; preserve the original archive')
    changed = {}
    with zipfile.ZipFile(source) as before:
        names = before.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive entries')
        helper = before.read('shaders/lib/seele/cavern.glsl').decode('utf8')
        if '#ifdef SEELE_GEOFRONT' not in helper or 'SeeleCavernWeight()' not in helper:
            raise ValueError('The dimension-specific cavern helper is required')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, 'w') as after:
            for entry in before.infolist():
                data = before.read(entry.filename)
                if entry.filename in ('shaders/program/dh_terrain.glsl',
                                      'shaders/program/dh_water.glsl'):
                    old = data.decode('utf8')
                    needle = 'color.a *= smoothstep(far * 0.5, far * 0.7, lengthCylinder);'
                    if old.count(needle) != 1:
                        raise ValueError(f'Unexpected fade implementation: {entry.filename}')
                    text = old.replace(needle,
                        'color.a *= mix(smoothstep(far * 0.5, far * 0.7, lengthCylinder), '
                        '1.0, SeeleCavernWeight());')
                    include = '#include "/lib/seele/cavern.glsl"'
                    if include not in text:
                        text = text.replace('#ifdef FRAGMENT_SHADER',
                                            '#ifdef FRAGMENT_SHADER\n' + include, 1)
                    data = text.encode('utf8')
                    changed[entry.filename] = {
                        'before': hashlib.sha256(before.read(entry.filename)).hexdigest(),
                        'after': hashlib.sha256(data).hexdigest(),
                    }
                after.writestr(entry, data)
    with zipfile.ZipFile(source) as before, zipfile.ZipFile(destination) as after:
        assert after.testzip() is None
        assert before.namelist() == after.namelist()
        assert {name for name in before.namelist()
                if before.read(name) != after.read(name)} == set(changed)
    report = {'source': str(source), 'candidate': str(destination),
              'before_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'after_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'changed': changed, 'world_modified': False,
              'scope': 'Existing SEELE_GEOFRONT cavern fade only; original material alpha retained'}
    destination.with_suffix('.receipt.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    patch(args.source, args.destination)

"""Do not interpret the authored rain-free GeoFront biome as a sandstorm biome."""
from pathlib import Path
import argparse
import zipfile
from patch_zip_entries import replace_entries

ORIGINAL = 'uniform float inDry;'
REPLACEMENT = '''#ifdef SEELE_GEOFRONT
// The custom GeoFront biome has no precipitation; it is not a desert.
const float inDry = 0.0;
#else
uniform float inDry;
#endif'''

def patch(source):
    if REPLACEMENT in source:
        return source
    assert source.count(ORIGINAL) == 1
    return source.replace(ORIGINAL, REPLACEMENT)

def install(path):
    member = 'shaders/lib/uniforms.glsl'
    with zipfile.ZipFile(path) as archive:
        source = archive.read(member).decode('utf8')
    result = patch(source).encode('utf8')
    replace_entries(path, {member: result})
    with zipfile.ZipFile(path) as archive:
        assert archive.read(member) == result
    print('GeoFront dry-weather classification repaired:', path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('shader', type=Path)
    install(parser.parse_args().shader)

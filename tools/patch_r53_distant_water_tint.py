"""Keep the GeoFront DH water input in the same color space as near fluid vertices.

Patch a user-installed private shader pack, retaining all credits and other
programs. This does not distribute the source pack or change liquid textures.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATERIAL = 'shaders/lib/materials/specificMaterials/translucents/water.glsl'


def patch(source):
    colors = {json.loads(p.read_text('utf8'))['effects']['water_color']
              for p in (ROOT/'src/main/resources/data/projectseele/worldgen/biome').glob('geofront_*.json')}
    if len(colors) != 1:
        raise ValueError('GeoFront biome water tints differ; a shared distant tint is no longer valid')
    color = next(iter(colors))
    rgb = [(color >> shift) & 255 for shift in (16, 8, 0)]
    marker = '    #if WATER_STYLE < 3\n        vec3 colorPM = pow2(colorP.rgb);'
    source = source.replace('\r', '')
    if source.count(marker) != 1 or 'seeleWaterTint' in source:
        raise ValueError('Unexpected or already-patched water material')
    code = f'''    #if defined DH_WATER && defined SEELE_GEOFRONT && WATERCOLOR_MODE >= 2
        // DH colors already multiply texture albedo by biome tint; the water
        // material expects the tint alone, as supplied by vanilla fluid vertices.
        // Shared authored GeoFront biome water_color: 0x{color:06x}.
        vec3 seeleWaterTint = vec3({rgb[0]}.0, {rgb[1]}.0, {rgb[2]}.0) / 255.0;
        #if WATERCOLOR_MODE >= 3
            seeleWaterTint.g = max(seeleWaterTint.g, 0.39);
        #endif
        glColorM = sqrt1(seeleWaterTint) * vec3(1.0, 0.85, 0.8);
    #endif

'''
    return source.replace(marker, code+marker)


def build(source, output):
    if output.exists(): raise FileExistsError(output)
    with zipfile.ZipFile(source) as z:
        entries = {n: z.read(n) for n in z.namelist()}
    original = dict(entries)
    entries[MATERIAL] = patch(entries[MATERIAL].decode('utf8')).encode('utf8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items(): z.writestr(name, data)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert all(z.read(n) == data for n, data in original.items() if n != MATERIAL)
    receipt = dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                   output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                   changed_entries=[MATERIAL], near_water_lcl_and_other_dimensions_unchanged=True,
                   native_review_required=True)
    output.with_suffix('.json').write_text(json.dumps(receipt, indent=2), 'utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('source', type=Path); p.add_argument('output', type=Path)
    a = p.parse_args(); build(a.source, a.output)

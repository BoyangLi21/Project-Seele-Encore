"""Keep surface sunrise atmosphere out of the GeoFront cavern."""
from pathlib import Path
import argparse
import zipfile
from patch_zip_entries import replace_entries


def repair(pack):
    path = 'shaders/lib/atmospherics/fog/mainFog.glsl'
    with zipfile.ZipFile(pack) as z:
        source = z.read(path).decode('utf8')
    old = 'void DoAtmosphericFog(inout vec3 color, vec3 playerPos, float lViewPos, float VdotS) {'
    marker = '// SEELE: exterior atmosphere must not tint the underground cavern.'
    # Preserve distant lake/armor contrast inside the finite 1.8 km cavern.
    # This branch is already masked by dimension and underground altitude.
    previous = 'float cavernFog = 1.0 - exp(-2.0 * pow(max(lPos / renderDistance, 0.0), 2.2));'
    revised = 'float cavernFog = 1.0 - exp(-0.65 * pow(max(lPos / renderDistance, 0.0), 2.2));'
    fog_changed = previous in source
    source = source.replace(previous, revised)
    if marker in source:
        if fog_changed:
            replace_entries(pack, {path: source.encode('utf8')})
            with zipfile.ZipFile(pack) as z:
                assert z.read(path) == source.encode('utf8')
        return fog_changed
    assert source.count(old) == 1 and 'SeeleCavernWeight' in source
    new = old + '\n        ' + marker + '\n        if (SeeleCavernWeight() >= 1.0) return;'
    source = source.replace(old, new)
    # Blend the inherited atmosphere through the same dimension/altitude mask
    # already used by the cavern sky, rather than changing global shader options.
    start = source.index(new)
    end = source.index('\n#endif', start)
    section = source[start:end]
    blend = 'color = mix(color, fogColorM, fog);'
    assert section.count(blend) == 1
    section = section.replace(blend, 'color = mix(color, fogColorM, fog * (1.0 - SeeleCavernWeight()));')
    source = source[:start] + section + source[end:]
    replace_entries(pack, {path: source.encode('utf8')})
    with zipfile.ZipFile(pack) as z:
        assert z.read(path) == source.encode('utf8')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pack', type=Path)
    args = parser.parse_args()
    print({'updated': repair(args.pack), 'requires_shader_reload': True})

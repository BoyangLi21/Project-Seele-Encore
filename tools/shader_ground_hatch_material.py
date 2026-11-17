"""Shader pack material for the ground hatch cover (R64): the pack lights the cover as the grass it shows.

The shipped Complementary pack gives minecraft:grass_block its own material (one entry of shaders/block.properties).
A block the pack does not know gets the default material, and at a low viewing angle the closed hatch of the remote
air shaft then lies in the plain as a duller square. This adds projectseele:nerv_ground_hatch to the entry that holds
the plain grass block. Only that one line of block.properties changes; every other entry of the author's archive
stays byte for byte.

tools/package_r60.py applies it to the shipped pack under the pack's own file name. Standalone (prints both SHA-256
and the changed path):

  python tools/shader_ground_hatch_material.py <pack.zip> <out.zip>
"""
import hashlib
import sys
import zipfile

MEMBER = 'shaders/block.properties'
COVER = 'projectseele:nerv_ground_hatch'
GRASS = 'grass_block:snowy=false'


def patch_text(text):
    """block.properties with the cover in the entry of the plain grass block; unchanged if it is already there."""
    if COVER in text:
        return text
    newline = '\r\n' if '\r\n' in text else '\n'
    lines = text.split(newline)
    hits = [i for i, line in enumerate(lines)
            if line.startswith('block.') and '=' in line and GRASS in line.split('=', 1)[1].split()]
    if len(hits) != 1:
        raise ValueError('Expected one material entry with the plain grass block, found %d' % len(hits))
    lines[hits[0]] = lines[hits[0]].rstrip() + ' ' + COVER
    return newline.join(lines)


def main():
    source, target = sys.argv[1:3]
    changed = []
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(target, 'w') as zout:
        for info in zin.infolist():
            data = zin.read(info)
            if info.filename == MEMBER:
                text = data.decode('utf8')
                patched = patch_text(text)
                if patched != text:
                    data = patched.encode('utf8'); changed.append(info.filename)
            zout.writestr(info, data)
        zout.comment = zin.comment
    digest = lambda path: hashlib.sha256(open(path, 'rb').read()).hexdigest()
    print('source', digest(source))
    print('output', digest(target))
    print('changed', changed or 'nothing (already patched)')


if __name__ == '__main__':
    main()

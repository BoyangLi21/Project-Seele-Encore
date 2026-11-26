"""Build the private NERV-16 skin from the installed vehicle atlas and a local NERV logo."""
import argparse
import io
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

TEXTURE = 'assets/superbwarfare/textures/bedrock/vehicle/j_16.png'
MODEL = 'assets/superbwarfare/models/bedrock/vehicle/j_16.geo.json'
# The fuselage sides and four wing faces share this island. All other islands remain intact.
BADGE = (729, 668, 972, 771)
NUMBER = (717, 880, 1001, 951)


def stamp(atlas, box, mask):
    cut = ImageOps.contain(mask.crop(mask.getbbox()), (box[2]-box[0]-8, box[3]-box[1]-8), Image.Resampling.LANCZOS)
    area = Image.new('L', (box[2]-box[0], box[3]-box[1]))
    area.paste(cut, ((area.width-cut.width)//2, (area.height-cut.height)//2))
    # A narrow dark upper edge, light lower edge and shallow recess let the aircraft colour show through.
    shifted = Image.new('L', area.size)
    shifted.paste(area, (1, 2))
    shadow = ImageChops.subtract(area, shifted)
    light = ImageChops.subtract(shifted, area)
    face = Image.new('RGBA', area.size, (116, 122, 128, 0))
    face.putalpha(area.point(lambda value: value*150//255))
    for tint, edge in [((74, 80, 86), shadow), ((176, 182, 188), light)]:
        layer = Image.new('RGBA', area.size, tint)
        layer.putalpha(edge)
        face = Image.alpha_composite(face, layer)
    atlas.paste(face, box)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-jar', type=Path, required=True)
    parser.add_argument('--logo', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with zipfile.ZipFile(args.source_jar) as source:
        atlas = Image.open(io.BytesIO(source.read(TEXTURE))).convert('RGBA')
        geometry = json.loads(source.read(MODEL))['minecraft:geometry'][0]
    bones = {bone['name'] for bone in geometry['bones'] for cube in bone.get('cubes', [])
             if isinstance(cube.get('uv'), dict) and any(
                 BADGE[0] <= face['uv'][0] < BADGE[2] and BADGE[1] <= face['uv'][1] < BADGE[3]
                 for face in cube['uv'].values())}
    if atlas.size != (1024, 1024) or bones != {'body', 'wingL', 'wingL2'}:
        raise ValueError('The installed airframe uses a different UV layout.')
    emblem = Image.open(args.logo).convert('RGBA')
    ink = ImageChops.multiply(ImageChops.subtract(emblem.getchannel('R'), emblem.getchannel('G')), emblem.getchannel('A'))
    if not ink.getbbox():
        raise ValueError('The source logo has no red insignia.')
    stamp(atlas, BADGE, ink)
    # The source aircraft carries a white six-digit fleet number on a second transparent island.
    mask = Image.new('L', (340, 80))
    draw = ImageDraw.Draw(mask)
    draw.text((2, 0), 'NERV-16', font=ImageFont.load_default(size=66), fill=255, stroke_width=1)
    stamp(atlas, NUMBER, mask)
    image = io.BytesIO()
    atlas.save(image, format='PNG', optimize=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, 'w', zipfile.ZIP_DEFLATED) as pack:
        pack.writestr('pack.mcmeta', json.dumps({'pack': {'pack_format': 15, 'description': 'Project SEELE · NERV-16'}}))
        pack.writestr(TEXTURE, image.getvalue())
        for lang, label in [('zh_cn', 'NERV-16特别战斗机'), ('en_us', 'NERV-16 Special Fighter')]:
            pack.writestr(f'assets/superbwarfare/lang/{lang}.json', json.dumps({'entity.superbwarfare.j_16': label}, ensure_ascii=False))


if __name__ == '__main__':
    main()

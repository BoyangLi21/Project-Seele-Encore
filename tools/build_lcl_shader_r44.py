"""Preserve the active R39 lighting/switches and replace only its LCL override."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

from lcl_shader_material_r44 import material_patch

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def build(source, target):
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise ValueError('The original shader must remain intact')
    target.parent.mkdir(parents=True, exist_ok=True)
    changed = []
    path = 'shaders/program/gbuffers_water.glsl'
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
        if src.read('shaders/block.properties').decode().count('block.32001=projectseele:lcl') != 1:
            raise ValueError('Expected one existing LCL material assignment')
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == path:
                text = data.decode()
                start = text.index('    // Project SEELE LCL:')
                end = text.index('    // Blending', start)
                old = text[start:end]
                if old.count('if (mat == 32001)') != 1 or 'color.a = 0.30;' not in old:
                    raise ValueError('Unexpected existing LCL override; inspect before patching')
                data = (text[:start] + material_patch() + text[end:]).encode()
                changed.append(info.filename)
            dst.writestr(info, data)
        dst.writestr('SEELE_LCL_R44.txt', 'Local derivative: dense orange-red LCL. Only custom material 32001 changes. R39 facility illumination, command-room switches, original shader credits and licenses are preserved. Native visual review is recorded separately.\n')
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target) as dst:
        unchanged = [n for n in src.namelist() if n != path]
        assert all(src.read(n) == dst.read(n) for n in unchanged)
        assert changed == [path]
        assert dst.testzip() is None
    settings = source.with_name(source.name + '.txt')
    if settings.exists():
        shutil.copy2(settings, target.with_name(target.name + '.txt'))
    manifest = dict(source=str(source), source_sha256=sha(source.read_bytes()), output=str(target),
                    output_sha256=sha(target.read_bytes()), changed_shader_files=changed,
                    unchanged_files=len(unchanged), java_argb='F2DB5420', shader_alpha=242 / 255,
                    visual_review='pending', command_room_lighting='byte-identical to source R39')
    target.with_suffix('.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=ROOT / 'run/shaderpacks/ComplementaryUnbound_r5.3_SEELE_R39.zip')
    p.add_argument('--target', type=Path, default=ROOT / 'artifacts/rebuild_r44/lcl/ComplementaryUnbound_r5.3_SEELE_R44.zip')
    args = p.parse_args()
    print(json.dumps(build(args.source, args.target), indent=2))

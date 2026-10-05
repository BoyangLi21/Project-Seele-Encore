"""Preserve supplied UV/materials; split only the working mechanical assemblies."""
from pathlib import Path
import io, json, struct
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / 'artifacts/rebuild_r48/tripo_pipeline'
ASSETS = ROOT / 'artifacts/rebuild_r48/assets/assets/projectseele'


def textures(name):
    raw = (PIPE / name / 'lod0.glb').read_bytes()
    size = struct.unpack_from('<I', raw, 12)[0]
    doc = json.loads(raw[20:20 + size]); start = 28 + size
    mat = doc['materials'][0]; pbr = mat['pbrMetallicRoughness']
    target = ASSETS / 'textures/entity'; target.mkdir(parents=True, exist_ok=True)

    def pixels(texture):
        image = doc['images'][doc['textures'][texture['index']]['source']]
        view = doc['bufferViews'][image['bufferView']]
        offset = start + view.get('byteOffset', 0)
        return Image.open(io.BytesIO(raw[offset:offset + view['byteLength']])).convert('RGBA')

    base = pixels(pbr['baseColorTexture'])
    base.save(target / f'tripo_{name}_r48.png')
    if 'normalTexture' in mat:
        normal = pixels(mat['normalTexture'])
        # LabPBR normal: XY tangent normal, B ambient occlusion, A height.
        n = np.array(normal); n[:, :, 2] = 255; n[:, :, 3] = 255
        Image.fromarray(n).save(target / f'tripo_{name}_r48_n.png')
    if 'metallicRoughnessTexture' in pbr:
        packed = np.array(pixels(pbr['metallicRoughnessTexture']))
        spec = np.zeros_like(packed)
        spec[:, :, 0] = 255 - packed[:, :, 1]
        spec[:, :, 1] = np.where(packed[:, :, 2] > 128, 230, 10)
        spec[:, :, 3] = 255
        Image.fromarray(spec).save(target / f'tripo_{name}_r48_s.png')
    return base.size


def export(name):
    source = np.load(PIPE / name / 'lod0_geometry.npz')
    vertices = source['vertices'].astype(float)
    faces = source['triangles']; uv = source['uv'].copy(); uv[:, :, 1] = 1 - uv[:, :, 1]
    normals = source['normals'].astype(float)
    centres = vertices[faces].mean(1)
    labels = np.full(len(faces), 'body', dtype=object)
    anchors = {}
    if name == 'gripper':
        # Aperture centre and hinge pins measured on the imported geometry.
        jaws = (centres[:, 1] < .315) & (centres[:, 2] < -.145)
        labels[jaws & (centres[:, 0] < 0)] = 'jaw_left'
        labels[jaws & (centres[:, 0] >= 0)] = 'jaw_right'
        origin = np.array([0, .24, -.335]); scale = 6.0
        vertices = (vertices - origin) * scale
        anchors['mount'] = ((np.array([0, .97, -.02]) - origin) * scale).tolist()
        for side, sign in [('left', -1), ('right', 1)]:
            anchors['jaw_' + side] = ((np.array([sign * .29, .315, -.335]) - origin) * scale).tolist()
    else:
        labels[centres[:, 1] < .08] = 'deck'
        platform = (centres[:, 0] < -.171) & (centres[:, 1] > .595) & (centres[:, 1] < .81)
        labels[platform] = 'service_platform'
        contact_height = ((centres[:, 1] > .22) & (centres[:, 1] < .30)) | ((centres[:, 1] > .525) & (centres[:, 1] < .585)) | ((centres[:, 1] > .795) & (centres[:, 1] < .87))
        contact = contact_height & (np.abs(centres[:, 0] - .04) < .12) & (centres[:, 2] < -.005) & ~platform
        labels[contact] = 'contact_pads'
        # Main posts, jaw spacings and deck fit the existing 31m shaft. The
        # supplied side service platform folds about its own hinge in transit.
        vertices[:, 0] = (vertices[:, 0] - .04) * 61.44
        vertices[:, 2] = np.where(vertices[:, 2] < 0, vertices[:, 2] * 64, vertices[:, 2] * 38) + 5
        knots = np.array([-.001, .08, .26, .55, .82, .981])
        heights = np.array([-2.2, 0, 20, 37, 53.5, 61])
        slopes = np.diff(heights) / np.diff(knots)
        bands = np.clip(np.searchsorted(knots, source['vertices'][:, 1], side='right') - 1, 0, len(slopes) - 1)
        sy = slopes[bands]
        sz = np.where(source['vertices'][:, 2] < 0, 64., 38.)
        vertices[:, 1] = np.interp(source['vertices'][:, 1], knots, heights)
        normals /= np.stack([np.full(len(vertices), 61.44), sy, sz], axis=1)[faces]
        anchors['service_platform'] = [(-.171 - .04) * 61.44, float(np.interp(.590, knots, heights)), .045 * 38 + 5]
    normals /= np.maximum(np.linalg.norm(normals, axis=2, keepdims=True), 1e-12)
    encoded = np.concatenate([vertices[faces], uv, normals], axis=2)
    parts = {label: np.round(encoded[labels == label], 6).ravel().tolist() for label in sorted(set(labels))}
    doc = dict(format_version=1, stride=8, units='blocks', texture=f'projectseele:textures/entity/tripo_{name}_r48.png',
               source='User supplied GLB; original master retained; UVs and material preserved',
               parts=parts, anchors=anchors, triangles=len(faces),
               bounds=[vertices.min(0).tolist(), vertices.max(0).tolist()])
    target = ASSETS / 'mesh'; target.mkdir(parents=True, exist_ok=True)
    (target / f'tripo_{name}_r48.json').write_text(json.dumps(doc, separators=(',', ':')), 'utf8')
    dims = textures(name)
    np.savez_compressed(PIPE / name / 'game_geometry.npz', vertices=vertices, triangles=faces, labels=labels.astype(str))
    receipt = dict(parts={key: len(value) // 24 for key, value in parts.items()}, anchors=anchors,
                   texture_size=dims, bounds=doc['bounds'], game_render_unverified=True)
    (PIPE / name / 'game_export.json').write_text(json.dumps(receipt, indent=2), 'utf8')
    print(name, json.dumps(receipt), flush=True)


if __name__ == '__main__':
    for asset in ('gripper', 'carrier'): export(asset)

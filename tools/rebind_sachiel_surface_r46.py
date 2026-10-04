"""Rebind a byte-bound surface only after proving rendered mesh data are identical."""
from pathlib import Path
import argparse, hashlib, json, struct


def sha(data): return hashlib.sha256(data).hexdigest()


def rebind(original_mesh, delivery_mesh, surface, movie):
    original = original_mesh.read_bytes()
    selected = delivery_mesh.read_bytes()
    a, b = json.loads(original), json.loads(selected)
    # Provenance is the only permitted difference. No topology/weight/UV bypass.
    a.pop('provenance', None); b.pop('provenance', None)
    if a != b: raise ValueError('Rendered mesh data changed: regenerate surface instead')
    binary = surface.read_bytes()
    if len(binary) < 60 or struct.unpack('>I', binary[:4])[0] != 0x53573134:
        raise ValueError('Invalid surface header')
    if binary[28:60].hex() != sha(original): raise ValueError('Source mesh is not bound surface source')
    clip = json.loads(movie.read_bytes())
    if clip.get('surface_deformation_r14') != sha(binary): raise ValueError('Movie is not bound surface source')
    result = binary[:28] + bytes.fromhex(sha(selected)) + binary[60:]
    clip['surface_deformation_r14'] = sha(result)
    return result, clip, dict(source_mesh_sha256=sha(original), delivery_mesh_sha256=sha(selected),
        source_surface_sha256=sha(binary), delivery_surface_sha256=sha(result),
        geometry_uv_weights_unchanged=True, deformation_frames_unchanged=binary[60:]==result[60:])


def main():
    p=argparse.ArgumentParser()
    for key in ('original-mesh','delivery-mesh','surface','movie','out'): p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args(); result,clip,receipt=rebind(a.original_mesh,a.delivery_mesh,a.surface,a.movie)
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/a.surface.name).write_bytes(result)
    (a.out/a.movie.name).write_text(json.dumps(clip,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (a.out/'surface_binding_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))

if __name__=='__main__': main()

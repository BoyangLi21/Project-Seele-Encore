"""Convert owner-supplied glTF PBR channels without resampling or repainting.

glTF: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
LabPBR: https://shaderlabs.org/wiki/LabPBR_Material_Standard
"""
import argparse
import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image


def normal_channels(source, scale=1.0):
    result = np.asarray(source.convert("RGBA")).copy()
    if scale != 1.0:
        normal = result[:, :, :3].astype(np.float64) / 127.5 - 1
        normal[:, :, :2] *= scale
        normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-12)
        result[:, :, :2] = np.rint((normal[:, :, :2] + 1) * 127.5).clip(0, 255)
    # glTF uses +Y tangent normals; LabPBR uses -Y. Its B/A are AO/height.
    result[:, :, 1] = 255 - result[:, :, 1]
    result[:, :, 2:] = 255
    return Image.fromarray(result)


def specular_channels(source, metallic_factor=1.0, roughness_factor=1.0):
    packed = np.asarray(source.convert("RGBA"))
    result = np.zeros_like(packed)
    roughness = packed[:, :, 1].astype(np.float64) / 255 * roughness_factor
    result[:, :, 0] = np.rint(255 * (1 - roughness.clip(0, 1)))
    metallic = packed[:, :, 2].astype(np.float64) / 255 * metallic_factor
    # 230 specifically selects iron. 255 uses the source albedo as conductor F0.
    # LabPBR has no continuous metallic mixture; only boundary texels quantize.
    result[:, :, 1] = np.where(metallic >= 0.5, 255, 10)
    result[:, :, 3] = 255
    return Image.fromarray(result)


def convert(source, output, name):
    raw = source.read_bytes()
    if raw[:4] != b"glTF":
        raise ValueError("Expected a binary glTF")
    length, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A:
        raise ValueError("Missing JSON chunk")
    document = json.loads(raw[20:20 + length])
    binary = 28 + length
    if len(document["materials"]) != 1:
        raise ValueError("Use separate material exports for multi-material input")
    material = document["materials"][0]
    pbr = material["pbrMetallicRoughness"]

    def image(texture):
        if texture.get("texCoord", 0) != 0 or texture.get("extensions"):
            raise ValueError("Texture transform requires explicit UV handling")
        record = document["images"][document["textures"][texture["index"]]["source"]]
        view = document["bufferViews"][record["bufferView"]]
        offset = binary + view.get("byteOffset", 0)
        return Image.open(io.BytesIO(raw[offset:offset + view["byteLength"]]))

    output.mkdir(parents=True, exist_ok=True)
    files = []
    if "normalTexture" in material:
        normal = material["normalTexture"]
        target = output / (name + "_n.png")
        normal_channels(image(normal), normal.get("scale", 1)).save(target)
        files.append(str(target))
    if "metallicRoughnessTexture" in pbr:
        target = output / (name + "_s.png")
        specular_channels(image(pbr["metallicRoughnessTexture"]),
                          pbr.get("metallicFactor", 1),
                          pbr.get("roughnessFactor", 1)).save(target)
        files.append(str(target))
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.out, args.name)))

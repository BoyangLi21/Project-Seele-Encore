#!/usr/bin/env python3
"""Convert Kiki's Lilith GLB into Project SEELE's mesh layers.

The source artwork is never copied into the public mod resources or Git. The
output lives in the ignored eva_real_model resource pack. The model is CC BY
4.0 and the owner approved shipping it with credit on 2026-11-18; every
release that carries it must show ATTRIBUTION (see docs/ASSETS.md).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile


REPO = Path(__file__).resolve().parent.parent
DEFAULT_ARCHIVE = REPO / "external-assets/incoming/lilith-kiki260100.zip.zip"
WORK_GLB = REPO / "external-assets/work/lilith/kiki/source/lilith_-_evangelion.glb"
DEFAULT_OUTPUT = REPO / "run/resourcepacks/eva_real_model/assets/projectseele"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
EXPORT_VERSION = 1
# The owner approved shipping the converted model with credit on 2026-11-18 ("用 Kiki 署名"). The source is CC BY 4.0;
# the mesh and textures still stay out of Git (size) and travel in the release's private asset pack.
RELEASE_APPROVED_ON = "2026-11-18"
LICENSE = "CC-BY-4.0"
ATTRIBUTION = ("\"Lilith - Evangelion\" by kiki260100 "
               "(https://sketchfab.com/3d-models/lilith-evangelion-8203459ac3dc48e18bad7b2a6b46995f), "
               "licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); "
               "converted into mesh layers for Project SEELE, the cross material removed.")

LAYER_FOR_MATERIAL = {
    "m_lilith": "lilith_body",
    "lambert1": "lilith_body",
    "blinn5": "lilith_face_dark",
    "blinn7": "lilith_mask",
    "blinn8": "lilith_nails",
    "m_longinus": "lilith_spear",
    "m_ojos": "lilith_eyes",
}

SOLID_COLOURS = {
    "lilith_body": (0.92, 0.90, 0.84, 1.0),
    "lilith_face_dark": (0.018, 0.007, 0.028, 1.0),
    "lilith_nails": (0.10, 0.10, 0.11, 1.0),
    "lilith_spear": (0.36, 0.005, 0.008, 1.0),
    "lilith_eyes": (0.004, 0.004, 0.004, 1.0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_glb() -> Path:
    if WORK_GLB.is_file():
        return WORK_GLB
    if not DEFAULT_ARCHIVE.is_file():
        raise SystemExit(f"Lilith source archive not found: {DEFAULT_ARCHIVE}")
    WORK_GLB.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(DEFAULT_ARCHIVE) as archive:
        candidates = [name for name in archive.namelist()
                      if name.lower().endswith(".glb")]
        if len(candidates) != 1:
            raise SystemExit(f"Expected one GLB in {DEFAULT_ARCHIVE}, found {candidates}")
        WORK_GLB.write_bytes(archive.read(candidates[0]))
    return WORK_GLB


def output_is_current(output: Path, source_hash: str) -> bool:
    manifest = output / "mesh/lilith-local.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    required = [
        output / "mesh" / f"{layer}.mesh.json"
        for layer in sorted(set(LAYER_FOR_MATERIAL.values()))
    ] + [
        output / "textures/entity" / f"{layer}.png"
        for layer in sorted(set(LAYER_FOR_MATERIAL.values()))
    ]
    return (data.get("export_version") == EXPORT_VERSION
            and data.get("source_sha256") == source_hash
            and all(path.is_file() and path.stat().st_size > 0 for path in required))


def run_blender(source: Path, output: Path) -> None:
    blender = Path(os.environ.get("BLENDER", str(BLENDER)))
    if not blender.is_file():
        raise SystemExit(f"Blender executable not found: {blender}")
    command = [str(blender), "--background", "--python", str(Path(__file__).resolve()),
               "--", "--blender-export", str(source), str(output)]
    subprocess.run(command, cwd=REPO, check=True)


def normal_main() -> None:
    source = find_glb()
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT
    source_hash = sha256(source)
    if output_is_current(output, source_hash):
        print(f"Lilith local model is current: {output}")
        return
    run_blender(source, output)
    if not output_is_current(output, source_hash):
        raise SystemExit("Lilith Blender export did not produce a valid local manifest")
    source_note = output.parent.parent / "LILITH_SOURCE.txt"
    source_note.write_text(
        "Lilith - Evangelion by Kiki260100 (Sketchfab).\n"
        "Local evaluation only; redistribution/release approval pending.\n"
        f"Source SHA-256: {source_hash}\n",
        encoding="utf-8")
    print(f"Built Kiki Lilith local resource layers: {output}")


def save_solid_texture(bpy, path: Path, colour: tuple[float, float, float, float]) -> None:
    image = bpy.data.images.new("seele_" + path.stem, width=2, height=2, alpha=True)
    image.pixels = list(colour) * 4
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def save_mask_texture(bpy, path: Path) -> None:
    material = bpy.data.materials.get("blinn7")
    image = None
    if material is not None and material.use_nodes:
        for node in material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                image = node.image
                break
    if image is None:
        raise RuntimeError("Kiki mask texture Image_1 was not found")
    bpy.context.scene.render.image_settings.file_format = "PNG"
    image.save_render(str(path), scene=bpy.context.scene)


def blender_export(source: Path, output: Path) -> None:
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    body_objects = [obj for obj in objects
                    if any(slot.material and slot.material.name in LAYER_FOR_MATERIAL
                           for slot in obj.material_slots)]
    if not body_objects:
        raise RuntimeError("No supported Lilith mesh objects were imported")

    points = [obj.matrix_world @ vertex.co
              for obj in body_objects for vertex in obj.data.vertices]
    minimum_up = min(point.z for point in points)
    maximum_up = max(point.z for point in points)
    # Kiki's body is 515 source units tall. Thirty-two Minecraft blocks keep
    # the wrists inside the 48-block Terminal Dogma containment chamber.
    blocks_per_source_unit = 32.0 / (maximum_up - minimum_up)
    pixels_per_source_unit = blocks_per_source_unit * 16.0

    layers: dict[str, list[float]] = {
        name: [] for name in sorted(set(LAYER_FOR_MATERIAL.values()))
    }
    triangles = {name: 0 for name in layers}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in body_objects:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        mesh.calc_loop_triangles()
        uv_layer = mesh.uv_layers.active.data if mesh.uv_layers.active else None
        normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
        materials = [slot.material.name if slot.material else ""
                     for slot in obj.material_slots]
        for triangle in mesh.loop_triangles:
            material = (materials[triangle.material_index]
                        if triangle.material_index < len(materials) else "")
            layer = LAYER_FOR_MATERIAL.get(material)
            if layer is None:
                continue
            world_normal = (normal_matrix @ triangle.normal).normalized()
            # Values compensate LocalTriangleMeshLayer's Bedrock X reflection.
            normal = (-world_normal.x, world_normal.z, -world_normal.y)
            for loop_index in triangle.loops:
                loop = mesh.loops[loop_index]
                world = obj.matrix_world @ mesh.vertices[loop.vertex_index].co
                uv = uv_layer[loop_index].uv if uv_layer else (0.0, 0.0)
                layers[layer].extend((
                    round(-world.x * pixels_per_source_unit, 5),
                    round((world.z - minimum_up) * pixels_per_source_unit, 5),
                    round(-world.y * pixels_per_source_unit, 5),
                    round(float(uv[0]), 6), round(1.0 - float(uv[1]), 6),
                    round(normal[0], 5), round(normal[1], 5), round(normal[2], 5),
                ))
            triangles[layer] += 1
        evaluated.to_mesh_clear()

    mesh_dir = output / "mesh"
    texture_dir = output / "textures/entity"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)
    for layer, values in layers.items():
        if not values:
            raise RuntimeError(f"No triangles exported for {layer}")
        payload = {
            "format_version": 1,
            "source": "Kiki260100 Lilith - Sketchfab",
            "local_only": True,
            "release_approved": True,
            "license": LICENSE,
            "attribution": ATTRIBUTION,
            "model_height_blocks": 32.0,
            "stride": 8,
            "parts": {"root": {"pivot": [0.0, 0.0, 0.0], "vertices": values}},
            "triangle_count": triangles[layer],
        }
        (mesh_dir / f"{layer}.mesh.json").write_text(
            json.dumps(payload, separators=(",", ":")), encoding="utf-8")

    for layer, colour in SOLID_COLOURS.items():
        save_solid_texture(bpy, texture_dir / f"{layer}.png", colour)
    save_mask_texture(bpy, texture_dir / "lilith_mask.png")

    source_hash = sha256(source)
    manifest = {
        "export_version": EXPORT_VERSION,
        "source_sha256": source_hash,
        "source": "Kiki260100 Lilith - Evangelion",
        "local_only": True,
        "release_approved": True,
        "release_approved_on": RELEASE_APPROVED_ON,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "height_blocks": 32.0,
        "layers": triangles,
        "excluded_materials": ["blinn6 (cross; Project SEELE uses its red block crucifix)"],
    }
    (mesh_dir / "lilith-local.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("LILITH_EXPORT", json.dumps(manifest, sort_keys=True))


def blender_arguments() -> tuple[Path, Path] | None:
    if "--" not in sys.argv:
        return None
    arguments = sys.argv[sys.argv.index("--") + 1:]
    if len(arguments) == 3 and arguments[0] == "--blender-export":
        return Path(arguments[1]).resolve(), Path(arguments[2]).resolve()
    return None


if __name__ == "__main__":
    blender_args = blender_arguments()
    if blender_args is None:
        normal_main()
    else:
        blender_export(*blender_args)

"""Run in Blender background mode with -- SOURCE_ZIP OUTPUT_NPZ."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import bpy
import numpy as np


def convert(archive, output):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with TemporaryDirectory() as temp, ZipFile(archive) as source:
        models = [
            entry for entry in source.namelist() if entry.lower().endswith(".fbx")
        ]
        if len(models) != 1:
            raise ValueError("Expected the supplied single FBX scene")
        path = Path(temp) / "collector.fbx"
        path.write_bytes(source.read(models[0]))
        bpy.ops.import_scene.fbx(filepath=str(path))
    points, normals, faces, materials = [], [], [], []
    names = []
    start = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        mesh.calc_loop_triangles()
        transform = obj.matrix_world
        normal_matrix = transform.to_3x3().inverted().transposed()
        points.extend([tuple(transform @ v.co) for v in mesh.vertices])
        normals.extend(
            [tuple((normal_matrix @ v.normal).normalized()) for v in mesh.vertices]
        )
        faces.extend(
            [tuple(start + i for i in t.vertices) for t in mesh.loop_triangles]
        )
        materials.extend([len(names) + t.material_index for t in mesh.loop_triangles])
        names.extend([material.name for material in mesh.materials] or ["hull"])
        start += len(mesh.vertices)
    np.savez(output, v=points, n=normals, f=faces, m=materials, names=names)


if __name__ == "__main__":
    archive, output = sys.argv[sys.argv.index("--") + 1 :]
    convert(archive, output)

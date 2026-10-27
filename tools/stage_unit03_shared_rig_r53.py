"""Stage Unit-03 geometry, motion, and physical profiles without installing them."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import shutil
import zipfile

import numpy as np
from scipy.spatial import ConvexHull


def read(path):
    return json.loads(path.read_text("utf8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), "utf8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Use a fresh stage directory")
    assets = args.out / "assets/projectseele"
    shutil.copytree(args.candidate / "assets/projectseele", assets)
    source = args.client / "projectseele-local-maps"
    runtime = args.out / "projectseele-local-maps"
    runtime.mkdir()
    mesh = read(assets / "mesh/eva_un01.mesh.json")
    geo = read(assets / "geo/eva_un01.geo.json")
    bones = geo["minecraft:geometry"][0]["bones"]
    bones.append(dict(name="unit03_shared_unit01_r53", parent="root", pivot=[0, 0, 0]))
    write(assets / "geo/eva_un01.geo.json", geo)
    by_name = {b["name"]: b for b in bones}

    with zipfile.ZipFile(args.client / "mods/projectseele-0.1.0-all.jar") as jar:
        animation = jar.read("assets/projectseele/animations/eva_unit01.animation.json")
    (assets / "animations").mkdir(exist_ok=True)
    (assets / "animations/eva_un01.animation.json").write_bytes(animation)

    body = read(source / "eva_body_r44.json")
    body["rigs"]["4"] = [{k: v for k, v in b.items()
                          if k in ("name", "parent", "pivot", "rotation")} for b in bones]
    support = {}
    carrier = []
    for name, part in mesh["parts"].items():
        values = np.asarray(part["vertices"]).reshape(-1, 8)
        points = np.unique(((values[:, :3] + part["pivot"]) * [-1, 1, 1]).round(6), axis=0)
        if len(points) < 4:
            continue
        hull = ConvexHull(points)
        support[name] = points[hull.vertices].tolist()
        world = points * (5 / 16)
        carrier.append(np.concatenate((world.min(0), world.max(0))).round(6).tolist())
    body["rig_support"]["4"] = support
    body["carrier_hulls"]["4"] = carrier
    head = np.asarray(mesh["parts"]["head"]["vertices"]).reshape(-1, 8)
    head = (head[:, :3] + mesh["parts"]["head"]["pivot"]) * [-1, 1, 1]
    eye = head[(abs(head[:, 0]) < 5) & (head[:, 1] > 162) & (head[:, 1] < 175)]
    body["eye_positions"]["4"] = [0, float(np.median(eye[:, 1])), float(np.quantile(eye[:, 2], .05))]
    body["stance_clips_by_rig"]["4"] = copy.deepcopy(body["stance_clips_by_rig"]["1"])
    body["locomotion_contract_r43"]["4"] = copy.deepcopy(body["locomotion_contract_r43"]["1"])
    body["unit03_shared_r53"] = dict(source_rig=1, destination_rig=4,
                                    entity_serial=1, entity_progress_changed=False)
    write(runtime / "eva_body_r44.json", body)

    gameplay = read(source / "eva_gameplay_r44_1.json")
    gameplay["rig_key"] = 4
    gameplay["rig_contract_r44"] = body["rigs"]["4"]
    gameplay["unit03_shared_r53"] = dict(source_sha256=sha(source / "eva_gameplay_r44_1.json"),
                                        source_rig=1)
    write(runtime / "eva_gameplay_r44_4.json", gameplay)

    physics = read(source / "articulated_bodies_r35.json")
    physical = copy.deepcopy(physics["models"]["1"])
    physical["render_rig"] = body["rigs"]["4"]
    groups = {row["name"]: [] for row in physical["bodies"]}
    for name, points in support.items():
        owner = name
        while owner not in groups and owner in by_name:
            owner = by_name[owner].get("parent")
        if owner in groups:
            groups[owner].extend(points)
    for row in physical["bodies"]:
        points = np.unique(np.asarray(groups[row["name"]]).round(6), axis=0) * .0125
        if len(points) < 4:
            raise ValueError("Missing measured physical surface: " + row["name"])
        bind = np.asarray(row["bind"]).reshape(4, 4)
        local = (np.linalg.inv(bind) @ np.column_stack((points, np.ones(len(points)))).T).T[:, :3]
        hull = ConvexHull(local)
        row["hulls"] = [local[hull.vertices].round(7).tolist()]
        row["hull_planes"] = [np.unique(hull.equations.round(7), axis=0).tolist()]
        row["size"] = np.maximum(abs(local.min(0)), abs(local.max(0))).round(7).tolist()
    physics["models"]["4"] = physical
    write(runtime / "articulated_bodies_r35.json", physics)

    if (args.candidate / "dorsal-profile.json").exists():
        dorsal = read(source / "eva_dorsal_r30.json")
        dorsal["profiles"]["eva_un01"] = read(args.candidate / "dorsal-profile.json")
        write(runtime / "eva_dorsal_r30.json", dorsal)

    manifest = read(source / "combat_bundle_r44.json")
    manifest["bundle_id"] += "-unit03-shared-r53"
    for file in runtime.iterdir():
        manifest["files"][file.name] = sha(file)
    write(runtime / "combat_bundle_r44.json", manifest)
    contract = dict(schema="projectseele.unit03-shared-r53.v1", rig_key=4,
                    triangles=mesh["triangleCount"], parts=len(mesh["parts"]),
                    resources={role: sha(assets / name) for role, name in {
                        "mesh": "mesh/eva_un01.mesh.json",
                        "geo": "geo/eva_un01.geo.json",
                        "animation": "animations/eva_un01.animation.json",
                        "texture": "textures/entity/eva_un01.png"}.items()},
                    additional_resources={name: sha(assets / name) for name in (
                        "mesh/eva_un01_anatomical_hands_r53.mesh.json",
                        "textures/entity/eva_un01_eyes.png")})
    write(assets / "eva/unit03_shared_r53.json", contract)
    write(args.out / "STAGE_RECEIPT.json", dict(
        status="Candidate only; dorsal integration and native review still required",
        unchanged_entity_slot="EvaPrototypeEntity, UNSerial=1, rig=4",
        new_body_triangles=mesh["triangleCount"], gameplay_clips=len(gameplay["clips"]),
        physics_bodies=len(physical["bodies"]),
        source_files={name: sha(source / name) for name in (
            "eva_body_r44.json", "eva_gameplay_r44_1.json", "articulated_bodies_r35.json",
            "combat_bundle_r44.json")},
        changes={str(p.relative_to(args.out)): sha(p) for p in args.out.rglob("*") if p.is_file()},
        world_written=False))
    print(json.dumps(dict(out=str(args.out), clips=len(gameplay["clips"]), bones=len(bones))))


if __name__ == "__main__":
    main()

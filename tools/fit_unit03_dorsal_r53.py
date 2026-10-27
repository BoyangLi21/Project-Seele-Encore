"""Fit a measured capsule receiver to the private Unit-03 candidate."""
from pathlib import Path
import argparse
import json
import shutil

import numpy as np
from PIL import Image

from fit_un_dorsal_r21 import fit
from stage_unit03_shared_rig_r53 import read, write


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Use a fresh candidate directory")
    shutil.copytree(args.candidate / "assets", args.out / "assets")
    assets = args.out / "assets/projectseele"
    source = args.out / "receiver-source"
    target = args.out / "receiver-result"
    mesh = read(assets / "mesh/eva_un01.mesh.json")
    geo = read(assets / "geo/eva_un01.geo.json")
    geo["minecraft:geometry"][0]["bones"] = [
        b for b in geo["minecraft:geometry"][0]["bones"]
        if b["name"] not in ("dorsal_cover", "dorsal_liner")]
    write(source / "mesh/eva_prototype.mesh.json", mesh)
    write(source / "geo/eva_prototype.geo.json", geo)
    # The ray starts inside the actual upper back and locates its outer skin.
    # These are model-space landmarks, unrelated to map placement.
    frame = dict(centre=[0, 162, 12], outward=[0, .90587519, .42354474])
    fit(source, target, frame, args.out / "receiver-fit.json", "01")
    fitted = read(target / "mesh/eva_prototype.mesh.json")
    fitted_geo = read(target / "geo/eva_prototype.geo.json")
    image = np.asarray(Image.open(assets / "textures/entity/eva_un01.png").convert("RGB"))
    palette = np.array([[46, 53, 73], [9, 13, 19], [137, 37, 44],
                        [111, 118, 131], [164, 174, 186], [18, 20, 28]])
    pixels = image.reshape(-1, 3).astype(float)
    uv = []
    for colour in palette:
        index = np.square(pixels-colour).sum(1).argmin()
        y, x = divmod(int(index), image.shape[1])
        uv.append([(x+.5)/image.shape[1], (y+.5)/image.shape[0]])
    for name in ("dorsal_cover", "dorsal_liner"):
        part = fitted["parts"][name]
        values = np.asarray(part["vertices"]).reshape(-1, 8)
        colour = np.minimum(5, (values[:, 3]*4).astype(int) + 4*(values[:, 4]*3).astype(int))
        values[:, 3:5] = np.asarray(uv)[colour]
        part["vertices"] = values.ravel().tolist()
    write(assets / "mesh/eva_un01.mesh.json", fitted)
    write(assets / "geo/eva_un01.geo.json", fitted_geo)
    write(args.out / "dorsal-profile.json", {
        k: v for k, v in fitted["r13_dorsal_socket"].items() if k != "radius_model"})
    report = read(args.out / "receiver-fit.json")
    report["status"] = "Candidate; closed/open rear views and native capsule passage still required"
    write(args.out / "receiver-fit.json", report)
    print(json.dumps(dict(out=str(args.out), centre=report["frame"]["centre"],
                          triangles=fitted["triangleCount"])))


if __name__ == "__main__":
    main()

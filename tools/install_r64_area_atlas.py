"""Install the GeoFront map resource pack from pre-rendered, world-specific layers in an offline client."""
import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED


PACK = "SEELE_GeoFront_Area_Maps.zip"
ROOT = "assets/projectseele/area_maps/"


def set_selected(client):
    path = client / "options.txt"
    lines = path.read_bytes().splitlines(keepends=True)
    rows = [i for i, line in enumerate(lines) if line.startswith(b"resourcePacks:")]
    if len(rows) != 1:
        raise ValueError("Expected the review client's resourcePacks setting")
    i = rows[0]
    original = lines[i].rstrip(b"\r\n")
    packs = json.loads(original.split(b":", 1)[1])
    name = "file/" + PACK
    if name in packs:
        return
    packs.append(name)
    lines[i] = b"resourcePacks:" + json.dumps(packs, separators=(",", ":")).encode() + lines[i][len(original):]
    with NamedTemporaryFile(dir=client, delete=False) as f:
        f.writelines(lines)
        temp = Path(f.name)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def install(stage, client):
    directory = stage / ROOT
    index = json.loads((directory / "index.json").read_bytes())
    layers = index["layers"]
    if index["schema"] != 1 or index["dimension"] != "projectseele:geofront":
        raise ValueError("Unsupported map projection")
    ids = {layer["id"] for layer in layers}
    if len(ids) != len(layers) or not {"surface", "geofront"} <= ids:
        raise ValueError("Duplicate or missing map layer")
    files = {"index.json"}
    for layer in layers:
        for key in ("texture", "preview", "mask", "bottom", "ceiling", "ground"):
            if key not in layer:
                continue
            head, sep, filename = layer[key].rpartition("/")
            if head != "projectseele:area_maps" or not sep or not filename.endswith(".png") or "\\" in filename:
                raise ValueError(f"Unexpected atlas resource {layer[key]}")
            files.add(filename)
    destination = client / "resourcepacks" / PACK
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        with ZipFile(temp, "w") as zipped:
            metadata = {"pack": {"pack_format": 15, "description": "Project SEELE · GeoFront 区域地图"}}
            zipped.writestr("pack.mcmeta", json.dumps(metadata, ensure_ascii=False).encode("utf8"), ZIP_DEFLATED)
            for name in sorted(files):
                zipped.write(directory / name, ROOT + name)
        with ZipFile(temp) as zipped:
            for name in files:
                if zipped.read(ROOT + name) != (directory / name).read_bytes():
                    raise ValueError(f"Atlas readback failed for {name}")
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    set_selected(client)
    return dict(pack=str(destination), layers=len(layers), images=len(files) - 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.stage, args.client)))

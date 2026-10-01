"""Read the actually selected texture/shader sources; never edit pack images."""
from pathlib import Path
from io import BytesIO
import hashlib
import json
import zipfile

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/rebuild_r44/city_expansion/misato_material_root_cause_v1"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resource = ROOT / "run/resourcepacks/rotrblocks-v87-128x-2d.zip"
    shader = ROOT / "artifacts/rebuild_r44/atmosphere/geofront_shader_v3/ComplementaryUnbound_r5.3_SEELE_R44_GeoFrontCandidate_v3.zip"
    textures = []
    with zipfile.ZipFile(resource) as source:
        for base in ("quartz_block_side", "quartz_block_bottom", "quartz_block_top", "white_concrete", "white_terracotta"):
            for suffix in ("", "_s", "_n"):
                name = f"assets/minecraft/textures/block/{base}{suffix}.png"
                if name not in source.namelist():
                    continue
                raw = source.read(name)
                image = Image.open(BytesIO(raw))
                textures.append(dict(resource=name, sha256=hashlib.sha256(raw).hexdigest(),
                                     size=image.size, mode=image.mode, extrema=image.getextrema(),
                                     mean=ImageStat.Stat(image).mean))
    with zipfile.ZipFile(shader) as source:
        properties = source.read("shaders/block.properties").decode()
        mapping = [line for line in properties.splitlines() if any(
            term in line for term in ("quartz", "white_concrete", "projectseele:nerv", "smooth_sandstone"))]
        quartz = source.read("shaders/lib/materials/specificMaterials/terrain/quartzBlock.glsl").decode()
    record = dict(
        resource_pack=str(resource), resource_sha256=hashlib.sha256(resource.read_bytes()).hexdigest(),
        shader_pack=str(shader), shader_sha256=hashlib.sha256(shader.read_bytes()).hexdigest(),
        native_photo_epoch="space_photos/installed_school_v22_and_misato_v13/20261001_184116",
        actual_diffuse_and_pbr_channels=textures, actual_block_mapping=mapping, actual_quartz_code=quartz,
        first_error="Polished quartz was assigned to residential wall/ceiling plaster in the scene producer.",
        evidence="Diffuse alpha is fully opaque; source assigns quartz high smoothness/intense Fresnel. Native walls reflect room/window patterns.",
        qualification="Exact active PBR branch still requires a controlled same-camera A/B. No assertion of transparent geometry.",
        intended_fix="Separate matte residential plaster block and slab; preserve genuine quartz materials elsewhere.",
        reference_urls=["https://shaderlabs.org/wiki/LabPBR_Material_Standard",
                        "https://github.com/ComplementaryDevelopment/ComplementaryReimagined/blob/main/shaders/block.properties"],
        installed=False,
    )
    (OUT / "actual_material_sources.json").write_text(json.dumps(record, indent=2), encoding="utf8")
    for row in textures:
        if not row["resource"].endswith("_n.png"):
            print(row["resource"].split("/")[-1], "means", [round(x, 2) for x in row["mean"]], "range", row["extrema"])
    print("Actual mappings:", *mapping, sep="\n")
    print(OUT / "actual_material_sources.json")


if __name__ == "__main__":
    main()

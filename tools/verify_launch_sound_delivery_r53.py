"""Read the selected/deployed JAR's exact current launch catalog and original Oggs."""
from __future__ import annotations
import argparse, hashlib, json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = {"launch_electric_burst_r53", "launch_rail_friction_r53"}
OGGS = ("launch_electric_burst_r53", "launch_rail_friction_r53_0", "launch_rail_friction_r53_1", "launch_rail_friction_r53_2")
sha = lambda data: hashlib.sha256(data).hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--jar", type=Path, required=True)
    ap.add_argument("--before-jar", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists(): raise ValueError("Fresh external receipt required")
    if any((p / "level.dat").exists() or (p / "session.lock").exists() for p in (out, *out.parents)):
        raise ValueError("Receipt inside World")
    source_path = ROOT / "src/main/resources/assets/projectseele/sounds.json"
    source_bytes = source_path.read_bytes(); source = json.loads(source_bytes)
    with zipfile.ZipFile(args.before_jar) as z: before = json.loads(z.read("assets/projectseele/sounds.json"))
    assert len(before) == 88 and len(source) == 90 and set(source) - set(before) == EVENTS and not set(before) - set(source)
    assert all(source[k] == before[k] for k in before), "Original88 sound definitions changed"
    rows = []
    with zipfile.ZipFile(args.jar) as z:
        delivered_bytes = z.read("assets/projectseele/sounds.json"); delivered = json.loads(delivered_bytes)
        assert delivered == source, "Selected JAR lacks exact current90 sound definitions"
        assert delivered_bytes == source_bytes, "Catalog bytes differ from frozen current Source"
        registry = z.read("com/projectseele/registry/ModSounds.class")
        assert all(name.encode("ascii") in registry for name in EVENTS), "Registered launch events absent from actual class"
        for name in OGGS:
            member = "assets/projectseele/sounds/" + name + ".ogg"; data = z.read(member)
            assert data == (ROOT / "src/main/resources" / member).read_bytes(), "Original synthesized Ogg bytes changed"
            assert data[:4] == b"OggS" and b"\x01vorbis" in data, "Actual Ogg/Vorbis headers absent"
            rows.append(dict(member=member, bytes=len(data), sha256=sha(data)))
        captions = {}
        for lang in ("en_us", "zh_cn"):
            table = json.loads(z.read("assets/projectseele/lang/" + lang + ".json"))
            captions[lang] = {"subtitles.projectseele." + event: table.get("subtitles.projectseele." + event) for event in sorted(EVENTS)}
    report = dict(passed=True, jar=str(args.jar.resolve()), jar_sha256=sha(args.jar.read_bytes()), source_catalog_sha256=sha(source_bytes),
                  original_definitions_unchanged=88, exact_current_definitions=90, exact_added_events=sorted(EVENTS), oggs=rows,
                  subtitle_translations_observed=captions, world_written=False, source_modified=False,
                  native_sound_resource_reload_or_actual_playback_pass=False,
                  scope="Exact actual JAR packaging readback only. Real client resource reload and committed launch audio playback remain native checks.")
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "events": 90, "original_unchanged": 88, "ogg_files": len(rows), "receipt": str(out)}))

if __name__ == "__main__": main()

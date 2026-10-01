"""Compile only explicitly frozen Java candidates against the current built game.

Other workers may edit unrelated sources. No shared build output is replaced.
The native review tools overlay these classes on a frozen complete baseline.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
JAVAC = Path("C:/Users/liboy/jdks/jdk-17.0.19+10/bin/javac.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("freeze", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    from release_combat_r36 import guard
    guard()
    assert not args.output.exists(), "Use a fresh immutable compile directory"
    doc = json.loads(args.freeze.read_text(encoding="utf8"))
    rows = [r for r in doc["files"] if r["path"].endswith(".java")]
    assert rows
    args.output.mkdir(parents=True)
    sources = args.output / "sources"
    classes = args.output / "classes"
    classes.mkdir()
    files = []
    for row in rows:
        source = Path(row["path"])
        assert sha(source) == row["sha256"], ("Source changed after freeze", source)
        relative = source.resolve().relative_to((ROOT / "src/main/java").resolve())
        target = sources / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append(target)
    cp_file = ROOT / "build/classpath/runClient_minecraftClasspath.txt"
    jars = cp_file.read_text(encoding="utf8").replace(";", "\n").splitlines()
    properties = (ROOT / "gradle.properties").read_text(encoding="utf8")
    gecko_version = re.search(r"(?m)^geckolib_version=(.+)$", properties).group(1).strip()
    minecraft_version = re.search(r"(?m)^minecraft_version=(.+)$", properties).group(1).strip()
    gradle_cache = Path(os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle"))) / "caches/forge_gradle/deobf_dependencies"
    gecko = gradle_cache / f"software/bernie/geckolib/geckolib-forge-{minecraft_version}/{gecko_version}_mapped_official_{minecraft_version}/geckolib-forge-{minecraft_version}-{gecko_version}_mapped_official_{minecraft_version}.jar"
    assert gecko.is_file(), f"Pinned mapped GeckoLib compile dependency missing: {gecko}"
    classpath = os.pathsep.join([str(ROOT / "build/classes/java/main"), str(gecko), *[p for p in jars if p.strip()]])
    command = ["-encoding", "UTF-8", "-source", "17", "-target", "17", "-proc:none", "-implicit:none",
               "-classpath", classpath, "-sourcepath", str(sources.resolve()), "-d", str(classes.resolve()),
               *[str(p.resolve()) for p in files]]
    argfile = args.output / "javac.args"
    argfile.write_text("\n".join('"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"' for value in command), encoding="utf8")
    compiled = subprocess.run([str(JAVAC), "-J-Duser.language=en", "-J-Dfile.encoding=UTF-8", "@" + str(argfile.resolve())], cwd=ROOT, capture_output=True)
    (args.output / "javac_stdout.bin").write_bytes(compiled.stdout)
    (args.output / "javac_stderr.bin").write_bytes(compiled.stderr)
    diagnostic = (compiled.stdout + compiled.stderr).decode("utf8", errors="replace")
    (args.output / "javac.log").write_text(diagnostic, encoding="utf8")
    receipt = dict(frozen_source=str(args.freeze.resolve()), freeze_sha256=sha(args.freeze), sources=rows,
                   base_classes=str(ROOT / "build/classes/java/main"), classpath_sha256=sha(cp_file),
                   extra_dependencies=[dict(path=str(gecko),sha256=sha(gecko))],
                   result=compiled.returncode, shared_classes_written=False,
                   produced={p.relative_to(classes).as_posix():sha(p) for p in classes.rglob("*.class")})
    (args.output / "compile_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
    print("Frozen Java files:", len(files), "output classes:", len(receipt["produced"]), "exit:", compiled.returncode)
    if compiled.returncode:
        print(diagnostic[-9000:])
    raise SystemExit(compiled.returncode)


if __name__ == "__main__":
    main()

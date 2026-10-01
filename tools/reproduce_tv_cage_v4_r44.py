"""Reproduce published v4 with its exact frozen incremental authoring recipe.

Creates an isolated private workspace and uses the frozen complete v3 input
and producer bytes. Does not bake with changed live source or write src/world.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rebuild_r44/hangar_machinery'
FROZEN = BASE / 'v4_reproduction_inputs_de2d938'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out):
    out = Path(out).resolve()
    base = BASE.resolve()
    if out.parent != base or out.exists():
        raise ValueError('Use a fresh private output below artifacts/rebuild_r44/hangar_machinery')
    manifest = json.loads((FROZEN / 'hashes.json').read_text('utf8'))
    for row in manifest['files']:
        if sha(FROZEN / row['relative_path']) != row['sha256']:
            raise ValueError('Frozen input/source drift: ' + row['relative_path'])
    out.mkdir(parents=True, exist_ok=False)
    workspace = out / 'workspace'
    shutil.copytree(FROZEN / 'source', workspace)
    parent = workspace / 'artifacts/rebuild_r44/hangar_machinery/tv_cage_whole_candidate_v3'
    parent.mkdir(parents=True)
    shutil.copyfile(FROZEN / 'inputs/v3_af2f2657.json', parent / 'tv_shoulder_shells_r44.json')
    result = subprocess.run([sys.executable, str(workspace / 'tools/refine_tv_aprons_r44.py')],
                            cwd=workspace, capture_output=True, text=True, check=True)
    generated = parent.parent / 'tv_cage_whole_candidate_v4/tv_shoulder_shells_r44.json'
    if sha(generated) != manifest['expected_v4_sha256']:
        raise ValueError('Exact frozen recipe produced another resource; preserve diagnostics, do not install')
    artifact = out / 'tv_shoulder_shells_r44.json'
    pad = out / 'hangar_shoulder_contacts_r44.json'
    shutil.copyfile(generated, artifact)
    shutil.copyfile(FROZEN / 'inputs/pad_a2e2fb6e.json', pad)
    report = {'cage_sha256': sha(artifact), 'pad_sha256': sha(pad),
              'frozen_manifest_sha256': sha(FROZEN / 'hashes.json'),
              'exact_frozen_v4_reproduction': True, 'producer_stdout': result.stdout.strip(),
              'inputs': 'Frozen complete v3 asset + frozen refine and author bytes. Frozen contact/body retain parent provenance; incremental refinement does not pretend to remeasure them.',
              'installed_src_mutated': False, 'world_write_performed': False,
              'native_passed': False, 'visual_passed': False}
    (out / 'reproduction_receipt.json').write_text(json.dumps(report, indent=2), 'utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Exact private reproduction of frozen de2 v4; fresh output only.')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        main(args.out)
    except (ValueError, FileNotFoundError) as failure:
        parser.error(str(failure))

"""Cold-stage the exact declared bank-edge equipment successor, retaining save data.

Only the owner source entry and its bundle binding change. Native stopped-bank
admission must subsequently accept the backed-up predecessor. This is not a
world-state or entity migration.
"""
import argparse
import copy
import hashlib
import json
import msvcrt
import re
import shutil
from pathlib import Path


def stage(world, backup, apply):
    source = (Path(__file__).resolve().parents[1] /
              'src/main/java/com/projectseele/world/NervLegacyBankClearanceR53.java').read_text('utf8')
    values = {key: re.search(r'\b' + key + r'="([^"]+)"', source).group(1)
              for key in ('SOURCE', 'SOURCE_SHA', 'PREVIOUS_SOURCE_SHA')}
    owner_path, bundle_path = world / 'ROOT_MECHANICAL_OWNER.json', world / 'ROOT_ASSEMBLY_BUNDLE.json'
    with (world / 'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        owner_bytes, bundle_bytes = owner_path.read_bytes(), bundle_path.read_bytes()
        owner, bundle = json.loads(owner_bytes), json.loads(bundle_bytes)
        assert owner['mechanism_sources'][values['SOURCE']] == values['PREVIOUS_SOURCE_SHA'], 'Exact accepted first-bank source required'
        assert bundle['mechanical_owner']['file'] == owner_path.name
        assert hashlib.sha256(owner_bytes).hexdigest() == bundle['mechanical_owner']['sha256']
        next_owner, next_bundle = copy.deepcopy(owner), copy.deepcopy(bundle)
        next_owner['mechanism_sources'][values['SOURCE']] = values['SOURCE_SHA']
        next_owner_bytes = json.dumps(next_owner, separators=(',', ':'), ensure_ascii=False).encode('utf8')
        next_bundle['mechanical_owner']['sha256'] = hashlib.sha256(next_owner_bytes).hexdigest()
        next_bundle_bytes = json.dumps(next_bundle, separators=(',', ':'), ensure_ascii=False).encode('utf8')
        if apply:
            backup.mkdir(parents=True, exist_ok=False)
            shutil.copy2(owner_path, backup / owner_path.name)
            shutil.copy2(bundle_path, backup / bundle_path.name)
            try:
                owner_path.write_bytes(next_owner_bytes)
                bundle_path.write_bytes(next_bundle_bytes)
                assert owner_path.read_bytes() == next_owner_bytes
                assert bundle_path.read_bytes() == next_bundle_bytes
            except BaseException:
                owner_path.write_bytes(owner_bytes)
                bundle_path.write_bytes(bundle_bytes)
                raise
    print(('Staged' if apply else 'Ready to stage') +
          ' one declared equipment source in two metadata files; original world progress untouched.')
    print('Native admission predecessor directory:', backup)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    stage(args.world.resolve(), args.backup.resolve(), args.apply)

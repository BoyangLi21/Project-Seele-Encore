"""Stage an uninstalled source-bound carrier candidate; never edits the selected runtime."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('hardware', 'sole', 'existing_selection', 'existing_jar', 'output'):
        p.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    a = p.parse_args()
    hardware, sole = a.hardware.read_bytes(), a.sole.read_bytes()
    hd, sd = json.loads(hardware), json.loads(sole)
    old = json.loads(a.existing_selection.read_bytes())
    assert hd['schema'] == 'projectseele.r53.rear-guide-hardware.v1'
    assert sd['schema'] == 'projectseele.r53.carrier-sole-bearing.v1'
    assert hd['carrier_sha256'] == sd['carrier_source_sha256']
    dependencies = dict(hd['source_hardware_sha256'])
    dependencies['mesh/carrier_mk2_r53.json'] = hd['carrier_sha256']
    rails = 'facility/r52_upright_guideway_paths.json'
    dependencies[rails] = old['resources'][rails]
    assert dependencies[rails] == old['legacy_upright_sha256']
    with zipfile.ZipFile(a.existing_jar) as jar:
        for resource, expected in dependencies.items():
            assert sha(jar.read('assets/projectseele/' + resource)) == expected, resource
    assert hd['transfer_stow_lift_m'] == 7
    assert hd['candidate_lateral_retraction_m'] == .65
    selected = dict(old)
    selected['resources'] = dict(old['resources'])
    selected['resources']['mesh/carrier_rear_guides_r53.json'] = sha(hardware)
    feet = dict(schema='projectseele.r53.carrier-sole-selection.v1',
                resources={'mesh/carrier_sole_bearings_r53.json': sha(sole)})
    files = {'mesh/carrier_rear_guides_r53.json': hardware,
             'mesh/carrier_sole_bearings_r53.json': sole,
             'eva/carrier_rear_guides_r53_sources.json': (json.dumps(selected, indent=2) + '\n').encode(),
             'eva/carrier_sole_bearings_r53_sources.json': (json.dumps(feet, indent=2) + '\n').encode()}
    output = a.output.resolve()
    assert not output.exists(), 'Use a fresh isolated candidate directory'
    output.mkdir(parents=True)
    resources = {}
    for name, raw in files.items():
        path = output / 'assets/projectseele' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        assert path.read_bytes() == raw
        resources[name] = sha(raw)
    receipt = dict(schema='projectseele.r53.uninstalled-carrier-mount-candidate.v1',
                   installed=False, activated=False, world_written=False,
                   resources=resources, required_unchanged_resources=dependencies,
                   directory_sha256=old['directory_sha256'],
                   missing_integration=['hoist candidate', 'owner controller/payload trajectories',
                                        'source commissioning and continuous migration proof',
                                        'normal native opening/recovery/launch and visual review'])
    raw = (json.dumps(receipt, indent=2) + '\n').encode()
    (output / 'RECEIPT.json').write_bytes(raw)
    print(json.dumps(dict(output=str(output), receipt_sha256=sha(raw), resources=resources)))


if __name__ == '__main__':
    main()

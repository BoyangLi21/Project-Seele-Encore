"""Audit supplied EVA surfaces and stage an unwarped Unit-03 source baseline.

No installed resource, live world, runtime actor, or old candidate is modified.
The Unit-03 output is an interchange surface, not an installable rigged pack.
"""
import argparse
import collections
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(p):
    return json.loads(p.read_text('utf8'))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), 'utf8')


def obj_surfaces(raw):
    vertices, uv, normals = [], [], []
    faces = collections.defaultdict(list)
    name = material = None
    for line in raw.decode('utf8').splitlines():
        row = line.split()
        if not row:
            continue
        if row[0] == 'v':
            vertices.append(list(map(float, row[1:4])))
        elif row[0] == 'vt':
            uv.append(list(map(float, row[1:3])))
        elif row[0] == 'vn':
            normals.append(list(map(float, row[1:4])))
        elif row[0] in ('o', 'g'):
            name = row[1]
        elif row[0] == 'usemtl':
            material = row[1]
        elif row[0] == 'f':
            refs = [tuple(int(n)-1 for n in item.split('/')) for item in row[1:]]
            assert all(len(r) == 3 and min(r) >= 0 for r in refs)
            for at in range(1, len(refs)-1):
                faces[name, material].append((refs[0], refs[at], refs[at+1]))
    v, u, n = map(np.asarray, (vertices, uv, normals))
    result = {}
    for (name, material), entries in faces.items():
        f = np.asarray(entries)
        result[name] = dict(material=material,
            corners=np.concatenate((v[f[:, :, 0]], u[f[:, :, 1]], n[f[:, :, 2]]), axis=2))
    return result


def unit03(a, output):
    output.mkdir()
    raw_archive = a.unit03.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw_archive)) as outer:
        nested_raw = outer.read('source/Unit03.zip')
    with zipfile.ZipFile(io.BytesIO(nested_raw)) as nested:
        obj = nested.read('Unit03.obj')
        mtl = nested.read('Unit03.mtl')
        files = {name: nested.read(name) for name in ('e03_201.png', 'w03_001.png', 'e03_201_glow.png')}
    assert obj == (a.previous_unit03/'unpacked/Unit03.obj').read_bytes()
    groups = obj_surfaces(obj)
    body = groups['e03_201_0_Untitled.079']['corners']
    hand = groups['w03_201_0_Untitled.077']['corners']
    duplicate = groups['w03_001_0_Untitled.078']['corners']
    assert np.array_equal(hand, duplicate)
    assert body.shape == (3191, 3, 8) and hand.shape == (718, 3, 8)
    # The selected alias actually names the forearm texture. Preserve that
    # image instead of importing its coincident differently named duplicate.
    assert 'newmtl e03_201_w03_001.png' in mtl.decode('utf8')
    section = mtl.decode('utf8').split('newmtl e03_201_w03_001.png')[1].split('newmtl')[0]
    assert 'map_Kd w03_001.png' in section
    raw = np.concatenate((body, hand))
    ymin, ymax = raw[:, :, 1].min(), raw[:, :, 1].max()
    scale = 192/(ymax-ymin)
    transformed = raw.copy()
    transformed[:, :, :3] = (raw[:, :, :3]-[0, ymin, 0])*[scale, scale, -scale]
    transformed[:, :, 5:8] *= [1, 1, -1]
    # Keep UVs and winding in original OBJ order in this interchange file.
    # The future runtime exporter must explicitly account for its reflection.
    restored = transformed[:, :, :3]/[scale, scale, -scale]+[0, ymin, 0]
    assert np.allclose(restored, raw[:, :, :3], rtol=0, atol=1e-14)
    assert np.array_equal(transformed[:, :, 3:5], raw[:, :, 3:5])
    assert np.array_equal(transformed[:, :, 5:8]*[1, 1, -1], raw[:, :, 5:8])
    original_edges = np.roll(raw[:, :, :3], -1, axis=1)-raw[:, :, :3]
    result_edges = np.roll(transformed[:, :, :3], -1, axis=1)-transformed[:, :, :3]
    lengths = np.linalg.norm(original_edges, axis=2)
    valid = lengths > 1e-12
    relative = np.linalg.norm(result_edges, axis=2)[valid]/lengths[valid]
    assert np.max(abs(relative/scale-1)) < 1e-10
    np.savez_compressed(output/'unit03_source_surface.npz',
        source_corners=raw, normalized_corners=transformed,
        material=np.r_[np.zeros(len(body), dtype=np.uint8), np.ones(len(hand), dtype=np.uint8)],
        source_face=np.r_[np.arange(len(body)), np.arange(len(hand))],
        scale=scale, source_ymin=ymin)
    textures = {}
    for name, data in files.items():
        (output/name).write_bytes(data)
        image = Image.open(io.BytesIO(data))
        textures[name] = dict(size=image.size, mode=image.mode, sha256=digest(data), bytes_identical=True)
    shutil.copy2(a.previous_unit03/'COMPONENTS.json', output/'COMPONENTS.json')
    old = read(a.previous_unit03/'candidate-v10/bind_report.json')
    source = np.asarray([r['source'] for r in old['landmarks']])
    target = np.asarray([r['target'] for r in old['landmarks']])
    i, j = np.triu_indices(len(source), 1)
    ratios = np.linalg.norm(target[i]-target[j], axis=1)/np.linalg.norm(source[i]-source[j], axis=1)
    assert ratios.max()/ratios.min() > 1.1, 'Known warped candidate must fail the uniform-proportion check'
    rejected = dict(candidate='candidate-v10', evaluated='Existing measured landmark pair distances',
        pair_distance_ratio_min=float(ratios.min()), pair_distance_ratio_max=float(ratios.max()),
        nonuniform_ratio=float(ratios.max()/ratios.min()), uniform_transform_compatible=False,
        does_not_measure_all_animated_skin_errors=True)
    report = dict(status='SOURCE_BASELINE_ONLY_NOT_INSTALLABLE', source_archive=str(a.unit03.resolve()),
        archive_sha256=digest(raw_archive), nested_archive_sha256=digest(nested_raw), obj_sha256=digest(obj),
        raw_source_triangles=4627, exact_coincident_duplicate_triangles=718,
        unique_source_triangles=3909, retained_triangles=len(transformed),
        source_bounds=[raw[:, :, :3].min((0, 1)).tolist(), raw[:, :, :3].max((0, 1)).tolist()],
        normalized_bounds=[transformed[:, :, :3].min((0, 1)).tolist(), transformed[:, :, :3].max((0, 1)).tolist()],
        uniform_scale=float(scale), axis='OBJ X/Y-up/+Z-front -> model X/Y-up/-Z-front',
        origin_shift_y=float(ymin), all_edge_lengths_have_same_scale=True,
        maximum_edge_relative_error=float(np.max(abs(relative/scale-1))),
        nonrigid_warp=False, source_UV_exact=True, source_normal_components_exact_after_inverse_axis=True,
        source_normals_are_not_renormalized=True, source_textures=textures,
        hand_original_curl_retained=True, back_source_surface_retained=True,
        replacement_hands=False, generic_dorsal_bore=False, skeleton_calibration_pending=True,
        old_candidate_negative_regression=rejected, actual_world_written=False,
        future_work=['Measure Unit-03 skeleton and finger bind axes on this unchanged surface',
            'Retarget Unit-01 motion deltas to Unit-03 rest basis; do not reuse exact Unit-01 pivots',
            'Fit entry-plug axis/cover to actual Unit-03 dorsal landmarks before any exact surface cut',
            'Recompute rig4 support, physical hulls, hands, eyes, attachment and contact contracts as one candidate',
            'Review full render/animation states on temporary actors; preserve the UN01 original entity slot and progress'])
    write(output/'SOURCE_SURFACE.json', report)
    return report


def installed(a, output):
    historical = read(a.historical/'ASSET_AUDIT.json')
    coverage = {r['unit']: r for r in read(a.historical/'NERV_SURFACE_COVERAGE.json')}
    options = (a.client/'options.txt').read_text('utf8')
    selected = json.loads(next(row.split(':', 1)[1] for row in options.splitlines() if row.startswith('resourcePacks:')))
    packs = []
    for name in selected:
        if name.startswith('file/'):
            p = a.client/'resourcepacks'/name[5:]
            assert p.is_file(), p
            packs.append((name, zipfile.ZipFile(p)))
    rows, frozen = [], {}
    with zipfile.ZipFile(a.client/'mods/projectseele-0.1.0-all.jar') as jar:
        for unit in ('00', '01', '02'):
            model = 'eva_unit'+unit
            names = ['mesh/'+model+'.mesh.json', 'geo/'+model+'.geo.json',
                     'mesh/'+model+'_anatomical_hands_r45.mesh.json']
            names += ['textures/entity/'+model+s+'.png' for s in ('', '_n', '_s', '_eyes')]
            resources, data = {}, {}
            for n in names:
                key = 'assets/projectseele/'+n
                assert not any(key in z.namelist() for _, z in packs), ('Selected override needs separate audit', key)
                blob = jar.read(key)
                frozen[key] = digest(blob)
                old = a.historical/'installed/assets/projectseele'/n
                resources[n] = dict(sha256=digest(blob), same_as_existing_audit=old.exists() and old.read_bytes() == blob,
                                    selected_resourcepack_override=False)
                assert resources[n]['same_as_existing_audit']
                if n.endswith('.json'):
                    data[n] = json.loads(blob)
            mesh = data[names[0]]
            hand = data[names[2]]
            cov = coverage[unit]
            bands = collections.Counter()
            for face in cov['changed_surfaces']:
                x, y, z = face['centroid']
                bands['hand_band' if 70 < y < 110 and abs(x) > 15 else
                      'head_neck_back_band' if y > 145 else 'unclassified'] += 1
            assert bands['unclassified'] == 0
            original = historical['sources']['unit'+unit]
            archive = Path(original['path'])
            assert digest(archive.read_bytes()) == original['sha256']
            visible_body = sum(len(p['vertices'])//24 for n, p in mesh['parts'].items()
                               if not n.startswith(('hand_', 'finger_')))
            rows.append(dict(unit=unit, source_triangles=cov['source_faces'], source=original,
                stored_body_triangles=mesh['triangleCount'],
                anatomical_hand_triangles=sum(len(p['vertices'])//24 for p in hand['parts'].values()),
                visible_body_before_pose_filters_triangles=visible_body,
                resources=resources, equivalent_source_area_fraction=cov['equivalent_source_area_fraction'],
                surface_equivalent_faces=cov['surface_equivalent_faces'],
                unmatched_face_bands=dict(bands), source_surface_sample_points=cov['source_samples'],
                sample_threshold_model_units=cov['threshold_model_units'],
                deliberate_geometry_metadata={k: v for k, v in mesh.items() if k.startswith(('r13_', 'r37_', 'r51_'))},
                hand_source=hand['source'],
                static_audit_still_applies_to_current_selected_resources=True,
                total_triangle_count_is_not_a_source_coverage_proof=True,
                native_continuous_hand_neck_dorsal_pose_acceptance=False))
        old_un01 = json.loads(jar.read('assets/projectseele/mesh/eva_un01.mesh.json'))
        un01 = dict(current_source=old_un01.get('source'), triangles=old_un01['triangleCount'],
                    unit03_contract_installed='assets/projectseele/eva/unit03_shared_r53.json' in jar.namelist())
    for _, z in packs:
        z.close()
    # Parent may be deploying unrelated carrier classes concurrently. Verify
    # audited resources again instead of assuming the whole JAR is stationary.
    with zipfile.ZipFile(a.client/'mods/projectseele-0.1.0-all.jar') as jar:
        assert all(digest(jar.read(n)) == h for n, h in frozen.items())
    result = dict(models=rows, resourcepacks=selected, un01_slot=un01,
        provenance='Current selected JAR entries read twice; selected terrain packs do not override these resources',
        sources_read_only=True, UN00_work_excluded=True,
        limits=['Seven geometric samples per source face do not prove every pixel is visible',
                'Replacement hands and dorsal cuts require native pose review despite matching resource hashes',
                'Source ZIPs themselves contain low-thousands of triangles; this audit does not substitute another high-poly author model'])
    write(output/'CURRENT_NERV_PRECISION.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('client', 'historical', 'unit03', 'previous-unit03', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    nerve = installed(a, a.output)
    unit = unit03(a, a.output/'unit03-source-preserved')
    write(a.output/'SUMMARY.json', dict(current_models=[dict(unit=r['unit'], source_faces=r['source_triangles'],
        exact_audit_resources_unchanged=True, remaining_changed_bands=r['unmatched_face_bands']) for r in nerve['models']],
        unit03_unique_source_faces=unit['unique_source_triangles'], unit03_source_preserved=True,
        unit03_rig_ready=False, old_v10_rejected_by_uniform_check=True,
        actual_world_written=False, installed_assets_written=False))
    print('Current 00/01/02 resources match existing coverage audit; Unit-03 3909 source faces preserved without warp.')


if __name__ == '__main__':
    main()

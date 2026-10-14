"""Root's exact field/identity ledger for the HQ-only native MTR migration.

Reads the original archive, independently decodes candidate bytes, and checks
the actual chosen world before or after installation. Never writes that world.
"""
import argparse,hashlib,json
from pathlib import Path
from audit_hq_mtr_protection_r52 import baseline,record,vehicles,differences,rail_position_id

ROOT=Path(__file__).resolve().parents[1]
WORLD=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52')
PATCH=ROOT/'artifacts/r52_mtr_progress_review/member_patch_v3'
OUT=ROOT/'.Codex/r52_mtr_install'
MANIFEST_SHA='45dbcf14e84061fafdb86099653e45684ff18311348334726697b3851d9ffaa0'
NATIVE_SHA='c38fa3b3d269a940dd3256fe0b0a55f96c8dce5c15f23bd898cd81b602db3156'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def load(p):return json.loads(p.read_text('utf8'))
def bounded(base,relative):
    assert relative.startswith('mtr/projectseele/geofront/') and '..'not in relative and '\\'not in relative and ':'not in relative
    p=(base/relative).resolve();assert p.is_relative_to(base.resolve());return p


def review(phase):
    assert sha((PATCH/'PATCH_MANIFEST.json').read_bytes())==MANIFEST_SHA
    assert sha((PATCH/'NATIVE_BINARY_PATCH_VERIFICATION.json').read_bytes())==NATIVE_SHA
    manifest=load(PATCH/'PATCH_MANIFEST.json');original=baseline();ops=manifest['operations']
    assert len(original)==251 and sum(n.startswith('mtr/projectseele/geofront/')for n in original)==248
    assert len(ops)==72 and manifest['counts']=={'modify':8,'delete':10,'create':54}
    assert len({r['target_relative_path']for r in ops})==72
    expected=dict(original);modified={};retired=set();created={}
    allowed_depots={'38DEE70431CA579F','C60ACDD5B2F2A3E2'}
    allowed_sidings={'870D8E318A61ABC0','DF5FECA5A69869EA'}
    for op in ops:
        name=op['target_relative_path'];kind=name.split('/')[3];identifier=name.rsplit('/',1)[-1]
        target=bounded(WORLD,name);action=op['action']
        if action in ('modify','delete'):
            assert name in original and original[name]['sha256']==op['before_sha256']
            assert sha(bounded(PATCH/'before',name).read_bytes())==op['before_sha256']
        else:assert action=='create' and name not in original and op['before_sha256'] is None
        if action!='delete':
            raw=bounded(PATCH/'after',name).read_bytes();assert sha(raw)==op['after_sha256'];after=record(raw)
            expected[name]=after
        else:expected.pop(name);retired.add(name)
        if action=='modify':
            before=original[name];a,b=before['data'],after['data']
            assert before['opaque_tail_bytes']==after['opaque_tail_bytes'] and before['opaque_tail_sha256']==after['opaque_tail_sha256']
            if kind in ('stations','platforms'):
                assert identifier in {'7F36F8DC34907D9B','910C703E8C195E14','5F8F651005220016','7503CEFA3D9A08FC'}
                wanted=json.loads(json.dumps(a));wanted['position1']['y']-=93;wanted['position2']['y']-=93;assert wanted==b
            elif kind=='depots':
                assert identifier in allowed_depots
                assert {k:v for k,v in a.items()if k!='path'}=={k:v for k,v in b.items()if k!='path'}
            elif kind=='sidings':
                assert identifier in allowed_sidings
                fields={'vehicles'}|({'pathSidingToMainRoute'}if identifier=='DF5FECA5A69869EA'else set())
                assert {k:v for k,v in a.items()if k not in fields}=={k:v for k,v in b.items()if k not in fields}
                assert len(a['vehicles'])==len(b['vehicles'])==3
                for av,bv in zip(a['vehicles'],b['vehicles']):
                    mutable={'railProgress','nextStoppingIndexAto','nextStoppingIndexManual'}
                    assert {k:v for k,v in av.items()if k not in mutable}=={k:v for k,v in bv.items()if k not in mutable}
            else:raise AssertionError(('Unapproved modified member kind',name))
            modified[name]=dict(before=before['sha256'],after=after['sha256'],actual_fields=differences(a,b))
        elif action=='delete':assert kind=='rails'
        else:
            assert kind=='rails' and identifier==rail_position_id(after['data'])
            template=op['inherited_template_archive_member'].removeprefix('SEELE_R50_WORLD/');assert template in original
            mutable={'position1','position2','angle1','angle2','shape','verticalRadius','speedLimit1','speedLimit2','signalColors'}
            assert {k:v for k,v in original[template]['data'].items()if k not in mutable}=={k:v for k,v in after['data'].items()if k not in mutable}
            created[name]=after
    old_ten={r['member'].removeprefix('SEELE_R50_WORLD/')for r in load(ROOT/'artifacts/r52_hq_rail_boundary/hq_ten_rails.json')}
    assert retired==old_ten
    candidate=load(ROOT/'artifacts/r52_hq_approach_candidate/CANDIDATE.json')['segments'];assert len(candidate)==len(created)==54
    def endpoint(p,a):return tuple(p[k]for k in ('x','y','z'))+(a,)
    actual_geometry={frozenset((endpoint(r['data']['position1'],r['data']['angle1']),endpoint(r['data']['position2'],r['data']['angle2']))):r['data']for r in created.values()}
    assert len(actual_geometry)==54
    for segment in candidate:
        key=frozenset((tuple(segment['from'])+(segment['from_angle'],),tuple(segment['to'])+(segment['to_angle'],)))
        assert key in actual_geometry;d=actual_geometry[key]
        assert d['shape']==segment['shape'] and d['verticalRadius']==segment['vertical_radius']
    original_fleet,errors=vehicles(original);assert not errors
    final_fleet,errors=vehicles(expected);assert not errors and original_fleet.keys()==final_fleet.keys() and len(final_fleet)==40
    native=load(PATCH/'NATIVE_BINARY_PATCH_VERIFICATION.json')
    assert native['fleet_input_loader']=='actual patched member bytes / native MessagePackReader'
    assert native['native_reassembly_matches_expected_paths'] and native['vehicles_remapped']==6
    protected={r['member'].removeprefix('SEELE_R50_WORLD/'):r['sha256']for r in manifest['protected_original_members']}
    assert len(protected)==230
    # Three original vanilla-dimension settings records sit outside the
    # agent's GeoFront-only patch scope and must also remain byte-identical.
    protected.update({n:r['sha256']for n,r in original.items()if not n.startswith('mtr/projectseele/geofront/')})
    assert len(protected)==233 and set(protected)==set(original)-set(modified)-retired
    for name,h in protected.items():assert original[name]['sha256']==expected[name]['sha256']==h
    current={p.relative_to(WORLD).as_posix():sha(p.read_bytes())for p in (WORLD/'mtr').rglob('*')if p.is_file()}
    wanted=original if phase=='before'else expected
    assert set(current)==set(wanted),('Actual member inventory differs',phase,set(current)^set(wanted))
    assert all(current[n]==r['sha256']for n,r in wanted.items()),'Actual MTR byte readback mismatch'
    summary=dict(schema='projectseele.r52.root-mtr-ledger.v1',map_author='root',reviewed=True,world=str(WORLD),patch_directory=str(PATCH),
        manifest_sha256=MANIFEST_SHA,native_binary_receipt_sha256=NATIVE_SHA,phase=phase,world_written=False,
        actual_members=len(current),original_vehicles=40,protected_exact_members=233,protected_geofront_members=230,protected_other_dimension_settings=3,operations=ops,
        reviewed_modifications=modified,operating_changes='Only three shared approach groups become bidirectional60 with distinct signal blocks; preserve original isolated branch directions.',
        vehicle_changes='Only railProgress and both path indices on original six U1/U2 vehicles; logical next stop and all other vehicle state preserved.',
        full_native_gameplay_verified=False,pending=['actual driver ride and signal waiting','derived navigation and wayfinding refresh'])
    OUT.mkdir(exist_ok=True);path=OUT/('ROOT_REVIEWED_LEDGER.json'if phase=='before'else'ACTUAL_WORLD_READBACK.json')
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n','utf8')
    print(json.dumps({k:v for k,v in summary.items()if k not in ('operations','reviewed_modifications')}))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--phase',choices=('before','after'),required=True);review(ap.parse_args().phase)

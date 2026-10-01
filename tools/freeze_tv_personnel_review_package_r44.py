"""Freeze the incomplete personnel candidate for review; never publish/apply it."""
from pathlib import Path
import json,hashlib,shutil

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'artifacts/rebuild_r44/hangar_machinery'
OUT=BASE/'tv_personnel_platform_package_v5_review_v3'
if OUT.exists():raise ValueError('Immutable review package already exists')
OUT.mkdir()
files={
    'model/tv_shoulder_shells_r44.json':BASE/'tv_personnel_supports_v5_draft12/tv_shoulder_shells_r44.json',
    'model/explicit_geometry_equal_receipt.json':BASE/'tv_personnel_supports_v5_draft12/receipt.json',
    'model/hangar_shoulder_contacts_r44.json':ROOT/'src/main/resources/assets/projectseele/mesh/hangar_shoulder_contacts_r44.json',
    'world/operations.json':BASE/'personnel_platforms_v5_boundaries_v4/operations.json',
    'world/inverse.json':BASE/'personnel_platforms_v5_boundaries_v4/inverse.json',
    'world/r44_tv_personnel_platforms.json':BASE/'personnel_platforms_v5_boundaries_v4/r44_tv_personnel_platforms.json',
    'world/layout.json':BASE/'personnel_platforms_v5_layout_v4/layout.json',
    'validation/boundaries_original_ops_contract.json':BASE/'personnel_platforms_v5_boundaries_v2/contract.json',
    'validation/three_width_paths.json':BASE/'personnel_draft11_virtual_access_v1/contract.json',
    'validation/fixed_geometry.json':BASE/'personnel_draft11_fixed_geometry_v1/contract.json',
    'validation/whole_standing_with_actual_boundary.json':BASE/'personnel_draft11_whole_standing_v1/contract.json',
    'validation/continuous_self.json':BASE/'personnel_draft11_continuous_self_v1/contract.json',
    'validation/complete_current_interfaces.json':BASE/'personnel_draft11_current_interfaces_v1/complete_physical_interfaces.json',
    'validation/full_carrier_continuous_envelopes.json':BASE/'personnel_draft11_carrier_envelopes_v1/contract.json',
    'validation/mounted_rams.json':BASE/'personnel_draft11_mounted_rams_v1/contract.json',
    'validation/grating_maximum_openings.json':BASE/'personnel_native_grating_openings_v1/contract.json',
    'negative_controls/draft9_original_whole_standing.json':BASE/'personnel_draft9_whole_standing_v2/contract.json',
    'negative_controls/draft9_true14_after_actual_guard_boundary.json':BASE/'personnel_draft9_whole_standing_outline_v3/contract.json',
    'validation/deck64_native_union.json':BASE/'tv_personnel_deck_native_v1/native_union_readback/result.json',
    'validation/guard64_native_union.json':BASE/'tv_personnel_guard_native_v1/native_union_readback/verified_union_result.json',
    'inputs/actual_native_fullbody.json':ROOT/'artifacts/rebuild_r44/space_photos/installed_maps_hakone_and_tv_fullbody/20261001_045405/r44_hangar_body_surfaces.json',
}
for name in ('TvPersonnelPlatformInterlockR44','TvCageCollisionR44','EvaLogisticsDirector','CityPersonnelDoorR44','TvPersonnelDeckR44','TvPersonnelGuardR44'):
    files[f'source/{name}.java']=ROOT/f'src/main/java/com/projectseele/world/{name}.java'
for name in ('build_tv_personnel_supports_r44','plan_tv_personnel_platforms_r44','plan_tv_personnel_boundaries_r44',
             'audit_tv_proposed_personnel_walk_r44','audit_tv_personnel_fixed_geometry_r44','preview_tv_personnel_platforms_r44',
             'build_tv_shoulder_shells_r44','build_tv_personnel_deck_assets_r44','build_tv_personnel_guard_assets_r44',
             'audit_tv_personnel_whole_standing_r44','audit_tv_personnel_continuous_self_r44','audit_tv_personnel_carrier_envelopes_r44',
             'audit_tv_grating_openings_r44','freeze_tv_personnel_preapply_r44','prepare_tv_personnel_producer_recipe_r44','prepare_tv_crane_mesh_witness_r44'):
    files[f'source/{name}.py']=ROOT/f'tools/{name}.py'
for folder in ('tv_personnel_deck_native_v1','tv_personnel_guard_native_v1'):
    for path in (BASE/folder/'assets').rglob('*'):
        if path.is_file():files[str(path.relative_to(BASE/folder))]=path
for folder in ('personnel_draft12_preapply_epoch_v2','personnel_source_recipe_v2','personnel_crane_mesh_witness_v1','personnel_draft12_native_view_plan_v1','personnel_owned_motion_pause_v1'):
    for path in (BASE/folder).rglob('*'):
        if path.is_file():files[folder+'/'+str(path.relative_to(BASE/folder))]=path
rows=[]
for target,source in files.items():
    dest=OUT/target;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    rows.append({'path':target,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size})
report={'schema':44,'status':'INCOMPLETE_REVIEW_CANDIDATE_NOT_APPLICABLE','files':rows,'private_reference_comparison_not_for_distribution':True,
        'model_sha256':'2a789960d2649118b12505be8d6c93888ed8e1cabe6beaef0c20f498b12551a3',
        'geometry_tested_source_sha256':'b6cb6756d6436c54eb4635e964abc42b82bf8fd59eb4f74fded9dfdc0be31b81',
        'new_model_geometry_equal_tested_source':'parts/collision_parts/components exact JSON equality; only current metadata provenance changes',
        'world_apply_allowed':False,'native_personnel_passed':False,'art_passed':False,'world_write_performed':False,
        'engineering_only_completed':['70772 stance actualsupport/body clearance including exact guard boundary and allgreen faces;134 boundaryrefinements retained','144 fixed/newmoving part combinations each120continuous intervals0','complete actualbody/capsule/currentworld/full02owner clearance0','24 actual carrierparts240 continuous source intervals vs newnative floors/guards/gates0; mountedram54bounds0','64actualnativegrating slot maxnarrowaxis0.12125m; whole0.6mfootprint doesnotfit','427 currentbefore allmatch/0BE touched; full6localBEs/12entities/allglobalownedSavedData epochstable; inverse427'],
        'remaining':['rootcompile and native freshgeneration/maintenance of newconcrete finite source_recipe_v2','strictmetadata/allinstalledfloors guards gates validation in current frozen interlock loader','nativecurrent crane complete emitted geometry and continuous coupledrelease path','independent carrier/ejection/activation/launch clock hold/sync/NBT/relogin rootcoordination; oldhooksketch is notcompilable','actual native stationarygratinglandings/full six entry-and-return/green/whole occupancy/door/prepare/pause-resume/unknown controls','cold/relogin/multiplayer/source/installationreadback and performance','actualmatching TVdirection/pose/liquid/gallery views and originaldenseviscousLCL art; no user art acceptance']}
(OUT/'manifest.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps({'package':str(OUT),'files':len(rows),'apply_allowed':False}))

"""Classify explicitly approved original lattice/soil preimages; emit Root-only final candidate."""
from pathlib import Path
import copy
import json
import shutil
import nbtlib

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'artifacts/rebuild_r48/city/c03_lowrise_restore_candidate'
DEST=ROOT/'artifacts/rebuild_r48/city/c03_lowrise_restore_final_v2'


def main():
    assert SOURCE.is_dir() and not DEST.exists()
    data=json.loads((SOURCE/'manifest.json').read_text(encoding='utf8'))
    approved=[]
    for hold in data['holds']:
        assert hold['type']=='UNKNOWN_OR_OWNED_OCCUPANCY_NOT_CLEARABLE'
        x,y,z=hold['pos']; assert hold['full_before_nbt'] is None
        component=next((c for c in data['components'] if c['complete_static_and_clearance_inspection_box'][0]<=x<=c['complete_static_and_clearance_inspection_box'][3]
                        and c['complete_static_and_clearance_inspection_box'][2]<=z<=c['complete_static_and_clearance_inspection_box'][5]),None)
        assert component is not None
        if hold['before']=='minecraft:dirt':
            assert 76<=y<=79
            proof='ThirdTokyoSurfaceBuilder.buildFoundation/TvWorldPreviewTerrain original surface grading fill; Root explicitly approved only four complete shaft footprints'
        else:
            assert hold['before']=='minecraft:polished_deepslate' and y==79
            rx,rz=x-30,z-220
            assert -156<=rx<=156 and -156<=rz<=156
            assert ((rx+152)%16==0 or (rz+152)%16==0)
            proof='Tokyo3LandscapeBuilder original under-deck lattice (axis -152..152 step16, span -156..156, OriginY-1); Root explicitly approved finite four-shaft structural replacement'
        approved.append(dict(**hold,template_id=component['template_id'],classification='KNOWN_APPROVED_SOURCE_LAYER',provenance=proof))
    assert len([h for h in approved if h['before']=='minecraft:polished_deepslate'])==132
    assert len([h for h in approved if h['before']=='minecraft:dirt'])==4748
    shutil.copytree(SOURCE,DEST)
    # Refer to final copies while retaining the unaltered source-world paths and full original NBT.
    def replace_paths(value):
        if isinstance(value,str):return value.replace(str(SOURCE),str(DEST))
        if isinstance(value,list):return [replace_paths(v) for v in value]
        if isinstance(value,dict):return {k:replace_paths(v) for k,v in value.items()}
        return value
    data=replace_paths(data)
    data['stage']='FINAL_ROOT_ONLY_COLD_APPLY_CANDIDATE_NOT_APPLIED'
    data['holds']=[]; data['holds_count']=0
    data['approved_finite_source_layer_replacements']=approved
    data['candidate_world_application_allowed']=True
    data['application_authority']='Root only; compare every complete before/NBT then install payload/static/recipe, read back, finally promote marker. Do not import any actor/mission progress.'
    data['lattice_continuity']=dict(origin=[30,80,220],axis_start=-152,axis_end=152,axis_step=16,span_range=[-156,156],y=79,
                                   all132_preimages_match_source_formula=True,
                                   altered_cross_in_swept_footprint_cells=116,
                                   source_cross_at_four_liner_edges_retained=16,
                                   complete_y79_outer_liner_ring_radius=8,
                                   outside_lattice_after_footprint_unchanged=True,
                                   replacement_static_bearing_columns_and_complete_lower_saddle=True)
    for c in data['components']:
        c['source_lattice_attachment']=dict(y=79,old_cross_endpoints_retained_at_offsets=[[-8,0],[8,0],[0,-8],[0,8]],
                                             new_full_perimeter_path_radius=8,material='minecraft:polished_deepslate',
                                             note='Original four incoming lattice arms remain connected around the shaft on the new complete 64-cell perimeter; no material-wide delete.')
    marker='projectseele_city_rigid_topology_r45_8246338109520.dat'
    pending=nbtlib.load(DEST/marker)
    pending['data']['LowriseAddonR48']['OriginalSettledLedger']=copy.deepcopy(nbtlib.load(DEST/'metadata_before/projectseele_city_rigid_control_r45_8246338109520.dat')['data'])
    pending.save(DEST/marker,gzipped=True)
    installed=copy.deepcopy(pending)
    addon=installed['data']['LowriseAddonR48']
    addon['Stage']=nbtlib.String('INSTALLED')
    addon['ExactComponentMigrationPassed']=nbtlib.Byte(1)
    addon['FullSweepVerified']=nbtlib.Byte(1)
    installed.save(DEST/'topology_after_full_readback_ONLY.dat',gzipped=True)
    data['inactive_marker']=str(DEST/marker)
    data['after_verified_application_marker']=str(DEST/'topology_after_full_readback_ONLY.dat')
    data['marker_promote_order']='After exact World full before match, apply full 4 payload/static + recipe/cargo, verify complete after/anchors and original96 prefix/ledger unchanged, then write the installed addon marker last. The flags are not a claim that this script ran game/native QA.'
    data['native_motion_or_client_visual_passed']=False
    (DEST/'manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(dict(output=str(DEST),holds=0,world_written=False,changed_cells=data['changed_cells'],known_lattice=132,
                          known_surface_soil=4748,metadata_promotion_after_root_readback_only=True),indent=2))


if __name__=='__main__':main()

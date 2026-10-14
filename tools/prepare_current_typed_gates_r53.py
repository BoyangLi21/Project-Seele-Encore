"""Root-selected 41 typed gate candidates. Writes files only; no World access."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json,math
from root_bundle_authority_r53 import candidate
ROOT=Path(__file__).resolve().parents[1]
BASE=Path('D:/eva/artifacts/map_complete_20261013')
C11=Path('D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate/final_c11_selected_assets_v2/ROOT_MECHANICAL_OWNER.json')
def read(p):return json.loads(Path(p).read_text('utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--directory',type=Path,required=True);ap.add_argument('--directory-sha256',required=True);ap.add_argument('--floor-extension-role-table',type=Path);ap.add_argument('--floor-extension-role-sha256');ap.add_argument('--full-wet-throat',type=Path);ap.add_argument('--full-wet-throat-sha256');a=ap.parse_args()
    out=candidate(a.out,BASE/'WORLD');out.mkdir(parents=True,exist_ok=True)
    assert sha(a.directory)==a.directory_sha256,'Explicit current Root directory SHA changed'
    directory=read(a.directory);assert directory['epoch']==53 and directory['schema']=='projectseele.r52.route-directory.v2'
    old=read(C11);old_gates={g['resource']:g for g in old['gates']};gates=[];provenance={str(C11):sha(C11),str(a.directory):sha(a.directory)}
    extension=[]
    assert bool(a.floor_extension_role_table)==bool(a.floor_extension_role_sha256)
    if a.floor_extension_role_table:
        assert sha(a.floor_extension_role_table)==a.floor_extension_role_sha256
        extension=[r for r in read(a.floor_extension_role_table)['cells'] if r['group_role']=='wet_transfer/original_floor_join'];assert len(extension)==165
        provenance[str(a.floor_extension_role_table)]=a.floor_extension_role_sha256
    assert bool(a.full_wet_throat)==bool(a.full_wet_throat_sha256)
    if a.full_wet_throat:
        assert extension and sha(a.full_wet_throat)==a.full_wet_throat_sha256
        extra=[r for r in read(a.full_wet_throat)['wet_throat_candidates'] if r['position'][1]==-1063 and 303<=r['position'][2]<=310];assert len(extra)==672
        extension+=extra;provenance[str(a.full_wet_throat)]=a.full_wet_throat_sha256
    def write(name,value):
        path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(json.dumps(value,separators=(',',':')).encode(),mtime=0));return {'cells_file':name,'sha256':sha(path)}
    def frame(x,y,z,q=None):return dict(position=[x,y,z],quaternion=q or [0,0,0,1])
    for v in range(3):
        source=old_gates[f'bay_{v}_front'];g={k:copy.deepcopy(source[k]) for k in ('resource','kind','variant','stage','frame','width','height','hangar_stack','supports','floor_seal_original_cells')};g['frame']['position'][1]-=384
        for s in g['supports']:s['position'][1]-=384
        for p in g['floor_seal_original_cells']:p[1]-=384
        ref=source['collision_steps'];path=C11.parent/ref['cells_file'];assert sha(path)==ref['sha256'];provenance[str(path)]=sha(path);rows=read_gzip(path)
        for row in rows:
            for c in row:c['position'][1]-=384
        if extension:
            actual=[r for r in extension if {w['variant'] for w in r['motion_witnesses']}=={v}];assert len(actual)==(279 if a.full_wet_throat else 55)
            f=g['hangar_stack']['floor_seal'];f['version']=2;f['retained_box_count']=len(f['closed_boxes']);cells={tuple(p) for p in g['floor_seal_original_cells']};existing={tuple(c['position']) for row in rows for c in row};cx,cy,cz=g['frame']['position'];assert g['frame']['quaternion']==[0,1,0,0]
            for r in actual:
                x,y,z=r['position'];assert r['state'].split('[')[0] in ('projectseele:nerv_floor_panel','projectseele:nerv_machine_hazard','projectseele:nerv_machine_panel','projectseele:nerv_machine_edge','minecraft:polished_basalt','minecraft:cut_copper','minecraft:exposed_cut_copper','minecraft:iron_block','minecraft:polished_blackstone','minecraft:sea_lantern') and y==cy-1 and 301<=z<=310
                assert r['native_boxes']==[[x,y,z,x+1,y+1,z+1]],'Only Root-selected complete native floor cubes belong to the seal'
                if (x,y,z) in cells:continue
                assert (x,y,z) not in existing
                f['closed_boxes'].append([cx-x-1,y-cy,cz-z-1,cx-x,y+1-cy,cz-z]);cells.add((x,y,z));rows[0].append(dict(position=[x,y,z],closed=r['state'],open='minecraft:air'))
            g['floor_seal_original_cells']=[list(p) for p in sorted(cells)];assert len(cells)==(293 if a.full_wet_throat else 69)
        g['collision_steps']=write('source_tables/'+g['resource']+'.json.gz',rows);gates.append(g)
    pits=BASE/'complete_carrier_pits/three_supported_dry_carrier_pits/PLAN.json';p=read(pits);provenance[str(pits)]=sha(pits)
    assert p['service_gantry_yaw_degrees']==180 and p['dynamic_floor_cells']==3465 and p['selected_actual_hatch_geometry_sha256']=='9f8d07a9e77ba88f3caf76924b2b4a31630e2225d1ca1f1d582863e171ab5246'
    for source in p['gates']:
        g={k:copy.deepcopy(source[k]) for k in ('resource','kind','variant','stage','frame','width','height','silo_hatch','supports')};ref=source['collision_steps'];path=pits.parent/ref['cells_file'];assert sha(path)==ref['sha256'];provenance[str(path)]=sha(path);g['collision_steps']=write('source_tables/'+g['resource']+'.json.gz',read_gzip(path));gates.append(g)
    air=BASE/'air_transport_shaft/actual_machine_bearings_and_cassettes/PLAN.json';alignment=BASE/'air_transport_shaft/south_leaf_collision_alignment/APPLIED.json';cases=read(air)['cases'];align=read(alignment);assert align['actual_machine_frame']==[-1120,-475,-635];provenance.update({str(air):sha(air),str(alignment):sha(alignment)})
    for c in cases:
        horizontal=c['kind']=='horizontal';g=dict(resource='remote_airshaft_surface' if horizontal else 'remote_airshaft_south',kind='SILO' if horizontal else 'HANGAR',variant=0,stage=3,frame=frame(*c['frame']),width=164,height=164 if horizontal else 181,supports=[{k:copy.deepcopy(s[k]) for k in ('position','state')} for s in c['support_cells']])
        if horizontal:g['silo_hatch']=dict(opening_x=164,opening_z=164,open_ticks=160,close_ticks=160,separation_sign=1,beam_bottom=-2.01,service_column_ports=False,upright_guide_ports=False)
        else:g['hangar_stack']=dict(open_ticks=160,close_ticks=160,depth_direction=1)
        gates.append(g)
    for lane,x in enumerate((-11.5,30.5,72.5)):
        v=2-lane
        for bank,z in ((1,106.5),(2,58.5)):
            gates.append(dict(resource=f'bank_{bank}_rear_lane_{lane}',kind='HANGAR',variant=v,stage=0,frame=frame(x,-1030,z),width=33,height=75,hangar_stack=dict(open_ticks=120,close_ticks=180,depth_direction=-1),supports=[]))
        rows=[(f'bank_{b}_upper_lane_{lane}',-948.98,z) for b,z in ((1,124.5),(2,76.5),(3,28.5))]
        rows += [(f'bank_1_surface_lane_{lane}',-466.98,124.5),(f'bank_2_surface_lane_{lane}',80.02,-35.5)]
        rows += [(f'bank_2_retained_{i}_lane_{lane}',y,-35.5) for i,y in enumerate((-331.98,-191.98,-51.98),1)]
        for name,y,z in rows:gates.append(horizontal_gate(name,v,x,y,z))
    for v,x in enumerate((-1130,-1250,-1370)):gates.append(horizontal_gate(f'bank_3_surface_lane_{2-v}',v,x,174.02,-1520.5))
    wanted=[r['id'] for r in directory['resources'] if r['kind']=='DOOR'];assert len(gates)==len(wanted)==41 and {g['resource'] for g in gates}==set(wanted) and len(set(wanted))==41
    ordered={g['resource']:g for g in gates};result=dict(schema='projectseele.r53.root-selected-gate-seed.v1',map_author='root',epoch=53,directory_sha256=a.directory_sha256,status='CANDIDATE_CURRENT_FACTORY_EXPORT_PENDING',gates=[ordered[k] for k in wanted],source_inputs=provenance,world_written=False,native_controllers_installed=False)
    path=out/'ROOT_GATE_SEED.json';path.write_text(json.dumps(result,indent=2)+'\n','utf8');print(json.dumps(dict(path=str(path),sha256=sha(path),gates=41,world_written=False)))
def read_gzip(p):return json.loads(gzip.decompress(Path(p).read_bytes()))
def horizontal_gate(name,v,x,y,z):return dict(resource=name,kind='SILO',variant=v,stage=3,frame=dict(position=[x,y,z],quaternion=[0,0,0,1]),width=31,height=31,silo_hatch=dict(opening_x=31,opening_z=31,open_ticks=120,close_ticks=20 if '_surface_lane_' in name else 180,separation_sign=1,beam_bottom=-2.02,service_column_ports=False,upright_guide_ports=True),supports=[])
if __name__=='__main__':main()

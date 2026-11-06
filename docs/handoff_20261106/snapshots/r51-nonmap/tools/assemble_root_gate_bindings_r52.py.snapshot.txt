"""Aggregate Root's constructed real doors and exact closed collision tables."""
import copy,gzip,hashlib,json,math,uuid
from pathlib import Path
import numpy as np
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure

def main():
    root=Path(__file__).resolve().parents[1];out=BASE/'runtime_directory/gates';out.mkdir(parents=True,exist_ok=True);gates=[];owned={};checks=0
    def box_cells(box):
        x,y,z,X,Y,Z=box
        return[dict(position=[xx,yy,zz],closed='minecraft:barrier',open='minecraft:air')for xx in range(x,X+1)for yy in range(y,Y+1)for zz in range(z,Z+1)]
    def add(g,rows):
        nonlocal checks
        g=copy.deepcopy(g);g.setdefault('stage',3)
        g['supports']=[dict(position=c['position'],state=c['state'])for c in g['supports']]
        points=np.asarray([c['position']for c in rows]+[c['position']for c in g['supports']]);lo=tuple(map(int,points.min(0)));hi=tuple(map(int,points.max(0)));a,p=measure(lo,hi)
        def actual(q):x,y,z=q;return p[int(a[y-lo[1],z-lo[2],x-lo[0]])]
        for c in rows:
            q=tuple(c['position']);assert q not in owned,(q,owned.get(q),g['resource']);owned[q]=g['resource'];assert actual(q)==c['closed'],(g['resource'],q,c['closed'],actual(q));checks+=1
        for c in g['supports']:assert actual(c['position'])==c['state'],(g['resource'],c,actual(c['position']));checks+=1
        filename=g['resource']+'_cells.json.gz';encoded=json.dumps([rows],separators=(',',':')).encode('utf8');(out/filename).write_bytes(gzip.compress(encoded,mtime=0))
        g['collision_steps']=dict(cells_file=filename,sha256=hashlib.sha256((out/filename).read_bytes()).hexdigest());g.pop('closed_box',None);gates.append(g)
    for p in [BASE/'launch_hatch_bearings/fifteen_source_matched_hatch_bearings/PLAN.json',BASE/'launch_hatch_bearings/retained_surface_column_nine_bulkheads/PLAN.json',BASE/'bank3_surface_receivers/three_founded_low_receivers/PLAN.json',BASE/'launch_hatch_bearings/upper_seals_above_rear_lintels/PLAN.json']:
        d=json.loads(p.read_text());assert d['world_written']
        for g in d['gates']:
            if p.parent.name=='fifteen_source_matched_hatch_bearings'and'_upper_'in g['resource']:continue
            add(g,box_cells(g['closed_box']))
    folder=root/'artifacts/r52_original_owner_candidate_20261010';d=json.loads((folder/'ACTUAL_FINAL_DOOR_CIVIL_MEASUREMENTS_OCT11.json').read_text())
    for source in d['doors']:
        name=source['id'];v=int(name.split('_')[1])if name.startswith('bay_')else 2-int(name.rsplit('_',1)[1]);ref=source['controlled_collision_table'];data=(folder/ref['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==ref['sha256'];rows=json.loads(gzip.decompress(data))
        g=dict(resource=name,visual=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:'+name)),kind='HANGAR',variant=v,stage=0,frame=dict(position=source['position'],quaternion=source['quaternion']),width=source['width'],height=source['height'],hangar_stack=dict(open_ticks=120,close_ticks=180),supports=[dict(position=c['floor_cell'],state=c['actual_world_state'])for c in source['bearing_points']]);add(g,rows)
    p=BASE/'carrier_service_pits/three_dry_pits_below_original_wet_floors/PLAN.json';original=json.loads(p.read_text());corrected=json.loads((BASE/'carrier_service_pits/downward_hatch_outer_bearing_correction/PLAN.json').read_text())
    corrections={r['id']:r for r in corrected['gates']}
    for source in original['gates']:
        v=source['variant'];ref=source['collision_cells'];data=(p.parent/ref['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==ref['sha256'];rows=json.loads(gzip.decompress(data));rows=[dict(position=c['position'],closed=c['closed_state'],open=c['open_state'])for c in rows]
        # Final actual side-beam feet at Z309/347, from Root's separately
        # installed outer bearing correction; true contact topY=-681.
        cx=(72.5,30.5,-11.5)[v];supports=corrections[source['id']]['support_cells']
        g=dict(resource=source['id'],visual=source['visual_uuid'],kind='SILO',variant=v,stage=0,frame=dict(position=[cx,-678.98,328.5],quaternion=[0,0,0,1]),width=33,height=33,silo_hatch=dict(opening_x=33,opening_z=33,open_ticks=120,close_ticks=180,separation_sign=-1,beam_bottom=-2.02,service_column_ports=True),supports=supports);add(g,rows)
    remote=json.loads((BASE/'air_transport_shaft/actual_machine_bearings_and_cassettes/PLAN.json').read_text());assert remote['world_written']
    for case in remote['cases']:
        horizontal=case['kind']=='horizontal';name='remote_airshaft_surface'if horizontal else'remote_airshaft_south'
        frame=[-1120,68.02,-720]if horizontal else[-1120,-475,-636.5]
        supports=[]
        for c in case['support_cells']:
            q=list(c['position'])
            if not horizontal:
                contact=c['actual_source_contact'];q=[math.floor(contact[0]),round(contact[1])-1,math.floor(contact[2]-1.5)]
            supports.append(dict(position=q,state=c['state']))
        g=dict(resource=name,visual=str(uuid.uuid5(uuid.NAMESPACE_URL,'projectseele:r52:'+name)),kind='SILO'if horizontal else'HANGAR',variant=0,stage=3,frame=dict(position=frame,quaternion=[0,0,0,1]),width=164,height=164 if horizontal else 181,supports=supports)
        if horizontal:g['silo_hatch']=dict(opening_x=164,opening_z=164,open_ticks=160,close_ticks=160,separation_sign=1,beam_bottom=-2.02,service_column_ports=False)
        else:g['hangar_stack']=dict(open_ticks=160,close_ticks=160)
        add(g,box_cells([-1202,68,-802,-1039,68,-639]if horizontal else[-1202,-475,-637,-1039,-295,-636]))
    cannon=json.loads((BASE/'far_cannon_magazine/founded_original_cannon_lift_chamber/PLAN.json').read_text());assert cannon['world_written'];add(cannon['gate'],box_cells(cannon['gate']['closed_box']))
    assert len(gates)==42
    doc=dict(schema='projectseele.r52.root-measured-gates.v1',map_author='root',status='design',world_written=False,physical_civil_verified=True,native_controllers_installed=False,gates=gates)
    path=out/'ROOT_GATES.json';path.write_text(json.dumps(doc,separators=(',',':')),'utf8')
    receipt=dict(gates=len(gates),moving_cells=len(owned),exact_state_checks=checks,source_file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),world_written=False,native_controllers_installed=False)
    (out/'READBACK.json').write_text(json.dumps(receipt,indent=2),'utf8');print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()

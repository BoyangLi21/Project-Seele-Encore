"""Finite v9 command-door 37 inputs + 51 bidirectional real-player path data."""
from pathlib import Path
from collections import deque
import hashlib,json,math,sys
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import iter_block_entities

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45'
WORLD=ART/'composition_candidates/R45_source_candidate_20261004_v11_01/world'
OUT=ART/'lifts_doors_lifecycle_sol_v2/command17_native_v11_v4'
NORMAL={'north':(0,-1),'south':(0,1),'east':(1,0),'west':(-1,0)}
def read(p):return json.loads(Path(p).read_text('utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
def write(p,d):Path(p).write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf8'))

def main():
    assert not OUT.exists();OUT.mkdir()
    actual=read(WORLD.parent/'composition_v11_readback.json');assert actual['source1736_unchanged']and actual['phase']=='COMPLETE'
    marker_file=WORLD/'.projectseele_command_sliding_doors_r01.json'
    marker_overlay=ART/'lifts_doors_lifecycle_sol_v2/command16_17_same_level_side_inputs_v1/marker.after.json'
    assert sha(marker_file)==sha(marker_overlay)
    marker=read(marker_file);assert len(marker['doors'])==17
    m=MeasuredWorld(WORLD)
    for d in marker['doors']:m.around(d['lower'],10)
    m.load();assert all(s=='full'for s in m.status.values())
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(-20,-445,225),(80,-400,380),selected_chunks=set(m.selected)))
    inputs=[];crossings=[];owners=[];proofs=[]
    def full(p):
        p=tuple(p);t=tags.get(p);return dict(pos=list(p),state=m.block(p),full_nbt=None if t is None else t.snbt())
    def outside_auto18(d,p):
        if d['id']!=18:return True
        x,y,z=d['lower'];lo=[x-1 if d['axis']=='x'else x,y,z-1 if d['axis']=='z'else z];hi=[x+2 if d['axis']=='x'else x+1,y+2,z+2 if d['axis']=='z'else z+1]
        a=[p[0]-.300001,p[1],p[2]-.300001];b=[p[0]+.300001,p[1]+1.8,p[2]+.300001]
        inflate=[2.2,.15,2.2]
        return not all(a[k]<hi[k]+inflate[k]and b[k]>lo[k]-inflate[k]for k in range(3))
    def bearing(g,p):
        if g.standing(p)=='STATIC_STANDING':return 'FULL_DATUM'
        if g.clear(p)!='CLEAR':raise RuntimeError('Actual planned body obstruction '+str(p))
        for dx in(-.25,0,.25):
            for dz in(-.25,0,.25):
                x,z=p[0]+dx,p[2]+dz;hit=False
                for y in range(math.floor(p[1])-2,math.floor(p[1])+1):
                    q=math.floor(x),y,math.floor(z);boxes=g.boxes(q);assert boxes is not None
                    hit|=any(q[0]+b[0]<=x<=q[0]+b[3]and q[2]+b[2]<=z<=q[2]+b[5]and p[1]-.65<=y+b[4]<=p[1]+.02 for b in boxes)
                if not hit:raise RuntimeError('Unsupported planned stair footprint '+str(p))
        return 'SHAPED_STEP_NATIVE_REQUIRED'
    def segment(g,a,b):
        y=max(a[1],b[1]);return g.clear([a[0],y,a[2]],target=[b[0],y,b[2]])=='CLEAR'
    def connect(g,a,b):
        if math.dist(a,b)<.001:return[a]
        if abs(a[1]-b[1])>.001:return connect_steps(g,a,b)
        if segment(g,a,b):
            try:
                for t in range(17):bearing(g,[a[k]+(b[k]-a[k])*t/16 for k in range(3)])
                return[a,b]
            except RuntimeError:pass
        def centre(p):return[math.floor(p[0])+.5,a[1],math.floor(p[2])+.5]
        s,e=centre(a),centre(b);queue=deque([s]);previous={tuple(s):None}
        while queue:
            p=queue.popleft()
            if p==e:
                route=[];key=tuple(p)
                while key is not None:route.append(list(key));key=previous[key]
                route=route[::-1];result=[a]+route+[b];result=[p for i,p in enumerate(result)if i==0 or p!=result[i-1]]
                if all(segment(g,u,v)for u,v in zip(result,result[1:])):return result
            for dx,dz in((1,0),(-1,0),(0,1),(0,-1)):
                n=[p[0]+dx,a[1],p[2]+dz];key=tuple(n)
                if key in previous or abs(n[0]-a[0])>9 or abs(n[2]-a[2])>9:continue
                if g.standing(n)=='STATIC_STANDING'and segment(g,p,n):previous[key]=tuple(p);queue.append(n)
        raise RuntimeError('No actual bounded approach '+str((a,b)))
    def connect_steps(g,a,b):
        # Only the registered operator-to-port domain is searched. Foot heights
        # are actual collision tops, .5m rises require existing stair support.
        min_y,max_y=min(a[1],b[1])-.5,max(a[1],b[1])+.5
        queue=deque([tuple(a)]);previous={tuple(a):None}
        def tops(x,z):
            values=set()
            for Y in range(math.floor(min_y)-1,math.floor(max_y)+1):
                q=math.floor(x),Y,math.floor(z);boxes=g.boxes(q)
                if boxes is None:continue
                for box in boxes:
                    h=Y+box[4]
                    if min_y<=h<=max_y and q[0]+box[0]<=x<=q[0]+box[3]and q[2]+box[2]<=z<=q[2]+box[5]:values.add(h)
            return sorted(values)
        def stair_between(p,n):
            return any('_stairs['in str(m.block((math.floor(q[0]+dx),math.floor(q[1]-.05),math.floor(q[2]+dz))))for q in(p,n)for dx in(-.25,0,.25)for dz in(-.25,0,.25))
        while queue:
            p=queue.popleft()
            if math.dist(p,b)<.001:
                route=[];key=p
                while key is not None:route.append(list(key));key=previous[key]
                return route[::-1]
            for dx,dz in((.5,0),(-.5,0),(0,.5),(0,-.5)):
                x,z=p[0]+dx,p[2]+dz
                if abs(x-a[0])>7 or abs(z-a[2])>7:continue
                for h in tops(x,z):
                    n=x,h,z
                    if n in previous or abs(h-p[1])>.51 or abs(h-p[1])>.01 and not stair_between(p,n):continue
                    if not segment(g,p,n):continue
                    try:bearing(g,n)
                    except RuntimeError:continue
                    previous[n]=p;queue.append(n)
        raise RuntimeError('No actual existing-stair 3D approach '+str((a,b)))
    for d in marker['doors']:
        mask={tuple(p)for p in d['aperture']}
        class Image:
            world=WORLD
            def block(self,p):return'minecraft:air'if tuple(p)in mask else m.block(p)
            def get(self,x,y,z):return self.block((math.floor(x),math.floor(y),math.floor(z)))
        g=ActualGeometry(Image());x,y,z=d['lower'];dx,dz=NORMAL[d['facing']];ax,az=(1,0)if d['axis']=='x'else(0,1)
        controls=[]
        for c in d['fixedInputContractsR45']:
            pos=c['pos'];operator=c['operator'];assert full(pos)['state']==c['state_after']and full(pos)['full_nbt']is None and full(c['fixed_support']['pos'])==c['fixed_support']
            chosen=operator
            if not outside_auto18(d,chosen):
                options=[]
                for n in range(1,17):
                    p=[operator[0]+dx*c['side']*n*.25,operator[1],operator[2]+dz*c['side']*n*.25]
                    if outside_auto18(d,p)and g.standing(p)=='STATIC_STANDING'and math.dist([p[0],p[1]+1.62,p[2]],[pos[0]+.5,pos[1]+.5,pos[2]+.5])<=4.2:
                        try:connect(g,p,operator)
                        except RuntimeError:continue
                        options.append(p)
                if not options:raise RuntimeError('No actual input18 operator outside auto aura')
                chosen=options[0]
            assert g.standing(chosen)=='STATIC_STANDING'
            entry=dict(id=f"input/{d['id']}/{pos[0]}_{pos[1]}_{pos[2]}",kind='input',door_id=d['id'],side=c['side'],button=full(pos),fixed_support=full(c['fixed_support']['pos']),staging=chosen,marker_original_operator=operator,outside_auto18_aura=outside_auto18(d,chosen),original_alias=c.get('preserved_original_alias',False),native_pass=False)
            inputs.append(entry);controls.append(entry)
        owners.append(dict(id=d['id'],lower=d['lower'],axis=d['axis'],facing=d['facing'],aperture=[full(p)for p in d['aperture']],inputs=controls,auto_proximity_radius=2.2 if d['id']==18 else None))
        for lane in(-1,0,1):
            if d['id']==15:base=[[x+.5+lane,-414,282.5],[x+.5+lane,-413.5,283.1],[x+.5+lane,-413,283.8],[x+.5+lane,-413,284.5],[x+.5+lane,-413,285.5]];north_is_side=-1
            elif d['id']==12 and lane==-1:base=[[21.5,y,281.5],[21.5,y,282.5],[20.5,y,282.5],[20.5,y,283.5],[20.5,y,284.5]];north_is_side=1
            elif d['id']==13 and lane==1:base=[[35.5,y,281.5],[35.5,y,282.5],[36.5,y,282.5],[36.5,y,283.5],[36.5,y,284.5]];north_is_side=1
            else:base=[[x+.5+ax*lane+dx*t,y,z+.5+az*lane+dz*t]for t in(-1.5,-.5,0,.5,1.5)];north_is_side=-1
            for side in(-1,1):
                route=base if side==north_is_side else list(reversed(base));control=next(c for c in controls if c['side']==side and not c['original_alias']);other=next(c for c in controls if c['side']==-side and not c['original_alias'])
                approach=connect(g,control['staging'],route[0]);exit_path=connect(g,route[-1],other['staging']);path=approach+route[1:]+exit_path[1:]
                threshold=[x+.5+ax*lane,y,z+.5+az*lane];ordinal=path.index(threshold)
                checks=[]
                for p in path:checks.append(dict(point=p,body=g.clear(p),bearing=bearing(g,p)))
                assert all(r['body']=='CLEAR'for r in checks)and all(segment(g,a,b)for a,b in zip(path,path[1:]))
                if d['id']==18:assert outside_auto18(d,path[-1])
                case=dict(id=f"cross/{d['id']}/lane{lane}/from{side}",kind='crossing',door_id=d['id'],lane=lane,side=side,button=control['button'],fixed_support=control['fixed_support'],staging=control['staging'],path=path,threshold_waypoint=ordinal,occupied_hold_actual_ticks=120,occupied_expiry_without_auto_refresh_required=d['id']!=18,auto18_policy_observation_only=d['id']==18,native_pass=False)
                crossings.append(case);proofs.append(dict(id=case['id'],only_assigned6_opened_in_RAM=True,full_body_points=checks,full_neighbor_sweeps_clear=True,native_pass=False))
        # Rejected exploratory nodes do not authorize a path or block edit.
        # Returned points and every full sweep above must remain known/CLEAR.
    assert len(inputs)==39 and len(crossings)==102 and len({c['id']for c in inputs+crossings})==141
    write(OUT/'command17_cases141.UNBOUND.json',dict(schema='projectseele.command17-native-inputs.v1',bound=False,world=str(WORLD),actual_source=ref(WORLD.parent/'composition_v11_readback.json'),required_marker_after=ref(marker_file),marker_overlay_installed=True,owners=owners,input_required=39,original_inputs37_kept=True,door_lines_required=51,directed_crossings_required=102,cases=inputs+crossings,all141_native_pass=False,no_case_start_repeated_teleport=True,actual_client_server_3D_stop_and_floor_ACK_required=True,actor_full_NBT_and_strict8tick_restore_required=True))
    write(OUT/'all102_complete_body_bearing_and_neighbor_sweep_proofs.json',proofs)
    write(OUT/'preparation_scope.json',dict(actual_source_v11=True,input_cases39=True,original_inputs37_kept=True,marker_overlay_installed=True,full51_lines_bidirectional102=True,total_cases141=True,only_assigned_door_open_RAM_projection=True,original_37_inputs_102_apertures_preserved=True,ID12_ID13_full_turn_paths=True,ID15_three_lanes_fractional_steps=True,ID18_actual_operator_and_exit_outside_auto_aura=True,ID18_independent_occupied_expiry_NOT_claimed=True,world_written=False,Java_MC_started=False,native_pass=False))
    print('Prepared actual installed v11 COMMAND17 39inputs+102 full-body directed crossings; no world/Java writes.')
if __name__=='__main__':main()

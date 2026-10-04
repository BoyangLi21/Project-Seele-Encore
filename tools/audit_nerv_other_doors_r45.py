"""All679 non-reader doors from a frozen composition, with exact exported geometry."""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, math, sys
from pathlib import Path
sys.dont_write_bytecode=True
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import iter_block_entities, AIR
from prepare_school_hakone_native_r45 import ActualGeometry

ROOT=Path(__file__).resolve().parents[1]
QUEUE=ROOT/'artifacts/rebuild_r45/candidate_transport_acceptance_sol_v1/nerv_security_full_interface_queue.json'
NORMAL={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}
def read(p):return json.loads(Path(p).read_text('utf8'))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n','utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main(args):
    world,out=args.world.resolve(),args.out.resolve()
    assert world.name=='world' and world.parent.parent.name=='composition_candidates' and not out.exists()
    queue=read(QUEUE);objects=[r for r in queue['objects'] if r['kind']!='FULL_NBT_CARD_CONTROLLED_FIXED_READER'];assert len(objects)==679
    marker_path=world/'.projectseele_command_sliding_doors_r01.json';marker=read(marker_path)
    shapes_path=world/'native_collision_shapes.json';traits_path=world/'native_state_traits_r44.json'
    measured=MeasuredWorld(world);requests=collections.defaultdict(set);rows=[]
    for row in objects:
        if 'actual' in row:measured.around(row['actual']['pos'],4)
        elif row['kind']=='REAL_RUNTIME_NO_SAVE_PAIRED_SLIDING':
            measured.around(row['source']['lower'],8)
            for q in row['source']['buttons']:measured.around(q,4)
        else:lo,hi=row['bounds'];measured.box(lo,hi)
    regions=world/'dimensions/projectseele/geofront/region'
    selected_regions={regions/f'r.{cx//32}.{cz//32}.mca'for cx,cz in measured.selected}
    before={str(p):sha(p)for p in selected_regions};measured.load()
    tags=dict(iter_block_entities(world,'projectseele:geofront',(-400,-600,-300),(400,120,800),selected_chunks=set(measured.selected)))
    proposal=None
    if args.proposal:
        folder=args.proposal.resolve();proposal=read(folder/'proposal.json')
        assert proposal['world']==str(world) and proposal['marker_file_proposal']['before_sha256']==sha(marker_path)
        assert proposal['forward_sha256']==sha(folder/'forward.jsonl.gz') and proposal['inverse_sha256']==sha(folder/'inverse.jsonl.gz')
        assert proposal['marker_file_proposal']['after_sha256']==sha(folder/'command_marker.after.json')
        with gzip.open(folder/'forward.jsonl.gz','rt',encoding='utf8')as f:forward=[json.loads(line)for line in f]
        with gzip.open(folder/'inverse.jsonl.gz','rt',encoding='utf8')as f:inverse=[json.loads(line)for line in f]
        assert len(forward)==len({tuple(r['pos'])for r in forward})==len(inverse)
        original_get=measured.get;original=lambda q:original_get(*q);image={}
        for row,reverse in zip(forward,inverse):
            q=tuple(row['pos']);tag=tags.get(q)
            assert original(q)==row['before'] and (None if tag is None else tag.snbt())==row['before_nbt']
            assert row['before_nbt'] is None and row['after_nbt'] is None and row['before'] in AIR
            assert all(reverse[k]==row[v]for k,v in [('pos','pos'),('before','after'),('after','before'),('before_nbt','after_nbt'),('after_nbt','before_nbt')])
            image[q]=row['after']
        measured.block=lambda q:image.get(tuple(q),original(q))
        measured.get=lambda x,y,z:measured.block(tuple(map(math.floor,(x,y,z))))
        marker=read(folder/'command_marker.after.json')
    current_specs={r['id']:r for r in marker['doors']}
    assert len(current_specs)==len(marker['doors'])==17
    traits=read(traits_path)
    def full(q):
        q=tuple(q);tag=tags.get(q)
        return dict(pos=list(q),state=measured.block(q),full_nbt=None if tag is None else tag.snbt())
    def requested(state,q,method):
        if state is not None:requests[(state,method)].add(tuple(q))
    def geo(opened=()):
        class Image:
            def __init__(self):self.world=world
            def block(self,q):return 'minecraft:air'if tuple(q) in opened else measured.block(q)
            def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
        return ActualGeometry(Image())
    raw=geo()
    def standing(geometry,x,y,z):
        # Resolve actual nearby surface heights, never assign an air datum.
        candidates={float(y)}
        for Y in range(math.floor(y)-2,math.floor(y)+2):
            q=(math.floor(x),Y,math.floor(z));boxes=geometry.boxes(q)
            if boxes is None:requested(measured.block(q),q,'exact_collision')
            else:
                for box in boxes:
                    if q[0]+box[0]<=x<=q[0]+box[3] and q[2]+box[2]<=z<=q[2]+box[5] and y-1.1<=Y+box[4]<=y+1.1:candidates.add(Y+box[4])
        for feet in sorted(candidates,key=lambda v:(abs(v-y),-v)):
            point=[x,feet,z];status=geometry.standing(point)
            if status=='STATIC_STANDING':return dict(point=point,status=status)
        return dict(point=[x,y,z],status=geometry.standing([x,y,z]),tested_feet=sorted(candidates))
    def operators(q,facing,geometry):
        dx,dz=NORMAL.get(facing,(0,0));lx,lz=-dz,dx;result=[]
        for distance in (1,1.5,2,2.5,3):
            for lateral in (0,-.5,.5,-1,1):
                for datum in (q[1]-1,q[1]-2,q[1]-3,q[1]):
                    point=standing(geometry,q[0]+.5+dx*distance+lx*lateral,datum,q[2]+.5+dz*distance+lz*lateral)
                    if point['status']=='STATIC_STANDING' and math.dist([point['point'][0],point['point'][1]+1.62,point['point'][2]],[q[0]+.5,q[1]+.5,q[2]+.5])<=4.0:
                        if point not in result:result.append(point)
        return result
    def button(q):
        actual=full(q);state=actual['state'];p=properties(state or '');issues=[];support=None;operator=None
        if state is None:issues.append('UNKNOWN_CELL')
        elif 'ButtonBlock'not in traits.get(state,{}).get('runtime_class',''):issues.append('REGISTERED_INPUT_NOT_ACTUAL_BUTTON')
        else:
            face=p.get('face');dx,dz=NORMAL.get(p.get('facing'),(0,0))
            support=(q[0]-dx,q[1],q[2]-dz)if face=='wall'else(q[0],q[1]-1,q[2])if face=='floor'else(q[0],q[1]+1,q[2])
            backing=full(support);boxes=raw.boxes(support)
            if backing['state'] in AIR:issues.append('INPUT_ATTACHED_TO_DISAPPEARING_AIR')
            elif backing['state']=='minecraft:barrier':issues.append('INPUT_ATTACHED_TO_RUNTIME_BARRIER')
            elif boxes is None:issues.append('UNKNOWN_EXACT_SUPPORT_SHAPE')
            elif not boxes:issues.append('INPUT_HAS_NO_PHYSICAL_BACKING')
            actual_operators=operators(q,p.get('facing'),raw)
            operator=actual_operators[0]if actual_operators else standing(raw,q[0]+.5+dx*1.5,q[1]-1,q[2]+.5+dz*1.5)
            if not actual_operators:issues.append('NO_COMPLETE_SUPPORTED_OPERATOR_IN_FULL_FRONT_REGION')
            requested(state,q,'exact_outline_and_native_canSurvive_actual_context')
        return dict(actual=actual,support=None if support is None else full(support),operator=operator,all_supported_front_operators=actual_operators if support is not None else [],issues=issues,native_use_pass=False)
    for obj in objects:
        kind=obj['kind'];row=dict(id=obj['id'],kind=kind,issues=[],native_pass=False)
        if kind=='REAL_RUNTIME_NO_SAVE_PAIRED_SLIDING':
            old_spec=obj['source'];spec=current_specs[old_spec['id']]
            assert all(spec[k]==old_spec[k]for k in ('id','lower','facing','axis','aperture'))
            lower=spec['lower'];normal=NORMAL[spec['facing']];along=spec['axis']=='x'
            aperture=[tuple(q)for q in spec['aperture']];mask_valid=all(measured.block(q) in AIR|{'minecraft:barrier'} and q not in tags for q in aperture)
            opened=geo(set(aperture)) if mask_valid else raw
            if not mask_valid:row['issues'].append('FOREIGN_COMPLETE_STATE_OR_NBT_IN_RUNTIME_APERTURE')
            lanes=[]
            for span in (-1,0,1):
                x,z=lower[0]+.5+(span if along else 0),lower[2]+.5+(0 if along else span)
                front=standing(opened,x+normal[0],lower[1],z+normal[1]);back=standing(opened,x-normal[0],lower[1],z-normal[1])
                issue=[]
                if front['status']!='STATIC_STANDING' or back['status']!='STATIC_STANDING':issue.append('LANE_WITHOUT_COMPLETE_BEARNING_OR_HEADROOM')
                elif abs(front['point'][1]-back['point'][1])>.01:issue.append('NATIVE_STEP_TRANSITION_REQUIRED')
                elif opened.clear(front['point'],target=back['point'])!='CLEAR':issue.append('OPENED_FULL_BODY_LANE_OBSTRUCTED')
                lanes.append(dict(span=span,front=front,back=back,issues=issue));row['issues']+=issue
            controls=[button(tuple(q))for q in spec['buttons']];row['issues'] += [e for b in controls for e in b['issues']]
            existing=[]
            for X in range(lower[0]-7,lower[0]+8):
                for Y in range(lower[1]-1,lower[1]+4):
                    for Z in range(lower[2]-7,lower[2]+8):
                        q=(X,Y,Z);s=measured.block(q)
                        if s and 'ButtonBlock'in traits.get(s,{}).get('runtime_class',''):existing.append(button(q))
            healthy=[b for b in controls if not b['issues']]
            sides={1 if (b['actual']['pos'][0]-lower[0])*normal[0]+(b['actual']['pos'][2]-lower[2])*normal[1]>0 else -1 for b in healthy}
            if sides!={-1,1}:row['issues'].append('NO_HEALTHY_REGISTERED_MANUAL_INPUT_ON_BOTH_NORMAL_SIDES')
            row.update(source_spec=spec,actual_aperture=[full(q)for q in aperture],complete_open_image_lanes=lanes,registered_controls=controls,all_actual_nearby_buttons=existing)
        elif kind.startswith('ACTUAL_DOOR'):
            q=tuple(obj['actual']['pos']);lower=full(q);upper=full((q[0],q[1]+1,q[2]));state=lower['state'];p=properties(state or '');up=properties(upper['state'] or '')
            if lower!=obj['actual'] or upper!=obj['actual_upper']:row['issues'].append('FROZEN_DIRECTORY_FULL_STATE_NBT_CHANGED')
            if state is None or upper['state'] is None:row['issues'].append('UNKNOWN_COMPLETE_DOOR_PAIR')
            elif state.partition('[')[0]!=upper['state'].partition('[')[0] or up.get('half')!='upper' or any(up.get(k)!=v for k,v in p.items() if k!='half'):row['issues'].append('COMPLETE_PAIR_PROPERTIES_MISMATCH')
            normal=NORMAL.get(p.get('facing'),(0,0));opened=geo()
            if state and state.startswith('projectseele:city_personnel_door'):
                class OpenDoor:
                    def __init__(self):self.world=world
                    def block(self,pt):
                        s=measured.block(pt);return s.replace('open=false','open=true')if tuple(pt)in {q,(q[0],q[1]+1,q[2])} and s else s
                    def get(self,x,y,z):return self.block(tuple(map(math.floor,(x,y,z))))
                opened=ActualGeometry(OpenDoor());classification='FINITE_BRIDGE_INTERLOCK'if q[1]==-394 else'ORIGINAL_COMMAND_FREE_HAND_LATCH'
                fronts=[standing(opened,q[0]+.5+normal[0]*side,q[1],q[2]+.5+normal[1]*side)for side in (-1,1)]
                if classification=='FINITE_BRIDGE_INTERLOCK':
                    # Fine authored grating intentionally has ray-sized holes.
                    # Nine-ray solid-floor rules cannot label it a missing deck.
                    row['issues'].append('ACTUAL_GRATING_AND_STEP_BEARING_REQUIRES_NATIVE_ACTOR')
                elif q==(24,-423,254):row['issues'].append('ORIGINAL_RETAINED_SHAFT_DOOR_NOT_PUBLIC_FLAT_CORRIDOR')
                elif any(a['status']!='STATIC_STANDING'for a in fronts):row['issues'].append('NO_COMPLETE_ACTUAL_OPEN_DOOR_APPROACH')
                row.update(open_approaches=fronts,open_body_sweep=opened.clear(fronts[0]['point'],target=fronts[1]['point'])if fronts[0]['status']==fronts[1]['status']=='STATIC_STANDING'else'UNVERIFIED')
            else:
                classification='NATIVE_MTR_CLIENT_CONTROLLED_PLATFORM_LEAF'
                if lower['full_nbt']is None or upper['full_nbt']is None:row['issues'].append('NATIVE_FACTORY_BE_UNSAVED_REQUIRES_RUNTIME_OBJECT_CAPTURE')
                # Server-side empty APG shapes cannot certify a closed client leaf.
                row['issues'].append('SERVER_SHAPE_NOT_CLIENT_LEAF_LIFECYCLE_PROOF')
                requested(state,q,'actual_client_APG_leaf_OPEN_CLOSED_occupied_sweep_and_actual_BE')
            row.update(classification=classification,actual=lower,actual_upper=upper)
        else:
            lo,hi=obj['bounds'];counter=collections.Counter();be=[]
            for X in range(lo[0],hi[0]+1):
                for Y in range(lo[1],hi[1]+1):
                    for Z in range(lo[2],hi[2]+1):
                        q=(X,Y,Z);s=measured.block(q);counter[s]+=1
                        if q in tags:be.append(full(q))
                        if s is not None and raw.boxes(q) is None:requested(s,q,'exact_native_mechanical_plane_collision')
            if None in counter:row['issues'].append('UNKNOWN_FULL_MECHANICAL_PLANE_CELLS')
            row.update(bounds=obj['bounds'],complete_state_census=dict(counter),complete_plane_cells=sum(counter.values()),all_actual_full_BE=be,
                       source_file=obj['source_file'],source_method=obj['source_method'],root_model_owner=True,mechanical_cycle_clearance='UNVERIFIED_ROOT_ACTUAL_MECHANISM_REQUIRED')
        for state in raw.unknown:
            # A native state name stays unknown; no cube/air fallback is synthesized.
            if not state.startswith('UNMEASURED:'):requests[(state,'exact_collision_unresolved_context')]
        row['issues']=sorted(set(row['issues']));rows.append(row)
    after={str(p):sha(p)for p in selected_regions};assert after==before
    out.mkdir(parents=True)
    summary=dict(total_objects=679,types=dict(collections.Counter(r['kind']for r in rows)),issue_counts=dict(collections.Counter(e for r in rows for e in r['issues'])),
                 native_pass=False,world_written=False,java_started=False,sourcecandidate_unchanged=True,source_regions_sha256=before,
                 native_shape_sha256=sha(shapes_path),native_traits_sha256=sha(traits_path),command_marker_sha256=sha(marker_path),old_queue_sha256=sha(QUEUE))
    summary['candidate_is_heap_only']=proposal is not None
    if proposal is not None:summary['candidate_proposal']=dict(path=str(args.proposal.resolve()/'proposal.json'),sha256=sha(args.proposal.resolve()/'proposal.json'))
    write(out/'all679_complete_object_audit.json',rows);write(out/'summary.json',summary)
    write(out/'exact_native_capture_requests.json',[dict(state=s,method=m,actual_positions=[list(q)for q in sorted(ps)],native_pass=False)for(s,m),ps in sorted(requests.items())])
    print(json.dumps({k:v for k,v in summary.items()if k!='source_regions_sha256'},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--proposal',type=Path);main(p.parse_args())

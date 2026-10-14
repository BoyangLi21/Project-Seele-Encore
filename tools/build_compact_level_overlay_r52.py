"""Retire only the obsolete R52 long level rails; no World writes."""
from pathlib import Path
import argparse,hashlib,json,struct,shutil
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'.Codex/map_complete_20261013/route_audit/compact_level_candidate';OUT.mkdir(parents=True,exist_ok=True)
source_path=ROOT/'src/main/resources/assets/projectseele/mesh/legacy_running_heads_r52.json';source_sha='63fa3c8c4140a34557ee7a07f47a7bc82485900b68d669b11457ba6b1aee3f97';assert hashlib.sha256(source_path.read_bytes()).hexdigest()==source_sha
j=json.loads(source_path.read_text(encoding='utf-8'));retired=[];components=[];native_scope=[]
def clip(poly,z,lower):
    if not poly:return []
    out=[];a=poly[-1];da=a[2]-z;ia=da>=0 if lower else da<=0
    for b in poly:
        db=b[2]-z;ib=db>=0 if lower else db<=0
        if ia!=ib:out.append(a+(b-a)*(da/(da-db)))
        if ib:out.append(b.copy())
        a=b;da=db;ia=ib
    return out
def trimmed(array):
    out=[]
    for t in array.reshape(-1,3,6):
        poly=clip(clip(list(t),28.5,True),127.,False)
        for i in range(1,len(poly)-1):
            q=np.array([poly[0],poly[i],poly[i+1]])
            if np.linalg.norm(np.cross(q[1,:3]-q[0,:3],q[2,:3]-q[0,:3]))>1e-10:out.extend(q.reshape(-1).tolist())
    return out
for v in range(3):
    floor=[];head=[];end=None
    for member in j['members']:
        name=member['part']
        if not name.startswith((f'level_actual/{v}/',f'level_heads/{v}/')):continue
        assert member['frame']=='world'
        values=j['parts'][name];a=np.array(values,dtype=float);digest=hashlib.sha256(b''.join(struct.pack('>d',x)for x in values)).hexdigest();retired.append({'name':name,'role':member['role'],'frame':member['frame'],'original_triangle_count':len(values)//18,'triangles_f64be_sha256':digest})
        if name.endswith('/bank3_finite_end'):
            end=a.reshape(-1,6).copy();end[:,2]+=810.;assert abs(end[:,2].min()-18.49)<1e-8 and abs(end[:,2].max()-28.5)<1e-8
        elif name.startswith('level_actual/'):floor.extend(trimmed(a))
        else:head.extend(trimmed(a))
    assert end is not None and floor and head
    for name,role,values in [(f'level_actual/{v}/compact_96m','static',floor),(f'level_heads/{v}/compact_96m','static_head',head),(f'level_heads/{v}/compact_terminal_10p01m','static_head',end.reshape(-1).tolist())]:
        a=np.array(values).reshape(-1,6)[:,:3];components.append({'name':name,'frame':'world','role':role,'triangles_rgb':values});native_scope.append({'name':name,'actual_vertex_world_extrema':[*a.min(axis=0),*a.max(axis=0)],'triangles':len(values)//18})
assert len(retired)==345
document={'schema':'projectseele.r52.exact-compact-level-rails.v1','original_running_source_sha256':source_sha,'retired_parts':retired,'components':components,'root_plan':{'bank_root_z':[124.5,76.5,28.5],'main_level_z':[28.5,127.0],'bank1_original_tail_join_z':127.0,'bank3_required_forefoot_halfspan':10.0,'finite_pad_halfspan':.004,'terminal_head_margin':.006,'terminal_head_z':[18.49,28.5],'terminal_geometry':'Exact original 72-triangle end bridge per variant rigidly translated by +810m in Z; head/web/base and finite bearing shape unchanged'},'world_written':False}
path=OUT/'legacy_compact_level_r52.json';path.write_text(json.dumps(document,separators=(',',':'))+'\n',encoding='utf-8');receipt={'status':'ROOT_SELECTED_COMPACT_LEVEL_CANDIDATE','world_written':False,'source_sha256':source_sha,'overlay_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'retired_parts':len(retired),'new_parts':len(components),'new_geometry':native_scope,'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(OUT/'CANDIDATE_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in receipt.items()if k!='new_geometry'},indent=2))
if args.publish:
    target=ROOT/'src/main/resources/assets/projectseele/mesh/legacy_compact_level_r52.json';shutil.copyfile(path,target);assert target.read_bytes()==path.read_bytes();print('Published exact compact rail resource',target)

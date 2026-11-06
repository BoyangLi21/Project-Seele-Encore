"""Read actual preserved personnel and their full saved homes; never spawn replacements."""
import argparse,json,uuid
from collections import defaultdict
from pathlib import Path
import nbtlib
from r52_spatial_plan import BASE
from query_blocks import iter_selected_sections
from transplant_s22_authority import read_region,parse_chunk
from move_component_actors_r52 import identity,descendants
from facility_frame_nbt_r52 import unpack_position


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);a=p.parse_args()
    base=a.base.resolve();world=base/'WORLD';out=base/'runtime_directory/staff';out.mkdir(parents=True,exist_ok=True)
    contract=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert contract['map_author']=='root' and contract['epoch']==53 and contract['delivery_scope']['id']=='scope124'
    roster={r['id']:r for r in json.loads((world/'nerv_staff_r15.json').read_text('utf8'))['stations']}
    actual={};issues=[]
    for path in(world/'dimensions/projectseele/geofront/entities').glob('r.*.mca'):
        if not path.stat().st_size:continue
        for blob in read_region(path)[1]:
            if blob is None:continue
            for parent in parse_chunk(blob).get('Entities',[]):
                for tag in descendants(parent):
                    if str(tag.get('id'))!='projectseele:nerv_staff':continue
                    key=str(tag['StaffId']);assert key in roster and key not in actual,key
                    post=roster[key];feet=list(unpack_position(tag['StaffStation']));assert feet==post['feet'],(key,feet,post['feet'])
                    assert str(tag['StaffRole'])==post['role']and str(tag['StaffSkin'])==post['skin']
                    actual[key]=dict(original_uuid=identity(tag),id=key,name=post['name'],role=post['role'],skin=post['skin'],feet=feet,yaw=float(tag['StaffStationYaw']))
    saved=nbtlib.load(world/'dimensions/projectseele/geofront/data/projectseele_staff_r15.dat')['data']['Members']
    saved={str(k):str(uuid.UUID(bytes=b''.join((int(x)&0xffffffff).to_bytes(4,'big')for x in v)))for k,v in saved.items()}
    for key,row in actual.items():assert saved.get(key)==row['original_uuid'],(key,'original saved UUID mismatch')
    selected=defaultdict(set);by_section=defaultdict(list)
    for row in actual.values():
        x,y,z=row['feet'];y-=1;selected[x//16,z//16].add(y//16);by_section[x//16,z//16,y//16].append((row,(x,y,z)))
    seen=set()
    for cx,cz,sy,palette,indices in iter_selected_sections(world,'projectseele:geofront',selected):
        a=indices.reshape(16,16,16)
        for row,(x,y,z)in by_section[cx,cz,sy]:
            s=palette[int(a[y%16,z%16,x%16])];row['support']=[dict(position=[x,y,z],state=s)];seen.add(row['id'])
            if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:water'):issues.append(dict(id=row['id'],floor=[x,y,z],state=s))
    assert seen==set(actual),'Some original homes are in unmeasured chunks'
    missing_saved={key:uid for key,uid in saved.items()if key not in actual}
    uninstantiated=[key for key in roster if key not in saved]
    doc=dict(schema='projectseele.r52.root-original-staff.v1',map_author='root',status='design',world_written=False,
             staff=list(actual.values()),issues=issues,saved_identities_without_actor=missing_saved,roster_posts_without_original_identity=uninstantiated,native_verified=False)
    (out/'ROOT_STAFF.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(dict(original_actors=len(actual),saved_identities=len(saved),roster_posts=len(roster),support_issues=issues,
          saved_identities_without_actor=missing_saved,roster_posts_without_original_identity=len(uninstantiated)),ensure_ascii=False))


if __name__=='__main__':main()

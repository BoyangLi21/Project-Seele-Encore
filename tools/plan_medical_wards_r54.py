"""Read-only exact medical-wing migration. Root alone installs the result."""
import argparse,json,gzip,sys,copy
from pathlib import Path
from collections import Counter
sys.path.append(str(Path(__file__).resolve().parents[1]/'.Codex/map-deps'))
import nbtlib
from query_blocks import read_box,iter_block_entities,AIR
from medical_wards_r54 import layout,make_tag,ROOM_ID
from regional_voxels import canonical_state
DIM='projectseele:geofront';LO=(-49,-528,377);HI=(-7,-519,407)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists();a.out.mkdir(parents=True)
    old=read_box(a.world,DIM,LO,HI);tags=dict(iter_block_entities(a.world,DIM,LO,HI))
    desired,newtags,rooms=layout(-528); desired={q:canonical_state(s) for q,s in desired.items()}
    beds={q for q,s in old.items() if s.startswith('minecraft:white_bed[')}
    assert len(beds)==64 and all(str(tags[q]['id'])=='minecraft:bed' for q in beds)
    for q in beds:desired[q]='minecraft:air'
    retired=[]
    for x,y,z in sorted(beds):
        if 'part=foot' not in old[x,y,z]:continue
        for p,expected in [((x+1,y,z),'projectseele:nerv_wall_panel'),((x+1,y+1,z),'projectseele:nerv_medical_panel[facing=west]')]:
            assert old[p]==expected,(p,old[p]);desired[p]='minecraft:air';retired.append(p)
    # Partition fabric and new bed pairs take precedence over retired furniture.
    recipe,_,_=layout(-528)
    desired.update({q:canonical_state(s) for q,s in recipe.items()})
    protected={q for q in tags if q not in beds}
    protected.update(q for q,s in old.items() if 'nerv_storage_panel' in s or 'period_fixture_part' in s)
    for q in protected:desired.pop(q,None)
    # Preserve original load-bearing columns through the new suspended ceiling.
    for q,s in old.items():
        if s=='projectseele:nerv_structural_panel':desired.pop(q,None)
    rows=[]
    for q,s in sorted(desired.items()):
        before=old[q];bn=tags[q].snbt() if q in tags else None
        an=make_tag(q,*newtags[q]).snbt() if q in newtags else None
        if before==s and bn==an:continue
        assert -48<=q[0]<=-8 and 378<=q[2]<=406
        rows.append(dict(pos=list(q),before=before,after=s,before_nbt=bn,after_nbt=an,owner=ROOM_ID+'/private_wards_r54',reason='Explicitly assigned existing medical room: retire 32-bed template; original three independent recovery wards and entry lobby'))
    inverse=[dict(r,before=r['after'],after=r['before'],before_nbt=r['after_nbt'],after_nbt=r['before_nbt']) for r in rows]
    def write(name,data): (a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    for name,data in [('forwardPatch.json',rows),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos'] for r in rows])]:write(name,data)
    for name,data in [('forward.jsonl.gz',rows),('inverse.jsonl.gz',inverse)]:
        with gzip.open(a.out/name,'wt',encoding='utf8') as f:
            for r in data:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    write('preserved_block_entities.json',[dict(pos=q,state=old[q],snbt=t.snbt()) for q,t in tags.items() if q not in beds])
    after=dict(old);after.update({tuple(r['pos']):r['after'] for r in rows})
    # Test every room floor tile with actual exported native collision boxes, both door states.
    from prepare_school_hakone_native_r45 import ActualGeometry
    class Overlay:
        world=a.world
        def block(self,q):return after.get(tuple(q))
        def get(self,x,y,z):return self.block((x,y,z))
    geo=ActualGeometry(Overlay());cases=[];coverage=[]
    opened=[(x,y,387) for c in (-42,-28,-14) for x in (c-1,c) for y in (-527,-526)]
    for room in rooms:
        c=room['entry'][0];path=geo.path((-28,379),(c+1,401),(-48,378,-8,406),-527,opened)
        assert path,('No valid full-body native-shape route',room['id'],geo.unknown)
        cases.append(dict(id=room['id']+'/entry_to_bedside',path=path,open_doors=opened,native_passed=False))
        aa,bb,zz,ZZ=room['bounds'];floor_tiles=[(x,z) for x in range(aa,bb+1) for z in range(zz,ZZ+1)]
        count=Counter(geo.standing((x+.5,-527,z+.5),opened) for x,z in floor_tiles)
        # Both door lanes must pass when open and be blocked when closed.
        for x in (c-1,c):
            assert geo.clear((x+.5,-527,386.5),opened,(x+.5,-527,388.5))=='CLEAR'
            assert geo.clear((x+.5,-527,386.5),(),(x+.5,-527,388.5))=='ACTUAL_BODY_OBSTRUCTION'
        assert geo.path((-28,379),(c+1,401),(-48,378,-8,406),-527,()) is None, 'Closed ward must be independent from the lobby'
        for x in range(aa,bb+1):
            for z in range(zz,ZZ+1):
                assert after[x,-523,z] not in AIR, ('Ceiling hole',x,z)
        coverage.append(dict(room=room['id'],whole_floor_cells=len(floor_tiles),classification=dict(count),both_open_door_lanes_clear=True,both_closed_lanes_blocked=True))
    assert not geo.unknown,sorted(geo.unknown)
    write('native_cases.json',cases);write('clearance_report.json',coverage)
    write('r54_medical_wards.json',dict(schema='projectseele.medical-wards.r54.v1',replaces_room=ROOM_ID,world_coordinate_frame='installed R52 headquarters offset -93',rooms=rooms,lobby=dict(id=ROOM_ID+'/lobby',bounds=[-48,-8,378,386],floor=-528,entry=[-28,-527,377]),old_bed_template_retired=True,preserved_equipment=[list(q) for q in protected]))
    write('camera_itinerary.json',[dict(id=r['id'],position=[r['entry'][0]+.5,-525.38,389.5],look_at=[r['entry'][0]+.5,-525,402.5],coverage=['private room','bed','head equipment','divided cool ceiling']) for r in rooms]+[dict(id='medical_lobby',position=[-28.5,-525.38,379.5],look_at=[-28,-525,387])])
    # Only these local generation chunks are consulted; current HQ is not maintained by city Static.
    maintained=[];g=a.world/'dimensions/projectseele/geofront/data/city_rigid_generation_r45/chunks'
    for cx,cz in sorted({(r['pos'][0]>>4,r['pos'][2]>>4) for r in rows}):
        p=g/f'{cx}_{cz}.dat'
        if not p.exists():continue
        for e in nbtlib.load(p)['Static']:
            n=int(e['Pos']);q=(n>>38,((n&4095)+2048)%4096-2048,(((n>>12)&67108863)+33554432)%67108864-33554432)
            if q in desired:maintained.append(q)
    assert not maintained,('Update explicit runtime static recipe first',maintained)
    write('installation_manifest.json',dict(world=str(a.world.resolve()),dimension=DIM,bounds=[LO,HI],static_cells=len(rows),old_beds_retired=32,new_private_beds=3,original_nonbed_nbt_preserved=len(tags)-len(beds),new_nbt=10,world_tables=['r54_medical_wards.json'],maintained_static_overlap=maintained,world_written=False,native_passed=False,visual_review='pending root actual game',collision_validation='exported native shapes, whole floor census and open/closed double door sweeps',full_nbt_inverse=True))
    print(json.dumps(dict(cells=len(rows),beds_retired=32,private_wards=3,protected_nonbed_nbt=len(tags)-len(beds),clearance=coverage),ensure_ascii=False))
if __name__=='__main__':main()

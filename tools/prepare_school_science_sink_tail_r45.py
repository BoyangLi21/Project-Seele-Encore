"""Eight measured cells reconnect the complete science-room front work line.

No install command. Existing player, task, native transit and every BE survive.
"""
from pathlib import Path
import argparse
import json
from collections import Counter
from school_hakone_patch_r45 import Candidate, ROOT, ART, sha
from prepare_school_hakone_native_r45 import ActualGeometry, room_group, ordinary_doors
from measure_world_r40 import MeasuredWorld
from query_blocks import iter_block_entities


def main():
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    p.add_argument('--out',type=Path,default=ART/'science_sink_wall_v2');a=p.parse_args()
    c=Candidate(a.world,[254,76,-698,272,82,-688],'r45/school/2-S3/science_rinse_line')
    before=[]
    for i,x in enumerate((257,261,265,269)):
        source=(x,78,-691);target=(271,78,-695+i)
        assert c.measured.block(source)=='minecraft:water_cauldron[level=3]' and c.measured.block(target)=='minecraft:air'
        assert source not in c.tags and target not in c.tags
        c.put(source,'minecraft:air','Remove the failed rear-row basin relocation that cut the entire student desk aisle')
        c.put(target,'minecraft:water_cauldron[level=3]','Whole right-wall rinse line with measured continuous X270 operation aisle; every desk gap remains connected')
        before.append(dict(original=list(source),replacement=list(target),original_state=c.measured.block(source),destination_state=c.measured.block(target)))
    w=MeasuredWorld(a.world);w.box((216,48,-790),(314,102,-668));w.load()
    g_before=ActualGeometry(w)
    class Overlay:
        world=w.world
        def block(self,q):return c.target[tuple(q)]['after'] if tuple(q) in c.target else w.block(q)
        def get(self,x,y,z):
            import math
            return self.block((math.floor(x),math.floor(y),math.floor(z)))
    overlay=Overlay();g_after=ActualGeometry(overlay)
    doors=ordinary_doors(w,'school',[216,48,-790,314,102,-668],g_before)
    rooms=json.loads((a.world/'r45_school_hakone_components.json').read_text('utf8'))['school']['rooms']
    _,raster_before=room_group(rooms,doors,g_before);_,raster_after=room_group(rooms,doors,g_after)
    assert len(raster_before)==len(raster_after)==20
    assert all(not r['disconnected_cells'] for r in raster_after),raster_after
    science=next(r for r in rooms if r.get('kind')=='science');region=science['bounds'];reachable=set(map(tuple,next(r for r in raster_after if r['id']==science['id'])['routed_cells']))
    operations=[];furniture=[]
    tags=dict(iter_block_entities(a.world,'projectseele:geofront',region[:3],region[3:]))
    for x in range(region[0],region[3]+1):
        for y in range(region[1],region[4]+1):
            for z in range(region[2],region[5]+1):
                q=(x,y,z);st=overlay.block(q)
                if not any(t in st for t in ['period_fixture[','residential_chair[','water_cauldron[']):continue
                options=[]
                for xx,zz in sorted(reachable):
                    point=[xx+.5,78,zz+.5]
                    if (point[0]-(x+.5))**2+(point[2]-(z+.5))**2<=2.25**2 and abs(y-78)<=2:
                        options.append(point)
                assert options,('No connected real operator footprint at science furniture',q,st)
                furniture.append(dict(position=list(q),actual_or_exact_candidate_state=st,full_NBT=tags[q].snbt() if q in tags else None,
                    connected_real_operation_footprints=options,native_use_or_reading_ray='UNVERIFIED'))
    for i in range(4):
        q=[270.5,78,-694.5+i];assert g_after.standing(q)=='STATIC_STANDING' and (270,-695+i) in reachable
        operations.append(dict(basin=[271,78,-695+i],front_operator=q,actual_before_and_after_front_support=g_before.standing(q),after_static_support=g_after.standing(q)))
    entry=next(d for d in doors if d['position']==[259,78,-689]);opened={tuple(entry['position']),tuple(entry['upper_position'])}
    lateral=[]
    for n in range(29,72):
        first=[259+n/100,78,-687.5];last=[259+n/100,78,-689.5]
        if g_after.standing(first,opened)=='STATIC_STANDING' and g_after.standing(last,opened)=='STATIC_STANDING' and g_after.clear(first,opened,last)=='CLEAR':lateral.append(n/100)
    assert .5 in lateral
    c.export(a.out,dict(title='Complete 2-S3 science right-wall rinse-line connectivity tail',exact_scope='Four existing native cauldrons relocated, all tables/chairs/boards/floors/BE remain',
        original_author=str((ROOT/'tools/author_school_campus_r45.py').resolve()),original_author_sha256=sha(ROOT/'tools/author_school_campus_r45.py'),
        cause='The first 8-cell rear-row change created ten supported but isolated columns; move the full rinse line to the actual right wall and preserve the continuous right-side operation aisle',
        failed_first_tail=str((ART/'science_sink_tail_v1').resolve()),failed_first_tail_not_redefined_pass=True,
        layout_changes=before,unverified=['Root exact installation','Actual complete room/rinse operation and door passage','Native room photograph','Final installed readback']))
    proof=dict(world_written=False,native_or_art_pass=False,before_all20_rooms=raster_before,after_all20_rooms=raster_after,
        preserved_full_science_BE=[dict(position=list(q),full_NBT=t.snbt()) for q,t in tags.items()],
        every_science_furniture=furniture,all4_basin_front_operations=operations,
        entry=dict(actual_pair=entry,measured_open_swept_supported_centre_offsets=lateral,actual_centre_path_clear=True,
                   player_width=.58,nominal_leaf_cell_width=1,native_passage='UNVERIFIED'),
        first_failed_before_isolated_columns=sum(len(r['disconnected_cells']) for r in raster_before),
        candidate_after_isolated_columns=sum(len(r['disconnected_cells']) for r in raster_after),
        no_other_room_geometry_modified=True,no_whole_world_replay=True)
    (a.out/'whole20_room_and_every_science_operator_proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n','utf8')
    print('Prepared eight exact cells, zero BE changes, no world write',a.out,flush=True)


if __name__=='__main__':main()

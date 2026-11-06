"""Root's measured R50 hangar and original incline ownership, no save writes.

The wet enclosure and original inclined hall are complete components. The
experimental lab under the incline, its entry plugs, the compact lift and the
original upper launch wells are separate retained facilities.
"""
import hashlib,json
import numpy as np
from r52_spatial_plan import BASE,HANGAR
from plan_factory_r20 import guide_y


def main():
    path=BASE/'survey/original_hangar_transfer_launch.npz'
    data=np.load(path);a=data['states'];o=data['origin']
    yy,zz,xx=np.ogrid[:a.shape[0],:a.shape[1],:a.shape[2]]
    x,y,z=xx+o[0],yy+o[1],zz+o[2]
    full=lambda v:np.broadcast_to(v,a.shape).copy()
    wet=full((z>=-294)&(z<=-213)&(y>=-470)&(y<=-338))
    grade=np.asarray([int(np.floor(guide_y(int(q)))) for q in z.ravel()])[None,:,None]
    incline=full((z>=-212)&(z<=-54)&(y>=grade-6)&(y<=grade+86))
    # Complete original galleries lie outside the machinery trench. Their
    # structural piers continue down to the original bearing elevation.
    gallery=full((x>=95)&(z>=-292)&(z<=-54)&(y>=-398)&(y<=-363))
    east_piers=full((x>=112)&(x<=113)&(z>=-279)&(z<=-54)&(((z+279)%24)<=1)&(y>=-467)&(y<-398))
    west_piers=full((x==-34)&(z>=-212)&(z<=-54)&(((z+212)%20)<=1)&(y>=-467)&(y<grade-6))
    # The original incline generator also built the east row at x=94.
    # Its exposed remnants must retire with the hall. Current deep foundations
    # have separate ownership, so this obsolete row is not copied into them.
    obsolete_east_piers=full((x==94)&(z>=-212)&(z<=-54)&(((z+212)%20)<=1)&(y>=-466)&(y<grade-6))
    # Three original loading pits share the old outer wall and partitions.
    # Copy only the bank's lower plant; its original surface wells stay put.
    bank=full((x>=-29)&(x<=89)&(z>=-54)&(z<=-18)&(y>=-444)&(y<=-310))
    preserved_lift=full((x>=89)&(x<=99)&(z>=-56)&(z<=-48))
    move=(wet|incline|gallery|west_piers|east_piers|bank)&~preserved_lift
    old_foundation=full((x>=-43)&(x<=107)&(z>=-292)&(z<=-198)&(y>=-512)&(y<=-471))
    # The lower section of the original vertical wells must stay available
    # for the new inclined connection; copied loading machinery is removed.
    # Keep all well walls above the original loading floor.
    old_well=full((x>=-29)&(x<=89)&(z>=-53)&(z<=-18)&(y>=-410))
    retire=(move|old_foundation|obsolete_east_piers)&~old_well&~preserved_lift
    def owns(p):
        px,py,pz=np.floor(p).astype(int)-o
        return 0<=py<a.shape[0] and 0<=pz<a.shape[1] and 0<=px<a.shape[2] and bool(move[py,pz,px])
    devices=json.loads((BASE/'survey/original_hangar_transfer_launch_devices.json').read_text('utf8'))
    owned_devices=[dict(r,destination=HANGAR.block(r['pos'])) for r in devices if owns(r['pos'])]
    actors=json.loads((BASE/'survey/ORIGINAL_ALL_ACTORS.json').read_text('utf8'))['actors']
    owned_actors=[dict(r,destination=HANGAR.point(r['pos'])) for r in actors if owns(r['pos'])]
    assert len(owned_actors)==15,[(r['id'],r['pos']) for r in owned_actors]
    assert sum(r['id']=='projectseele:training_pilot' for r in owned_actors)==3
    assert sum(r['id'].startswith('projectseele:eva_unit') for r in owned_actors)==3
    assert all(r['pos'][2]!=-52 for r in owned_devices if r['id'].startswith('movingelevators:'))
    assert not any(owns(p) for p in [(30.5,-466.5,-123),(55.5,-466.5,-123),(96,-394,-52),(103,-466,-82),(-34,-466,-118)])
    out=BASE/'hangar_component';out.mkdir(exist_ok=True)
    np.savez_compressed(out/'owner_mask.npz',origin=o,move=move,retire=retire,bank=bank)
    (out/'devices_and_actors.json').write_text(json.dumps(dict(devices=owned_devices,actors=owned_actors),ensure_ascii=False),'utf8')
    report=dict(source=str(path),source_sha256=hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),
        source_component_cells=int(move.sum()),retirement_cells=int(retire.sum()),
        moved_devices=len(owned_devices),moved_actor_graph_members=len(owned_actors),
        source_frame=HANGAR.__dict__,preserved=['old experimental lab and its actors','compact lift 96;-52',
        'upper original surface wells','all MTR objects'],world_written=False,
        pending=['measured destination overlap check','typed device and native lift migration',
                 'bank junction construction and old laboratory interface finishing','runtime frame binding'])
    (out/'COMPONENT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

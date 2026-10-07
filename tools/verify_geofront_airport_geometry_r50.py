"""Exact planned full-width civil geometry review; no game or world writes."""
from pathlib import Path
import gzip,json
from query_blocks import read_box,AIR

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'artifacts/rebuild_r50/underground_airport'
WORLD=ROOT/'artifacts/rebuild_r49/construction/SEELE_R49_WORLD'

def desired(folder):
    result={}
    with gzip.open(folder/'complete_generation_source.jsonl.gz','rt',encoding='utf8')as stream:
        for line in stream:
            r=json.loads(line);result[tuple(r['pos'])]=r['after']
    return result

def main():
    data=desired(P/'candidates/receiver')
    original=read_box(WORLD,'projectseele:geofront',(-35,-486,6),(101,-342,137))
    at=lambda p:data.get(p,original[p])
    failures=[];checks=0
    layout=json.loads((P/'candidates/receiver/receiver_layout.json').read_text('utf8'))
    for v,cx in enumerate((-12,30,72)):
        for x in range(cx-17,cx+18):
            for z in range(83,118):
                checks+=1
                if at((x,-411,z))!='projectseele:nerv_floor_panel'and not(cx-15<=x<=cx+15 and x in(cx-13,cx+13)and at((x,-411,z))=='minecraft:iron_block'):
                    failures.append(['receiver_floor',x,-411,z,at((x,-411,z))])
        for x in range(cx-15,cx+16):
            for z in range(6,101):
                for y in range(-410,-345):
                    checks+=1
                    if at((x,y,z)) not in AIR:failures.append(['mechanical65_air',x,y,z,at((x,y,z))])
        for x in range(cx-16,cx+17):
            for z in range(38,129):
                floor=-411-(z-16)//2
                for y in range(floor+1,floor+7):
                    checks+=1
                    if at((x,y,z)) not in AIR:failures.append(['retained_lower_stair6_air',x,y,z,at((x,y,z))])
    for side in(9,93):
        for z in range(15,35):
            floor=-411 if z<17 else -411-(z-16)//2
            for x in range(side-2,side+3):
                checks+=1
                if at((x,floor,z)) in AIR:failures.append(['new5_stair_bearing',x,floor,z])
                for y in range(floor+1,floor+7):
                    checks+=1
                    if at((x,y,z)) not in AIR:failures.append(['new5_stair6_air',x,y,z,at((x,y,z))])
    del data,original
    data=desired(P/'candidates/airport');gear=[]
    for x in(-454,-426):
        for z in(-280,-260):
            state=data[x,-476,z];assert state=='minecraft:gray_concrete'
            gear.append(dict(point=[x,-475,z],floor=[x,-476,z],state=state))
    assert not failures,failures[:20]
    report=dict(schema=50,receiver_checks=checks,geometry_failures=failures,complete35_receiver_floor=True,
        complete65_axis_air=True,new5_wide_crew_and6_high_headroom=True,retained_lower33_stairs6_high=True,
        actual_mesh_gear_contact=gear,world_written=False,native_verified=False,visual_verified=False)
    (P/'full_width_geometry_audit.json').write_text(json.dumps(report,indent=2),'utf8')
    print(checks,'civil envelope cells; crew/receiver/gear planned geometry PASS; native NOT tested',flush=True)

if __name__=='__main__':main()

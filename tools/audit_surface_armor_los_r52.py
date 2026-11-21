"""Read current Root-owned world blocks and audit the production attack lines. No world write or game launch."""
import json,math,hashlib
from pathlib import Path
import numpy as np
from survey_r52_original_complex import measure, WORLD

SOURCE=Path(__file__).resolve().parents[1]
OUT=SOURCE/'.Codex/r52_surface_armor_attack/results'
FREE={'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light','minecraft:grass','minecraft:fern','minecraft:dandelion','minecraft:poppy'}

def main():
    rows=json.loads((OUT/'ATTACK_ROWS.json').read_text())
    lo=(-12,78,310);hi=(68,145,400)
    states,names=measure(lo,hi)
    def state(point):
        x,y,z=map(math.floor,point)
        assert lo[0]<=x<=hi[0] and lo[1]<=y<=hi[1] and lo[2]<=z<=hi[2],point
        return (x,y,z),names[int(states[y-lo[1],z-lo[2],x-lo[0]])]
    def first(a,b):
        a=np.array(a);b=np.array(b);delta=b-a
        # Exact grid-plane partition. Partial collision shapes are conservatively counted as solid cells.
        ts={0.,1.}
        for k in range(3):
            if abs(delta[k])<1e-12:continue
            for n in range(math.floor(min(a[k],b[k]))+1,math.ceil(max(a[k],b[k]))):
                t=(n-a[k])/delta[k]
                if 0<t<1:ts.add(float(t))
        ts=sorted(ts)
        for l,r in zip(ts,ts[1:]):
            at=a+delta*((l+r)/2);p,s=state(at)
            if s.split('[')[0] not in FREE:return dict(block=list(p),state=s,entry=(a+delta*l).tolist())
        return None
    def plate(hit):
        if not hit:return False
        x,y,z=hit['block'];return 27<=x<=33 and 78<=y<=80 and 352<=z<=358
    proofs=[]
    for row in rows:
        if row['actor']=='sachiel' and row['age']==32:
            hit=first(row['actual_skull_origin'],row['aim']);assert plate(hit),hit
            proofs.append(dict(actor='sachiel',source='production posed skull DQS vertex',first_solid=hit))
    for side in [-1,1]:
        contacts=[]
        for row in rows:
            if row['actor']!='shamshel' or row['side']!=side or not 28<=row['age']<=37:continue
            points=row['points']
            for a,b in zip(points,points[1:]):
                hit=first(a,b)
                if plate(hit):contacts.append(dict(age=row['age'],first_solid=hit))
        assert contacts,(side,'No production whip segment has first solid contact in actual plate')
        proofs.append(dict(actor='shamshel',side=side,source='production original-length FK points',actual_plate_contacts=len(contacts),first_contact=contacts[0]))
    report=dict(world=str(WORLD),world_written=False,game_launched=False,native_acceptance=False,
        collision_shapes='Conservative full-block occupancy; native Minecraft clip remains production damage authority',
        measured_box=[lo,hi],actual_states_sha256=hashlib.sha256(states.tobytes()+json.dumps(names).encode()).hexdigest(),proofs=proofs)
    (OUT/'ACTUAL_WORLD_LOS.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

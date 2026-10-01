"""Measured camera itinerary for the completed assemblies and ecology calibration."""
from pathlib import Path
import gzip,json,math
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44';WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'

def main():
    views=[]
    def add(name,at,target,anchors):
        d=[target[i]-at[i] for i in range(3)];d[1]-=1.62
        views.append(dict(file='r44_calibration_'+name+'.png',position=at,yaw=math.degrees(math.atan2(-d[0],d[2])),pitch=-math.degrees(math.atan2(d[1],math.hypot(d[0],d[2]))),warmupTicks=180,requiredSections=anchors))
    add('emergency_gate',[226.5,81,309.5],[226.5,82.5,302],[[225,81,302],[228,82,303]])
    add('regional_gate',[-360.5,81,726.5],[-360.5,83,733],[[-363,81,733],[-354,82,732]])
    add('inner_checkpoint',[114.5,75,273.5],[120,76.5,273.5],[[119,76,270],[120,75,271]])
    add('arrival_hall',[-387.5,-466,730.5],[-354,-463.5,734],[[-382,-467,730],[-347,-453,732]])
    add('arrival_roof',[-391.5,-460,713.5],[-351,-464,732],[[-395,-453,725],[-349,-453,732]])
    add('low_service_floor',[88.5,-442,-287.5],[27.5,-439.5,-286],[[30,-443,-278],[51,-437,-287]])
    add('low_access_gallery',[103.5,-442,-263.5],[103.5,-440,-90],[[103,-443,-240],[103,-437,-192]])
    add('east_call_console',[66.5,-406,309.5],[65,-405,308],[[65,-405,308],[64,-406,308]])
    add('coordination_console',[34.5,-406,391.5],[38.5,-404.5,393],[[38,-404,393],[36,-405,393]])
    rows=[json.loads(line) for line in gzip.open(ART/'ecology/calibration.forward.jsonl.gz','rt',encoding='utf8')]
    for name,box in [('surface_woodland',[-801,-773,1071,1118]),('surface_meadow',[447,479,-701,-671]),('underground_woodland',[-839,-806,589,630]),('underground_meadow',[874,918,733,786])]:
        selected=[r for r in rows if box[0]<=r['pos'][0]<=box[1] and box[2]<=r['pos'][2]<=box[3] and (r['pos'][1]<0)==name.startswith('underground')]
        assert selected,name
        x=sum(r['pos'][0] for r in selected)/len(selected);z=sum(r['pos'][2] for r in selected)/len(selected);y=min(r['pos'][1] for r in selected)
        at=[x-20,y+8,z-15];target=[x,y+3,z];anchors=[selected[len(selected)//2]['pos'],selected[0]['pos']]
        add(name,at,target,anchors)
    measured=MeasuredWorld(WORLD)
    for row in views:measured.around([row['position'][0],row['position'][1]+1.62,row['position'][2]],0)
    measured.load()
    for row in views:
        eye=[row['position'][0],row['position'][1]+1.62,row['position'][2]];state=measured.block(eye)
        assert state in ('minecraft:air','minecraft:cave_air'),('Camera requires a corrected measured view',row['file'],eye,state)
    out=ART/'space_photos/calibration_itinerary.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(views,indent=2),'utf8')
    print('Measured non-solid cameras:',len(views),out)

if __name__=='__main__':main()

"""Select affected native walk routes and cameras for the two receiving aprons."""
from pathlib import Path
import json,shutil

ROOT=Path(__file__).resolve().parents[1]
WORLD=ROOT/'run/saves/SEELE_FIELD_R40_REVIEW'
OUT=ROOT/'artifacts/world_combat_r40/reception_review'


def intersects(a,b,box):
    return all(max(a[i],b[i])>=box[i] and min(a[i],b[i])<=box[i+3] for i in range(3))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=json.loads((WORLD/'quality_walk_cases.json').read_text('utf8'))
    selected=[]
    for row in rows:
        points=row.get('path',[row.get('start'),row.get('end')])
        boxes=[(6238,73,-6136,6509,84,-6003),(-363,-467,732,-338,-459,743)]
        if any(intersects(a,b,box) for a,b in zip(points,points[1:]) for box in boxes):selected.append(row)
    added=[]
    for pad in json.loads((WORLD/'un_air_reception_r40.json').read_text())['pads']:
        serial=pad['serial'];cx,_,cz=pad['deck'];x0,x1,z0,z1=pad['bounds'];hx,_,hz=pad['approach']
        paths=[[[hx,77,hz],[cx,77,cz]],[[cx,77,cz],[cx,77,z1-2.5]]]
        for z in range(z0+6,z1-4,10):paths.append([[x0+2.5,77,z+.5],[x1-2.5,77,z+.5]])
        for x in range(x0+6,x1-4,10):paths.append([[x+.5,77,z0+2.5],[x+.5,77,z1-2.5]])
        for i,path in enumerate(paths):
            for suffix,route in [('',path),('/return',path[::-1])]:
                added.append(dict(id=f'r40/un_receiving/{serial}/{i}'+suffix,path=route))
    (OUT/'new_paths.json').write_text(json.dumps(added,indent=2))
    (WORLD/'r40_walk_cases.json').write_text(json.dumps(selected+added))
    shutil.copy2(WORLD/'r40_walk_cases.json',OUT/'cases.json')
    old=json.loads((ROOT/'artifacts/world_combat_r40/final_photos/itinerary.json').read_text())
    photos=old[:2]
    for row in photos:row['file']=row['file'].replace('r40_final_','r40_header_')
    for serial,cx in [(0,6466.5),(1,6278.5)]:
        photos.append(dict(file=f'r40_un{serial}_receiving_apron.png',position=[cx-46,105,-5984],yaw=-35,pitch=19,
                           requiredSections=[[int(cx),77,-6048],[int(cx),77,-6090]],warmupTicks=240))
    photos.append(dict(file='r40_board_rear.png',position=[-330.5,-466,748.5],yaw=90,pitch=-3,
                       requiredSections=[[-335,-463,749]],warmupTicks=180))
    (OUT/'photos.json').write_text(json.dumps(photos,indent=2))
    print(json.dumps(dict(affected=len(selected),added=len(added),photos=len(photos))))


if __name__=='__main__':main()

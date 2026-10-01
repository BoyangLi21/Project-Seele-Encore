"""Apply the airport-safe rail alignment and simpler native aircraft taxiways."""
import json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
import nbtlib
import regional_voxels as vox
from build_transit_civil_r20 import arrays,grouped,ff,DECK,AIR,FLOOR,STEEL,GLASS,LIGHT
from build_station_boards_r19 import packed
from plan_transit_r20 import key

OUT=vox.ROOT/'artifacts/world_rebuild_r20/transit/airport_revision'
TROOT=OUT.parent

def main():
    OUT.mkdir(parents=True,exist_ok=True);vox.OUT=OUT;p=vox.Painter();before=json.loads((TROOT/'built1/native_commission.json').read_text(encoding='utf8'));after=json.loads((TROOT/'built3/native_commission.json').read_text(encoding='utf8'));assert after['passed']
    b={x['id']:x for x in before['curves']};a={x['id']:x for x in after['curves']};retired=[r for k,r in b.items() if k not in a and r['mode']=='TRAIN'];added=[r for k,r in a.items() if k not in b and r['mode']=='TRAIN'];mask=defaultdict(set)
    def reserve(box):
        x,y,z,X,Y,Z=map(int,box)
        for xx in range(x,X+1):
            for zz in range(z,Z+1):mask[xx,zz].update(range(y,Y+1))
    for r in retired:
        for xx,yy,zz in r['points']:
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz);reserve((x-3,y-3,z-3,x+3,y+5,z+3))
    oldplaces=json.loads((TROOT/'civil/viaduct_stations_and_streets/places.json').read_text(encoding='utf8'))
    terrain=arrays(vox.ROOT/'artifacts/world_quality_r02/terrain_target.npz');ox,oz=map(int,terrain['origin']);hfield=terrain['height'];nz,nx=hfield.shape
    for x,y,z in oldplaces['piers']:
        if (x,z) in mask:
            h=int(hfield[z-oz,x-ox]);reserve((x-1,h-3,z-1,x+1,y-4,z+1))
    # Reverse only our first review's obsolete elevated railway cells. The
    # original airport pavement and terrain are restored exactly, not guessed.
    delta=next((TROOT/'civil/viaduct_stations_and_streets').glob('applied_*/delta'));chunks={(x//16,z//16) for x,z in mask};restored=0
    for cx,cz in chunks:
        f=delta/f'c.{cx}.{cz}.npz'
        if not f.exists():continue
        with np.load(f) as d:
            minimum=int(d['minimum']);pal=d['palette'];offsets=d['offsets'];old=d['before'];new=d['after']
            for i,n in enumerate(offsets):
                n=int(n);x=cx*16+n%16;z=cz*16+(n//16)%16;y=minimum+n//256
                if y in mask.get((x,z),()):p.match((x,y,z,x,y,z),str(pal[new[i]]),str(pal[old[i]]),'r20/retire_runway_crossing_viaduct');restored+=1
    deck=defaultdict(set);core=defaultdict(set);piers=[]
    for r in added:
        for i,(xx,yy,zz) in enumerate(r['points']):
            x,y,z=math.floor(xx),math.floor(yy),math.floor(zz)
            for dx in range(-3,4):
                for dz in range(-3,4):deck[x+dx,z+dz].add(y)
            for dx in range(-1,2):
                for dz in range(-1,2):core[x+dx,z+dz].add(y)
            if i%43==0 and not any(abs(x-X)<18 and abs(z-Z)<18 for X,Y,Z in piers):piers.append((x,y,z))
    for (x,z),ys in deck.items():
        for y in ys:ff(p,(x,y-3,z,x,y-1,z),DECK,'r20/airport_east_viaduct')
    road=arrays(TROOT/'civil/road_contract.npz')
    for x,y,z in piers:
        h=int(hfield[z-oz,x-ox]);onroad=bool(road['mask'][z-oz,x-ox])
        if not onroad:ff(p,(x-1,h-3,z-1,x+1,y-4,z+1),DECK,'r20/airport_viaduct_pier')
    for (x,z),ys in core.items():
        for y in ys:ff(p,(x,y,z,x,y+5,z),AIR,'r20/airport_rail_body');ff(p,(x,y-1,z,x,y-1,z),'minecraft:gravel','r20/airport_ballast')
    # Airport ground circulation no longer needs to descend to the old rail
    # level. Retire the old dead underpasses and connect terminal, train hall
    # and the existing native boarding stairs at one walking elevation.
    walks=[];boards=[]
    def path(name,points):walks.extend([dict(id='r20/airport/'+name,path=points),dict(id='r20/airport/'+name+'/return',path=list(reversed(points)))])
    for name,sx,sz,oldgx,rz,bx,bz,platform in [('bay',740,1190,650,1430,669,1232,(650,80,1240)),('hakone',-1670,-265,-1610,-20,-1628,-218,(-1610,80,-210))]:
        owner='r20/airport/'+name;terminal=rz-305
        ff(p,(min(sx,oldgx)-6,70,terminal-2,max(sx,oldgx)+6,79,rz-211),'minecraft:stone',owner+'/retire_underpass')
        ff(p,(oldgx-7,81,rz-239,oldgx+7,90,rz-211),AIR,owner+'/retire_old_stair_pavilion')
        ff(p,(oldgx-7,80,rz-239,oldgx+7,80,rz-211),'minecraft:gray_concrete',owner+'/apron')
        ff(p,(sx-5,79,terminal-4,sx+5,88,sz-17),DECK,owner+'/concourse')
        ff(p,(sx-4,81,terminal-4,sx+4,87,sz-16),AIR,owner+'/concourse')
        ff(p,(sx-4,80,terminal-4,sx+4,80,sz-15),FLOOR,owner+'/concourse')
        for x in (sx-5,sx+5):ff(p,(x,82,terminal+1,x,86,sz-18),GLASS,owner+'/concourse_glazing')
        for z in range(terminal+4,sz-17,9):ff(p,(sx-2,88,z,sx+2,88,z+1),LIGHT,owner+'/concourse_lighting')
        # Finish both doorways after the roof and side walls.
        ff(p,(sx-4,81,terminal-4,sx+4,87,terminal),AIR,owner+'/terminal_door')
        ff(p,(sx-4,81,sz-18,sx+4,87,sz-15),AIR,owner+'/station_door')
        zcross=sz+18
        for X,Z in [(sx,z) for z in range(sz-18,zcross+1)]+[(x,zcross) for x in range(min(sx,bx),max(sx,bx)+1)]+[(bx,z) for z in range(zcross,bz+1)]:
            ff(p,(X-3,79,Z-3,X+3,79,Z+3),DECK,owner+'/ground_walk_support');ff(p,(X-3,80,Z-3,X+3,80,Z+3),FLOOR,owner+'/ground_walk')
            # The last metres are the runtime-retracting boarding stair zone.
            if Z<=bz-5:ff(p,(X-2,81,Z-2,X+2,85,Z+2),AIR,owner+'/ground_walk_clearance')
        # Direction strip and a supported, real aircraft departure display.
        at=(sx+4,85,terminal-2);support=(sx+5,85,terminal-2);ff(p,(*support,*support),STEEL,owner)
        p.put(*at,'projectseele:station_departure_board[facing=west]',owner);p.block_entities[at]=nbtlib.Compound({'id':nbtlib.String('projectseele:station_departure_board'),'x':nbtlib.Int(at[0]),'y':nbtlib.Int(at[1]),'z':nbtlib.Int(at[2]),'PlatformCentre':nbtlib.Long(packed(platform)),'Station':nbtlib.String('箱根湾机场' if name=='bay' else '新箱根机场'),'Route':nbtlib.String('F1')});boards.append(dict(pos=at,platform=platform))
        p.block_entities[at]['AirService']=nbtlib.Byte(1)
        path(name+'/terminal_station',[[sx+.5,81,terminal-4.5],[sx+.5,81,sz-16.5]])
        path(name+'/station_boarding',[[sx+.5,81,sz-16.5],[sx+.5,81,zcross+.5],[bx+.5,81,zcross+.5],[bx+.5,81,bz+.5]])
    # Repaint taxi markings from the final native paths. This also covers old
    # redundant yellow curves with the same apron surface before new lines.
    for x0,x1,z0,z1 in [(490,1220,1130,1510),(-2170,-1480,-310,62)]:
        for old in ('minecraft:yellow_concrete','minecraft:yellow_terracotta'):
            p.match((x0,80,z0,x1,80,z1),old,'minecraft:gray_concrete','r20/retire_old_taxi_markings')
    for r in after['curves']:
        if r['mode']!='AIRPLANE' or max(q[1] for q in r['points'])>90 or r['kind'] in ('platform','siding'):continue
        g=r['geometry'];runway=max(g['speedLimit1'],g['speedLimit2'])>=150
        for i,(xx,yy,zz) in enumerate(r['points']):
            x,y,z=math.floor(xx),80,math.floor(zz)
            if runway:
                ff(p,(x,77,z-18,x,79,z+18),'minecraft:stone','r20/runway_foundation');ff(p,(x,80,z-18,x,80,z+18),'minecraft:black_concrete','r20/runway_pavement')
                if (i//16)%2==0:ff(p,(x,80,z-1,x,80,z+1),'minecraft:white_concrete','r20/runway_line')
            else:
                # Existing apron level is 80; all markings are flush.
                ff(p,(x-7,78,z-7,x+7,79,z+7),'minecraft:stone','r20/taxi_foundation');ff(p,(x-7,80,z-7,x+7,80,z+7),'minecraft:gray_concrete','r20/taxi_pavement')
        if not runway:
            for xx,yy,zz in r['points']:x,z=math.floor(xx),math.floor(zz);ff(p,(x,80,z,x,80,z),'minecraft:yellow_concrete','r20/native_taxi_centreline')
    p.meta.update(retired_rail_curves=[r['id'] for r in retired],added_rail_curves=[r['id'] for r in added],restored_cells=restored,walk_nodes=walks,boards=boards,plane_stands_unchanged=True,airport_railway_outside_runways=True)
    p.save_plan('safe_airport_connections');print('Airport revision ready',len(p.ops),flush=True)
if __name__=='__main__':main()

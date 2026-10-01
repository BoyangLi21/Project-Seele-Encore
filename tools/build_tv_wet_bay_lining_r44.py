"""Original wall-mounted wet-bay cast panels, seams and service pipes.

Read-only source measurement. Every plate sits on a complete existing pressure
wall and skips doors, windows, native equipment and the two personnel layers.
This writes a private mesh candidate, never a Minecraft save or installed asset.
"""
from pathlib import Path
import hashlib,json,math
import numpy as np
import build_tv_machinery_r16 as m
from build_tv_shoulder_shells_r44 import export_glb,bounds
from measure_world_r40 import MeasuredWorld
from audit_facility_transit_r44 import Geometry
from query_blocks import AIR
from hangar_tv_design_r44 import FINISHABLE,FULL_CUBE

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/tv_wet_bay_lining_v1'
BLUE=0x536478;EDGE=0x7B8987;SEAM=0x293D48;METAL=0x687A80


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW')
    w.box((-33,-443,-267),(93,-366,-213));w.load();g=Geometry(w)
    m.PARTS.clear();components=[];collision={};dependencies={};plates=[];held=[]
    for variant,cx in enumerate((-12,30,72)):
        origin=np.array([cx+.5,-442.96,-239.5])
        for side in (-1,1):
            wallx=cx+side*20;innerx=cx+side*19
            name=f'wall_cast_lining_{variant}_'+('l' if side<0 else 'r')
            m.use(name);collision[name]=[]
            def eligible(y0,y1,z0,z1):
                for y in range(y0,y1):
                    for z in range(z0,z1):
                        q=(wallx,y,z);state=w.block(q)
                        if state is None:raise RuntimeError(('Unknown declared pressure wall',q))
                        adjacent=w.block((innerx,y,z))
                        if state.partition('[')[0] not in FINISHABLE or g.boxes(state)!=FULL_CUBE:
                            return False,{'position':q,'reason':'Not a full existing pressure cube','state':state}
                        if adjacent is None:raise RuntimeError(('Unknown wall interface',innerx,y,z))
                        if adjacent.partition('[')[0] not in AIR|{'minecraft:light','projectseele:lcl','minecraft:water'}:
                            return False,{'position':[innerx,y,z],'reason':'Existing attached equipment, floor or opening boundary','state':adjacent}
                return True,None
            def facebox(y0,y1,z0,z1,relief,depth,color):
                # Surface X is ±19.5 relative to the real fixed gantry origin.
                x0=19.5-relief-depth if side>0 else -19.5+relief
                local=np.array([x0,y0-origin[1],z0-origin[2]])
                m.box(*local,depth,y1-y0,z1-z0,color)
                collision[name].append([local.tolist(),(local+[depth,y1-y0,z1-z0]).tolist()])
            for y0,y1 in ((-442,-435),(-435,-428),(-428,-421),(-421,-414),(-414,-407),
                          (-407,-400),(-400,-396),(-390,-382),(-382,-374),(-373,-367)):
                for z0 in range(-266,-218,4):
                    z1=min(-214,z0+4)
                    ok,reason=eligible(y0,y1,z0,z1)
                    if not ok:held.append({'variant':variant,'side':side,'panel':[y0,y1,z0,z1],'witness':reason});continue
                    yy0,yy1=y0+.035,y1-.035;zz0,zz1=z0+.035,z1-.035
                    color=BLUE if ((y0+z0)//4)%3 else 0x56687A
                    facebox(yy0,yy1,zz0,zz1,0,.028,SEAM)
                    facebox(yy0+.075,yy1-.075,zz0+.075,zz1-.075,.030,.018,color)
                    # Stepped pressure seam, narrow edge reveal and captive
                    # service fasteners; no equal-thickness giant wall beams.
                    facebox(yy0+.08,yy1-.08,zz0+.065,zz0+.110,.050,.025,METAL)
                    facebox(yy0+.065,yy0+.105,zz0+.11,zz1-.11,.050,.022,EDGE)
                    for y in (yy0+.20,yy1-.20):
                        for z in (zz0+.20,zz1-.20):
                            a=np.array([side*(19.5-.081),y-origin[1],z-origin[2]])
                            b=a+[side*-.025,0,0]
                            m.cylinder(a,b,.043,EDGE,6)
                    plates.append({'variant':variant,'side':side,'bounds_yz':[y0,y1,z0,z1],
                        'maximum_wall_projection_m':.106,'backing':'complete existing known full pressure cubes'})
                    for y in range(y0,y1):
                        for z in range(z0,z1):
                            q=(wallx,y,z);dependencies[q]=w.block(q)
            # Two small service pipes are supported by actual panel bays;
            # they terminate at the crew-layer boundaries rather than cross
            # controllers, windows or a declared public floor.
            for z in (-263,-251,-239,-227,-215):
                for y0,y1 in ((-440,-397),(-390,-375),(-373,-368)):
                    ok,reason=eligible(y0,y1,z,z+1)
                    if not ok:continue
                    for dz in (-.095,.095):
                        a=np.array([side*19.365,y0-origin[1],z+.5+dz-origin[2]])
                        b=a+[0,y1-y0,0];m.cylinder(a,b,.026,SEAM,12)
                        lo=np.minimum(a,b)-.026;hi=np.maximum(a,b)+.026
                        collision[name].append([lo.tolist(),hi.tolist()])
                        for y in np.arange(y0+.20,y1,3.0):
                            a=np.array([side*19.355,y-origin[1],z+.5+dz-origin[2]])
                            b=np.array([side*19.500,y-origin[1],z+.5+dz-origin[2]])
                            m.cylinder(a,b,.035,METAL,10)
                            lo=np.minimum(a,b)-[0,.035,.035];hi=np.maximum(a,b)+[0,.035,.035]
                            collision[name].append([lo.tolist(),hi.tolist()])
                    for y in range(y0,y1):dependencies[wallx,y,z]=w.get(wallx,y,z)
            if m.PARTS[name]:
                components.append({'id':name,'part':name,'variant':variant,'side':side,'motion':'fixed',
                    'pivot_local':[0,0,0],'closed_bounds_local':bounds(m.PARTS[name]),
                    'source_component':'EvaHangarBuilder existing complete wet pressure side facade',
                    'fixed_gantry_origin_world':origin.tolist(),'personnel_footprint_wall_gap_m':.039})
    resource={'stride':6,'frame':'fixed_gantry_local_metres_world_axes','parts':m.PARTS,
        'components':components,'collision_parts':collision,'original_geometry':True,
        'installed':False,'world_write_performed':False,'native_passed':False,'visual_passed':False,
        'reference':'TV cage blue-grey fabricated pressure panels and service risers, original authored geometry only',
        'limit':'Side pressure-wall relief only. Roof, rear doors, observation glazing and exposed edge/cap integration remain separate; complete chamber art is not passed.'}
    path=OUT/'tv_wet_bay_lining_r44.json';path.write_text(json.dumps(resource,separators=(',',':')),encoding='utf8')
    export_glb(m.PARTS,OUT/'tv_wet_bay_lining_r44.glb')
    report={'resource_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'plates':plates,'held_panels':held,
        'source_wall_dependencies':[{'position':list(q),'state':s} for q,s in sorted(dependencies.items())],
        'maximum_geometry_relief_m':.161,'verification_guard_m':.01,
        'two_crews_layers_excluded_y':[[-396,-390],[-367,-355]],
        'minimum_existing_crew_footprint_clearance_m':19.5-.161-.01-19.3,
        'candidate_only':True,'requires':'Full source-dependent world/crew/equipment sweep, original TV proportions review and native geometry/photos before integration'}
    (OUT/'contract.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({'plates':len(plates),'held':len(held),'parts':len(components),
        'triangles':sum(len(p)//18 for p in m.PARTS.values()),'sha256':report['resource_sha256'],
        'source_dependencies':len(dependencies),'crew_gap_m':report['minimum_existing_crew_footprint_clearance_m'],
        'installed':False,'visual_passed':False}))


if __name__=='__main__':main()

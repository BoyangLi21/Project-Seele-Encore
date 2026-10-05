"""R47 civil envelope outside machinery and the retained personnel galleries.

Pure geometry author: no save writer. The inner wet-cell faces are retained
machine/door boundaries, not the exterior shell. The original pressure gates
remain live at Z=-212.5 with their R29 top=-370; no static south wet wall.
"""
from pathlib import Path
import json, math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WEST, EAST, NORTH = -48, 114, -294
BLUE = 'projectseele:nerv_shaft_panel'
STRUCT = 'projectseele:nerv_structural_panel'
GREEN = 'projectseele:nerv_machine_panel'

def components(guide_y):
    """Complete named faces, roof/floor returns, and explicit open ports."""
    parts = []
    def face(name, cells, purpose):
        parts.append(dict(id=name, cells=dict(cells), purpose=purpose,
                          door_state='STATIC_SEALED_FACE'))
    for x, name in ((WEST, 'west'), (EAST, 'east')):
        face('wet/common_outer_'+name,
             (((x,y,z),STRUCT if y in (-468,-355) else BLUE)
              for y in range(-468,-354) for z in range(NORTH,-212)),
             'Outside shared galleries, all three capsules and full rear-door pockets')
    face('wet/common_outer_north',
         (((x,y,NORTH),STRUCT if y in (-468,-355) else BLUE)
          for x in range(WEST,EAST+1) for y in range(-468,-354)),
         'Outside existing north gallery Z=-292 and observation lift Z=-278')
    # Extend the existing common roof only outside its original footprint.
    for y, name, state in ((-355,'roof',BLUE),(-468,'foundation_pan',STRUCT)):
        face('wet/common_'+name+'_perimeter_extension',
             (((x,y,z),state) for x in range(WEST,EAST+1) for z in range(NORTH,-212)
              if ((x < -40 or x > 104 or z < -289) if name=='roof'
                  else (x < -43 or x > 107 or z < -292))),
             'Complete exterior return tied to the retained common roof/foundation; no interior cap')
    for x,name in ((WEST,'west'),(EAST,'east')):
        face('transfer/outer_'+name,
             (((x,y,z),STRUCT if y in (math.floor(guide_y(z))-6,math.floor(guide_y(z))+86) else GREEN)
              for z in range(-212,-53)
              for y in range(math.floor(guide_y(z))-6,math.floor(guide_y(z))+87)),
             'Outside full cabin sweep and retained middle/upper side galleries')
    for offset,name,state in ((-6,'underside_return',GREEN),(86,'roof_return',STRUCT)):
        face('transfer/'+name,
             (((x,math.floor(guide_y(z))+offset,z),state)
              for z in range(-212,-53) for x in range(WEST,EAST+1)
              if x < -35 or x > 95),
             'Sealed continuous side extensions; original full underside/roof stay unchanged')
    # Side-shell steps overlap above the original gate top and below the
    # inclined sealed pan. Never put a vertical return through the door pocket.
    face('wet_transfer/roof_step_return',
         (((x,y,-213),STRUCT) for x in range(WEST,EAST+1)
          if x < -40 or x > 104 for y in range(-357,-354)),
         'Two-metre roof step entirely above door top -370')
    face('wet_transfer/bottom_step_return',
         (((x,y,-213),STRUCT) for x in range(WEST,EAST+1)
          if x < -35 or x > 95 for y in range(-468,-448)
          if not (-36<=x<=-32 and -468<=y<=-465)),
         'Civil pan step; full five-wide experimental west branch x=-36..-32 remains open at feet -468')
    # Three original launch core openings remain as machinery ports. The
    # observation port is the documented R28 opening, now inside the shell.
    def launch_open(x,y):
        return (any(abs(x-cx)<=16 for cx in (-12,30,72))
                or (89<=x<=99 and -470<=y<=-364)
                or (95<=x<=113 and -394<=y<=-388)
                or (89<=x<=112 and -369<=y<=-364))
    face('transfer_launch/common_front_return',
         (((x,y,-53),STRUCT if y in (-417,-325) else BLUE)
          for x in range(WEST,EAST+1) for y in range(-417,-324)
          if not launch_open(x,y)),
         'Close front exterior including 52/-381/-53; retain full-height carrier ports and existing observation opening')
    for x0,x1,number in ((6,12,0),(48,54,1)):
        for z,name in ((-53,'north'),(-18,'south')):
            face(f'launch/interbay_{number}_{name}_complete_bridge',
                 (((x,y,z),STRUCT if y in (-410,80) else BLUE)
                  for x in range(x0,x1+1) for y in range(-410,81)),
                 'Close inter-bay external seam; does not lengthen lower short partitions Z=-32..-18')
    return parts

def mechanical_envelopes(root=ROOT, interfaces=None):
    """Conservative current rigid meshes plus identified inherited negatives.

    Every local detailed shoulder collision box is swept over its entire
    translation interval. Current carrier envelopes are deliberately broad;
    no JVM articulated-hull execution is claimed here.
    """
    masks=[]
    def box(name,kind,lo,hi):
        masks.append(dict(device=name,kind=kind,lo=list(map(float,lo)),hi=list(map(float,hi))))
    meshbase=root/'artifacts/rebuild_r47/assets/assets/projectseele/mesh'
    shoulder=json.loads((meshbase/'tv_shoulder_shells_r44.json').read_text('utf8'))
    facility=json.loads((meshbase/'tv_facilities_r16.json').read_text('utf8'))
    frame=json.loads((root/'artifacts/rebuild_r44/facility_transit_r44/hangar_tv_calibration_v2/semantic_frame.json').read_text('utf8'))
    def smooth(t):
        t=np.clip(t,0,1);return t*t*(3-2*t)
    def bounds(name):
        v=np.asarray(facility['parts'][name],float).reshape(-1,facility['stride'])[:,:3]
        return v.min(0),v.max(0)
    for variant,cx in enumerate((-12,30,72)):
        for part in shoulder['components']:
            if part.get('variant',variant)!=variant or part['part'].startswith(('thin_side_rails','wall_cast_lining')):continue
            offsets=[]
            for stage in np.linspace(0,1,121):
                if part['motion']=='translation_only_with_exact_facet_pad':
                    d=np.asarray(part['normal'])*2.1*smooth(stage/.25);d[0]+=part['outboard_m']*smooth((stage-.23)/.65)
                elif part['motion']=='telescoping_translation':
                    a,b=part['opening_interval'];d=np.asarray(part['translation_open_local'])*smooth((stage-a)/(b-a))
                else:d=np.zeros(3)
                offsets.append(d+[cx+.5,-442.96,-239.5])
            offsets=np.asarray(offsets)
            for index,(lo,hi) in enumerate(shoulder['collision_parts'][part['part']]):
                box(f'wet/{variant}/{part["part"]}/box{index}','current_shoulder_complete_translation_sweep',
                    np.asarray(lo)+offsets.min(0)-.045,np.asarray(hi)+offsets.max(0)+.045)
        bay=next(b for b in frame['bays'] if b['variant']==variant)
        for key in ('capsule_sweep_negative','carrier_sweep_negative'):
            box(f'wet_transfer/{variant}/{key}','identified_R44_never_static_fill',*bay[key])
        box(f'launch/{variant}/31x31_core','source_complete_launch_core',(cx-15,-412,-51),(cx+16,100,-20))
        for name in facility['parts']:
            if not name.startswith('carrier_') or name=='carrier_ram_unit':continue
            if name.startswith(('carrier_contacts_','carrier_contact_pads_')) and not name.endswith('_'+str(variant)):continue
            lo,hi=bounds(name);extra=np.array([0,-3 if name in ('carrier_deck','carrier_deck_guides') else -64,-3 if name=='carrier_clamp' else 0])
            plus=np.array([0,0,10 if name.startswith(('carrier_contacts_','carrier_contact_pads_')) else 0])
            box(f'carrier/{variant}/{name}','current_mesh_full_transfer_lower_raise_release_envelope',
                lo+[cx+.5,-442,-239.5]+extra,hi+[cx+.5,100,-35.5]+plus)
        lo,hi=bounds('pressure_leaf');hi[1]*=73/65
        for side in (-1,1):
            a,b=lo.copy(),hi.copy()
            if side<0:a[0],b[0]=-hi[0],-lo[0]
            box(f'wet/{variant}/rear_pressure_leaf/{side}','current_gate_full_17m_slide_top_minus370',
                a+[cx+.5+(-17 if side<0 else 0),-443,-212.5],b+[cx+.5+(17 if side>0 else 0),-443,-212.5])
        lo,hi=bounds('carrier_ram_unit')
        for i,m in enumerate(facility.get('carrier_actuator_mounts',{}).get(str(variant),[])):
            samples=[]
            for stroke in (0,min(10,m[3]-m[2]-.28)):
                scale=np.array([1,1,m[3]-m[2]-stroke]);offset=np.array([m[0],m[1],m[2]+stroke]);samples.append((lo*scale+offset,hi*scale+offset))
            box(f'carrier/{variant}/ram{i}','current_ram_complete_stroke_and_transfer',
                np.minimum(samples[0][0],samples[1][0])+[cx+.5,-506,-239.5],np.maximum(samples[0][1],samples[1][1])+[cx+.5,100,-35.5])
        lo,hi=bounds('hatch_panel')
        for y in (-332,-192,-52,80):
            for side in (-1,1):
                for i in range(4):
                    samples=[]
                    for stage in np.linspace(0,1,121):
                        xx=i*4+(16.4-i*4)*smooth((stage-.3)/.7);yy=(1.1+(3-i)*1.1)*smooth(stage/.3)
                        a,b=lo.copy(),hi.copy()
                        if side<0:a[0],b[0]=-hi[0],-lo[0]
                        offset=[cx+.5+side*xx,y+.01+yy,-35.5];samples.append((a+offset,b+offset))
                    box(f'launch/{variant}/hatch/{y}/{side}/{i}','current_121stage_lift_then_stack_envelope',
                        np.min([s[0]for s in samples],0),np.max([s[1]for s in samples],0))
    if interfaces is None:
        interfaces=json.loads((root/'artifacts/rebuild_r47/lifts_navigation/final_navigation_r47/actual26_lift_interfaces.json').read_text('utf8'))
    for lift in interfaces:
        stops=lift['landings'];x,_,z=stops[0]['cabin_centre'];r=7 if x==-360 else 3 if stops[0]['controller'][0]==130 else 2;h=9 if x==-360 else 6
        ys=[s['cabin_centre'][1]for s in stops]
        box(lift['id']+'/cabin','actual_26landing_full_cabin_sweep',(x-r,min(ys)-1,z-r),(x+r+1,max(ys)+h-1,z+r+1))
        for stop in stops:
            X,Y,Z=stop['cabin_centre'];dx,dz={'north':(0,-1),'south':(0,1),'west':(-1,0),'east':(1,0)}[stop['exit']];X+=dx*4;Z+=dz*4
            box(lift['id']+f'/door/{Y}','actual_26landing_full_leaf_pocket',(X-5 if dz else X-.5,Y,Z-.5 if dz else Z-5),(X+6 if dz else X+1.5,Y+3.24,Z+1.5 if dz else Z+6))
    for row in json.loads((root/'artifacts/world_rebuild_r20/lifts/sweep_masks.json').read_text('utf8')):
        if row['group']in {'9;253','130;269','96;-52','-26;-278','63;302','31;321'}:
            box(row['group']+'/template','identified_source_lift_negative',row['sweep'][0],np.asarray(row['sweep'][1])+1)
    return masks

def membership(positions, masks):
    """Sparse exact block/mask intersections; no public navigation substitute."""
    from scipy.spatial import cKDTree
    q=np.asarray(positions,dtype=float).reshape(-1,3);result={}
    if not len(q):return result
    tree=cKDTree(q+.5)
    for m in masks:
        lo,hi=np.asarray(m['lo']),np.asarray(m['hi'])
        candidates=np.asarray(tree.query_ball_point((lo+hi)/2,float(np.max(hi-lo)/2+.5),p=np.inf),dtype=int)
        a=q[candidates]
        ii=candidates[np.all(a+1>lo+1e-6,1)&np.all(a<hi-1e-6,1)]
        for i in ii:result.setdefault(int(i),[]).append(m)
    return result

def author_source(scene, block_entities, guide_y, masks):
    """Complete measured Scene author, preserving old parts/state and BEs."""
    from query_blocks import AIR
    cells={q:s for p in components(guide_y) for q,s in p['cells'].items()}
    selected=list(cells);blocked=membership(selected,masks);written=0
    for i,q in enumerate(selected):
        if i in blocked:raise RuntimeError(('R47 exterior design intersects machinery',q,blocked[i]))
        # R20's Scene uses module LO; its existing protected mask remains final.
        import plan_factory_r20 as f
        if not all(f.LO[k]<=q[k]<=f.HI[k]for k in range(3)):continue
        yy,zz,xx=q[1]-f.LO[1],q[2]-f.LO[2],q[0]-f.LO[0]
        if scene.protected[yy,zz,xx] or q in block_entities:continue
        before=scene.palette[int(scene.after[yy,zz,xx])]
        # Two measured natural grass tufts lie in the named full interbay
        # faces. Replace these exact source members; never type-scan a region.
        natural_face_member=q in {(12,37,-53),(48,41,-18)} and before=='minecraft:grass'
        if before.partition('[')[0] not in AIR and not natural_face_member:continue
        scene.after[yy,zz,xx]=scene.state(cells[q]);written+=1
    return written

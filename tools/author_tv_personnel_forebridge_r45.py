"""Author a shallow, usable cage forebridge as an isolated geometry candidate.

TV reference: privately observed episode-one cage composition. The split
personnel bridge and integrated side castings are observed; telescope motion,
dimensions and playable safety provisions remain our engineering adaptation.
No production assets, world cells or acceptance hashes are overwritten.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import numpy as np
import build_tv_shoulder_shells_r44 as cage
import build_tv_personnel_supports_r44 as support

SURFACES={}
SLOTS={}


def surface(name,x,y,z,w,h,d):
    SURFACES.setdefault(name,[]).append([[x,y,z],[x+w,y+h,z+d]])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mirror_boxes(boxes):
    result = copy.deepcopy(boxes)
    for lo, hi in result:
        lo[0], hi[0] = -hi[0], -lo[0]
    return result


def stage(index, name):
    m = cage.m
    m.use(name)
    x = index * 2.15
    bottom, top = 48.54 - .08 * index, 49.44 + .08 * index
    depth, wall = 1.89 + .14 * index, .055
    z = -18.45 - depth / 2
    for yy, hh, zz, dd in (
            (bottom, wall, z, depth),
            (bottom+wall, top-bottom-2*wall, z, wall),
            (bottom+wall, top-bottom-2*wall, z+depth-wall, wall)):
        m.box(x, yy, zz, 2.33, hh, dd, cage.PAINT)
        cage.physical(name, x, yy, zz, 2.33, hh, dd)
    slots=sorted((centre-.027,centre+.027)for i in range(index)
                 for centre in (-18.45-(1.89+.14*i)/2+.055,-18.45+(1.89+.14*i)/2-.055))
    roof=[];cursor=z
    for low,high in slots:
        roof.append((cursor,low));cursor=high
    roof.append((cursor,z+depth))
    for low,high in roof:
        m.box(x,top-wall,low,2.33,wall,high-low,cage.PAINT)
        cage.physical(name,x,top-wall,low,2.33,wall,high-low)
        surface(name,x,top-wall,low,2.33,wall,high-low)
    SLOTS[name]=[[[x,top-wall,low],[x+2.33,top,high]]for low,high in slots]
    # Etched seams lie flush with the real load-bearing roof. No raised
    # rectangular cover visually contradicts the collision floor.
    for zz in (z+.12, z+depth-.12):
        m.box(x+.09, top+.001, zz, 2.15, .001, .018, cage.DARK)
    # Half-width fastening pairs avoid ten conspicuous square picture frames.
    for xx in (x+.26, x+2.06):
        for zz in (z+.23, z+depth-.23):
            m.cylinder((xx, top, zz), (xx, top+.004, zz), .025, cage.JOINT, 8)
    cage.hazard_phase(x+.02, bottom+.075, z-.004, 2.29, .39)
    m.box(x+.02, bottom+.51, z-.004, 2.29, .023, .010, cage.DARK)
    # Replace the lost tall lower volume with a real narrow reinforcing web.
    # Every stiffener is inside its own hollow sleeve, below the nesting lane.
    for xx in (x+.13, x+2.18):
        m.box(xx, bottom+.055, z+.055, .035, .009, depth-.11, cage.JOINT)
        cage.physical(name, xx, bottom+.055, z+.055, .035, .009, depth-.11)
    if index:
        # The next smaller sleeve is 80mm above this one's bottom: a 55mm
        # floor plus a 25mm replaceable wear strip carries it without a gap.
        for zz in (z+.14,z+depth-.26):
            m.box(x+.02,bottom+.055,zz,2.29,.025,.12,cage.DARK)
            cage.physical(name,x+.02,bottom+.055,zz,2.29,.025,.12)
    # Slender dark personnel guards are a playable safety adaptation. They
    # remain separate nested lanes and pass through real receiver roof slots.
    for zz in (z+.055,z+depth-.055):
        for xx in (x+.07,x+2.26):
            m.cylinder((xx,top,zz),(xx,top+1.05,zz),.020,cage.DARK,10)
            cage.physical(name,xx-.02,top,zz-.02,.04,1.05,.04)
        for yy in (top+.52,top+1.05):
            m.cylinder((x,yy,zz),(x+2.33,yy,zz),.022,cage.DARK,10)
            cage.physical(name,x,yy-.022,zz-.022,2.33,.044,.044)


def receiver(outer, name):
    m = cage.m
    m.use(name)
    # Exact outer stage bottom48.22 and roof49.76. Keep actual running gaps;
    # do not shrink a hollow body with a bulk scale operation.
    for x,y,z,w,h,d in (
            (10.62,48.07,-20.14,outer-10.62,.105,3.20),
            (10.62,48.175,-20.14,outer-10.62,1.645,.105),
            (10.62,48.175,-17.045,outer-10.62,1.645,.105),
            (outer-.105,48.175,-20.035,.105,1.645,2.99)):
        m.box(x,y,z,w,h,d,cage.JOINT)
        cage.physical(name,x,y,z,w,h,d)
    # Slots are authored in the actual roof, not invisible collision cuts.
    slots=sorted((centre-.027,centre+.027)for i in range(5)
                 for centre in (-18.45-(1.89+.14*i)/2+.055,-18.45+(1.89+.14*i)/2-.055))
    spans=[];cursor=-20.14
    for low,high in slots:
        spans.append((cursor,low));cursor=high
    spans.append((cursor,-16.94))
    for low,high in spans:
        m.box(10.62,49.82,low,.97,.105,high-low,cage.JOINT)
        cage.physical(name,10.62,49.82,low,.97,.105,high-low)
        surface(name,10.62,49.82,low,.97,.105,high-low)
    m.box(11.59,49.82,-20.14,outer-11.59,.105,3.20,cage.JOINT)
    cage.physical(name,11.59,49.82,-20.14,outer-11.59,.105,3.20)
    surface(name,11.59,49.82,-20.14,outer-11.59,.105,3.20)
    SLOTS[name]=[[[10.62,49.82,low],[11.59,49.925,high]]for low,high in slots]
    for x in ([11.22,outer-.57] if outer>14 else [11.20]):
        m.cylinder((x,48.70,-20.14),(x,48.70,-20.31),.30,cage.DARK,32)
        m.cylinder((x,48.70,-20.31),(x,48.70,-20.36),.16,cage.EDGE,24)
    # Bearing pedestals land on the retained side structure below the opening.
    for x in (10.76,outer-.48):
        m.housing(x,47.97,-19.96,.32,.10,.52,.02,cage.PAINT)
        cage.physical(name,x,47.97,-19.96,.32,.10,.52)
    # Low-load sliding pads close the vertical load path to the outer sleeve.
    for x in (10.67,11.14):
        m.box(x,48.175,-19.63,.19,.045,.14,cage.DARK)
        cage.physical(name,x,48.175,-19.63,.19,.045,.14)


def side_landing(outer, name):
    """Integral shallow landing connects receiver roof to the existing ramp."""
    m = cage.m
    m.use(name)
    z0, z1 = -17.225, -16.50
    def original(z):
        return 48.96 + (z+20.50)*3.74/13.92
    def deck(z):
        return 49.925 + (z-z0)/(z1-z0)*(original(z1)-49.925)
    # A solid tapered casting below the deck, not a floating upper sheet.
    cage.slope(8.90,outer,z0,z1,deck(z0),deck(z1),.08,cage.PAINT)
    for a,b in zip(np.linspace(z0,z1,85)[:-1],np.linspace(z0,z1,85)[1:]):
        lo = min(original(a),original(b))-.08
        hi = max(deck(a),deck(b))
        cage.physical(name,8.90,lo,a,outer-8.90,hi-lo,b-a)
        surface(name,8.90,lo,a,outer-8.90,hi-lo,b-a)
    for x in (8.90,outer):
        cage.m.quad((x,original(z0)-.08,z0),(x,deck(z0),z0),
                    (x,deck(z1),z1),(x,original(z1)-.08,z1),cage.PAINT)
    cage.m.quad((8.90,original(z0)-.08,z0),(outer,original(z0)-.08,z0),
                (outer,deck(z0),z0),(8.90,deck(z0),z0),cage.PAINT)
    return {'x_range':[8.90,outer], 'z_range':[z0,z1],
            'receiver_deck_y':49.925, 'apron_join_y':original(z1),
            'maximum_authored_slope':abs(original(z1)-49.925)/(z1-z0),
            'purpose':'Fixed personnel landing into the retained inclined side casting'}


def authored_side(name,front_portal=None):
    """Rebuild complete source members; do not crop arbitrary old triangles."""
    cage.m.use(name)
    if name=='platform_2_r':
        support.platform02_utility()
        support.inspection_edges(name,10.452,front_portal)
    else:
        cage.platform(inspection_portal=(-16.50,-14.50))
        support.inspection_edges(name,13.95,front_portal)
        cage.slope(14.20,14.50,-16.50,-14.50,48.96+4*3.74/13.92,48.96+6*3.74/13.92,.12,cage.JOINT)
        for z in np.arange(-16.50,-14.50,.125):
            end=min(z+.125,-14.50);low=48.96+(z+20.5)*3.74/13.92;high=48.96+(end+20.5)*3.74/13.92
            cage.physical(name,14.20,low-.12,z,.30,high-low+.12,end-z)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.exists():
        raise ValueError('Keep prior candidate evidence; use a fresh directory')
    if 'artifacts' not in args.out.resolve().parts:
        raise ValueError('Private artifact destination required')
    doc=json.loads(args.base.read_text('utf8'))
    base_parts=copy.deepcopy(doc['parts'])
    cage.m.PARTS={}
    cage.COLLISION={}
    for index in range(5):
        stage(index,f'front_stage_{index}_r')
    receiver(14.20,'front_receiver_r')
    receiver(12.20,'front_receiver_2_r')
    landing = {}
    for name,outer in [('platform_r',14.20),('platform_2_r',12.20)]:
        authored_side(name)
        assert cage.m.PARTS[name]==doc['parts'][name],('Source recipe no longer reproduces exact original side',name)
        assert cage.COLLISION[name]==doc['collision_parts'][name],('Source collision recipe changed',name)
        cage.m.PARTS[name]=[];cage.COLLISION[name]=[]
        authored_side(name,(9.02,10.39)if name=='platform_2_r'else(10.25,13.40))
        for lo,hi in cage.COLLISION[name]:
            datum=48.96+(hi[2]+20.50)*3.74/13.92
            if min(abs(hi[1]-datum-offset)for offset in (0,.048,.073))<1e-7:
                SURFACES.setdefault(name,[]).append([lo.copy(),hi.copy()])
        landing[name]=side_landing(outer,name)
    for name in list(cage.m.PARTS):
        if name in ('platform_2_r','front_receiver_2_r'):
            continue
        left=name[:-1]+'l'
        cage.m.PARTS[left]=cage.reflected(cage.m.PARTS[name],-1)
        cage.COLLISION[left]=mirror_boxes(cage.COLLISION[name])
        SURFACES[left]=mirror_boxes(SURFACES.get(name,[]))
        SLOTS[left]=mirror_boxes(SLOTS.get(name,[]))
    doc['parts'].update(cage.m.PARTS)
    doc['collision_parts'].update(cage.COLLISION)
    for row in doc['components']:
        if row['part'] not in cage.m.PARTS:
            continue
        bounds=np.asarray(cage.bounds(doc['parts'][row['part']]))
        delta=np.asarray(row.get('translation_open_local',[0,0,0]))
        row['closed_bounds_local']=bounds.tolist()
        row['sampled_sweep_bounds_local']=[np.minimum(bounds[0],bounds[0]+delta).tolist(),
                                         np.maximum(bounds[1],bounds[1]+delta).tolist()]
    unchanged=[n for n in base_parts if n not in cage.m.PARTS]
    assert all(doc['parts'][n]==base_parts[n] for n in unchanged)
    doc['personnel_forebridge_r45']={
        'standing_surface_boxes':SURFACES,'roof_running_slots':SLOTS,
        'source_sha256':digest(args.base), 'observed_reference':'TV episode-one cage: shallow split personnel bridge, integrated side machinery',
        'original_adaptation':'Five nested stages, dimensions, fixed access landing and safety provisions',
        'world_write':False, 'install_allowed':False, 'native_passed':False,
        'user_accepted':False, 'pending':['Whole assembly exact sweep and load-path checks',
          'Player-width support, guards, doors and full entry/return',
          'Expanded operator occupancy contract and producer',
          'Three original EVA pose/immersion proportions and native art review']}
    args.out.mkdir(parents=True)
    target=args.out/'tv_shoulder_shells_r44.json'
    target.write_text(json.dumps(doc,separators=(',',':')),'utf8')
    visual={row['part']:doc['parts'][row['part']] for row in doc['components']
            if row.get('variant',0)==0 and not row['part'].startswith(('wet_','cage_frame_lower'))}
    cage.export_glb(visual,args.out/'forebridge_candidate.glb')
    cage.preview(visual,args.out/'forebridge_closed_offline.png',
                 camera=[23,68,-53],target=[0,51,-10],resolution=(1400,1000))
    result={'source_sha256':digest(args.base),'candidate_sha256':digest(target),
            'changed_parts':sorted(cage.m.PARTS),'unchanged_parts_count':len(unchanged),
            'landing':landing,'bridge_roof_step_m':.08,'receiver_step_m':.165,
            'world_write':False,'native_passed':False,'install_allowed':False}
    (args.out/'receipt.json').write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps(result))


if __name__=='__main__':
    main()

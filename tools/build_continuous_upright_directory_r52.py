"""Root-owned continuous upright route design, without world writes.

Keep original bay/ramp/bank/exit coordinates. Replace only the withdrawn
stop-and-rotate launch legs with explicit C2 translation curves. This is a
design input, never a clearance or commissioning certificate.
"""
from pathlib import Path
import argparse, copy, hashlib, json, math
import numpy as np
from r52_spatial_plan import BASE

ROOT = Path(__file__).resolve().parents[1]
OUT = BASE / 'continuous_upright'
IDENTITY = [0., 0., 0., 1.]
UPRIGHT = [0., 1., 0., 0.]


def segment(points):
    return {'controls': np.asarray(points, dtype=float).tolist()}


def sample(controls, n=257):
    p = np.asarray(controls, dtype=float)
    t = np.linspace(0., 1., n)
    degree = len(p) - 1
    w = np.array([math.comb(degree, i) * t**i * (1-t)**(degree-i)
                  for i in range(degree+1)])
    return w.T @ p


def corner(a, b, c, distance=10.):
    u = (b-a) / np.linalg.norm(b-a)
    v = (c-b) / np.linalg.norm(c-b)
    p, q = b-u*distance, b+v*distance
    return [p, p+.4*distance*u, p+.8*distance*u,
            q-.8*distance*v, q-.4*distance*v, q]


def reversed_curve(segments):
    return [segment(s['controls'][::-1]) for s in reversed(segments)]


def verify_segments(segments):
    previous = None
    distance = 0.
    for s in segments:
        p = np.asarray(s['controls'])
        assert len(p) in (2, 6) and np.isfinite(p).all()
        tangent = p[1]-p[0]
        if previous is not None:
            assert np.linalg.norm(previous[-1]-p[0]) < 1e-8
            a, b = previous[-1]-previous[-2], tangent
            assert np.dot(a, b)/np.linalg.norm(a)/np.linalg.norm(b) > 1-1e-9
        derivative = (len(p)-1)*np.diff(p, axis=0)
        # Independent numerical authoring sanity check. Production parser
        # must supply its own certified nonzero derivative/error checks.
        assert np.min(np.linalg.norm(sample(derivative, 2049), axis=1)) > .05
        q = sample(p, 2049)
        distance += np.linalg.norm(np.diff(q, axis=0), axis=1).sum()
        previous = p
    return float(distance)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--separated-throats',action='store_true',help='Complete lane separation inside the entry bend; collect lanes only after rising clear of the far bend')
    parser.add_argument('--axial-throats',action='store_true',help='Keep X fixed through both vertical bends; perform lateral travel only after a full-body Z setback')
    parser.add_argument('--spread-level-throats',action='store_true',help='Finish lane separation on the level Z throat before turning laterally')
    parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args();output=args.output.resolve()
    assert output.is_relative_to(BASE.resolve()), 'Root candidate directory required'
    assert sum((args.separated_throats,args.axial_throats,args.spread_level_throats))<=1, 'Choose one finite candidate'
    if args.separated_throats or args.axial_throats or args.spread_level_throats:assert output!=OUT.resolve(), 'Do not replace the current design before complete geometry review'
    output.mkdir(parents=True,exist_ok=True)
    baseline_path = BASE/'runtime_directory/GROUND_DESIGN.json'
    old = json.loads(baseline_path.read_text('utf8'))
    mesh_path = ROOT/'.Codex/r52_continuous_route_migration_20261012/UPRIGHT_FULL_ACTUAL_TRIANGLE_BOUNDS_AND_HEIGHT_SLICES.json'
    mesh = json.loads(mesh_path.read_text('utf8'))
    old_nodes = {n['id']: n for n in old['nodes']}
    old_legs = {l['id']: l for l in old['legs']}
    nodes, legs, routes, reports = {}, {}, [], []
    resources, space_bindings = {}, {}

    def resource(key, kind):
        resources[key] = dict(id=key, kind=kind, component=key)
        return key

    def include_node(key):
        nodes[key] = copy.deepcopy(old_nodes[key])
        assert nodes[key]['foot_frame']['quaternion_xyzw'] == IDENTITY
        return np.asarray(nodes[key]['foot_frame']['translation'])

    def occupy(points, variant):
        # Conservative design reservation only. Final exact swept envelope
        # producer replaces/validates these against source geometry.
        box = mesh['variants'][variant]['actual_complete_assembly']['actual_xyz_bounds_m']
        low, high = np.array(box[:3])-2, np.array(box[3:])+2
        keys = set()
        for q in points:
            a, b = np.floor((q+low)/32).astype(int), np.floor((q+high)/32).astype(int)
            for x in range(a[0], b[0]+1):
                for y in range(a[1], b[1]+1):
                    for z in range(a[2], b[2]+1):
                        key = f'space/c{x}_{y}_{z}'
                        resource(key, 'SPACE'); keys.add(key)
                        space_bindings[key] = dict(resource=key, component=key,
                            spaces=[[x*32,y*32,z*32,(x+1)*32,(y+1)*32,(z+1)*32]])
        return sorted(keys)

    def include_legacy(key):
        for name in (key, key+'/reverse'):
            leg = copy.deepcopy(old_legs[name]); legs[name] = leg
            include_node(leg['from']); include_node(leg['to'])
            for key in leg['rails']: resource(key, 'RAIL')
            resource(leg['support'], 'SUPPORT')
            for key in leg['doors']: resource(key, 'DOOR')
            for key in leg['occupancy']:
                resource(key, 'SPACE')
                if key not in space_bindings:
                    x,y,z = map(int,key.split('/c')[1].split('_'))
                    space_bindings[key]=dict(resource=key,component=key,
                        spaces=[[x*32,y*32,z*32,(x+1)*32,(y+1)*32,(z+1)*32]])

    for unit in old['units']:
        v, lane = unit['variant'], unit['lane']
        prefix = f'unit{v}'
        include_legacy(prefix+'/original_incline')
        for j in (1,2): include_legacy(prefix+f'/bank{j}_to_{j+1}')
        for bank in (1,2,3):
            ready, end = prefix+f'/bank{bank}', prefix+f'/exit{bank}/surface'
            start, finish = include_node(ready), include_node(end)
            # The original ramp ends horizontally. A sub-metre forward bow
            # turns translation upward while the whole assembly stays upright.
            up = start + [0,24,0]
            pieces = [segment([start, start+[0,0,-1], start+[0,0,-2],
                               up-[0,8,0], up-[0,4,0], up])]
            doors = [f'bank_{bank}_upper_lane_{lane}']
            if bank == 2:
                pieces.append(segment([up,finish]))
            else:
                # Actual GeoFront grass on the long corridor falls to -482.
                # Keep the upright 60m body and the lined tunnel below it;
                # the earlier -536 foot endpoint exposed a long surface cut.
                a = np.array([start[0],-549.,start[2]])
                b = np.array([finish[0],-545. if bank==1 else -548.,finish[2]])
                if args.spread_level_throats and bank==3:
                    # A full-height carrier first clears the vertical throat
                    # in Z. All lateral lane separation is then completed
                    # on a level straight before its horizontal turn. The
                    # fixed outer tracks consequently never cut across a
                    # still-vertical neighbour's upper frame.
                    offset=np.array([12. if v==0 else -12. if v==2 else 0.,0.,0.])
                    c,d=a+[0,0,160.]+offset,b-[0,0,160.]+offset
                    s,e=a+[0,0,48.],a+[0,0,112.]+offset
                    t,u=b-[0,0,112.]+offset,b-[0,0,48.]
                    first,last=corner(up,a,s),corner(u,b,finish)
                    entry,leave=corner(e,c,d,32.),corner(c,d,t,32.)
                    def level_spread(p,q):
                        dz=np.array([0.,0.,12.8])
                        return segment([p,p+dz,p+2*dz,q-2*dz,q-dz,q])
                    pieces += [segment([up,first[0]]),segment(first),segment([first[-1],s]),
                               level_spread(s,e),segment([e,entry[0]]),segment(entry),
                               segment([entry[-1],leave[0]]),segment(leave),segment([leave[-1],t]),
                               level_spread(t,u),segment([u,last[0]]),segment(last),segment([last[-1],finish])]
                    first=last=None
                elif args.axial_throats and bank==3:
                    # Fixed-attitude carriers occupy all sixty metres above
                    # the foot platform. A future rail must not move inward
                    # in X while its current carrier is still rising. Keep
                    # both vertical bends in the Y/Z plane, then change X
                    # only beyond the actual complete body's Z footprint.
                    c,d=a+[0,0,96.],b-[0,0,96.]
                    first,last=corner(up,a,c),corner(d,b,finish)
                    entry,leave=corner(a,c,d,48.),corner(c,d,b,48.)
                    pieces += [segment([up,first[0]]),segment(first),
                               segment([first[-1],entry[0]]),segment(entry)]
                    s,t=entry[-1],leave[0]
                    direction=(d-c)/np.linalg.norm(d-c)
                    if v!=1:
                        normal=np.array([direction[2],0.,-direction[0]])
                        offset=normal*(12. if v==0 else -12.)
                        p,q=s+direction*80+offset,t-direction*80+offset
                        pieces += [segment([s,s+direction*16,s+direction*32,
                                             p-direction*32,p-direction*16,p]),
                                   segment([p,q]),
                                   segment([q,q+direction*16,q+direction*32,
                                             t-direction*32,t-direction*16,t])]
                    else:pieces.append(segment([s,t]))
                    pieces += [segment(leave),segment([leave[-1],last[0]]),
                               segment(last),segment([last[-1],finish])]
                    first=last=None
                else:
                    first, last = corner(up,a,b), corner(a,b,finish)
                separated=args.separated_throats and bank==3 and v!=1
                offset=np.array([12. if v==0 else -12.,0.,0.]) if separated else np.zeros(3)
                if separated:
                    # The old normal fan started AFTER this bend and ended
                    # BEFORE the far bend; the fixed neighbouring rail then
                    # crossed a carrier's underside. Open the X spacing in
                    # the already-above-gate bend, before diagonal travel.
                    first=[p.copy() if i<3 else p+offset for i,p in enumerate(first)]
                    last=[p+offset for p in last]
                if first is not None:pieces += [segment([up,first[0]]), segment(first)]
                if first is None:
                    pass
                elif bank == 3 and v != 1 and not separated:
                    # A shallow lane fan keeps independently partitioned
                    # bores clear when fixed-yaw carriers travel diagonally.
                    direction = (b-a)/np.linalg.norm(b-a)
                    normal = np.array([direction[2],0.,-direction[0]])
                    offset = normal*(12. if v == 0 else -12.)
                    s,t = first[-1],last[0]
                    distance = np.linalg.norm(t-s)
                    p,q = s+direction*80+offset,t-direction*80+offset
                    pieces += [segment([s,s+direction*16,s+direction*32,
                                        p-direction*32,p-direction*16,p]),
                               segment([p,q]),
                               segment([q,q+direction*16,q+direction*32,
                                        t-direction*32,t-direction*16,t])]
                    assert distance > 180
                else:
                    pieces.append(segment([first[-1],last[0]]))
                if last is not None:pieces.append(segment(last))
                if separated:
                    # The fixed diagonals remain below the carrier while
                    # it climbs. Only then return to the unchanged exit X.
                    s=last[-1];e=s-offset+[0,48,0]
                    assert e[1]<finish[1]
                    pieces += [segment([s,s+[0,9.6,0],s+[0,19.2,0],
                                        e-[0,19.2,0],e-[0,9.6,0],e]),segment([e,finish])]
                elif last is not None:
                    pieces.append(segment([last[-1],finish]))
                if bank == 1:
                    doors += [f'bank_1_retained_{j}_lane_{lane}' for j in (1,2,3)]
            doors.append(f'bank_{bank}_surface_lane_{lane}')
            length = verify_segments(pieces)
            legid = prefix+f'/exit{bank}/upright_continuous'
            points = np.concatenate([sample(s['controls'],max(65,
                math.ceil(np.linalg.norm(np.ptp(np.array(s['controls']),axis=0)))+1)) for s in pieces])
            rail, support = resource('rail/'+legid,'RAIL'), resource('support/'+legid,'SUPPORT')
            new = dict(id=legid, **{'from':ready,'to':end}, motion='VERTICAL' if bank==2 else 'LAUNCH_INCLINE',
                ticks=max(2,math.ceil(length/180*20)), eva_from_xyzw=UPRIGHT,eva_to_xyzw=UPRIGHT,
                rails=[rail],support=support,doors=[resource(d,'DOOR') for d in doors],
                occupancy=occupy(points,v),centre_curve=dict(segments=pieces))
            legs[legid]=new
            legs[legid+'/reverse']=dict(new,id=legid+'/reverse',**{'from':end,'to':ready},
                centre_curve=dict(segments=reversed_curve(pieces)))
            path=[prefix+'/original_incline']+[prefix+f'/bank{j}_to_{j+1}' for j in range(1,bank)]+[legid]
            departure=prefix+f'/departure/{bank}'; back=prefix+f'/recovery/{bank}'
            route=dict(id=departure,variant=v,bank=bank,lane=lane,
                region='GEOFRONT' if bank==2 else 'SURFACE',port=prefix+f'/exit{bank}/port',legs=path,
                motion_profile=dict(type='continuous_upright',cruise_mps=180.,acceleration_mps2=120.,
                    deceleration_mps2=120.,ready_node=ready))
            routes += [route,dict(route,id=back,reverse_of=departure,legs=[l+'/reverse' for l in reversed(path)])]
            reports.append(dict(route=departure,ascent_curve_length_m=length,segments=len(pieces),
                constant_world_foot_quaternion=IDENTITY,constant_eva_relative_quaternion=UPRIGHT,
                original_transfer_unchanged=True,native_clearance_passed=False))

    for resource_ in old['resources']:
        if resource_['kind']=='DOOR': resources[resource_['id']]=resource_
    document=dict(old,nodes=list(nodes.values()),legs=list(legs.values()),routes=routes,
        resources=list(resources.values()),status='design',
        runtime=dict(old['runtime'],bindings=list(space_bindings.values())),
        root_construction_note='Root continuous upright design. Constant prepared attitude; no turn stations. Exact clearance, physical guides, civil delta and native installation still required.')
    target=output/'GROUND_CONTINUOUS_DESIGN.json'
    target.write_text(json.dumps(document,separators=(',',':')),'utf8')
    report=dict(world_written=False,commissioned=False,baseline_sha256=hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
        input_mesh_sha256=hashlib.sha256(mesh_path.read_bytes()).hexdigest(),
        design_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),routes=reports,
        node_count=len(nodes),leg_count=len(legs),route_count=len(routes),
        caveat='Numerical authoring checks only; parser certificates, real steel and exact swept mesh acceptance pending.')
    report['separated_throats_candidate']=args.separated_throats
    report['axial_throats_candidate']=args.axial_throats
    report['spread_level_throats_candidate']=args.spread_level_throats
    (output/'ROOT_DESIGN_REPORT.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='routes'}),flush=True)


if __name__=='__main__': main()

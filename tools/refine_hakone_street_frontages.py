"""Detail existing measured parcels and approaches; never generate new addresses.

All edits compose with the outdoor grading candidate. Doors, block entities,
railways, and the city lift system retain their current objects and positions.
"""
import argparse,json,math
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from author_hakone_lakefront import Editor
from author_hakone_district_blocks import Frontage,rotate_state
from query_blocks import AIR

SOIL={'minecraft:grass_block','minecraft:dirt','minecraft:stone','minecraft:andesite','minecraft:granite','minecraft:diorite','minecraft:coarse_dirt','minecraft:rooted_dirt','minecraft:podzol'}
PLANTS={'minecraft:grass','minecraft:tall_grass','minecraft:fern','minecraft:large_fern'}
PAVE={'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:gray_concrete','minecraft:polished_andesite','minecraft:gravel','minecraft:cobblestone'}
ROAD={'minecraft:black_concrete','minecraft:white_concrete','projectseele:road_asphalt_slab','projectseele:road_marking_slab'}
WALL={'minecraft:white_terracotta','minecraft:smooth_sandstone','minecraft:light_gray_concrete','minecraft:bricks','minecraft:dark_oak_planks','minecraft:gray_terracotta','minecraft:cyan_terracotta','minecraft:smooth_quartz','minecraft:polished_andesite'}
def bare(s):return s.split('[')[0]


def finish_grounding(a):
    """Resolve one-block raster rounding at measured side walks, not whole hills."""
    e=Editor(a.candidate);check=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    catalog={r['id']:r for r in json.loads((a.candidate/'catalog.json').read_text('utf8'))};resolved=[]
    for row in check.get('buried_remaining',[]):
        x,y,z,X,Y,Z=catalog[row['id']]['occupied_bounds']
        for xx,zz in row['columns']:
            states=[e.state(xx,yy,zz)for yy in range(y,y+5)]
            if any(bare(s)not in SOIL|AIR|PLANTS for s in states):raise ValueError(('Outdoor edge contains a structure',xx,y,zz))
            for yy in range(y+1,y+5):e.put(xx,yy,zz,'minecraft:air')
            e.put(xx,y,zz,'minecraft:stone_bricks')
            # A neighbouring terrace remains at its true grade. Face its low
            # earth edge as a retaining curb rather than slicing another plot.
            dx=-1 if xx<x else 1 if xx>X else 0;dz=-1 if zz<z else 1 if zz>Z else 0
            for yy in range(y,y+4):
                if bare(e.state(xx+dx,yy,zz+dz))in SOIL:e.put(xx+dx,yy,zz+dz,'minecraft:stone_bricks')
        resolved.append(dict(id=row['id'],columns=len(row['columns'])))
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    m.update(regions=regions,cells=sum(r['cells']for r in regions),raster_edge_curbs=resolved)
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    check['errors']=[r for r in check['errors']if r[0]!='outdoor-grounding-pending'];check['buried_remaining']=[];check['raster_edge_curbs']=resolved
    (a.candidate/'functional-check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),'utf8')
    print('Grounded final plot edge columns',sum(r['columns']for r in resolved),flush=True)


def check_walk_width(a):
    """Keep all previously clear three-wide approaches, including bend corners."""
    e=Editor(a.candidate);details=json.loads((a.candidate/'street-details.json').read_text('utf8'))
    groups=defaultdict(set)
    for route in details['paths']:
        for x,y,z in route['points']:
            for dx in range(-1,2):
                for dz in range(-1,2):groups[(x+dx)//512,(z+dz)//512].add((x+dx,y,z+dz))
    errors=[];checked=0;restored=0
    for key,points in sorted(groups.items()):
        for x,y,z in points:
            for yy in (y+1,y+2):
                try:old=e.state(x,yy,z,True);now=e.state(x,yy,z)
                except (KeyError,FileNotFoundError):continue
                if bare(old)not in AIR:continue
                checked+=1
                if bare(now)in AIR|PLANTS or old==now:continue
                if bare(now)=='minecraft:stone_brick_wall':e.put(x,yy,z,old);restored+=1
                else:errors.append(['approach-width-regression',x,yy,z,now])
        e.save();e.regions.clear()
    check=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    check['errors'].extend(errors);check.update(full_width_air_cells_checked=checked,bend_guards_removed=restored)
    (a.candidate/'functional-check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),'utf8')
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=regions,cells=sum(r['cells']for r in regions))
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    print('Existing full-width headroom',checked,'corner guards removed',restored,'errors',len(errors),flush=True)
    repair_walk_edges(a)


def repair_walk_edges(a):
    """Keep the measured approach envelope where terrace interpolation overlaps."""
    e=Editor(a.candidate);p=a.candidate/'functional-check.json';check=json.loads(p.read_text('utf8'))
    changes=[r for r in check['errors']if r[0]=='approach-width-regression'];columns={(r[1],r[3])for r in changes};count=0
    for x,z in sorted(columns):
        for y in range(-128,320):
            old=e.state(x,y,z,True);now=e.state(x,y,z)
            if old==now:continue
            if bare(old)in SOIL|AIR|PLANTS and bare(now)in SOIL|PAVE|AIR|{'projectseele:city_rain_pipe'}:
                e.put(x,y,z,old);count+=1
            elif 'city_rain_gutter'in now and 'outlet=true'in now:e.put(x,y,z,now.replace('outlet=true','outlet=false'))
    unresolved=[]
    for row in changes:
        _,x,y,z,s=row
        if bare(e.state(x,y,z))not in AIR|PLANTS:unresolved.append(row)
    check['errors']=[r for r in check['errors']if r[0]!='approach-width-regression']+unresolved
    check.update(approach_edge_columns_retained=len(columns),approach_edge_cells_restored=count)
    p.write_text(json.dumps(check,ensure_ascii=False,indent=2),'utf8')
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=regions,cells=sum(r['cells']for r in regions))
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    print('Retained measured approach edge columns',len(columns),'remaining errors',len(unresolved),flush=True)


def refine(a):
    rows=json.loads((a.candidate/'catalog.json').read_text('utf8'));m=json.loads((a.candidate/'manifest.json').read_text('utf8'))
    if m.get('street_refinement'):raise ValueError('Use a fresh candidate for another authored pass')
    e=Editor(a.candidate);stats=Counter();objects=[];path_checks=[];errors=[]
    walks=[]
    for r in rows:
        if r.get('footway'):walks.append(dict(id=r['id'],points=[[x,y-1,z]for x,y,z in r['footway']]))
    valley=json.loads((a.gis/'valley-integration-v12/valley-buildings.json').read_text('utf8'))
    for i,p in enumerate(valley['approaches']):walks.append(dict(id='valley-approach/'+str(i),points=p))
    reserved=set()
    for w in walks:
        for x,y,z in w['points']:
            reserved.update((x+dx,z+dz)for dx in range(-2,3)for dz in range(-2,3))
    def state(x,y,z,original=False):
        if not -128<=y<320:return '__missing__'
        try:return e.state(int(x),int(y),int(z),original)
        except (FileNotFoundError,KeyError):return '__missing__'
    def empty(x,y,z):return bare(state(x,y,z))in AIR|PLANTS
    def solid(x,y,z):
        s=bare(state(x,y,z))
        return s in SOIL|PAVE|WALL|{'minecraft:stone_bricks','minecraft:smooth_quartz','minecraft:polished_deepslate'}
    def fixture(ops,supports,kind):
        if any((x,z)in reserved or not empty(x,y,z)for x,y,z,s in ops):return False
        if any(not solid(*p)for p in supports):return False
        for x,y,z,s in ops:e.put(x,y,z,s)
        objects.append(dict(kind=kind,supports=supports,positions=[p[:3]for p in ops]));stats[kind]+=1;return True
    def flush():
        e.save();e.regions.clear()

    for n,r in enumerate(sorted(rows,key=lambda r:(r['occupied_bounds'][0]//512,r['occupied_bounds'][2]//512,r['id']))):
        x,y,z,X,Y,Z=r['occupied_bounds'];site=r.get('site');record=Counter()
        # Ground the complete outdoor plot. Existing paths and drains retain
        # their original surfaces; natural soil alone becomes a side walkway.
        for xx in range(x-3,X+4):
            for zz in range(z-3,Z+4):
                if x<=xx<=X and z<=zz<=Z:continue
                distance=max(x-xx,xx-X,z-zz,zz-Z)
                if distance>2:continue
                if bare(state(xx,y,zz))in SOIL and empty(xx,y+1,zz)and empty(xx,y+2,zz):
                    e.put(xx,y,zz,'minecraft:stone_bricks'if distance==2 else'minecraft:smooth_stone');record['sidewalk_cells']+=1
        if site and site['floors']:
            f=Frontage(site);hx,hz=site['half'];roof=site['floors']*5
            def get(lx,ly,lz):return state(*f.point(lx,ly,lz))
            def put(lx,ly,lz,s):e.put(*f.point(lx,ly,lz),rotate_state(s,site['rotation']))
            # Replace only the measured wooden shell; the closed gables and
            # roof deck underneath stay intact.
            pitched=(r['template']=='valley'and(r.get('kind')=='station'or site['variant']%3))or(r['template']=='district'and site.get('style')=='residential'and site['floors']<=4)
            if pitched:
                extra=int(r['template']=='valley');steps=min(5,hz)if extra else 5
                for step in range(steps-1):
                    for sign,face in[(-1,'south'),(1,'north')]:
                        for lx in range(-hx-1,hx+2):
                            p=(lx,roof+1+step,sign*(hz+extra-step))
                            if get(*p)=='minecraft:dark_oak_planks':put(*p,f'minecraft:dark_oak_stairs[facing={face},half=bottom,shape=straight,waterlogged=false]');record['roof_stair_cells']+=1
            # Back eaves have continuous downpipes at solid corners. A pipe is
            # installed as a complete assembly, never as disconnected pieces.
            pipe_x=[]
            for lx in(-hx,hx):
                if all(bare(get(lx,ly,-hz-1))in AIR and bare(get(lx,ly,-hz))in WALL for ly in range(1,roof)):
                    if solid(*f.point(lx,0,-hz-1)):
                        for ly in range(1,roof-1):put(lx,ly,-hz-1,'projectseele:city_rain_pipe[facing=south]')
                        pipe_x.append(lx);record['complete_downpipes']+=1
            for lx in range(-hx,hx+1):
                if bare(get(lx,roof-1,-hz-1))in AIR and bare(get(lx,roof-1,-hz))in WALL:
                    put(lx,roof-1,-hz-1,'projectseele:city_rain_gutter[facing=south,outlet='+str(lx in pipe_x).lower()+']');record['gutter_cells']+=1
            # Thin awning edge and masonry plinth distinguish the public floor
            # from the repeated upper floor pattern without replacing glazing.
            for lx in range(-hx+1,hx):
                if bare(get(lx,4,hz+2))in WALL|{'minecraft:red_terracotta','minecraft:green_terracotta'}:
                    material='dark_oak'if site.get('style')=='residential'or r['template']=='valley'else'smooth_quartz'
                    put(lx,4,hz+2,f'minecraft:{material}_slab[type=top,waterlogged=false]');record['awning_edge_cells']+=1
            for lx in range(-hx,hx+1):
                if bare(get(lx,1,hz))in WALL:put(lx,1,hz,'minecraft:polished_andesite');record['plinth_cells']+=1
            # Small forecourts have different uses: station waiting benches,
            # residential planted edges, and clear commercial display windows.
            for lx in(-hx+1,hx-1):
                px,py,pz=f.point(lx,0,hz+3)
                ops=[(*f.point(lx,1,hz+3),'minecraft:polished_andesite'),(*f.point(lx,2,hz+3),'minecraft:flowering_azalea'if n%3==0 else'minecraft:azalea')]
                fixture(ops,[[px,py,pz]],'planted_forecourts')
            bx=-hx+3 if hx>=7 else hx-2
            ops=[(*f.point(bx+dx,1,hz+3),rotate_state('minecraft:dark_oak_stairs[facing=north,half=bottom,shape=straight,waterlogged=false]',site['rotation']))for dx in(-1,0,1)]
            fixture(ops,[f.point(bx+dx,0,hz+3)for dx in(-1,0,1)],'frontage_benches')
        stats.update(record)
        if len(e.regions)>3 or n%25==24:
            flush();print('Detailed occupied parcels',n+1,'/',len(rows),flush=True)
    flush()

    # Widen the measured approaches only where there is actual bearing near
    # their floor. Steep outer edges get a parapet outside a three-wide walk.
    for number,w in enumerate(walks):
        points=w['points'];centres=set((x,z)for x,y,z in points);accepted={}
        for i,(x,expected,z)in enumerate(points):
            choices=[yy for yy in range(expected-2,expected+3)if bare(state(x,yy,z))in PAVE and empty(x,yy+1,z)and empty(x,yy+2,z)]
            if not choices:continue
            y=min(choices,key=lambda yy:abs(yy-expected));accepted[x,z]=y
            for dx in range(-2,3):
                for dz in range(-2,3):
                    xx,zz=x+dx,z+dz
                    if not empty(xx,y+1,zz)or not empty(xx,y+2,zz):continue
                    if bare(state(xx,y,zz))not in SOIL|AIR|PLANTS:continue
                    g=next((yy for yy in range(y,y-3,-1)if solid(xx,yy,zz)),None)
                    if g is None:continue
                    if any(bare(state(xx,yy,zz))not in SOIL|AIR|PLANTS for yy in range(g,y+1)):continue
                    for yy in range(g+1,y):e.put(xx,yy,zz,'minecraft:stone_bricks')
                    e.put(xx,y,zz,'minecraft:smooth_stone');stats['widened_path_cells']+=1
            # The central existing walk is an offline check, never a runtime
            # movement gate. New furniture is excluded from all path envelopes.
            path_checks.append([w['id'],x,y,z])
        edge=set()
        for (x,z),y in accepted.items():
            for dx,dz in[(-2,0),(2,0),(0,-2),(0,2)]:
                xx,zz=x+dx,z+dz;ox,oz=xx+dx//2,zz+dz//2
                if any((xx+sx,zz+sz)in centres for sx in(-1,0,1)for sz in(-1,0,1)):continue
                if bare(state(xx,y,zz))not in PAVE or not empty(xx,y+1,zz):continue
                if all(empty(ox,yy,oz)for yy in range(y-2,y+2)):
                    edge.add((xx,y+1,zz))
        for x,y,z in edge:
            connections={k:('low'if any((x+dx,y+dy,z+dz)in edge for dy in(-1,0,1))else'none')for k,dx,dz in [('north',0,-1),('south',0,1),('west',-1,0),('east',1,0)]}
            s='minecraft:stone_brick_wall['+','.join(f'{k}={v}'for k,v in sorted(connections.items()))+',up=true,waterlogged=false]'
            e.put(x,y,z,s);objects.append(dict(kind='path_guard',supports=[[x,y-1,z]],positions=[[x,y,z]]));stats['guardrail_cells']+=1
        if number%25==24 or len(e.regions)>3:flush();print('Detailed approaches',number+1,'/',len(walks),flush=True)
    flush()

    # Crossing marks are tied to existing public approach ends, spaced apart,
    # and applied only to existing carriageway blocks at a matching elevation.
    crossings=[]
    for w in walks:
        x,expected,z=w['points'][-1]
        if any(math.hypot(x-X,z-Z)<45 for X,Z in crossings):continue
        hits=[]
        for xx in range(x-8,x+9):
            for zz in range(z-8,z+9):
                for y in range(expected-2,expected+3):
                    s=state(xx,y,zz)
                    if bare(s)in ROAD and empty(xx,y+1,zz)and empty(xx,y+2,zz):hits.append((xx,y,zz,s))
        if len(hits)<15:continue
        along_x=np.std([p[0]for p in hits])>np.std([p[2]for p in hits]);count=0
        for xx,y,zz,s in hits:
            along=xx-x if along_x else zz-z;across=zz-z if along_x else xx-x
            if abs(along)>3 or abs(across)>7:continue
            mark=(across%3!=2)
            material='projectseele:road_marking_slab'if mark else'projectseele:road_asphalt_slab'
            new=material+s[s.index('['):]if '_slab['in s else'minecraft:white_concrete'if mark else'minecraft:black_concrete'
            e.put(xx,y,zz,new);count+=1
        if count:crossings.append((x,z));stats['marked_crossings']+=1
        if len(e.regions)>3:flush()
    flush()

    # Check changed public spaces and retained entrances, not whole gameplay.
    for obj in objects:
        for p in obj['supports']:
            if not solid(*p):errors.append(['unsupported-detail',obj['kind'],*p])
        if len(e.regions)>3:e.regions.clear()
    for name,x,y,z in path_checks:
        if not empty(x,y+1,z)or not empty(x,y+2,z):errors.append(['approach-headroom',name,x,y,z])
        if len(e.regions)>3:e.regions.clear()
    baseline=json.loads((a.candidate/'before-findings.json').read_text('utf8'));buried_before=sum(bool(r['buried_perimeter_columns'])for r in baseline);remaining=[];doors=0
    catalog={r['id']:r for r in rows}
    for r in baseline:
        b=catalog[r['id']]['occupied_bounds'];x,y,z,X,Y,Z=b
        for xx,yy,zz,s in r['doors']:
            doors+=1
            if state(xx,yy,zz)!=s or state(xx,yy+1,zz)!=state(xx,yy+1,zz,True):errors.append(['retained-door-changed',r['id'],xx,yy,zz])
        bad=[[xx,zz]for xx,zz in r['buried_perimeter_columns']if any(bare(state(xx,yy,zz))in SOIL for yy in range(y+1,y+4))]
        if bad:remaining.append(dict(id=r['id'],columns=bad))
        if len(e.regions)>3:e.regions.clear()
    regions=e.save();m.update(regions=regions,cells=sum(r['cells']for r in regions),street_refinement=dict(stats),bounds_xz=[-2048,-1024,2560,1536])
    (a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    prior=json.loads((a.candidate/'functional-check.json').read_text('utf8'))
    errors.extend(err for err in prior['errors']if err[0]!='detail-authoring-pending')
    # Residual buried perimeter columns must be classified or repaired before
    # the exact-delta installer can accept the candidate.
    if remaining:errors.append(['outdoor-grounding-pending',len(remaining)])
    prior.update(errors=errors,retained_doors_checked=doors,approach_centres_checked=len(path_checks),supported_details_checked=len(objects),buried_before=buried_before,buried_remaining=remaining)
    (a.candidate/'functional-check.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2),'utf8')
    (a.candidate/'street-details.json').write_text(json.dumps(dict(stats=dict(stats),objects=objects,crossings=crossings,paths=walks),ensure_ascii=False),'utf8')
    chunks=[]
    for f in (a.candidate/'delta').glob('*.npz'):
        with np.load(f)as d:chunks.extend(d['coordinates'].tolist())
    (a.candidate/'transport-changed-chunks.json').write_text(json.dumps(chunks),'utf8')
    print(json.dumps(dict(stats=dict(stats),errors=errors[:15],buried_remaining=len(remaining),cells=m['cells'])),flush=True)
    finish_grounding(a)
    check_walk_width(a)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','gis'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--finish-grounding',action='store_true')
    p.add_argument('--check-walk-width',action='store_true')
    p.add_argument('--repair-walk-edges',action='store_true')
    a=p.parse_args()
    if a.finish_grounding:finish_grounding(a)
    elif a.check_walk_width:check_walk_width(a)
    elif a.repair_walk_edges:repair_walk_edges(a)
    else:refine(a)

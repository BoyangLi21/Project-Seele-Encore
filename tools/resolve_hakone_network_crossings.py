"""Resolve observed full-width crossings in an offline candidate, not gameplay."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_dilation,label
from author_hakone_lakefront import Editor
from repair_hakone_surface_ownership import load_grid,sampled
from plan_hakone_network_repair import network_grade
from hakone_earthworks import road_blocks,min_slope_envelope
from plan_ashi_landscape_r54 import NATURAL,SOIL
from verify_hakone_network_candidate import PAVEMENT
from query_blocks import AIR

def run(a):
    e=Editor(a.candidate);d=load_grid(a.plan/'network.npz');x0,z0,x1,z1=map(int,d['bounds'])
    errors=json.loads((a.candidate/'functional-check.json').read_text('utf8'))['errors']
    oldgrade=d['grade2'].copy();oldwalk=d['walk'].copy();ceilings={};touch=set();report=[]
    catalog=json.loads((a.plan/'catalog.json').read_text('utf8'))
    boxes=[r['occupied_bounds']for r in catalog]+json.loads((a.plan/'station-volumes.json').read_text('utf8'))
    def bare(x,y,z):return e.state(x,y,z).split('[')[0]
    def at(x,z):return z-z0,x-x0
    def inside(x,z):return x0<=x<=x1 and z0<=z<=z1
    def room(x,y,z):return any(b[0]-2<=x<=b[3]+2 and b[2]-2<=z<=b[5]+2 and b[1]-1<=y<=b[4]+8 for b in boxes)
    # Detect the actual lowest retained deck over each reported crossing,
    # including its full neighbouring width before changing approach grades.
    for row in errors:
        if row[0]not in {'road-object','actual-road-floor-or-body'}:continue
        _,x,y,z,states=row;touch.add((x,z))
        if any('light_gray_concrete'in s for s in states[1:]):
            for X in range(x-10,x+11):
                for Z in range(z-10,z+11):
                    if not inside(X,Z)or not d['walk'][at(X,Z)]or d['core'][at(X,Z)]:continue
                    h=int((d['grade2'][at(X,Z)]+1)//2)
                    ys=[Y for Y in range(max(-128,min(y,h)-7),min(319,max(y,h)+6)+1)if bare(X,Y,Z)=='minecraft:light_gray_concrete']
                    if ys:
                        lo=min(ys)
                        if lo<=h+3 and lo+8>=h:ceilings[X,Z]=min(ceilings.get((X,Z),320),lo-3)
    for (x,z),h in ceilings.items():d['grade2'][at(x,z)]=min(int(d['grade2'][at(x,z)]),h*2)
    # The eastern retained facility wall is a real room boundary. Move the
    # adjacent street edge outside the wall instead of cutting a hole in it.
    wall=[]
    for z in range(35,110):
        if bare(364,75,z)=='projectseele:nerv_structural_panel':wall.append(z)
    for z in wall:
        for x in range(362,367):
            if not inside(x,z):continue
            d['walk'][at(x,z)]=False;d['road'][at(x,z)]=False;d['held'][at(x,z)]=True
    # The measured retained room east of that wall includes a ceiling light.
    # A new raster road had incorrectly occupied its interior. Withdraw that
    # complete proposed component, restoring current room contents verbatim.
    groups,n=label(d['road']|d['tunnel'],np.ones((3,3)))
    k=int(groups[at(370,48)]);restored=[]
    if k:
        zs,xs=np.where(groups==k)
        if len(xs)<200 and xs.min()+x0>=367 and xs.max()+x0<=374 and zs.min()+z0>=43 and zs.max()+z0<=63:
            for iz,ix in zip(zs,xs):
                X,Z=int(ix+x0),int(iz+z0);h=int((oldgrade[iz,ix]+1)//2)
                for Y in range(h-2,h+9):e.put(X,Y,Z,e.state(X,Y,Z,original=True))
                d['road'][iz,ix]=False;d['walk'][iz,ix]=False;d['held'][iz,ix]=True;restored.append([X,Z])
    if restored:(a.candidate/'retained-facility-overlay.json').write_text(json.dumps(dict(reason='Proposed street inside retained room',restored_columns=restored)),encoding='utf8')
    entrances=np.full(d['walk'].shape,np.nan,np.float32)
    for row in catalog:
        for x,y,z in row.get('footway',[]):
            x,z=int(x),int(z)
            if inside(x,z)and d['walk'][at(x,z)]:entrances[at(x,z)]=oldgrade[at(x,z)];break
    d['grade2']=network_grade(d['grade2'],d['walk'],d['core'],entrances)
    changed=(oldgrade!=d['grade2'])&d['walk']
    for x,z in touch:
        if inside(x,z)and d['walk'][at(x,z)]:changed[at(x,z)]=True
    # Refit local road shoulders using the same continuous surface authority.
    ceiling=min_slope_envelope(np.where(changed,d['grade2']//2,np.inf),.75)
    ground=d['ground'].copy();fit=np.minimum(ground,np.rint(ceiling)).astype(np.int16)
    held=d['held']|d['core'];fit[held]=ground[held]
    d['ground']=fit
    mutable=NATURAL|PAVEMENT|{'minecraft:stone_brick_wall','minecraft:iron_bars','minecraft:polished_andesite','minecraft:sea_lantern','minecraft:lantern','projectseele:nerv_edge_rail'}
    affected=(fit!=ground)|changed
    zs,xs=np.nonzero(affected);order=sorted(((int(x),int(z))for x,z in zip(xs+x0,zs+z0)),key=lambda p:(p[0]//512,p[1]//512))
    chunks=set();remaining=[];last=None
    for x,z in order:
        key=(x//512,z//512)
        if last is not None and last!=key:e.save();e.regions.clear()
        last=key;ij=at(x,z);h=int((d['grade2'][ij]+1)//2);previous=int((oldgrade[ij]+1)//2)
        if changed[ij]:
            states=[bare(x,Y,z)for Y in range(h,h+3)]
            if any(s not in mutable and s!='minecraft:deepslate_bricks'for s in states):
                remaining.append([x,h,z,states]);continue
            # Existing masonry with clear headroom is already a valid floor.
            keep=states[0]=='minecraft:deepslate_bricks'and all(s in AIR for s in states[1:])
            for Y in range(h+1,max(h+3,previous+1)):
                s=bare(x,Y,z)
                if s in mutable and not room(x,Y,z):e.put(x,Y,z,'minecraft:air')
            if not keep:
                slab=bool(d['grade2'][ij]%2);road=bool(d['road'][ij]);mark=bool(d['marking'][ij])
                mat=('projectseele:road_marking_slab'if mark else 'projectseele:road_asphalt_slab'if road else 'minecraft:smooth_stone_slab')+'[type=bottom,waterlogged=false]'if slab else 'minecraft:white_concrete'if mark else 'minecraft:black_concrete'if road else 'minecraft:smooth_stone'
                if not room(x,h,z):e.put(x,h,z,mat)
            # A narrow structural road bed is sufficient over an existing void;
            # never fill an entire railway/tunnel undercroft with solid earth.
            if bare(x,h-1,z)in NATURAL:e.put(x,h-1,z,'minecraft:stone')
            chunks.add((x//16,z//16))
        else:
            new,old=int(fit[ij]),int(ground[ij])
            for Y in range(new,old+1):
                if bare(x,Y,z)in NATURAL and not room(x,Y,z):e.put(x,Y,z,'minecraft:grass_block[snowy=false]'if Y==new else 'minecraft:air');chunks.add((x//16,z//16))
    regions=e.save();m=json.loads((a.candidate/'manifest.json').read_text('utf8'));m.update(regions=regions,cells=sum(r['cells']for r in regions));(a.candidate/'manifest.json').write_text(json.dumps(m,indent=2),'utf8')
    p=a.candidate/'transport-changed-chunks.json';chunks|=set(map(tuple,json.loads(p.read_text('utf8'))));p.write_text(json.dumps(sorted(chunks)),'utf8')
    np.savez_compressed(a.plan/'network.npz',**d)
    out=dict(observed_ceiling_columns=len(ceilings),changed_road_columns=int(changed.sum()),wall_margin_columns=int((oldwalk&~d['walk']).sum()),remaining=remaining)
    (a.candidate/'crossing-completion.json').write_text(json.dumps(out,indent=2),'utf8');print(out,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in ('candidate','plan'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())

"""Build register-relative facade deltas and georeferenced far silhouettes from a stopped R65 cargo recipe."""
import argparse, gzip, json, struct, sys
from pathlib import Path
import nbtlib
from city_body_sync import topology
from private_cleanup import unpack, DATA, state
from tokyo3_r66_design import OWNERS, model, AIR

# Exterior colour at several blocks/pixel, with actual glazing measured independently of night glow.
def colour(s):
    if 'glass' in s: return (125,164,176) if 'blue' in s else (117,141,151) if 'gray' in s else (157,181,191)
    if 'froglight' in s or 'lantern' in s or 'shroomlight' in s:return (220,202,150)
    if 'white' in s or 'quartz' in s: return (215,217,210)
    if 'gray' in s and 'light_gray' not in s or 'deepslate' in s or 'black' in s: return (79,86,87)
    if 'yellow' in s:return (192,158,80)
    if 'red' in s:return (146,88,74)
    if 'wood' in s or 'planks' in s:return (145,121,97)
    return (157,162,160)

def mesh(owner,t,v,out):
    """Read the four exterior elevations and roof from the actual registered cargo.
    Preserve split towers and their alley at one-block resolution. Merge contiguous coplanar runs.
    Row record: owner, face, local face/col/row, width, height, RGB, lighting.
    """
    f=t['fp']; cx,cy,cz=t['centre'];out.write(struct.pack('>hhhhhhhh',cx,cy,cz,t['ret'],*f))
    faces=[]
    for face in range(5):
        planes={}
        for (x,y,z),s in v.items():
            if face<2: u,w,d=z,y,x if face==0 else -x
            elif face<4: u,w,d=x,y,z if face==2 else -z
            else:u,w,d=x,z,y
            k=(u,w)
            if k not in planes or planes[k][0]<d:planes[k]=(d,s)
        rows={}
        for (u,w),(d,s) in planes.items():
            rgb=colour(s);glow=0
            if 'glass' in s and face<4:
                x,y,z=(d,w,u) if face==0 else (-d,w,u) if face==1 else (u,w,d) if face==2 else (u,w,-d)
                dx,dz=((1,0),(-1,0),(0,1),(0,-1))[face]
                behind=v.get((x-dx,y,z-dz),'')
                if 'froglight' in behind or 'lantern' in behind or 'shroomlight' in behind:glow=1
            if 'froglight' in s or 'shroomlight' in s or 'sea_lantern' in s:glow=1
            p=d+1 if face in (0,2,4) else -d
            rows.setdefault((w,p,rgb,glow),[]).append(u)
        rectangles={}
        for (w,p,rgb,glow),us in sorted(rows.items()):
            us.sort(); start=prev=us[0]
            for u in us[1:]+[10000]:
                if u==prev+1:prev=u;continue
                key=(p,start,prev+1,rgb,glow)
                if key in rectangles and rectangles[key][-1][1]==w:rectangles[key][-1][1]=w+1
                else:rectangles.setdefault(key,[]).append([w,w+1])
                start=prev=u
        for (p,u,u1,rgb,glow),spans in rectangles.items():
            for w,w1 in spans:faces.append((face,p,u,w,u1-u,w1-w,*rgb,glow))
    out.write(struct.pack('>I',len(faces)))
    for row in faces:out.write(struct.pack('>BhhhBBBBBB',*row))
    return len(faces)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('world',type=Path);parser.add_argument('out',type=Path)
    a=parser.parse_args();a.out.mkdir(parents=True,exist_ok=True);top=topology(a.world);report={}
    with gzip.open(a.out/'city_shells_r66.bin.gz','wb',compresslevel=3) as far:
        far.write(struct.pack('>IH',0x54333636,len(top)))
        for i,t in top.items():
            recipe=nbtlib.load(a.world/DATA/'city_rigid_generation_r45'/'cargo'/f'{i}.dat')['data']['Buildings'][0]['Cargo']
            original={unpack(c['Pos']):state(c['State']) for c in recipe}
            new=model(i,t['H'],t['fp'][1],original) if i in OWNERS else original
            for c in recipe:
                if 'NBT' in c:
                    p=unpack(c['Pos']);new[p]=original[p]
            delta=[(p,original.get(p,AIR),new.get(p,AIR)) for p in sorted(original.keys()|new.keys()) if original.get(p)!=new.get(p)]
            if delta:
                with gzip.open(a.out/f'{i}.tsv.gz','wt',encoding='utf8') as f:
                    for (x,y,z),before,after in delta:f.write(f'{x}\t{y}\t{z}\t{before}\t{after}\n')
            report[i]=dict(cargo_before=len(original),cargo_after=len(new),changes=len(delta),quads=mesh(i,t,new,far),centre=t['centre'],base=t['ret'],height=t['H'],fp=t['fp'])
            if i%10==0:print(i,report[i],flush=True)
    (a.out/'owners.json').write_text(json.dumps(report,indent=1),'utf8')
if __name__=='__main__':main()

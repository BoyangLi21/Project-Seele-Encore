"""Cheap source-grounded terrain plans/sections; no Minecraft or world writes."""
from pathlib import Path
import argparse,gzip,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from query_blocks import read_box,AIR

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    area=ROOT/'artifacts/rebuild_r49/encounter_facilities'
    lo=(-95,72,435);hi=(155,140,535)
    before=read_box(args.world,'projectseele:geofront',lo,hi);after=dict(before)
    with gzip.open(area/'r50_yashima/Y01_south_ridge_power_and_access/forward.jsonl.gz','rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line);p=tuple(r['pos'])
            if all(a<=v<=b for v,a,b in zip(p,lo,hi)):
                before[p]=r['before'];after[p]=r['after']
    def height(states):
        a=np.full((101,251),71,dtype=float)
        for (x,y,z),s in states.items():
            if s not in AIR:a[z-435,x+95]=max(a[z-435,x+95],y)
        return a
    b=height(before);a=height(after)
    fig,ax=plt.subplots(3,2,figsize=(15,12),layout='constrained')
    for axis,data,title in [(ax[0,0],b,'Measured original south edge'),(ax[0,1],a,'R50 current civil candidate')]:
        im=axis.imshow(data,origin='lower',extent=(-95,155,435,535),cmap='terrain',vmin=75,vmax=136,aspect='equal')
        axis.set_title(title);axis.set_xlabel('X / m');axis.set_ylabel('Z / m (north is down)')
        for z in(429,435,530):axis.axhline(z,color='red',lw=.8,ls='--')
    ax[0,1].plot(30.5,498.5,'rx');ax[0,1].plot(30.5,458.5,'bx')
    xs=np.arange(-95,156);zs=np.arange(435,536)
    ax[1,0].plot(xs,b[498-435],label='Original');ax[1,0].plot(xs,a[498-435],label='Candidate')
    ax[1,0].set(title='Transverse X section at Z498: long shoulders and actual EVA ramp',xlabel='X / m',ylabel='Highest measured solid Y');ax[1,0].legend();ax[1,0].grid(alpha=.3)
    ax[1,1].plot(zs,b[:,30+95],label='Original');ax[1,1].plot(zs,a[:,30+95],label='Candidate')
    ax[1,1].set(title='Highest solids at X30; deck and natural ridge are separated below',xlabel='Z / m',ylabel='Highest measured solid Y');ax[1,1].legend();ax[1,1].grid(alpha=.3)
    def section(states):
        result=np.ones((69,101,3))
        for y in range(72,141):
            for z in range(435,536):
                s=states.get((30,y,z),'minecraft:air');n=s.split('[')[0]
                if n in AIR:continue
                colour=(.40,.70,.34)if n in {'minecraft:grass_block','minecraft:oak_leaves'} else(.58,.48,.38)if n in{'minecraft:stone','minecraft:andesite','minecraft:dirt','minecraft:gravel','minecraft:sand'} else(.40,.44,.48)
                result[y-72,z-435]=colour
        return result
    for axis,states,title in [(ax[2,0],before,'Actual original material section X30'),(ax[2,1],after,'Candidate: green rounded ridge + grey supported engineering deck')]:
        axis.imshow(section(states),origin='lower',extent=(435,536,72,141),aspect='equal')
        axis.set(title=title,xlabel='Z / m',ylabel='Y / m')
    fig.suptitle('Exact block source + candidate overlay. Not a native screenshot or user art acceptance.')
    fig.savefig(args.out/'south_ridge_sections.png',dpi=150);plt.close(fig)
    old={};new={};solid={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:clay','minecraft:deepslate','minecraft:andesite','minecraft:diorite','minecraft:granite','minecraft:tuff'}
    with gzip.open(area/'r50_marine/complete_generation_source.jsonl.gz','rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line);x,y,z=r['pos']
            if (x-1630)**2+(z-685)**2>118**2:continue
            if r['before'].split('[')[0]in solid:old[x,z]=max(old.get((x,z),-1),y)
            if r['after'].split('[')[0]in solid:new[x,z]=max(new.get((x,z),-1),y)
    beds=[]
    for values in(old,new):
        data=np.full((237,237),np.nan)
        for (x,z),v in values.items():data[z-567,x-1512]=v
        beds.append(data)
    fig,ax=plt.subplots(1,3,figsize=(16,5),layout='constrained')
    for axis,data,title in zip(ax[:2],beds,['Original basin seabed 34..56','Candidate inner bed16 and graded shoulder']):
        axis.imshow(data,origin='lower',extent=(1512,1749,567,804),cmap='viridis',vmin=16,vmax=56)
        axis.set(title=title,xlabel='X / m',ylabel='Z / m')
        for radius,color in[(105,'white'),(101.55417528,'red')]:axis.add_patch(plt.Circle((1630,685),radius,fill=False,color=color,lw=.8))
        axis.plot(1519.5,771.5,'wx')
    x=np.arange(1512,1749)
    ax[2].plot(x,[old.get((int(v),685),np.nan)for v in x],label='Original bed')
    ax[2].plot(x,[new.get((int(v),685),np.nan)for v in x],label='Candidate bed')
    for y,name in[(63,'water surface'),(18,'lowest attacking jaw'),(55,'main body top'),(68,'dorsal top')]:ax[2].axhline(y,ls='--',lw=.8,label=name)
    ax[2].set(title='Scale1 actual asymmetric attack clearance',xlabel='X / m at Z685',ylabel='Y / m');ax[2].legend(fontsize=8);ax[2].grid(alpha=.3)
    fig.suptitle('Full-yaw root sweep radius101.55m, inner basin105m. Native movement and cannon rays pending.')
    fig.savefig(args.out/'marine_basin_sections.png',dpi=150);plt.close(fig)
    print('Source-grounded terrain preview PNGs:',args.out)
if __name__=='__main__':main()

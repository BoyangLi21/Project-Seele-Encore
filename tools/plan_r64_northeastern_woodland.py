"""Extend the northeast survey corner into measured high ground in separate stands.

Centers are foothill search windows in world coordinates; local relief, soil, water
and existing canopy choose each actual stand and the probability of each actual stem.
"""
from pathlib import Path
import argparse
import numpy as np
from scipy import ndimage as nd
from finish_r64_playtest_woodland import d8
from plan_r64_playtest_terrain import smooth

STANDS=(
 (3520,-1475,115,105,.77),(3690,-1550,130,83,.81),(3885,-1630,123,154,1.24),
 (4100,-1482,96,112,.72),(4240,-1680,154,131,1.25),(4435,-1525,103,99,.82),
 (4585,-1625,108,152,1.10),(4570,-1410,168,105,1.18),(4680,-1250,126,106,.97),
 (4575,-1080,98,133,.83),(4740,-904,171,103,1.14),(4595,-730,103,107,.73),
 (4705,-562,147,109,.91),(4615,-382,84,95,.51),
)
def design(work):
    out=work/'woodland-plan';out.mkdir(exist_ok=True)
    rx0,rz0=6,-5;rx1,rz1=10,0
    size=((rz1-rz0+1)*64,(rx1-rx0+1)*64)
    h,k,v,wet=[np.zeros(size,'f') for _ in range(4)]
    def cut(rx,rz):return np.s_[(rz-rz0)*64:(rz-rz0+1)*64,(rx-rx0)*64:(rx-rx0+1)*64]
    for rx in range(rx0,rx1+1):
        for rz in range(rz0,rz1+1):
            a=np.load(work/'after-final'/f'r.{rx}.{rz}.npz');sl=cut(rx,rz);kind=a['k']
            h[sl]=d8(np.where(kind!=0,a['h'],0));k[sl]=d8(kind==3);v[sl]=d8(a['v']);wet[sl]=d8(kind==4)
    xx,zz=np.meshgrid(rx0*512+np.arange(size[1])*8+4,rz0*512+np.arange(size[0])*8+4)
    g=nd.gaussian_filter(h,3);relative=g-nd.gaussian_filter(g,15);slope=np.hypot(*np.gradient(g))/8
    potential=np.zeros(size,'f');anchors=[]
    for x,z,wx,wz,strength in STANDS:
        # Seek the higher, better drained ground inside each lowland search window.
        offset=((xx-x)/62)**2+((zz-z)/68)**2
        score=np.where((offset<1)&(k>.85),relative*.095-offset*.85,-10000.)
        j,i=np.unravel_index(np.argmax(score),score.shape)
        if score[j,i]<-9000:continue
        ax,az=int(xx[j,i]),int(zz[j,i]);anchors.append((ax,az))
        # Warp stand contours along drainage folds instead of following X or Z.
        dx=xx-ax+23*np.sin(zz/93+xx/151);dz=zz-az+26*np.sin(xx/107-zz/187)
        potential+=strength*np.exp(-.5*((dx/wx)**2+(dz/wz)**2))
    sites=(.78+.21*smooth((relative+9)/19))*(.86+.10*np.cos(zz/51-xx/113)+.055*np.sin(xx/48+zz/119))
    habitat=(1-np.exp(-potential))*.86*sites*smooth((h+75)/32)*smooth((2.1-slope)/1.25)
    habitat*=smooth((.36-nd.gaussian_filter(wet,3))/.29)
    # Inside the already restored map only fill the transitional shoulder.
    inward=np.maximum(smooth((-1350-zz)/150),smooth((xx-4400)/150))
    habitat*=inward
    deficit=np.maximum(habitat-nd.gaussian_filter(v,1.7)-.018,0)*smooth((k-.45)/.5)
    # Below this probability even a mature stand contributes less than one crown per chunk.
    deficit=np.where(potential>.07,deficit,0)
    for rx in range(rx0,rx1+1):
        for rz in range(rz0,rz1+1):
            sl=cut(rx,rz);p=np.rint(np.clip(deficit[sl],0,.8)*255).astype('B')
            classes=np.where(relative[sl]>-2,2,4).astype('B')
            np.savez_compressed(out/f'r.{rx}.{rz}.npz',add=p,remove=np.zeros_like(p),classes=classes)
    print('stand centers',anchors,'supported 8m cells',int((deficit>.02).sum()),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('work',type=Path);a=p.parse_args();design(a.work)

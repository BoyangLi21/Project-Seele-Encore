"""Actual posed leg/boot triangles against the complete selected Angel skin."""
import argparse,json,hashlib
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from r52_motion_core import selected,read,UNIT,MIRROR
from author_finisher_r52 import keyposes

def segment_hit(a,b,tri):
    d=b-a;e1=tri[:,1]-tri[:,0];e2=tri[:,2]-tri[:,0];h=np.cross(d,e2);det=np.einsum('ij,ij->i',e1,h)
    good=np.abs(det)>1e-9;f=np.divide(1,det,out=np.zeros_like(det),where=good);s=a-tri[:,0]
    u=f*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=f*(q@d);t=f*np.einsum('ij,ij->i',e2,q)
    return good&(u>1e-6)&(v>1e-6)&(u+v<1-1e-6)&(t>1e-6)&(t<1-1e-6)

def intersections(hero,angel):
    amin,amax=angel.min(1),angel.max(1);hits=[]
    # A real triangle intersection shares a point inside both bounding
    # spheres. This conservative query avoids scanning the entire Angel for
    # every triangle of the 34-joint hands; exact edge tests still decide hits.
    centres=angel.mean(1);radii=np.linalg.norm(angel-centres[:,None,:],axis=2).max(1)
    hero_centres=hero.mean(1);hero_radii=np.linalg.norm(hero-hero_centres[:,None,:],axis=2).max(1)
    neighbours=cKDTree(centres).query_ball_point(hero_centres,hero_radii+radii.max()+1e-8)
    for i,tri in enumerate(hero):
        indices=np.asarray(neighbours[i],dtype=int)
        mask=np.all(amax[indices]>=tri.min(0),axis=1)&np.all(amin[indices]<=tri.max(0),axis=1)
        indices=indices[mask];other=angel[indices]
        if not len(other):continue
        found=np.zeros(len(other),bool)
        for j in range(3):found|=segment_hit(tri[j],tri[(j+1)%3],other)
        for j in np.flatnonzero(~found):
            enemy=other[j]
            if any(segment_hit(enemy[e],enemy[(e+1)%3],tri[None])[0] for e in range(3)):found[j]=True
        for j in np.flatnonzero(found):hits.append({'hero_triangle':i,'angel_triangle':int(indices[j]),'hero_centre':tri.mean(0).tolist(),'angel_centre':other[j].mean(0).tolist()})
    return hits

def main():
    ap=argparse.ArgumentParser()
    for n in ('body','assets','angel-rig','out'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--clip',type=Path);a=ap.parse_args();b,h,e=selected(a.body,a.assets,a.angel_rig);records=[]
    if a.clip:
        d=read(a.clip);cases=[]
        for t in [4.8,5.5,7.2,7.9,8.35,8.8,9.4,10.4,11.4,12,12.5,13.5,16.8,17.2,17.5,17.8,18.1,18.25]:
            i=round(t*d['fps']);cases.append({'name':str(t),'eva':h.decode(d['eva']['frames'][i],d['eva']['bones']),'angel':e.decode(d['angel']['frames'][i],d['angel']['bones']),'hr':np.asarray(d['eva']['root_blocks'][i]),'ar':np.asarray(d['angel']['root_blocks'][i])})
    else:cases=keyposes(h,e)[2:5]
    for k in cases:
        legs=k['eva'].surface(['leg_l','shin_l','foot_l','leg_r','shin_r','foot_r'])*MIRROR*UNIT+k['hr'];enemy=k['angel'].surface()*UNIT+k['ar']
        hits=intersections(legs.reshape(-1,3,3),enemy.reshape(-1,3,3));records.append({'name':k['name'],'intersection_pairs':len(hits),'hits':hits[:24]});print(k['name'],len(hits),flush=True)
    a.out.write_text(json.dumps({'clip':str(a.clip.resolve()) if a.clip else None,'sha256':hashlib.sha256(a.clip.read_bytes()).hexdigest() if a.clip else None,'scope':'Actual triangle surface intersections; endpoint contacts excluded. Does not replace native motion review.','samples':records,'native_verified':False,'user_accepted':False},indent=2),encoding='utf-8')
if __name__=='__main__':main()

"""Candidate source-foot shims. No world writes or runtime source installation."""
import argparse, hashlib, json, zipfile
from pathlib import Path
import numpy as np

def hull(points):
    points=sorted(set(map(tuple,points)))
    def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    low=[];high=[]
    for p in points:
        while len(low)>1 and cross(low[-2],low[-1],p)<=1e-9: low.pop()
        low.append(p)
    for p in reversed(points):
        while len(high)>1 and cross(high[-2],high[-1],p)<=1e-9: high.pop()
        high.append(p)
    return low[:-1]+high[:-1]

def surface(tri,x,z):
    a=tri[:,0];b=tri[:,1]-a;c=tri[:,2]-a
    det=b[:,0]*c[:,2]-b[:,2]*c[:,0];good=np.abs(det)>1e-8
    u=np.divide((x-a[:,0])*c[:,2]-(z-a[:,2])*c[:,0],det,out=np.zeros_like(det),where=good)
    v=np.divide(b[:,0]*(z-a[:,2])-b[:,2]*(x-a[:,0]),det,out=np.zeros_like(det),where=good)
    good&=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
    return float(np.max((a[:,1]+u*b[:,1]+v*c[:,1])[good])) if good.any() else None

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jar',type=Path,required=True);p.add_argument('--bodies',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=zipfile.ZipFile(a.jar).read('assets/projectseele/mesh/carrier_mk2_r53.json');carrier=json.loads(raw);deck=np.asarray(carrier['parts']['deck']).reshape(-1,3,8)[:,:,:3]
    rows=[]
    for variant in range(3):
        bodyraw=(a.bodies/f'unit0{variant}.json').read_bytes();body=json.loads(bodyraw)
        for bone in ['foot_l','foot_r']:
            foot=np.asarray(body['parts'][bone]).reshape(-1,3,3);low=float(foot[:,:,1].min())
            normal=np.cross(foot[:,1]-foot[:,0],foot[:,2]-foot[:,0]);facets=foot[(foot[:,:,1].max(1)<low+.01)&(abs(normal[:,1])>.0001)]
            assert len(facets)>0,(variant,bone,'No finite sole facets')
            authored_count=len(facets);selected=[]
            for f in facets:
                heights=[surface(deck,x,z) for x,_,z in list(f)+[f.mean(0)]]
                if all(h is not None for h in heights) and max(heights)-min(heights)<.00001 and .005<low-max(heights)<.5:selected.append(f)
            facets=np.asarray(selected);assert len(facets)>0
            poly=hull(facets[:,:,[0,2]].reshape(-1,2));area=float(np.abs(np.cross(facets[:,1]-facets[:,0],facets[:,2]-facets[:,0])[:,1]).sum()/2);assert area>1
            probes=list(facets.reshape(-1,3))+list(facets.mean(1));heights=[surface(deck,x,z) for x,_,z in probes]
            assert all(h is not None for h in heights),(variant,bone,'Foot outside imported deck')
            assert max(heights)-min(heights)<.00001 and .005<low-max(heights)<.5,(variant,bone,low,heights)
            bottom=float(max(heights));top=float(facets[:,:,1].max());tri=[];edges={}
            for f in facets:
                if np.cross(f[1]-f[0],f[2]-f[0])[1]<0:f=f[::-1]
                tri.append(f.tolist());b=f.copy();b[:,1]=bottom;tri.append(b[::-1].tolist())
                for i in range(3):
                    u=tuple(f[i]);v=tuple(f[(i+1)%3]);key=tuple(sorted((u,v)))
                    edges.setdefault(key,[]).append((u,v))
            for uses in edges.values():
                assert len(uses)<=2,'Nonmanifold sole source'
                if len(uses)!=1:continue
                u,v=uses[0];ub=(u[0],bottom,u[2]);vb=(v[0],bottom,v[2]);tri.extend([[u,ub,vb],[u,vb,v]])
            xyz=np.asarray(tri).reshape(-1,3);rgb=np.concatenate([xyz,np.tile([.19,.21,.22],(len(xyz),1))],1).reshape(-1)
            rows.append(dict(variant=variant,bone=bone,name=f'sole_bearing_{variant}_{bone}',triangles_rgb=rgb.tolist(),contact_facets=facets.tolist(),footprint=poly,top=top,bottom=bottom,area_m2=area,unused_foot_facet_count=authored_count-len(facets),foot_source_faces_removed=0,body_export_sha256=hashlib.sha256(bodyraw).hexdigest()))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(dict(schema='projectseele.r53.carrier-sole-bearing.v1',stride=6,carrier_source_sha256=hashlib.sha256(raw).hexdigest(),installed=False,parts=rows),separators=(',',':')),'utf8')
    print(json.dumps([dict(variant=r['variant'],bone=r['bone'],top=r['top'],bottom=r['bottom'],area=r['area_m2']) for r in rows]))
if __name__=='__main__':main()

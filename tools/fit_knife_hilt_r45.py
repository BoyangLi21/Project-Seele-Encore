"""Fit only the private knife hilt to the new glove; blade/UV/topology retained."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.parent.mkdir(parents=True,exist_ok=True)
m=json.loads(a.source.read_text());part=m['parts']['knife'];raw=np.asarray(part['vertices']).reshape(-1,m['stride']);v=raw[:,:3]+part['pivot'];before=v.copy();t=np.clip((v[:,1]-84)/4,0,1);w=t*t*(3-2*t);derivative=np.where((t>0)&(t<1),6*t*(1-t)/4,0);sx=1-.2*w;sz=1-.45*w;cx,cz=part['pivot'][0],part['pivot'][2];dxdy=-.2*derivative*(v[:,0]-cx);dzdy=-.45*derivative*(v[:,2]-cz);sy=np.where(v[:,1]>84,1.35,1.)
v[:,0]=cx+(v[:,0]-cx)*sx;v[:,2]=cz+(v[:,2]-cz)*sz;v[:,1]=np.where(v[:,1]>84,84+(v[:,1]-84)*1.35,v[:,1]);changed=before[:,1]>84
n=raw[:,5:8].copy();n[:,0]/=sx;n[:,2]/=sz;n[:,1]=(n[:,1]-dxdy*n[:,0]-dzdy*n[:,2])/sy;n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-12);raw[changed,:3]=v[changed]-part['pivot'];raw[changed,5:8]=n[changed];part['vertices']=np.round(raw,7).reshape(-1).tolist();m['hilt_fit_r45']=dict(source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),changed_vertices=int(changed.sum()),blade_vertices_preserved=int((~changed).sum()),cross_section_scale=[.8,.55],hilt_length_scale=1.35,visual_accepted=False)
a.out.write_text(json.dumps(m,separators=(',',':')),encoding='utf8');print(json.dumps(m['hilt_fit_r45']))

"""Retain both complete supplied GLB forms in a private optional render asset.

No remeshing, welding, quantization, or public distribution of the source.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    raw=args.source.read_bytes()
    magic,version,size=struct.unpack_from('<III',raw)
    assert magic==0x46546c67 and version==2 and size==len(raw)
    chunks={};offset=12
    while offset<len(raw):
        length,kind=struct.unpack_from('<II',raw,offset)
        chunks[kind]=raw[offset+8:offset+8+length];offset+=8+length
    doc=json.loads(chunks[0x4e4f534a]);binary=chunks[0x004e4942]
    assert not doc.get('skins') and not doc.get('animations')
    assert not doc.get('images') and not doc.get('textures'), 'Only the supplied constant-material source is supported'
    assert {n['name']for n in doc['nodes']}=={'Ramiel1.1','Ramiel1.2','Ramiel2.1','Ramiel2.2','Ramiel2.3','Center1','Center2'}
    def accessor(index):
        a=doc['accessors'][index];assert 'sparse'not in a
        view=doc['bufferViews'][a['bufferView']];assert view['buffer']==0
        typ={5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
        width=np.dtype(typ).itemsize
        start=view.get('byteOffset',0)+a.get('byteOffset',0)
        return np.ndarray((a['count'],components),dtype=typ,buffer=binary,
            offset=start,strides=(view.get('byteStride',components*width),width)).copy()
    def rotation(q):
        x,y,z,w=q
        return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                         [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                         [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    scale=8.25/6.460382461547852
    parts=[];materials=[];outputs=[];repaired_uv_faces=0
    for i,m in enumerate(doc['materials']):
        pbr=m['pbrMetallicRoughness'];rgba=np.array(pbr['baseColorFactor'])
        emission=np.array(m.get('emissiveFactor',[0,0,0]))
        transmission=m.get('extensions',{}).get('KHR_materials_transmission',{}).get('transmissionFactor',0)
        # Keep glTF alpha separate from transmission: multiplying both made
        # the native crystal almost white and erased the authored blue facets.
        color=emission if np.max(emission)>0 else rgba[:3]
        color=np.where(color<=.0031308,color*12.92,1.055*np.power(color,1/2.4)-.055)
        alpha=rgba[3]
        pixel=tuple(np.clip(np.r_[color,alpha]*255,0,255).round().astype(int))
        name=f'textures/entity/ramiel_source_r53_{i}.png'
        target=args.output/name;target.parent.mkdir(parents=True,exist_ok=True)
        Image.new('RGBA',(4,4),pixel).save(target);outputs.append(target)
        # glTF's perceptual roughness maps to LabPBR's perceptual smoothness.
        # https://shaderlabs.org/wiki/LabPBR_Material_Standard
        smoothness=round(255*(1-pbr['roughnessFactor']))
        specular=target.with_name(target.stem+'_s.png')
        Image.new('RGBA',(4,4),(smoothness,10,0,180 if np.max(emission)>0 else 0)).save(specular)
        outputs.append(specular)
        normal=target.with_name(target.stem+'_n.png')
        Image.new('RGBA',(4,4),(128,128,255,255)).save(normal);outputs.append(normal)
        materials.append(dict(source=m,texture='projectseele:'+name,
                              effective_blend_alpha=alpha,emissive=bool(np.max(emission)>0)))
    for n in doc['nodes']:
        assert not n.get('children')and 'matrix'not in n and 'scale'not in n
        name=n['name'];phase='closed'if name.startswith('Ramiel1')or name=='Center1'else'open'
        origin=np.array([29.957931518554688,15.000174522399902,0])if phase=='closed'else np.array([0,15.000174522399902,0])
        r=rotation(n.get('rotation',[0,0,0,1]));translation=np.array(n.get('translation',[0,0,0]))-origin
        for number,p in enumerate(doc['meshes'][n['mesh']]['primitives']):
            assert p.get('mode',4)==4
            idx=accessor(p['indices']).ravel();a=p['attributes']
            pos=(accessor(a['POSITION']).astype(float)@r.T+translation)*scale
            normals=accessor(a['NORMAL']).astype(float)@r.T
            assert np.max(np.abs(np.linalg.norm(normals,axis=1)-1))<1e-4
            uv=accessor(a['TEXCOORD_0'])if 'TEXCOORD_0'in a else np.zeros((len(pos),2))
            uv=uv.copy();uv[:,1]=1-uv[:,1]
            rows=np.concatenate([pos,uv,normals],axis=1).astype(np.float32)[idx]
            assert len(rows)%3==0 and np.isfinite(rows).all()
            # The supplied blue primitives have constant/missing UVs because
            # glTF uses only a material factor. Shader tangents require a
            # nonzero UV determinant even for a flat normal map. These
            # textures are constant, so a per-triangle UV basis changes no
            # appearance, source positions, normals, or face count.
            original_uvs=rows[:,3:5].copy()
            triangles=rows.reshape(-1,3,8)
            a=triangles[:,1,3:5]-triangles[:,0,3:5]
            b=triangles[:,2,3:5]-triangles[:,0,3:5]
            degenerate=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])<1e-10
            triangles[degenerate,0,3:5]=(.25,.25)
            triangles[degenerate,1,3:5]=(.75,.25)
            triangles[degenerate,2,3:5]=(.25,.75)
            repaired_uv_faces+=int(np.count_nonzero(degenerate))
            parts.append(dict(name=f'{name}/{number}',phase=phase,
                shell_shift=1 if name=='Ramiel1.1'else -1 if name=='Ramiel1.2'else 0,
                core=name.startswith('Center'),material=p['material'],vertices=rows.ravel().tolist(),
                triangles=len(rows)//3,source_uvs=original_uvs.ravel().tolist(),shader_uv_repaired_faces=int(np.count_nonzero(degenerate)),bounds=[rows[:,:3].min(0).tolist(),rows[:,:3].max(0).tolist()]))
    assert sum(p['triangles']for p in parts)==8816
    output=dict(schema='projectseele.r53.ramiel-source.v1',stride=8,
        source_sha256=hashlib.sha256(raw).hexdigest(),scale=scale,
        source_faces=8816,removed_faces=0,shader_uv_repaired_faces=repaired_uv_faces,materials=materials,parts=parts,
        material_limit='Original alpha, LabPBR roughness/F0/emission; glTF transmission remains metadata, without ray-traced refraction')
    mesh=args.output/'mesh/ramiel_source_r53.json';mesh.parent.mkdir(parents=True,exist_ok=True)
    mesh.write_text(json.dumps(output,separators=(',',':')),'utf-8');outputs.append(mesh)
    manifest=dict(schema='projectseele.r53.ramiel-selection.v1',resources={p.relative_to(args.output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in outputs})
    selection=args.output/'eva/ramiel_source_r53_sources.json';selection.parent.mkdir(parents=True,exist_ok=True)
    selection.write_text(json.dumps(manifest,indent=2),'utf-8')
    print(json.dumps(dict(source_sha256=output['source_sha256'],source_faces=8816,
        parts=[{k:v for k,v in p.items()if k not in ('vertices','source_uvs')}for p in parts],resources=manifest['resources'])))


if __name__=='__main__':main()

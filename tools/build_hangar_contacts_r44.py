"""Authored shoulder pads and actuators from six actual submitted armour facets."""
from pathlib import Path
import argparse, hashlib, json, math
import numpy as np
from PIL import Image
import build_tv_machinery_r16 as mesh

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'src/main/resources/assets/projectseele'
SOURCE=ROOT/'artifacts/rebuild_r44/facility_transit_r44/hangar_shoulder_contact_v2/contacts.json'
OUT=ROOT/'artifacts/rebuild_r44/hangar_machinery/shoulder_contact_v1'


def prism(points,normal,thickness,color):
    a,b,c=np.asarray(points,dtype=float);normal=np.asarray(normal,dtype=float)
    d,e,f=(p+normal*thickness for p in (a,b,c))
    mesh.tri(a,c,b,color);mesh.tri(d,e,f,color)
    mesh.quad(a,b,e,d,color);mesh.quad(b,c,f,e,color);mesh.quad(c,a,d,f,color)


def paint_maps(target):
    target.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(44102)
    fleck=np.clip(rng.normal(248,1,(128,128)),244,251).astype(np.uint8)
    Image.fromarray(np.stack([fleck]*3,axis=-1)).save(target/'machinery_paint_r44.png')
    material=np.zeros((128,128,4),dtype=np.uint8)
    material[:,:,0]=104;material[:,:,1]=48;material[:,:,3]=255
    Image.fromarray(material).save(target/'machinery_paint_r44_s.png')
    normal=np.zeros((128,128,4),dtype=np.uint8)
    normal[:,:,0]=128;normal[:,:,1]=128;normal[:,:,2]=255;normal[:,:,3]=255
    Image.fromarray(normal).save(target/'machinery_paint_r44_n.png')


def main(apply=False,source=SOURCE,out=OUT):
    global SOURCE,OUT
    SOURCE,OUT=Path(source),Path(out)
    OUT.mkdir(parents=True,exist_ok=True)
    data=json.loads(SOURCE.read_text('utf8'));assert len(data['contacts'])==6
    mesh.PARTS.clear();rows=[]
    for contact in data['contacts']:
        variant,side=contact['variant'],contact['side']
        assert variant in (0,1,2) and side in (-1,1)
        points=np.asarray(contact['pad_contact_fixed_gantry_local'],dtype=float)
        normal=np.asarray(contact['exact_geometric_outward_normal_world'],dtype=float)
        assert np.dot(np.cross(points[1]-points[0],points[2]-points[0]),normal)>0
        centre=points.mean(axis=0)
        name=f'shoulder_pad_{variant}_{"l" if side<0 else "r"}'
        mesh.use(name)
        prism(points,normal,.08,mesh.BLACK)
        prism(points+normal*.08,normal,.08,mesh.OLIVE)
        # Captive fasteners sit in the outer plate, never through the EVA skin.
        for corner in points:
            q=centre+(corner-centre)*.54+normal*.16
            mesh.cylinder(q,q+normal*.05,.055,mesh.STEEL,12)
        upper=centre+normal*.22
        anchors=[];links=[]
        for dz in (-.36,.36):
            anchors.append([side*14.6,53.8,centre[2]+dz])
            links.append((upper+np.array([0,0,dz])).tolist())
        if 'anchors_override_fixed_gantry_local' in contact:
            anchors=contact['anchors_override_fixed_gantry_local']
        rows.append(dict(variant=variant,side=side,part=name,normal=normal.tolist(),
                         points=points.tolist(),centre=centre.tolist(),anchors=anchors,links=links,
                         release=contact['release']))
    mesh.use('shoulder_fixed_mounts')
    for side in (-1,1):
        mesh.housing(side*14.6-.50,51.15,-5.8,1.0,3.1,12.1,.20,mesh.OLIVE)
        for z in (-5.8,6.3):
            mesh.housing(side*14.6-.7,51.10,z-.6,1.4,.55,1.2,.18,mesh.EDGE)
        for z in (-2.8,2.8):
            mesh.cylinder((side*14.6,51.60,z),(side*14.6,53.70,z),.21,mesh.EDGE,20)
    mesh.use('shoulder_barrel')
    mesh.cylinder((0,0,0),(0,0,2.2),.30,mesh.OLIVE,24)
    for z in (.06,2.05):mesh.cylinder((0,0,z),(0,0,z+.13),.40,mesh.EDGE,24)
    mesh.use('shoulder_piston_unit')
    mesh.cylinder((0,0,0),(0,0,1),.16,mesh.STEEL,20)
    mesh.use('shoulder_joint')
    mesh.cylinder((0,0,-.08),(0,0,.08),.28,mesh.DARK,20)
    resource=dict(stride=6,contacts=rows,parts=mesh.PARTS,
        source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        contact_frame='Actual stationary gantry anchor; independent of actor rig pivot',
        geometry_quality='Native contact, opening sweep and artistic review remain pending')
    candidate=OUT/'hangar_shoulder_contacts_r44.json'
    candidate.write_text(json.dumps(resource,separators=(',',':')),'utf8')
    paint_maps(OUT/'textures')
    (OUT/'source_contract.json').write_bytes(SOURCE.read_bytes())
    lengths=[]
    def ramp(value,a,b):
        t=max(0,min(1,(value-a)/(b-a)))
        return t*t*(3-2*t)
    for row in rows:
        for opening in np.linspace(0,1,121):
            move=np.asarray(row['normal'])*2.1*ramp(opening,0,.25)+np.array([row['side']*5.35*ramp(opening,.23,.88),0,0])
            for anchor,link in zip(row['anchors'],row['links']):
                length=float(np.linalg.norm(np.asarray(link)+move-anchor))
                assert length>2.22, ('Barrel consumes piston stroke',row['variant'],row['side'],opening,length)
                lengths.append(length)
    receipt=dict(candidate=str(candidate),sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        source_sha256=resource['source_sha256'],pad_count=6,
        triangle_counts={k:len(v)//18 for k,v in mesh.PARTS.items()},
        procedural_material='Original matte coated metal; flat normal, LabPBR specular channels',
        author_source='Six measured submitted armour facets, TV screenshot shoulder-seat engineering relation',
        author_stroke_samples=len(lengths),minimum_total_actuator_metres=min(lengths),
        maximum_total_actuator_metres=max(lengths),barrel_metres=2.2,
        native_passed=False,visual_passed=False)
    if apply:
        import shutil
        target=ASSETS/'mesh'/candidate.name
        assert not target.exists(),'Preserve the previous candidate as a named revision'
        shutil.copy2(candidate,target)
        for path in (OUT/'textures').glob('*.png'):shutil.copy2(path,ASSETS/'textures/entity'/path.name)
    (OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),'utf8')
    print('Actual-facet shoulder machinery:',len(rows),'pads; native/art gate remains pending',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    parser.add_argument('--source',type=Path,default=SOURCE);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();main(args.apply,args.source,args.out)

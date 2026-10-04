"""Rigid original armour plates over a narrow flexible joint underlayer.

The original EVA outline and UVs remain the source. Cutting at measured joint
planes gives hard phalanges that do not rubber-stretch when the fingers bend.
"""
from pathlib import Path
import argparse,copy,json
import numpy as np
from PIL import Image
import make_tiger_unit01_pack as tiger
from author_anatomical_hand_rig_r45 import model_matrix,unit

ROOT=Path(__file__).resolve().parents[1]
def clip(poly,origin,normal,greater):
    if not poly:return []
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=float((a[:3]-origin)@normal);db=float((b[:3]-origin)@normal);ina=da>=-1e-10 if greater else da<=1e-10;inb=db>=-1e-10 if greater else db<=1e-10
        if ina:result.append(a)
        if ina!=inb:result.append(a+(b-a)*(da/(da-db)))
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    contract=json.loads((a.candidate/'hand_rig_contract.json').read_text());key=contract['rig'];name=f'eva_unit0{key}';geo=json.loads((a.candidate/(name+'.geo.json')).read_text());bone_list=geo['minecraft:geometry'][0]['bones'];bones={b['name']:b for b in bone_list};cache={};data=json.loads((a.candidate/(name+'_anatomical_hands_r45.mesh.json')).read_text())
    v,uv,ns,tris=tiger.parse_obj(Path(contract['source']).read_text());tiger.CLEAN_GRIP_FINGERS=False;fb,_,_=tiger.discover_finger_rig(v,tris);owners=tiger.complete_face_owners(v,tris,fb);minimum=min(p[1]for p in v);scale=192/(max(p[1]for p in v)-minimum)
    source_to_native=lambda p:(np.asarray(p)-[0,minimum,0])*[-1,1,-1]*scale/16
    tex=Image.open(ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/textures/entity/{name}.png').convert('RGBA');pixels=np.asarray(tex);roi=pixels[:,:tex.width//2,:3];valid=pixels[:,:tex.width//2,3]>250;brightness=roi.astype(float).mean(2);brightness[~valid]=1e9;y,x=np.unravel_index(brightness.argmin(),brightness.shape);dark_uv=[(x+.5)/tex.width,(y+.5)/tex.height]
    report=[]
    for side in ['l','r']:
        hand='hand_'+side;original=data['parts'][hand];raw=np.asarray(original['vertices']).reshape(-1,8);native_normal=raw[:,5:8]*[-1,1,1];native_normal/=np.linalg.norm(native_normal,axis=1)[:,None]
        original_points=(raw[:,:3]+original['pivot'])*[-1,1,1]/16;inner=original_points-native_normal*.005;raw[:,:3]=inner*[-1,1,1]*16-original['pivot'];raw[:,3:5]=dark_uv;original['vertices']=np.round(raw.reshape(-1),7).tolist();original['surface_role']='flexible underlayer, source-derived, inset0.025 world blocks'
        palm='r45_hand_'+side+'_palm_shell';spec=dict(name=palm,parent=hand,pivot=bones[hand]['pivot']);bone_list.append(spec);bones[palm]=spec;contract['new_bones'].append(spec)
        parts={palm:[]};joints=contract['hands'][side]['digits'];gap=.006
        def emit(bone,poly):
            if len(poly)<3:return
            buf=parts.setdefault(bone,[]);pivot=np.asarray(bones[bone]['pivot'])
            for i in range(1,len(poly)-1):
                for row in [poly[0],poly[i],poly[i+1]]:
                    pos=row[:3]*[-1,1,1]*16-pivot;n=unit(row[5:8])*[-1,1,1];buf.extend([*pos,*row[3:5],*n])
        for i,face in enumerate(tris):
            owner=owners[i]
            if not(owner==hand or owner.startswith('finger_')and owner.endswith('_'+side)):continue
            poly=[]
            for ref in face:
                pos=source_to_native(v[ref[0]]);t=uv[ref[1]]if ref[1]>=0 else[0,0];normal=ns[ref[2]]if ref[2]>=0 else tiger.face_normal([v[r[0]]for r in face]);poly.append(np.r_[pos,[t[0]*.5,1-t[1]],np.asarray(normal)*[-1,1,-1]])
            if owner==hand:emit(palm,poly);continue
            digit=owner.split('_')[1];chain=joints[digit]['joints'];points=[np.asarray(j['head_bind'])for j in chain]+[np.asarray(chain[-1]['tip_bind'])];axes=[unit(points[1]-points[0]),unit(points[2]-points[0]),unit(points[3]-points[1])]
            emit(palm,clip(poly,points[0]-axes[0]*gap,axes[0],False))
            for j in range(3):
                piece=clip(poly,points[j]+axes[j]*gap,axes[j],True)
                if j<2:piece=clip(piece,points[j+1]-axes[j+1]*gap,axes[j+1],False)
                emit(chain[j]['name'],piece)
        for bone,values in parts.items():
            if not values:continue
            count=len(values)//8;bind=model_matrix(bones,bone,cache);data['parts'][bone]=dict(pivot=bones[bone]['pivot'],vertices=np.round(values,7).tolist(),surface_role='original rigid palm/phalange armour clipped at measured hinge planes')
            data['jointSkins'][bone]=dict(influences={bone:[1.]*count},inverseBindColumnMajor={bone:np.linalg.inv(bind).T.reshape(-1).tolist()})
        report.append(dict(side=side,rigid_parts=len(parts),rigid_triangles=sum(len(x)//24 for x in parts.values()),gap_world_blocks=gap*10,underlayer_inset_world_blocks=.025))
    contract['armour_segmentation']=dict(method='Original source triangles clipped at anatomical joint planes, rigid plates plus inset flexible source underlayer',parts=report,visual_approved=False)
    (a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8');(a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(data,separators=(',',':')),'utf8');(a.out/'hand_rig_contract.json').write_text(json.dumps(contract,indent=2),'utf8');print(json.dumps(report))
if __name__=='__main__':main()

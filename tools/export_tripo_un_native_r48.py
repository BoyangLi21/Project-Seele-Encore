"""Native candidate on the complete existing gameplay hierarchy; no live-pack mutation."""
from pathlib import Path
import copy,json,shutil
import numpy as np
from scipy.spatial import ConvexHull
from PIL import Image,ImageDraw
from export_tripo_machinery_r48 import textures

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/rebuild_r48'
SOURCE=BASE/'assets/assets/projectseele'
OUT=BASE/'un_native_candidate'

def main():
    body=json.loads((BASE/'runtime/projectseele-local-maps/eva_body_r44.json').read_text())
    physics=json.loads((BASE/'runtime/projectseele-local-maps/articulated_bodies_r35.json').read_text())
    out_assets=OUT/'assets/projectseele'
    for directory in ('mesh','geo','textures/entity'):(out_assets/directory).mkdir(parents=True,exist_ok=True)
    out_runtime=OUT/'projectseele-local-maps';out_runtime.mkdir(parents=True,exist_ok=True)
    for slot,short,model in [(3,'un00','eva_prototype'),(4,'un01','eva_un01')]:
        folder=BASE/'tripo_pipeline'/short;geometry=np.load(folder/'lod0_geometry.npz')
        landmarks=json.loads((folder/'rig_candidate/rig_landmarks.json').read_text())
        skin=json.loads((folder/'rig_candidate/smoothed_skin.json').read_text())
        scale=192/(geometry['vertices'][:,1].max()-geometry['vertices'][:,1].min())
        vertices=geometry['vertices'].astype(float);vertices[:,1]-=vertices[:,1].min();vertices*=scale
        triangles=geometry['triangles'];uv=geometry['uv'].copy();uv[:,:,1]=1-uv[:,:,1]
        normals=geometry['normals'];ids=np.array(skin['skin_indices']).reshape(-1,4);weights=np.array(skin['skin_weights']).reshape(-1,4)
        old_geo=json.loads((SOURCE/'geo'/f'{model}.geo.json').read_text());geo=copy.deepcopy(old_geo)
        old={b['name']:b for b in old_geo['minecraft:geometry'][0]['bones']}
        measured={b['name']:b for b in landmarks['bones']}
        positions={n:np.array(b['pivot'],float)*[-1,1,1]for n,b in old.items()}
        for n,b in measured.items():positions[n]=np.array(b['pivot'])*scale
        for side in ('l','r'):
            positions['wrist_'+side]=positions['hand_'+side].copy()
            positions['ankle_'+side]=positions['foot_'+side].copy()
            positions['r30_knee_socket_'+side]=positions['shin_'+side].copy()
            positions['r30_elbow_socket_'+side]=positions['forearm_'+side].copy()
            positions['clavicle_'+side]=np.array([0,positions['arm_'+side][1],positions['arm_'+side][2]])
        positions['neck']=positions['head'].copy();positions['aim_pitch']=positions['clavicle_l'].copy()
        for weapon in ('knife','cannon','lance','n2'):positions[weapon]=positions['hand_r'].copy()
        # Unused legacy marker/adapter names remain resolvable. The new fingers
        # attach directly to their measured chain; those adapters deform nothing.
        done=set(measured)|{'neck','aim_pitch','knife','cannon','lance','n2'}|{a+s for a in ('wrist_','ankle_','r30_knee_socket_','r30_elbow_socket_','clavicle_')for s in ('l','r')}
        def move_marker(n):
            if n in done:return
            b=old[n];parent=b.get('parent')
            if parent:
                move_marker(parent)
                positions[n]=positions[parent]+(np.array(b['pivot'])-np.array(old[parent]['pivot']))*[-1,1,1]
            done.add(n)
        for n in old:move_marker(n)
        bones=[]
        for old_bone in old_geo['minecraft:geometry'][0]['bones']:
            b=copy.deepcopy(old_bone);n=b['name'];b['pivot']=np.round(positions[n]*[-1,1,1],6).tolist();b.pop('cubes',None)
            b.pop('rotation',None)
            if n.startswith('finger_')and n in measured:b['parent']=measured[n]['parent']
            bones.append(b)
        for n,b in measured.items():
            if n not in old:bones.append(dict(name=n,parent=b['parent'],pivot=np.round(positions[n]*[-1,1,1],6).tolist()))
        for segment in landmarks['segments']:
            n=segment['bone']
            if n.startswith('finger_')and '_distal_'in n:
                tip='tripo_tip_'+n
                bones.append(dict(name=tip,parent=n,pivot=np.round(np.array(segment['end'])*scale*[-1,1,1],6).tolist()))
        bones.append(dict(name='tripo_hand_adapter_r48',parent='root',pivot=[0,0,0]))
        by_name={b['name']:b for b in bones}
        geo['minecraft:geometry'][0]['bones']=bones
        geo['minecraft:geometry'][0]['description'].update(texture_width=4096,texture_height=4096)
        palette=skin['bones'];dominant=ids[np.arange(len(ids)),np.argmax(weights,axis=1)]
        face_owners=[]
        for face in triangles:
            tally={}
            for vertex in face:
                for bone,w in zip(ids[vertex],weights[vertex]):tally[bone]=tally.get(bone,0)+w
            face_owners.append(palette[max(tally,key=tally.get)])
        face_owners=np.array(face_owners);parts={};joint_skins={};support={}
        for owner in sorted(set(face_owners)):
            selected=face_owners==owner;owner_index=palette.index(owner);all_faces=triangles[selected]
            own_weights=np.where(ids[all_faces]==owner_index,weights[all_faces],0).sum(2)
            rigid=(own_weights.min(1)>1-1e-6)
            for suffix,keep in [('',rigid),('_blend',~rigid)]:
                if not np.any(keep):continue
                selected_indices=np.flatnonzero(selected)[keep];faces=triangles[selected_indices];pivot=np.array(by_name[owner]['pivot'])
                part_name=owner if not suffix else 'tripo_blend_'+owner
                if suffix:
                    bones.append(dict(name=part_name,parent=owner,pivot=pivot.tolist()))
                data=np.concatenate([vertices[faces]*[-1,1,1]-pivot,uv[selected_indices],normals[selected_indices]*[-1,1,1]],axis=2)
                parts[part_name]=dict(pivot=pivot.tolist(),vertices=np.round(data,6).ravel().tolist())
                if suffix:
                    influences={};face_ids=ids[faces].reshape(-1,4);face_weights=weights[faces].reshape(-1,4)
                    for index in np.unique(face_ids):
                        values=np.where(face_ids==index,face_weights,0).sum(1)
                        if values.max()>0:influences[palette[index]]=np.round(values,7).tolist()
                    joint_skins[part_name]=dict(influences=influences)
            if owner not in ('knife','cannon','lance','n2','entry_plug'):
                points=np.unique(vertices[all_faces].reshape(-1,3).round(5),axis=0)
                support[owner]=points[ConvexHull(points).vertices].tolist()
        mesh=dict(format_version=1,stride=8,model_height=192,source='Owner supplied Tripo '+short+'; unchanged surface, measured R48 skeleton with Mesh2Motion boundary smoothing',
                  parts=parts,jointSkins=joint_skins,triangleCount=len(triangles),tripo_r48_candidate=True)
        (out_assets/'mesh'/f'{model}.mesh.json').write_text(json.dumps(mesh,separators=(',',':')),'utf8')
        (out_assets/'geo'/f'{model}.geo.json').write_text(json.dumps(geo,indent=2),'utf8')
        # Texture conversion stays beside intake resources. Preserve the owner's
        # original surface appearance and UV layout in the native candidate.
        textures(short)
        for suffix in ('','_n','_s'):
            source=SOURCE/'textures/entity'/f'tripo_{short}_r48{suffix}.png'
            if source.exists():shutil.copy2(source,out_assets/'textures/entity'/f'{model}{suffix}.png')
        paint_path=out_assets/'textures/entity'/f'{model}.png';paint=Image.open(paint_path).convert('RGBA')
        selection=Image.new('L',paint.size);draw=ImageDraw.Draw(selection)
        centres=geometry['vertices'][triangles].mean(1)
        eye_region=(abs(centres[:,0])<(.016 if slot==3 else .034))&(centres[:,1]>(.847 if slot==3 else .875))&(centres[:,1]<(.895 if slot==3 else .922))&(centres[:,2]<-.018)
        for row in geometry['uv'][eye_region]:draw.polygon([(float(u*paint.width),float((1-v)*paint.height))for u,v in row],fill=255)
        pixels=np.array(paint);rgb=pixels[:,:,:3].astype(float)
        colour=(rgb[:,:,1]>rgb[:,:,0]*1.12)&(rgb[:,:,1]>rgb[:,:,2]*.93)&(rgb[:,:,1]>45)if slot==3 else (rgb[:,:,0]>rgb[:,:,1]*1.20)&(rgb[:,:,1]>rgb[:,:,2]*1.08)&(rgb[:,:,0]>70)
        mask=(np.array(selection)>0)&colour;eyes=pixels.copy();eyes[:,:,3]=np.where(mask,255,0)
        Image.fromarray(eyes).save(out_assets/'textures/entity'/f'{model}_eyes.png')
        pixels[mask,:3]=[3,4,3];Image.fromarray(pixels).save(paint_path)
        body['rigs'][str(slot)]=[{k:v for k,v in b.items()if k in ('name','parent','pivot','rotation')}for b in bones]
        body['rig_support'][str(slot)]=support
        eye_y=.871 if slot==3 else .898
        head=vertices[(abs(vertices[:,0])<1.6)&(abs(vertices[:,1]-eye_y*scale)<1.1)]
        body['eye_positions'][str(slot)]=[0,float(eye_y*scale),float(np.quantile(head[:,2],.05))]
        # Re-measure existing physical bodies rather than keeping the old UN
        # silhouette as an invisible collision actor behind the new surface.
        physical=physics['models'][str(slot)];physical['render_rig']=body['rigs'][str(slot)]
        physical_parts={row['name']:row for row in physical['bodies']}
        groups={n:[]for n in physical_parts}
        for part_name,part in parts.items():
            owner=part_name
            while owner not in physical_parts and owner in by_name:owner=by_name[owner].get('parent')
            if part_name.startswith('tripo_blend_'):
                owner=part_name.removeprefix('tripo_blend_')
                while owner not in physical_parts and owner in by_name:owner=by_name[owner].get('parent')
            if owner in groups:
                xyz=(np.asarray(part['vertices']).reshape(-1,8)[:,:3]+part['pivot'])*[-1,1,1]*.0125
                groups[owner].append(xyz)
        for bone,row in physical_parts.items():
            if not groups[bone]:continue
            points=np.unique(np.concatenate(groups[bone]).round(6),axis=0);low=points.min(0);high=points.max(0);centre=(low+high)/2
            bind=np.eye(4);bind[:3,3]=centre;local=points-centre;hull=ConvexHull(local)
            row['bind']=bind.ravel().tolist();row['initial']=bind.ravel().tolist()
            row['hulls']=[local[hull.vertices].round(6).tolist()];row['hull_planes']=[np.unique(hull.equations.round(6),axis=0).tolist()]
            row['shape']='box';row['size']=((high-low)/2).round(6).tolist()
            joint=np.asarray(row['joint']).reshape(4,4);joint[:3,3]=positions[bone]*.0125;row['joint']=joint.ravel().tolist()
        gameplay=json.loads((BASE/'runtime/projectseele-local-maps'/f'eva_gameplay_r44_{slot}.json').read_text())
        gameplay['rig_contract_r44']=body['rigs'][str(slot)]
        (out_runtime/f'eva_gameplay_r44_{slot}.json').write_text(json.dumps(gameplay,separators=(',',':')),'utf8')
        (folder/'rig_candidate/native_mapping.json').write_text(json.dumps(dict(model=model,rig_key=slot,bones=len(bones),triangles=len(triangles),
            rigid_gpu_triangles=sum(len(p['vertices'])//24 for n,p in parts.items()if n not in joint_skins),
            blended_joint_triangles=sum(len(parts[n]['vertices'])//24 for n in joint_skins),
            gameplay_geometry_candidate_only=True,remaining=['actual finger poses and weapon grips','dorsal entry-plug opening and pose binding','physics profile regeneration','native game and motion verification']),indent=2),'utf8')
        print(model,len(bones),'bones',len(triangles),'triangles; candidate only',flush=True)
    (out_runtime/'eva_body_r44.json').write_text(json.dumps(body,separators=(',',':')),'utf8')
    (out_runtime/'articulated_bodies_r35.json').write_text(json.dumps(physics,separators=(',',':')),'utf8')

if __name__=='__main__':main()

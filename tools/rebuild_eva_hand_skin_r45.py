"""Continuous EVA glove surface on the anatomical neutral skeleton.

The artist palm and its finger boundary are retained. Finger skin is a loft
through measured phalanx lengths, with narrow DQ skin bands at real hinges.
No exposed ball joints, capsule parts or changes to the original full mesh.
"""
from pathlib import Path
import argparse, collections, copy, json
import numpy as np
import make_tiger_unit01_pack as tiger
from author_anatomical_hand_rig_r45 import model_matrix, unit

ROOT = Path(__file__).resolve().parents[1]

def smooth(v):
    v = np.clip(v, 0, 1)
    return v*v*(3-2*v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--basis', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=False)
    c = json.loads((a.basis/'hand_rig_contract.json').read_text())
    name = f"eva_unit0{c['rig']}"
    geo = json.loads((a.basis/(name+'.geo.json')).read_text())
    bones = {b['name']:b for b in geo['minecraft:geometry'][0]['bones']}; cache = {}
    v, uv, normals, faces = tiger.parse_obj(Path(c['source']).read_text())
    tiger.CLEAN_GRIP_FINGERS = False
    fb, _, _ = tiger.discover_finger_rig(v, faces)
    owners = tiger.complete_face_owners(v, faces, fb)
    minimum = min(p[1] for p in v); scale = 192/(max(p[1] for p in v)-minimum)/16
    native = lambda p: (np.asarray(p)-[0,minimum,0])*[-1,1,-1]*scale
    src = json.loads((ROOT/f'run/resourcepacks/eva_real_model/assets/projectseele/mesh/{name}.mesh.json').read_text())
    def membership():
        found=collections.defaultdict(set)
        for i,face in enumerate(faces):
            for ref in face:found[tuple(np.round(v[ref[0]],6))].add(owners[i])
        return found
    memberships=membership(); corrected=[]
    for side in ['l','r']:
        wrist={pt for pt,names in memberships.items() if 'forearm_'+side in names}
        for i,face in enumerate(faces):
            if owners[i]=='finger_thumb_'+side and any(tuple(np.round(v[r[0]],6)) in wrist for r in face):
                corrected.append(dict(face=i,old_owner=owners[i],new_owner='hand_'+side));owners[i]='hand_'+side
    memberships=membership()
    result = dict(format_version=1, model_height=192, stride=8,
                  source='Original EVA palm with continuous anatomical finger skin; independent 30-joint rig',
                  parts={}, jointSkins={}, r37_mouth={'preserve_auto_joint_seams':True})
    audit = []
    for side in ['l','r']:
        hand = 'hand_'+side; h = c['hands'][side]
        palette = [hand,'forearm_'+side]+[j['name'] for d in h['digits'].values() for j in d['joints']]
        slot = {n:i for i,n in enumerate(palette)}; vertices = []; weights = []
        thumb_border = np.asarray([native(k) for k,names in memberships.items() if hand in names and any(n.startswith('finger_thumb_') and n.endswith('_'+side) for n in names)])
        thumb_cmc = h['digits']['thumb']['joints'][0]['name']
        wrist_border=np.asarray([native(k) for k,names in memberships.items() if hand in names and 'forearm_'+side in names])
        def tri(points, texcoords, ns, ws):
            if np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0])) < 1e-12: return
            for p,t,n,w in zip(points,texcoords,ns,ws):
                vertices.extend([*(np.asarray(p)*[-1,1,1]*16-np.asarray(bones[hand]['pivot'])),*t,*(unit(n)*[-1,1,1])]); weights.append(w)
        palm_weight = np.eye(len(palette))[slot[hand]]
        def palm_skin(point):
            wrist_distance=float(np.linalg.norm(wrist_border-np.asarray(point),axis=1).min())
            w=palm_weight.copy()
            wrist_weight=.5*(1-float(smooth(wrist_distance/.375)))
            w*=1-wrist_weight;w[slot['forearm_'+side]]+=wrist_weight
            return w
        for i, face in enumerate(faces):
            if owners[i] != hand: continue
            ps = [native(v[r[0]]) for r in face]
            ts = [[uv[r[1]][0]*.5,1-uv[r[1]][1]] for r in face]
            ns = [np.asarray(normals[r[2]] if r[2]>=0 else tiger.face_normal([v[x[0]] for x in face]))*[-1,1,-1] for r in face]
            patches=[(np.asarray(ps),np.asarray(ts),np.asarray(ns))]
            for _ in range(2):
                refined=[]
                for arrays in patches:
                    both=[np.concatenate([x,(x+np.roll(x,-1,axis=0))*.5]) for x in arrays]
                    for ids in [(0,3,5),(3,1,4),(5,4,2),(3,4,5)]:refined.append(tuple(x[list(ids)] for x in both))
                patches=refined
            for ps,ts,ns in patches:tri(ps,ts,ns,[palm_skin(p) for p in ps])
        for digit, d in h['digits'].items():
            joints = d['joints']; visible_start = 0
            j0 = joints[visible_start]; head = np.asarray(j0['head_bind'])
            along = unit(np.asarray(j0['tip_bind'])-head)
            palmar = np.asarray(h['palmar_normal_bind']); palmar = unit(palmar-along*(palmar@along))
            cross = unit(np.cross(palmar,along)); dorsal = -palmar
            lengths = [j['length'] for j in joints[visible_start:]]
            total = sum(lengths); hinge_s = np.r_[0,np.cumsum(lengths)]
            dim = next(q for q in c['construction']['dimensions'] if q['side']==side and q['digit']==digit)
            rx,rz = dim['radii']
            base = [native(k) for k,names in memberships.items() if hand in names and any(n.startswith('finger_'+digit+'_') and n.endswith('_'+side) for n in names)]
            base = np.asarray(base); bc = base.mean(0)
            angles = np.arctan2((base-bc)@dorsal, (base-bc)@cross)
            order = np.argsort(angles); base=base[order]; angles=angles[order]
            if digit=='thumb':
                # A seated soft metacarpal sits below the rigid artist palm.
                # Do not drag the wrist or thumb armour along with opposition.
                # Close the vacated artist cut behind that overlapping socket.
                centre=base.mean(0);face_normal=unit(np.cross(base[1]-base[0],base[2]-base[0]))
                palm_uv=np.asarray(src['parts']['finger_thumb_'+side]['vertices'][3:5])
                for k in range(len(base)):
                    ps=[centre,base[k],base[(k+1)%len(base)]]
                    tri(ps,[palm_uv]*3,[face_normal]*3,[palm_skin(q)for q in ps])
                angles=np.linspace(-np.pi,np.pi,8,endpoint=False)
                base=np.asarray([head+cross*np.cos(angle)*rx*.2+dorsal*np.sin(angle)*rz*.2 for angle in angles])
            # Split existing boundary edges. Every boundary point remains on
            # the artist palm and has exactly the same palm skin weights.
            subdivisions = 4; ring_angles=[]; boundary=[]
            for k in range(len(base)):
                nxt=(k+1)%len(base); end_angle=angles[nxt]+(2*np.pi if nxt==0 else 0)
                for step in range(subdivisions):
                    t=step/subdivisions; boundary.append(base[k]*(1-t)+base[nxt]*t); ring_angles.append(angles[k]*(1-t)+end_angle*t)
            ring_angles=np.asarray(ring_angles); N=len(ring_angles)
            uniform_uv=np.asarray(src['parts']['finger_'+digit+'_'+side]['vertices'][3:5])
            samples = np.unique(np.r_[np.linspace(0,total*.91,32), hinge_s[:-1],
                *[s+np.array([-.045,-.024,0,.024,.045])*total for s in hinge_s[1:-1]],
                total*np.array([.935,.955,.974,.989,.997])])
            samples=samples[(samples>=0)&(samples<total)]
            rings=[]; ring_ns=[]; ring_ws=[]
            for index,s in enumerate(samples):
                f=s/total; centre=head+along*s;frame_along=along;frame_cross=cross;frame_dorsal=dorsal
                if digit=='thumb':
                    segment=min(len(joints)-1,max(0,int(np.searchsorted(hinge_s,s,side='right')-1)))
                    joint=joints[segment];frame_along=unit(np.asarray(joint['tip_bind'])-np.asarray(joint['head_bind']))
                    centre=np.asarray(joint['head_bind'])+frame_along*(s-hinge_s[segment])
                    frame_cross=unit(np.cross(palmar,frame_along));frame_dorsal=unit(np.cross(frame_along,frame_cross))
                taper=np.interp(f,[0,.12,.46,.73,.89,1],[1,1,.96,.88,.78,0])
                if f>.89: taper=.78*np.sqrt(max(0,1-((f-.89)/.11)**2))
                # A rounded back and flatter finger pad, no barrel-shaped rods.
                xx=np.cos(ring_angles); zz=np.sin(ring_angles)
                section=centre+frame_cross[None,:]*(xx*rx*taper)[:,None]+frame_dorsal[None,:]*(zz*rz*taper)[:,None]
                join=float(smooth(s/(total*.18)))
                section=np.asarray(boundary)*(1-join)+section*join
                n=unit(cross*1.)
                norms=[unit(frame_cross*x/rx+frame_dorsal*z/rz+frame_along*max(0,(f-.89)/.11)) for x,z in zip(xx,zz)]
                w=np.zeros(len(palette)); seg=min(len(lengths)-1,max(0,int(np.searchsorted(hinge_s,s,side='right')-1)))
                w[slot[joints[visible_start+seg]['name']]]=1
                for k,hs in enumerate(hinge_s[1:-1],start=1):
                    band=min(lengths[k-1],lengths[k])*.28
                    if abs(s-hs)<=band:
                        t=float(smooth((s-hs+band)/(2*band))); w[:]=0
                        w[slot[joints[visible_start+k-1]['name']]]=1-t; w[slot[joints[visible_start+k]['name']]]=t
                base_blend=float(smooth(s/(total*.115)))
                if digit=='thumb':
                    # CMC moves the metacarpal under the existing palm, MCP
                    # and IP move the two visible phalanges.
                    w*=base_blend; w[slot[joints[0]['name']]]+=1-base_blend
                else: w=w*base_blend+palm_weight*(1-base_blend)
                rings.append(section); ring_ns.append(norms); ring_ws.append(w)
            for k in range(len(rings)-1):
                for t in range(N):
                    tn=(t+1)%N
                    for ids in [((k,t),(k,tn),(k+1,tn)),((k,t),(k+1,tn),(k+1,t))]:
                        pts=[rings[i][j] for i,j in ids]; ns=[ring_ns[i][j] for i,j in ids]; ws=[ring_ws[i] for i,j in ids]
                        tri(pts,[uniform_uv]*3,ns,ws)
            tip=np.asarray(joints[-1]['tip_bind'])
            for t in range(N):tri([rings[-1][t],rings[-1][(t+1)%N],tip],[uniform_uv]*3,[ring_ns[-1][t],ring_ns[-1][(t+1)%N],along],[ring_ws[-1]]*3)
            audit.append(dict(side=side,digit=digit,source_boundary_vertices=len(base),ring_count=len(rings),visible_segments=len(lengths),axis=along.tolist()))
        weights=np.asarray(weights)
        result['parts'][hand]=dict(pivot=bones[hand]['pivot'],vertices=np.round(vertices,7).tolist())
        result['jointSkins'][hand]=dict(influences={n:np.round(weights[:,i],7).tolist() for i,n in enumerate(palette)},inverseBindColumnMajor={n:np.linalg.inv(model_matrix(bones,n,cache)).T.reshape(-1).tolist() for n in palette})
    c['construction']['fingers']='Continuous glove skin; original palm boundaries, measured lengths, narrow DQ joint transitions, no exposed spheres'
    c['construction']['skin_loft']=audit; c['construction']['visual_passed']=False
    c['construction']['source_component_owner_corrections']=corrected
    c['angle_convention']='Desired local=neutral_local*Rz(side*splay)*Ry(side*twist)*Rx(-flexion); both mesh and skeleton authored at anatomical neutral.'
    (a.out/(name+'.geo.json')).write_text(json.dumps(geo,indent=2),'utf8')
    (a.out/(name+'_anatomical_hands_r45.mesh.json')).write_text(json.dumps(result,separators=(',',':')),'utf8')
    (a.out/'hand_rig_contract.json').write_text(json.dumps(c,indent=2),'utf8')
    print(json.dumps({'new_surface':str(a.out),'triangles':len(vertices)//24,'original_palm_preserved':True,'visual_accepted':False}))

if __name__=='__main__':main()

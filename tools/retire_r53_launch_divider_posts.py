"""Retire the explicitly rejected launch dividers and re-seat their rail brackets.

The three centre curves, gates, actors and completed task progress are retained.
Plan on a saved world; apply uses a world lock, exact preimages and full backups.
"""
from pathlib import Path
import argparse, collections, copy, gzip, hashlib, io, json, msvcrt, subprocess
import numpy as np
import nbtlib
import regional_voxels as vox
from query_blocks import read_box, iter_block_entities
from finish_r53_launch_armor import protected_cells
from transplant_s22_authority import read_region, parse_chunk, build_region, chunk_blob
from apply_s20_approved_semantic_repairs import atomic_replace, decompress_chunk

DIM='projectseele:geofront'
LO=(5,-1024,18);HI=(55,-957,142)
AIR={'minecraft:air','minecraft:cave_air','minecraft:void_air'}
FACES=np.array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5])

def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(doc):return (json.dumps(doc,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def selected(p):
    x,y,z=p
    return -1024<=y<=-957 and (5<=x<=13 or 47<=x<=55) and any(a<=z<=b for a,b in ((18,46),(66,94),(114,142)))

def fingerprint(path,java,gson,classes):
    return subprocess.check_output([str(java),'-cp',str(classes)+';'+str(gson),'JsonDocumentFingerprintR53',str(path)],text=True).strip()

def mesh(name,leg,side,component,vertices):
    v=np.asarray(vertices);centre=v.mean(axis=0)
    t=(v-centre).astype(np.float32).astype(float)[FACES]
    rgb=np.column_stack([t,np.tile([.30,.36,.39],(len(t),1))])
    return dict(name=name,leg=leg,side=side,component=component,
                frame=dict(translation=centre.tolist(),quaternion_xyzw=[0,0,0,1]),triangles_rgb=rgb.ravel().tolist())

def beam(name,a,b,width,leg,side):
    a=np.asarray(a);b=np.asarray(b);z=b-a;length=np.linalg.norm(z);z/=length
    x=np.cross(z,[0,1,0]);x=np.cross(z,[1,0,0])if np.linalg.norm(x)<.1 else x
    x/=np.linalg.norm(x);y=np.cross(z,x);h=width/2
    v=np.array([[-h,-h,0],[h,-h,0],[h,h,0],[-h,h,0],[-h,-h,length],[h,-h,length],[h,h,length],[-h,h,length]])
    return mesh(name,leg,side,'bracket',v@np.stack([x,y,z],axis=1).T+a)

def plan(w,out,java,gson,classes):
    assert not out.exists(),'Frozen candidate already exists'
    out.mkdir(parents=True);(out/'candidate').mkdir();(out/'before').mkdir()
    c=read_box(w,DIM,(5,-1024,17),(55,-953,142));tags=dict(iter_block_entities(w,DIM,LO,HI))
    protected=protected_cells(w)
    names=['ROOT_RUNTIME_DIRECTORY.json','ROOT_MECHANICAL_OWNER.json','ROOT_ASSEMBLY_BUNDLE.json','ROOT_AIR_TRANSPORT.json','personnel_lifts_r52.json','UPRIGHT_GUIDEWAY_SOURCE.json']
    docs={n:json.loads((w/n).read_bytes())for n in names};old=copy.deepcopy(docs)
    bundle=docs['ROOT_ASSEMBLY_BUNDLE.json'];oldfp=bundle['directory_fingerprint'];g=docs['UPRIGHT_GUIDEWAY_SOURCE.json']
    assert fingerprint(w/'ROOT_RUNTIME_DIRECTORY.json',java,gson,classes)==oldfp
    requests={s['socket_id']:s for s in g['socket_requests']};pieces={p['name']:p for p in g['pieces']}
    affected=[a for a in g['anchors'] if selected(a['at'])]
    assert len(affected)==28
    replacements={};added=[];removed=set();proof=[]
    for a in affected:
        x,y,z=a['at'];rear=z-25;assert rear in (17,65,113)
        q=requests[a['socket_id']];A=np.array(q['rail_bearing']);oldseat=pieces[a['seat_piece']]
        index=a['seat_piece'].split('/')[-1]
        old_names=[n for n in pieces if n==a['seat_piece'] or n==f'upright_native_connector/{index}' or n.startswith(f'upright_native_connector/{index}/')]
        removed.update(old_names)
        # A triangulated two-foot bracket transfers the same rail weld to the
        # existing rear fixed pier. It stays wholly inside the retired divider
        # strip; the rail path/head/weld and gate pocket never move.
        feet=[]
        for j,yy in enumerate((y,y+4)):
            at=(x,yy,rear);state=c[at]
            assert state.split('[')[0] in {'projectseele:nerv_launch_armor','projectseele:nerv_machine_edge','projectseele:nerv_shaft_panel'}
            B=np.array([x+.5,yy+.5,rear+1.]);assert np.linalg.norm(B-A)<26
            width=.28
            added.append(beam(f'upright_rear_pier_bracket/{index}/{j}',A,B,width,a['leg'],oldseat['side']))
            seatname=f'upright_rear_pier_seat/{index}/{j}';h=.24
            v=np.array([[-h,-h,0],[h,-h,0],[h,h,0],[-h,h,0],[-h,-h,.06],[h,-h,.06],[h,h,.06],[-h,h,.06]])+B
            added.append(mesh(seatname,a['leg'],oldseat['side'],'native_seat',v))
            feet.append(dict(leg=a['leg'],at=list(at),state=state,bearing=B.tolist(),normal=[0.,0.,1.],seat_piece=seatname,socket_id=a['socket_id']))
        replacements[tuple(a['at'])]=feet
        proof.append(dict(old=copy.deepcopy(a),new=feet,weld_unchanged=q['rail_bearing'],steel_width_m=width,
                          native_feet_vertical_separation_m=4.,maximum_connector_length_m=max(float(np.linalg.norm(np.array(v['bearing'])-A))for v in feet)))
    g['pieces']=[p for p in g['pieces'] if p['name']not in removed]+added
    g['anchors']=[a for a in g['anchors'] if not selected(a['at'])]+[f for fs in replacements.values()for f in fs]
    assert g['paths']==old['UPRIGHT_GUIDEWAY_SOURCE.json']['paths']
    assert all(p==pieces[p['name']]for p in g['pieces'] if p['name']in pieces)
    g['rear_pier_reseat_r53']=dict(retired_native_posts=28,source_geometry_unchanged=True,brackets=proof)
    guide_raw=encode(g);newguide=sha(guide_raw);oldguide=bundle['upright_guideway']['sha256']
    rows=[]
    allowed={'projectseele:nerv_launch_armor','projectseele:nerv_machine_edge','projectseele:nerv_strip_light','projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','minecraft:sea_lantern','minecraft:iron_block','minecraft:black_concrete'}
    for p,s in c.items():
        if not selected(p) or s in AIR:continue
        assert p not in tags and (p not in protected or p in replacements),(p,'unrelated mechanical point')
        assert s.split('[')[0]in allowed,(p,s)
        rows.append(dict(pos=p,old=s,new='minecraft:air'))
    assert all(p in {tuple(r['pos'])for r in rows}for p in replacements)
    changes=[]
    def transform(v,path=''):
        if isinstance(v,dict):
            if 'position'in v and tuple(v['position'])in replacements:
                raise AssertionError('Cell list must be transformed as a complete group')
            for k in list(v):
                if isinstance(v[k],list) and v[k] and all(isinstance(e,dict) and 'position'in e and 'state'in e for e in v[k]):
                    outcells=[]
                    for r in v[k]:
                        p=tuple(r.get('position',[]))
                        if p in replacements:
                            assert r['state']==protected[p]
                            outcells.extend(dict(position=f['at'],state=f['state'])for f in replacements[p]);changes.append(path+'/cells/'+str(p))
                        else:outcells.append(r)
                    unique={tuple(r['position']):r for r in outcells}
                    assert len(unique)==len(outcells)
                    v[k]=outcells
                elif v[k]==oldguide:v[k]=newguide
                else:transform(v[k],path+'/'+k)
        elif isinstance(v,list):
            for i,e in enumerate(v):transform(e,path+'/'+str(i))
    for n in ['ROOT_RUNTIME_DIRECTORY.json','ROOT_MECHANICAL_OWNER.json']:transform(docs[n],n)
    assert len(changes)==112
    receipt=dict(scope='User rejected tall front launch dividers',removed_cells=len(rows),rail_connections=proof,
                 routes_gates_and_actors_unchanged=True,game_verification_pending=True)
    receipt_raw=encode(receipt);(out/'RESEAT_DESIGN.json').write_bytes(receipt_raw)
    docs['ROOT_MECHANICAL_OWNER.json']['commissioning_receipt_sha256']=sha(receipt_raw)
    dpath=out/'candidate/ROOT_RUNTIME_DIRECTORY.json';dpath.write_bytes(encode(docs['ROOT_RUNTIME_DIRECTORY.json']))
    newfp=fingerprint(dpath,java,gson,classes)
    def replace(v):
        if isinstance(v,dict):return {k:replace(e)for k,e in v.items()}
        if isinstance(v,list):return [replace(e)for e in v]
        return newfp if v==oldfp else v
    for n in names:docs[n]=replace(docs[n])
    for n in names:
        if n=='ROOT_ASSEMBLY_BUNDLE.json':continue
        raw=encode(docs[n]);(out/'candidate'/n).write_bytes(raw)
    bundle=docs['ROOT_ASSEMBLY_BUNDLE.json']
    for key in ('directory','mechanical_owner','upright_guideway','personnel_lifts','air_transport'):
        bundle[key]['sha256']=sha((out/'candidate'/bundle[key]['file']).read_bytes())
    (out/'candidate/ROOT_ASSEMBLY_BUNDLE.json').write_bytes(encode(bundle))
    for n in names:(out/'before'/n).write_bytes((w/n).read_bytes())
    (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(encode(rows),mtime=0))
    report=dict(world=str(w),old_directory=oldfp,new_directory=newfp,old_guide=oldguide,new_guide=newguide,
                cells=len(rows),rebound_cell_entries=len(changes),old_anchors=len(old['UPRIGHT_GUIDEWAY_SOURCE.json']['anchors']),
                new_anchors=len(g['anchors']),removed_pieces=len(removed),added_pieces=len(added),
                frozen_sources={n:sha((w/n).read_bytes())for n in names},route_centres=[-11.5,30.5,72.5],
                canonical_references={fingerprint(out/'before'/n,java,gson,classes):fingerprint(out/'candidate'/n,java,gson,classes)for n in names})
    (out/'PLAN.json').write_bytes(encode(report));print(report)

def install(w,out):
    report=json.loads((out/'PLAN.json').read_bytes())
    assert not (out/'INSTALLED.json').exists()
    with (w/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        for n,h in report['frozen_sources'].items():assert sha((w/n).read_bytes())==h,n
        rows=json.loads(gzip.decompress((out/'EXACT_DELTA.json.gz').read_bytes()))
        c=read_box(w,DIM,LO,HI);tags=dict(iter_block_entities(w,DIM,LO,HI))
        assert all(c[tuple(r['pos'])]==r['old']and tuple(r['pos'])not in tags for r in rows)
        pairs={report['old_directory']:report['new_directory'],report['old_guide']:report['new_guide'],
               report['frozen_sources']['ROOT_ASSEMBLY_BUNDLE.json']:sha((out/'candidate/ROOT_ASSEMBLY_BUNDLE.json').read_bytes())}
        pairs.update(report['canonical_references'])
        pairs={k:v for k,v in pairs.items()if k!=v}
        runtime=w/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat'
        current=nbtlib.load(runtime)['data']
        assert str(current['DirectoryFingerprint'])==report['old_directory'] and not str(current['Fault'])
        assert all(str(j['Phase'])=='PARKED'for j in current['Jobs']), 'Retire only while original units are parked'
        edits=[];journal=[]
        def rewrite(tag,mapping,where,found):
            if isinstance(tag,nbtlib.Compound):
                for k in list(tag):
                    if isinstance(tag[k],nbtlib.String) and str(tag[k])in mapping:
                        old=str(tag[k]);tag[k]=nbtlib.String(mapping[old]);found.append(where+'/'+k)
                    else:rewrite(tag[k],mapping,where+'/'+k,found)
            elif isinstance(tag,nbtlib.List):
                for i in range(len(tag)):
                    if isinstance(tag[i],nbtlib.String)and str(tag[i])in mapping:
                        tag[i]=nbtlib.String(mapping[str(tag[i])]);found.append(where+'/'+str(i))
                    else:rewrite(tag[i],mapping,where+'/'+str(i),found)
        def changed(tag,label):
            before=copy.deepcopy(tag);found=[];rewrite(tag,pairs,label,found)
            if found:
                inverse=copy.deepcopy(tag);rewrite(inverse,{v:k for k,v in pairs.items()},'',[])
                assert inverse.snbt()==before.snbt(),'Only exact installation references may change'
                journal.append(dict(path=label,fields=found))
            return bool(found)
        for p in w.rglob('*.dat'):
            raw=p.read_bytes()
            unpacked=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
            if not any(key.encode()in unpacked for key in pairs):continue
            try:tag=nbtlib.load(p)
            except (OSError,ValueError):continue
            if changed(tag,p.relative_to(w).as_posix()):
                stream=io.BytesIO();tag.write(stream)
                edits.append((p,raw,gzip.compress(stream.getvalue(),mtime=0)))
        for folder in [w/'entities',*(w/'dimensions').glob('*/*/entities')]:
            if not folder.exists():continue
            for p in folder.glob('r.*.*.mca'):
                raw=p.read_bytes()
                if not raw:continue
                stamps,blobs=read_region(p);dirty=False
                for i,blob in enumerate(blobs):
                    if blob is None:continue
                    length=int.from_bytes(blob[:4],'big')
                    unpacked=decompress_chunk(blob[4],blob[5:4+length])
                    if not any(key.encode()in unpacked for key in pairs):continue
                    tag=parse_chunk(blob)
                    if changed(tag,p.relative_to(w).as_posix()+'/'+str(i)):
                        blobs[i]=chunk_blob(tag);dirty=True
                if dirty:edits.append((p,raw,build_region(stamps,blobs)))
        assert any(p==runtime for p,_,_ in edits)
        for n in report['frozen_sources']:edits.append((w/n,(w/n).read_bytes(),(out/'candidate'/n).read_bytes()))
        backup=out/'install_before';backup.mkdir()
        for p,before,after in edits:
            target=backup/p.relative_to(w);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(before)
        (out/'CONFIGURATION_REFERENCE_CHANGES.json').write_bytes(encode(journal))
        vox.WORLD=w;vox.DIM=DIM;vox.OUT=out;painter=vox.Painter(vertical_bounds=(-1440,320))
        for r in rows:painter.exact((*r['pos'],*r['pos']),r['old'],r['new'],'retire_user_rejected_front_divider')
        painter.apply('retired_front_divider_posts',session_lock=lock)
        written=[]
        try:
            for p,before,after in edits:
                assert p.read_bytes()==before
                atomic_replace(p,after);written.append((p,before))
                assert p.read_bytes()==after
            actual=read_box(w,DIM,LO,HI)
            assert all(actual[tuple(r['pos'])]==r['new']for r in rows)
        except BaseException:
            for p,before in reversed(written):atomic_replace(p,before)
            inverse=vox.Painter(vertical_bounds=(-1440,320))
            for r in rows:inverse.exact((*r['pos'],*r['pos']),r['new'],r['old'],'rollback_divider_reseat')
            inverse.apply('rollback_divider_reseat',session_lock=lock)
            raise
        result=dict(exact_readback=True,cells=len(rows),changed_files=[dict(path=p.relative_to(w).as_posix(),before=sha(b),after=sha(a))for p,b,a in edits],
                    progress_and_identity_verified_by_inverse_nbt=True,field_changes=sum(len(j['fields'])for j in journal),native_commission_and_visual_review_pending=True)
        (out/'INSTALLED.json').write_bytes(encode(result));print({k:v for k,v in result.items()if k!='changed_files'})

def finish_outer_edges(w,out):
    report=json.loads((out/'PLAN.json').read_bytes());extra=out/'outer_edges_and_nested_manifests'
    assert (out/'INSTALLED.json').exists() and not (extra/'EXACT_DELTA.json.gz').exists()
    extra.mkdir(exist_ok=True);(extra/'before').mkdir(exist_ok=True)
    with(w/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        lo=(4,-1024,18);hi=(56,-957,142);c=read_box(w,DIM,lo,hi);tags=dict(iter_block_entities(w,DIM,lo,hi));protected=protected_cells(w)
        rows=[]
        for p,s in c.items():
            x,y,z=p
            if x not in (4,14,46,56)or not any(a<=z<=b for a,b in ((18,46),(66,94),(114,142)))or s in AIR:continue
            assert p not in tags and p not in protected
            assert s.split('[')[0]in {'projectseele:nerv_launch_armor','projectseele:nerv_machine_edge','projectseele:nerv_structural_panel','projectseele:nerv_strip_light','minecraft:iron_block','minecraft:sea_lantern','minecraft:black_concrete','minecraft:polished_basalt'},(p,s)
            rows.append(dict(pos=p,old=s,new='minecraft:air'))
        edits=[]
        for name in ('headquarters_command_doors.json','travel.json','headquarters.json'):
            p=w/'r52'/name;before=p.read_bytes();doc=json.loads(before)
            assert doc['directory_fingerprint']==report['old_directory']
            doc['directory_fingerprint']=report['new_directory']
            if name=='headquarters.json':
                doc['command_door_sha256']=sha(edits[0][2])
            edits.append((p,before,encode(doc)))
        (extra/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(encode(rows),mtime=0))
        vox.WORLD=w;vox.DIM=DIM;vox.OUT=extra;paint=vox.Painter(vertical_bounds=(-1440,320))
        for r in rows:paint.exact((*r['pos'],*r['pos']),r['old'],r['new'],'retire_front_divider_outer_edge')
        paint.apply('outer_divider_posts',session_lock=lock)
        for p,before,after in edits:
            (extra/'before'/p.name).write_bytes(before);assert p.read_bytes()==before
            atomic_replace(p,after);assert p.read_bytes()==after
        actual=read_box(w,DIM,lo,hi);assert all(actual[tuple(r['pos'])]==r['new']for r in rows)
        (extra/'INSTALLED.json').write_bytes(encode(dict(cells=len(rows),exact_readback=True,unchanged_gate_geometry_and_route_controls=True,
            configuration_changes=[dict(file=p.relative_to(w).as_posix(),before=sha(b),after=sha(a))for p,b,a in edits])))
        print('Outer posts removed',len(rows),'and three nested runtime manifests rebound')

def finish_air_reference(w,out,java,gson,classes):
    extra=out/'air_canonical_reference';assert not extra.exists()
    old=fingerprint(out/'before/ROOT_AIR_TRANSPORT.json',java,gson,classes)
    new=fingerprint(w/'ROOT_AIR_TRANSPORT.json',java,gson,classes)
    report=json.loads((out/'PLAN.json').read_bytes())
    before=json.loads((out/'before/ROOT_AIR_TRANSPORT.json').read_bytes());after=json.loads((w/'ROOT_AIR_TRANSPORT.json').read_bytes())
    assert before['directory_fingerprint']==report['old_directory'] and after['directory_fingerprint']==report['new_directory']
    before['directory_fingerprint']=report['new_directory'];assert before==after,'Aircraft geometry/mission changed'
    assert old!=new
    with(w/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        state=nbtlib.load(w/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat')['data']
        assert not str(state['Fault'])and str(state['DirectoryFingerprint'])==report['new_directory']
        air=nbtlib.load(w/'dimensions/projectseele/geofront/data/projectseele_nerv_air_transport_r52.dat')['data']
        assert all(str(j['Phase'])in {'COMPLETE','CANCELLED'}for j in air['Jobs']),'Active flight must finish before manifest reference migration'
        extra.mkdir();edits=[];fields=[]
        def rewrite(tag,src,dst,path,found):
            if isinstance(tag,(nbtlib.Compound,nbtlib.List)):
                for k in list(tag)if isinstance(tag,nbtlib.Compound)else range(len(tag)):
                    if isinstance(tag[k],nbtlib.String)and str(tag[k])==src:tag[k]=nbtlib.String(dst);found.append(path+(k,))
                    else:rewrite(tag[k],src,dst,path+(k,),found)
        def change(tag,path):
            before=copy.deepcopy(tag);found=[];rewrite(tag,old,new,(),found)
            if found:
                reverted=copy.deepcopy(tag)
                for address in found:
                    parent=reverted
                    for key in address[:-1]:parent=parent[key]
                    parent[address[-1]]=nbtlib.String(old)
                assert reverted.snbt()==before.snbt()
                fields.extend(path+'/'+('/'.join(map(str,address)))for address in found)
            return bool(found)
        for p in w.rglob('*.dat'):
            raw=p.read_bytes();unpacked=gzip.decompress(raw)if raw[:2]==b'\x1f\x8b'else raw
            if old.encode()not in unpacked:continue
            tag=nbtlib.load(p)
            if change(tag,p.relative_to(w).as_posix()):
                stream=io.BytesIO();tag.write(stream);edits.append((p,raw,gzip.compress(stream.getvalue(),mtime=0)))
        for folder in [w/'entities',*(w/'dimensions').glob('*/*/entities')]:
            if not folder.exists():continue
            for p in folder.glob('r.*.*.mca'):
                raw=p.read_bytes()
                if not raw:continue
                ts,blobs=read_region(p);dirty=False
                for i,blob in enumerate(blobs):
                    if blob is None:continue
                    size=int.from_bytes(blob[:4],'big');unpacked=decompress_chunk(blob[4],blob[5:4+size])
                    if old.encode()not in unpacked:continue
                    tag=parse_chunk(blob)
                    if change(tag,p.relative_to(w).as_posix()+'/'+str(i)):blobs[i]=chunk_blob(tag);dirty=True
                if dirty:edits.append((p,raw,build_region(ts,blobs)))
        assert fields and any('R52AircraftSample/Manifest'in f for f in fields)
        for p,b,v in edits:
            dest=extra/'before'/p.relative_to(w);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        written=[]
        try:
            for p,b,v in edits:
                assert p.read_bytes()==b;atomic_replace(p,v);written.append((p,b));assert p.read_bytes()==v
        except BaseException:
            for p,b in reversed(written):atomic_replace(p,b)
            raise
        (extra/'INSTALLED.json').write_bytes(encode(dict(old=old,new=new,fields=fields,exact_readback=True,other_nbt_verified_inverse_equal=True)))
        print('Canonical aircraft references migrated',len(fields),'fields in',len(edits),'files')

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--java',type=Path);p.add_argument('--gson',type=Path);p.add_argument('--classes',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--finish-outer-edges',action='store_true');p.add_argument('--finish-air-reference',action='store_true')
    a=p.parse_args()
    if a.finish_air_reference:
        assert a.java and a.gson and a.classes
        finish_air_reference(a.world,a.output,a.java,a.gson,a.classes)
    elif a.finish_outer_edges:finish_outer_edges(a.world,a.output)
    elif a.apply:install(a.world,a.output)
    else:
        assert a.java and a.gson and a.classes
        plan(a.world,a.output,a.java,a.gson,a.classes)

if __name__=='__main__':main()

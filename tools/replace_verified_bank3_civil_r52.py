"""Root-only finite replacement of the withdrawn continuous bank3 bore.

Reconstruct the native layer preceding its authored lining rather than
restoring the previous lying-carrier excavation. Preserve later devices,
doors and exact unrelated edits. The caller must supply new measured hulls
and a complete same-source nine-route geometry receipt before any planning.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse, gzip, hashlib, json, msvcrt
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
import regional_voxels as vox
from query_blocks import iter_selected_sections, iter_block_entities
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from prepare_continuous_upright_civil_r52 import slot, xyz_for, cuboids, RETIRED

OLD=BASE/'continuous_upright/civil_replacement'
WORLD=BASE/'WORLD_R52'
STAGE='verified_bank3_axial_throats_and_tv_lining'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def plan(args):
    out=args.output.resolve();assert out.is_relative_to(BASE.resolve())
    assert not (out/'CANDIDATE.npz').exists(), 'Never overwrite a measured candidate'
    out.mkdir(parents=True,exist_ok=True)
    measured=np.load(args.measurement/'MEASURED_SOURCE.npz')
    meta=json.loads((args.measurement/'MEASURED_REPORT.json').read_text())
    assert meta['directory_sha256']==sha(args.directory)
    hulls=json.loads(args.hulls.read_text())
    assert sha(args.hulls)==meta['hulls_sha256'] and hulls['root_design_sha256']==sha(args.directory)
    assert hulls['model_source_sha256']==args.model_sha, 'Actual bore hulls must include the final model geometry'
    model=Path(__file__).resolve().parents[1]/'src/main/resources/assets/projectseele/mesh/upright_outer_captured_r52.json'
    assert sha(model)==args.model_sha and sha(args.steel)==args.steel_sha
    proof=json.loads(args.geometry.read_text())
    assert len(proof['rows'])==9 and not proof['pairs'], 'Whole nine-route geometry must be clear'
    directory=json.loads(args.directory.read_text())
    expected={(l['id'],int(l['id'].split('/')[0].removeprefix('unit'))) for l in directory['legs'] if l['id'].endswith('/upright_continuous')}
    assert len(expected)==9 and {(r['leg'],r['variant']) for r in proof['rows']}==expected
    assert all(r['source_pairs']==0 and r['ten_bearing_samples_pass']==r['true_arc_samples'] for r in proof['rows'])
    lock=json.loads(args.geometry_lock.read_text())
    # Exact source pins are explicit command inputs, not copied from the old
    # model or renamed exploratory bounds.
    assert proof['model_sha256']==args.model_sha and proof['steel_sha256']==args.steel_sha
    assert lock['exit_code']==0
    for name,path,digest in [('ground',args.directory,sha(args.directory)),('model',model,args.model_sha),('steel',args.steel,args.steel_sha)]:
        actual=lock['actual_read_inputs'][name]
        assert Path(actual['path']).resolve()==path.resolve() and actual['sha256']==digest, ('Geometry input differs',name)
    for path,digest in lock['source_java_sha256'].items():assert sha(path)==digest, ('Geometry producer/source changed',path)
    previous=np.load(OLD/'CIVIL_CANDIDATE.npz')
    oldmeasurement=np.load(BASE/'continuous_upright/civil_measurement/MEASURED_SOURCE.npz')
    names=[];ids={}
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    def recode(palette):return np.array([code(str(s)) for s in palette],np.uint16)
    mapping=recode(previous['palette']);oldkeys=[tuple(map(int,k)) for k in previous['section_keys']]
    oldbefore={k:mapping[a] for k,a in zip(oldkeys,previous['before'])}
    oldafter={k:mapping[a] for k,a in zip(oldkeys,previous['after'])}
    oldbank={tuple(map(int,k)):a for k,a in zip(oldmeasurement['section_keys'],oldmeasurement['banks'])}
    newkeys=[tuple(map(int,k)) for k in measured['section_keys']]
    core=dict(zip(newkeys,measured['core']));shell=dict(zip(newkeys,measured['shell']))
    newbank=dict(zip(newkeys,measured['banks']))
    keys=set(oldkeys)|set(newkeys);selected=defaultdict(set)
    for cx,cz,sy in keys:selected[cx,cz].add(sy)
    current={}
    for cx,cz,sy,pal,values in iter_selected_sections(WORLD,'projectseele:geofront',selected,skip_unfinished=True):
        current[cx,cz,sy]=recode(pal)[values]
    assert keys<=current.keys(), ('Unmeasured current sections',len(keys-current.keys()))
    protected={k:np.zeros(4096,bool) for k in keys}
    gates=json.loads((BASE/'runtime_directory/gates/ROOT_GATES.json').read_text())['gates']
    for gate in gates:
        positions=[r['position'] for r in gate['supports']]
        phases=json.loads(gzip.decompress((BASE/'runtime_directory/gates'/gate['collision_steps']['cells_file']).read_bytes()))
        positions.extend(r['position'] for phase in phases for r in phase)
        for p in positions:
            key,j=slot(p)
            if key in protected:protected[key][j]=True
    kk=np.asarray(list(keys));lo=(kk[:,[0,2,1]]*16).min(0);hi=(kk[:,[0,2,1]]*16+15).max(0)
    devices=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=selected))
    for p in devices:
        k,j=slot(p)
        if k in protected:protected[k][j]=True
    baseline={k:a.copy() for k,a in oldbefore.items()}
    retired_inputs=[]
    for stem in RETIRED:
        applied=list((BASE/stem).glob('applied_*'));assert len(applied)==1
        for file in sorted((applied[0]/'delta').glob('*.npz')):
            retired_inputs.append(file)
            data=np.load(file);_,cx,cz=file.stem.split('.');cx,cz=int(cx),int(cz)
            off=data['offsets'].astype(np.int64);y=off//256+int(data['minimum']);jj=(y%16)*256+off%256
            pm=recode(data['palette']);before,after=pm[data['before']],pm[data['after']]
            for sy in np.unique(y//16):
                key=cx,cz,int(sy)
                if key not in baseline:continue
                hit=y//16==sy;ix=jj[hit];take=(baseline[key][ix]==after[hit])&~protected[key][ix]
                baseline[key][ix[take]]=before[hit][take]
    result={k:a.copy() for k,a in current.items()};counts=Counter();kept=Counter()
    oldpanel=code('projectseele:nerv_shaft_panel');panel=code('projectseele:nerv_machine_panel')
    edge=code('projectseele:nerv_machine_edge');light=code('projectseele:nerv_strip_light[lit=true]');air=code('minecraft:air')
    retained=[i for i,s in enumerate(names) if 'glass' in s or s.startswith('minecraft:ladder[') or s in ('minecraft:barrier','minecraft:structure_void','minecraft:lodestone')]
    for key in keys:
        xyz=xyz_for(key);x,y,z=xyz.T;now=current[key]
        keep=protected[key]|np.isin(now,retained)|(y<=-584)
        # Protect the original second-bank straight shaft and the first
        # bank's retained upper well/public interfaces regardless of which
        # legs a caller chose to measure.
        keep|=(x>=-54)&(x<=110)&(z>=-355)&(z<=-300)
        keep|=(x>=-54)&(x<=110)&(z>=-58)&(z<=-15)&(y>=-473)
        keep|=(x>=89)&(z>=-56)&(z<=-46)
        keep|=(y>=-470)&(x>=-54)&(x<=110)&(z<=-55)&(z>=-190)
        if key in oldbank:
            bank3=(oldbank[key]&4)!=0
            old_authored=bank3&(oldafter[key]!=baseline[key])&(now==oldafter[key])&~keep
            result[key][old_authored]=baseline[key][old_authored]
            counts['withdrawn_bank3_cells_restored_to_native_layer']+=int(old_authored.sum())
            # Same original material palette on the retained first-bank
            # lining. Its geometry, equipment and openings remain exact.
            paint=((oldbank[key]&1)!=0)&(now==oldpanel)&(oldafter[key]==oldpanel)&(oldbefore[key]!=oldafter[key])&~keep
            result[key][paint]=panel;counts['retained_bank1_material_only']+=int(paint.sum())
        if key in core:
            active=shell[key]&((newbank[key]&4)!=0)&(y>-584)&(y<=67)
            ring=active&~core[key]&~keep
            result[key][ring]=panel
            result[key][ring&(y%24==0)]=edge
            result[key][ring&(y%24==1)&(x%12==0)&(z%12==0)]=light
            result[key][active&core[key]&~keep]=air
            for v,n in zip(*np.unique(now[active&core[key]&keep],return_counts=True)):kept[names[int(v)]]+=int(n)
        result[key][keep]=now[keep]
    for p in devices:
        k,j=slot(p)
        if k in result:assert result[k][j]==current[k][j],p
    ordered=sorted(keys)
    np.savez_compressed(out/'CANDIDATE.npz',section_keys=np.asarray(ordered,np.int32),
        before=np.asarray([current[k] for k in ordered]),after=np.asarray([result[k] for k in ordered]),palette=names)
    report=dict(world_written=False,runtime_admitted=False,directory_sha256=sha(args.directory),
        hulls_sha256=meta['hulls_sha256'],model_sha256=args.model_sha,steel_sha256=args.steel_sha,
        geometry_receipt=str(args.geometry),geometry_sha256=sha(args.geometry),measurement=str(args.measurement),
        changed_cells=sum(int((current[k]!=result[k]).sum()) for k in keys),counts=dict(counts),
        preserved_devices=len(devices),protected_envelope_padding=dict(kept),
        restored_old_lying_carrier_bore=False,original_loading_plant_and_all_endpoints_preserved=True)
    inputs=[args.directory,args.hulls,args.steel,args.geometry,args.geometry_lock,model,
            args.measurement/'MEASURED_SOURCE.npz',args.measurement/'MEASURED_REPORT.json',
            OLD/'CIVIL_CANDIDATE.npz',BASE/'runtime_directory/gates/ROOT_GATES.json',
            BASE/'continuous_upright/civil_measurement/MEASURED_SOURCE.npz',Path(__file__)]
    inputs.extend(retired_inputs)
    inputs.extend(Path(p) for p in lock['source_java_sha256'])
    inputs.extend(BASE/'runtime_directory/gates'/g['collision_steps']['cells_file'] for g in gates)
    report['input_files']={str(p.resolve()):sha(p) for p in inputs}
    report['candidate_npz_sha256']=sha(out/'CANDIDATE.npz')
    (out/'CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

def apply(args):
    out=args.output.resolve();assert out.is_relative_to(BASE.resolve());assert not list((out/STAGE).glob('applied_*'))
    data=np.load(out/'CANDIDATE.npz');palette=list(map(str,data['palette']));report=json.loads((out/'CANDIDATE.json').read_text())
    assert sha(out/'CANDIDATE.npz')==report['candidate_npz_sha256'], 'Exact reviewed candidate required'
    for path,digest in report['input_files'].items():assert sha(path)==digest, ('Candidate input changed',path)
    assert sha(args.directory)==report['directory_sha256'] and sha(args.geometry)==report['geometry_sha256']
    p=vox.Painter(vertical_bounds=(-960,320));count=0
    for key,before,after in zip(data['section_keys'],data['before'],data['after']):
        cx,cz,sy=map(int,key);count+=cuboids(p,(cx*16,sy*16,cz*16),before.reshape(16,16,16),after.reshape(16,16,16),palette,'R52_verified_bank3_finite_replacement')
    assert count==report['changed_cells'];vox.WORLD=WORLD;vox.OUT=out;vox.DIM='projectseele:geofront'
    p.meta.update(root_author=True,directory_sha256=report['directory_sha256'],source_geometry_sha256=report['geometry_sha256'],runtime_admitted=False)
    lock=acquire_world_lock()
    try:report.update(receipt=p.apply(STAGE,session_lock=lock),world_written=True)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (out/STAGE/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--measurement',type=Path,required=True)
    p.add_argument('--geometry',type=Path,required=True);p.add_argument('--geometry-lock',type=Path,required=True)
    p.add_argument('--hulls',type=Path,required=True);p.add_argument('--steel',type=Path,required=True)
    p.add_argument('--model-sha',required=True);p.add_argument('--steel-sha',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--apply',action='store_true')
    a=p.parse_args();apply(a) if a.apply else plan(a)

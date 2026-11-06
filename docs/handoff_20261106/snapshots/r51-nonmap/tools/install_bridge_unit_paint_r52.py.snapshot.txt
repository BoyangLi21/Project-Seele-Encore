"""Root paint-state migration for the same original bridge geometry and phases."""
import copy,gzip,hashlib,json,msvcrt,sys
from pathlib import Path
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

def paint(state,variant):
    if not state.startswith('projectseele:entry_plug_bridge_deck['):return state
    name,properties=state[:-1].split('[',1);values=dict(v.split('=',1)for v in properties.split(','));values['unit']=str(variant)
    return name+'['+','.join(k+'='+v for k,v in sorted(values.items()))+']'

def verify_applied():
    """Resume only readback after a completed application; never replay its writes."""
    folder=BASE/'runtime_directory/units';stage=BASE/'bridge_unit_finish/three_original_bridge_paint_states'
    applications=list(stage.glob('applied_*'));assert len(applications)==1
    old=json.loads((stage/'before_3_ROOT_UNITS.json').read_bytes())
    raw=(folder/'ROOT_UNITS.json').read_bytes();current=json.loads(raw);expected=copy.deepcopy(old);rows=0
    for i,u in enumerate(expected['units']):
        ref=u['bridge_states'];before=(stage/('before_'+str(i)+'_'+Path(ref['cells_file']).name)).read_bytes()
        assert hashlib.sha256(before).hexdigest()==ref['sha256']
        phases=json.loads(gzip.decompress(before))
        for phase in phases:
            for cell in phase:
                new=paint(cell['state'],u['variant']);rows+=new!=cell['state'];cell['state']=new
        encoded=gzip.compress(json.dumps(phases,separators=(',',':')).encode('utf8'),mtime=0)
        assert (folder/ref['cells_file']).read_bytes()==encoded
        ref['sha256']=hashlib.sha256(encoded).hexdigest()
    assert current==expected
    operations=json.loads(gzip.decompress((stage/'ops.json.gz').read_bytes()));total=0
    for op in operations:
        box=op['box'];actual,palette=measure(tuple(box[:3]),tuple(box[3:]))
        assert all(palette[int(i)]==op['state'] for i in np.unique(actual)),box
        total+=actual.size
    report=dict(world_written=True,actual_deck_cells=total,all_phase_paint_rows=rows,geometry_unchanged=True,
                root_units_sha256=hashlib.sha256(raw).hexdigest(),application=str(applications[0]),
                exact_world_and_phase_readback=True,native_colour_verification_pending=True)
    (stage/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

def main():
    folder=BASE/'runtime_directory/units';manifest=folder/'ROOT_UNITS.json';raw=manifest.read_bytes();doc=json.loads(raw);out=BASE/'bridge_unit_finish';stage='three_original_bridge_paint_states';assert not list((out/stage).glob('applied_*'))
    vox.WORLD=BASE/'WORLD_R52';vox.OUT=out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-960,320));pending={};snapshots=[];total=0;table_cells=0
    for u in doc['units']:
        variant=u['variant'];ref=u['bridge_states'];path=folder/ref['cells_file'];old=path.read_bytes();assert hashlib.sha256(old).hexdigest()==ref['sha256'];states=json.loads(gzip.decompress(old))
        points=set()
        for phase in states:
            for row in phase:
                new=paint(row['state'],variant)
                if new!=row['state']:points.add(tuple(row['position']));row['state']=new;table_cells+=1
        assert points
        pos=np.asarray(list(points));lo=tuple(map(int,pos.min(0)));hi=tuple(map(int,pos.max(0)));before,names=measure(lo,hi);after=before.copy()
        for x,y,z in points:
            at=y-lo[1],z-lo[2],x-lo[0];state=names[int(before[at])];new=paint(state,variant)
            if new!=state:
                if new not in names:names.append(new)
                after[at]=names.index(new)
        total+=runs(p,lo,before,after,names,'R52_original_bridge_unit_paint');snapshots.append((lo,hi,after,names))
        encoded=gzip.compress(json.dumps(states,separators=(',',':')).encode('utf8'),mtime=0);pending[path]=(old,encoded);ref['sha256']=hashlib.sha256(encoded).hexdigest()
    encoded=(json.dumps(doc,ensure_ascii=False,separators=(',',':'))).encode('utf8');pending[manifest]=(raw,encoded)
    p.meta.update(root_author=True,collision_geometry_unchanged=True,unit_colours=['#DB9A32','#8655BD','#BC3932']);plan=p.save_plan(stage);lock=acquire_world_lock()
    try:
        for i,(path,(old,new))in enumerate(pending.items()):assert path.read_bytes()==old;(plan/('before_'+str(i)+'_'+path.name)).write_bytes(old)
        receipt=p.apply(stage,session_lock=lock)
        for path,(old,new)in pending.items():atomic_replace(path,new);assert path.read_bytes()==new
        for lo,hi,expected,names in snapshots:
            actual,pal=measure(lo,hi);ids={s:i for i,s in enumerate(names)};assert np.array_equal(np.asarray([ids.get(s,-1)for s in pal])[actual],expected)
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    report=dict(world_written=True,actual_deck_cells=total,all_phase_paint_rows=table_cells,geometry_unchanged=True,root_units_sha256=hashlib.sha256(encoded).hexdigest(),application=receipt,native_colour_verification_pending=True)
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':
    if '--verify-applied' in sys.argv:verify_applied()
    else:main()

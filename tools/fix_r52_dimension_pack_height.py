"""Make the actual enabled world datapack agree with the R52 deep dimension."""
import json,hashlib,msvcrt
from pathlib import Path
from r52_spatial_plan import BASE
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

world=BASE/'WORLD_R52';out=BASE/'dimension_pack_height';out.mkdir(exist_ok=True)
assert not(out/'APPLIED.json').exists(),'Already fixed; read the existing receipt'
relative=Path('datapacks/tv_world_preview/data/projectseele/dimension_type/geofront.json');path=world/relative
before=path.read_bytes();old=json.loads(before);assert old['min_y']==-672 and old['height']==992
new=dict(old,min_y=-960,height=1280,logical_height=1280)
assert new['min_y']+new['height']==old['min_y']+old['height']==320
assert all(new[k]==v for k,v in old.items()if k not in ('min_y','height','logical_height'))
raw=(json.dumps(new,indent=2)+'\n').encode('utf8');(out/'original_geofront.json').write_bytes(before)
lock=acquire_world_lock()
try:
    assert path.read_bytes()==before;atomic_replace(path,raw);assert path.read_bytes()==raw
finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
report=dict(world_written=True,file=relative.as_posix(),before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(raw).hexdigest(),
            changed_fields={k:dict(before=old.get(k),after=new[k])for k in ('min_y','height','logical_height')},other_dimension_fields_preserved=True,
            min_y=-960,max_y_exclusive=320,native_corrected_height_pending=True)
(out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

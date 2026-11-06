"""Root original power controls and stock migrate to the founded distant ridge.

The old artificial near-city ridge is undone only through its complete owned
inverse. Original rack identities, unique stocks and power block entities move.
"""
import argparse,copy,gzip,hashlib,json,msvcrt
from pathlib import Path
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE,Frame
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from query_blocks import iter_block_entities
from move_component_actors_r52 import prepare_actor_files
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'far_yashima_service';stage='original_stock_power_and_near_ridge_retirement';assert not list((out/stage).glob('applied_*'))
    recipe=Path('D:/eva/artifacts/rebuild_r49/encounter_facilities/r50_yashima/complete_generation_source.jsonl.gz')
    low=[10**9]*3;high=[-10**9]*3;states=set();count=0
    with gzip.open(recipe,'rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line);count+=1;states.update((r['before'],r['after']))
            for i,v in enumerate(r['pos']):low[i]=min(low[i],v);high[i]=max(high[i],v)
    assert count==671427;lo=tuple(low);hi=tuple(high);old,pal=measure(lo,hi);names=list(dict.fromkeys(pal+sorted(states)));ids={s:i for i,s in enumerate(names)}
    before=np.asarray([ids[s]for s in pal],np.uint16)[old];after=before.copy();retired_tree=0
    # Copy the original complete local power component before retiring it.
    plo=(54,103,497);phi=(60,117,513);power,power_pal=measure(plo,phi);pf=Frame(0,-1362,71,-1874)
    power_tags=dict(iter_block_entities(world,'projectseele:geofront',plo,phi));assert len(power_tags)==3
    with gzip.open(recipe,'rt',encoding='utf8')as f:
        for line in f:
            r=json.loads(line);x,y,z=r['pos'];k=y-lo[1],z-lo[2],x-lo[0];current=names[int(before[k])]
            if current!=r['after']:
                assert current==r['before']=='minecraft:air'and('_log'in r['after']or'_leaves'in r['after']),(r['pos'],current,r['after'])
                retired_tree+=1
            after[k]=ids[r['before']]
    assert retired_tree==78
    actual_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert set(actual_tags)==set(power_tags)
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    n=runs(painter,lo,before,after,names,'R52_retire_owned_near_city_yashima');snapshots=[(lo,hi,after,names)]
    # A below-grade automatic magazine keeps the existing cannon stock. Its
    # original model and inventory do not become a second free weapon.
    flo=(-1315,111,-1383);fhi=(-1297,189,-1359);a,npal=measure(flo,fhi)
    mats=['minecraft:air','projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_wall_panel','minecraft:sea_lantern','minecraft:ladder[facing=east,waterlogged=false]','minecraft:iron_trapdoor[facing=east,half=bottom,open=false,powered=false,waterlogged=false]']
    fn=list(dict.fromkeys(npal+power_pal+mats));fi={s:i for i,s in enumerate(fn)};fb=np.asarray([fi[s]for s in npal],np.uint16)[a];fa=fb.copy()
    def fill(box,state):
        x,y,z,X,Y,Z=box;assert flo[0]<=x<=X<=fhi[0]and flo[1]<=y<=Y<=fhi[1]and flo[2]<=z<=Z<=fhi[2]
        fa[y-flo[1]:Y-flo[1]+1,z-flo[2]:Z-flo[2]+1,x-flo[0]:X-flo[0]+1]=fi[state]
    fill((-1314,111,-1382,-1298,161,-1364),'projectseele:nerv_structural_panel')
    fill((-1313,114,-1381,-1299,159,-1365),'minecraft:air')
    fill((-1313,113,-1381,-1299,113,-1365),'projectseele:nerv_floor_panel')
    for y in(122,138,154):fill((-1314,y,-1374,-1314,y,-1372),'minecraft:sea_lantern')
    # Real service ladder on the magazine's west side, with an operable flush
    # top hatch. Its 2m approach is clear of the original 11m rack envelope.
    fill((-1315,114,-1375,-1313,174,-1371),'projectseele:nerv_wall_panel')
    fill((-1314,114,-1374,-1313,174,-1372),'minecraft:air')
    fill((-1314,114,-1373,-1314,173,-1373),'minecraft:ladder[facing=east,waterlogged=false]')
    fill((-1314,174,-1373,-1314,174,-1373),'minecraft:iron_trapdoor[facing=east,half=bottom,open=false,powered=false,waterlogged=false]')
    # The original controls and three pylons are a single exact translation.
    dstlo,dsthi=pf.box(plo,phi);x,y,z=dstlo;X,Y,Z=dsthi
    fa[y-flo[1]:Y-flo[1]+1,z-flo[2]:Z-flo[2]+1,x-flo[0]:X-flo[0]+1]=np.asarray([fi[s]for s in power_pal],np.uint16)[power]
    assert not list(iter_block_entities(world,'projectseele:geofront',flo,fhi))
    touched={fn[int(v)]for v in np.unique(fb[fb!=fa])};assert touched<=set(('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]')),touched
    n+=runs(painter,flo,fb,fa,fn,'R52_far_power_and_original_magazine');snapshots.append((flo,fhi,fa,fn))
    for pos,tag in power_tags.items():
        newpos=pf.block(pos);tag=copy.deepcopy(tag)
        for k,v in zip(('x','y','z'),newpos):tag[k]=nbtlib.Int(v)
        painter.block_entities[newpos]=tag
    # Shield well foundation only; the original 54m moving well is an actor.
    slo=(-1206,171,-1457);shi=(-1171,175,-1422);a,sp=measure(slo,shi);sn=list(dict.fromkeys(sp+['projectseele:nerv_structural_panel','projectseele:nerv_floor_panel']));si={s:i for i,s in enumerate(sn)};sb=np.asarray([si[s]for s in sp],np.uint16)[a];sa=sb.copy()
    sa[:3,:,:]=si['projectseele:nerv_structural_panel'];sa[3,:,:]=si['projectseele:nerv_floor_panel']
    assert not list(iter_block_entities(world,'projectseele:geofront',slo,shi));assert{sn[int(v)]for v in np.unique(sb[sb!=sa])}<=set(('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]'))
    n+=runs(painter,slo,sb,sa,sn,'R52_far_original_shield_well_foundation');snapshots.append((slo,shi,sa,sn))
    actors=json.loads((BASE/'survey/ORIGINAL_ALL_ACTORS.json').read_text('utf8'))['actors'];wanted={'e9fd32e9-b3a3-5dc6-8d9f-21ce267a848e':Frame(0,-1301,65,-1942),'749cf141-0e2f-59ef-9e9b-d08346d5ea8d':Frame(0,-1418,4,-1826)}
    expected={r['uuid']:r['snbt']for r in actors if r['uuid']in wanted};assert len(expected)==2
    painter.meta.update(root_author=True,near_component_inverse_sha256=hashlib.sha256(recipe.read_bytes()).hexdigest(),original_power_frame=pf.__dict__)
    plan=painter.save_plan(stage);report=dict(world_written=False,changed_cells=n,old_owned_rows=count,already_retired_tree_cells=78,power_frame=pf.__dict__,new_rack_positions={'0':[-1188.5,175,-1439.5],'1':[-1305.5,114,-1373.5]},native_acceptance=False)
    if args.apply:
        lock=acquire_world_lock();written=[];backups={}
        try:
            actor_files,actor_receipt=prepare_actor_files(world,wanted,expected)
            report['application']=painter.apply(stage,session_lock=lock)
            for i,(path,data)in enumerate(actor_files.items()):
                backups[path]=path.read_bytes()if path.exists()else None
                if backups[path]is not None:(plan/f'actor_before_{i}.mca').write_bytes(backups[path])
                path.parent.mkdir(parents=True,exist_ok=True);atomic_replace(path,data);written.append(path)
            for path,data in actor_files.items():assert path.read_bytes()==data
            for lo2,hi2,b,nm in snapshots:
                a,p=measure(lo2,hi2);m={s:i for i,s in enumerate(nm)};assert np.array_equal(np.asarray([m[s]for s in p])[a],b)
            assert not list(iter_block_entities(world,'projectseele:geofront',lo,hi))
            new_tags=dict(iter_block_entities(world,'projectseele:geofront',flo,fhi));assert set(new_tags)==set(painter.block_entities)
            for q,tag in new_tags.items():assert tag.snbt()==painter.block_entities[q].snbt()
            report.update(world_written=True,whole_exact_readback=True,actors=actor_receipt,metadata_pending=True)
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (plan/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()

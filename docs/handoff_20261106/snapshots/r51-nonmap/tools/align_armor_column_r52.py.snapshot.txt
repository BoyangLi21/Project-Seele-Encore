"""Move the owned upper armour component seven metres onto Lilith's real axis."""
import argparse,copy,gzip,hashlib,json,msvcrt
from pathlib import Path
import nbtlib
import numpy as np
import regional_voxels as vox
from r52_spatial_plan import BASE
from survey_r52_original_complex import measure
from prepare_terminal_move_r52 import runs
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace
from query_blocks import iter_block_entities

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
    world=BASE/'WORLD_R52';out=BASE/'armor_column_alignment';stage='complete_owned_column_z_minus7'
    assert not list((out/stage).glob('applied_*'))
    source=Path('D:/eva/artifacts/rebuild_r49/encounter_facilities/r50_armor/complete_generation_source.jsonl.gz')
    with gzip.open(source,'rt',encoding='utf8')as f:rows=[json.loads(line)for line in f]
    assert len(rows)==7112 and not any(r['before_nbt']or r['after_nbt']for r in rows)
    lo=(26,20,344);hi=(40,84,360);before,names=measure(lo,hi)
    for r in rows:
        for field in('before','after'):
            if r[field]not in names:names.append(r[field])
    ids={s:i for i,s in enumerate(names)};after=before.copy()
    def at(q):x,y,z=q;return y-lo[1],z-lo[2],x-lo[0]
    for r in rows:
        assert names[int(before[at(r['pos'])])]==r['after'],(r['pos'],'source changed')
        after[at(r['pos'])]=ids[r['before']]
    destinations=[]
    for r in rows:
        q=[r['pos'][0],r['pos'][1],r['pos'][2]-7]
        existing=names[int(after[at(q)])]
        assert existing in('minecraft:air','minecraft:stone','minecraft:dirt','minecraft:grass_block[snowy=false]',
            'minecraft:deepslate','minecraft:deepslate[axis=y]','minecraft:polished_deepslate','minecraft:smooth_stone',
            'minecraft:iron_block','minecraft:deepslate_tiles','minecraft:black_concrete','minecraft:orange_concrete',
            'minecraft:smooth_quartz','minecraft:light_gray_concrete','minecraft:red_terracotta','minecraft:sea_lantern',
            'minecraft:barrel[facing=north,open=false]')or existing.startswith('projectseele:nerv_'),(q,existing)
        destinations.append((q,r['after']))
    for q,state in destinations:after[at(q)]=ids[state]
    tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert set(tags)=={(37,81,345)}
    # The shifted inspection enclosure touches one existing service barrel.
    # Keep that actual inventory and block state, moving it one metre north
    # on the same unchanged counter floor, outside the complete shaft wall.
    old_barrel=(37,81,345);new_barrel=(37,81,344)
    assert names[int(after[at(new_barrel)])]=='minecraft:air'
    assert names[int(after[at((37,80,344))])]=='minecraft:smooth_stone'
    after[at(new_barrel)]=ids['minecraft:barrel[facing=north,open=false]']
    barrel=copy.deepcopy(tags[old_barrel]);barrel['z']=nbtlib.Int(344)
    path=world/'nerv_armor_column_r50.json';original=path.read_bytes();meta=json.loads(original)
    assert meta['surface']==[30.5,80,355.5]
    def move(p):return[p[0],p[1],p[2]-7]
    for key in('surface','repair_control'):meta[key]=move(meta[key])
    meta['hole_bounds']=[move(p)for p in meta['hole_bounds']]
    for row in meta['layers']:
        row['sensor']=move(row['sensor']);row['plate_bounds']=[move(p)for p in row['plate_bounds']]
        if 'inspection_shelf'in row:row['inspection_shelf']=[move(p)for p in row['inspection_shelf']]
    meta['terminal_pos']=[30.5,-880,348.5];meta['r52_root_translation']=[0,0,-7]
    encoded=(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode('utf8')
    vox.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-960,320))
    n=runs(painter,lo,before,after,names,'R52_owned_armour_column_axis_correction');painter.meta.update(root_author=True,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    painter.block_entities[new_barrel]=barrel
    folder=painter.save_plan(stage);report=dict(world_written=False,changed_cells=n,source_rows=7112,terminal_actual=[30.5,-880,348.5],surface_actual=meta['surface'],physical_layers=8,native_acceptance=False)
    if args.apply:
        lock=acquire_world_lock()
        try:
            assert path.read_bytes()==original;(folder/'before_metadata.json').write_bytes(original)
            receipt=painter.apply(stage,session_lock=lock)
            a,pal=measure(lo,hi);assert np.array_equal(np.asarray([ids[s]for s in pal])[a],after)
            actual_tags=dict(iter_block_entities(world,'projectseele:geofront',lo,hi));assert set(actual_tags)=={new_barrel}and actual_tags[new_barrel].snbt()==barrel.snbt()
            atomic_replace(path,encoded);assert path.read_bytes()==encoded
            report.update(world_written=True,whole_component_exact_readback=True,application=receipt)
        finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()
    (folder/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)

if __name__=='__main__':main()

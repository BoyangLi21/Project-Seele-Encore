"""Freeze all 93 actual cargo archives and prepare default-off native probe jobs.

Does not write a world, install a mod, configure Create or launch/build Minecraft.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import nbtlib
from measure_city_placements_r45 import unpack_pos
from measure_central_tower_ports_r44 import specs

ROOT=Path(__file__).resolve().parents[1]


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_size(tag):
    stream=io.BytesIO();nbtlib.File(tag).write(stream);return len(stream.getvalue())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--world',type=Path,default=ROOT/'run/saves/SEELE_FIELD_R45_REVIEW')
    parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/create_probe_v1')
    parser.add_argument('--anchor',nargs=3,type=int,default=(2048,160,2048))
    parser.add_argument('--delta-y',type=int,default=-60)
    parser.add_argument('--ticks',type=int,default=240)
    parser.add_argument('--profile',choices=('constant','c1_trapezoid'),default='c1_trapezoid')
    args=parser.parse_args()
    world=args.world.resolve();out=args.out.resolve()
    assert world.name=='SEELE_FIELD_R45_REVIEW' and world.is_dir()
    assert not out.exists(), 'Preserve earlier probe inputs/results; choose a new output directory'
    data_dir=world/'dimensions/projectseele/geofront/data'
    identity=str(nbtlib.load(data_dir/'projectseele_tokyo3_building_world_id_r44.dat')['data']['WorldUUID'])
    seed=int(nbtlib.load(world/'level.dat')['Data']['WorldGenSettings']['seed'])
    archives={}
    for path in data_dir.glob('projectseele_tokyo3_building_archive_r44_*.dat'):
        data=nbtlib.load(path)['data'];assert str(data['WorldUUID'])==identity and int(data['Version'])==1
        assert len(data['Buildings'])==1
        building=data['Buildings'][0]
        assert 'FixedStreetCore' in building and 'Transaction' not in building
        archives[unpack_pos(int(building['Centre']))]=(path,building)
    assert len(archives)==93
    frozen=out/'cargo';frozen.mkdir(parents=True)
    rows=[]
    total_nbt=0
    for index,(x,z,_,_) in enumerate(specs()):
        source,building=archives[(x,80,z)];dest=frozen/source.name
        shutil.copyfile(source,dest);assert sha(source)==sha(dest)
        palette=[];palette_ids={};blocklist=[];nbt_count=0
        support=None
        for cell in building['Cargo']:
            state=cell['State'];canonical=state.snbt()
            if canonical not in palette_ids:palette_ids[canonical]=len(palette);palette.append(state)
            pos=unpack_pos(int(cell['Pos']))
            assert abs(pos[0])<=int(building['Half']) and abs(pos[2])<=int(building['Half']) and 0<=pos[1]<=int(building['Height'])+3
            assert not (bool(building['FixedStreetCore']) and pos==(0,0,0))
            value=nbtlib.Compound({'Pos':cell['Pos'],'State':nbtlib.Int(palette_ids[canonical])})
            if 'NBT' in cell:
                value['Data']=cell['NBT'];value['UpdateTag']=cell['NBT'];nbt_count+=1
            blocklist.append(value)
            if support is None and pos[1]==0 and abs(pos[0])<int(building['Half'])-2 and abs(pos[2])<int(building['Half'])-2 and str(state['Name']) in {
                'minecraft:smooth_stone','minecraft:stone_bricks','minecraft:polished_deepslate','minecraft:iron_block','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:sea_lantern'}:
                support=pos
        half=int(building['Half']);height=int(building['Height'])
        payload=nbtlib.Compound({'Type':nbtlib.String('create:pulley'),'InitialOffset':nbtlib.Int(0),
            'Anchor':nbtlib.Compound({key:nbtlib.Int(value) for key,value in zip(('X','Y','Z'),args.anchor)}),
            'Blocks':nbtlib.Compound({'Palette':nbtlib.List[nbtlib.Compound](palette),'BlockList':nbtlib.List[nbtlib.Compound](blocklist)}),
            'BoundsFront':nbtlib.List[nbtlib.Float]([-half,0,-half,half+1,height+4,half+1])})
        # Full server data and client UpdateTag deliberately match. Estimate
        # the spawn form: Create uses UpdateTag as Data and removes UpdateTag.
        spawn_blocks=[]
        for entry in blocklist:
            spawn_blocks.append(nbtlib.Compound({key:value for key,value in entry.items() if key!='UpdateTag'}))
        spawn=nbtlib.Compound(dict(payload));spawn['Blocks']=nbtlib.Compound({'Palette':payload['Blocks']['Palette'],'BlockList':nbtlib.List[nbtlib.Compound](spawn_blocks)})
        spawn_bytes=raw_size(nbtlib.Compound({'Contraption':spawn}))+512
        # Palette round-trip maps all exact full-NBT cargo cells unchanged.
        for old,new in zip(building['Cargo'],blocklist):
            assert old['State']==palette[int(new['State'])]
            assert ('NBT'in old)==('Data'in new)
            if 'NBT'in old: assert old['NBT']==new['Data']==new['UpdateTag']
        rows.append(dict(index=index,path=str(dest),sha256=sha(dest),source_path=str(source),source_sha256=sha(source),
            center=[x,80,z],height=height,half=half,cells=len(blocklist),full_block_entities=nbt_count,
            estimated_spawn_bytes=spawn_bytes,below_stock_spawn_limit=spawn_bytes<=1048576-20000,
            source_fixed_core=bool(building['FixedStreetCore']),fixed_dome_mask=list(map(int,building['NegativeDomeAnchorMask'])),
            support_local=support))
        total_nbt+=nbt_count
    assert total_nbt==1471
    selections={'first':0,'largest':max(range(93),key=lambda i:rows[i]['cells']),
        'largest_packet':max(range(93),key=lambda i:rows[i]['estimated_spawn_bytes']),
        'noncore':next(i for i,r in enumerate(rows) if not r['source_fixed_core'])}
    jobs=[]
    for label,index in selections.items():
        for mode in ('roundtrip','interrupt','resume'):
            shared=out/(label+('_roundtrip_native' if mode=='roundtrip' else '_reload_native'))
            job=dict(schema='projectseele.create-rigid-lift-input-r45.v1',enable_native_probe=True,
                world=str(world),world_seed=seed,world_id=identity,dimension='projectseele:geofront',
                mode=mode,tower_index=index,archives=rows,anchor=args.anchor,delta_y=args.delta_y,
                duration_ticks=args.ticks,settle_ticks=40,hold_ticks=40,timeout_ticks=12000,
                motion_profile=args.profile,ramp_ticks=min(16,args.ticks//4),
                allowed_probe_actor_uuids=[],spawn_collision_probe=rows[index]['support_local'] is not None,
                support_local=rows[index]['support_local'] or [0,0,0],output=str(shared),
                candidate_default_enabled=False,production_endpoint_transaction_ready=False)
            path=out/f'{label}_{mode}.json';path.write_text(json.dumps(job,indent=2),'utf8');jobs.append(dict(path=str(path),sha256=sha(path)))
    summary=dict(schema='projectseele.create-probe-preflight-r45.v1',world=str(world),world_id=identity,
        source_world_written=False,all_cargo_preserved=True,cargo_cells=sum(r['cells'] for r in rows),
        full_block_entities=total_nbt,fixed_core_count=sum(r['source_fixed_core'] for r in rows),
        create_default_max_blocks_moved=2048,required_reviewed_max_blocks_moved=max(r['cells'] for r in rows),
        stock_spawn_byte_limit=1048576-20000,max_estimated_spawn_bytes=max(r['estimated_spawn_bytes'] for r in rows),
        all_estimates_below_stock_limit=all(r['below_stock_spawn_limit'] for r in rows),
        native_minecraft_test=False,source_world_gated='SEELE_FIELD_R45_REVIEW',selections=selections,jobs=jobs,records=rows)
    (out/'preflight.json').write_text(json.dumps(summary,indent=2),'utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('records','jobs')},indent=2))


if __name__=='__main__':main()

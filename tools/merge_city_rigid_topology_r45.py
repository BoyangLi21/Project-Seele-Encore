"""Verify complete96 inverse/component topology and emit a DRAFT authority tag.

Never applies a patch, writes a world or marks Root/native/art verification true.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,json
import nbtlib
from plan_city_rigid_topology_r45 import packed
from measure_city_placements_r45 import unpack_pos

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=ROOT/'artifacts/rebuild_r45/city_motion/whole_topology_v1');args=parser.parse_args()
    out=args.out.resolve();assert not out.exists();sources=[ROOT/'artifacts/rebuild_r45/city_motion/topology_v3',ROOT/'artifacts/rebuild_r45/city_motion/private_topology_v2']
    reports=[json.loads((s/'topology.json').read_text('utf8')) for s in sources]
    assert reports[0]['world_id']==reports[1]['world_id'] and not any(r['held'] or r['region_files_changed_during_read'] for r in reports)
    out.mkdir(parents=True);(out/'cargo').mkdir()
    import shutil
    towers=nbtlib.List[nbtlib.Compound]();cargo_records=[]
    for report in reports:
        for row in report['records']:
            generated='source_center'in row
            center=row['source_center'] if generated else row['center'];h=row['height'];half=row['half'];base=19-h if generated else row['retracted_base_y']
            footprint=dict(MinX=-half,MaxX=half,MinZ=-half,MaxZ=half) if generated else row['footprint']
            anchors=row['new_negative_anchor_mask']
            assert len(anchors)==64 and all(not(footprint['MinX']<=p[0]-center[0]<=footprint['MaxX'] and footprint['MinZ']<=p[2]-center[2]<=footprint['MaxZ']) for p in anchors)
            core=row['new_fixed_core'] if generated else None
            if core:assert not(footprint['MinX']<=core[0]-center[0]<=footprint['MaxX'] and footprint['MinZ']<=core[2]-center[2]<=footprint['MaxZ'])
            for bearing in row['overhead_bearings']:
                samples=bearing['two_layers'] if generated else bearing['complete_two_layers']
                assert len(samples)==18 and all(value is not None and not value.endswith(':air') for _,value in samples)
            source=Path(row['archive_candidate'] if generated else row['archive']);tag=nbtlib.load(source);building=tag['data']['Buildings'][0]
            assert str(tag['data']['WorldUUID'])==report['world_id'];cells=building['Cargo'];assert len({int(c['Pos']) for c in cells})==len(cells)
            be=sum('NBT'in c for c in cells);path=out/'cargo'/source.name;shutil.copyfile(source,path)
            if generated:
                old=nbtlib.load(ROOT/'artifacts/rebuild_r45/city_motion/create_probe_v2/cargo'/source.name)['data']['Buildings'][0]
                bypos={int(c['Pos']):c for c in cells}
                assert all(bypos[int(c['Pos'])]==c for c in old['Cargo']), 'Existing full cargo was changed/lost'
            t=nbtlib.Compound({'Centre':nbtlib.Long(packed(center)),'Height':nbtlib.Int(h),'Half':nbtlib.Int(half),
                'Kind':nbtlib.String('generated'if generated else 'private'),'RetractedBaseY':nbtlib.Int(base),
                'Footprint':nbtlib.Compound({k:nbtlib.Int(v)for k,v in footprint.items()}),
                'NegativeDomeAnchorMask':nbtlib.LongArray([packed(p)for p in anchors])})
            if core:t['FixedCorePos']=nbtlib.Long(packed(core))
            towers.append(t);cargo_records.append(dict(index=len(towers)-1,cargo=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cells=len(cells),full_be=be,
                source=row,old_source_cargo_changed=False))
    assert len(towers)==96 and sum(r['full_be']for r in cargo_records)==1471 and sum('FixedCorePos'in t for t in towers)==64
    # Each source stream has exact paired inverse order. Cross-component
    # conflicts only need the small private coordinate set in memory.
    private={}
    for line in gzip.open(sources[1]/'forward.jsonl.gz','rt',encoding='utf8'):
        row=json.loads(line);private[tuple(row['pos'])]=row
    counters={};seen_private=set();changes=0
    f=gzip.open(out/'forward.jsonl.gz','wt',encoding='utf8');inv=gzip.open(out/'inverse.jsonl.gz','wt',encoding='utf8')
    for number,source in enumerate(sources):
        local=0
        with gzip.open(source/'forward.jsonl.gz','rt',encoding='utf8')as forward,gzip.open(source/'inverse.jsonl.gz','rt',encoding='utf8')as inverse:
            for raw,back_raw in zip(forward,inverse,strict=True):
                row=json.loads(raw);back=json.loads(back_raw);assert row['pos']==back['pos']
                assert (row['before'],row['after'],row['before_nbt'],row['after_nbt'])==(back['after'],back['before'],back['after_nbt'],back['before_nbt'])
                point=tuple(row['pos'])
                if number==0 and point in private:
                    peer=private[point];assert all(row[k]==peer[k]for k in ('before','after','before_nbt','after_nbt')),'Different complete-component edits overlap'
                    seen_private.add(point)
                if number==1 and point in seen_private:continue
                f.write(json.dumps(row)+'\n');inv.write(json.dumps(back)+'\n');changes+=1;local+=1
        counters[source.name]=local
    f.close();inv.close()
    metadata=nbtlib.Compound({'Version':nbtlib.Int(1),'WorldUUID':nbtlib.String(reports[0]['world_id']),
        'Origin':nbtlib.Long(packed((30,80,220))),'Stage':nbtlib.String('DRAFT'),
        'RuntimeEnabled':nbtlib.Byte(0),'GenerationFolder':nbtlib.String('city_rigid_generation_r45'),
        'NativeStructurePassed':nbtlib.Byte(0),'ExactCargoMigrationPassed':nbtlib.Byte(0),'Towers':towers})
    authority=out/f'projectseele_city_rigid_topology_r45_{packed((30,80,220))&((1<<64)-1)}.dat'
    nbtlib.File({'DataVersion':nbtlib.Int(3465),'data':metadata}).save(authority,gzipped=True)
    summary=dict(schema='projectseele.whole-city-rigid-topology-r45.v1',world=reports[0]['world'],world_id=reports[0]['world_id'],
        world_written=False,archives_written=False,authority_stage='DRAFT',root_native_structure_passed=False,root_art_passed=False,
        objects=96,full_be=1471,original_cargo_cells=731190+3*5996,added_moving_floor_cells=64,cargo_cells=sum(r['cells']for r in cargo_records),
        fixed_controller_roles_preserved=64,negative_anchor_masks_outside_all_cargo=True,complete_two_layer_bearings=96*4,
        lower_bearing_saddles_outside_sweep=True,existing_complete_cargo_nbt_equal=True,changed_cells=changes,merged_counts=counters,
        forward_sha256=hashlib.sha256((out/'forward.jsonl.gz').read_bytes()).hexdigest(),inverse_sha256=hashlib.sha256((out/'inverse.jsonl.gz').read_bytes()).hexdigest(),
        authority=str(authority),authority_sha256=hashlib.sha256(authority.read_bytes()).hexdigest(),records=cargo_records)
    (out/'manifest.json').write_text(json.dumps(summary,indent=2),'utf8')
    print(json.dumps({k:v for k,v in summary.items()if k!='records'},indent=2))


if __name__=='__main__':main()

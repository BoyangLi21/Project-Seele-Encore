"""Retire measured predecessor seal planes after their original hatches moved up.

Produces an exact reversible block candidate. No world writes and no actor,
active gate table, support, route, task or navigation edits.
"""
import argparse
import gzip
import json
import shutil
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text('utf8'))


def prepare(world, predecessor, successor, measured, output, compact_plan=None):
    owner=read(world/'ROOT_MECHANICAL_OWNER.json')
    before={tuple(c['position']):c['state'] for c in measured['cells']}
    assert not measured['block_entities']
    owned=set();supports=set()
    for gate in owner['gates']:
        rows=gate['collision_steps']
        if isinstance(rows,dict):rows=json.loads(gzip.decompress((world/rows['cells_file']).read_bytes()))
        owned.update(tuple(c['position'])for step in rows for c in step)
        supports.update(tuple(c['position'])for c in gate.get('supports',[]))
    old={g['resource']:g for g in read(predecessor)['gates']}
    new={g['resource']:g for g in read(successor)['gates']}
    current={g['resource']:g for g in owner['gates']}
    compact=read(compact_plan) if compact_plan else None
    if compact:
        assert compact['world_written'] and compact['full_component_exact_readback']
        assert compact['source']=='frozen original bank geometry'
        assert compact['bank_centres_z']==[124.5,76.5,28.5] and compact['centre_spacing']==48
    banks=range(1,4) if compact else [1]
    forward=[];scope=[];already_clear=0;targets=set()
    for bank,lane in [(bank,lane)for bank in banks for lane in range(3)]:
        name=f'bank_{bank}_upper_lane_{lane}'
        a,b,c=old[name],new[name],current[name]
        assert a['variant']==b['variant']==c['variant']
        box=a['closed_box'];replacement=b['closed_box']
        assert box[1]==box[4]==-568 and replacement[1]==replacement[4]==-565
        assert [box[k]for k in (0,2,3,5)]==[replacement[k]for k in (0,2,3,5)]
        assert box[3]-box[0]==box[5]-box[2]==30
        z=compact['bank_centres_z'][bank-1] if compact else b['frame']['position'][2]
        assert c['frame']['position']==[b['frame']['position'][0],b['frame']['position'][1]-384,z]
        dz=z-b['frame']['position'][2];assert dz==int(dz)
        target=[box[0],box[1]-384,box[2]+int(dz),box[3],box[4]-384,box[5]+int(dz)]
        for x in range(target[0],target[3]+1):
            for z in range(target[2],target[5]+1):
                p=(x,target[1],z)
                assert p not in targets;targets.add(p)
                assert before[p] in ('minecraft:barrier','minecraft:air') and p not in owned and p not in supports
                if before[p]=='minecraft:air':already_clear+=1;continue
                forward.append(dict(pos=list(p),before='minecraft:barrier',after='minecraft:air',
                                    before_nbt=None,after_nbt=None,purpose='retired_predecessor_upper_hatch_proxy'))
        scope.append(dict(gate=name,retired_box=target,current_proxy_y=-949))
    assert len(targets)==961*3*len(banks) and len(forward)+already_clear==len(targets)
    assert len({tuple(r['pos'])for r in forward})==len(forward)
    output.mkdir(parents=True,exist_ok=True)
    inverse=[dict(r,before=r['after'],after=r['before'])for r in forward]
    for name,value in [('forwardPatch.json',forward),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in forward])]:
        (output/name).write_text(json.dumps(value,separators=(',',':'))+'\n','utf8')
    construction=dict(world=str(world),dimension='projectseele:geofront',installed=False,changed_static_cells=len(forward),already_clear_cells=already_clear,
        predecessor_plan=str(predecessor),successor_plan=str(successor),scope=scope,
        compact_plan=str(compact_plan) if compact_plan else None,
        reason='The original hatch was raised three metres before the accepted rigid deep migration. Its previous 31x31 proxy survived beneath the current source-owned proxy.',
        actual_preconditions='Every target is exactly minecraft:barrier, has no block entity and is absent from every current gate phase table and support set.',
        measured_full_core_boxes=measured['boxes'],other_core_materials='Only current source-owned seal planes remain; retain their normal open/close state.',
        changed_metadata=[],changed_navigation=[],changed_runtime_resources=[],changed_entity_or_task_fields=[],
        acceptance='Root applies with the normal locked-world patch tool, reads back all changed cells, then resumes the original DEPARTING task and its production full-assembly preflight.')
    (output/'construction.json').write_text(json.dumps(construction,indent=2)+'\n','utf8')
    (output/'inverse').mkdir(exist_ok=True)
    metadata=['ROOT_MECHANICAL_OWNER.json','ROOT_ASSEMBLY_BUNDLE.json']
    for name in metadata:shutil.copy2(world/name,output/'inverse'/name)
    manifest=dict(world=str(world),static_cells=len(forward),metadata_preconditions=metadata,world_tables=[])
    (output/'installation_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n','utf8')
    print(f'Prepared {len(forward)} exact retired proxy cells; {already_clear} already-clear cells retained; active seals and all original progress unchanged.')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('world','predecessor','successor','measured','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--compact-plan',type=Path)
    a=p.parse_args();prepare(a.world,a.predecessor,a.successor,read(a.measured),a.output,a.compact_plan)

"""Prepare complete current city components at the cross-layout coordinates.

Reads the stopped playable world through query_blocks; never installs it.
The original ledger and historical journals stay intact. Current inventory
snapshots are tied to their committed journey until the next completed trip.
Retired lots and new maintenance approaches must join the streetscape batch
before this candidate is installed.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import shutil
import nbtlib
import numpy as np
from query_blocks import AIR, chunk_statuses, iter_selected_sections, iter_block_entities, dimension_dir
from install_r53_carrier_trays import stopped_world
from plan_hakone_relocations import unpack
from inspect_map_assets import palette_state
from apply_s20_approved_semantic_repairs import parse_state
from transplant_s22_authority import read_region, parse_chunk

DIM = 'projectseele:geofront'
DATA = Path('dimensions/projectseele/geofront/data')
MIN_Y, MAX_Y = -128, 320


def packed(pos):
    x,y,z=map(int,pos)
    value=((x&0x3ffffff)<<38)|((z&0x3ffffff)<<12)|(y&0xfff)
    return value-(1<<64) if value>=1<<63 else value


def translated(value, delta):
    return nbtlib.Long(packed([a+b for a,b in zip(unpack(value),delta)]))


def contains(box,p):
    return all(box[i]<=p[i]<box[i+3]+1 for i in range(3))


def move_nbt(tag,delta):
    result=copy.deepcopy(tag)
    if all(k in result for k in ('x','y','z')):
        for key,d in zip(('x','y','z'),delta):result[key]=nbtlib.Int(int(result[key])+d)
    return result


def metadata(out,relative,before,after):
    for stage,tag in [('before',before),('after',after)]:
        file=out/stage/relative;file.parent.mkdir(parents=True,exist_ok=True)
        tag.save(file,gzipped=True)


def prepare(world,planfile,out):
    if out.exists():raise ValueError('Choose a new candidate directory')
    plan=json.loads(planfile.read_text(encoding='utf-8'))
    data=world/DATA
    topology_file=next(data.glob('projectseele_city_rigid_topology_r45_*.dat'))
    control_file=next(data.glob('projectseele_city_rigid_control_r45_*.dat'))
    topology=nbtlib.load(topology_file);control=nbtlib.load(control_file)
    top=topology['data'];ledger=control['data']
    if str(ledger['Phase'])!='IDLE' or int(ledger['Depth'])!=int(ledger['Target']):
        raise ValueError('A moving city must finish its actual journey before cold relocation')
    if int(ledger['Depth']) not in (0,312):raise ValueError('Unknown endpoint')
    depth=int(ledger['Depth']);journey=copy.deepcopy(ledger['Journey'])
    towers=top['Towers'];moves=[];selected={}
    for row in plan['towers']:
        if not any(row['delta']):continue
        index=row['index'];tower=towers[index];centre=unpack(tower['Centre'])
        if centre!=row['source_centre']:raise ValueError(f'Changed city position: {index}')
        if row['delta'][1] or str(tower['Kind'])!='generated':raise ValueError('This batch only translates generated towers horizontally')
        half=int(tower['Half']);height=int(tower['Height']);base=int(tower['RetractedBaseY'])
        # Includes four-bearing rings, full shaft, controller and five-long
        # lower doorway apron; the old placement plan used a narrower margin.
        box=[centre[0]-half-4,base-1,centre[2]-half-4,
             centre[0]+half+4,centre[1]+height+3,centre[2]+half+5]
        target=[v+row['delta'][i%3]for i,v in enumerate(box)]
        move=dict(row,box=box,target_box=target,half=half,base=base)
        moves.append(move)
        for b in (box,target):
            for cx in range(b[0]//16,b[3]//16+1):
                for cz in range(b[2]//16,b[5]//16+1):selected[cx,cz]=set(range(MIN_Y//16,MAX_Y//16))
    statuses=chunk_statuses(world,DIM,selected)
    unfinished=[p for p,v in statuses.items()if v!='full']
    if unfinished:raise ValueError(f'Unknown source/destination chunks: {unfinished[:12]}')
    out.mkdir(parents=True);(out/'measured').mkdir();(out/'delta').mkdir()
    palette=['minecraft:air'];ids={palette[0]:0};blocks={p:np.zeros((MAX_Y-MIN_Y,16,16),np.uint16)for p in selected}
    for cx,cz,sy,pal,cells in iter_selected_sections(world,DIM,selected):
        for state in pal:
            if state not in ids:ids[state]=len(palette);palette.append(state)
        code=np.asarray([ids[s]for s in pal],np.uint16)
        blocks[cx,cz][sy*16-MIN_Y:sy*16-MIN_Y+16]=code[cells].reshape(16,16,16)
    lo=tuple(min(b[i] for m in moves for b in (m['box'],m['target_box']))for i in range(3))
    hi=tuple(max(b[i+3] for m in moves for b in (m['box'],m['target_box']))for i in range(3))
    block_entities=dict(iter_block_entities(world,DIM,lo,hi,selected_chunks=set(selected)))
    def code_at(p):
        x,y,z=p;return int(blocks[x//16,z//16][y-MIN_Y,z%16,x%16])
    def state_at(p):return palette[code_at(p)]
    source_chunks=defaultdict(list)
    for m in moves:
        b=m['box']
        for cx in range(b[0]//16,b[3]//16+1):
            for cz in range(b[2]//16,b[5]//16+1):source_chunks[cx,cz].append(m)
    def member(p):
        return next((m for m in source_chunks[int(np.floor(p[0]/16)),int(np.floor(p[2]/16))]if contains(m['box'],p)),None)
    recipes=data/'city_rigid_generation_r45/chunks'
    affected=set(selected);loaded={};owned=defaultdict(dict);ground=defaultdict(dict)
    for cx,cz in sorted(affected):
        file=recipes/f'{cx}_{cz}.dat'
        if not file.exists():continue
        tag=nbtlib.load(file);loaded[cx,cz]=tag
        for cell in tag['Static']:
            p=tuple(unpack(cell['Pos']));m=member(p)
            if m:owned[m['index']][p]=copy.deepcopy(cell)
        for cell in tag['Ground']:
            index=int(cell['Object'])
            if any(m['index']==index for m in moves):ground[index][tuple(unpack(cell['Pos']))]=copy.deepcopy(cell)
    print(f'Measured {len(selected)} FULL chunks for {len(moves)} components',flush=True)
    measured_groups=defaultdict(list)
    for p in sorted(selected):measured_groups[p[0]//32,p[1]//32].append(p)
    for (rx,rz),coords in measured_groups.items():
        np.savez_compressed(out/'measured'/f'r.{rx}.{rz}.npz',coordinates=np.asarray(coords),
                            blocks=np.stack([blocks[p]for p in coords]),palette=np.asarray(palette))
    desired={};be_after=dict(block_entities);target_owner={};foreign=[];component_reports=[]
    relocated_topology=copy.deepcopy(topology)
    # Remove all source components before inserting any targets. Layout moves
    # can overlap another source, so serial cut/paste would lose its contents.
    for m in moves:
        points=set(owned[m['index']])|set(ground[m['index']])
        if not points:raise ValueError(f'Missing declared component {m["index"]}')
        for p in points:
            desired[p]=code_at(p) if p in ground[m['index']] else 0
            if p not in ground[m['index']]:be_after.pop(p,None)
    staged_recipes={}
    def shard(chunk):
        if chunk not in staged_recipes:
            staged_recipes[chunk]=copy.deepcopy(loaded.get(chunk,nbtlib.File({
                'Version':nbtlib.Int(1),'WorldUUID':copy.deepcopy(top['WorldUUID']),
                'InitialDepth':nbtlib.Int(depth),'Palette':nbtlib.List[nbtlib.Compound](),
                'Static':nbtlib.List[nbtlib.Compound](),'Ground':nbtlib.List[nbtlib.Compound]()})))
        return staged_recipes[chunk]
    # Each modified chunk is rebuilt once from its unmodified unrelated rows.
    static_rows=defaultdict(dict);ground_rows=defaultdict(dict)
    for chunk,tag in loaded.items():
        for cell in tag['Static']:
            p=tuple(unpack(cell['Pos']));m=member(p)
            if not m:continue
            # Retired shaft no longer generates cargo, controllers or anchors.
            row=nbtlib.Compound({'Pos':copy.deepcopy(cell['Pos']),'State':parse_state('minecraft:air')})
            static_rows[chunk][p]=row
        for cell in tag['Ground']:
            if int(cell['Object']) not in ground:continue
            p=tuple(unpack(cell['Pos']))
            ground_rows[chunk][p]=None
            static_rows[chunk][p]=nbtlib.Compound({'Pos':copy.deepcopy(cell['Pos']),'State':parse_state(state_at(p))})
    for m in moves:
        index=m['index'];delta=m['delta'];source=m['source_centre'];target=m['target_centre']
        points=set(owned[index])|set(ground[index]);current_be=0;nonair=0
        for p in points:
            q=tuple(a+b for a,b in zip(p,delta))
            if q in target_owner and target_owner[q]!=index:raise ValueError('Components overlap at target')
            target_owner[q]=index
            if q in block_entities and not member(q):foreign.append(dict(kind='destination_block_entity',tower=index,pos=q,id=str(block_entities[q].get('id',''))))
            desired[q]=code_at(p);nonair+=state_at(p) not in AIR
            be_after.pop(q,None)
            if p in block_entities:be_after[q]=move_nbt(block_entities[p],delta);current_be+=1
        tower=relocated_topology['data']['Towers'][index]
        tower['IdentityCentre']=copy.deepcopy(tower.get('IdentityCentre',tower['Centre']))
        tower['Centre']=translated(tower['Centre'],delta)
        if 'FixedCorePos'in tower:tower['FixedCorePos']=translated(tower['FixedCorePos'],delta)
        tower['NegativeDomeAnchorMask']=nbtlib.LongArray([translated(v,delta)for v in tower['NegativeDomeAnchorMask']])
        cargo_file=data/'city_rigid_generation_r45/cargo'/f'{index}.dat'
        old_cargo=nbtlib.load(cargo_file);new_cargo=copy.deepcopy(old_cargo);building=new_cargo['data']['Buildings'][0]
        building['IdentityCentre']=copy.deepcopy(tower['IdentityCentre']);building['Centre']=copy.deepcopy(tower['Centre'])
        building['NegativeDomeAnchorMask']=copy.deepcopy(tower['NegativeDomeAnchorMask'])
        if 'R45FixedControllerPos'in building:building['R45FixedControllerPos']=translated(building['R45FixedControllerPos'],delta)
        building['RelocationSnapshotJourney']=copy.deepcopy(journey)
        cells=[];base=source[1]if depth==0 else m['base'];half=m['half']
        for y in range(int(tower['Height'])+4):
            for z in range(-half,half+1):
                for x in range(-half,half+1):
                    p=(source[0]+x,base+y,source[2]+z);state=state_at(p)
                    if state in AIR and p not in block_entities:continue
                    cell=nbtlib.Compound({'Pos':nbtlib.Long(packed((x,y,z))),'State':parse_state(state)})
                    if p in block_entities:cell['NBT']=move_nbt(block_entities[p],delta)
                    cells.append(cell)
        building['Cargo']=nbtlib.List[nbtlib.Compound](cells)
        metadata(out,cargo_file.relative_to(world),old_cargo,new_cargo)
        for p,cell in owned[index].items():
            q=tuple(a+b for a,b in zip(p,delta));chunk=q[0]//16,q[2]//16
            old=loaded[p[0]//16,p[2]//16]
            state=copy.deepcopy(cell['State']if'State'in cell else old['Palette'][int(cell['StateId'])])
            row=copy.deepcopy(cell);row.pop('StateId',None);row['State']=state;row['Pos']=nbtlib.Long(packed(q))
            if 'NBT'in row:row['NBT']=move_nbt(row['NBT'],delta)
            static_rows[chunk][q]=row
        for p,cell in ground[index].items():
            q=tuple(a+b for a,b in zip(p,delta));chunk=q[0]//16,q[2]//16
            state=loaded[p[0]//16,p[2]//16]['Palette'][int(cell['StateId'])]
            row=copy.deepcopy(cell);row.pop('StateId');row['State']=copy.deepcopy(state);row['Pos']=nbtlib.Long(packed(q))
            ground_rows[chunk][q]=row
        component_reports.append(dict(index=index,source=source,target=target,depth=depth,
            component_cells=len(points),nonair=nonair,block_entities=current_be,current_cargo=len(cells),
            source_door=[source[0],m['base']+1,source[2]+half+1],target_door=[target[0],m['base']+1,target[2]+half+1]))
        print(f'Prepared component {len(component_reports)}/{len(moves)}',flush=True)
    for chunk in set(static_rows)|set(ground_rows):
        tag=shard(chunk);pal=tag['Palette'];codes={palette_state(v):i for i,v in enumerate(pal)}
        for key,changes in [('Static',static_rows[chunk]),('Ground',ground_rows[chunk])]:
            kept=[cell for cell in tag[key]if tuple(unpack(cell['Pos']))not in changes]
            for cell in changes.values():
                if cell is None:continue
                state=cell.pop('State');name=palette_state(state)
                if name not in codes:codes[name]=len(pal);pal.append(state)
                cell['StateId']=nbtlib.Int(codes[name]);kept.append(cell)
            tag[key]=nbtlib.List[nbtlib.Compound](kept)
        relative=DATA/'city_rigid_generation_r45/chunks'/f'{chunk[0]}_{chunk[1]}.dat'
        before=loaded.get(chunk)
        if before is not None:metadata(out,relative,before,tag)
        else:
            file=out/'after'/relative;file.parent.mkdir(parents=True,exist_ok=True);tag.save(file,gzipped=True)
    metadata(out,topology_file.relative_to(world),topology,relocated_topology)
    (out/'preserved').mkdir();shutil.copyfile(control_file,out/'preserved'/control_file.name)
    # Archive complete native block-entity images; only x/y/z are translated.
    changed_be=[]
    for p in set(block_entities)|set(be_after):
        before=block_entities.get(p);after=be_after.get(p)
        if before==after:continue
        row=nbtlib.Compound({'Pos':nbtlib.Long(packed(p))})
        if before is not None:row['Before']=copy.deepcopy(before)
        if after is not None:row['After']=copy.deepcopy(after)
        changed_be.append(row)
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changed_be)}).save(out/'block-entities.dat',gzipped=True)
    actor_refs=[];entity_dir=dimension_dir(world,DIM)/'entities'
    for rx,rz in measured_groups:
        file=entity_dir/f'r.{rx}.{rz}.mca'
        if not file.exists()or not file.stat().st_size:continue
        _,records=read_region(file)
        for slot,record in enumerate(records):
            if record is None:continue
            root=parse_chunk(record)
            for actor in root.get('Entities',[]):
                pos=list(map(float,actor.get('Pos',[])))
                if len(pos)!=3:continue
                source=member(pos);destination=next((m for m in moves if contains(m['target_box'],pos)),None)
                if source or destination:
                    actor_refs.append(dict(region=file.name,slot=slot,uuid=list(map(int,actor.get('UUID',[]))),
                        id=str(actor.get('id','')),pos=pos,source_component=source['index']if source else None,
                        target_component=destination['index']if destination else None,nbt=actor.snbt()))
    deltas=defaultdict(list)
    for p,after in desired.items():
        before=code_at(p)
        if before!=after:deltas[p[0]//512,p[2]//512].append((p,before,after))
    for (rx,rz),rows in deltas.items():
        np.savez_compressed(out/'delta'/f'r.{rx}.{rz}.npz',positions=np.asarray([r[0]for r in rows],np.int32),
            before=np.asarray([r[1]for r in rows],np.uint16),after=np.asarray([r[2]for r in rows],np.uint16),palette=np.asarray(palette))
    (out/'actors.json').write_text(json.dumps(actor_refs,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest=dict(schema='projectseele.hakone-city-cross-candidate.v1',world=str(world),world_written=False,
        source_plan=str(planfile),depth=depth,components=component_reports,changed_blocks=sum(map(len,deltas.values())),
        block_entity_changes=len(changed_be),actor_references=len(actor_refs),foreign_block_entities=foreign,
        metadata_files=len(list((out/'after').rglob('*.dat'))),original_ledger_and_journals='unchanged',
        inverse='swap before/after for block and NBT deltas; remove metadata files absent from before',
        installation_ready=False,remaining=['Retired lot surface/roof grading with main streetscape',
            'Connect translated underground doorway aprons to maintenance access',
            'Resolve recorded foreign devices/actors without deleting identities',
            'Combine terrain and street patches, then stopped-world install and changed LOD refresh'])
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items()if k not in ('components','foreign_block_entities')},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    with stopped_world(args.world):prepare(args.world,args.plan,args.out)


if __name__=='__main__':main()

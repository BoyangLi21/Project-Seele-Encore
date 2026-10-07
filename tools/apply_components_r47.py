"""Apply measured R47 component deltas once, through the existing palette writer."""
from pathlib import Path
from collections import defaultdict
import argparse,copy,gzip,json
import nbtlib
import regional_voxels as v
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--components',type=Path,nargs='+',required=True);parser.add_argument('--batch',required=True)
    parser.add_argument('--native-qa',action='store_true')
    parser.add_argument('--revision',type=int,choices=(47,48,49),default=47)
    args=parser.parse_args();world=args.world.resolve();base=(ROOT/f'artifacts/rebuild_r{args.revision}').resolve()
    native_sources={base/'native_qa/game/saves'/name for name in (f'SEELE_R{args.revision}_WORLD',f'SEELE_R{args.revision}_RELEASE')}
    if args.revision in(48,49):
        receipt=base/'native_qa/COPY_ONCE.json'
        if receipt.is_file():
            copy_info=json.loads(receipt.read_text('utf-8-sig'));retained=(base/f'native_qa/worlds/SEELE_R{args.revision}_QA').resolve()
            if copy_info.get('copied_once') is True and Path(copy_info['qa_world']).resolve()==retained:
                native_sources.add(retained)
    allowed=world.is_relative_to(base/'construction') or args.native_qa and world in native_sources
    if not allowed:raise ValueError('Only Root construction or the explicit stopped native QA copy is writable')
    out=base/'applied'/args.batch
    if list(out.glob('components/applied_*/receipt.json')):raise ValueError('Batch already applied; do not replay')
    rows={};owners=defaultdict(int)
    for component in args.components:
        component=component.resolve()
        r50_airport=(ROOT/'artifacts/rebuild_r50/underground_airport/candidates').resolve()
        r50_yashima=(ROOT/'artifacts/rebuild_r50/yashima/attempt07_approach').resolve()
        if not(component.is_relative_to(base)or args.revision==49 and
                (component.is_relative_to(r50_airport)or component.is_relative_to(r50_yashima))):
            raise ValueError('Foreign component')
        with gzip.open(component/'forward.jsonl.gz','rt',encoding='utf-8') as stream:
            for line in stream:
                row=json.loads(line);point=tuple(row['pos']);owners[component.name]+=1
                previous=rows.get(point)
                if previous is not None:
                    if any(previous.get(key)!=row.get(key) for key in ('before','after','before_nbt','after_nbt')):
                        raise ValueError(('Conflicting components',point,previous,row))
                rows[point]=row
    measured=MeasuredWorld(world)
    for point in rows:measured.box(point,point)
    measured.load();tags={};chunks=defaultdict(list)
    for point in rows:chunks[point[0]//16,point[2]//16].append(point[1])
    for (cx,cz),ys in chunks.items():
        tags.update(iter_block_entities(world,v.DIM,(cx*16,min(ys),cz*16),(cx*16+15,max(ys),cz*16+15),selected_chunks={(cx,cz)}))
    painter=v.Painter()
    for point,row in rows.items():
        actual=measured.block(point)
        if actual!=row['before']:raise ValueError(('State changed',point,actual,row['before']))
        before=None if row.get('before_nbt') is None else nbtlib.parse_nbt(row['before_nbt'])
        after=None if row.get('after_nbt') is None else nbtlib.parse_nbt(row['after_nbt'])
        if tags.get(point)!=before:raise ValueError(('Full device NBT changed',point))
        painter.match((*point,*point),row['before'],row['after'],f'r{args.revision}/'+row.get('owner',row.get('reason','component')))
        if row['before']==row['after'] and after is not None:
            painter.entity_updates[point]=(row['before'],copy.deepcopy(before),copy.deepcopy(after),'r47/full_device_nbt')
        if after is not None:painter.block_entities[point]=after
    lock=world/'session.lock'
    if not lock.exists():
        with lock.open('xb') as stream:stream.write('☃'.encode('utf-8'))
    v.WORLD=world;v.OUT=out;out.mkdir(parents=True,exist_ok=True)
    painter.save_plan('components');painter.apply('components')
    (out/'components.json').write_text(json.dumps({'components':dict(owners),'unique_cells':len(rows),'world':str(world),'entities_and_progress_not_replaced':True},indent=2),encoding='utf-8')

if __name__=='__main__':main()

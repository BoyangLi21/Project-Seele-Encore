"""Root's finite short steel connections from isolated rail anchors to real lining.

Candidates stay artifacts until the complete gate and moving-assembly checks.
The measured air is clearance for an explicitly required support, not a room.
"""
import argparse,json
from collections import defaultdict
from pathlib import Path
from query_blocks import iter_selected_sections,iter_block_entities,AIR
from r52_spatial_plan import BASE


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--extended',action='store_true');args=parser.parse_args()
    before=json.loads((BASE/'fixed_foot_rail_foundations/existing_shell_native_sockets/PLAN.json').read_text('utf8'))
    pending=before['pending'];known_blocked=set();out=BASE/'fixed_foot_rail_foundations/connectors'
    if args.extended:
        old=json.loads((out/'GATE_CLEAR_CANDIDATES.json').read_text('utf8'));covered={tuple(r['anchor'])for r in old['candidates']}
        pending=[r for r in pending if tuple(r['position'])not in covered]
        known_blocked={tuple(r['cell'])for r in json.loads((out/'GATE_CLEARANCE.json').read_text('utf8'))['conflicting_cells']}
    points={tuple(r['position'])for r in pending};world=BASE/'WORLD_R52'
    wanted=set()
    # Finite axis-aligned bracket options, not an unrestricted excavation search.
    directions=((1,0,0),(-1,0,0),(0,0,1),(0,0,-1),(0,-1,0),(0,1,0))
    designs={};limit=28 if args.extended else 14
    for point in points:
        paths=[]
        for d in directions:
            line=[point]
            for n in range(1,limit+1):
                q=tuple(point[i]+d[i]*n for i in range(3));line.append(q);paths.append(tuple(line))
                if n<=(28 if args.extended else 7):
                    for e in directions:
                        if sum(a*b for a,b in zip(d,e)):continue
                        branch=line.copy()
                        for m in range(1,(12 if args.extended else limit)+1):
                            branch.append(tuple(q[i]+e[i]*m for i in range(3)));paths.append(tuple(branch))
        designs[point]=paths
        for path in paths:wanted.update(path)
    selected=defaultdict(set);sections=defaultdict(set);states={}
    for x,y,z in wanted:selected[x//16,z//16].add(y//16);sections[x//16,z//16,y//16].add((x,y,z))
    for cx,cz,sy,palette,ix in iter_selected_sections(world,'projectseele:geofront',selected):
        a=ix.reshape(16,16,16)
        for x,y,z in sections[cx,cz,sy]:states[x,y,z]=palette[int(a[y%16,z%16,x%16])]
    assert len(states)==len(wanted)
    supports={'projectseele:nerv_shaft_panel','projectseele:nerv_structural_panel','projectseele:nerv_machine_edge',
        'projectseele:nerv_machine_panel','projectseele:nerv_floor_panel','minecraft:stone','minecraft:andesite','minecraft:diorite',
        'minecraft:black_concrete','minecraft:gray_concrete','minecraft:light_gray_concrete','minecraft:deepslate','minecraft:deepslate[axis=y]'}
    candidates=[];unresolved=[]
    for row in pending:
        point=tuple(row['position']);valid=[]
        for path in designs[point]:
            if states[path[-1]]not in supports or not all(states[q]in AIR and q not in known_blocked for q in path[:-1]):continue
            # Keep the shell's existing top-level hardware, no material overwrite.
            moves=[tuple(b[i]-a[i]for i in range(3))for a,b in zip(path,path[1:])]
            bends=sum(a!=b for a,b in zip(moves,moves[1:]));valid.append((len(path)+bends*2,path))
        valid=sorted(set(valid),key=lambda a:(a[0],a[1]))
        if not valid:unresolved.append(list(point));continue
        # Retain multiple finite options until actual moving steel determines one.
        for rank,(cost,path)in enumerate(valid[:128 if args.extended else 48]):
            candidates.append(dict(anchor=list(point),path_id=row['path'],rank=rank,cost=cost,
                cells=[list(p)for p in path[:-1]],attachment=list(path[-1]),attachment_state=states[path[-1]]))
    out.mkdir(exist_ok=True)
    cells=sorted({tuple(q)for row in candidates for q in row['cells']})
    report=dict(world_written=False,native_verified=False,anchors=len(pending),candidates=candidates,candidate_cells=[list(p)for p in cells],
        source_path_sha256=before['source_sha256'],unresolved=unresolved,
        purpose='Short finite foundation brackets for the exact original source rail anchor pads; final paths require whole gate and carrier clearance')
    (out/('EXTENDED_CANDIDATES.json'if args.extended else'CANDIDATES.json')).write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(dict(anchors=len(pending),options=len(candidates),candidate_cells=len(cells),unresolved=unresolved)),flush=True)


if __name__=='__main__':main()

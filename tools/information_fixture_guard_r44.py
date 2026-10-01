"""Keep later bulk repairs from building through retained wide information faces.

The real block entity owns an out-of-anchor mesh. An explicit NBT replacement
or exact anchor retirement transfers that ownership to the caller's complete
component plan; unrelated bulk wall/floor fills do not. Reads use query_blocks.
"""
from collections import defaultdict
from query_blocks import iter_block_entities
from measure_world_r40 import MeasuredWorld, properties


def retained_faces(painter, world, dimension):
    if not painter.by_chunk:
        return {}
    chunks={(cx+dx,cz+dz) for cx,cz in painter.by_chunk
            for dx,dz in ((0,0),(-1,0),(1,0),(0,-1),(0,1))}
    lo=(min(cx for cx,cz in chunks)*16, min(op.box[1] for op in painter.ops)-1,
        min(cz for cx,cz in chunks)*16)
    hi=(max(cx for cx,cz in chunks)*16+15, max(op.box[4] for op in painter.ops),
        max(cz for cx,cz in chunks)*16+15)
    owners=[]
    for q,tag in iter_block_entities(world,dimension,lo,hi,selected_chunks=chunks):
        if str(tag.get('id',''))!='projectseele:station_departure_board' or q in painter.block_entities:
            continue
        retired=any(op.mode=='match' and op.box==(*q,*q)
                    and op.extra[0].startswith('projectseele:station_departure_board[')
                    and not op.state.startswith('projectseele:station_departure_board[')
                    for op in (painter.ops[i] for i in painter.by_chunk.get((q[0]//16,q[2]//16),[])))
        if not retired:
            owners.append(q)
    if not owners:
        return {}
    measured=MeasuredWorld(world,dimension)
    for q in owners:measured.around(q,0)
    measured.load();faces=defaultdict(dict)
    for q in owners:
        state=measured.block(q)
        if not state or not state.startswith('projectseele:station_departure_board['):
            continue  # Compact panels fit their own anchor cell.
        axis=properties(state)['facing'] in ('north','south')
        for width in (-1,0,1):
            for height in (0,1):
                p=(q[0]+(width if axis else 0),q[1]+height,q[2]+(0 if axis else width))
                if p!=q and (p[0]//16,p[2]//16)in painter.by_chunk:
                    faces[p[0]//16,p[2]//16][p]=q
    return faces


def check_retained_faces(faces, chunk, before, after, palettes, minimum):
    for p,owner in faces.get(chunk,{}).items():
        yy=p[1]-minimum*16
        if not 0<=yy<before.shape[0]:
            continue
        old,new=int(before[yy,p[2]&15,p[0]&15]),int(after[yy,p[2]&15,p[0]&15])
        if old==65535 or old==new:
            continue
        state=palettes[new]
        if state.split('[')[0] not in {'minecraft:air','minecraft:cave_air','minecraft:void_air','minecraft:light'}:
            raise RuntimeError(f'Bulk edit intersects retained information face: cell {p}, board {owner}, {palettes[old]} -> {state}; include an explicit complete fixture relocation instead')

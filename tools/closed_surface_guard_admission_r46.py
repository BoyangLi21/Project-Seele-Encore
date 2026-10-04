"""Prevent explicit old guard recipes from restoring a closed, supported pit."""
from pathlib import Path
import json
from query_blocks import read_box

NAME='closed_surface_guard_sides_r46.json'
NORMAL={'east':(1,0),'west':(-1,0),'south':(0,1),'north':(0,-1)}
def props(state):return dict(p.split('=',1)for p in state.partition('[')[2].rstrip(']').split(',')if'='in p)
def validate_closed_surface_guards(painter,world,dimension):
 file=Path(world)/NAME
 if not file.is_file():return
 data=json.loads(file.read_text('utf8'))
 if data['schema']!='projectseele.closed-surface-guard.r46.v1':raise RuntimeError('Unknown closed surface guard authority')
 if data['dimension']!=dimension:return
 wanted={tuple(row['guard']):row for row in data['guards']};checked={}
 for op in painter.ops:
  if not op.state.startswith('projectseele:nerv_edge_rail['):continue
  p=props(op.state);a,b,c,d,e,f=op.box
  for q,row in wanted.items():
   if not(a<=q[0]<=d and b<=q[1]<=e and c<=q[2]<=f):continue
   for side in row['retired_sides']:
    if p.get(side)!='true':continue
    floor=tuple(row['supported_floor'][side]['pos']);expected=row['supported_floor'][side]['state']
    if floor not in checked:checked[floor]=read_box(Path(world),dimension,floor,floor).get(floor)
    # A separately measured exact excavation explicitly transfers ownership
    # of this ground. Historical replay without such a plan must fail.
    excavation=any(edit.mode=='match'and edit.box==(*floor,*floor)and edit.extra[0]==expected and edit.state in{'minecraft:air','minecraft:cave_air','minecraft:void_air'}for edit in painter.ops)
    if checked[floor]==expected and not excavation:
     raise RuntimeError(f'Closed pit guard {q}/{side} would block its restored full ground {floor}; retire the old recipe or measure a new actual drop')

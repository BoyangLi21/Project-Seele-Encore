"""Measured underground door authority; never synthesize train stopping phase."""
from pathlib import Path
import json
FILE='r47_native_platform_door_alignment.json'
EXPECTED={'-7994891824548717036','6885833474752774166','1856022593920040742','-4820290924094918262','7409068398910781353','-4822663963938582820','-4991105154196472855','8431810501538351356'}

def authority(world):
 path=Path(world)/FILE
 if not path.is_file():raise RuntimeError('Refuse underground APG midpoint/5m phase generation without complete actual R47 stopped-car authority: '+str(path))
 data=json.loads(path.read_text('utf8'));assert data['schema']=='projectseele.r47.actual-native-door-authority.v1'
 rows={r['platform_id']:r for r in data['platforms']};assert set(rows)==EXPECTED and data['complete_wanted8_ids']is True
 return rows

def bank(world,pid,offset):
 row=authority(world).get(str(pid));assert row is not None,('Undeclared underground platform',pid)
 value=next((b for b in row['banks']if b['offset']==offset),None)
 if value is None:raise RuntimeError(('No measured active bank for this native platform; no new bank or cross-carway gate allowed',pid,offset))
 return row,value

def door_part(mouths,u,face):
 if u+1 in mouths:part=0
 elif u in mouths:part=1
 else:return None
 return 1-part if face in('south','west')else part

def floor_link(mouths,u,face):
 pair_cells={p for m in mouths for p in(m-1,m)};cw=1 if face in('north','east')else-1
 door=u in pair_cells;right=u+cw in pair_cells;left=u-cw in pair_cells
 return 2 if door and right else 3 if door and left else 1 if right else 4 if left else 0

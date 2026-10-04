"""Frozen full NBT from the pinned MTR native factory, with explicit admission.

The template corpus is a native registry/factory observation. New states require
a fresh native export rather than guessed fields or a wildcard type mapping.
"""
from pathlib import Path
import copy,json
import nbtlib

FILE=Path(__file__).with_name('native_apg_factory_templates_r46.json')
_CACHE=None
def canonical(state):
 name,sep,props=state.partition('[')
 return name if not sep else name+'['+','.join(sorted(props[:-1].split(',')))+']'

def templates():
 global _CACHE
 if _CACHE is None:
  data=json.loads(FILE.read_text('utf8'))
  if data['schema']!='projectseele.native-apg-factory.r46.v1' or data['mtr_version']!='4.0.5' or not data['native_factory_roundtrip_all16']:
   raise RuntimeError('APG native factory corpus is not admitted')
  _CACHE={canonical(r['state']):nbtlib.parse_nbt(r['full_snbt']) for r in data['states']}
  if len(_CACHE)!=16:raise RuntimeError('Complete16 reviewed APG factory states required')
 return _CACHE

def native_apg_tag(position,state):
 state=canonical(state);tag=templates().get(state)
 if tag is None:raise RuntimeError('No reviewed native APG factory template for '+state)
 tag=copy.deepcopy(tag)
 for key,value in zip(('x','y','z'),position):tag[key]=nbtlib.Int(int(value))
 return tag

def validate_apg_entities(painter):
 """Every explicit desired native APG cell carries its complete native tag.

Validation deliberately refuses a missing binding. A broad old material edit
cannot silently erase a retained block entity. Callers must preserve its full
observed tag or bind native_apg_tag for an explicitly new/missing native door.
 """
 expected={}
 for op in painter.ops:
  if not op.state.startswith('mtr:apg_door['):continue
  x0,y0,z0,x1,y1,z1=op.box
  if (x1-x0+1)*(y1-y0+1)*(z1-z0+1)>500000:raise RuntimeError('Explicit APG component mask too large')
  if canonical(op.state)not in templates():raise RuntimeError('Unreviewed APG state: '+op.state)
  for x in range(x0,x1+1):
   for y in range(y0,y1+1):
    for z in range(z0,z1+1):expected[x,y,z]=op.state
 for q,state in expected.items():
  tag=painter.block_entities.get(q)
  if tag is None:raise RuntimeError(f'Native APG component {q} has no full BE binding; retain exact measured NBT or call native_apg_tag(position,state)')
  if str(tag.get('id',''))!='mtr:apg_door' or tuple(int(tag.get(k,-2147483648))for k in('x','y','z'))!=q:
   raise RuntimeError(f'Native APG full BE type/position binding differs at {q}')

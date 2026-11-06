"""Bounded source/delivery measurements at the user's explicitly reported ports."""
from pathlib import Path
import json
import numpy as np
import survey_r52_original_complex as survey

BOXES={
 'transfer_pit':((-32,-1052,112),(10,-1028,148)),
 'old_wells':((22,-390,-36),(50,-365,-5)),
 'suspended_research':((184,-470,400),(207,-450,425)),
 'pyramid_projection':((49,-468,363),(75,-445,388)),
 'old_west_lift':((2,-563,248),(21,-493,269)),
 'old_east_lift':((55,-563,299),(75,-493,321)),
 'crosscut_wall':((42,-563,354),(64,-483,388)),
 'black_corridor':((17,-506,357),(39,-492,379)),
 'lower_junction':((72,-563,358),(108,-541,391)),
 'pyramid_apex':((20,-306,305),(40,-278,325)),
}
def run(base):
 out=base/'oct16-request-measurements';out.mkdir(exist_ok=True)
 report={}
 for world in ('WORLD','CANDIDATE'):
  survey.WORLD=base/world
  for key,(lo,hi) in BOXES.items():
   dest=out/f'{world}-{key}.npz'
   if dest.exists():continue
   a,palette=survey.measure(lo,hi)
   np.savez_compressed(dest,origin=lo,states=a,palette=palette)
   ids,counts=np.unique(a,return_counts=True)
   report[world+'-'+key]={palette[int(i)]:int(n) for i,n in zip(ids,counts)}
   print(world,key,a.shape,flush=True)
 (out/'palette-counts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);run(p.parse_args().base)

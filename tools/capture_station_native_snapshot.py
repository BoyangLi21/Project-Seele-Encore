"""Capture native transport bytes from a stopped world for isolated authoring."""
import argparse
from install_r53_carrier_trays import stopped_world
from native_transit_additions import inventory
from pathlib import Path
from map_pipeline.delivery_check import read,write


def capture(a):
    with stopped_world(a.world):
        current=inventory(a.world/'mtr')
        if len(current)!=a.expected_members:raise ValueError('Unexpected installed native inventory')
        a.out.mkdir(exist_ok=False)
        for name,content in current.items():
            target=a.out/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
        if inventory(a.out)!=current:raise ValueError('Native snapshot readback differs')
    if a.continuation:
        state=read(a.continuation);state['current_native_snapshot']=str(a.out);write(a.continuation,state)
    print('Cold native snapshot:',len(current),'members; no world writes.')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for k in('world','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--continuation',type=Path);p.add_argument('--expected-members',type=int,required=True)
    capture(p.parse_args())

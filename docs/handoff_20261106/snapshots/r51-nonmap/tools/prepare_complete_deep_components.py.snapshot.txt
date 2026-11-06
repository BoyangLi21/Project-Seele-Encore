"""Prepare the user-approved -384 translation from current complete components.

The old original component masks and explicit three-bank room volumes grant
ownership. Current states and original NBT are copied; two main lift shafts and
their added landings are composed separately by Root. No world-writing entry.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import nbtlib
import survey_r52_original_complex as survey
from query_blocks import iter_block_entities
from r52_spatial_plan import Frame, HANGAR, TERMINAL
from facility_frame_nbt_r52 import block_entity_in_frame

SHIFT=Frame(0,0,-384,0)
DIM='projectseele:geofront'


def slices(lo, box):
    x,y,z,X,Y,Z=box
    return np.s_[y-lo[1]:Y-lo[1]+1,z-lo[2]:Z-lo[2]+1,x-lo[0]:X-lo[0]+1]


def clipped(lo,hi,box):
    a=np.maximum(lo,box[:3]);b=np.minimum(hi,box[3:])
    return None if (a>b).any() else (*a,*b)


def masks(base):
    s=np.load(base/'survey/original_hangar_transfer_launch.npz')
    m=np.load(base/'hangar_component/owner_mask.npz')['move'][:,::-1,::-1]
    oldlo=s['origin'];oldhi=oldlo+np.array(s['states'].shape)[[2,0,1]]-1
    hl,hh=HANGAR.box(oldlo,oldhi)
    lo=np.minimum(hl,[-54,-680,9]);hi=np.maximum(hh,[108,-546,112])
    owned=np.zeros(tuple((hi-lo+1)[[1,2,0]]),bool)
    owned[slices(lo,(*hl,*hh))]=m
    for z in (58,10):owned[slices(lo,(-29,-680,z,89,-546,z+36))]=True
    for a,b in ((95,105),(47,57)):owned[slices(lo,(-54,-653,a,108,-561,b))]=True
    for z in (106,58,10):
        for cx in (-12,30,72):owned[slices(lo,(cx-17,-652,z,cx+17,-570,z+1))]=True
    parts=[('hangar_ramp_banks',lo,hi,owned)]
    s=np.load(base/'survey/terminal_complete.npz');tl,th=TERMINAL.box(s['origin'],s['origin']+np.array(s['states'].shape)[[2,0,1]]-1)
    parts.append(('complete_terminal',np.array(tl),np.array(th),np.ones(s['states'].shape,bool)))
    return parts


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--lift-civil',type=Path,required=True);args=p.parse_args()
    base=args.base.resolve();world=base/'WORLD';out=base/'deep_components_384';out.mkdir(exist_ok=True)
    assert json.loads((base/'deeper_foundation_1344/APPLIED.json').read_text('utf8'))['new_min_y']==-1344
    assert not (out/'APPLIED.json').exists()
    survey.WORLD=world
    report=[];devices=[]
    # The full signed owner boxes include call backplates and threshold trims.
    lift_ownership=json.loads((args.lift_civil/'OWNERSHIP.json').read_text('utf8'))
    landing_boxes=[(*r['source'][0],*r['source'][1]) for r in lift_ownership['added_moving_pieces']]
    for name,lo,hi,owned in masks(base):
        y,z,x=np.ogrid[lo[1]:hi[1]+1,lo[2]:hi[2]+1,lo[0]:hi[0]+1]
        shaft=((x>=6)&(x<=12)&(z>=250)&(z<=256)&(y>=-848)&(y<=-497))|((x>=63)&(x<=69)&(z>=299)&(z<=305)&(y>=-605)&(y<=-452))
        owned &= ~np.broadcast_to(shaft,owned.shape)
        for box in landing_boxes:
            box=clipped(lo,hi,box)
            if box is not None:owned[slices(lo,box)]=False
        before,palette=survey.measure(tuple(lo),tuple(hi))
        destlo=lo+[0,-384,0];desthi=hi+[0,-384,0]
        target_before,tp=survey.measure(tuple(destlo),tuple(desthi))
        names=list(dict.fromkeys(palette+tp+['minecraft:stone','minecraft:deepslate[axis=y]']))
        ids={s:i for i,s in enumerate(names)}
        before=np.array([ids[s] for s in palette],np.uint16)[before]
        target_before=np.array([ids[s] for s in tp],np.uint16)[target_before]
        occupied={names[int(i)]:int(n) for i,n in zip(*np.unique(target_before[owned],return_counts=True))}
        assert set(occupied)<={'minecraft:stone','minecraft:deepslate[axis=y]','minecraft:deepslate','minecraft:bedrock'},('Unexpected authored destination',name,occupied)
        bedrock=np.argwhere(owned&(target_before==ids.get('minecraft:bedrock',-1)))[:,0]+destlo[1]
        assert np.all((bedrock>=-960)&(bedrock<=-956)),'Only explicitly retired old dimension bottom allowed'
        tags=dict(iter_block_entities(world,DIM,tuple(lo),tuple(hi)))
        selected={pos:t for pos,t in tags.items() if owned[pos[1]-lo[1],pos[2]-lo[2],pos[0]-lo[0]]}
        refs={p:SHIFT.block(p) for p,t in selected.items() if str(t['id'])=='movingelevators:elevator_tile'}
        destination_tags=dict(iter_block_entities(world,DIM,tuple(destlo),tuple(desthi)))
        for pos,tag in selected.items():
            q=SHIFT.block(pos);assert q not in destination_tags
            shifted=block_entity_in_frame(tag,SHIFT,reference_positions=refs)
            devices.append(dict(component=name,source=pos,target=q,before_snbt=tag.snbt(),after_snbt=shifted.snbt(),
                state=names[int(before[pos[1]-lo[1],pos[2]-lo[2],pos[0]-lo[0]])]))
        retired=before.copy()
        fill=np.broadcast_to(np.where(y<-672,ids['minecraft:deepslate[axis=y]'],ids['minecraft:stone']),owned.shape)
        retired[owned]=fill[owned]
        after=target_before.copy();after[owned]=before[owned]
        # Both the full component (including its air) and every retired cell
        # have exact inverse data; retained source cells stay byte-identical.
        np.savez_compressed(out/(name+'.npz'),origin=lo,destination_origin=destlo,palette=names,
            source_before=before,source_after=retired,destination_before=target_before,destination_after=after,owned=owned)
        assert np.array_equal(after[owned],before[owned])
        row=dict(name=name,source_box=[lo.tolist(),hi.tolist()],destination_box=[destlo.tolist(),desthi.tolist()],
            owned_volume=int(owned.sum()),source_changed=int((before!=retired).sum()),target_changed=int((target_before!=after).sum()),
            block_entities=len(selected),destination_measured_materials=occupied,
            npz_sha256=hashlib.sha256((out/(name+'.npz')).read_bytes()).hexdigest())
        report.append(row);print(json.dumps(row),flush=True)
    (out/'BLOCK_ENTITY_MOVES.json').write_text(json.dumps(devices,ensure_ascii=False,indent=2),'utf8')
    (out/'PLAN.json').write_text(json.dumps(dict(world=str(world),world_written=False,dy=-384,parts=report,
        main_shaft_axes_excluded=True,separate_main_landing_boxes=landing_boxes,office_preserved=True,
        pending=['compose two main lift shafts and landings','typed native groups and current actor graph movement','metadata references','native validation']),ensure_ascii=False,indent=2),'utf8')


if __name__=='__main__':main()

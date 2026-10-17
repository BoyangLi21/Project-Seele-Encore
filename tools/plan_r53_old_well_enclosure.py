"""Preview missing lining at the three active old-well junctions.

Uses the complete installed bank-two motion envelope, not an inferred room.
No world-writing entry point: mechanical clearance and ports remain separate
acceptance gates. A full horizontal escape test records both before and after.
"""
from collections import deque
from pathlib import Path
import argparse
import json
import numpy as np
import survey_r52_original_complex as survey
from query_blocks import AIR, iter_block_entities
from model_r53_facility import export, save_json

LO = (-40, -480, -85)
HI = (105, -350, 25)


def envelopes(base):
    shape = tuple((np.asarray(HI)-LO+1)[[1,2,0]])
    core = np.zeros(shape,bool); shell = core.copy()
    sources = [base/'phased_routes/final68_measurement/combined/MEASURED_SOURCE.npz',
               base/'phased_routes/reverse_head_edges_measurement/MEASURED_SOURCE.npz']
    for path in sources:
        data = np.load(path); origins = data['section_keys'][:,[0,2,1]]*16
        selected = np.flatnonzero(np.all(origins<=HI,axis=1)&np.all(origins+15>=LO,axis=1))
        c,s = data['core'],data['shell']
        for i in selected:
            org = origins[i]; a = np.maximum(LO,org); b = np.minimum(HI,org+15)
            dst = tuple(slice(int(a[k]-LO[k]),int(b[k]-LO[k]+1)) for k in (1,2,0))
            src = tuple(slice(int(a[k]-org[k]),int(b[k]-org[k]+1)) for k in (1,2,0))
            core[dst] |= c[i].reshape(16,16,16)[src]
            shell[dst] |= s[i].reshape(16,16,16)[src]
    return core,shell,sources


def escapes(cells,palette,core):
    passable = np.isin(cells,[i for i,s in enumerate(palette) if s in AIR])
    rows=[]
    for y in range(-466,-379):
        floor = passable[y-LO[1]]
        outside = np.zeros(floor.shape,bool); queue=deque()
        for z,x in np.argwhere(floor):
            if z in (0,floor.shape[0]-1) or x in (0,floor.shape[1]-1):
                outside[z,x]=True;queue.append((z,x))
        while queue:
            z,x=queue.popleft()
            for Z,X in ((z-1,x),(z+1,x),(z,x-1),(z,x+1)):
                if 0<=Z<floor.shape[0] and 0<=X<floor.shape[1] and floor[Z,X] and not outside[Z,X]:
                    outside[Z,X]=True;queue.append((Z,X))
        for variant,cx in enumerate((72.5,30.5,-11.5)):
            xx=np.arange(LO[0],HI[0]+1)
            seed=core[y-LO[1]] & floor & (abs(xx-cx)<10)[None,:]
            rows.append(dict(y=y,variant=variant,air_seed_cells=int(seed.sum()),
                             horizontal_escape=bool(np.any(seed&outside))))
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--world',required=True,type=Path)
    p.add_argument('--source-base',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    current=json.loads((args.world/'ROOT_RUNTIME_DIRECTORY.json').read_text('utf8'))
    previous=json.loads((args.source_base/'phased_routes/west_early_current/ROOT_PREVIOUS_PHASED.json').read_text('utf8'))
    for v in range(3):
        key=f'unit{v}/exit2/upright_continuous'
        a=next(l for l in current['legs'] if l['id']==key)
        b=next(l for l in previous['legs'] if l['id']==key)
        assert a['centre_curve']==b['centre_curve'],'Installed bank-two path changed'
    core,shell,sources=envelopes(args.source_base)
    survey.WORLD=args.world;before,palette=survey.measure(LO,HI)
    after=before.copy();yy,zz,xx=np.ogrid[LO[1]:HI[1]+1,LO[2]:HI[2]+1,LO[0]:HI[0]+1]
    protected=np.broadcast_to((xx>=89)&(zz>=-56)&(zz<=-46),before.shape).copy()
    protected |= np.broadcast_to((yy>=-490)&(zz<=-55),before.shape)
    for pos,tag in iter_block_entities(args.world,survey.DIM,LO,HI):
        x,y,z=np.asarray(pos)-LO;protected[y,z,x]=True
    def protect(v):
        if isinstance(v,dict):
            for r in v.get('supports',[]):
                q=r['position']
                if all(LO[k]<=q[k]<=HI[k] for k in range(3)):
                    x,y,z=np.asarray(q)-LO;protected[y,z,x]=True
            for child in v.values():protect(child)
        elif isinstance(v,list):
            for child in v:protect(child)
    protect(json.loads((args.world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8')))
    ring=shell&~core&~protected&((yy>=-466)&(yy<=-380))
    mask=ring&np.isin(before,[i for i,s in enumerate(palette) if s in AIR])
    for state in ('projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge'):
        if state not in palette:palette.append(state)
    after[mask]=palette.index('projectseele:nerv_shaft_panel')
    after[mask&(yy%12==0)]=palette.index('projectseele:nerv_machine_edge')
    assert not np.any(mask&core) and not np.any(mask&protected)
    report=dict(world_written=False,status='GEOMETRY_PREVIEW_REQUIRES_PORT_AND_NATIVE_REVIEW',
        source_world=str(args.world),bank_two_curve_unchanged=True,
        added_lining_cells=int(mask.sum()),no_existing_blocks_removed=True,
        full_motion_envelope_sources=[str(s) for s in sources],
        outside_complete_padded_motion_core=True,protected_lab_lift_devices_supports=True,
        before=escapes(before,palette,core),after=escapes(after,palette,core))
    save_json(args.out/'ENCLOSURE_REVIEW.json',report)
    np.savez_compressed(args.out/'EXACT_PREVIEW.npz',origin=LO,palette=palette,
                        before=before,after=after,core=core,shell=shell,positive_edit_mask=mask)
    export(after,palette,LO,HI,args.out,'old_well_enclosure_preview')
    print(json.dumps(dict(world_written=False,added=int(mask.sum()),
        before_leaking_slices=sum(r['horizontal_escape'] for r in report['before']),
        after_leaking_slices=sum(r['horizontal_escape'] for r in report['after']))))


if __name__=='__main__':main()

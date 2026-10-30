"""Reconcile a main-city repair with later stations and the current cold save.

Known station interiors and native running volumes keep their actual blocks.
Only conflicts explained by a later installed batch are accepted. Device moves
use the current complete tags, never the original authoring inventory.
"""
import argparse,copy,json
from collections import defaultdict
from pathlib import Path
import nbtlib
import numpy as np
from install_hakone_array_patch import Palette,compose
from query_blocks import iter_selected_sections,iter_block_entities
from install_r53_carrier_trays import stopped_world
from plan_ashi_landscape_r54 import NATURAL


def main(a):
    if a.out.exists():raise ValueError('Use a new reconciled candidate')
    (a.out/'source').mkdir(parents=True);(a.out/'delta').mkdir()
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Current-save merge incomplete'])))
    manifest=json.loads((a.revision/'manifest.json').read_text('utf8'))
    world=Path(manifest['world']);installed=Path(manifest['installed_predecessor']);revised=Path(manifest['revised_design'])
    later=[a.gis/name for name in('station-corridor-ready','tozan-valley-candidate-v5','funicular-candidate-v3','tozan-valley-north-completion')]
    oldrows=json.loads((installed/'neighbourhood.json').read_text('utf8'));newrows=json.loads((revised/'neighbourhood.json').read_text('utf8'))
    oldpos={tuple(d['source']):tuple(d['target'])for r in oldrows for d in r['devices']}
    newpos={tuple(d['source']):tuple(d['target'])for r in newrows for d in r['devices']}
    if oldpos.keys()!=newpos.keys():raise ValueError('Device identities changed')
    railvol=defaultdict(dict)
    for folder in ('tozan-native/validated-v7','ropeway-native/validated-v6'):
        file=a.gis/folder/'track_samples.json'
        if not file.exists():continue
        for rail in json.loads(file.read_text('utf8')):
            # Aerial cable geometry is not a ground rail bed.
            if rail['id'].startswith(('HRW','HRE')):continue
            for px,py,pz in rail['points']:
                x,y,z=map(int,np.floor([px,py,pz]))
                for X in range(x-1,x+2):
                    for Z in range(z-1,z+2):
                        key=(X,Z);low,high=railvol[X//16,Z//16].get(key,(320,-129))
                        railvol[X//16,Z//16][key]=(min(low,y-2),max(high,y+5))
    regions=[];unknown=[];held_count=0;merged_count=0;latest={}
    with stopped_world(world):
        latest=dict(iter_block_entities(world,'projectseele:geofront',(-832,-128,-640),(1023,319,1023)))
        for source in sorted((revised/'source').glob('*.npz')):
            name=source.name;palette=Palette()
            with np.load(source)as f:coords=f['coordinates']
            keys=[tuple(map(int,p))for p in coords];index={p:i for i,p in enumerate(keys)}
            selected={p:set(range(-8,20))for p in keys};blocks=np.zeros((len(keys),448,16,16),np.uint16)
            for cx,cz,sy,names,ids in iter_selected_sections(world,'projectseele:geofront',selected):
                blocks[index[cx,cz],sy*16+128:sy*16+144]=palette.codes(names)[ids].reshape(16,16,16)
            revision_file=a.revision/'delta'/name
            revision=compose([revision_file],palette)if revision_file.exists()else{}
            layers=[compose([folder/'delta'/name],palette)for folder in later if(folder/'delta'/name).exists()]
            natural=np.asarray([s.split('[')[0]in NATURAL for s in palette.names])
            coordinates=[];ranges=[0];offsets=[];before=[];after=[];yy=np.arange(-128,320)[:,None,None]
            for chunk,(at,expected,desired)in revision.items():
                current=blocks[index[chunk]].reshape(-1);actual=current[at]
                explained=(actual==expected)|(actual==desired);hold=np.zeros((448,16,16),bool)
                for layer in layers:
                    if chunk not in layer:continue
                    li,lb,la=layer[chunk];common,ri,ki=np.intersect1d(at,li,return_indices=True)
                    explained[ri]|=actual[ri]==la[ki]
                    owned=li[(current[li]==la)&~natural[la]]
                    if len(owned):
                        lo=np.full(256,320,np.int16);hi=np.full(256,-129,np.int16)
                        np.minimum.at(lo,owned%256,owned//256-128)
                        np.maximum.at(hi,owned%256,owned//256-128)
                        hold|=(yy>=lo.reshape(16,16))&(yy<=hi.reshape(16,16)+4)
                for (x,z),(low,high)in railvol[chunk].items():hold[max(0,low+128):min(448,high+129),z%16,x%16]=True
                # Keep a current device even if it is not present in an old
                # station's differential material mask.
                for pos,tag in latest.items():
                    if(pos[0]//16,pos[2]//16)==chunk and pos not in oldpos.values():
                        hold[pos[1]+128,pos[2]%16,pos[0]%16]=True
                bad=np.flatnonzero(~explained)
                for i in bad:
                    off=int(at[i]);unknown.append(dict(pos=[chunk[0]*16+off%16,off//256-128,chunk[1]*16+off//16%16],
                        expected=palette.names[expected[i]],actual=palette.names[actual[i]],desired=palette.names[desired[i]]))
                keep=hold.reshape(-1)[at];held_count+=int((keep&(actual!=desired)).sum())
                merged_count+=int(((actual!=expected)&explained&~keep).sum())
                wanted=desired.copy();wanted[keep]=actual[keep];changed=wanted!=actual
                if not changed.any():continue
                coordinates.append(chunk);offsets.append(at[changed]);before.append(actual[changed]);after.append(wanted[changed]);ranges.append(ranges[-1]+int(changed.sum()))
            np.savez_compressed(a.out/'source'/name,coordinates=coords,blocks=blocks,palette=np.asarray(palette.names))
            if coordinates:
                np.savez_compressed(a.out/'delta'/name,coordinates=np.asarray(coordinates,np.int32),ranges=np.asarray(ranges,np.int64),indices=np.concatenate(offsets).astype(np.uint32),
                    before=np.concatenate(before).astype(np.uint16),after=np.concatenate(after).astype(np.uint16),palette=np.asarray(palette.names))
                regions.append(dict(path='delta/'+name,cells=ranges[-1]))
            print('Merged current',name,ranges[-1],'cells;',len(unknown),'unknown conflicts',flush=True)
    (a.out/'unknown-current-edits.json').write_text(json.dumps(unknown,ensure_ascii=False,indent=2),'utf8')
    if unknown:raise ValueError('Unexplained current edits; keep the playable save unchanged')
    moves={oldpos[key]:newpos[key]for key in oldpos if oldpos[key]!=newpos[key]};changes={}
    for old,new in moves.items():
        if old not in latest:raise ValueError('Missing current device '+str(old))
        if new in latest and new not in moves:raise ValueError('Occupied device destination '+str(new))
        changes.setdefault(old,nbtlib.Compound())['Before']=copy.deepcopy(latest[old])
        tag=copy.deepcopy(latest[old])
        for k,v in zip(('x','y','z'),new):tag[k]=nbtlib.Int(v)
        changes.setdefault(new,nbtlib.Compound())['After']=tag
    nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes.values())}).save(a.out/'block-entities.dat',gzipped=True)
    for file in('neighbourhood.json','street-connections.json','district-surface.npz'):
        (a.out/file).write_bytes((revised/file).read_bytes())
    result=dict(world=str(world),regions=regions,cells=sum(r['cells']for r in regions),bounds_xz=[-832,-640,1023,1023],world_written=False,
        original_revision=str(a.revision),preserved_later_volume_cells=held_count,reconciled_later_cells=merged_count,moved_devices=len(moves),
        pending=['actual merged exterior/entrance check','cold installation and changed-region LOD'])
    (a.out/'manifest.json').write_text(json.dumps(result,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=['Merged exterior check pending'],unknown_current_edits=0,visual_verified=False),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('gis','revision','out'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())

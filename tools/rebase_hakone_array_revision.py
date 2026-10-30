"""Turn a revised frozen candidate into edits against its installed predecessor.

Neither input is a current-save replacement. The output installer must still
match current block states and full device tags; later installations and new
player edits are explicit merge conflicts, never silently overwritten.
"""
import argparse,copy,json
from pathlib import Path
import nbtlib
import numpy as np
from install_hakone_array_patch import Palette,compose


def device_changes(folder):
    file=folder/'block-entities.dat'
    if not file.exists():return {}
    result={}
    for change in nbtlib.load(file)['Changes']:
        tag=change.get('After',change.get('Before'))
        result[tuple(int(tag[k])for k in('x','y','z'))]=change
    return result


def rebase(installed,revised,out):
    if out.exists():raise ValueError('Use a fresh revision output')
    old_manifest=json.loads((installed/'manifest.json').read_text('utf8'))
    manifest=json.loads((revised/'manifest.json').read_text('utf8'))
    if old_manifest['world']!=manifest['world']:raise ValueError('Different world sources')
    check=json.loads((revised/'functional-check.json').read_text('utf8'))
    if check['errors']or check.get('road_conflicts'):raise ValueError('Revised candidate has unresolved functional errors')
    (out/'delta').mkdir(parents=True)
    names=sorted({p.name for folder in(installed,revised)for p in(folder/'delta').glob('*.npz')})
    regions=[]
    for name in names:
        palette=Palette()
        old_file=installed/'delta'/name;new_file=revised/'delta'/name
        old=compose([old_file],palette)if old_file.exists()else{}
        new=compose([new_file],palette)if new_file.exists()else{}
        coordinates=[];ranges=[0];offsets=[];before=[];after=[]
        for chunk in sorted(old.keys()|new.keys()):
            empty=(np.array([],np.int32),)*3
            ai,ab,aa=old.get(chunk,empty);bi,bb,ba=new.get(chunk,empty)
            common,ia,ib=np.intersect1d(ai,bi,return_indices=True)
            if np.any(ab[ia]!=bb[ib]):raise ValueError(f'Different original arrays at {chunk}')
            index=np.union1d(ai,bi);original=np.empty(len(index),np.int32)
            ap=np.searchsorted(index,ai);bp=np.searchsorted(index,bi)
            original[ap]=ab;original[bp]=bb
            current=original.copy();desired=original.copy();current[ap]=aa;desired[bp]=ba
            changed=current!=desired
            if not changed.any():continue
            coordinates.append(chunk);offsets.append(index[changed]);before.append(current[changed]);after.append(desired[changed]);ranges.append(ranges[-1]+int(changed.sum()))
        if not coordinates:continue
        if len(palette.names)>65535:raise ValueError('Revision palette overflow')
        np.savez_compressed(out/'delta'/name,coordinates=np.asarray(coordinates,np.int32),ranges=np.asarray(ranges,np.int64),
            indices=np.concatenate(offsets).astype(np.uint32),before=np.concatenate(before).astype(np.uint16),
            after=np.concatenate(after).astype(np.uint16),palette=np.asarray(palette.names))
        regions.append(dict(path='delta/'+name,cells=ranges[-1]))
        print('Rebased',name,ranges[-1],'cells',flush=True)
    a,b=device_changes(installed),device_changes(revised);changes=[]
    for position in a.keys()|b.keys():
        originals=[row['Before']for row in(a.get(position,{}),b.get(position,{}))if 'Before'in row]
        if len(originals)==2 and originals[0]!=originals[1]:raise ValueError('Different original device '+str(position))
        original=originals[0]if originals else None
        current=a[position].get('After')if position in a else original
        desired=b[position].get('After')if position in b else original
        if current==desired:continue
        change=nbtlib.Compound()
        if current is not None:change['Before']=copy.deepcopy(current)
        if desired is not None:change['After']=copy.deepcopy(desired)
        changes.append(change)
    if changes:nbtlib.File({'Changes':nbtlib.List[nbtlib.Compound](changes)}).save(out/'block-entities.dat',gzipped=True)
    result=dict(world=manifest['world'],regions=regions,cells=sum(row['cells']for row in regions),world_written=False,
        installed_predecessor=str(installed),revised_design=str(revised),device_changes=len(changes),
        pending=['merge later installed stations/valley and latest device contents while save is closed','full external street interfaces','cold installation and changed-region distant terrain'])
    (out/'manifest.json').write_text(json.dumps(result,indent=2),'utf8')
    # Explicitly not installable until later batches and current state are merged.
    (out/'functional-check.json').write_text(json.dumps(dict(errors=['Current-save/later-batch merge is pending'],
        revised_design_check=check,visual_verified=False),indent=2),'utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('installed','revised','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();rebase(a.installed,a.revised,a.out)

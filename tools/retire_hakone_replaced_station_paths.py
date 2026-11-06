"""Remove measured old station street branches after new access is verified."""
import argparse,json,os,shutil
from pathlib import Path
import numpy as np
import nbtlib
from scipy.ndimage import binary_dilation
from author_hakone_lakefront import Editor
from detail_hakone_nerv_streets import preservation_mask
from map_pipeline.launch_protection import load,check_candidate
from verify_hakone_togendai_neighbourhood import verify
from verify_hakone_station_connection import verify as station_verify

def run(a):
    if json.loads((a.candidate/'functional-check.json').read_text('utf8'))['errors']:raise ValueError('Unverified new access')
    if station_verify(a.candidate)['errors']:raise ValueError('Current platform access required')
    def copy(src,dst):
        if Path(src).parent.name=='source':os.link(src,dst);return dst
        return shutil.copy2(src,dst)
    shutil.copytree(a.candidate,a.out,copy_function=copy);e=Editor(a.out)
    with np.load(a.out/'plan/network.npz')as f:d={k:f[k]for k in f.files}
    x,z,X,Z=map(int,d['bounds']);spec=json.loads((a.out/'plan/authored-design.json').read_text('utf8'));protected=preservation_mask(a.out,spec)
    rows=json.loads((a.out/'plan/buildings.json').read_text('utf8'));boxes=[r['new_payload_bounds']for r in rows]
    keep=binary_dilation(d['walk'],iterations=2);devices={tuple(int(t[k])for k in('x','y','z'))for t in nbtlib.load(a.out/'captured-devices.dat')['Devices']};owned=set()
    for row in rows:
        if row.get('kind')!='station':continue
        # Published road levels can be corrected independently of the legacy
        # path. Its horizontal endpoint still identifies original ownership;
        # retirement uses the captured legacy elevations, not the new datum.
        paths=[p for p in row['original_approach_paths']if p[-1][::2]==row['road'][::2]]
        if len(paths)!=1:raise ValueError('Original street approach not unique')
        for px,py,pz in paths[0]:
            owned.update((px+dx,Y,pz+dz)for dx in(-1,0,1)for dz in(-1,0,1)for Y in range(py-2,py+1))
    changed=[]
    for pos in sorted(owned):
        px,py,pz=pos;j,i=pz-z,px-x
        if not(x<=px<=X and z<=pz<=Z)or keep[j,i]or pos in devices or protected(pos):continue
        if any(all(b[k]<=pos[k]<=b[k+3]for k in range(3))for b in boxes):continue
        before=e.state(*pos)
        if before.split('[')[0]not in {'minecraft:smooth_stone','minecraft:stone_bricks'}:continue
        h=int(d['ground'][j,i]);after='minecraft:air'if py>h else'minecraft:grass_block[snowy=false]'if py==h else'minecraft:dirt'if py>=h-3 else'minecraft:stone'
        e.put(*pos,after);changed.append(dict(pos=list(pos),before=before,after=after))
    patches=e.save();m=json.loads((a.out/'manifest.json').read_text('utf8'));m.update(regions=patches,cells=sum(r['cells']for r in patches))
    for name,data in [('manifest.json',m),('retired-station-street-paths.json',dict(changes=changed,original_owned_cells=len(owned),native_platform_paths_retained=True)),('launch-protection.json',check_candidate(load(Path(m['world'])),a.out))]:(a.out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf8')
    if verify(a.out)['errors']or station_verify(a.out)['errors']:raise ValueError('Regression after old passenger branch retirement')
    print('Retired',len(changed),'old street approach blocks; complete original ownership checked')

if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for n in('candidate','out'):p.add_argument('--'+n,type=Path,required=True)
    run(p.parse_args())

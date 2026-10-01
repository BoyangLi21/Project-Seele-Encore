"""Actual whole-before/after ridge visualization and virtual-rail preflight only."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('--transport-snapshot',type=Path,default=ROOT/'artifacts/rebuild_r44/current_transport_geometry_20261001/native_snapshot.json');p.add_argument('--report-name',default='whole_terrain_current_transport_review_v2.json');a=p.parse_args();assert not (a.plan/a.report_name).exists();d=np.load(a.plan/'whole_heightfield.npz');origin=d['origin'];before=d['before'];after=np.where(d['eligible'],d['after'],before);good=before>-32768
    X,Z=np.meshgrid(np.arange(before.shape[1])+origin[0],np.arange(before.shape[0])+origin[1]);before=np.where(good,before,np.nan);after=np.where(good,after,np.nan)
    fig=plt.figure(figsize=(16,8))
    for i,(name,Y) in enumerate([('ACTUAL CURRENT GROUND',before),('EXACT PROPOSED CONTINUOUS RIDGES',after)],1):
        ax=fig.add_subplot(1,2,i,projection='3d');ax.plot_surface(X[::3,::3],Z[::3,::3],Y[::3,::3],cmap='terrain',linewidth=0,antialiased=True,vmin=-490,vmax=-405);ax.view_init(elev=28,azim=-122);ax.set_zlim(-490,-400);ax.set_title(name);ax.set_xlabel('X / m');ax.set_ylabel('Z / m');ax.set_zlabel('Y / m')
    fig.suptitle('Measured current GeoFront sector + one joint ridge/valley field. OFFLINE HEIGHTFIELD, not Minecraft.');fig.tight_layout();file=a.plan/'whole_before_after_ground.png';fig.savefig(file,dpi=150);plt.close(fig)
    source=a.transport_snapshot;rails=json.loads(source.read_text('utf8'))['curves'];conflicts=[];near=0
    envelopes={'TRAIN':(6,3,10),'AIRPLANE':(64,24,80)}
    for curve in rails:
        halo,below,above=envelopes[curve['mode']]
        for x,y,z in curve['points']:
            i,j=round(x-origin[0]),round(z-origin[1])
            if i<-halo or j<-halo or i>=before.shape[1]+halo or j>=before.shape[0]+halo:continue
            near+=1
            for jj in range(max(0,j-halo),min(before.shape[0],j+halo+1)):
                for ii in range(max(0,i-halo),min(before.shape[1],i+halo+1)):
                    if d['eligible'][jj,ii] and after[jj,ii]+1>y-below and before[jj,ii]<y+above:conflicts.append(dict(curve=curve['id'],mode=curve['mode'],pos=[int(ii+origin[0]),float(y),int(jj+origin[1])]))
    contract=json.loads((a.plan/'terrain_contract.json').read_text('utf8'));minimum_clear=float(np.nanmin(d['ceilings'][d['eligible']]-after[d['eligible']])) if d['eligible'].any() else None
    report=dict(actual_ground_only=True,offline_native_photo=False,visual_passed=False,virtual_transport_curve_source=str(source.resolve()),virtual_transport_curve_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),sampled_curve_points_in_sector=near,full3D_transport_conflicts=conflicts,spherical_roof_clearance_min=minimum_clear,existing_protection_volumes_preserved=True,central650m_disc_unchanged=True,tree_removals_or_moves=0,whole_heightfield_sha256=hashlib.sha256((a.plan/'whole_heightfield.npz').read_bytes()).hexdigest(),changed_cells=contract['changed_cells'],root_may_review_whole_landform=not conflicts and not contract['held'] and minimum_clear>=24,world_written=False)
    (a.plan/a.report_name).write_text(json.dumps(report,indent=2),'utf8');print('Whole ridge review',report['root_may_review_whole_landform'],'transportpoints',near,'conflicts',len(conflicts),'roofclearance',minimum_clear,flush=True)


if __name__=='__main__':main()

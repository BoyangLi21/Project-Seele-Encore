"""Resize the authored lake so its submerged apex meets the existing HQ corner."""
from pathlib import Path
import argparse,json
import numpy as np
import survey_r52_original_complex as survey
import regional_voxels as vox
from prepare_continuous_upright_civil_r52 import cuboids
from query_blocks import iter_block_entities

LO=(-285,-552,333);HI=(23,-440,639)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--apply',action='store_true');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    survey.WORLD=a.world;before,names=survey.measure(LO,HI);after=before.copy();ids={n:i for i,n in enumerate(names)}
    def code(s):
        if s not in ids:ids[s]=len(names);names.append(s)
        return ids[s]
    stone=code('minecraft:stone');soil=code('minecraft:dirt');grass=code('minecraft:grass_block[snowy=false]');water=code('minecraft:water[level=0]');black=code('minecraft:black_concrete');floorpanel=code('projectseele:nerv_floor_panel');warm=code('minecraft:ochre_froglight[axis=y]');air=code('minecraft:air')
    yy,zz,xx=np.ogrid[LO[1]:HI[1]+1,LO[2]:HI[2]+1,LO[0]:HI[0]+1]
    footprint=(xx>=-168)&(xx<8)&(zz>=350)&(zz<526)
    # A shared physical point: native west/south corner x=-80,z=438 at y=-544.
    # The floor block below that vertex is y=-545. Water surface remains -472.
    radius=np.maximum(abs(xx+.5+80),abs(zz+.5-438))
    floor=-545+np.floor(np.minimum(radius,88)*68/88).astype(int)
    oldpool=(xx>=-270)&(xx<=7)&(zz>=347)&(zz<=624)
    ordinary={'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:gravel','minecraft:sand','minecraft:water','minecraft:black_concrete','minecraft:ochre_froglight'}
    shell_radius=np.floor(120*(1-(yy+559)/172)+.5);distance=np.maximum(abs(xx-30),abs(zz-327));outside_hq=distance>shell_radius
    empty=np.isin(before,[i for i,n in enumerate(names) if n in {'minecraft:air','minecraft:cave_air','minecraft:void_air'}])
    eligible=(np.isin(before,[i for i,n in enumerate(names) if n.split('[')[0] in ordinary])|(empty&(yy>=-472)))&outside_hq
    # Reclaim only the authored old reservoir. Existing HQ shell and rooms stay.
    reclaim=oldpool&~footprint&(yy<=-468)&eligible
    after[reclaim]=stone;after[reclaim&(yy>=-471)]=soil;after[reclaim&(yy==-468)]=grass
    target=footprint&(yy<=-473)&eligible
    after[target&(yy<=floor)]=black;after[target&(yy>floor)]=water
    # Extend the previously authorized external wet collar below its old limit.
    collar=footprint&empty&outside_hq&(distance<=shell_radius+4)&(yy<=-473)&(yy>floor)
    after[collar]=water
    # Floor-embedded light contours remain below water; no floating curves.
    rings=[]
    for r in (80,57,5):
        ring=footprint&(np.floor(radius)==r)&(yy==floor)&(after==black)
        after[ring]=warm;rings.append(dict(radius=r,cells=int(ring.sum())))
    outer=(xx>=-175)&(xx<=14)&(zz>=343)&(zz<=532)
    bank=outer&~footprint
    bankeligible=(eligible|np.isin(before,[code('projectseele:nerv_floor_panel'),code('projectseele:nerv_machine_edge'),code('projectseele:nerv_hazard_paving')]))&outside_hq
    support=bank&(yy<=-468)&bankeligible
    after[support]=stone;after[support&(yy==-468)]=floorpanel
    # Keep existing external approach roads. Only relocate this pass's lamps
    # and service fittings, by exact previously installed coordinates/states.
    source=a.out.parent/'lakeside350/EXACT_DELTA.json.gz'
    import gzip
    if source.exists():
        rows=json.loads(gzip.decompress(source.read_bytes()))
        for row in rows:
            x,y,z=row['pos']
            if not (LO[0]<=x<=HI[0] and LO[1]<=y<=HI[1] and LO[2]<=z<=HI[2]):continue
            iy,iz,ix=y-LO[1],z-LO[2],x-LO[0]
            if y>-468 and before[iy,iz,ix]==ids.get(row['after']):after[iy,iz,ix]=code(row['before'])
    # Retire the superseded lake bank, keeping intersecting HQ structures.
    oldbank=(xx>=-278)&(xx<=15)&(zz>=339)&(zz<=632)&~oldpool&~outer
    after[oldbank&(yy==-468)&np.isin(before,[floorpanel,code('projectseele:nerv_hazard_paving')])]=grass
    after[oldbank&(yy>-468)&np.isin(before,[i for i,n in enumerate(names) if n.startswith('projectseele:nerv_edge_rail[')])]=air
    # A proper native inner bank guard, with the walking strip behind it.
    for x,z in [(x,z) for x in (-169,8) for z in range(349,527)]+[(x,z) for z in (349,526) for x in range(-168,8)]:
        ix=x-LO[0];iz=z-LO[2]
        if after[-468-LO[1],iz,ix]==floorpanel and after[-467-LO[1],iz,ix]==air:
            state='projectseele:nerv_edge_rail[east=false,north=true,south=true,west=false]' if x in (-169,8) else 'projectseele:nerv_edge_rail[east=true,north=false,south=false,west=true]'
            after[-467-LO[1],iz,ix]=code(state)
    beacons=[]
    for x,z in [(x,z) for x in (-172,11) for z in range(358,526,28)]+[(x,z) for z in (346,529) for x in range(-156,8,28)]:
        ix=x-LO[0];iz=z-LO[2]
        if after[-468-LO[1],iz,ix]!=floorpanel:continue
        if any(after[y-LO[1],iz,ix]!=air for y in (-467,-466,-465)):continue
        for y,state in [(-467,'projectseele:nerv_machine_edge'),(-466,'projectseele:nerv_machine_panel'),(-465,'projectseele:nerv_alert_light[hanging=false,lit=true]')]:after[y-LO[1],iz,ix]=code(state)
        beacons.append([x,-465,z])
    # Rooted crowns also cover the former water area reclaimed by this resize.
    from extend_r53_geofront_forest import tree_template
    rng=np.random.default_rng(362);trees=[];templates=[tree_template(i) for i in range(12)]
    leaves=code('minecraft:oak_leaves[distance=1,persistent=true,waterlogged=false]');log=code('minecraft:oak_log[axis=y]')
    for z in range(353,621,13):
        for x in range(-263,4,13):
            x+=int(rng.integers(-2,3));z1=z+int(rng.integers(-2,3))
            if -182<x<21 and 336<z1<540:continue
            ix=x-LO[0];iz=z1-LO[2]
            if after[-468-LO[1],iz,ix]!=grass:continue
            k=int(rng.integers(0,12));t=templates[k];tx=t[:,0]+ix;ty=t[:,1]-467-LO[1];tz=t[:,2]+iz
            if tx.min()<0 or tx.max()>=after.shape[2] or tz.min()<0 or tz.max()>=after.shape[1]:continue
            if not np.isin(after[ty,tz,tx],[air,leaves]).all():continue
            after[ty,tz,tx]=np.where(t[:,3]==1,log,leaves);trees.append(dict(root=[x,-467,z1],template=k))
    # The lake authorization never includes the original HQ shell or interior.
    protected_hq=~np.broadcast_to(outside_hq,before.shape);after[protected_hq]=before[protected_hq]
    beacons=[p for p in beacons if after[p[1]-LO[1],p[2]-LO[2],p[0]-LO[0]]==code('projectseele:nerv_alert_light[hanging=false,lit=true]')]
    # All original devices, including invisible artwork and railway fixtures.
    for (x,y,z),tag in iter_block_entities(a.world,'projectseele:geofront',LO,HI):
        assert after[y-LO[1],z-LO[2],x-LO[0]]==before[y-LO[1],z-LO[2],x-LO[0]],(x,y,z,str(tag['id']))
    assert np.all(after[~np.broadcast_to(outside_hq,before.shape)]==before[~np.broadcast_to(outside_hq,before.shape)]),'HQ interior changed'
    report=dict(world=str(a.world),old_water_side=276,new_water_side=176,water_surface_y=-472,shared_corner=[-80,-544,438],lake_bounds=[[-168,350],[8,526]],rings=rings,warning_lights=beacons,changed_cells=int((after!=before).sum()),original_hq_shell_preserved=True,reclaimed_ground_trees=trees)
    np.savez_compressed(a.out/'EXACT_BEFORE_AFTER.npz',origin=LO,palette=names,before=before,after=after)
    (a.out/'PLAN.json').write_text(json.dumps(report,indent=2),'utf8')
    if a.apply:
        vox.WORLD=a.world;vox.OUT=a.out;vox.DIM='projectseele:geofront';p=vox.Painter(vertical_bounds=(-1344,320));cuboids(p,LO,before,after,names,'authorized_lake_ratio_and_shared_apex');report['receipt']=p.apply('shared_apex_lake');(a.out/'INSTALLED.json').write_text(json.dumps(report,indent=2),'utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()

"""Remove the two original authored HQ links whose HQ endpoint moved.

The R19 upper_transfer footprint and R28 science_hq_bridge identify the
components. Keep the operating station, ground, and R28 lower research entry.
"""
from pathlib import Path
import argparse,json,numpy as np
import survey_r52_original_complex as survey
import regional_voxels as vox
from survey_facility_target import role_of
from query_blocks import iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',required=True,type=Path)
    ap.add_argument('--world',type=Path)
    ap.add_argument('--apply',action='store_true')
    args=ap.parse_args();base=args.base;world=args.world or base/'CANDIDATE'
    for name,lo,hi,retire in (
        ('old_hq_hangar_link',(111,-467,-10),(125,-432,249),(113,-466,-8,123,-432,247)),
        ('old_research_hq_branch',(142,-467,393),(203,-453,411),(144,-466,395,201,-454,409))):
        survey.WORLD=world;before,names=survey.measure(lo,hi);after=before.copy()
        survey.WORLD=base/'R50_RESTORE/server/SEELE_R50_WORLD';old,oldnames=survey.measure(lo,hi)
        survey.WORLD=base/'WORLD';frozen,fn=survey.measure(lo,hi)
        keys=np.asarray(names);mask=(keys[before]==np.asarray(oldnames)[old])&(keys[before]==np.asarray(fn)[frozen])
        artificial=np.asarray([role_of(s) not in ('air','natural','fluid') and not s.startswith(('minecraft:rail[','minecraft:powered_rail[')) for s in names])
        yy,zz,xx=np.ogrid[:before.shape[0],:before.shape[1],:before.shape[2]]
        y,z,x=yy+lo[1],zz+lo[2],xx+lo[0];a,b,c,d,e,f=retire
        mask &= artificial[before]&(x>=a)&(x<=d)&(y>=b)&(y<=e)&(z>=c)&(z<=f)
        devices=dict(iter_block_entities(world,survey.DIM,lo,hi));retired=[]
        for p,t in devices.items():
            q=(p[1]-lo[1],p[2]-lo[2],p[0]-lo[0])
            if mask[q]:
                assert str(t['id'])=='projectseele:station_departure_board' and bool(t.get('Wayfinding',0)),(p,t)
                retired.append(list(p))
        after[mask]=names.index('minecraft:air')
        if name=='old_hq_hangar_link':
            for state in ('projectseele:nerv_structural_panel','projectseele:nerv_wall_panel','projectseele:clear_glass'):
                if state not in names:names.append(state)
            for y0 in range(-442,-436):
                for x0 in range(113,124):
                    q=(y0-lo[1],-9-lo[2],x0-lo[0]);assert (x0,y0,-9) not in devices
                    material='projectseele:nerv_structural_panel' if y0==-437 or x0 in (113,123) else 'projectseele:nerv_wall_panel'
                    if 114<=x0<=122 and -441<=y0<=-439:material='projectseele:clear_glass'
                    after[q]=names.index(material)
        else:
            for x0 in range(195,198):
                for y0 in range(-466,-462):
                    assert names[int(after[y0-lo[1],410-lo[2],x0-lo[0]])]=='minecraft:air','Retain original lower research entrance'
        changed=int(np.count_nonzero(before!=after));assert changed>0
        out=base/'superseded-hq-links'/world.name/name;out.mkdir(parents=True,exist_ok=True)
        report=dict(component=name,changed_cells=changed,retired_wayfinding=retired,
                    original_ground_retained=True,operating_station_retained=True,original_lower_research_entry_retained=True)
        (out/'PLAN.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps(report),flush=True)
        if args.apply:
            vox.WORLD=world;vox.DIM=survey.DIM;vox.OUT=out
            p=vox.Painter(vertical_bounds=(-1440,320));cuboids(p,lo,before,after,names,name)
            p.meta.update(report);assert not list((out/name).glob('applied_*'));p.apply(name)
            survey.WORLD=world;actual,an=survey.measure(lo,hi)
            assert np.array_equal(np.asarray(an)[actual],np.asarray(names)[after])
            print(name+': complete volume readback passed',flush=True)

if __name__=='__main__':main()

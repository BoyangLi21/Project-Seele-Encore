"""Measured whole city period-architecture ghost, exact current BEFORE/inverse."""
from pathlib import Path
import argparse,gzip,json,math,shutil
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_new_city_blocks_r44 import SOIL,SMALL,PAVING
from regional_voxels import canonical_state
from city_period_architecture_r44 import author,WALLS,complete_shop_front

ROOT=Path(__file__).resolve().parents[1];WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--installed',action='store_true');p.add_argument('--landscape-only',action='store_true');p.add_argument('--shopfront-only',action='store_true');p.add_argument('--ownership',type=Path,action='append',default=[]);a=p.parse_args();assert not a.output.exists()
    district=json.loads((a.source/'new_district.json').read_text('utf8'));x0,x1,z0,z1=district['bounds'];w=MeasuredWorld(WORLD);w.box((x0-16,40,z0-16),(x1+16,220,z1+16));w.load()
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',(x0-16,40,z0-16),(x1+16,220,z1+16),selected_chunks=set(w.selected)))
    read=lambda path:[json.loads(s) for s in gzip.open(path/'forward.jsonl.gz','rt',encoding='utf8')]
    rows=read(a.source);owned={tuple(r['pos']):r for path in a.ownership+[a.source] for r in read(path)}
    target={} if a.installed else {tuple(r['pos']):(r['after'],r.get('after_nbt'),r['owner'],r['reason']) for r in rows}
    held=[]
    def state(q):return target[q][0] if q in target else w.block(q)
    def put(q,s,owner,reason,nbt=None):
        q=tuple(q);actual=w.block(q);name=(actual or '').split('[')[0]
        if actual is None or (q in tags and q not in owned) or (q not in owned and name not in SOIL|SMALL|PAVING|AIR):held.append({'pos':q,'state':actual,'reason':reason});return
        s=canonical_state(s);oldnbt=tags[q].snbt() if q in tags else None
        if s==actual and oldnbt==nbt:target.pop(q,None)
        else:target[q]=(s,nbt,owner,reason)
    # Retire only known authored public exterior plaques and close their old
    # east-facing holes. Individual gallery unit numbers remain intact.
    for q,r in ([] if a.landscape_only or a.shopfront_only else owned.items()):
        st=state(q)
        if st and '_wall_sign[' in st:
            b=next((b for b in district['buildings'] if b['id']==r['owner']),None)
            if b is None or (b['kind']=='gallery_danchi' and b['bounds'][1]<q[2]<b['bounds'][3]):continue
            put(q,'minecraft:air',r['owner'],'Retire the actual authored high/in-wall exterior engineering plaque with exact full NBT inverse')
            if b.get('facing')=='east' and q[0]==b['bounds'][2]:put(q,'minecraft:smooth_sandstone',r['owner'],'Close the old in-wall sign/window hole before mounting the true external entrance plaque')
    protected=set()
    protected_cases_file=a.source/('all_native_cases.json' if a.installed and (a.source/'all_native_cases.json').exists() else 'native_cases.json')
    for c in json.loads(protected_cases_file.read_text('utf8')):
        for start,end in zip(c['path'],c['path'][1:]):
            steps=max(1,math.ceil(math.dist(start,end)*4))
            for i in range(steps+1):
                q=[start[k]+(end[k]-start[k])*i/steps for k in range(3)]
                for xx in range(math.floor(q[0]-.31),math.floor(q[0]+.31)+1):
                    for zz in range(math.floor(q[2]-.31),math.floor(q[2]+.31)+1):
                        for yy in range(math.floor(q[1]),math.ceil(q[1]+1.8)):protected.add((xx,yy,zz))
    street={'hakone_west':'西町','tokyo_north':'北町','kirisato_north':'霧里北'}.get(district['id'],'南町');details=[]
    if a.shopfront_only:
        assert a.installed and district['id']=='hakone_west';shop=next(b for b in district['buildings'] if b['kind']=='local_shop');service=complete_shop_front(shop,state,put);details=[service]
        if not service['service_founded']:held.append(dict(owner=shop['id'],reason='Side service route lacks measured founded bearing',profiles=service['service_bearing']))
    elif not a.landscape_only:
        for i,b in enumerate(district['buildings'],1):details.append(author(b,i,street,state,put,protected))
    else:
        assert a.installed and district['id']=='hakone_west'
        details=json.loads((a.source/'architecture_components.json').read_text('utf8'))['components']
        garden=[];preserved_structures=[];owner=next(b['id'] for b in district['buildings'] if b['kind']=='small_inn')
        def natural_only(q,s,reason):
            actual=w.block(q);name=(actual or '').split('[')[0]
            if name not in SOIL|SMALL|AIR:
                original=owned.get(q);preserved_structures.append(dict(pos=q,state=actual,source_owner=original.get('owner') if original else None,source_role=original.get('reason') if original else None,action='PRESERVED EXACTLY',support_role='Existing authored masonry/retaining footing/cap or facade detail; no material, support, collision or fullNBT changed'))
                return
            put(q,s,owner,reason)
        for xx in range(-1943,-1936):
            for zz in range(481,498):
                g=max([yy for yy in range(40,130) if (w.get(xx,yy,zz) or '').split('[')[0] in SOIL],default=None)
                if g is None or abs(g-104)>8:held.append(dict(pos=[xx,104,zz],ground=g,reason='Shared garden grading must use real restrained8m soil profile'));continue
                for yy in range(min(g+1,102),104):
                    q=(xx,yy,zz)
                    if q not in protected:natural_only(q,'minecraft:stone','Complete shared green-court natural-soil formation; every existing authored masonry footing preserved')
                if (xx,104,zz) not in protected:natural_only((xx,104,zz),'minecraft:grass_block[snowy=false]','Entire shared inn/home garden at realY105 feet, preserving all authored structure/footing/caps')
                for yy in range(105,g+2):
                    q=(xx,yy,zz)
                    if q not in protected and ((w.block(q) or '').split('[')[0] in SOIL|SMALL):put(q,'minecraft:air',owner,'Remove the measured whole high natural soil strip between parcels rather than hide it with decoration')
                garden.append(dict(pos=[xx,zz],native_feet=105,owner=owner,role='Whole measured shared green court; street/door/foundation/old562paths preserved'))
    a.output.mkdir(parents=True)
    final=[dict(pos=q,before=w.block(q),after=s,before_nbt=tags[q].snbt() if q in tags else None,after_nbt=n,owner=o,reason=r) for q,(s,n,o,r) in sorted(target.items())]
    for name,inv in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in final:
                r=dict(row)
                if inv:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                stream.write(json.dumps(r,ensure_ascii=False)+'\n')
    for n in ['new_district.json','native_cases.json','road_authority.json','ecology_reservations.json','parcel_components.json','source_shape_candidates.json']:
        if (a.source/n).exists():shutil.copy2(a.source/n,a.output/n)
    if a.landscape_only:
        parcel=json.loads((a.output/'parcel_components.json').read_text('utf8'));parcel['full_court_columns'].extend(garden)
        (a.output/'parcel_components.json').write_text(json.dumps(parcel,ensure_ascii=False,indent=2),'utf8')
        protection=json.loads((a.output/'ecology_reservations.json').read_text('utf8'));protection['reservations'].append(dict(bounds=[-1943,96,481,-1937,110,497],owner=owner,role='Exact fully regraded shared green court and canopy-free old562 circulation'))
        (a.output/'ecology_reservations.json').write_text(json.dumps(protection,indent=2),'utf8')
        (a.output/'preserved_structural_roles.json').write_text(json.dumps(dict(actual_current_baseline=str(a.source.resolve()),preserved=preserved_structures,non_natural_forward_replacements=0,world_written=False),ensure_ascii=False,indent=2),'utf8')
    if a.installed and not a.shopfront_only and (a.source/'all_native_cases.json').exists():
        shutil.copy2(a.source/'all_native_cases.json',a.output/'inherited_298_native_cases.json')
        basecases=json.loads((a.output/'native_cases.json').read_text('utf8'));identities={c['id'] for c in basecases}
        inherited=json.loads((a.source/'all_native_cases.json').read_text('utf8'))
        for c in inherited:
            if c['id'] not in identities:
                v=dict(c,source_case_id=c['id'],id=c['id']+'/retained_applied_epoch',native_passed=False);basecases.append(v)
        (a.output/'native_cases.json').write_text(json.dumps(basecases,ensure_ascii=False,indent=2),'utf8')
    if a.shopfront_only:
        previous=json.loads((a.source/'all_native_cases.json').read_text('utf8'));kept=[];retired=[]
        # Scans are regenerated from the new actual occupied floor/court;
        # architectural goals and all unaffected public/roof/station ports
        # stay. The old staircase endpoint sat on the future closed glass.
        for c in previous:
            if '/whole_row_' in c['id'] or '/whole_forecourt_row' in c['id'] or '/to_operating_station' in c['id']:
                retired.append(dict(c,classification='Regenerated full occupied floor/court or station journey; same real room/floor/station goal coverage. Shop old geometry scans no longer define an open facade'));continue
            if c['id'].startswith(shop['id']+'/stairs1'):
                forward=c['path'][::-1] if '/return' in c['id'] else c['path'];start=next(i for i,p in enumerate(forward) if p[1]>=shop['floor']+4);tail=forward[start:];revised=service['service_street_route']+tail;v=dict(c,path=revised[::-1] if '/return' in c['id'] else revised,door=service['service_door'],native_passed=False,retired_before_path=c['path'],revision_reason='Real roof goal retained through purposeful west service door; old facade scan point retired');kept.append(v);retired.append(dict(c,classification='Replaced stair access; same real upper roof endpoint, real side street/door replaces old open-shopfront start'));continue
            kept.append(c)
        kept=[c for c in kept if not c['id'].startswith(shop['id']+'/west_service_entry')]
        for suffix,path in [('',service['service_street_route']),('/return',service['service_street_route'][::-1])]:kept.append(dict(id=shop['id']+'/west_service_entry'+suffix,path=path,door=service['service_door'],native_passed=False))
        parcel=json.loads((a.output/'parcel_components.json').read_text('utf8'));existing={tuple(c['pos']) for c in parcel['full_court_columns']}
        parcel['full_court_columns'].extend(dict(pos=p['pos'],native_feet=shop['floor']+1,owner=shop['id'],role='Whole2m side footway and3m front service landing') for p in service['service_bearing'] if tuple(p['pos']) not in existing)
        (a.output/'parcel_components.json').write_text(json.dumps(parcel,indent=2),'utf8')
        (a.output/'native_cases.json').write_text(json.dumps(kept,ensure_ascii=False,indent=2),'utf8')
        (a.output/'case_geometry_revisions.json').write_text(json.dumps(dict(source=str(a.source.resolve()),retired_before=retired,kept_or_replaced_goals=len(kept),all_original_floor_and_roof_goals_preserved=True,world_written=False),ensure_ascii=False,indent=2),'utf8')
    audit=json.loads((a.source/'audit.json').read_text('utf8'));audit.update(changed_cells=len(final),held=held,world_written=False,ready=False,native_passed=False,visual_passed=False,exact_current_repair_only=a.installed)
    (a.output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),'utf8')
    (a.output/'architecture_components.json').write_text(json.dumps({'components':details,'source_helper':'city_period_architecture_r44.py','retained_route_obligations':len(json.loads((a.source/'native_cases.json').read_text('utf8'))),'world_written':False},ensure_ascii=False,indent=2),'utf8')
    if a.installed:
        (a.output/'delta_provenance.json').write_text(json.dumps({'installed':str(a.ownership[0].resolve()),'known_applied_revisions':[str(p.resolve()) for p in a.ownership+[a.source]],'actual_world_only':True,'whole_city_reapply_allowed':False,'world_written':False},indent=2),'utf8')
    print('Period architecture',district['id'],'cells',len(final),'held',len(held),'world unchanged',flush=True)


if __name__=='__main__':main()

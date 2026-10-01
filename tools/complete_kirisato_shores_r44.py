"""Exact dry-bank retaining components and short timber apron abutments.

Actual water voxels are immutable. Every component has a founded, tapered
whole masonry section; boundary guards supplement the structure, not replace it.
"""
from pathlib import Path
from collections import defaultdict
import argparse,gzip,json,math,shutil,hashlib
from measure_world_r40 import MeasuredWorld
from query_blocks import AIR,iter_block_entities
from plan_kirisato_living_ground_r44 import SOIL,PLANTS

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    assert not a.output.exists();a.output.mkdir(parents=True)
    parcels=json.loads((a.plan/'parcel_ground_plan.json').read_text('utf8'));columns={tuple(r['pos']):r for r in parcels['columns']}
    review=json.loads((a.plan/'whole_outer_grade_classification.json').read_text('utf8'))
    edges=[r for r in review['held'] if r['kind']=='HOLD_WATERFRONT_RETAINING_DESIGN_REQUIRED'];assert len(edges)==len(review['held'])
    rows={tuple(r['pos']):r for r in map(json.loads,gzip.open(a.plan/'forward.jsonl.gz','rt',encoding='utf8'))}
    water=json.loads((a.plan/'complete_current_water_landscape.json').read_text('utf8'))
    roads={tuple(r['pos']):r['native_feet']for r in json.loads((a.plan/'road_authority.json').read_text('utf8'))['columns']}
    w=MeasuredWorld(ROOT/'run/saves/SEELE_FIELD_R44_REVIEW');designs=[]
    for edge in edges:
        x,feet,z=edge['pos'];nX,nZ=edge['neighbour_xz'];dx,dz=x-nX,z-nZ
        head=math.ceil(feet)-1;base=min(columns[x,z]['before_ground'],head)-2
        height=max(0,feet-edge['water_surface']);width=max(2,math.ceil(height/3)+1)
        designs.append(dict(id='shore_'+str(len(designs)),edge=edge,base=base,head=head,base_width=width,inward=[dx,dz],cells=[]))
        for depth in range(width):w.box((x+dx*depth,base-2,z+dz*depth),(x+dx*depth,head+2,z+dz*depth))
    # The five-metre timber cross-beam seats on measured dry banks at both ends.
    decks=water['supported_apron_deck_columns'];groups=defaultdict(list)
    for r in decks:groups[r['pos'][1],r['feet']].append(r)
    abutments=[]
    for (z,feet),deck in groups.items():
        xs=sorted(r['pos'][0]for r in deck);assert xs==list(range(xs[0],xs[-1]+1))
        for x in [xs[0]-1,xs[-1]+1]:
            assert (x,z) in columns,('Timber beam needs an owned dry-bank abutment',x,z)
            base=columns[x,z]['before_ground']-2;head=math.ceil(feet)-2
            abutments.append(dict(pos=[x,z],base=base,head=head,deck_span=[xs[0],xs[-1]],feet=feet,cells=[]))
            w.box((x,base-1,z),(x,head+1,z))
    w.load();lo=[min(x*16 for x,z in w.selected),32,min(z*16 for x,z in w.selected)];hi=[max(x*16+15 for x,z in w.selected),159,max(z*16+15 for x,z in w.selected)]
    tags=dict(iter_block_entities(w.world,w.dimension,lo,hi,selected_chunks=set(w.selected)));held=[];touched=set();guards=defaultdict(set)
    def get(q):return rows[q]['after'] if q in rows else w.block(q)
    def put(q,state,component):
        before=w.block(q);current=get(q);name=(current or '').split('[')[0]
        if before is None or q in tags or before.startswith('minecraft:water') or name not in SOIL|PLANTS|AIR|{'minecraft:stone_bricks','minecraft:smooth_stone','minecraft:smooth_stone_slab','minecraft:mossy_stone_bricks','minecraft:polished_andesite'}:
            held.append(dict(pos=q,before=before,planned=current,component=component,reason='Whole dry retaining section meets retained water/fixture/unknown'));return False
        if state=='minecraft:stone_bricks' and current=='minecraft:mossy_stone_bricks':state=current
        if before==state:rows.pop(q,None)
        else:rows[q]=dict(pos=q,before=before,after=state,before_nbt=None,after_nbt=None,owner='r44/kirisato/whole_shore/'+component,reason='Whole founded dry-bank masonry retaining section / load-bearing timber-span abutment. Every actual water voxel remains unchanged.')
        touched.add(q);return True
    for d in designs:
        x,feet,z=d['edge']['pos'];dx,dz=d['inward'];q=x,z
        if columns[q]['role']=='supported_pond_apron_deck':
            d['structural_type']='Timber cross-beam span on two complete dry-bank abutments; no masonry or landfill in the water-bearing deck column'
            d['base_width_actual']=0
        else:
            blocked=[]
            for depth in range(d['base_width']):
                xx,zz=x+dx*depth,z+dz*depth
                if (xx,zz) not in columns and (xx,zz) not in roads:blocked.append([xx,zz]);continue
                if any((w.block((xx,y,zz))or'').startswith('minecraft:water') for y in range(d['base'],d['head']-depth*2)):blocked.append([xx,zz])
            # A curved wet shore may not have a dry gravity-wall footprint.
            # Use a keyed reinforced facing against the complete authored
            # earth bank there; do not project its footing into the pond.
            d['structural_type']='Keyed reinforced masonry facing of complete founded earthen bank' if blocked else 'Tapered gravity masonry retaining section'
            d['gravity_footprint_contacts']=blocked;d['base_width_actual']=1 if blocked else d['base_width']
            water_y=[y for y in range(d['base'],d['head']+1)if (w.block((x,y,z))or'').startswith('minecraft:water')]
            if water_y:d['base']=max(d['base'],max(water_y)+2);d['retained_aquifer_below_footing']=water_y
        for depth in range(d['base_width_actual']):
            xx,zz=x+dx*depth,z+dz*depth
            if (xx,zz) not in columns and (xx,zz) not in roads:
                held.append(dict(pos=[xx,zz],component=d['id'],reason='Full retaining base exceeds known positive dry parcel authority'));continue
            # A gravity section tapers inboard: full-height face, then a lower
            # backing mass. Native soil remains above the backing wedge.
            head=d['head']-1-depth*2
            if (xx,zz) in roads:head=min(head,math.floor(roads[xx,zz])-2)
            for y in range(d['base'],head+1):
                st='minecraft:mossy_stone_bricks' if depth==0 and y<=d['edge']['water_surface']+1 else 'minecraft:stone_bricks'
                pos=xx,y,zz
                if put(pos,st,d['id']):d['cells'].append(dict(pos=pos,after=st))
        bearing=get((x,d['base']-1,z));d['complete_candidate_bearing_state']=bearing;d['actual_before_bearing_state']=w.block((x,d['base']-1,z))
        if d['base_width_actual'] and (bearing is None or bearing.split('[')[0] not in SOIL|{'minecraft:stone_bricks','minecraft:smooth_stone'}):held.append(dict(component=d['id'],reason='Retaining footing lacks full candidate solid bearing',state=bearing))
        if not columns[q]['role'].startswith('graded_'):
            direction={(1,0):'east',(-1,0):'west',(0,1):'south',(0,-1):'north'}[(-dx,-dz)]
            guards[x,math.ceil(feet),z].add(direction)
    for d in abutments:
        x,z=d['pos']
        for y in range(d['base'],d['head']+1):
            if put((x,y,z),'minecraft:stone_bricks','timber_apron_abutment'):d['cells'].append(dict(pos=[x,y,z],after='minecraft:stone_bricks'))
        d['measured_bearing_state']=w.block((x,d['base']-1,z))
        if (d['measured_bearing_state']or'').split('[')[0] not in SOIL:held.append(dict(component='timber_abutment',pos=[x,z],reason='No actual soil bearing'))
    for q,sides in guards.items():
        before=w.block(q);current=get(q)
        if before is None or q in tags or (current or'').split('[')[0] not in AIR|PLANTS:
            held.append(dict(pos=q,component='shore_guard',state=current,reason='Shore boundary guard meets retained component'));continue
        state='projectseele:nerv_edge_rail['+','.join(k+'='+str(k in sides).lower()for k in ['east','north','south','west'])+']'
        rows[q]=dict(pos=q,before=before,after=state,before_nbt=None,after_nbt=None,owner='r44/kirisato/whole_shore/public_boundary_guard',reason='Thin existing native boundary rail along the actual water-facing edge of a fully founded terrace; public walking centre remains open')
    # Multiple perpendicular sections share corner masonry. Moist exposed
    # faces take precedence over dry backing finish; freeze the assembled
    # joint states, rather than stale per-section pre-composition colours.
    joined=0
    for d in designs+abutments:
        for c in d['cells']:
            final=get(tuple(c['pos']));assert final in {'minecraft:stone_bricks','minecraft:mossy_stone_bricks'}
            if c['after']!=final:joined+=1;c['after']=final
    assert not any(r['before'].startswith('minecraft:water')for r in rows.values())
    for name,inverse in [('forward',False),('inverse',True)]:
        with gzip.open(a.output/(name+'.jsonl.gz'),'wt',encoding='utf8')as f:
            for q,row in sorted(rows.items()):
                r=dict(row)
                if inverse:r['before'],r['after']=row['after'],row['before'];r['before_nbt'],r['after_nbt']=row['after_nbt'],row['before_nbt']
                f.write(json.dumps(r,ensure_ascii=False)+'\n')
    for name in ['new_district.json','road_authority.json','native_cases.json','parcel_components.json','parcel_ground_plan.json','complete_current_water_landscape.json','public_grade_composition.json']:shutil.copy2(a.plan/name,a.output/name)
    report=dict(source=str(a.plan.resolve()),changed_cells=len(rows),held=held,complete_retaining_sections=designs,timber_abutments=abutments,joined_masonry_finish_declarations=joined,
        public_boundary_guards=[dict(pos=q,sides=sorted(v))for q,v in guards.items()],all_actual_water_preserved=True,world_written=False,native_passed=False,visual_passed=False,
        engineering_inference='Whole founded earthen bank receives a two-metre keyed tapered masonry section where the dry base fits. Curved wet shores use a one-metre reinforced facing keyed onto measured contiguous solid soil/rock above any preserved aquifer, with the complete authored earth bank behind it. No gravity footing is silently clipped into water. Timber apron five-metre beam seats on two dry-bank masonry abutments. TV-period Japanese residential embankment interpretation; game metre choices are engineering inference.',
        producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (a.output/'whole_waterfront_components.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
    print('Whole founded shores:',len(designs),'sections;',len(abutments),'timber abutments;',len(guards),'boundary guards;',len(rows),'cells;',len(held),'held; NO WORLD WRITE',flush=True)

if __name__=='__main__':main()

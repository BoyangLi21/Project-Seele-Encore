"""Author only Root's current nine ascent bores from complete source envelopes.

The current original city well, gate proxy cells and unrelated authored
structures remain separate owners. No failed R52 after-state is imported.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import argparse,gzip,hashlib,json,msvcrt
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
import regional_voxels as vox
import extend_world_depth_r52 as extension
from query_blocks import iter_selected_sections,iter_block_entities
from prepare_continuous_upright_civil_r52 import cuboids,xyz_for
from build_continuous_upright_directory_r52 import sample


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--measurement',type=Path,required=True);ap.add_argument('--directory',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--apply',action='store_true')
    ap.add_argument('--head-edge-expansion',action='store_true');args=ap.parse_args()
    base=args.base.resolve();world=base/'WORLD';out=args.output.resolve()
    assert out.is_relative_to(base) and not out.is_relative_to(world)
    assert not (out/'APPLIED.json').exists()
    contract=json.loads((base/'ROOT_SPATIAL_PLAN.json').read_text('utf8'))
    assert contract['epoch']==53 and contract['delivery_scope']['id']=='scope124'
    directory=json.loads(args.directory.read_text('utf8'))
    source=np.load(args.measurement/'MEASURED_SOURCE.npz')
    measured=json.loads((args.measurement/'MEASURED_REPORT.json').read_text('utf8'))
    assert measured['directory_sha256']==hashlib.sha256(args.directory.read_bytes()).hexdigest()
    assert measured['measured_legs']=='all_actual_forward_continuous_legs'
    assert measured['measured_height_range_m']==([-5.,-3.] if args.head_edge_expansion else None)
    keys=[tuple(map(int,k)) for k in source['section_keys']];names=list(map(str,source['palette']))
    codes={s:i for i,s in enumerate(names)}
    def code(state):
        if state not in codes:codes[state]=len(names);names.append(state)
        return codes[state]
    air=code('minecraft:air');panel=code('projectseele:nerv_shaft_panel')
    edge=code('projectseele:nerv_machine_edge');lamp=code('projectseele:nerv_strip_light[lit=true]')
    natural={'minecraft:stone','minecraft:deepslate','minecraft:deepslate[axis=y]',
             'minecraft:bedrock','minecraft:dirt','minecraft:grass_block[snowy=false]',
             'minecraft:gravel','minecraft:sand','minecraft:andesite','minecraft:diorite','minecraft:granite',
             'minecraft:tuff','minecraft:coal_ore','minecraft:iron_ore','minecraft:copper_ore',
             'minecraft:deepslate_coal_ore','minecraft:deepslate_iron_ore','minecraft:deepslate_copper_ore'}
    natural_ids={i for i,s in enumerate(names) if s in natural}
    air_ids={i for i,s in enumerate(names) if s in ('minecraft:air','minecraft:cave_air','minecraft:void_air')}
    authored_bank_ids={i for i,s in enumerate(names) if s.startswith('projectseele:nerv_') or s in ('minecraft:light_gray_concrete','minecraft:gray_concrete','minecraft:black_concrete','minecraft:iron_block','minecraft:polished_basalt[axis=y]','minecraft:sea_lantern','minecraft:ladder[facing=south,waterlogged=false]')}
    selected=defaultdict(set)
    for cx,cz,sy in keys:selected[cx,cz].add(sy)
    lo=np.min(np.array(keys)[:,[0,2,1]]*16,axis=0);hi=np.max(np.array(keys)[:,[0,2,1]]*16+15,axis=0)
    devices={tuple(q) for q,_ in iter_block_entities(world,'projectseele:geofront',tuple(map(int,lo)),tuple(map(int,hi)),selected_chunks=selected)}
    device_slots=defaultdict(list)
    for x,y,z in devices:device_slots[x//16,z//16,y//16].append((y%16)*256+(z%16)*16+x%16)
    rows=[];distances=[]
    for leg in directory['legs']:
        if 'centre_curve' not in leg or leg['id'].endswith('/reverse'):continue
        points=np.concatenate([sample(s['controls'],max(3,int(np.ceil(np.linalg.norm(np.ptp(s['controls'],axis=0))*2))+1)) for s in leg['centre_curve']['segments']])
        travel=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        rows.append(points+[0,25,0]);distances.append(travel)
    centre=np.concatenate(rows);along=np.concatenate(distances);tree=cKDTree(centre)
    before=source['before'];core_rows=source['core'];shell_rows=source['shell'];bank_rows=source['banks']
    prior_lining={};prior_states={};support_slots=defaultdict(list)
    if args.head_edge_expansion:
        old_path=base/'phased_routes/final68_ascent_civil/CIVIL_CANDIDATE.npz'
        old_source=np.load(old_path);old_before=old_source['before'];old_after=old_source['after'];old_palette=list(map(str,old_source['palette']))
        old_ids=[j for j,s in enumerate(old_palette) if s in ('projectseele:nerv_shaft_panel','projectseele:nerv_machine_edge','projectseele:nerv_strip_light[lit=true]')]
        for j,k in enumerate(old_source['section_keys']):
            key=tuple(map(int,k));prior_lining[key]=(old_before[j]!=old_after[j])&np.isin(old_after[j],old_ids);prior_states[key]=old_after[j]
        from pathlib import Path as _Path
        gate_path=_Path(__file__).resolve().parents[1]/'.Codex/map_complete_20261013/route_audit/final_gate_native_readback/rebound_current/ROOT_TYPED_GATES_CANDIDATE.json'
        for g in json.loads(gate_path.read_text('utf8'))['gates']:
            for s in g['supports']:
                x,y,z=s['position'];support_slots[x//16,z//16,y//16].append((y%16)*256+(z%16)*16+x%16)
    after=before.copy();foreign=[];protected=Counter();changed_material=Counter()
    for i,key in enumerate(keys):
        xyz=xyz_for(key);x,y,z=xyz.T;old=before[i];core=core_rows[i];shell=shell_rows[i];banks=bank_rows[i]
        active=shell & (((banks&1)!=0)&(y<=-467) | ((banks&2)!=0)&(y<=80) | ((banks&4)!=0)&(y<=174))
        # Explicit newly rebuilt bank roof ownership, not inferred from air.
        bank_roof=(y>=-956)&(y<=-930)&(x>=-31)&(x<=91)&(z>=9)&(z<=147)
        # Exact positive ownership from relocate_regional_eva.geometry:
        # eva/new_foundation, eva/new_plinth north side and eva/new_apron.
        # Only their intersection with the authored new connecting bore is
        # replaced; the retained laboratory and its access remain protected.
        old_base=(x>=-55)&(x<=162)&(z>=-150)&(z<=14)&(y>=-512)&(y<=-506)
        old_north_plinth=(x>=-46)&(x<=110)&(z>=-7)&(z<=14)&(y>=-505)&(y<=-444)
        old_north_apron=(x>=-46)&(x<=110)&(z>=-7)&(z<=14)&(y==-443)
        owned_plinth=((old_base|old_north_plinth)&(old==codes.get('minecraft:deepslate_bricks',-1))) | (old_north_apron&(old==codes.get('minecraft:polished_deepslate',-1)))
        # The preserved original well's lower shell is the explicitly chosen
        # bank-two junction. It is not a generic room/air clearance mask.
        old_lower_well=(x>=-30)&(x<=90)&(z>=-54)&(z<=-17)&(y>=-500)&(y<=-411)
        new_geofront_apron=(x>=-31)&(x<=91)&(z>=100)&(z<=148)&(y>=-469)&(y<=-467)
        # Keep the original city shaft and equipment; only its own separate
        # gate and exact native-intersection patches may later change it.
        city_well=(y>=-410)&(x>=-54)&(x<=110)&(z>=-58)&(z<=-15)
        pyramid=(x>=-90)&(x<=150)&(z>=207)&(z<=447)&(y>=-563)&(y<=-384)
        original_hangar=(x>=-54)&(x<=108)&(z>=280)&(z<=375)&(y>=-1136)&(y<=-930)
        original_loading_banks=(y<-956)&(x>=-54)&(x<=108)&(z>=9)&(z<=148)
        retained_laboratory=(y>=-490)&(z>=-190)&(z<=-55)&(x>=-54)&(x<=110)
        retained_compact_access=(x>=89)&(z>=-56)&(z<=-46)
        retained_west_edge=(x==-30)&(y==-444)&((z==-41)|(z==-40))
        # Preserve the old well's outer operating rim. Thirteen cells enter
        # the deliberately padded convex construction hull, so their actual
        # triangle clearance stays an explicit admission check after lining.
        # A construction margin cannot authorize cutting its walking deck.
        retained_operating_rim=(x>=-31)&(x<=91)&(y>=-444)&(y<=-411)&(z>=-16)&(z<=-6)
        unrelated=pyramid|original_hangar|city_well|original_loading_banks|retained_laboratory|retained_compact_access|retained_west_edge|retained_operating_rim
        barriers=np.isin(old,[j for j,s in enumerate(names) if s=='minecraft:barrier'])
        valid=np.isin(old,list(natural_ids|air_ids)) | owned_plinth | ((bank_roof|old_lower_well|new_geofront_apron)&np.isin(old,list(authored_bank_ids)))
        keep=unrelated|barriers
        if args.head_edge_expansion:
            current_lining=prior_lining.get(key,np.zeros(4096,bool))
            # Only positively owned existing lining and the original authored
            # bank component can be let out for the new physical head corners.
            valid|=current_lining|(original_loading_banks&np.isin(old,list(authored_bank_ids)))
            keep&=~original_loading_banks
            keep|=barriers|np.array([names[int(v)] in ("projectseele:clear_glass","minecraft:light_gray_stained_glass","minecraft:smooth_stone_slab[type=bottom,waterlogged=false]") or names[int(v)].startswith("projectseele:nerv_warning_beacon") for v in old])
            keep[support_slots.get(key,[])]=True
            # The measured head does not reach these six original Hakone
            # hatch bearings; only the padded construction envelope does.
            keep|=np.isin(x,[-1147,-1267,-1387])&np.isin(y,[169,170])&(z==-1505)
        keep[device_slots.get(key,[])]=True
        unknown=active&~valid&~keep
        if args.head_edge_expansion:unknown&=core
        for j in np.flatnonzero(unknown):
            foreign.append(dict(position=xyz[j].tolist(),state=names[int(old[j])],core=bool(core[j]),bank_roof=bool(bank_roof[j])))
        for value,count in zip(*np.unique(old[active&keep],return_counts=True)):protected[names[int(value)]]+=int(count)
        edit=active&valid&~keep
        after[i][edit&core]=air
        ring=edit&~core
        if args.head_edge_expansion:ring&=~np.isin(old,list(air_ids))
        after[i][ring]=panel
        where=np.flatnonzero(ring)
        if len(where):
            _,nearest=tree.query(xyz[where]+.5)
            rib=np.mod(along[nearest],24)<1.15
            after[i][where[rib]]=edge
            # Every fourth rib carries sparse embedded lamps on the shell.
            lights=(np.mod(along[nearest],96)<1.15)&(np.mod(y[where],12)==1)
            after[i][where[lights]]=lamp
        changed=old!=after[i]
        for value,count in zip(*np.unique(old[changed],return_counts=True)):changed_material[names[int(value)]]+=int(count)
        if i%1000==0:print('planned sections',i,'/',len(keys),'foreign',len(foreign),flush=True)
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'CIVIL_CANDIDATE.npz',section_keys=np.array(keys,np.int32),before=before,after=after,palette=names)
    (out/'UNCLASSIFIED_CURRENT_CELLS.json.gz').write_bytes(gzip.compress(json.dumps(foreign,separators=(',',':')).encode(),mtime=0))
    report=dict(world_written=False,root_author=True,directory_sha256=measured['directory_sha256'],hulls_sha256=measured['hulls_sha256'],
                candidate_sha256=hashlib.sha256((out/'CIVIL_CANDIDATE.npz').read_bytes()).hexdigest(),
                changed_cells=int(np.count_nonzero(before!=after)),sections=len(keys),foreign_current_cells=len(foreign),
                changed_materials=changed_material,retained_original_or_gate_cells=protected,original_devices=len(devices),
                body_clearance_and_fixed_steel_admission=False,head_edge_expansion=args.head_edge_expansion,
                unchanged_original_body_bands_preserved=args.head_edge_expansion)
    (out/'CANDIDATE.json').write_text(json.dumps(report,indent=2),'utf8');print(json.dumps(report),flush=True)
    if not args.apply:return
    assert not foreign,'Unclassified current material requires Root ownership review'
    vox.WORLD=extension.WORLD=world;vox.OUT=out;vox.DIM='projectseele:geofront';painter=vox.Painter(vertical_bounds=(-1344,320))
    for i,(cx,cz,sy) in enumerate(keys):
        if np.any(before[i]!=after[i]):cuboids(painter,(cx*16,sy*16,cz*16),before[i].reshape(16,16,16),after[i].reshape(16,16,16),names,'root_current_nine_monotone_ascent_bores')
    painter.meta.update(report);painter.save_plan('nine_monotone_ascent_bores')
    lock=extension.acquire_world_lock()
    try:
        receipt=painter.apply('nine_monotone_ascent_bores',session_lock=lock)
        indexes={key:i for i,key in enumerate(keys)};read=0
        for cx,cz,sy,palette,values in iter_selected_sections(world,vox.DIM,selected):
            actual=np.array([codes[s] for s in palette])[values];assert np.array_equal(actual,after[indexes[cx,cz,sy]])
            read+=1
        assert read==len(keys)
        report.update(world_written=True,full_selected_sections_read_back=read,receipt=receipt)
        (out/'APPLIED.json').write_text(json.dumps(report,indent=2),'utf8')
    finally:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()

"""Real-source RAM roundtrip and narrow admission negative controls; no world write."""
from pathlib import Path
import copy,json,sqlite3,sys
sys.dont_write_bytecode=True
import nbtlib,numpy as np
import compose_r45_candidate_v5 as v5

def main():
    out=v5.OWN/'verification_v1';assert not out.exists();out.mkdir()
    catalog=v5.read(v5.CATALOG);core=v5.load_core(catalog);policy=core.Policy()
    before=v5.check_source(policy,catalog);context=v5.contract_context(policy,catalog);policy.v5_contract=context;codec=context[-1]
    db=sqlite3.connect('file:'+str(v5.OWN/'runs/dry_source_v1/cells.sqlite')+'?mode=ro',uri=True)
    states={v:i for i,(v,)in enumerate(db.execute('SELECT b AS s FROM cells UNION SELECT a FROM cells'))};reverse={v:k for k,v in states.items()}
    counts=dict(chunks=0,rows=0,before_BE=0,after_BE=0,full_nonlight_NBT_guard_roundtrips=0,complete_semantic_sections_roundtripped=0,complete_BE_roundtrips=0);first_change=None;first_root=None;first_states=None
    for rx,rz in db.execute('SELECT DISTINCT rx,rz FROM cells ORDER BY rx,rz'):
        path=codec.q.dimension_dir(v5.SOURCE,catalog['dimension'])/'region'/f'r.{rx}.{rz}.mca';blobs=codec.read_region(path)[1]
        for cx,cz in db.execute('SELECT DISTINCT cx,cz FROM cells WHERE rx=? AND rz=? ORDER BY cx,cz',(rx,rz)):
            changes=[(sy,off,states[b],states[a],bn,an)for sy,off,b,a,bn,an in db.execute('SELECT sy,off,b,a,bn,an FROM cells WHERE cx=? AND cz=? ORDER BY sy,off',(cx,cz))]
            root=codec.parse_chunk(blobs[(cx&31)+(cz&31)*32]);projected=copy.deepcopy(root)
            codec.mutate_chunk(projected,changes,reverse,False);v5.validate_after_chunk(projected,context,codec)
            counts['before_BE']+=len(codec.block_tags(root));counts['after_BE']+=len(codec.block_tags(projected))
            inverse=[(sy,off,a,b,an,bn)for sy,off,b,a,bn,an in changes];codec.mutate_chunk(projected,inverse,reverse,False)
            assert codec.chunk_guard_hash(root,changes,False)==codec.chunk_guard_hash(projected,changes,False)
            assert codec.block_tags(root)==codec.block_tags(projected)
            for sec in root['sections']:
                sy=int(sec['Y']);old=codec.measured_section(root,sy);new=codec.measured_section(projected,sy)
                if old is None:assert new is None
                else:assert np.array_equal(np.asarray(old[0])[old[1]],np.asarray(new[0])[new[1]])
                counts['complete_semantic_sections_roundtripped']+=1
            counts['chunks']+=1;counts['rows']+=len(changes);counts['full_nonlight_NBT_guard_roundtrips']+=1;counts['complete_BE_roundtrips']+=len(codec.block_tags(root))
            if first_change is None and changes[0][2]!=changes[0][3]:first_change=changes;first_root=root;first_states=reverse
    db.close();assert counts['rows']==631 and counts['before_BE']-counts['after_BE']==8
    negatives=[]
    def reject(name,fn):
        try:fn()
        except (RuntimeError,ValueError,OSError,AssertionError)as exc:negatives.append(dict(name=name,rejected=True,reason=str(exc)))
        else:raise AssertionError('Negative control unexpectedly accepted '+name)
    repairs=v5.read(v5.OWN/'reviewed_be_repairs9.json');migration=next(r for r in repairs if r['after_nbt'] is not None);retired=next(r for r in repairs if r['after_nbt'] is None)
    def validate_row(row,component):
        _,_,_,_,_,_,b,a,bn,an,_=codec.cell(row,catalog['dimension']);v5.validate_cell_contract(policy,catalog,dict(id=component),row,b,a,bn,an)
    changed=copy.deepcopy(retired);tag=nbtlib.parse_nbt(changed['before_nbt']);tag['is_waxed']=nbtlib.Byte(0);changed['before_nbt']=tag.snbt()
    reject('changed_complete_retired_before_NBT',lambda:validate_row(changed,'retired_fixture_be8'))
    changed2=copy.deepcopy(migration);tag=nbtlib.parse_nbt(changed2['after_nbt']);tag['id']=nbtlib.String('minecraft:sign');changed2['after_nbt']=tag.snbt()
    reject('wrong_after_native_type',lambda:validate_row(changed2,'device_physical25'))
    reject('nine_component_owner_does_not_allow_invalid_before_elsewhere',lambda:validate_row(dict(retired,pos=[-1953,107,492]),'retired_fixture_be8'))
    reject('unreviewed_before_relation_rejected',lambda:validate_row(retired,'registered_stairs243'))
    changed3=copy.deepcopy(retired);changed3['after']='minecraft:air'
    reject('retirement_permission_does_not_allow_block_geometry_change',lambda:validate_row(changed3,'retired_fixture_be8'))
    wrong_before=list(first_change);sy,off,b,a,bn,an=wrong_before[0];wrong_before[0]=(sy,off,a,b,bn,an)
    reject('actual_full_chunk_wrong_before_rejected',lambda:codec.validate_chunk(first_root,wrong_before,first_states))
    reject('QA_world_is_not_a_candidate_target',lambda:policy.new_candidate(v5.ART/'native_facility_session_v1/gameDir/saves/SEELE_FIELD_R45_REVIEW'))
    reject('immutable_source_cannot_be_reused_or_overwritten',lambda:policy.new_candidate(v5.SOURCE.parent))
    reject('derived_level_dat_overwrite_forbidden',lambda:policy.relative('level.dat'))
    reject('derived_region_copy_forbidden',lambda:policy.relative('dimensions/projectseele/geofront/region/r.0.0.mca'))
    reject('existing_progress_archive_not_generic_metadata',lambda:core.stage_files(policy,dict(allowed_file_targets=[v5.IDENTITY]),[dict(id='route_sign_be1',files=[dict(target=v5.IDENTITY,kind='STATIC_SEMANTIC_METADATA')])],before))
    # Complete stage algorithm must reject an overlapping noncontiguous chain.
    rows=list(core.row_stream(v5.OWN/'forward631.jsonl.gz'));sample=next(r for r in rows if r['component']=='registered_stairs243');collision=dict(sample,after='minecraft:air' if sample['after']!='minecraft:air' else 'projectseele:nerv_floor_panel')
    for name,row in [('overlap1',sample),('overlap2',collision)]:
        with (out/(name+'.jsonl')).open('w',encoding='utf8',newline='\n')as f:f.write(json.dumps(row)+'\n')
        inv=dict(row,before=row['after'],after=row['before'],before_nbt=row['after_nbt'],after_nbt=row['before_nbt'])
        with (out/(name+'.inverse.jsonl')).open('w',encoding='utf8',newline='\n')as f:f.write(json.dumps(inv)+'\n')
    components=[dict(id='registered_stairs243',owner_prefixes=[sample['owner']],patches=[dict(forward=dict(path=str(out/(name+'.jsonl')),sha256=v5.sha(out/(name+'.jsonl'))),inverse=dict(path=str(out/(name+'.inverse.jsonl')),sha256=v5.sha(out/(name+'.inverse.jsonl'))),rows=1)])for name in ['overlap1','overlap2']]
    overlap_report=out/'overlap_report';overlap_report.mkdir();overlap_db=sqlite3.connect(overlap_report/'cells.sqlite')
    reject('noncontiguous_overlap_holds_whole_batch_before_copy',lambda:core.stage_cells(policy,catalog,components,overlap_report,codec,overlap_db))
    assert v5.inventory(v5.SOURCE)==before
    report=dict(scope='IMMUTABLE_SOURCE_READ_AND_RAM_ONLY',catalog_sha256=v5.sha(v5.CATALOG),world_written=False,new_world_created=False,Java_MC_started=False,source1736_before_after_equal=True,actual_replacement_BE8_full_preimages_checked=True,forward_inverse631=counts,negative_controls=negatives,native_tick=False,new_structure_native=False,visual_accepted=False)
    core.durable(out/'verification.json',report);print(json.dumps(report,ensure_ascii=True,indent=2))
if __name__=='__main__':main()

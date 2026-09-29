"""Stage only applied R43 receipts over the owner's preserved R42 progress."""
from pathlib import Path
import copy,gzip,hashlib,json,shutil
import nbtlib
import compose_world_r40 as prior
import regional_voxels as v
from release_combat_r36 import guard

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/repair_r43';SOURCE=ART/'source_world_backup';REVIEW=ROOT/'run/saves/SEELE_FIELD_R43_REVIEW';OUT=ART/'world_composition';DEST=OUT/'ready/SEELE_R43_STAGE_WORLD'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    guard();OUT.mkdir(exist_ok=True);assert not DEST.exists(),'Never replace a release world'
    baseline=json.loads((ART/'baseline.json').read_text());owner=Path(baseline['source'])
    for name,digest in baseline['files'].items():assert sha(owner/name)==digest,('Owner progress changed; rebase before packaging',name)
    prior.ART=ART;prior.SOURCE=SOURCE;prior.REVIEW=REVIEW;prior.OUT=OUT
    receipts,cells,tags,conflicts=prior.inventory();measured=prior.states(SOURCE,set(cells)|set(tags))
    conflicts += [dict(kind='baseline',pos=q,expected=b,actual=measured.get(q)) for q,(b,a) in cells.items() if measured.get(q)!=b]
    report=dict(receipts=[str(r) for r in receipts],unique_cells=len(cells),changed_cells=sum(a!=b for b,a in cells.values()),nbt_records=len(tags),conflicts=conflicts,source=str(owner),scope='User-requested interim acceptance; global R43 remains unfinished')
    (OUT/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');assert not conflicts,conflicts[:5]
    positions=set(cells)|set(tags);owner_tags=prior.entities(SOURCE,positions);review_tags=prior.entities(REVIEW,positions);fields=[]
    v.WORLD=DEST;v.OUT=OUT;p=v.Painter();changed={q:(b,a) for q,(b,a) in cells.items() if b!=a}
    for q,(before,after) in sorted(changed.items()):
        p.match((*q,*q),before,after,'r43_stage/applied_static_receipts')
        row=tags.get(q)
        if row is not None:
            if row['after']:p.block_entities[q]=nbtlib.parse_nbt(row['after'])
        elif q in review_tags:
            assert q not in owner_tags or str(owner_tags[q].get('id')) in ('projectseele:station_departure_board','minecraft:sign','mtr:apg_door'),('Unexpected device replacement',q)
            p.block_entities[q]=copy.deepcopy(review_tags[q])
    for q,row in tags.items():
        if q in changed:continue
        old=nbtlib.parse_nbt(row['before']) if row['before'] else nbtlib.Compound()
        new=nbtlib.parse_nbt(row['after']) if row['after'] else nbtlib.Compound();original=owner_tags.get(q);merged=copy.deepcopy(original) if original is not None else nbtlib.Compound()
        names=prior.changed_fields(old,new)
        for name in names:
            assert original is None or original.get(name)==old.get(name),('Owner NBT field conflict',q,name)
            if name in new:merged[name]=copy.deepcopy(new[name])
            else:merged.pop(name,None)
        if original is None:merged=copy.deepcopy(new)
        p.update_block_entity(q,measured[q],original,merged,'r43_stage/explicit_derived_nbt');fields.append(dict(pos=q,fields=sorted(names)))
    shutil.copytree(SOURCE,DEST);p.meta.update(source=str(owner),preserved='Original player/entity/mission/MTR progress; no review-world progress copied',receipts=report['receipts'],nbt_fields=fields);p.apply('static_world')
    metadata=['regional_states.json','native_collision_shapes.json','quality_walk_cases.json','retired_wet_cell_walks_r43.json','platform_interfaces_r43.json']
    for name in metadata:
        assert (REVIEW/name).exists(),name;shutil.copy2(REVIEW/name,DEST/name)
    level=nbtlib.load(DEST/'level.dat');original=copy.deepcopy(level['Data']);level['Data']['LevelName']=nbtlib.String('Project SEELE R43 阶段验收');level.save()
    check=nbtlib.load(DEST/'level.dat')['Data'];check['LevelName']=original['LevelName'];assert check.snbt()==original.snbt()
    actual=prior.states(DEST,set(changed));assert all(actual[q]==a for q,(_,a) in changed.items())
    allowed=set(metadata)|{'level.dat'};preserved=0
    for file in SOURCE.rglob('*'):
        if not file.is_file():continue
        name=file.relative_to(SOURCE).as_posix()
        if name in allowed or name.startswith('dimensions/projectseele/geofront/region/'):continue
        assert sha(file)==sha(DEST/name),('Unrelated owner file changed',name);preserved+=1
    report.update(destination=str(DEST),preserved_files=preserved,derived_metadata=metadata,nbt_fields=fields,world_progress_from=str(owner),new_antechamber_openings_included=False)
    (OUT/'composed.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8');print('Composed stage',report['changed_cells'],'static cells,',preserved,'unrelated files preserved',flush=True)

if __name__=='__main__':main()

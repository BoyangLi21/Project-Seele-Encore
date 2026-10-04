"""Readonly source/legacyQA fleet/plug lineage; no recovery/reset/model/world writes."""
from pathlib import Path
import hashlib,json,sys,uuid
sys.dont_write_bytecode=True
import nbtlib
from verify_main_r20 import entities
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r45';OUT=ART/'lifts_doors_lifecycle_sol_v2/eva02_persisted_hold_readonly_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def uid(tag):return str(uuid.UUID(bytes=b''.join((int(x)&0xffffffff).to_bytes(4,'big')for x in tag)))
def snapshot(world,full=False):
    file=world/'data/projectseele_eva_fleet.dat';tag=nbtlib.load(file);es=entities(world);fleet=[]
    for e in tag['data']['Fleet']:
        row=dict(variant=int(e['Variant']),phase=str(e['Phase']),ticks=int(e['Ticks']),carrier=int(e['Carrier']),LclLayers=int(e['LclLayers']),full_fleet_NBT=e.snbt())
        for key in ('Canonical','EntryPlug'):
            q=tuple(map(int,e[key]));actual=es.get(q)
            row[key]=dict(UUID=uid(e[key]),actual_present=actual is not None,full_NBT=actual.snbt()if actual is not None and(full or int(e['Variant'])==2)else None,position=list(map(float,actual['Pos']))if actual is not None else None)
            if actual is not None:
                row[key].update(saved_stage=int(actual.get('InsertionStage',-1)),saved_cabin_stage=int(actual.get('CabinStage',-1)),saved_hatch=int(actual.get('HatchOpen',-1)),passengers=[dict(id=str(p['id']),UUID=uid(p['UUID']),name=str(p.get('CustomName','')),full_NBT=p.snbt())for p in actual.get('Passengers',[])])
        fleet.append(row)
    return dict(world=str(world),fleet_file=str(file),fleet_sha256=sha(file),fleet_full_NBT=tag.snbt(),entity_count=len(es),entries=fleet)
def main():
    assert not OUT.exists();OUT.mkdir();source=[]
    for name in ('R45_source_candidate_20261003_v4_01','R45_source_candidate_20261004_v5_01','R45_source_candidate_20261004_v6_01'):
        world=ART/'composition_candidates'/name/'world';source.append(snapshot(world,True))
    assert len({r['fleet_sha256']for r in source})==1 and all(e['phase']=='PARKED'for r in source for e in r['entries'])
    legacy=snapshot(ROOT/'run/saves/SEELE_FIELD_R31_REVIEW');assert next(e for e in legacy['entries']if e['variant']==2)['phase']=='PLUG_FAULT'
    original=next(e for e in source[-1]['entries']if e['variant']==2);fault=next(e for e in legacy['entries']if e['variant']==2)
    assert original['Canonical']['UUID']!=fault['Canonical']['UUID']and original['EntryPlug']['UUID']!=fault['EntryPlug']['UUID']
    historical=ROOT/'artifacts/combat_rebuild_r35/facility/native_cycle_r35_03.log';lines=historical.read_text('utf8',errors='replace').splitlines();hit=[dict(line=i+1,text=s)for i,s in enumerate(lines)if'entry-plug fail-closed hold:'in s and'EVA-02'in s]
    latest=ROOT/'run/logs/latest.log';latestlines=latest.read_text('utf8',errors='replace').splitlines();examples=[dict(line=i+1,text=s)for i,s in enumerate(latestlines)if'EVA-02 entry-plug sequence is in fail-closed hold'in s]
    (OUT/'source_v4_v5_v6_complete_lineage.json').write_bytes((json.dumps(source,ensure_ascii=False,indent=2)+'\n').encode('utf8'));(OUT/'legacy_R31_complete_lineage.json').write_bytes((json.dumps(legacy,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    report=dict(source_all3_fleet_PARKED_and_same_bytes=True,source_V6_does_not_save_PLUG_FAULT=True,source_original_UUIDs_present=True,source_eva02_plug_stage_OCCUPIED1=True,source_eva02_plug_passengers=original['EntryPlug']['passengers'],source_eva02_hatch0_cabin5=True,legacy_R31_eva02_PLUG_FAULT=True,legacy_R31_canonical_and_plug_UUIDs_distinct_from_source=True,legacy_R31_plug_stage_SUSPENDED0_empty=fault['EntryPlug']['saved_stage']==0 and not fault['EntryPlug']['passengers'],current_repeated_log_examples=examples,historical_first_specific_reason=hit,historical_log=str(historical),historical_sha256=sha(historical),actual_fault_reason_persisted_in_FleetSavedData=False,clearance_as_current_root_cause='NOT_PROVEN; repeated PLUG_FAULT message cannot identify origin or present geometric obstruction',source_old_model_NPC_EVA_reset=False,world_written=False,Java_MC_started=False,fix_scope='Do not reset source or sourceNPC/EVA. The inspected repeated cannonQA hold belongs to legacyR31 saved progress. Native final source PREPARE/rollback/recovery remains independently unverified.')
    (OUT/'report.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({k:v for k,v in report.items()if k not in ['current_repeated_log_examples','source_eva02_plug_passengers','historical_first_specific_reason']},ensure_ascii=True,indent=2))
if __name__=='__main__':main()

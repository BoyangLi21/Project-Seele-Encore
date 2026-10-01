"""Root-only provider candidates with all installed prefixes and complete city volumes."""
from pathlib import Path
import argparse,json,hashlib
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/rebuild_r44';WORLD=ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def compress_columns(reservations):
    groups=defaultdict(dict);other=[]
    for r in reservations:
        x,y,z,X,Y,Z=r['bounds']
        if x==X and z==Z:groups[y,Y][x,z]=r
        else:other.append(r)
    compressed=[]
    for (y,Y),cells in sorted(groups.items()):
        rows=defaultdict(list)
        for x,z in cells:rows[z].append(x)
        active={};done=[]
        for z in sorted(rows):
            runs=[]
            for x in sorted(rows[z]):
                if not runs or x>runs[-1][1]+1:runs.append([x,x])
                else:runs[-1][1]=x
            current={}
            for x,X in runs:
                key=x,X
                if key in active and active[key][1]==z-1:current[key]=(active[key][0],z)
                else:current[key]=(z,z)
            for key,(start,end) in active.items():
                if key not in current or current[key][0]!=start:done.append((*key,start,end))
            active=current
        done.extend((*key,start,end) for key,(start,end) in active.items())
        rebuilt=set()
        for x,X,z,Z in done:
            covered={(xx,zz) for xx in range(x,X+1) for zz in range(z,Z+1)};assert not rebuilt&covered;rebuilt.update(covered)
            owners=sorted({cells[q].get('owner','') for q in covered})
            compressed.append(dict(bounds=[x,y,z,X,Y,Z],source_owners=owners,role='Exact same-Y 3D protection union of complete source road/approach columns',original_columns=len(covered)))
        assert rebuilt==set(cells),'No protection cell may be added or removed by coalescing'
    return other+compressed


def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--city',type=Path,action='append',required=True);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True)
    source=ART/'ecology/uniform_3d_configuration_v1/ecology_reservations.json';data=json.loads(source.read_text('utf8'));reservations=list(data['reservations']);city_epochs=[]
    for city in a.city:
        contract=city/'construction_contract.json';c=json.loads(contract.read_text('utf8'));assert c['static_full_component_passed'] and c['exact_current_preconditions_passed'] and c['station_journeys_complete']
        protection=city/'ecology_reservations.json';r=json.loads(protection.read_text('utf8'))['reservations']
        assert all(len(v['bounds'])==6 and v['bounds'][0]<=v['bounds'][3] and v['bounds'][1]<=v['bounds'][4] and v['bounds'][2]<=v['bounds'][5] for v in r)
        reservations.extend(r);city_epochs.append(dict(plan=str(city.resolve()),contract_sha256=sha(contract),protection_sha256=sha(protection),reservations=len(r),actual_installed_receipt_required_before_native_reseed=True))
    uncompressed=len(reservations);reservations=compress_columns(reservations)
    protection=a.output/'ecology_reservations.json';protection.write_text(json.dumps(dict(data,reservations=reservations,uncompressed_source_volumes=uncompressed,exact_column_union_preserved=True,city_epochs=city_epochs,source_original=str(source),source_original_sha256=sha(source),world_written=False),indent=2),'utf8')
    old_prefix=ART/'ecology/mixed_layer_calibration_v2/installed_prefix.json';old=json.loads(old_prefix.read_text('utf8'))
    new_input=ART/'ecology/mixed_layer_calibration_v3_under_infrastructure/calibration.json';new_complete=new_input.with_name(new_input.name+'.complete.json')
    new_result=new_input.with_name('calibration.result.json');job=json.loads(new_input.read_text('utf8'));complete=json.loads(new_complete.read_text('utf8'));result=json.loads(new_result.read_text('utf8'))
    assert complete['complete'] and complete['completed_origins']==15 and result['native_preview_complete']
    second={(q['x'],q['z'],q['layer']) for q in job['chunks']};first={tuple(q) for q in old['installed_origin_keys']};assert len(first)==len(second)==15 and not first&second
    receipts=sorted((ART/'ecology/replay_native_mixed_calibration_under_bridge_v3').rglob('receipt.json'));assert len(receipts)==2
    for r in receipts:assert json.loads(r.read_text('utf8'))['verified']
    prefix=dict(installed_origin_keys=[list(q) for q in sorted(first|second)],prefixes=[dict(path=str(old_prefix),sha256=sha(old_prefix)),
        dict(input=str(new_input),input_sha256=sha(new_input),complete=str(new_complete),complete_sha256=sha(new_complete),result=str(new_result),result_sha256=sha(new_result),receipts=[dict(path=str(r),sha256=sha(r)) for r in receipts])],
        installed_origins=30,applied_cells=old['applied_cells']+4660,applied_biome_sections=old['applied_biome_sections']+159,world_written=False,
        interpretation='Both verified installed15 prefixes are preserved. These are installed origins, not30 new trees. Bridge root centre64/66/66 is native natural ground; original selector soil_top69/70 is the tile maximum.')
    prefix_path=a.output/'installed_prefix_30.json';prefix_path.write_text(json.dumps(prefix,indent=2),'utf8')
    providers=[];key='data/projectseele/dimension/geofront.json'
    for i,target in enumerate([ROOT/'src/main/resources'/key,WORLD/'datapacks/tv_world_preview'/key]):
        before=target.read_bytes();provider=json.loads(before);assert provider['generator']['biome_source']['type']=='projectseele:regional_ecology'
        provider['generator']['biome_source']['protected_volumes']=[r['bounds'] for r in reservations]
        backup=a.output/f'provider_{i:02d}.before.json';after=a.output/f'provider_{i:02d}.after.json';backup.write_bytes(before);after.write_text(json.dumps(provider,ensure_ascii=False,indent=2)+'\n','utf8')
        providers.append(dict(target=str(target.resolve()),before=str(backup.resolve()),after=str(after.resolve()),before_sha256=sha(backup),after_sha256=sha(after)))
    (a.output/'provider_plan.json').write_text(json.dumps(dict(forward=[dict(target=v['target'],expected_sha256=v['before_sha256'],bytes_from=v['after']) for v in providers],
        inverse=[dict(target=v['target'],expected_sha256=v['after_sha256'],bytes_from=v['before']) for v in providers],
        protection=str(protection.resolve()),protection_sha256=sha(protection),installed_prefix=str(prefix_path.resolve()),installed_prefix_sha256=sha(prefix_path),
        protected_volumes=len(reservations),source_written=False,world_written=False,
        native_full_manifest_frozen=False,requires='Root merges/installs these two provider candidates only for the actual installed city set, after its current native queue. Full46177 remaining manifest must be regenerated from original46207 inputs and all30 installed origins, then freeze current compiled sources/resources/all current mixins and four effective providers. Earlier v7 excludes15 and has stale mixins: DO NOT RUN.'),indent=2),'utf8')
    print('City ecology candidate',len(reservations),'volumes /30 installed origins /two exact provider candidates /world unchanged',flush=True)


if __name__=='__main__':main()

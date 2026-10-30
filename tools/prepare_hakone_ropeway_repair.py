"""Carry regenerated native return paths into current records, retaining vehicles."""
import argparse,json
from pathlib import Path
from prepare_mtr_member_patch_r52 import Parser,array_header
from install_r53_carrier_trays import stopped_world


def prepare(a):
    if a.out.exists():raise ValueError('Use a fresh repair candidate')
    receipt=json.loads(a.receipt.read_text('utf8'))
    if not receipt['passed']:raise ValueError('Native return paths did not succeed')
    ids={'depots':{(-469400220093972240)%(1<<64),2362368853306981846},'sidings':{1149635627703520433,2037334585482268947}}
    fields={'depots':{'repeatInfinitely','path','lastGeneratedStatus','lastGeneratedFailedStartId','lastGeneratedFailedEndId','lastGeneratedFailedSidingCount'},
            'sidings':{'pathSidingToMainRoute','pathMainRouteToSiding'}}
    members=[];proof=[];root=Path('mtr/projectseele/geofront')
    with stopped_world(a.world):
        for kind,wanted in ids.items():
            found=set()
            for file in(a.world/root/kind).rglob('*'):
                if not file.is_file():continue
                node=Parser(file.read_bytes()).node();identity=node.value.get('id',0)%(1<<64)
                if identity not in wanted:continue
                found.add(identity);relative=file.relative_to(a.world/root);generated=Parser((a.native/relative).read_bytes()).node()
                if generated.value['id']%(1<<64)!=identity:raise ValueError('Native identity mismatch')
                replacements={key.value:value.raw for key,value in generated.children if key.value in fields[kind]}
                if set(replacements)!=fields[kind]:raise ValueError('Missing native repair fields')
                retired=[];kept=[]
                if kind=='sidings':
                    vehicles=next(v for k,v in node.children if k.value=='vehicles')
                    expected={'id','transportMode','name','color','speed','railProgress','elapsedDwellTime','nextStoppingIndexAto','nextStoppingIndexManual','reversed','departureIndex','sidingDepartureTime'}
                    if any(set(v.value)!=expected for v in vehicles.children):raise ValueError('Unknown passenger/cargo fields require preservation')
                    # These are automatically dispatched cabins, not user
                    # rolling stock. Keep full current records at 45 seconds
                    # of nominal 12 km/h travel, retire only the excess fleet.
                    for vehicle in sorted(vehicles.children,key=lambda v:v.value['railProgress'],reverse=True):
                        if not kept or kept[-1].value['railProgress']-vehicle.value['railProgress']>=150:kept.append(vehicle)
                        else:retired.append(vehicle.value)
                    keep_ids={v.value['id']for v in kept}
                    replacements['vehicles']=array_header(vehicles,len(kept))+b''.join(v.raw for v in vehicles.children if v.value['id']in keep_ids)
                if kind=='depots'and generated.value['repeatInfinitely']:raise ValueError('Infinite circulation is still enabled')
                after=node.header+b''.join(key.raw+replacements.get(key.value,value.raw)for key,value in node.children)
                parsed=Parser(after).node();retained=[key for key in node.value if key not in replacements]
                if any(node.value[key]!=parsed.value[key]for key in retained):raise ValueError('Unrelated native fields changed')
                for directory,data in [('before',node.raw),('after',after)]:
                    target=a.out/directory/root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                if retired:
                    target=a.out/('retired-cabins-'+str(identity)+'.json');target.write_text(json.dumps(retired,indent=2),'utf8')
                members.append((root/relative).as_posix());proof.append(dict(kind=kind,id=str(identity),name=node.value['name'],changed_fields=sorted(replacements),
                    vehicles_before=len(node.value.get('vehicles',[])),vehicles_retained=len(kept),excess_automatic_cabins_retired=len(retired)))
            if found!=wanted:raise ValueError('Expected native services were not found')
    manifest=dict(world=str(a.world),world_written=False,regions=[],cells=0,native_members=members,records=proof,progress='Surviving cabin IDs/positions retained; unrelated members untouched; excess auto-spawned cabins retained in reversible repair records')
    (a.out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf8')
    (a.out/'functional-check.json').write_text(json.dumps(dict(errors=[],native_return_paths_passed=True,visual_verified=False)),'utf8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    for name in('world','native','receipt','out'):p.add_argument('--'+name,type=Path,required=True)
    prepare(p.parse_args())

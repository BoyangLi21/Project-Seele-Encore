"""Callback authority changes, separating transient ride graph from synced state."""
from pathlib import Path
import argparse,json
ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);ap.add_argument('--fresh-scope',type=Path);args=ap.parse_args();directory=args.directory
fresh=set(json.loads(args.fresh_scope.read_text('utf8'))['fresh_actor_uuids'])if args.fresh_scope else None
keys=('plug_inserted','power_ticks','activation','locked','weapon','stance','prone_requested','crouch_requested','grapple_action',
      'server_movement_owner','locked_plug_uuid','link_fault_logged','launch_phase','cannon_charge','n2_arm_ticks','cannon_aim_pitch',
      'ordinary_stage','heavy_active','kick_active','client_explicit_jump','client_jump_pending')
rows=[]
for file in directory.glob('*_callbacks.jsonl'):
    pending={};events=[];actors={}
    with file.open('r',encoding='utf8')as stream:
        for line in stream:
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            if fresh is not None and r['host_uuid']not in fresh:continue
            uid=r['host_uuid'];actors.setdefault(uid,dict(host_id=r['host_id'],side=r['side'],stages=0));actors[uid]['stages']+=1
            if r['stage']=='before_remove_passenger':pending[uid]=r
            elif r['stage']in ('after_authoritative_remove_cleanup','after_client_graph_only')and uid in pending:
                before=pending[uid];a=before['actual_authoritative_fields'];b=r['actual_authoritative_fields']
                changed={k:dict(before=a[k],after=b[k])for k in keys if k in a and k in b and a[k]!=b[k]}
                events.append(dict(host_uuid=uid,host_id=r['host_id'],side=r['side'],tick=r['tick'],stage=r['stage'],
                                   authoritative_changes=changed,plug_before=a.get('plug_inserted'),plug_after=b.get('plug_inserted'),
                                   graph_before=before['ride_graph_passengers'],graph_after=r['ride_graph_passengers']))
    rows.append(dict(file=str(file.resolve()),actors=[dict(uuid=u,**v)for u,v in actors.items()],callback_edges=events,
                     first_client_illegal_plug_clear=next((e for e in events if e['side']=='client'and e['plug_before']is True and e['plug_after']is False),None),
                     client_sync_changes=sum(bool(e['authoritative_changes'])for e in events if e['side']=='client')))
report=dict(files=rows,fresh_scope_source=str(args.fresh_scope)if args.fresh_scope else None,fresh_actor_uuids=sorted(fresh)if fresh is not None else None,scope='Actual callback stages. Passenger/pilot presence and derived powered are allowed to be transient during vanilla list reconstruction; authority comparisons use explicit synced/state fields. Server real ejection cleanup is reported, not forbidden. Art quality remains separate.')
(directory/'callback_authority_readback.json').write_text(json.dumps(report,indent=2),'utf8')
print(json.dumps([dict(file=r['file'],actors=len(r['actors']),edges=len(r['callback_edges']),first_clear=r['first_client_illegal_plug_clear'],client_sync_changes=r['client_sync_changes'])for r in rows],indent=2))

"""Complete the measured Terminal actor inventory after the first geometry batch."""
import json,msvcrt
from r52_spatial_plan import BASE,TERMINAL
from move_component_actors_r52 import prepare_actor_files
from extend_world_depth_r52 import acquire_world_lock
from apply_s20_approved_semantic_repairs import atomic_replace


def main():
    world=BASE/'WORLD_R52';out=BASE/'terminal_move/actor_inventory_completion'
    assert not out.exists(),'Do not replay the actor completion'
    applied=json.loads((BASE/'terminal_move/complete_terminal_translation/PLAN.json').read_text('utf8'))
    assert applied['world_written']
    rows=json.loads((BASE/'survey/ORIGINAL_ALL_ACTORS.json').read_text('utf8'))['actors']
    selected=[r for r in rows if r['uuid']=='1768a5fb-4caf-463d-96f8-be1364f5f9ba']
    assert len(selected)==1 and selected[0]['id']=='projectseele:nerv_staff'
    lock=acquire_world_lock();before={}
    try:
        pending,receipt=prepare_actor_files(world,{r['uuid']:TERMINAL for r in selected},{r['uuid']:r['snbt'] for r in selected})
        roster_path=world/'nerv_staff_r15.json';roster=json.loads(roster_path.read_text('utf8'))
        station=next(s for s in roster['stations'] if s['id']=='guard/dogma_checkpoint')
        assert station['feet']==[12,-566,285]
        station['feet']=list(TERMINAL.block(station['feet']))
        pending[roster_path]=(json.dumps(roster,ensure_ascii=False,indent=2)+'\n').encode('utf8')
        out.mkdir()
        for path in pending:
            before[path]=path.read_bytes();backup=out/'before'/path.relative_to(world);backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(before[path])
        for path,raw in pending.items():
            assert path.read_bytes()==before[path];atomic_replace(path,raw)
        receipt.update(guard_home_and_roster=[12,-766,278],complete_terminal_actor_count=2,original_lilith_already_moved=True,shared_access_and_runtime_still_pending=True)
        (out/'APPLIED.json').write_text(json.dumps(receipt,indent=2),'utf8')
        print(json.dumps(receipt))
    except BaseException:
        for path,raw in before.items():atomic_replace(path,raw)
        raise
    finally:
        msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


if __name__=='__main__':main()

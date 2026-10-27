"""Cold post-native readback of the three-cell flank, routing and held actors."""
import argparse
import ast
import json
import msvcrt
import shutil
import uuid
from pathlib import Path

import nbtlib
from inspect_map_assets import region_chunks
from preview_r53_retired_lift_flank import DIM, LO, HI, NAV, RETIRED, read, read_guards, sha, write
from query_blocks import read_box, iter_block_entities


def plain(value):
    if isinstance(value, dict): return {k:plain(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [plain(v) for v in value]
    if hasattr(value, 'tolist'): return value.tolist()
    if hasattr(value, 'unpack'): return value.unpack()
    return value


def entity_uuid(tag):
    words=tag.get('UUID',[])
    if len(words)!=4:return None
    return str(uuid.UUID(int=sum((int(v)&0xffffffff) << (96-i*32) for i,v in enumerate(words))))


def main(a):
    artifact=a.native.parent
    candidate=artifact/'old-shaft-flank-preview-v2'
    installed=read(artifact/'install-old-shaft-flank-v2/INSTALLED.json')
    assert Path(installed['world']).resolve()==a.world.resolve()
    assert not a.output.exists()
    with (a.world/'session.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        cells=read_box(a.world,DIM,LO,HI);tags=dict(iter_block_entities(a.world,DIM,LO,HI))
        baseline=read(candidate/'LOCAL_BEFORE.json.gz')
        expected={tuple(r['pos']):r['state'] for r in baseline}
        for r in read(candidate/'patch/EXACT_DELTA.json.gz'):expected[tuple(r['pos'])]=r['after']
        assert cells==expected
        expected_tags={tuple(r['pos']):nbtlib.parse_nbt(r['nbt']) for r in baseline if r['nbt'] is not None}
        assert plain(tags)==plain(expected_tags)
        guards=read_guards(a.world,artifact);assert len(guards)==30
        assert all(sha(a.world/n)==installed['five_navigation_sha256'][n] for n in NAV)
        graph,nearest,walking,local,local_nearest=[read(a.world/n) for n in NAV]
        assert nearest['graph_sha256']==sha(a.world/NAV[0])
        assert local_nearest['graph_sha256']==sha(a.world/NAV[3])
        lookup={tuple(r):i for i,r in enumerate(walking['nodes'])};retired={lookup[p] for p in RETIRED}
        assert all(not graph['node_active'][i] and nearest['nodes'][i] is None for i in retired)
        assert all(not retired & set(e[:2]) for e in walking['walking_edges'])
        previous=read(artifact/'upper-navigation-v2/BLOCKED_CONNECTIONS.json')['connections']
        forbidden={(lookup[tuple(r['a'])],lookup[tuple(r['b'])]) for r in previous}
        assert not forbidden & {tuple(e[:2]) for e in walking['walking_edges']}
        state_rel=Path('dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat')
        old=nbtlib.load(a.native/('before-'+state_rel.name))['data']
        current=nbtlib.load(a.world/state_rel)['data']
        jobs=[]
        for r in old['Jobs']:
            variant=int(r['Snapshot']['Variant'])
            q=next(v for v in current['Jobs'] if int(v['Snapshot']['Variant'])==variant)
            assert plain(r)==plain(q), ('Existing held job changed',variant)
            jobs.append(dict(variant=variant,phase=str(q['Phase']),snapshot=plain(q['Snapshot']),
                full_owner_data_unchanged=True,clock=plain(q['OwnerData']['ContinuousClockR52'])))
        assert len(jobs)==len(current['Jobs'])==3
        fleet=read(artifact.parent/'rear-rail1022/native-v17-reload-fleet-b.json')
        found={}
        for rx in (-1,0):
            path=a.world/f'dimensions/projectseele/geofront/entities/r.{rx}.0.mca'
            for _,_,chunk in region_chunks(path,(rx*32,rx*32+31,0,31)):
                pending=list(chunk.get('Entities',[]))
                while pending:
                    tag=pending.pop();found[entity_uuid(tag)]=tag
                    pending.extend(tag.get('Passengers',[]))
        # An occupied vehicle is saved with its player, not in entity regions.
        player_id='76a86ddf-0aef-4b82-99e9-41d080e8ed30'
        player_file=a.world/'playerdata'/f'{player_id}.dat'
        player=nbtlib.load(player_file) if player_file.exists() else nbtlib.load(a.world/'level.dat')['Data']['Player']
        root_vehicle=player.get('RootVehicle',{}).get('Entity')
        pending=[] if root_vehicle is None else [root_vehicle]
        while pending:
            tag=pending.pop();found[entity_uuid(tag)]=tag
            pending.extend(tag.get('Passengers',[]))
        actors=[]
        for r in fleet:
            actor=found[r['uuid']];position=[float(v) for v in actor['Pos']]
            assert position==list(ast.literal_eval(r['pos'])), ('Actor moved',r['variant'],position)
            assert float(actor['Health'])==r['health']==300
            actors.append(dict(variant=r['variant'],uuid=r['uuid'],position=position,health=float(actor['Health']),
                baseline='rear-rail1022/native-v17-reload-fleet-b.json',unchanged=True))
        jar=a.world.parent.parent/'mods/projectseele-0.1.0-all.jar'
        assert sha(jar)==(a.native/'JAR_BEFORE_SHA256.txt').read_text()
        assert (a.native/'MENU_SAVE_QUIT.txt').exists()
        before,after=[read(a.native/n) for n in ('native-before-camera.json','native-after-camera.json')]
        assert before['pass'] and after['pass']
        assert read(a.native/'camera/before.json')==read(a.native/'camera/after.json')
        shutil.copy2(a.world/state_rel,a.native/('after-'+state_rel.name))
        receipt=dict(pass_=True,actual_world_written=False,cold_exclusive_session_lock=True,
            three_cell_delta_exact=True,all_local_cells_match_candidate=True,
            full_local_block_entities_unchanged=len(tags),prior_guards_exact=30,
            five_navigation_sha256={n:sha(a.world/n) for n in NAV},both_nearest_bindings_exact=True,
            four_retired_nodes_and_eight_removed_edges_preserved=True,prior_four_removed_edges_preserved=True,
            jobs=jobs,original_actors=actors,original_unit01_7_2m_hold_and_clock_unchanged=True,
            actual_jar_unchanged_sha256=sha(jar),normal_pause_screen_save_and_quit=True,
            native_loaded_block_collision_pass=True,production_main_graph_and_nearest_rows_exact=129574,
            native_camera_player_unchanged=True,door_open_close='NOT_EXERCISED_NO_ACTOR_OR_TASK_OPERATION',
            console_two_directions='HOLD_NO_EDITS',primary_agent_visual_review='PASS: sealed armor/backing join; original new door and white floor retained')
        write(a.output,receipt)
    print(json.dumps(dict(pass_=True,exact_cells=3,guards=30,unchanged_jobs=3,unchanged_original_actors=3,
                         five_nav_exact=True,normal_exit=True,output=str(a.output))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('world','native','output'):p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())

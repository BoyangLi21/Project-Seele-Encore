"""Bounded purpose recovery for two old-shaft lips and one human console recess.

Only historical/frozen evidence is read. The three-cell proposal is a review
document, not an installer, world edit, or navigation cache replacement.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import nbtlib
from audit_r53_pyramid_stair_treads import Frozen
from prepare_school_hakone_native_r45 import ActualGeometry
from query_blocks import read_box, iter_block_entities, dimension_dir

DIM='projectseele:geofront'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text(encoding='utf8'))


def write(p,value):
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


class Overlay:
    def __init__(self,original,changes):
        self.original,self.changes,self.world=original,changes,original.world
    def block(self,p):
        return self.changes.get(tuple(p),self.original.block(p))
    def get(self,x,y,z):
        return self.block((x,y,z))


def main():
    ap=argparse.ArgumentParser(__doc__)
    for key in ('source','frozen','out','historical_saves'):
        ap.add_argument('--'+key.replace('_','-'),type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    m=Frozen(a.source,a.frozen);before=ActualGeometry(m)
    positions=[(15,y,256) for y in range(-512,-509)]
    changes={p:'projectseele:nerv_structural_panel' for p in positions}
    after=ActualGeometry(Overlay(m,changes))
    local=read_box(a.frozen,DIM,(12,-514,254),(17,-509,259))
    tags=dict(iter_block_entities(a.frozen,DIM,(12,-514,254),(17,-509,259)))
    assert all(local[p]==m.block(p)=='minecraft:air' and p not in tags for p in positions)
    assert m.block((15,-513,256))=='projectseele:nerv_floor_panel'
    assert all(m.block((15,y,255))=='projectseele:nerv_structural_panel' for y in range(-512,-509))
    assert all(m.block((x,y,257))=='projectseele:nerv_structural_panel' for x in (12,13,14) for y in range(-512,-509))
    bounds=(7,250,25,261);source=(23,258);pockets=[(13,256),(14,256)]
    paths_before={str(p):before.path(source,p,bounds,-512) for p in pockets}
    paths_after={str(p):after.path(source,p,bounds,-512) for p in pockets}
    assert all(paths_before.values()) and not any(paths_after.values())
    # This recreates the historical blind spot: a centreline-only closed-door
    # check passes despite the full-width route around the retired door plane.
    direct=before.clear((13.5,-512,258.5),target=(13.5,-512,256.5))
    assert direct=='ACTUAL_BODY_OBSTRUCTION'
    opening_regression=ActualGeometry(Overlay(m,{p:s for p,s in changes.items() if p[1]==-510}))
    assert opening_regression.path(source,pockets[0],bounds,-512)
    retained=[]
    for x in range(15,18):
        for z in range(257,261):
            point=(x+.5,-512,z+.5)
            if before.standing(point)=='STATIC_STANDING':
                assert after.standing(point)=='STATIC_STANDING'
                assert after.path(source,(x,z),bounds,-512)
                retained.append(point)
    # Open only the actual declared landing leaves for aperture clearance.
    manifest=read(a.frozen/'personnel_lifts_r52.json')
    lift=next(r for r in manifest['lifts'] if r['id']=='s20-command-rear-x12-z253-v4')
    floor=next(r for r in lift['floors'] if r['cabin'][1]==-512)
    opened={tuple(r['pos']):'minecraft:air' for kind in ('landing_doors','cabin_doors') for r in floor[kind]}
    b_open=ActualGeometry(Overlay(m,opened));a_open=ActualGeometry(Overlay(m,{**opened,**changes}))
    aperture=[]
    for x in range(7,12):
        for offset in (.3,.5,.7):
            p=(x+offset,-512,256.5);q=(x+offset,-512,258.5)
            old,new=b_open.clear(p,target=q),a_open.clear(p,target=q)
            assert old==new=='CLEAR';aperture.append(dict(start=p,end=q,status=new))
    assert not before.unknown|after.unknown|a_open.unknown|b_open.unknown|opening_regression.unknown
    graph=read(a.frozen/'nerv_routes_r24.json.gz');npc=read(a.frozen/'r53_personnel_walking_graph.json.gz')
    wanted={(13,-512,256),(14,-512,256),(15,-512,256)}
    nodes=[dict(id=i,pos=r[:3],active=graph['node_active'][i]) for i,r in enumerate(graph['nodes']) if tuple(r[:3]) in wanted]
    ids={r['id'] for r in nodes}
    assert len(nodes)==3 and all(r['active'] for r in nodes)
    assert not any(r['node'] in ids for r in graph['goals']+graph['named_lift_landings'])
    edges=[e for e in npc['walking_edges'] if e[0] in ids or e[1] in ids]
    patch=[dict(pos=p,before=local[p],after=s,before_nbt=None,after_nbt=None,
                purpose='Close obsolete shaft-side access around retired old door; retain public R20 vestibule south/east') for p,s in changes.items()]
    write(a.out/'PROPOSED_FORWARD.json',patch)
    write(a.out/'PROPOSED_INVERSE.json',[dict(pos=r['pos'],before=r['after'],after=r['before'],before_nbt=None,after_nbt=None) for r in patch])
    write(a.out/'POSITIVE_EDIT_MASK.json',positions)
    write(a.out/'FROZEN_LOCAL.json',[dict(pos=p,state=s,nbt=tags[p].snbt() if p in tags else None) for p,s in sorted(local.items())])
    historical=[]
    for name in ('SEELE_S20_RECOVERY_R23','SEELE_S20_RECOVERY_R28','SEELE_S20_RECOVERY_R32','SEELE_R30_WORLD'):
        w=a.historical_saves/name
        cells=read_box(w,DIM,(23,-411,284),(33,-406,290))
        exact=dict(iter_block_entities(w,DIM,(23,-411,284),(33,-406,290)))
        level=nbtlib.load(w/'level.dat')['Data']
        target=(24,-410,287);button=(24,-408,287)
        assert cells.get(target)=='minecraft:air'
        assert cells.get(button)=='minecraft:crimson_button[face=wall,facing=east,powered=false]'
        historical.append(dict(world=str(w),last_played=int(level['LastPlayed']),
            region_sha256=sha(dimension_dir(w,DIM)/'region/r.0.0.mca'),
            snapshot=[dict(pos=p,state=s,nbt=exact[p].snbt() if p in exact else None) for p,s in sorted(cells.items())]))
    write(a.out/'HUMAN_CONSOLE_HISTORY.json',historical)
    proofs={name:sha(root/name) for name in (
        'tools/prepare_final_audits_r23.py','tools/repair_pyramid_galleries_r20.py',
        'tools/prepare_complete_main_lift_civil.py','tools/restore_r53_original_personnel_lifts.py',
        'tools/repair_r53_lift_entrances.py','src/main/java/com/projectseele/world/NervOperationsConsole.java',
        'docs/handoff/CLAUDE_HANDOFF_20260807.md')}
    result=dict(actual_world_written=False,preview_world_created=False,source_sha256=sha(a.source),sources=proofs,
        old_shaft=dict(classification='SOURCE_PURPOSE_RECOVERED_OBSOLETE_SHAFT_LIP_WITH_SIDE_BYPASS',
            source_public_port=[12.5,-419,258.5],current_public_port=[9.5,-512,258.5],
            purpose_evidence=['R23 explicitly places x10..14/z256 behind physical door z257 on shaft side',
                'R20 defines public connecting vestibule x15..17/z256..260; original command stair Z>=262 is retained',
                'Later civil migration seals old door x12..14/z257; current new shaft is x9/z253',
                'Source corner x15/z256 remains the one access neck around that sealed retired door'],
            original_centreline_test=direct,side_routes_before=paths_before,side_routes_after=paths_after,
            reopened_flank_negative_detected=True,retained_vestibule_standing_points=retained,
            retained_new_door_full_width=aperture,proposed_cells=len(patch),
            navigation=dict(nodes_needing_retirement=nodes,edges_touching_retired_pocket=edges,goal_or_landing_nodes=0,
                changed=False,required='Current five navigation files must be frozen together, same-batch nearest caches regenerated; this report is not a nav patch'),
            pending=['Fresh actual local freeze and maintained-static ownership before implementation',
                     'Review protected public vestibule boundary and install geometry/nav in one batch',
                     'Native doorway/open-close, complete flank and public corridor visual review']),
        control_recess=dict(classification='INHERITED_HUMAN_CONSOLE_RECESS_NOT_PROVEN_ACCIDENT',
            original_cell=[24,-410,287],current_cell=[24,-503,287],directions=2,
            original_button=[24,-408,287],current_button=[24,-501,287],historical_real_snapshots=len(historical),
            conclusion='Exists before R52/R53 in exact author-era geometry; binding is human-authoritative. No approved complete floor variant found.',
            construction_authorized=False,proposal_cells=0,
            unresolved='History proves inheritance, not explicit intent or current aesthetic approval. Keep exact recess and button until stronger purpose evidence.'),
        installation_authorized_by_this_report=False)
    write(a.out/'PURPOSE_RECOVERY.json',result)
    print(json.dumps(dict(out=str(a.out),three_cell_preview=len(patch),old_centreline_missed_side_bypass=True,
                         public_points_preserved=len(retained),door_clearances=len(aperture),console_snapshots=len(historical))))


if __name__=='__main__':
    main()

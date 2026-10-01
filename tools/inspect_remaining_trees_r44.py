"""Current full-component evidence for every unretired legacy grid tree."""
from pathlib import Path
from collections import Counter
import argparse, hashlib, json, math
from classify_legacy_trees_r44 import spec, point, packed
from measure_world_r40 import MeasuredWorld, properties
from query_blocks import AIR, iter_block_entities

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT/'artifacts/rebuild_r44/ecology/legacy_tree_components'
WORLD = ROOT/'run/saves/SEELE_FIELD_R44_REVIEW'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);a=parser.parse_args()
    assert not a.output.exists(), 'Keep complete earlier scans'
    source=ART/'layer_resolved_retirement/audit.json';baseline=json.loads(source.read_text('utf8'))
    objects=[r for r in baseline['objects'] if r['status']!='RETIRE_VERIFIED_COMPLETE_GRID_COMPONENT']
    assert len(objects)==675
    roots={tuple(root) for r in objects for root in r['roots']};templates={}
    for gz in range(-115,152):
        for gx in range(-131,132):
            t=spec(gx,gz)
            if t is not None and tuple(t['root']) in roots:templates[tuple(t['root'])]=t
    assert roots==set(templates)
    w=MeasuredWorld(WORLD)
    for r in objects:
        lo,hi=r['bounds'];w.box(tuple(q-1 for q in lo),tuple(q+1 for q in hi))
    w.load();print('Remaining full component chunks',len(w.status),dict(Counter(w.status.values())),flush=True)
    lo=tuple(min(r['bounds'][0][i]-1 for r in objects) for i in range(3))
    hi=tuple(max(r['bounds'][1][i]+1 for r in objects) for i in range(3))
    tags=dict(iter_block_entities(WORLD,'projectseele:geofront',lo,hi,selected_chunks=set(w.selected)))
    config_path=ROOT/'artifacts/rebuild_r44/ecology/biome_source.completed.json';config=json.loads(config_path.read_text('utf8'))
    records=[];classes=Counter()
    for r in objects:
        members={};expected_logs={};expected_leaves=set()
        for root in r['roots']:
            t=templates[tuple(root)]
            expected_logs.update({q:t['log']+'[axis=y]' for q in t['logs']});expected_leaves.update(t['leaves'])
        expected_leaves-=expected_logs.keys();mask=set(expected_logs)|expected_leaves
        failures=[];states=Counter();unmeasured=0;boundary=[]
        for q in sorted(mask):
            pos=point(q);state=w.block(pos);members[pos]=state;states[str(state)]+=1
            if state is None:unmeasured+=1;continue
            if pos in tags:failures.append(dict(pos=pos,state=state,full_nbt=tags[pos].snbt(),reason='Complete block entity preserved'));continue
            p=properties(state)
            if q in expected_logs:
                if state!=expected_logs[q]:failures.append(dict(pos=pos,state=state,reason='Original vertical trunk differs'))
            elif state.split('[')[0]!='minecraft:oak_leaves' or p.get('persistent')!='true' or p.get('waterlogged')!='false':
                failures.append(dict(pos=pos,state=state,reason='Original persistent crown differs'))
        if not unmeasured and not failures:
            for q in mask:
                x,y,z=point(q)
                for dx,dy,dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
                    other=packed(x+dx,y+dy,z+dz)
                    if other in mask:continue
                    pos=point(other);s=w.block(pos)
                    if s is None or s.split('[')[0].endswith(('_log','_leaves')):boundary.append(dict(pos=pos,state=s))
        empty=sum(s in AIR for s in members.values())
        remaining=sum(s is not None and s not in AIR for s in members.values())
        vegetation=sum(s is not None and s.split('[')[0].endswith(('_log','_leaves')) for s in members.values())
        if unmeasured:status='UNMEASURED_COMPONENT_NO_RETIREMENT'
        elif empty==len(mask):status='ORIGINAL_COMPONENT_ABSENT_NO_EDIT_NEEDED'
        elif not vegetation:status='ORIGINAL_TREE_REPLACED_BY_CURRENT_SOLID_COMPONENT_NO_TREE_EDIT'
        elif not failures and not boundary:status='COMPLETE_UNCHANGED_RESERVED_GRID_RESEED_DESIGN_PENDING'
        elif boundary and not failures:status='CONNECTED_LATER_NATURAL_OR_MANUAL_COMPONENT_PRESERVED'
        else:status='CHANGED_OR_PARTIAL_COMPONENT_PRESERVED'
        classes[status]+=1
        lx,ly,lz=r['bounds'][0];hx,hy,hz=r['bounds'][1]
        reserved=[list(b) for b in config['underground_reserved_bounds'] if lx<=b[2] and hx>=b[0] and lz<=b[3] and hz>=b[1]]
        records.append(dict(id=r['id'],roots=r['roots'],bounds=r['bounds'],previous_status=r['status'],status=status,
            complete_source_mask_cells=len(mask),currently_non_air_members=remaining,air_members=empty,unmeasured_members=unmeasured,
            current_vegetation_members=vegetation,actual_member_states=dict(states),full_nbt_in_source_mask=[dict(pos=p,snbt=tags[p].snbt()) for p in members if p in tags],
            current_failures=failures,connected_boundary=list({tuple(b['pos']):b for b in boundary}.values()),
            underground_biome_reservations=reserved,forward_authorized=False,native_reseed_verified=False,visual_passed=False))
    result=dict(world=str(WORLD),source_audit=str(source),source_audit_sha256=sha(source),configuration_sha256=sha(config_path),
        objects=records,component_counts=dict(classes),source_objects=675,source_reserved=540,source_modified_or_incomplete=135,
        world_written=False,scope='Every source tree member and complete neighbouring crown/trunk/NBT boundary was read through query_blocks. Unfinished chunks are distinct from absent trees, and later natural/manually changed crowns remain protected. The broad underground XY reservations still prevent reseed; unchanged old-grid trees are pending actual facility-volume reconciliation, not landscape PASS.')
    a.output.mkdir(parents=True);(a.output/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf8')
    print('Full remaining tree classification',dict(classes),flush=True)


if __name__=='__main__':main()

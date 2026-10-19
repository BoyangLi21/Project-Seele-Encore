"""Drain only declared empty-bay LCL after an interrupted, mismatched refill save.

Requires a saved returning original EVA outside the bay and a native open-front
witness. Does not change actors, doors, task phases, clocks, or other bays.
"""
import argparse,gzip,json,hashlib,msvcrt,uuid
from pathlib import Path
import nbtlib
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities
from transplant_s22_authority import read_region,parse_chunk
from apply_s20_approved_semantic_repairs import decompress_chunk
from move_component_actors_r52 import identity,descendants

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('world',type=Path);p.add_argument('output',type=Path);p.add_argument('--native-status',type=Path,required=True);p.add_argument('--gate-witness',type=Path,required=True);p.add_argument('--apply',action='store_true');a=p.parse_args()
    w=a.world;out=a.output;assert not out.exists();out.mkdir()
    with(w/'session.lock').open('r+b')as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        status=json.loads(a.native_status.read_bytes());sj=next(j for j in status['jobs']if j['variant']==0)
        assert sj['phase']=='RETURNING'and sj['route']=='unit0/recovery/1'and sj['leg']==0 and sj['fraction']==0
        gate_proof=next(g for g in json.loads(a.gate_witness.read_bytes())['gates']if g['id']=='bay_0_front')
        assert gate_proof['progress']==1 and gate_proof['bad_cell_count']>0
        assert all('projectseele:lcl'in s for s in gate_proof['bad_cells'])
        owner=json.loads((w/'ROOT_MECHANICAL_OWNER.json').read_bytes());u=next(u for u in owner['units']if u['variant']==0);g=next(g for g in owner['gates']if g['resource']=='bay_0_front')
        def table(v):
            raw=(w/v['cells_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==v['sha256'];return json.loads(gzip.decompress(raw))
        wet=table(u['lcl']);front=table(g['collision_steps']);cells={tuple(c['position']):c for layer in wet+front for c in layer}
        assert len(wet)==44 and all(c['open']=='minecraft:air'for c in cells.values())
        found=[]
        key=uuid.UUID(u['eva']).bytes
        for p in(w/'dimensions/projectseele/geofront/entities').glob('r.*.mca'):
            if not p.stat().st_size:continue
            for blob in read_region(p)[1]:
                if blob is None:continue
                size=int.from_bytes(blob[:4],'big')
                if key not in decompress_chunk(blob[4],blob[5:4+size]):continue
                for parent in parse_chunk(blob).get('Entities',[]):
                    for e in descendants(parent):
                        if 'UUID'in e and identity(e)==u['eva']:found.append(e)
        # Occupied root vehicles are saved with the player, not the entity region.
        player_copies=[]
        for p in [w/'level.dat',*sorted((w/'playerdata').glob('*.dat'))]:
            saved=nbtlib.load(p);saved=saved.get('Data',saved);saved=saved.get('Player',saved)
            root=saved.get('RootVehicle',{}).get('Entity')
            if root is not None:
                player_copies.extend(e for e in descendants(root) if 'UUID'in e and identity(e)==u['eva'])
        if player_copies:
            assert not found,'EVA must not be duplicated in region and player saves'
            assert all(e==player_copies[0] for e in player_copies),'Player snapshots disagree'
            found=[player_copies[0]]
        assert len(found)==1
        pos=list(map(float,found[0]['Pos']));assert abs(pos[0]-72.5)<.001 and abs(pos[1]+466)<.001 and abs(pos[2]-124.5)<.001,'Original EVA must still be outside the empty bay'
        state=nbtlib.load(w/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat')['data'];assert not str(state['Fault'])
        assert [str(j['Phase'])for j in state['Jobs']].count('RETURNING')==1
        saved_job=next(j for j in state['Jobs'] if int(j['Snapshot']['Variant'])==0)
        saved_snapshot=saved_job['Snapshot']
        assert str(saved_job['Phase'])=='RETURNING' and str(saved_snapshot['Route'])=='unit0/recovery/1'
        assert int(saved_snapshot['Leg'])==0 and float(saved_snapshot['Fraction'])==0
        progress_files=[w/'level.dat',*sorted((w/'playerdata').glob('*.dat')),
                        w/'dimensions/projectseele/geofront/data/projectseele_nerv_routes_r52.dat',
                        *sorted((w/'dimensions/projectseele/geofront/entities').glob('r.*.mca'))]
        preserved={str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in progress_files}
        lo=tuple(min(p[i]for p in cells)for i in range(3));hi=tuple(max(p[i]for p in cells)for i in range(3));actual=read_box(w,'projectseele:geofront',lo,hi);bes=dict(iter_block_entities(w,'projectseele:geofront',lo,hi))
        rows=[]
        for at,c in cells.items():
            s=actual[at]
            if s.split('[')[0]!='projectseele:lcl':continue
            assert at not in bes;rows.append(dict(position=at,old=s,new='minecraft:air'))
        assert rows
        (out/'EXACT_DELTA.json.gz').write_bytes(gzip.compress(json.dumps(rows).encode(),mtime=0))
        proof=dict(variant=0,original_uuid=u['eva'],eva_position=pos,declared_lcl_and_open_front_cells_only=True,cells=len(rows),actor_and_progress_changes=0,
                   native_status=str(a.native_status),native_gate_witness=str(a.gate_witness),bounds=[lo,hi],preserved_files=preserved)
        (out/'PLAN.json').write_text(json.dumps(proof,indent=2),'utf8')
        if a.apply:
            vox.WORLD=w;vox.DIM='projectseele:geofront';vox.OUT=out;paint=vox.Painter(vertical_bounds=(-1440,320))
            for r in rows:paint.exact((*r['position'],*r['position']),r['old'],r['new'],'drain_empty_original_bay_after_interrupted_refill')
            paint.apply('interrupted_empty_bay_drain',session_lock=lock)
            check=read_box(w,'projectseele:geofront',lo,hi);assert all(check[tuple(r['position'])]=='minecraft:air'for r in rows)
            assert all(hashlib.sha256((w/p).read_bytes()).hexdigest()==sha for p,sha in preserved.items())
            (out/'INSTALLED.json').write_text(json.dumps(proof|dict(exact_readback=True),indent=2),'utf8')
        print(proof)
if __name__=='__main__':main()

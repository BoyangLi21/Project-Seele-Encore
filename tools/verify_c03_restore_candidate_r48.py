"""Verify the finite candidate's four full templates, swept shafts, lattice continuity and IDs."""
from pathlib import Path
import gzip
import json
import nbtlib
from plan_c03_lowrise_restore_r48 import template, unpack, LINER, IRON

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r48/city/c03_lowrise_restore_final_v2'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    assert not manifest['world_written'] and manifest['holds_count']==0 and len(manifest['components'])==4
    before={}
    for c in manifest['components']:
        with gzip.open(c['full_before_preimage'],'rt',encoding='utf8') as stream:
            for line in stream:
                row=json.loads(line); q=tuple(row['pos'])
                assert q not in before
                before[q]=(row['state'],row['full_nbt'])
    patches={}; count=0
    with gzip.open(OUT/'forward.jsonl.gz','rt',encoding='utf8') as f, gzip.open(OUT/'inverse.jsonl.gz','rt',encoding='utf8') as g:
        for line, reverse in zip(f,g,strict=True):
            a,b=json.loads(line),json.loads(reverse); q=tuple(a['pos']); assert q not in patches
            assert before[q]==(a['before'],a['before_nbt'])
            assert b['pos']==a['pos'] and b['before']==a['after'] and b['after']==a['before']
            assert b['before_nbt']==a['after_nbt'] and b['after_nbt']==a['before_nbt']
            patches[q]=(a['after'],a['after_nbt']); count+=1
    assert count==manifest['changed_cells']
    def after(q): return patches.get(q,before[q])
    records=[]
    for c in manifest['components']:
        cx,cy,cz=c['centre']; planned=template(cx,cz)
        # Complete source frame and the whole intermediate route; not just a centreline or endpoints.
        for x in range(-7,8):
            for z in range(-7,8):
                for y in range(-7,110):
                    wanted=planned.get((x,y-80,z),'minecraft:air') if y>=80 else 'minecraft:air'
                    assert after((cx+x,y,cz+z))==(wanted,None)
                assert after((cx+x,-8,cz+z))==(LINER,None)
        for y in range(-8,81):
            for x in range(-8,9):
                for z in range(-8,9):
                    if max(abs(x),abs(z))==8:
                        assert after((cx+x,y,cz+z))[0] in {LINER,IRON}
        # Four incoming original beams connect through an unbroken full ring around the new hole.
        for x in range(-8,9):
            for z in range(-8,9):
                if max(abs(x),abs(z))==8: assert after((cx+x,79,cz+z))==(LINER,None)
        for x,z in [(-9,0),(9,0),(0,-9),(0,9),(-8,0),(8,0),(0,-8),(0,8)]:
            assert before[cx+x,79,cz+z]==(LINER,None) and after((cx+x,79,cz+z))==(LINER,None)
        for sx in (-1,1):
            for sz in (-1,1):
                for x in (sx*10,sx*11):
                    for z in (sz*10,sz*11):
                        for y in range(20,80): assert after((cx+x,y,cz+z))==(IRON,None)
        assert max(p[1] for p,s in planned.items() if s!='minecraft:air')==26
        for x in range(-1,2):
            for y in range(81,84):
                # Original full three-wide/three-high entry and its original court-facing side remain clear.
                facing=1 if cz<220 else -1
                assert after((cx+x,y,cz+7*facing))==('minecraft:air',None)
                assert after((cx+x,y,cz+8*facing))==('minecraft:air',None)
        records.append(dict(id=c['template_id'],full_source_template=True,entire_swept_shaft_clear=True,
                            lower_saddle_and_outside_liner=True,complete64_anchors=True,
                            original_lattice_connected_around_shaft=True,original_entry_full_clear=True))
    marker='projectseele_city_rigid_topology_r45_8246338109520.dat'
    old=nbtlib.load(OUT/'metadata_before'/marker)['data']
    new=nbtlib.load(OUT/'topology_after_full_readback_ONLY.dat')['data']
    assert len(old['Towers'])==96 and len(new['Towers'])==100
    assert all(old['Towers'][i]==new['Towers'][i] for i in range(96))
    control='projectseele_city_rigid_control_r45_8246338109520.dat'
    source=Path(manifest['source_world'])/'dimensions/projectseele/geofront/data'
    assert (OUT/'metadata_before'/control).read_bytes()==(source/control).read_bytes()
    assert new['LowriseAddonR48']['OriginalSettledLedger']==nbtlib.load(source/control)['data']
    assert len({tuple(map(int,new['Towers'][i]['R48Owner'])) for i in range(96,100)})==4
    result=dict(schema='projectseele.r48.c03-finite-candidate-verification.v1',world_written=False,
                checked_changed_cells=count,original96_topology_exact=True,original_ledger_bytes_equal=True,
                independent4_new_owners=True,full_before_NBT_and_inverse=True,records=records,
                native_motion_or_visual_passed=False)
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(changed_cells=count,components=4,original96_unchanged=True,
                          source_control_bytes_unchanged=True,full_template_shaft_anchors_lattice_entry_verified=True,
                          world_written=False,native_passed=False),indent=2))


if __name__=='__main__':main()

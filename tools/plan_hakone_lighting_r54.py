"""Unify the complete authored Hakone station lighting without world writes.

R45's fifty ceiling lamps remain at their original supported positions. Only
R54's redundant added chain/lantern pairs are retired, using their exact receipt.
Controlled NERV lighting, platforms, moving walks and all block entities stay.
"""
from pathlib import Path
import argparse,collections,gzip,json
from query_blocks import AIR,read_box,iter_block_entities

WARM='minecraft:lantern[hanging=true,waterlogged=false]'


def source_lamp_targets(components):
    targets=[]
    for component in components:
        x,y,z,X,Y,Z=component['bounds']
        if component['kind']=='full_retained_operating_station_building':
            middle=(z+Z)//2
            targets.extend((component['id'],(xx,110,zz))
                           for xx in range(x+12,X-9,12)
                           for zz in (middle-6,middle+6))
        else:
            targets.extend((component['id'],(xx,y+4,z+2))for xx in (x+2,X-2))
    return targets


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--world',type=Path,required=True)
    parser.add_argument('--installed-art',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    components=json.loads((args.world/'r45_school_hakone_components.json').read_text('utf8'))['hakone']['components']
    targets=source_lamp_targets(components)
    with gzip.open(args.installed_art,'rt',encoding='utf8')as stream:
        extras=[json.loads(line)for line in stream]
    extras=[r for r in extras if r['after'].startswith(('minecraft:lantern[','minecraft:chain['))]
    lo=(-1554,108,621);hi=(-1406,112,691)
    actual=read_box(args.world,'projectseele:geofront',lo,hi)
    bes=dict(iter_block_entities(args.world,'projectseele:geofront',lo,hi))
    rows=[];by_component=collections.Counter()
    for owner,q in targets:
        old=actual[q]
        if old==WARM:continue
        if old!='minecraft:sea_lantern' or q in bes:
            raise ValueError(('Original decorative lamp changed; retain unknown fixture',q,old))
        if actual[(q[0],q[1]+1,q[2])]not in {'minecraft:oak_planks','minecraft:spruce_planks','minecraft:stripped_spruce_log[axis=z]'}:
            raise ValueError(('Original whole ceiling lamp has a changed support',q))
        rows.append(dict(pos=q,before=old,after=WARM,before_nbt=None,after_nbt=None,
                         owner=owner,reason='Original complete ceiling-lamp layout receives one warm 15-level fixture per existing 15-level decorative light; real timber ceiling support retained'))
        by_component[owner]+=1
    removed=0
    for source in extras:
        q=tuple(source['pos']);old=actual[q]
        if source['before']not in AIR or source.get('before_nbt')or source.get('after_nbt'):
            raise ValueError(('Receipt is not a plain R54 added decoration',q))
        if old==source['before']:continue
        if old!=source['after']or q in bes:
            raise ValueError(('R54 added fixture changed after installation',q,old))
        rows.append(dict(pos=q,before=old,after=source['before'],before_nbt=None,after_nbt=None,
                         owner='r54/hakone_station/redundant_added_lighting',reason='Retire exactly the R54 duplicate lantern/chain row; retain its ceiling beam and all original lighting positions'))
        removed+=1
    if len({tuple(r['pos'])for r in rows})!=len(rows):raise ValueError('Lighting owners overlap')
    circuit=json.loads((args.world/'facility_lighting_r30.json').read_text('utf8'))
    controlled={tuple(q)for q in circuit.get('command_lamps',[])}
    if controlled.intersection(tuple(r['pos'])for r in rows):
        raise ValueError('A proposed decorative change belongs to the registered command-light circuit')
    args.out.mkdir(parents=True,exist_ok=True)
    inverse=[dict(r,before=r['after'],after=r['before'])for r in rows]
    for name,values in [('forward',rows),('inverse',inverse)]:
        with gzip.open(args.out/(name+'.jsonl.gz'),'wt',encoding='utf8')as stream:
            for row in values:stream.write(json.dumps(row)+'\n')
    manifest=dict(schema='projectseele.r54.hakone-lighting-unification.v1',world=str(args.world),dimension='projectseele:geofront',
                  static_cells=len(rows),original_lamps=len(targets),replaced_by_component=dict(by_component),duplicate_fixture_cells_removed=removed,
                  old_and_new_original_lamp_light_level=15,controlled_lights_changed=0,block_entities_changed=0,
                  retained='Original ceiling supports, NERV controlled lighting, one pre-existing lantern, room and hall lighting positions, native moving walks and platforms',
                  affected_tiles=sorted({(r['pos'][0]//64,r['pos'][2]//64)for r in rows}),metadata_preconditions=[],world_tables=[],world_written=False,native_visual_pending=True)
    for name,value in [('forwardPatch.json',rows),('inversePatch.json',inverse),('positiveEditMask.json',[r['pos']for r in rows]),('installation_manifest.json',manifest)]:
        (args.out/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf8')
    print('Prepared',len(rows),'cells:',len(targets),'original lamp positions,',removed,'duplicate fixture cells removed; tiles',manifest['affected_tiles'])


if __name__=='__main__':main()

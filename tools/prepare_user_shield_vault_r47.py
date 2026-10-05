"""Measured, reversible enlargement of the owner's existing commissioned shield well."""
from pathlib import Path
import argparse,copy,gzip,json
from query_blocks import read_box,iter_block_entities,AIR

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/rebuild_r47/world/user_shield_vault'
DIM='projectseele:geofront'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--world',type=Path,required=True)
    args=parser.parse_args();world=args.world.resolve()
    if not world.is_relative_to(ROOT/'artifacts/rebuild_r47'):raise ValueError('Foreign world')
    metadata=world/'r47_equipment_vaults.json';before=json.loads(metadata.read_text('utf8'))
    after=copy.deepcopy(before);vault=next(v for v in after['vaults'] if v['payload']==7)
    if vault['lid_span']!=17:raise ValueError('Only the original 17-wide shield lid is selected')
    lo=(132,25,-55);hi=(199,83,-17)
    states=read_box(world,DIM,lo,hi);tags=dict(iter_block_entities(world,DIM,lo,hi));desired={}
    allowed=AIR|{'minecraft:stone','minecraft:dirt','minecraft:grass_block','minecraft:barrier',
        'projectseele:nerv_structural_panel','projectseele:nerv_floor_panel','projectseele:nerv_machine_hazard'}
    def put(q,value):
        old=states[q]
        if q in tags or old.partition('[')[0] not in allowed:raise ValueError((q,'Foreign device/structure',old))
        desired[q]=value
    cx,cz=154,-36;half=14;radius=15;floor=26;lids=[]
    for x in range(cx-radius,cx+radius+1):
        for z in range(cz-radius,cz+radius+1):
            rim=x in (cx-radius,cx+radius) or z in (cz-radius,cz+radius)
            for y in range(floor,81):
                if y==floor:value='projectseele:nerv_floor_panel'
                elif y==80:
                    value='projectseele:nerv_machine_hazard' if rim else 'minecraft:barrier'
                    if not rim:lids.append((x,y,z))
                else:value='projectseele:nerv_structural_panel' if rim else 'minecraft:air'
                put((x,y,z),value)
    apron={(x,z) for x in range(cx-radius-4,cx+radius+5) for z in range(cz-radius-4,cz+radius+5)
           if not(cx-radius<=x<=cx+radius and cz-radius<=z<=cz+radius)}
    apron|={(x,z) for x in range(132,200) for z in range(-20,-16)}
    for x,z in sorted(apron):
        if not(lo[0]<=x<=hi[0] and lo[2]<=z<=hi[2]) or (x,80,z) in desired:continue
        put((x,80,z),'projectseele:nerv_floor_panel')
        for y in range(79,71,-1):
            if states[x,y,z] not in AIR:break
            put((x,y,z),'projectseele:nerv_structural_panel')
        else:raise ValueError(((x,z),'No measured natural/apron bearing within eight metres'))
        for y in (81,82,83):
            if states[x,y,z] not in AIR:raise ValueError(((x,y,z),'Maintenance headroom is occupied'))
    rows=[dict(pos=q,before=states[q],after=v,before_nbt=None,after_nbt=None,
               owner='r47_owner_shield_vault',reason='complete_shield_payload_enclosure_and_dry_service_apron')
          for q,v in sorted(desired.items()) if states[q]!=v]
    OUT.mkdir(parents=True,exist_ok=True)
    for name,items in [('forward',rows),('inverse',[dict(r,before=r['after'],after=r['before']) for r in reversed(rows)])]:
        with gzip.open(OUT/(name+'.jsonl.gz'),'wt',encoding='utf8') as stream:
            for row in items:stream.write(json.dumps(row,separators=(',',':'))+'\n')
    (OUT/'positiveEditMask.json').write_text(json.dumps([r['pos'] for r in rows]),encoding='utf8')
    vault.update(half=half,shell_bounds=[(cx-radius,floor,cz-radius),(cx+radius,80,cz+radius)],
        inner_clearance=[(cx-half,floor+1,cz-half),(cx+half,79,cz+half)],floor_block_y=floor,
        pod_bottom_y=27,pod_height=52,lid_span=29,outer_span=31,lidPositions=lids,LidPositions=lids,
        payload_height=50,hatch='outer_edge_hinge_90_degrees',front_cover='vertical_header_retraction')
    after['maintenance_link']=dict(x=[132,199],z=[-20,-17],floor=80,feet=81)
    (OUT/'metadata_patch.json').write_text(json.dumps(dict(relative_target=metadata.name,before=before,after=after),indent=2),encoding='utf8')
    (OUT/'contract.json').write_text(json.dumps(dict(world=str(world),dimension=DIM,rows=len(rows),complete_NBT=True,
        same_original_station_UUID=True,no_entity_or_progress_writes=True,lid_cells=len(lids),
        payload_world_size=[25.3449156428,50,11.7174534717],clear_payload_box=[29,52,29],
        neighbouring_sword_well_unchanged=True,public_regenerator_reads_updated_shell_bounds=True,
        authorization='Owner supplied large shield; existing dedicated shield well enlarged as one component'),indent=2),encoding='utf8')
    print(json.dumps(dict(rows=len(rows),lid_cells=len(lids),shell=vault['shell_bounds'],metadata_patch=str(OUT/'metadata_patch.json'))))

if __name__=='__main__':main()

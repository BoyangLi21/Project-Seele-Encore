"""Read-only exact cargo representation diff and optimistic scheduler costs.

These are modelled placements from packaged cargo, not measured server writes.
Imported counts model template movement and hatch maintenance, not failure repair.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import nbtlib
from measure_central_tower_ports_r44 import specs

ROOT = Path(__file__).resolve().parents[1]


def unpack_pos(pos: int) -> tuple[int, int, int]:
    def signed(value: int, bits: int) -> int:
        return value - (1 << bits) if value >= 1 << (bits - 1) else value
    return signed((pos >> 38) & ((1 << 26) - 1), 26), signed(pos & 4095, 12), signed((pos >> 12) & ((1 << 26) - 1), 26)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT/'artifacts/rebuild_r45/city_performance/placement_cost.json')
    args = parser.parse_args()
    data_dir = ROOT/'artifacts/server-ready-r44-stage/stage/world/dimensions/projectseele/geofront/data'
    buildings = {}
    for path in sorted(data_dir.glob('projectseele_tokyo3_building_archive_r44_*.dat')):
        building = nbtlib.load(path)['data']['Buildings'][0]
        buildings[unpack_pos(int(building['Centre']))] = (path, building)
    per_layer = [[] for _ in range(312)]
    records = []
    for index, (cx, cz, _, _) in enumerate(specs()):
        path, building = buildings[(cx, 80, cz)]
        height, half = int(building['Height']), int(building['Half'])
        fixed_core = bool(building['FixedStreetCore'])
        anchors = {(x-cx, y, z-cz) for x,y,z in map(unpack_pos, building['NegativeDomeAnchorMask'])}
        cells = []
        for cell in building['Cargo']:
            state = json.dumps(cell['State'].unpack(), sort_keys=True, separators=(',', ':'))
            tag = copy.deepcopy(cell.get('NBT'))
            if tag is not None:
                for key in ('x', 'y', 'z'): tag.pop(key, None)
            cells.append((unpack_pos(int(cell['Pos'])), (state, tag.snbt() if tag is not None else None)))
        def state(name): return (json.dumps({'Name':'minecraft:'+name},sort_keys=True,separators=(',',':')), None)
        hatch = {}
        outer = max(abs(cx-30), abs(cz-220)) == 200
        for x in range(-half, half+1):
            for z in range(-half, half+1):
                edge=max(abs(x),abs(z))
                block='polished_deepslate' if edge>=half-1 else ('orange_concrete' if (x+z)%4<2 else 'black_concrete') if edge==half-2 else 'iron_block' if x%6==0 or z%6==0 else 'light_gray_concrete' if outer else 'gray_concrete'
                if abs(x)==half-3 and abs(z)==half-3: block='sea_lantern'
                hatch[(x,80,z)] = state(block)
        def representation(depth):
            surface=max(0,height-depth)
            below=max(0,min(height,depth-max(height,60)))
            result = dict(hatch) if depth else {}
            for (x,y,z), value in cells:
                if depth==0 and y==0: result[(x,80,z)] = value
                if surface>0 and y-depth>=1: result[(x,80+y-depth,z)] = value
                if below>0 and y>=height-below+1 and y<=height+3: result[(x,19-height+y,z)] = value
                if below==height and y==0: result[(x,19-height,z)] = value
            if below>0 and below<height:
                for x in range(-half,half+1):
                    for z in range(-half,half+1): result[(x,19-below,z)] = state('polished_deepslate')
                result[(0,19-below,0)] = state('sea_lantern')
            elif below==height and fixed_core: result[(0,19-height,0)] = state('sea_lantern')
            for pos in anchors: result.pop(pos,None)
            if fixed_core: result.pop((0,80,0),None)
            return result
        before=representation(0)
        counts=[]
        for depth in range(312):
            after=representation(depth+1)
            count=sum(before.get(key)!=after.get(key) for key in before.keys()|after.keys())
            per_layer[depth].append(count)
            counts.append(count)
            before=after
        records.append(dict(index=index,archive=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),height=height,half=half,placements=sum(counts),active_layers=sum(c>0 for c in counts),layer_placements=counts))
        if index%12==0: print(f'cargo {index+1}/93',flush=True)
    # Lossless adjacent state diff is symmetric: generated return has same count.
    generated=sum(r['placements'] for r in records)
    def generated_ticks(counts):
        index=0; remaining=counts[0]; ticks=0
        while index<len(counts):
            ticks+=1; writes=0
            while index<len(counts) and writes<4096:
                amount=min(remaining,2048); remaining-=amount; writes+=amount
                if remaining: break
                index+=1
                if index<len(counts): remaining=counts[index]
        return ticks
    optimistic_layer_ticks=[max(5,generated_ticks(c)+3) for c in per_layer]
    # All imported copies have equal body counts under rotation. Simulate one
    # non-rotated template, including a permanent ground hatch and runtime marker.
    template_path=ROOT/'artifacts/server-ready-r44-stage/stage/server/projectseele-local-maps/tokyo3_skyscraper.nbt'
    template=nbtlib.load(template_path)
    palette=[json.dumps(p.unpack(),sort_keys=True,separators=(',',':')) for p in template['palette']]
    blueprint={tuple(map(int,b['pos'])):palette[int(b['state'])] for b in template['blocks']}
    air=json.dumps({'Name':'minecraft:air'},sort_keys=True,separators=(',',':'))
    def plain(name): return json.dumps({'Name':'minecraft:'+name},sort_keys=True,separators=(',',':'))
    world={}; body_changes=0; maintenance_changes=0
    # Endpoint0 fixture assumes complete original template and complete hatch.
    for pos,value in blueprint.items(): world[(pos[0],81+pos[1],pos[2])]=value
    for x in range(23):
        for z in range(12): world[(x,80,z)]=plain('polished_deepslate' if x in (0,22) or z in (0,11) else 'iron_block' if x%5==0 or z%5==0 else 'gray_concrete')
    world[(0,80,0)]=plain('netherite_block')
    def put(pos,value):
        changed=world.get(pos,air)!=value
        if value==air: world.pop(pos,None)
        else: world[pos]=value
        return int(changed)
    descent_imported=[]; ascent_imported=[]
    for ascending in (False,True):
        for depth in (range(142) if not ascending else range(142,0,-1)):
            old_base=81-depth; new_base=old_base+(1 if ascending else -1)
            maintenance=put((0,old_base-1,0),air)+put((0,new_base-1,0),air)+2 # state marker clear/restore
            body=0
            for y in (range(81,-1,-1) if ascending else range(82)):
                for x in range(23):
                    for z in range(12): body+=put((x,new_base+y,z),blueprint.get((x,y,z),air))
            abandoned=old_base if ascending else old_base+81
            for x in range(23):
                for z in range(12): body+=put((x,abandoned,z),air)
            for x in range(23):
                for z in range(12):
                    if world.get((x,80,z),air)==air: maintenance+=put((x,80,z),plain('polished_deepslate' if x in (0,22) or z in (0,11) else 'iron_block' if x%5==0 or z%5==0 else 'gray_concrete'))
            maintenance+=put((0,new_base-1,0),plain('netherite_block'))
            (ascent_imported if ascending else descent_imported).append(dict(body=body,maintenance=maintenance))
    result=dict(schema='projectseele.city-placement-cost-r45.v1',world_written=False,native_minecraft_measured=False,
        generation_source='actual 93 R44-stage full cargo, archive representation semantics; no user edits between steps',
        generated_one_direction_placements=generated,generated_round_trip_placements=2*generated,
        generated_hypothetical_strict_4096_tick_floor=math.ceil(generated/4096),generated_hypothetical_strict_4096_seconds_floor=math.ceil(generated/4096)/20,
        generated_actual_step_overshoot_bound=4096+2048-1,
        optimistic_serial_schedule_one_direction_ticks=sum(optimistic_layer_ticks),optimistic_serial_schedule_one_direction_seconds=sum(optimistic_layer_ticks)/20,
        optimistic_serial_schedule_round_trip_seconds=sum(optimistic_layer_ticks)/10,
        min_generated_height=min(r['height'] for r in records),max_generated_height=max(r['height'] for r in records),
        no_generated_placements_after_depth=max(i+1 for i,c in enumerate(per_layer) if sum(c)>0),
        imported_template_sha256=hashlib.sha256(template_path.read_bytes()).hexdigest(),
        imported_target_drop=142,imported_template_body_placements_descent=sum(x['body'] for x in descent_imported)*3,
        imported_template_body_placements_ascent=sum(x['body'] for x in ascent_imported)*3,
        imported_maintenance_descent_estimate=sum(x['maintenance'] for x in descent_imported)*3,
        imported_maintenance_ascent_estimate=sum(x['maintenance'] for x in ascent_imported)*3,
        imported_maintenance_limit='Model of rotation NONE/index0; exact fixed hatch seam changes differ for rotated copies and indices, actual ground may retain user structures',
        layers=[dict(old_depth=i,total_generated_placements=sum(c),generated_min_ticks=generated_ticks(c),optimistic_period_ticks=optimistic_layer_ticks[i]) for i,c in enumerate(per_layer)],records=records)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,indent=2),'utf8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('layers','records')},indent=2),flush=True)


if __name__=='__main__':main()

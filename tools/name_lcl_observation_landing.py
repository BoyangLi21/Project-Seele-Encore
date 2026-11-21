"""Apply the installed LCL landing label to its Moving Elevators block entity."""
import argparse
from pathlib import Path
import copy
import json
import os
import shutil
import nbtlib

from install_r53_carrier_trays import stopped_world
from write_deep_cells import read_chunk, write_chunk, state_entry, block_at


def install(world, backup):
    geo = world/'dimensions/projectseele/geofront'
    manifest = json.loads((world/'personnel_lifts_r52.json').read_text('utf8'))
    lift = next(l for l in manifest['lifts'] if l['id'] == 'r25-west-observation')
    floor = next(f for f in lift['floors'] if f['cabin'][1] == -1088)
    x,y,z = floor['controller']
    label = floor['label']
    if not label or label.isdigit():
        raise ValueError('Expected a named LCL landing')
    chunk = (x >> 4, z >> 4)
    reg = geo/'region'/f'r.{x>>9}.{z>>9}.mca'
    recipe = geo/'data/city_rigid_generation_r45/surface'/f'{chunk[0]}_{chunk[1]}.dat'
    pos = ((x & 0x3ffffff) << 38) | ((z & 0x3ffffff) << 12) | (y & 4095)
    with stopped_world(world):
        buf = bytearray(reg.read_bytes())
        i,loc,count,t = read_chunk(buf,*chunk)
        state = block_at(t,x,y,z)
        if not state.startswith('movingelevators:elevator_block['):
            raise ValueError(f'Unexpected controller block {state}')
        entity = next(v for v in t['block_entities'] if (v['x'],v['y'],v['z']) == (x,y,z))
        if str(entity['id']) != 'movingelevators:elevator_tile':
            raise ValueError('Unexpected controller entity')
        entity['data']['name'] = nbtlib.String(label)
        entity['data']['hasName'] = nbtlib.Byte(1)
        if recipe.exists():
            rt = nbtlib.load(recipe)
        else:
            identity = nbtlib.load(next((geo/'data').glob('projectseele_city_rigid_control_r45_*.dat')))['data']['WorldUUID']
            rt = nbtlib.File(dict(Version=nbtlib.Int(1),WorldUUID=identity,Palette=nbtlib.List[nbtlib.Compound](),Spans=nbtlib.List[nbtlib.IntArray](),BlockEntities=nbtlib.List[nbtlib.Compound]()))
        value = state_entry(state)
        if value not in rt['Palette']:
            rt['Palette'].append(value)
        number = rt['Palette'].index(value)
        rt['BlockEntities'] = nbtlib.List[nbtlib.Compound]([v for v in rt['BlockEntities'] if int(v['Pos']) != pos])
        rt['BlockEntities'].append(nbtlib.Compound(dict(Pos=nbtlib.Long(pos),StateId=nbtlib.Int(number),NBT=copy.deepcopy(entity))))
        write_chunk(buf,i,loc,count,t)
        backup.mkdir(parents=True,exist_ok=True)
        for p in (reg, recipe):
            if p.exists() and not (backup/p.name).exists(): shutil.copy2(p,backup/p.name)
        recipe.parent.mkdir(parents=True,exist_ok=True)
        temp_recipe = recipe.with_suffix('.lcl-new')
        temp_region = reg.with_suffix('.lcl-new')
        rt.save(temp_recipe)
        temp_region.write_bytes(buf)
        os.replace(temp_recipe,recipe)
        os.replace(temp_region,reg)
        actual = read_chunk(reg.read_bytes(),*chunk)[3]
        be = next(v for v in actual['block_entities'] if (v['x'],v['y'],v['z']) == (x,y,z))
        if be['data']['name'] != label or not int(be['data']['hasName']):
            raise ValueError('LCL controller readback failed')
    print(f'{x} {y} {z} -> {label}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('world',type=Path)
    p.add_argument('backup',type=Path)
    args=p.parse_args()
    install(args.world,args.backup)

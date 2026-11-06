"""Install the three explicitly requested Hakone outlet power sockets."""
from pathlib import Path
import argparse,json,math
import nbtlib
import regional_voxels as vox
from query_blocks import read_box,iter_block_entities

def install(world,out,outlet_id='exit3',rear_offset=-23.5):
    owner=json.loads((world/'ROOT_MECHANICAL_OWNER.json').read_text('utf8'))
    outlets=[r for r in owner['receivers'] if f'/{outlet_id}/' in r['port']]
    assert len(outlets)==3
    vox.WORLD=world;vox.DIM='projectseele:geofront';vox.OUT=out
    painter=vox.Painter(vertical_bounds=(-1440,320));positions=[]
    for outlet in outlets:
        x,y,z=outlet['stopped_frame']['position']
        p=(math.floor(x),math.floor(y),math.floor(z+rear_offset));positions.append(p)
        lo=(p[0]-1,p[1]-1,p[2]-1);hi=(p[0]+1,p[1]+2,p[2]+1)
        states=read_box(world,vox.DIM,lo,hi);tags=dict(iter_block_entities(world,vox.DIM,lo,hi))
        base=(p[0],p[1]-1,p[2]);target='projectseele:umbilical_pylon'
        if states[p]==target:
            assert str(tags[p]['id'])==target
            continue
        assert states[p]=='minecraft:air' and p not in tags
        assert states[base]=='minecraft:grass_block[snowy=false]' and base not in tags
        assert all(states[(p[0],q,p[2])]=='minecraft:air' for q in range(p[1],p[1]+3))
        painter.exact((*base,*base),states[base],'projectseele:nerv_structural_panel',outlet['port']+'/power')
        painter.exact((*p,*p),states[p],target,outlet['port']+'/power')
        painter.block_entities[p]=nbtlib.Compound({'id':nbtlib.String(target),'x':nbtlib.Int(p[0]),'y':nbtlib.Int(p[1]),'z':nbtlib.Int(p[2])})
    if painter.ops:painter.apply(outlet_id+'_field_power')
    for p in positions:
        assert read_box(world,vox.DIM,p,p)[p]=='projectseele:umbilical_pylon'
        assert str(dict(iter_block_entities(world,vox.DIM,p,p))[p]['id'])=='projectseele:umbilical_pylon'
    print(json.dumps({'pylons':positions,'changed_cells':len(painter.ops),'actual_readback':True}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--world',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--outlet',choices=('hakone','geofront'),default='hakone');a=p.parse_args();install(a.world,a.out,'exit1' if a.outlet=='geofront' else 'exit3',23.5 if a.outlet=='geofront' else -23.5)

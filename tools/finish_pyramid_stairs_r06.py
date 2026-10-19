"""Add supported handrails to the explicitly authored six switchback flights."""
import argparse,json
import numpy as np
import regional_voxels as vox
from scan_regional_completion import volume

OUT=vox.ROOT/'artifacts/world_motion_r06/stair_finish'
LO=(61,-449,349);HI=(73,-355,369)
def main(apply=False):
    blocks,pal=volume(LO,HI);changes={}
    def old(pos):
        x,y,z=pos;return pal[blocks[y-LO[1],z-LO[2],x-LO[0]]]
    for y,z,x in np.ndindex(blocks.shape):
        state=pal[blocks[y,z,x]];pos=(x+LO[0],y+LO[1],z+LO[2])
        if state.startswith('minecraft:polished_deepslate_stairs['):changes[pos]=state.replace('polished_deepslate','polished_andesite')
        elif state=='minecraft:polished_deepslate' and 62<=pos[0]<=72:changes[pos]='minecraft:gray_concrete'
    for f in range(-449,-365,14):
        for centre,z0,start,step in [(64,364,f,-1),(69,357,f+7,1)]:
            for i in range(7):
                z=z0+step*i;y=start+i+1
                for x in (centre-2,centre+2):
                    for yy in range(start+1,y+1):
                        if old((x,yy,z))=='minecraft:air':changes[x,yy,z]='minecraft:gray_concrete'
                    pos=(x,y+1,z)
                    if old(pos)=='minecraft:air':
                        facing='north' if step<0 else 'south'
                        side=('right' if x<centre else 'left') if step<0 else ('left' if x<centre else 'right')
                        changes[pos]=f'mtr:escalator_side[facing={facing},orientation=slope,side={side}]'
    vox.OUT=OUT;p=vox.Painter()
    for pos,state in changes.items():p.match((*pos,*pos),old(pos),state,'r06/pyramid/supported_stair_guards')
    p.meta.update(flights=12,clear_width=3,style='Smooth concrete stringers, continuous sloped guards and stone treads',
                  source='R04 flight_a/flight_b exact centres and floor datums')
    p.apply('finish') if apply else p.save_plan('finish')
    print('Stair finish',len(changes),flush=True)
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');main(ap.parse_args().apply)

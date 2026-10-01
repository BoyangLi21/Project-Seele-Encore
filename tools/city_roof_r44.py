"""Continuous compact domestic roofs; no repeated half-rise stair strips."""
def compact_roof(b,state,put):
    x,z,X,Z=b['bounds'];roof=b['roof'];owner=b['id'];span=(X-x)//2
    for xx in range(x,X+1):
        for zz in range(z-1,Z+2):
            for yy in range(roof+1,roof+span+2):
                if (state((xx,yy,zz)) or '').startswith('minecraft:brick_stairs['):put((xx,yy,zz),'minecraft:air',owner,'Retire exact old separated half-rise compact roof tile strips')
    for xx in range(x,X+1):
        rise=min(xx-x,X-xx);yy=roof+1+rise;heading='east' if xx<(x+X)/2 else 'west'
        for zz in range(z-1,Z+2):
            for yb in range(roof+1,yy):put((xx,yb,zz),'minecraft:red_terracotta',owner,'Whole continuous weather backing beneath the tile skin, including the gable overhang; no detached tile sheets')
        for zz in range(z-1,Z+2):put((xx,yy,zz),f'minecraft:brick_stairs[facing={heading},half=bottom,shape=straight,waterlogged=false]',owner,'Whole connected tiled domestic gable: one stair rises one block per horizontal metre')
        # Full founded triangular gable faces close the under-roof end
        # voids. The attic stays clear elsewhere; the weather deck remains.
        for zz in [z,Z]:
            for yb in range(roof+1,yy):put((xx,yb,zz),'minecraft:smooth_sandstone',owner,'Continuous supported triangular gable wall below the connected tile slope')
    b['roof_role']='Connected45-degree compact tile gable with sealed triangular ends and retained continuous weather deck; no public roof route'
    return dict(building=owner,roof_plane=roof,ridge_y=roof+1+span,old_half_rise_template_retired=True,world_written=False)

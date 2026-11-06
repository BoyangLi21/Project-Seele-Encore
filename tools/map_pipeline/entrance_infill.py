"""Validate exact AIR-only pavement infill outside an unchanged entrance wall."""
from map_pipeline.frontage_geometry import entrance_frame
from map_pipeline.rail_underpasses import physical_deck_ceilings
from query_blocks import AIR


def validated_apron_infill(editor,spec,rows,curves):
    admitted={};by_id={r['id']:r for r in rows}
    for request in spec.get('protected_apron_infill',[]):
        row=by_id[request['parcel']]
        if row.get('translation',[0,0,0])!=[0,0,0]:raise ValueError('Protected apron infill requires an unmoved parcel')
        px,pz,dx,dz=entrance_frame(row);floor=int(row['site']['floor'])
        apron={(px+dx*d-dz*s,floor,pz+dz*d+dx*s)for d in(1,2,3)for s in(-1,0,1)}
        occupied=row['occupied_bounds']
        for point in request['positions']:
            p=tuple(map(int,point));x,y,z=p
            if p not in apron or occupied[0]<=x<=occupied[3]and occupied[2]<=z<=occupied[5]:
                raise ValueError(('Infill must be on the exterior doorway apron',p))
            if editor.state(*p,original=True).split('[')[0]not in AIR:raise ValueError(('Apron infill must retain every existing block',p))
            if physical_deck_ceilings(curves['trains'],[x,z,x,z])[x,z]!=319:raise ValueError(('Apron infill enters running track footprint',p))
            admitted[p]='minecraft:smooth_stone'
    return admitted

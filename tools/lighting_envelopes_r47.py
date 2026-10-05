"""Finite native rail-polyline sweep exclusion for fixture candidates."""
def rail_swept(point, curves, radius=4.0):
    x,y,z=point
    for curve in curves:
        if curve['mode']!='TRAIN':continue
        points=curve['points']
        for a,b in zip(points,points[1:]):
            if x<min(a[0],b[0])-radius or x>max(a[0],b[0])+radius or z<min(a[2],b[2])-radius or z>max(a[2],b[2])+radius:continue
            dx,dz=b[0]-a[0],b[2]-a[2];den=dx*dx+dz*dz
            t=max(0,min(1,((x-a[0])*dx+(z-a[2])*dz)/den)) if den>1e-9 else 0
            near_x,near_z=a[0]+t*dx,a[2]+t*dz
            rail_y=a[1]+t*(b[1]-a[1])
            if (x-near_x)**2+(z-near_z)**2<radius*radius and rail_y-.2<=y<=rail_y+6.1:return True
    return False

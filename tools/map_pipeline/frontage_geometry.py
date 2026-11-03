"""Cardinal entrance normals for offset leaves of a two-leaf doorway."""
def entrance_frame(row):
    x,_,z=row['door'];a,_,b=row['approach'];dx,dz=a-x,b-z
    if abs(dx)==abs(dz):raise ValueError(('Ambiguous entrance normal',row.get('id')))
    # The recorded door is one leaf, whereas the approach is the entrance
    # centre. Its one-cell lateral offset must not turn the porch diagonally.
    if abs(dx)>abs(dz):return x,b,1 if dx>0 else -1,0
    return a,z,0,1 if dz>0 else -1

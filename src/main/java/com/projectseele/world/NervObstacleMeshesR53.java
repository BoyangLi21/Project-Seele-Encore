package com.projectseele.world;

import java.util.*;

/** Index immutable local triangles once; callers supply the current world frame. */
final class NervObstacleMeshesR53
{
    private static final Map<EvaOriginalMeshGeometryR52.Geometry,List<NervRigidMeshSweepR52>> BODIES=new WeakHashMap<>();
    private static final Map<NervAirframeGeometryR52.Part,NervRigidMeshSweepR52> PARTS=new WeakHashMap<>();
    private static final Map<FullAssemblyGeometryR52.Provider,Map<Integer,Map<String,NervRigidMeshSweepR52>>> PLUGS=new WeakHashMap<>();

    static synchronized List<NervRigidMeshSweepR52> body(EvaOriginalMeshGeometryR52.Geometry geometry)
    {
        return BODIES.computeIfAbsent(geometry,g->g.parts().stream().map(p->new NervRigidMeshSweepR52(p.triangles())).toList());
    }

    static synchronized NervRigidMeshSweepR52 part(NervAirframeGeometryR52.Part part)
    {
        return PARTS.computeIfAbsent(part,p->new NervRigidMeshSweepR52(p.xyz()));
    }

    static synchronized Map<String,NervRigidMeshSweepR52> plugParts(FullAssemblyGeometryR52.Provider source,int variant)
    {
        return PLUGS.computeIfAbsent(source,p->new HashMap<>()).computeIfAbsent(variant,v->{
            var result=new LinkedHashMap<String,NervRigidMeshSweepR52>();
            source.closedPlugParts(v).forEach((name,xyz)->result.put(name,new NervRigidMeshSweepR52(xyz)));
            return Collections.unmodifiableMap(result);
        });
    }

    private NervObstacleMeshesR53(){}
}

package com.projectseele.world;

import java.util.LinkedHashMap;
import java.util.Map;
import net.minecraft.world.phys.Vec3;

/** Bounded results for two immutable source meshes; never a world clearance. */
final class NervRigidPairMemoR53
{
    private record Key(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,
        NervRigidMeshSweepR52 peer,RigidTransform peerFrom,RigidTransform peerTo,double maximumError,Vec3 extra){}
    private final int capacity;
    private final Map<Key,Boolean> results=new LinkedHashMap<>(64,.75f,true);
    private long evaluations;
    NervRigidPairMemoR53(int capacity)
    {
        if(capacity<1)throw new IllegalArgumentException("Positive result capacity required");
        this.capacity=capacity;
    }
    synchronized boolean intersects(NervRigidMeshSweepR52 mesh,RigidTransform from,RigidTransform to,
        NervRigidMeshSweepR52 peer,RigidTransform peerFrom,RigidTransform peerTo,double maximumError,Vec3 extra,
        NervRigidMeshSweepR52.PairQuery query)
    {
        var a=translated(from,from.translation().subtract(peerFrom.translation()));
        var b=translated(to,to.translation().subtract(peerTo.translation()));
        var c=translated(peerFrom,Vec3.ZERO);var d=translated(peerTo,Vec3.ZERO);
        // The constructor can renormalize a stored float quaternion. In that
        // case retain all original frames rather than alias another motion.
        if(sameRotation(a,from)&&sameRotation(b,to)&&sameRotation(c,peerFrom)&&sameRotation(d,peerTo))
        {from=a;to=b;peerFrom=c;peerTo=d;}
        var key=new Key(mesh,from,to,peer,peerFrom,peerTo,maximumError,extra);
        var result=results.get(key);
        if(result!=null)return result;
        boolean hit=mesh.intersects(from,to,peer,peerFrom,peerTo,maximumError,extra,query);
        evaluations++;results.put(key,hit);
        if(results.size()>capacity)results.remove(results.keySet().iterator().next());
        return hit;
    }
    private static RigidTransform translated(RigidTransform f,Vec3 p)
    {return new RigidTransform(p,f.qx(),f.qy(),f.qz(),f.qw());}
    private static boolean sameRotation(RigidTransform a,RigidTransform b)
    {return a.qx()==b.qx()&&a.qy()==b.qy()&&a.qz()==b.qz()&&a.qw()==b.qw();}
    synchronized long evaluations(){return evaluations;}
    synchronized int size(){return results.size();}
}

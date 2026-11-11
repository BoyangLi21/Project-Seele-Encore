package com.projectseele.physics;

import com.bulletphysics.collision.broadphase.Dbvt;
import com.bulletphysics.collision.broadphase.DbvtBroadphase;
import com.bulletphysics.collision.broadphase.DbvtProxy;
import com.bulletphysics.collision.broadphase.Dispatcher;
import com.bulletphysics.collision.dispatch.CollisionConfiguration;
import com.bulletphysics.collision.dispatch.CollisionObject;
import com.bulletphysics.dynamics.DiscreteDynamicsWorld;
import com.bulletphysics.dynamics.RigidBody;
import com.bulletphysics.dynamics.constraintsolver.ConstraintSolver;
import java.util.IdentityHashMap;
import javax.vecmath.Vector3f;

/**
 * A dynamics world that does not recompute the bounds of terrain boxes that never move.
 *
 * JBullet refreshes the bounds of every awake body on every substep, static ones included, and a static body stays
 * awake for its first two seconds. Once a terrain box has settled, that refresh computes the box it already has and
 * changes nothing in the broadphase tree; its only effect is to move the box to the head of the current stage list,
 * which keeps it in the tree of moving bodies. {@link TerrainPruningBroadphase#keepMoving} does that move alone.
 *
 * A box counts as settled only after a full refresh has been seen to change nothing: its first refresh fattens its
 * leaf, and the second puts the exact bounds back on its proxy.
 */
final class TerrainSteadyWorld extends DiscreteDynamicsWorld
{
    private final TerrainPruningBroadphase broadphase;
    /** Terrain boxes, and whether a full refresh of each has been seen to change nothing. */
    private final IdentityHashMap<CollisionObject,Boolean> terrain=new IdentityHashMap<>();
    private final float[] before=new float[12],after=new float[12];

    TerrainSteadyWorld(Dispatcher dispatcher,TerrainPruningBroadphase broadphase,ConstraintSolver solver,CollisionConfiguration configuration)
    {
        super(dispatcher,broadphase,solver,configuration);this.broadphase=broadphase;
    }

    /** Declares a static body that will keep its shape and place until it is removed. */
    void terrain(RigidBody body){terrain.put(body,Boolean.FALSE);}

    @Override public void removeRigidBody(RigidBody body)
    {
        terrain.remove(body);super.removeRigidBody(body);
    }

    @Override public void updateSingleAabb(CollisionObject body)
    {
        Boolean settled=terrain.get(body);
        if(settled==null||TerrainPruningBroadphase.rejected()){super.updateSingleAabb(body);return;}
        DbvtProxy proxy=(DbvtProxy)body.getBroadphaseHandle();
        if(settled&&TerrainPruningBroadphase.refreshTrusted())
        {
            if(!broadphase.keepMoving(proxy))super.updateSingleAabb(body);
            return;
        }
        Dbvt.Node leaf=proxy.leaf;boolean moving=proxy.stage!=DbvtBroadphase.STAGECOUNT;bounds(proxy,before);
        super.updateSingleAabb(body);
        bounds(proxy,after);
        boolean same=proxy.leaf==leaf;
        for(int i=0;i<12&&same;i++)same=Float.floatToRawIntBits(before[i])==Float.floatToRawIntBits(after[i]);
        if(!settled){if(same)terrain.put(body,Boolean.TRUE);}
        // A settled box of the moving tree must stay as it was; until that has held often enough, every refresh is the full one.
        else if(moving)
        {
            if(same)TerrainPruningBroadphase.refreshMatched();
            else TerrainPruningBroadphase.reject("a settled terrain box changed in the tree when its bounds were refreshed");
        }
    }

    private static void bounds(DbvtProxy proxy,float[] out)
    {
        Vector3f a=proxy.leaf.volume.Mins(),b=proxy.leaf.volume.Maxs(),c=proxy.aabb.Mins(),d=proxy.aabb.Maxs();
        out[0]=a.x;out[1]=a.y;out[2]=a.z;out[3]=b.x;out[4]=b.y;out[5]=b.z;
        out[6]=c.x;out[7]=c.y;out[8]=c.z;out[9]=d.x;out[10]=d.y;out[11]=d.z;
    }
}

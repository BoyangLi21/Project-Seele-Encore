package com.projectseele.client.render;

import com.projectseele.entity.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.phys.AABB;
import org.joml.Vector3f;
import java.util.Map;
import java.util.WeakHashMap;

/** Frozen visual limbs can extend beyond the post-ejection standing collision box. */
final class EvaRetainedRenderBoundsR46
{
    private record Cached(CompoundTag pose, AABB local) {}
    private static final Map<EvaUnit01Entity,Cached> CACHE=new WeakHashMap<>();

    static AABB bounds(EvaUnit01Entity eva,float partial)
    {
        if(!EvaShutdownR30.displaysCapturedPoseR45(eva))return null;
        CompoundTag tag=EvaShutdownPoseR30.retainedPoseForBounds(eva);
        if(tag.isEmpty())return null;
        Cached cached=CACHE.get(eva);
        if(cached==null||!cached.pose().equals(tag))
        {
            var pose=EvaBodyPose.neutralForTransportR32(eva);
            EvaShutdownR30.decode(tag,pose);
            AABB local=null;
            for(AABB part:EvaBodyPose.posedCarrierHulls(eva,pose))
                local=local==null?part:local.minmax(part);
            if(local==null)return null;
            cached=new Cached(tag.copy(),local);CACHE.put(eva,cached);
        }
        // Hulls already include render scale; retain the same shutdown frame/yaw.
        var transform=EvaRifleKinematics.world(eva,partial).scale(1/EvaScale.RENDER_SCALE);
        AABB b=cached.local(),world=eva.getBoundingBox();
        for(int i=0;i<8;i++)
        {
            var v=transform.transformPosition(new Vector3f((float)((i&1)==0?b.minX:b.maxX),
                    (float)((i&2)==0?b.minY:b.maxY),(float)((i&4)==0?b.minZ:b.maxZ)));
            world=world.minmax(new AABB(v.x,v.y,v.z,v.x,v.y,v.z));
        }
        return world.inflate(1);
    }
    private EvaRetainedRenderBoundsR46(){}
}

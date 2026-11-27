package com.projectseele.client.render;
import com.projectseele.entity.*;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** The same held service body feeds the original renderer, sockets and collider. */
final class EvaMechanicalServicePoseR52
{
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        return write(EvaBodyPose.sample(eva,partial),model,"R52_HELD_ORIGINAL_SERVICE_SOURCE");
    }
    static EvaMotionEngineV2.BoneWrites write(EvaBodyPose.Sample sample,BakedGeoModel model,String owner)
    {
        var changed=new HashSet<String>();
        for(String name:sample.rig.keySet())model.getBone(name).ifPresent(b->{
            var pivot=sample.rig.get(name).pivot();
            var position=sample.positions.get(name);
            b.setPivotX(pivot.x*16);b.setPivotY(pivot.y*16);b.setPivotZ(pivot.z*16);
            EvaRigTransforms.rotate(b,sample.rotations.get(name));
            b.setPosX(-position.x*16);b.setPosY(position.y*16);b.setPosZ(position.z*16);
            b.setScaleX(1);b.setScaleY(1);b.setScaleZ(1);
            changed.add(name);
        });
        var bones=Set.copyOf(changed);
        return new EvaMotionEngineV2.BoneWrites(bones,bones,owner);
    }
    private EvaMechanicalServicePoseR52(){}
}

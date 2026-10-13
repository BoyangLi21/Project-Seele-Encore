package com.projectseele.client.render;
import com.projectseele.entity.*;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** The same held service body feeds the original renderer, sockets and collider. */
final class EvaMechanicalServicePoseR52
{
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        var sample=EvaBodyPose.sample(eva,partial);var changed=new HashSet<String>();for(String name:sample.rig.keySet())model.getBone(name).ifPresent(b->{var spec=sample.rig.get(name);var p=sample.positions.get(name);b.setPivotX(spec.pivot().x*16);b.setPivotY(spec.pivot().y*16);b.setPivotZ(spec.pivot().z*16);EvaRigTransforms.rotate(b,sample.rotations.get(name));b.setPosX(-p.x*16);b.setPosY(p.y*16);b.setPosZ(p.z*16);b.setScaleX(1);b.setScaleY(1);b.setScaleZ(1);changed.add(name);});return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(changed),"R52_HELD_ORIGINAL_SERVICE_SOURCE");
    }
    private EvaMechanicalServicePoseR52(){}
}

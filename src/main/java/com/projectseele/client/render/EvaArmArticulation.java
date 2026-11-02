package com.projectseele.client.render;

import java.util.LinkedHashSet;
import java.util.Set;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/** Retargets the elbow articulation while retaining the evaluated hand intent. */
final class EvaArmArticulation
{
    static EvaMotionEngineV2.BoneWrites apply(BakedGeoModel model)
    {
        Set<String> rotations=new LinkedHashSet<>(),positions=new LinkedHashSet<>();var root=new Matrix4f();
        for(String side:new String[]{"l","r"})
        {
            var upper=model.getBone("arm_"+side).orElse(null);var lower=model.getBone("forearm_"+side).orElse(null);var wrist=model.getBone("wrist_"+side).orElse(null);var hand=model.getBone("hand_"+side).orElse(null);
            if(upper==null||lower==null||wrist==null||hand==null)continue;
            var target=EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root);var orientation=EvaRigTransforms.rotation(EvaRigTransforms.model(hand));
            var centre=EvaRigTransforms.elbow(lower,side);var shoulder=EvaRigTransforms.point(upper,EvaRigTransforms.pivot(upper),root);var elbow=EvaRigTransforms.point(upper,centre,root);
            float reach=new Vector3f(centre).sub(EvaRigTransforms.pivot(upper)).length()+EvaRigTransforms.pivot(hand).sub(centre).length();
            // A near-straight arm hovers at full reach: skipping the solve there
            // alternated solved and unsolved wrists between frames. Pull the
            // target just inside reach instead so the solution stays continuous.
            float span=target.distance(shoulder);
            if(span>reach-.001F)target.set(new Vector3f(target).sub(shoulder).mul((reach-.001F)/Math.max(span,1e-6F)).add(shoulder));
            EvaRigTransforms.solveArm(upper,lower,wrist,hand,side,target,orientation,elbow.sub(shoulder),root);
            rotations.addAll(Set.of("arm_"+side,"forearm_"+side,"wrist_"+side,"hand_"+side));positions.addAll(Set.of("forearm_"+side,"wrist_"+side,"hand_"+side));
        }
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(rotations),Set.copyOf(positions),"MOTION_ENGINE_LIVE_ACTION");
    }
}

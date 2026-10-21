package com.projectseele.client.render;

import com.projectseele.entity.EvaDorsalMechanism;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaDorsalProfile;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.Set;

/** Mechanical travel owns the upper body only while the socket is in use. */
public final class EvaDorsalPose
{
    /** Visibility must also run for captured/service poses that already own the hinge rotation. */
    public static void applyVisibility(EvaUnit01Entity eva, BakedGeoModel model)
    {
        boolean closed = EvaDorsalMechanism.open(eva) < .002F;
        model.getBone("dorsal_liner").ifPresent(bone -> bone.setHidden(closed));
    }

    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva, BakedGeoModel model)
    {
        float open=EvaDorsalMechanism.open(eva), bow=EvaDorsalMechanism.bow(eva);
        var profile=EvaDorsalProfile.of(eva);var axis=profile.hingeAxisModel();
        var rotation=new Quaternionf().rotationAxis((float)Math.toRadians(profile.openAngle()*open),(float)axis.x,(float)-axis.y,(float)-axis.z);
        model.getBone("dorsal_cover").ifPresent(b -> EvaRigTransforms.rotate(b,rotation));
        applyVisibility(eva, model);
        model.getBone("dorsal_leaf_l").ifPresent(b -> b.setRotY((float)Math.toRadians(-106*open)));
        model.getBone("dorsal_leaf_r").ifPresent(b -> b.setRotY((float)Math.toRadians(106*open)));
        if (bow < .0001F && open < .0001F) return new EvaMotionEngineV2.BoneWrites(Set.of("dorsal_cover"),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
        for (String name : new String[]{"root","torso_lower","torso_upper","neck","head"})
        {
            model.getBone(name).ifPresent(b -> {
                float weight=Math.max(bow,open);
                b.setRotX(b.getRotX()*(1-weight)+(name.equals("head") ? -.72F*bow : 0));
                b.setRotY(b.getRotY()*(1-weight)); b.setRotZ(b.getRotZ()*(1-weight));
                b.setPosX(b.getPosX()*(1-weight));b.setPosY(b.getPosY()*(1-weight));b.setPosZ(b.getPosZ()*(1-weight));
            });
        }
        return new EvaMotionEngineV2.BoneWrites(Set.of("dorsal_cover","root","torso_lower","torso_upper","neck","head"),Set.of("root","torso_lower","torso_upper","neck","head"),"MOTION_ENGINE_LIVE_ACTION");
    }
    private EvaDorsalPose() {}
}

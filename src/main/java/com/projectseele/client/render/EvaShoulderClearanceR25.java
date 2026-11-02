package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaPrototypeEntity;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.Set;

/** Shoulder pylons flare at their own hinges as the prone helmet turns past them. */
final class EvaShoulderClearanceR25
{
    private static final float PRONE_TILT=Float.parseFloat(System.getProperty("projectseele.proneTiltR56","50"));
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,float partial)
    {
        if(root==null||eva instanceof EvaPrototypeEntity||eva.isNervLogisticsLocked()||eva.isFirstBattleActive())return EvaMotionEngineV2.BoneWrites.empty();
        float prone=eva.rifleProneBlend(partial);var head=model.getBone("head").orElse(null);
        if(prone<.01F||head==null)return EvaMotionEngineV2.BoneWrites.empty();
        var direction=new Matrix4f(root).mul(EvaRigTransforms.model(head)).transformDirection(new Vector3f(0,0,-1)).normalize();
        float yaw=(float)Math.toDegrees(Math.atan2(-direction.x,direction.z));
        float relative=Math.abs(Mth.wrapDegrees(yaw-Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot)));
        float amount=Mth.clamp((relative-22)/18,0,1);amount=amount*amount*(3-2*amount);
        float angle=18*Mth.DEG_TO_RAD*amount*prone;
        model.getBone("pylon_l").ifPresent(b->b.setRotZ(b.getRotZ()+angle));
        model.getBone("pylon_r").ifPresent(b->b.setRotZ(b.getRotZ()-angle));
        return new EvaMotionEngineV2.BoneWrites(Set.of("pylon_l","pylon_r"),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
    }

    /**
     * Lying flat turns the pylons from upright to pointing past the helmet,
     * hiding it from the front and side. Tip them back over the shoulders as
     * the body goes down, whichever pose owner drew the body.
     */
    static void proneTilt(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(eva instanceof EvaPrototypeEntity||eva.isNervLogisticsLocked()||eva.isFirstBattleActive())return;
        float prone=Math.max(eva.rifleProneBlend(partial),EvaFixedCannonBodyR55.applies(eva)?1F:0F);
        if(prone<.01F)return;
        float tilt=PRONE_TILT*Mth.DEG_TO_RAD*prone*prone*(3-2*prone);
        model.getBone("pylon_l").ifPresent(b->b.setRotX(b.getRotX()+tilt));
        model.getBone("pylon_r").ifPresent(b->b.setRotX(b.getRotX()+tilt));
    }
    private EvaShoulderClearanceR25() {}
}

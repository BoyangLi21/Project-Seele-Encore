package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Vector3f;

/**
 * Straight punches land on the line the body faces, whichever shoulder throws
 * them. The captured right landed 2.8 blocks wide of it while the left landed
 * on it. The chest carries the correction, not the arm: bending the elbow
 * inward would take the drive out of the punch. The head stays on the target.
 */
final class EvaPunchAimR59
{
    /** Share of the chest's extra turn the neck gives back. */
    private static final float NECK=.75F;
    private static final float MOST_DEGREES=12;
    /** Clip phase from contact that the fist stays out, then the share over which the turn goes. */
    private static final float HELD=.22F,LEAVING=.3F;

    private EvaPunchAimR59(){}

    static void apply(EvaUnit01Entity e,EvaBodyPose.Sample body,float partial)
    {
        if(e.getWeapon()!=EvaUnit01Entity.WEAPON_FISTS||e.getOrdinaryAttackStage()<0||e.rifleStanceLevel(partial)>.01F)return;
        String clip=EvaGameplayMotionR32.activeGroundClip(e,partial);
        if(!clip.equals("jab")&&!clip.equals("cross")&&!clip.equals("hook"))return;
        // Held while the arm stays out, gone by the time it has come back.
        float phase=EvaGameplayMotionR32.phase(e,clip,EvaGameplayMotionR32.activeGroundPhase(e,partial)),contact=EvaGameplayMotionR32.contactPhase(e,clip);
        float weight=EvaDorsalMechanism.smooth(phase/contact)*(1-EvaDorsalMechanism.smooth((phase-contact-HELD)/LEAVING));
        if(weight<=0||!body.rig.containsKey("torso_upper"))return;
        var chest=body.matrix("torso_upper").transformPosition(new Vector3f(body.rig.get("torso_upper").pivot()));
        var left=fist(body,"l");
        var right=fist(body,"r");
        var fist=left.z<right.z?left:right;
        // Model forward is -z and the EVA's right +x: turn about the chest until the fist's x is zero.
        float x=fist.x-chest.x,forward=chest.z-fist.z,reach=Mth.sqrt(x*x+forward*forward);
        if(reach<1e-3F||Math.abs(chest.x)>=reach)return;
        float turn=(float)Math.toDegrees(-Math.asin(chest.x/reach)-Math.atan2(x,forward))*weight;
        turn=Mth.clamp(turn,-MOST_DEGREES,MOST_DEGREES);
        EvaStrideHeadingR59.turn(body,"torso_upper",turn);
        EvaStrideHeadingR59.turn(body,"neck",-turn*NECK);
    }

    private static Vector3f fist(EvaBodyPose.Sample body,String side)
    {
        return body.matrix("hand_"+side).transformPosition(new Vector3f(body.rig.get("hand_"+side).pivot()));
    }
}

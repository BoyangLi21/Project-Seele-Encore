package com.projectseele.client.render;

import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * R65: what the hips and the legs give a punch thrown from a stand.
 * <p>
 * The owner, 2026-11-22, of the left and right punches: "不要只有胳膊在动：腿、胯、躯干也要稍微有点动作，比如重心转移、
 * 后脚跟着转、胯随出拳转一点，不然太僵". Measured on the jab and the cross as R65 shipped them: the chest turns 44 and
 * 35 degrees with the blow and leans 20 to 34, and under it the pelvis does not turn a tenth of a degree, does not
 * move a tenth of a block, and the knees keep one angle: the planted movement model stands the pelvis over the feet
 * and takes nothing from the punch's clip but the trunk and the arms.
 * <p>
 * Here the pelvis takes a share of the chest's own turn, so the hips go with the shoulder that punches and the
 * waist twists less; the chest is turned back by as much, so the chest, the arms and the fist are where they were
 * (the blow is aimed and lands as before; what lands is decided on the server and is not touched). With the turn
 * the weight goes a little ahead and onto the foot away from the punching side, the pelvis sinks a little, and
 * the foot on the punching side comes up on its toes and turns on them, heel out, as a foot does that drives a
 * blow. The toes of that foot stay where they stand, the other foot stays flat: nothing slides. All of it follows
 * the chest's turn frame by frame, so it leads into the blow and comes back with the arm, and a second blow
 * from the other side swings the hips through.
 */
final class EvaPunchBodyR65
{
    /** The pelvis takes this share of the chest's turn against it. */
    private static final float SHARE=.3F;
    /** The rest is in full at this much turn of the chest against the pelvis (degrees). */
    private static final float FULL=36F;
    /** Blocks the pelvis goes ahead, toward the foot away from the punching side, and down. */
    private static final float AHEAD=1.0F,ASIDE=.6F,DOWN=.35F;
    /** Degrees the driving foot's heel comes up, and the foot turns on its toes. */
    private static final float HEEL=13F,PIVOT=9F;
    private static final boolean ENABLED=!Boolean.getBoolean("projectseele.noPunchBodyR65");

    /**
     * What a punch gives: the pelvis' turn (radians about the body's vertical, + toward its left), its shift ahead
     * and to the body's left and down (blocks), which foot drives (0 left, 1 right), how far that foot's heel is
     * up (degrees) and how far the foot is turned on its toes (degrees of Minecraft yaw, + clockwise from above),
     * and where the point that foot turns about is from its ankle: ahead and to the foot's left, in the model's units.
     */
    record Give(float turn,float ahead,float left,float down,int foot,float heel,float pivot,float toeAhead,float toeLeft){}

    /** The give of the frame in hand, or null where no punch from a stand is being thrown. The trunk is turned here. */
    static Give apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(!ENABLED)return null;
        String clip=EvaGameplayMotionR32.activeGroundClip(eva,partial);
        if(!clip.equals("jab")&&!clip.equals("cross")||!EvaGameplayMotionR32.ready(eva))return null;
        var pelvis=model.getBone("torso_lower").orElse(null);var chest=model.getBone("torso_upper").orElse(null);
        if(pelvis==null||chest==null)return null;
        // The chest as it will be drawn: the jab's clip wrings the waist 59 degrees, and the final pose holds it to
        // 45. Held to that now, the pelvis takes its share of what is drawn, and the chest ends where it did.
        EvaJointLimitsR57.limit(model,"torso_upper");
        var lower=new Quaternionf().rotationZYX(pelvis.getRotZ(),pelvis.getRotY(),pelvis.getRotX());
        var upper=new Quaternionf().rotationZYX(chest.getRotZ(),chest.getRotY(),chest.getRotX());
        // The chest's facing as the pelvis has it: the model faces -z, its right is +x.
        var facing=upper.transform(new Vector3f(0,0,-1));
        float right=(float)Mth.atan2(facing.x,-facing.z);
        if(Math.abs(right)<1e-3F)return null;
        float turn=-SHARE*right;
        // The pelvis about the body's vertical, the chest back by as much: it stays as the clip has it in the world.
        var turned=new Quaternionf().rotationY(turn).mul(lower);
        EvaRigTransforms.rotate(pelvis,turned);
        EvaRigTransforms.rotate(chest,new Quaternionf(turned).conjugate().mul(lower).mul(upper));
        float t=Mth.clamp(Math.abs(right)*Mth.RAD_TO_DEG/FULL,0,1),much=t*t*(3-2*t);
        // The chest turned to the right: the left shoulder punches, the left foot drives, the weight goes right.
        boolean leftDrives=right>0;
        // The model's right is +x and it faces -z.
        var toe=com.projectseele.entity.EvaCombatSupportR33.toe(eva,leftDrives?"l":"r");
        return new Give(turn,AHEAD*much,leftDrives?-ASIDE*much:ASIDE*much,DOWN*much,leftDrives?0:1,HEEL*much,leftDrives?PIVOT*much:-PIVOT*much,-toe.z,-toe.x);
    }

    private EvaPunchBodyR65(){}
}

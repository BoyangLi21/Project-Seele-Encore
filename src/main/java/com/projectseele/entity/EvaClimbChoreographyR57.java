package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Vector3f;
import static com.projectseele.entity.EvaKeyPosesR57.*;

/**
 * Climbing a ledge 21-44 blocks high (waist to chest height on the EVA):
 * both hands are set on the top and stay there while the server carries
 * the body up the climb path, the arms going from reaching to pressing
 * down; once the hips clear the edge the right foot is set on the top, the
 * body rises over it and the left leg follows.
 * <p>
 * The source capture hopped both knees up to the chest and folded over the
 * edge (chest past horizontal): on the EVA the back armour and pylons
 * stacked into a ball. Here the chest leans at most about 30 degrees.
 */
final class EvaClimbChoreographyR57
{
    // Hands on the top, chest over them, legs still under the body.
    private static final Key PLANT=key(0,-12,0,0,-10,0,0,10,0,0,6,0,-4,6,0,4,-12,0,0,-12,0,0,0,0,0,0,0,0,70,0,-8,70,0,8,25,0,0,25,0,0);
    // Pressing up, legs hanging, toes pointed.
    private static final Key PRESS=key(0,-18,0,0,-12,0,0,14,0,0,10,0,-4,16,0,4,-18,0,0,-26,0,0,-25,0,0,-25,0,0,25,0,-8,25,0,8,8,0,0,8,0,0);
    // Right knee over the edge.
    private static final Key KNEE=key(0,-20,0,0,-12,0,0,16,0,0,-6,0,-4,95,0,6,-24,0,0,-115,0,0,-25,0,0,20,0,0,15,0,-10,15,0,10,6,0,0,6,0,0);
    // Standing up over the right foot, the left leg swinging through.
    private static final Key STEP=key(0,-12,0,0,-8,0,0,10,0,0,40,0,-6,45,0,6,-90,0,0,-55,0,0,-10,0,0,10,0,0,25,0,-20,25,0,20,25,0,0,25,0,0);
    private static final Key[] KEYS={null,PLANT,PRESS,KNEE,STEP,null};
    /** Clip progress at each key: the climb path rises 10%, 60% and 100% of the ledge at 0.07, 0.37 and 0.54. */
    private static final float[] AT={0,.07F,.37F,.54F,.85F,1};
    /** Half the EVA's width, and the gap to the wall it climbs (blocks). */
    private static final float HALF=EvaScale.NORMAL_WIDTH*.5F,GAP=1;

    /**
     * progress: the climb clip's 0..1; rise and advance: the server path's
     * share of the ledge height and forward travel at this progress; height
     * and travel: the ledge's, in blocks.
     */
    static EvaBodyPose.Sample pose(EvaBodyPose.Sample base,float progress,float rise,float advance,float height,float travel)
    {
        var pose=play(base,KEYS,stations(progress,AT));
        // The top and the wall face, in pose space (model units of five blocks).
        float top=height*(1-rise)/5F,face=-(HALF+GAP-travel*advance)/5F;
        float hands=ease(Math.min(1,progress/.08F))*(1-ease((progress-.72F)/.16F));
        if(hands>0)for(String side:new String[]{"l","r"})
        {
            var shoulder=pose.matrix("arm_"+side).transformPosition(new Vector3f(pose.rig.get("arm_"+side).pivot()));
            var target=new Vector3f(shoulder.x*1.25F,top,face-.5F);
            // Elbows point back and out, as when pressing down on a wall top.
            reach(pose,"arm_"+side,"forearm_"+side,"hand_"+side,target,new Vector3f(Math.signum(shoulder.x)*.6F,-.2F,1),hands);
        }
        float foot=ease((progress-.4F)/.12F)*(1-ease((progress-.9F)/.1F));
        if(foot>0)
        {
            var hip=pose.matrix("leg_r").transformPosition(new Vector3f(pose.rig.get("leg_r").pivot()));
            // The ankle stands 1.16 units above the sole.
            reach(pose,"leg_r","shin_r","foot_r",new Vector3f(hip.x,top+1.16F,face-1.1F),new Vector3f(0,.5F,-1),foot);
        }
        return pose;
    }
    private EvaClimbChoreographyR57(){}
}

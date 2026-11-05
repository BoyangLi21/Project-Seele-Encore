package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Vector3f;
import static com.projectseele.entity.EvaKeyPosesR57.*;

/**
 * Space at a ledge taller than a step, by its height on the body (the EVA's
 * hip stands 34 blocks up, its shoulders 46, its reach overhead about 67):
 * <ul>
 * <li>up to hip height, a step up: the right knee lifts and sets the foot on
 * the top, the body drives up over it and the left leg comes through;</li>
 * <li>above that, a climb: the hands reach up and take the edge, the body
 * hangs and pulls up until the chest is over the top, presses up on
 * straight arms, sets the right knee and foot on the top and stands.</li>
 * </ul>
 * One clip for both read wrong at either end: a hip-high ledge was hoisted
 * onto with both hands like a wall, and nothing above the shoulders could
 * be climbed at all. The server carries the body along {@link #path}; the
 * hands and the right foot are set against the ledge where it is drawn.
 */
final class EvaClimbChoreographyR57
{
    /** Ledges up to this high (blocks above the feet) are stepped up onto; higher ones climbed. */
    static final double STEP_UP_HIGH=35;

    // Step up: a dip, weight on the left leg, the right knee starting up; it
    // rises above the top's height before it goes forward over the edge.
    private static final Key S_PREP=key(-.16F,-10,0,0,-6,0,0,6,0,0,22,0,-4,20,0,6,-44,0,0,-40,0,0,20,0,0,5,0,0,-15,0,-12,20,0,10,25,0,0,25,0,0);
    // Knee lifted, foot on the top, the left leg straight beneath.
    private static final Key S_LIFT=key(7.61F,-18,0,0,-12,0,0,14,0,0,18,0,-4,128,0,6,-5,0,0,-118,0,0,0,0,0,20,0,0,-20,0,-15,55,0,10,25,0,0,20,0,0);
    // Driving up over the right foot, chest forward, the left foot pushing off
    // on its toes beneath the body (trailed behind, the leg floated back).
    private static final Key S_DRIVE=key(0,-32,0,0,-14,0,0,24,0,0,28,0,-4,127,0,6,-25,0,0,-100,0,0,-45,0,0,5,0,0,-35,0,-20,40,0,10,25,0,0,20,0,0);
    // Up on the right leg, the left knee coming through.
    private static final Key S_STEP=key(4.5F,-12,0,0,-6,0,0,10,0,0,82,0,-6,37,0,6,-110,0,0,-25,0,0,-10,0,0,10,0,0,25,0,-10,-15,0,10,30,0,0,25,0,0);
    private static final Key[] STEP_KEYS={null,S_PREP,S_LIFT,S_DRIVE,S_STEP,null};
    private static final float[] STEP_AT={0,.12F,.3F,.55F,.8F,1};

    // Climb: a dip before the reach, hands drawn up to the chest.
    private static final Key C_CROUCH=key(-9.17F,-12,0,0,-8,0,0,10,0,0,40,0,-6,40,0,6,-70,0,0,-70,0,0,25,0,0,25,0,0,15,0,-25,15,0,25,115,0,0,115,0,0);
    // Both arms up to the edge, up on the toes, looking up.
    private static final Key C_REACH=key(0,-4,0,0,-6,0,0,-18,0,0,5,0,-4,5,0,4,-8,0,0,-8,0,0,-30,0,0,-30,0,0,172,0,6,172,0,-6,10,0,0,10,0,0);
    // Hanging from the edge, legs straight down, toes pointed. Hanging and
    // pressing, the legs hang plumb whatever the chest's lean: bent back from
    // the knees they floated out behind the body.
    private static final Key C_HANG=key(0,0,0,0,0,0,0,-10,0,0,3,0,-4,6,0,4,-12,0,0,-18,0,0,-25,0,0,-25,0,0,178,0,6,178,0,-6,5,0,0,5,0,0);
    // Pulled up, elbows bent, the right knee braced against the wall.
    private static final Key C_PULL=key(0,0,0,0,-6,0,0,10,0,0,3,0,-4,25,0,4,-15,0,0,-40,0,0,-20,0,0,-20,0,0,150,0,20,150,0,-20,110,0,0,110,0,0);
    // Pressed up on straight arms, chest over the top, legs hanging.
    private static final Key C_PRESS=key(0,-35,0,0,-15,0,0,25,0,0,35,0,-4,39,0,4,-15,0,0,-20,0,0,-25,0,0,-25,0,0,20,0,-10,20,0,10,5,0,0,5,0,0);
    // Right knee up and the foot on the top.
    private static final Key C_KNEE=key(0,-30,0,0,-10,0,0,20,0,0,30,0,-4,125,0,6,-20,0,0,-125,0,0,-25,0,0,20,0,0,35,0,-12,35,0,12,10,0,0,10,0,0);
    // Standing up over the right foot, the left leg swinging through.
    private static final Key C_RISE=key(0,-15,0,0,-5,0,0,10,0,0,75,0,-6,60,0,6,-110,0,0,-70,0,0,-20,0,0,10,0,0,20,0,-15,20,0,15,30,0,0,30,0,0);
    // Pressed up, the legs hang until the hips are ten blocks over the top:
    // swung up from lower, the right knee went into the wall below the edge.
    private static final Key[] CLIMB_KEYS={null,C_CROUCH,C_REACH,C_HANG,C_PULL,C_PRESS,C_PRESS,C_KNEE,C_RISE,null};
    private static final float[] CLIMB_AT={0,.07F,.14F,.24F,.45F,.6F,.72F,.82F,.91F,1};
    /** Progress at which the body has risen this far (blocks), by landmark: hanging, chest at the edge, hips at it, foot on it, up. */
    private static final float[] CLIMB_RISE_AT={.2F,.45F,.6F,.8F,.91F};

    /** Half the EVA's width, and the gap to the wall it climbs (blocks). */
    private static final float HALF=EvaScale.NORMAL_WIDTH*.5F,GAP=1;
    /** Parts kept out of the ledge's face, and the gap left to it (model units: one block). */
    private static final java.util.List<String> FRONT=java.util.List.of("torso_lower","torso_upper","leg_l","shin_l"),RIGHT_LEG=java.util.List.of("leg_r","shin_r");
    /** Within this of the top (model units) a part lets go of the face gradually. */
    private static final float CLEAR=.2F,FADE=.6F;
    /** Furthest the climbing body is drawn in towards the wall (model units). */
    private static final float APPROACH=.4F;
    /** Furthest the body is drawn back off the wall (model units): pushed back nine blocks, it slid away from the wall it was climbing. */
    private static final float PUSH=.5F;

    static boolean stepUp(double height){return height<=STEP_UP_HIGH;}
    /** Length of the move (ticks) for a ledge this high. */
    static int ticks(double height){return stepUp(height)?28:50;}

    /**
     * {rise, advance} of the body at progress, each 0..1 of the ledge's
     * height and the travel onto it. It moves forward only once it is nearly
     * up, and is done a little early: the client's position trails the
     * server's, and the end syncs it, so it must be standing still by then.
     */
    static float[] path(double height,float progress)
    {
        float p=Mth.clamp(progress,0,1),rise;
        // Stepping up, the left leg first drives the body up a third of the
        // ledge, so the right foot is set on the top from well above it: set
        // there from the ground, it had to come up level with the hip, past
        // the joints' reach, and the leg folded over backwards.
        if(stepUp(height))rise=.3F*ease((p-.08F)/.2F)+.7F*ease((p-.3F)/.42F);
        else
        {
            // Up through the landmarks without stopping on them: shoulders
            // over the edge, then hips, then the foot set on it, then standing.
            float h=(float)height,chest=Math.max(0,h-42),hips=Math.max(chest,h-32),foot=Math.max(hips,h-17);
            rise=Mth.clamp(through(stations(p,CLIMB_RISE_AT),0,chest,hips,foot,h),0,h)/h;
            if(p>=CLIMB_RISE_AT[CLIMB_RISE_AT.length-1])rise=1;
        }
        float from=stepUp(height)?.66F:.88F,to=stepUp(height)?.9F:.97F;
        return new float[]{rise,ease((p-from)/(to-from))};
    }
    /** Catmull-Rom through v at index position s. */
    private static float through(float s,float... v)
    {
        int i=Mth.clamp((int)Math.floor(s),0,v.length-2);float t=Mth.clamp(s-i,0,1);
        float a=v[Math.max(0,i-1)],b=v[i],c=v[i+1],d=v[Math.min(v.length-1,i+2)],t2=t*t,t3=t2*t;
        return .5F*(2*b+(c-a)*t+(2*a-5*b+4*c-d)*t2+(3*b-a-3*c+d)*t3);
    }

    /**
     * progress: the move's 0..1; rise and advance: the share of the ledge
     * height and travel the drawn body has covered; height and travel: the
     * ledge's, in blocks.
     */
    static EvaBodyPose.Sample pose(EvaUnit01Entity e,EvaBodyPose.Sample base,float progress,float rise,float advance,float height,float travel)
    {
        boolean step=stepUp(height);
        var pose=play(base,step?STEP_KEYS:CLIMB_KEYS,stations(progress,step?STEP_AT:CLIMB_AT));
        // The top and the wall face, in pose space (model units of five blocks).
        float top=height*(1-rise)/5F,face=-(HALF+GAP-travel*advance)/5F;
        // Climbing, drawn as close to the wall as the body allows: the chest,
        // hips and legs below the top close to a block short of the face as
        // the move begins; neither move lets them into it, leaning over or not
        // (the horn is let through). The body is let back as it moves forward
        // onto the top. Pushed a set five blocks nearer, the chest went three
        // into the wall; a step up keeps its distance, the knee's room to rise.
        // The right leg is let go of the face only as its foot lifts over the
        // edge: held to it, the leg about to step over pushed the whole body
        // eight blocks back, and the foot, out of reach, twisted behind. The
        // approach is set by the body alone and capped, so the leg letting go
        // does not pull the body at the wall.
        float lift=step?.03F:.68F,start=step?.2F:.78F,span=step?.16F:.1F;
        float rise_=ease((progress-start)/(span*.6F)),in=ease((progress-start-span*.4F)/(span*.6F));
        float body=EvaBodyPose.frontBelow(e,pose,FRONT,top,FADE)-(face+CLEAR);
        float room=Math.min(body,EvaBodyPose.frontBelow(e,pose,RIGHT_LEG,top,FADE)+2*(step?ease((progress-lift)/.04F):rise_)-(face+CLEAR));
        if(Float.isFinite(room))
        {
            float close=Math.max(-PUSH,Math.min(room,step||!Float.isFinite(body)?0:Mth.clamp(body,0,APPROACH)*ease(progress/.2F)*(1-advance)));
            pose.positions.get("root").z-=close;pose.dirty();
        }
        if(!step)
        {
            // The hands slide up the face, take the edge, move onto the top as
            // the body presses up, and keep it until the body stands over the
            // foot on the top. Gripping the top four blocks in from the edge
            // while the shoulders hung below it, the forearms cut the corner.
            // Swung up in front of the body, they passed through the wall.
            float hands=ease((progress-.02F)/.03F)*(1-ease((progress-.8F)/.1F));
            float from=ease((progress-.02F)/.06F),up=ease((progress-.04F)/.08F),over=ease((progress-.11F)/.04F),press=ease((progress-.45F)/.15F);
            if(hands>0)for(String side:new String[]{"l","r"})
            {
                var shoulder=pose.matrix("arm_"+side).transformPosition(new Vector3f(pose.rig.get("arm_"+side).pivot()));
                float out=Math.signum(shoulder.x);
                var path=new Vector3f(shoulder.x*1.1F,Mth.lerp(over,Mth.lerp(up,shoulder.y,top+.3F),top+.2F*(1-press)),Mth.lerp(over,face+.9F,Mth.lerp(press,face+.1F,face-.3F)));
                // From where the keys hold the hand, never into the face: the
                // wrist kept nearly a unit off it, the hand's own length.
                var target=pose.matrix("hand_"+side).transformPosition(new Vector3f(pose.rig.get("hand_"+side).pivot())).lerp(path,from);
                if(target.y<top)target.z=Math.max(target.z,face+.9F);
                // The elbows point back and out, off the wall: pointed down and
                // out, with the hand above the shoulder the elbow went forward
                // three blocks into the wall.
                var pole=new Vector3f(out*.6F,-.25F,1);
                reach(pose,"arm_"+side,"forearm_"+side,"hand_"+side,target,pole,hands);
            }
        }
        // The right foot follows its keys, knee up, kept out of the face below
        // the edge; then it rises clear of the edge and comes down just past
        // it, flat, and is handed back to the ground pose at the end only once
        // the body is up. Steered instead to a point above the edge, with the
        // body drawn against the wall that point lay at the hip a block or
        // two in front of it, and the leg folded back over it.
        float foot=ease((progress-lift)/.04F)*Math.max(1-ease((progress-.9F)/.1F),Mth.clamp(top/.1F,0,1));
        if(foot>0)
        {
            var hip=pose.matrix("leg_r").transformPosition(new Vector3f(pose.rig.get("leg_r").pivot()));
            var target=pose.matrix("foot_r").transformPosition(new Vector3f(pose.rig.get("foot_r").pivot()));
            // The ankle stands 1.16 units above the sole.
            target.set(Mth.lerp(in,target.x,hip.x),Mth.lerp(rise_,target.y,top+1.2F),Mth.lerp(in,target.z,face-.6F));
            // Below the top the toes, a unit ahead of the ankle, stay out of the
            // face; the hold lets go as the sole rises clear of the edge.
            target.z=Math.max(target.z,face+1.3F*(1-ease((target.y-top-.6F)/.6F)));
            reach(pose,"leg_r","shin_r","foot_r",target,new Vector3f(0,1,-1),foot);
            level(pose,"foot_r",foot*rise_);
        }
        return pose;
    }
    private EvaClimbChoreographyR57(){}
}

package com.projectseele.client.render;

import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import java.util.HashMap;
import java.util.Map;

/**
 * The moment a launched unit is let go by its rack.
 * <p>
 * Under the logistics lock the body is drawn held, in a cage in its structural bind pose, through
 * the ascent and for as long as the surface holds it. When the launch ended and the lock opened,
 * the live stance replaced that pose within one frame: a hand turned eighty degrees, the knees
 * bent and the pelvis dropped most of a block at once. Pose continuity did not catch it (the key
 * stays the same and no single core bone turns far enough to count as a pop), and a tenth of a
 * second of smoothing would not have been a landing anyway.
 * <p>
 * The unit now takes its own weight. From the last pose drawn under the lock the body flows into
 * the live one, the arms after the trunk, while the pelvis sinks past the stance on bending
 * knees and comes back up. Only a release at the end of a launch is treated this way.
 * <p>
 * There are two launches. The unit's own launch sequence carries it up on its rack and stops at
 * the surface. The facility's route (NervAssemblyOwnerR52) never starts that sequence: it moves
 * the unit in the mechanical frame of EvaMechanicalFrameR52, throws it out of the shaft and
 * opens the lock in the tick it comes down on the closed hatch. Either one counts here, and a
 * unit that comes down keeps the speed of its fall into the sink.
 */
public final class EvaRackReleaseR63
{
    /** Seconds over which the trunk and legs, the head, and the arms and hands leave the locked pose. */
    private static final float BODY=.4F,HEAD=.6F,ARMS=.85F;
    /** How far the pelvis sinks below the stance (blocks), when it is lowest, and when it has come back (seconds). */
    private static final float SINK=2.4F,SINK_AT=.32F,BACK_FROM=1.2F,END=1.7F;
    /**
     * The sink eases in over this long (seconds). A straight leg folds by the square root of how far
     * its hip comes down: without the ease the knees broke at full speed in the very first frame.
     */
    private static final float SINK_EASE=.12F;
    /** At its lowest the chest has given this far forward over the waist (radians); the head stays level by its share. */
    private static final float GIVE=.07F,HEAD_SHARE=.6F;
    /** The lock opening this soon after the launch sequence or the mechanical frame was last seen ends that launch (seconds). */
    private static final float AFTER_LAUNCH=.6F;
    /**
     * A unit that comes down at more than the first speed (blocks per second) goes on down at that
     * speed, losing it over the given time (seconds); the second speed is the most that counts, and
     * the sink never passes the last figure (blocks).
     */
    private static final float FALL_FROM=4F,FALL_MOST=40F,FALL_TIME=.2F,MOST_SINK=4.5F;
    /** The settle advances by at most this much per frame (seconds): a long frame slows it down, it does not skip ahead. */
    private static final float LONGEST_STEP=.05F;
    /** Bones that follow the body; weapons, the plug and the dorsal machinery keep their own state. */
    private static final String[] BODY_BONES={"root","torso","aim_pitch","leg_","shin_","ankle_","foot_","toe_"};
    private static final String[] HEAD_BONES={"neck","head","horn"};
    private static final String[] ARM_BONES={"clavicle_","arm_","forearm_","wrist_","hand_","finger_","r45_hand_"};
    private static final long NEVER=Long.MIN_VALUE;
    private static final class State
    {
        long frame=NEVER,launch=NEVER,released=NEVER;
        boolean locked;
        /** Seconds of the settle played so far, and how far the body is drawn below its stance this frame (blocks). */
        float clock,sink;
        /** Where the held body was drawn last frame (world y), how fast it was coming down, and the speed it landed with (blocks per second). */
        float height=Float.NaN,fall,impact;
        /** The pilot's eye as the held unit's fixed seat gave it, from the unit's position. */
        Vec3 eye;
        final Map<String,float[]> held=new HashMap<>();
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    /** Last in the pose graph, once the soles are on the ground and before the joints are re-seated. */
    static void apply(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        long now=AircraftRenderClockR21.frameNanos();
        // The lock itself, whichever owner draws the held body (the bind pose in a cage, the frozen pose of the frame).
        boolean locked=eva.isNervLogisticsLocked();
        boolean launching=eva.isLaunchSequenceActive()||com.projectseele.entity.EvaMechanicalFrameR52.active(eva);
        State s=STATES.get(eva);
        if(s==null)
        {
            // Nothing to follow for a unit that is neither held nor launching.
            if(!locked||!launching)return;
            s=new State();STATES.put(eva,s);
            // What standing on the ground needs is first read when the unit first stands: on the frame
            // after the release, where the hitch cut a tenth of a second out of the landing. The cage
            // is the place for it.
            EvaGroundContactR56.warm(eva);EvaFootPlacement.warm(eva);
        }
        // A shader pack draws the body twice in a frame: the second pass repeats the first.
        if(now!=s.frame)
        {
            if(launching)s.launch=now;
            boolean recent=s.launch!=NEVER&&now-s.launch<AFTER_LAUNCH*1e9F;
            if(locked)
            {
                s.released=NEVER;
                // Held again long after its launch (parked, under repair): nothing to prepare for.
                if(!recent){STATES.remove(eva);return;}
                // How fast the held body is coming down, over the last tenth of a second.
                if(root!=null)
                {
                    float dt=s.frame==NEVER?0:(now-s.frame)/1e9F;
                    if(Float.isFinite(s.height)&&dt>0&&dt<.25F)s.fall+=((s.height-root.m31())/dt-s.fall)*(1-(float)Math.exp(-dt/.08F));
                    s.height=root.m31();
                }
            }
            else if(s.released==NEVER)
            {
                if(s.locked&&recent&&s.frame!=NEVER&&now-s.frame<300_000_000L&&eva.isPoweredOn()&&!s.held.isEmpty())
                {
                    s.released=now;s.clock=0;
                    s.impact=s.fall>FALL_FROM?Math.min(FALL_MOST,s.fall):0;
                }
                else if(!recent){STATES.remove(eva);return;}
            }
            else s.clock+=Math.min(LONGEST_STEP,(now-s.frame)/1e9F);
            s.locked=locked;s.frame=now;
        }
        if(locked)
        {
            for(GeoBone bone:model.topLevelBones())remember(bone,s.held);
            return;
        }
        s.sink=0;
        if(s.released==NEVER)return;
        float t=s.clock;
        if(t>=END){STATES.remove(eva);return;}
        for(GeoBone bone:model.topLevelBones())follow(bone,s.held,t);
        // Its weight coming onto the legs, and on top of that the speed it came down with.
        float x=t/SINK_AT,weight=SINK*x*x*(float)Math.exp(2*(1-x))*smooth(t/SINK_EASE),landing=s.impact*t*(float)Math.exp(-t/FALL_TIME);
        float sink=Math.min(MOST_SINK,weight+landing)*(1-smooth((t-BACK_FROM)/(END-BACK_FROM)));
        GeoBone base=model.getBone("root").orElse(null);
        if(sink<.005F||root==null||base==null||!EvaGroundContactR56.applies(eva))return;
        float give=GIVE*sink/SINK;
        // Negative X pitches the chest forward on this rig (the stance itself stands at -0.16).
        model.getBone("torso_upper").ifPresent(b->b.setRotX(b.getRotX()-give));
        model.getBone("head").ifPresent(b->b.setRotX(b.getRotX()+give*HEAD_SHARE));
        // The whole body goes down and each leg folds by as much, so both soles stay where they stand.
        s.sink=sink;
        base.setPosY(base.getPosY()-sink*16/EvaScale.RENDER_SCALE);
        EvaGroundContactR56.reachGround(model,root,"l",-sink);
        EvaGroundContactR56.reachGround(model,root,"r",-sink);
    }

    /**
     * The pilot's eye through the release. A held unit seats the pilot at a fixed point, a live one
     * at its head: the view jumped 1.9 blocks up in the frame the lock opened. It now goes from the
     * one to the other with the trunk, and down with the body, or the landing would be something
     * only bystanders see. The camera is placed before the body is posed, so it follows by a frame.
     */
    public static Vec3 seat(EvaUnit01Entity eva,float partial,Vec3 live)
    {
        State s=STATES.get(eva);
        if(s==null)return live;
        Vec3 at=eva.getPosition(partial);
        if(eva.isNervLogisticsLocked()){s.eye=live.subtract(at);return live;}
        if(s.eye==null||AircraftRenderClockR21.frameNanos()-s.frame>100_000_000L)return live;
        // The frame the lock opened, before the body has been posed: still where it was held.
        if(s.released==NEVER)return s.locked?at.add(s.eye):live;
        return at.add(s.eye.lerp(live.subtract(at),smooth(s.clock/BODY))).add(0,-s.sink,0);
    }

    /** True while the body is still leaving the locked pose: a pose between two standing ones can put a sole a hair under the ground. */
    static boolean active(EvaUnit01Entity eva)
    {
        State s=STATES.get(eva);
        return s!=null&&s.released!=NEVER;
    }

    private static void remember(GeoBone bone,Map<String,float[]> held)
    {
        if(duration(bone.getName())>0)
        {
            float[] h=held.computeIfAbsent(bone.getName(),k->new float[6]);
            h[0]=bone.getRotX();h[1]=bone.getRotY();h[2]=bone.getRotZ();h[3]=bone.getPosX();h[4]=bone.getPosY();h[5]=bone.getPosZ();
        }
        for(GeoBone child:bone.getChildBones())remember(child,held);
    }

    private static void follow(GeoBone bone,Map<String,float[]> held,float t)
    {
        float d=duration(bone.getName());float[] h=held.get(bone.getName());
        if(d>0&&h!=null&&t<d)
        {
            float w=smooth(t/d);
            Quaternionf from=new Quaternionf().rotationZYX(h[2],h[1],h[0]),to=new Quaternionf().rotationZYX(bone.getRotZ(),bone.getRotY(),bone.getRotX());
            EvaRigTransforms.rotate(bone,from.slerp(to,w));
            bone.setPosX(h[3]+(bone.getPosX()-h[3])*w);bone.setPosY(h[4]+(bone.getPosY()-h[4])*w);bone.setPosZ(h[5]+(bone.getPosZ()-h[5])*w);
        }
        for(GeoBone child:bone.getChildBones())follow(child,held,t);
    }

    /** Seconds a bone takes to leave the locked pose, or 0 for one that is not part of the body. */
    private static float duration(String name)
    {
        for(String p:ARM_BONES)if(name.startsWith(p))return ARMS;
        for(String p:HEAD_BONES)if(name.startsWith(p))return HEAD;
        for(String p:BODY_BONES)if(name.startsWith(p))return BODY;
        return 0;
    }

    private static float smooth(float x)
    {
        x=Math.max(0,Math.min(1,x));
        return x*x*(3-2*x);
    }

    private EvaRackReleaseR63() {}
}

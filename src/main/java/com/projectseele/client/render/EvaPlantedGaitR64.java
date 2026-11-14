package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.entity.CombatReactionsR36;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaCombatR31;
import com.projectseele.entity.EvaMechanicalFrameR52;
import com.projectseele.entity.EvaMotionModelR64;
import com.projectseele.entity.EvaObstacleCollision;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaSprintR50;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModSounds;
import com.projectseele.util.WeakIdentityMap;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.BlockTags;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.CollisionContext;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * R64 (M1): the planted model's legs and pelvis.
 * <p>
 * A foot is in one of two states. Standing, it keeps the place and heading it was set down with, whatever the
 * body does above it. Swinging, it goes from where it left the ground to the next footfall, which is chosen
 * ahead of the body: where the hip will be when the body is over that foot, and the foot's own side of it. A
 * clock that runs at the cadence of the body's speed says when each foot lands, the two half a cycle apart; the
 * gait says how long before that a foot leaves the ground. A body that has stopped steps its feet back under
 * itself and stops the clock, and one that turns on the spot steps after its turn. The pelvis is carried by the
 * feet: over the body, toward the foot that bears it, as high as both legs reach. The legs are solved to the
 * feet every frame; the clips keep the trunk, the arms and the head, on the phase of these steps.
 * <p>
 * Nothing here reads a clip's legs, so a foot cannot slide, stand on its toes through its stance or leave the
 * ground the body is not on: where it stands is the ground that was read under it.
 */
public final class EvaPlantedGaitR64
{
    /** Pose owner, for the blend into and out of this model. */
    public static final String OWNER="PLANTED_R64";
    /** Review witness, per EVA: see {@link #witness}. */
    public static final Map<Integer,double[]> LAST=new HashMap<>();
    private static final boolean DIAG=Boolean.getBoolean("projectseele.plantedDiagR64");

    /** Slower than this (blocks a second) the body stands. */
    private static final double MOVE_AT=.8;
    /**
     * Setting off, the first steps are quick and short: for this long (seconds) after the first foot is asked to
     * step the cadence is at least this (steps a second, falling back to the gait's own), and the foot leaves the
     * ground this soon. At the gait's own cadence for a crawl the first foot was in the air for 0.6 seconds while
     * the body went 14 blocks on from the other, which stood until both knees were folded.
     */
    private static final double START_BOOST=.7,START_CADENCE=2.1,START_SHIFT=.04;
    /** Walking forward the trunk is carried this far forward of where the clip holds it (degrees; the clip leans back 7). */
    private static final float POSTURE_LEAN=6F;
    /**
     * The heel comes up as the hip goes on ahead of its foot: from this share of the leg's length ahead, fully at
     * this, by this many degrees. By where the hip is and not by the clock: timed by the stance, a dash that
     * shortened the stance from under a standing foot stood it on its toes within one frame (27 degrees).
     */
    private static final double HEEL_FROM=.22,HEEL_FULL=.5;
    private static final float HEEL_OFF=28F;
    /** At the fast run: fully up at this share of the leg ahead, by this many degrees; the change begins at this speed. */
    private static final double HEEL_FULL_FAST=.68,HEEL_OFF_FAST=46,FAST_FROM=70;
    /** A swinging foot is over its footfall at this share of its swing, and comes down on it over the rest. */
    private static final float OVER_BY=.9F;
    /** How far ahead a turn is read on for where a foot will be set down (seconds). */
    private static final double TURN_AHEAD=.35;
    /** A standing foot steps once it is this far from its place (blocks) or turned this far from the body (degrees). */
    private static final float STEP_AT=2.6F,STEP_TURN=18F;
    /** With the body still for this long (seconds), a smaller leftover gets a tidying step. */
    private static final float TIDY_AT=.8F,TIDY_TURN=5F,TIDY_AFTER=.25F;
    /** From the decision to step to the foot leaving the ground (seconds): the weight goes to the other foot first. */
    private static final double WEIGHT_SHIFT=.1;
    /** Steps on the spot: the share of their cycle a foot stands, a step's time slow and at a quick turn, its lift. */
    private static final double SETTLE_DUTY=.56,SETTLE_SWING=.42,SETTLE_SWING_FAST=.30,SETTLE_LIFT=1.6;
    /** The body turns this fast (degrees a second) for the quickest steps on the spot. */
    private static final float SETTLE_TURN_FAST=80F;
    /** Where ground is looked for about the body's own level, and how far over that level a step may be (blocks). */
    private static final double GROUND_ABOVE=30,GROUND_BELOW=48,STEP_MOST=21.5;
    /** A foot stands at least this long (seconds), and is not lifted for a swing shorter than this. */
    private static final double MIN_STANCE=.06,MIN_SWING=.12;
    /** A step taken out of turn, because the leg no longer reached its foot (seconds). */
    private static final double QUICK_SWING=.22;
    /** A leg is drawn out to this share of its length at most. */
    private static final float REACH=.985F;
    /** The heel comes up this far at most as the body leaves a foot behind, the toes this far as it lands (degrees). */
    private static final float HEEL_OFF_MOST=55F,TOES_UP_MOST=16F;
    /** A foot further from the body than this share of the leg has been left by something else: the feet are set anew. */
    private static final double LOST_SHARE=1.6;
    /** Seconds over which the measured speed, the pelvis height, the bearing foot and the ground level are eased. */
    private static final double VELOCITY_EASE=.07,HEIGHT_EASE=.045,SUPPORT_EASE=.09,GROUND_EASE=.15;
    /** Each foot is turned out by this (degrees). */
    private static final float TOE_OUT=3F;
    /** Going sideways the feet are set this far either side of the body (blocks) and step at least this often a second. */
    private static final double WIDE_HALF=7,SIDE_CADENCE=1.9;
    /** A step backward is this long at most (blocks). */
    private static final double BACK_STEP=15;
    /** The pelvis goes this share of the way toward the bearing foot: on the spot, walking, running. */
    private static final double SWAY_SPOT=.45,SWAY_WALK=.3,SWAY_RUN=.14;
    /** The trunk tips this many degrees for each block a second squared it gathers, and banks as much into a turn; at most. */
    private static final float LEAN_GAIN=.045F,LEAN_MOST=7F,BANK_GAIN=.05F,BANK_MOST=9F;
    private static final float LEAN_RATE=9F;
    /** How far the pelvis gives at a footfall (blocks): a step on the spot, a walk, a run; and how fast it comes back (1/s). */
    private static final double DIP_SPOT=.25,DIP_WALK=.6,DIP_RUN=1.0,DIP_RATE=13;

    private static final class Foot
    {
        final String side;
        /** +1 for the left foot, -1 for the right. */
        final float sign;
        /** +1 where its hip is on the body's left in the world, -1 on its right: read off the rig, not its names. */
        float lat;
        /** When in the cycle it lands: the right at 0, the left half a cycle later. */
        final double offset;
        boolean down=true;
        /** Standing: the ground under the ankle of the flat foot, and its heading (Minecraft degrees). */
        double x,y,z;
        float yaw;
        /** Standing: seconds since it landed, and the pitch it landed with (degrees, toes up). */
        double stood,roll=.1;
        float strike;
        /** Swinging: the ankle and the foot as they left the ground, how far through (0 to 1), where to. */
        double fromX,fromY,fromZ,fromGround;
        float fromYaw,fromPitch,swing;
        /** Swinging by the clock: where in its own cycle it left the ground (it lands as its cycle begins again). */
        double liftLocal;
        double toX,toY,toZ;
        float toYaw;
        boolean quick;
        /** As drawn in the last frame: the ankle, the pitch (degrees, toes up). */
        double ankleX,ankleY,ankleZ;
        float pitch,drawnYaw,landWith;
        /** Swinging: seconds until it lands, and how long the swing was to be as it began. */
        double timeLeft,swingTime=.4;
        float support=1;
        double reachShort;
        Foot(String side,float sign,double offset){this.side=side;this.sign=sign;this.offset=offset;}
    }

    /** Lengths of the rig as it is drawn (blocks). */
    private record Rig(float scale,float hipHalf,float footHalf,float leg,float ankle,float toe,float heel){}

    private static final class State
    {
        long begun=Long.MIN_VALUE/2,applied=Long.MIN_VALUE/2,posed=Long.MIN_VALUE/2;
        float dt;
        boolean live,running,moving;
        Rig rig;
        double phase,cycle=1.5,duty=.62,swingSeconds=.5,stanceSeconds=.9,half=4,speed,land=.5,lift=3,sink=.4,bounce,forwardSpeed,lateral;
        double vx,vz,originX,originZ;
        float yaw,yawRate,still,landPitch,startAge=99;
        double height=Double.NaN,ground=Double.NaN,sway,fast,slow;
        float lean,leanRate,bank,bankRate;
        double lastStep,dip,dipRate;long lastSound;
        final Foot left=new Foot("l",1,.5),right=new Foot("r",-1,0);
    }

    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    private static boolean wanted(EvaUnit01Entity e,float partial)
    {
        return EvaMotionModelR64.walks(e)&&!e.hasLegacyStrikeForRender()&&EvaBodyPose.hasTerrainStances()
                &&e.getMotionLabPhysicsPreview()==0&&!e.isVisuallyAirborneForRender()&&!e.hasLiveActionForRender(partial)
                &&!e.hasActiveCarrierMotion()&&e.rifleStanceLevel(partial)<.02F&&e.getOrdinaryAttackStage()<0
                &&!e.isHeavyMotionActive()&&!e.isKickMotionActive(partial)&&!e.fixedCannonOperatingR52()
                &&EvaCombatR31.action(e)==EvaCombatR31.NONE&&!CombatReactionsR36.active(e)
                &&!EvaMechanicalFrameR52.serviceSourceHeldR52(e)&&!EvaShutdownR30.displayed(e)
                &&!com.projectseele.anim.EvaAnimator.owns(e,partial);
    }

    /** -Dprojectseele.plantedDiagR64=true: what keeps this model off a Unit that asked for it, logged when it changes. */
    private static String why(EvaUnit01Entity e,float partial)
    {
        if(!EvaMotionModelR64.planted(e))return "not asked for, or not a Unit it is built for";
        if(!EvaMotionModelR64.walks(e))
            return "not walking freely: powered "+e.isPoweredOn()+" first battle "+e.isFirstBattleActive()+" berserk "+e.isBerserk()+" locked "+e.isNervLogisticsLocked()
                    +" launch "+e.isLaunchSequenceActive()+" activation "+e.getActivationTicks()+" visual pose "+e.getVisualPose()+" weapon "+e.getWeapon()
                    +" prone "+e.isPilotProne()+" crouching "+e.isPilotCrouching()+" action "+e.hasLiveActionForRender(0)+" simulated "+com.projectseele.physics.CombatBodyDynamics.active(e);
        return "legacy strike "+e.hasLegacyStrikeForRender()+" stances "+EvaBodyPose.hasTerrainStances()+" preview "+e.getMotionLabPhysicsPreview()
                +" airborne "+e.isVisuallyAirborneForRender()+" action "+e.hasLiveActionForRender(partial)+" carrier "+e.hasActiveCarrierMotion()
                +" stance "+e.rifleStanceLevel(partial)+" attack "+e.getOrdinaryAttackStage()+" heavy "+e.isHeavyMotionActive()+" kick "+e.isKickMotionActive(partial)
                +" cannon "+e.fixedCannonOperatingR52()+" combat "+EvaCombatR31.action(e)+" reaction "+CombatReactionsR36.active(e)
                +" service "+EvaMechanicalFrameR52.serviceSourceHeldR52(e)+" shutdown "+EvaShutdownR30.displayed(e)+" animator "+com.projectseele.anim.EvaAnimator.owns(e,partial);
    }
    private static final Map<Integer,String> WHY=new HashMap<>();

    /**
     * First thing in a frame's pose: whether this model walks the body, and if it does its clock and its feet
     * are stepped on, so that the clips sampled after this are on the phase of its steps.
     */
    static boolean begin(EvaUnit01Entity eva,float partial)
    {
        long now=AircraftRenderClockR21.frameNanos();
        State s=STATES.get(eva);
        boolean wanted=wanted(eva,partial);
        if(DIAG)
        {
            // Only what is true or false, not the stance's own number, so a line is logged when something changes.
            String reason=wanted?"walks":why(eva,partial).replaceAll("stance [0-9.E-]+","stance");
            if(WHY.size()>64)WHY.clear();
            if(!reason.equals(WHY.put(eva.getId(),reason)))ProjectSeele.LOGGER.info("R64PLANT unit {} entity {}: {}",eva.getUnitVariant(),eva.getId(),wanted?"walks":why(eva,partial));
        }
        if(!wanted)
        {
            if(s!=null)s.live=false;
            eva.plantedClipReleaseR64();
            return false;
        }
        if(s==null)
        {
            s=new State();STATES.put(eva,s);
        }
        if(now!=s.begun)
        {
            // Not posed in the frame before: something else had the body, and the feet are where it left them.
            if(s.live&&now-s.applied>300_000_000L)s.live=false;
            s.dt=Mth.clamp((now-s.begun)/1e9F,0,.1F);
            s.begun=now;
            if(s.live)advance(s,eva,partial,s.dt);
        }
        if(s.live)eva.plantedClipPhaseR64(clipPhase(s,eva,partial));
        else eva.plantedClipReleaseR64();
        return true;
    }

    /** This model posed the body in this frame. */
    static boolean applied(EvaUnit01Entity eva)
    {
        State s=STATES.get(eva);
        return s!=null&&s.live&&s.applied==AircraftRenderClockR21.frameNanos();
    }

    /**
     * Where in the walking clips these steps are: the right foot lands at 0 here, at .20 of the walk, .31 of the
     * run and .36 of the fast run (the left half a cycle on in all of them).
     */
    private static float clipPhase(State s,EvaUnit01Entity eva,float partial)
    {
        float run=Mth.clamp(eva.rifleRunBlend(partial),0,1),dash=Mth.clamp(EvaSprintR50.blend(eva,partial),0,1);
        return (float)(s.phase+Mth.lerp(run*dash,Mth.lerp(run,.20F,.31F),.36F));
    }

    private static double frac(double value){return value-Math.floor(value);}

    private static void advance(State s,EvaUnit01Entity eva,float partial,float dt)
    {
        Rig rig=s.rig;
        s.originX=Mth.lerp((double)partial,eva.xOld,eva.getX());s.originZ=Mth.lerp((double)partial,eva.zOld,eva.getZ());
        double ease=1-Math.exp(-dt/VELOCITY_EASE);
        s.vx+=((eva.getX()-eva.xOld)*20-s.vx)*ease;s.vz+=((eva.getZ()-eva.zOld)*20-s.vz)*ease;
        s.yaw=Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot);
        float rate=Mth.wrapDegrees(eva.yBodyRot-eva.yBodyRotO)*20;
        s.yawRate+=(rate-s.yawRate)*(float)ease;
        double speed=Math.hypot(s.vx,s.vz);
        // A teleport, or a correction of the body's place: not a speed to step by.
        if(speed>400){s.live=false;return;}
        s.speed=speed;
        float radians=s.yaw*Mth.DEG_TO_RAD;
        double fx=-Mth.sin(radians),fz=Mth.cos(radians),lx=Mth.cos(radians),lz=Mth.sin(radians);
        s.forwardSpeed=s.vx*fx+s.vz*fz;
        double sideSpeed=s.vx*lx+s.vz*lz;
        s.lateral=speed>1e-3?Math.abs(sideSpeed)/speed:0;
        s.moving=speed>MOVE_AT;
        // By the speed the body has, whatever gave it that speed: a pilot whose synchronisation carries the body
        // slower walks and runs in the gait of that speed.
        var gait=EvaMotionModelR64.gait(EvaMotionModelR64.tier(eva),speed);
        double cadence=gait.cadence();
        s.startAge=Math.min(99,s.startAge+dt);
        if(s.moving)
        {
            if(s.startAge<START_BOOST)cadence=Math.max(cadence,Mth.lerp(s.startAge/START_BOOST,START_CADENCE,cadence));
            // Sideways and backward a leg cannot take a walking step's length: more steps of less.
            cadence=Math.max(cadence,SIDE_CADENCE*s.lateral*Math.min(1,speed/10));
            if(s.forwardSpeed<0)cadence=Math.max(cadence,-s.forwardSpeed/BACK_STEP);
            s.duty=gait.duty();s.cycle=2/cadence;s.land=gait.land();s.lift=gait.lift();s.sink=gait.sink();s.bounce=gait.bounce();
            double half=rig.footHalf()*gait.width();
            s.half=Mth.lerp(s.lateral*Math.min(1,speed/8),half,Math.max(half,WIDE_HALF));
            // Heel first at a walk going forward; flat at a run, and going sideways or backward.
            double walking=Mth.clamp((s.duty-.40)/.22,0,1),ahead=Mth.clamp(s.forwardSpeed/Math.max(speed,1e-3)*2-1,0,1);
            s.landPitch=(float)(Math.min(12,.45*speed)*walking*ahead);
        }
        else
        {
            double swing=Mth.lerp(Math.min(1,Math.abs(s.yawRate)/SETTLE_TURN_FAST),SETTLE_SWING,SETTLE_SWING_FAST);
            s.duty=SETTLE_DUTY;s.cycle=swing/(1-SETTLE_DUTY);s.land=.5;s.lift=SETTLE_LIFT;s.sink=gait.sink();s.bounce=0;
            s.half=rig.footHalf();s.landPitch=0;
        }
        s.swingSeconds=(1-s.duty)*s.cycle;s.stanceSeconds=s.duty*s.cycle;
        s.still=s.moving||Math.abs(rate)>1?0:s.still+dt;

        // The feet have been left behind by something that moved the body: set them anew.
        if(Double.isFinite(s.ground)&&Math.abs(s.ground-eva.getY())>rig.leg()*1.3){s.live=false;return;}
        double lost=rig.leg()*LOST_SHARE;
        for(Foot f:new Foot[]{s.left,s.right})
        {
            if(f.down&&Math.hypot(f.x-s.originX,f.z-s.originZ)>lost){s.live=false;return;}
            if(f.down)f.stood+=dt;
        }

        if(!s.running)
        {
            Foot first=null;
            if(s.moving)first=firstToStep(s);
            else
            {
                double left=lag(s,s.left),right=lag(s,s.right);
                if(Math.max(left,right)>=1)first=left>=right?s.left:s.right;
            }
            if(first!=null)
            {
                s.running=true;
                if(s.moving&&s.startAge>=START_BOOST)
                {
                    // Setting off: the clock is set for the first quick step as it will be timed.
                    s.startAge=0;
                    s.cycle=Math.min(s.cycle,2/START_CADENCE);s.swingSeconds=(1-s.duty)*s.cycle;s.stanceSeconds=s.duty*s.cycle;
                }
                s.phase=frac(first.offset+s.duty-(s.moving?START_SHIFT:WEIGHT_SHIFT)/s.cycle);
            }
        }
        if(s.running)
        {
            s.phase=frac(s.phase+dt/s.cycle);
            for(Foot f:new Foot[]{s.right,s.left})
            {
                Foot other=f==s.left?s.right:s.left;
                // A foot lands as its own cycle begins, always: the two land half a cycle apart whatever the
                // speed does meanwhile. What the gait decides is when it leaves the ground before that.
                double local=frac(s.phase-f.offset);
                if(f.down)
                {
                    boolean due=local>=s.duty&&(1-local)*s.cycle>=MIN_SWING&&(s.moving||lag(s,f)>=1)&&(other.down||s.duty<.5)&&f.stood>MIN_STANCE;
                    // A leg drawn out past its length would pull its foot off the ground: it steps at once and
                    // quickly, where the other foot stands and stays until it is down again.
                    double otherLocal=frac(s.phase-other.offset);
                    boolean stays=other.down&&(otherLocal<s.duty?(s.duty-otherLocal)*s.cycle:0)>QUICK_SWING+.04;
                    boolean over=!due&&f.reachShort>.6&&stays&&f.stood>MIN_STANCE;
                    if(due||over)lift(s,f,over);
                    if(due){f.liftLocal=local;f.swingTime=(1-local)*s.cycle;}
                }
                if(!f.down)
                {
                    boolean landed;
                    if(f.quick){f.swing+=dt/(float)QUICK_SWING;landed=f.swing>=1;}
                    else
                    {
                        landed=local<f.liftLocal;
                        f.swing=landed?1:(float)((local-f.liftLocal)/Math.max(1e-3,1-f.liftLocal));
                    }
                    retarget(s,eva,f,local);
                    if(landed)land(s,eva,f);
                }
            }
            if(!s.moving&&s.left.down&&s.right.down&&lag(s,s.left)<1&&lag(s,s.right)<1)s.running=false;
        }
        for(Foot f:new Foot[]{s.left,s.right})
        {
            // The weight leaves a foot a little before the foot leaves the ground.
            boolean bearing=f.down;
            if(f.down&&s.running&&(s.moving||lag(s,f)>=1))
            {
                double local=frac(s.phase-f.offset);
                if(local<s.duty&&(s.duty-local)*s.cycle<WEIGHT_SHIFT*1.3)bearing=false;
            }
            f.support+=((bearing?1:0)-f.support)*(float)(1-Math.exp(-dt/SUPPORT_EASE));
        }
        // The trunk: into the stride as the body gathers way, back over the feet as it brakes, into a turn.
        s.fast+=(s.forwardSpeed-s.fast)*(1-Math.exp(-dt/.08));
        s.slow+=(s.forwardSpeed-s.slow)*(1-Math.exp(-dt/.35));
        float leanTarget=Mth.clamp((float)((s.fast-s.slow)/.27)*LEAN_GAIN,-LEAN_MOST,LEAN_MOST);
        // And into its walk: the walking clip carries the chest behind the hips, which reads as held back at these
        // steps. A run's clip leans of itself.
        double walk=EvaMotionModelR64.tier(eva).walk();
        leanTarget+=POSTURE_LEAN*(float)(Mth.clamp(s.forwardSpeed/walk,-.4,1)*(1-.6*Mth.clamp((.62-s.duty)/.22,0,1)));
        float bankTarget=Mth.clamp(s.yawRate*Mth.DEG_TO_RAD*(float)s.fast*BANK_GAIN,-BANK_MOST,BANK_MOST);
        int steps=Math.max(1,Mth.ceil(dt/.004F));float h=dt/steps;
        for(int i=0;i<steps;i++)
        {
            s.dipRate+=(-2*DIP_RATE*s.dipRate-DIP_RATE*DIP_RATE*s.dip)*h;s.dip+=s.dipRate*h;
            s.leanRate+=(-2*LEAN_RATE*s.leanRate-LEAN_RATE*LEAN_RATE*(s.lean-leanTarget))*h;s.lean+=s.leanRate*h;
            s.bankRate+=(-2*LEAN_RATE*s.bankRate-LEAN_RATE*LEAN_RATE*(s.bank-bankTarget))*h;s.bank+=s.bankRate*h;
        }
    }

    /** The body's left in the world, for a heading in Minecraft degrees. */
    private static double leftX(float yaw){return Mth.cos(yaw*Mth.DEG_TO_RAD);}
    private static double leftZ(float yaw){return Mth.sin(yaw*Mth.DEG_TO_RAD);}

    /** How overdue a standing foot is for a step back under the body: 1 is due. */
    private static double lag(State s,Foot f)
    {
        boolean tidy=s.still>TIDY_AFTER;
        double side=f.lat*s.rig.footHalf();
        double x=s.originX+leftX(s.yaw)*side,z=s.originZ+leftZ(s.yaw)*side;
        double distance=Math.hypot(x-f.x,z-f.z),turn=Math.abs(Mth.wrapDegrees(s.yaw-f.lat*TOE_OUT-f.yaw));
        return Math.max(distance/(tidy?TIDY_AT:STEP_AT),turn/(tidy?TIDY_TURN:STEP_TURN));
    }

    /** From standing, the foot that is further behind on the way the body goes steps first; level, the one on the side it goes to. */
    private static Foot firstToStep(State s)
    {
        double speed=Math.max(s.speed,1e-3),dx=s.vx/speed,dz=s.vz/speed;
        double left=(s.left.x-s.originX)*dx+(s.left.z-s.originZ)*dz,right=(s.right.x-s.originX)*dx+(s.right.z-s.originZ)*dz;
        if(Math.abs(left-right)>1)return left<right?s.left:s.right;
        double toLeft=dx*leftX(s.yaw)+dz*leftZ(s.yaw);
        if(Math.abs(toLeft)>.3)return (toLeft>0)==(s.left.lat>0)?s.left:s.right;
        return s.lastStep>0?s.right:s.left;
    }

    private static void lift(State s,Foot f,boolean quick)
    {
        f.down=false;f.swing=0;f.quick=quick;f.liftLocal=0;f.landWith=0;f.swingTime=QUICK_SWING;
        f.fromX=f.ankleX;f.fromY=f.ankleY;f.fromZ=f.ankleZ;f.fromYaw=f.yaw;f.fromPitch=f.pitch;f.fromGround=f.y;
        f.toX=f.x;f.toY=f.y;f.toZ=f.z;f.toYaw=f.yaw;
        s.lastStep=f.sign;
    }

    /** The footfall of a swinging foot: under where its hip will be when the body is over it, on its own side. */
    private static void retarget(State s,EvaUnit01Entity eva,Foot f,double local)
    {
        double left=f.quick?(1-f.swing)*QUICK_SWING:f.swing>=1?0:(1-local)*s.cycle,ahead=left+s.land*s.stanceSeconds;
        f.timeLeft=left;
        // Over its footfall the foot only comes down: the footfall is settled. Chosen anew to the last frame, a
        // foot coming down through a curve went 0.9 blocks over the ground in its last quarter block of height.
        if(!f.quick&&f.swing>=OVER_BY)return;
        // Where the body will face over that foot. No further ahead than a third of a second: a body coming to rest
        // has a long cycle, and a turn begun then read on over all of it swung the footfall 50 degrees round and
        // back within two frames.
        float yaw=s.yaw+Mth.clamp(s.yawRate*(float)Math.min(TURN_AHEAD,left+s.stanceSeconds*.5),-30,30);
        double side=f.lat*s.half;
        double x=s.originX+s.vx*ahead+leftX(yaw)*side,z=s.originZ+s.vz*ahead+leftZ(yaw)*side;
        f.toX=x;f.toZ=z;f.toYaw=yaw-f.lat*TOE_OUT;
        f.toY=soleGround(eva,s.rig,x,z,f.toYaw,Double.isFinite(s.ground)?s.ground:eva.getY());
    }

    private static void land(State s,EvaUnit01Entity eva,Foot f)
    {
        double step=Math.hypot(f.toX-f.fromX,f.toZ-f.fromZ);
        f.down=true;f.x=f.toX;f.y=f.toY;f.z=f.toZ;f.yaw=f.toYaw;f.stood=0;f.strike=Math.max(0,f.landWith);f.swing=0;f.quick=false;
        f.roll=Mth.clamp(.2*s.stanceSeconds,.05,.2);
        // The weight comes down on the foot: the pelvis gives by this much and comes back (a damped spring).
        double give=s.moving?Mth.lerp(Mth.clamp((.62-s.duty)/.32,0,1),DIP_WALK,DIP_RUN)*Mth.clamp(s.speed/20,.3,1):DIP_SPOT;
        s.dipRate-=give*DIP_RATE*Math.E;
        footfall(s,eva,f,step);
    }

    /**
     * The ground a sole stands on at a place: the highest under its heel, its middle and its toes, so a sole is
     * set on a kerb and not into it. NaN-free: where nothing is found the level given stands in.
     */
    private static double soleGround(EvaUnit01Entity eva,Rig rig,double x,double z,float yaw,double near)
    {
        float radians=yaw*Mth.DEG_TO_RAD;double hx=-Mth.sin(radians),hz=Mth.cos(radians);
        double best=Double.NEGATIVE_INFINITY;
        for(double along:new double[]{-rig.heel()*.8,(rig.toe()-rig.heel())*.5,rig.toe()*.8})
        {
            double ground=ground(eva,x+hx*along,z+hz*along,near);
            if(Double.isFinite(ground))best=Math.max(best,ground);
        }
        return Double.isFinite(best)?best:near;
    }

    /**
     * The ground at a place, looked for about the body's own level: from GROUND_ABOVE over it down to GROUND_BELOW
     * under it. Ground more than STEP_MOST over the body's level is a wall and not a step, as it is for the body
     * itself; a place roofed over at the top of the search is one too.
     * <p>
     * It was looked for 21 blocks either side of the level the feet stood on ({@code near}). Running up a slope
     * of one in one the next footfall lies further above the feet than that: the search began inside the hill,
     * found nothing, and the foot was set down at the feet's old level. From then on every footfall was, and the
     * body, carried by its feet, was drawn 60 to 87 blocks down inside the slope while the Unit stood on its top.
     */
    private static double ground(EvaUnit01Entity eva,double x,double z,double near)
    {
        double level=eva.getY();
        Vec3 from=new Vec3(x,level+GROUND_ABOVE,z),to=new Vec3(x,level-GROUND_BELOW,z);
        for(int i=0;i<6;i++)
        {
            var hit=eva.level().clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva));
            if(hit.getType()!=HitResult.Type.BLOCK)return Double.NaN;
            // Starting inside a block: a wall stands there, or a roof over it.
            if(i==0&&hit.getLocation().y>level+GROUND_ABOVE-.5)return Double.NaN;
            var pos=hit.getBlockPos();var state=eva.level().getBlockState(pos);
            var shape=state.getCollisionShape(eva.level(),pos,CollisionContext.of(eva));
            if(!EvaObstacleCollision.ignores(eva,state,pos,shape))return hit.getLocation().y>level+STEP_MOST?Double.NaN:hit.getLocation().y;
            from=new Vec3(x,pos.getY()-.001,z);
        }
        return Double.NaN;
    }

    /** A footfall is heard and seen where it is drawn: each client sounds its own (the server sounds none for this model). */
    private static void footfall(State s,EvaUnit01Entity eva,Foot f,double step)
    {
        if(DIAG)ProjectSeele.LOGGER.info("R64PLANT land {} step {} speed {} cadence {} duty {} at {} {} {}",f.side,
                String.format(java.util.Locale.ROOT,"%.1f",step),String.format(java.util.Locale.ROOT,"%.1f",s.speed),
                String.format(java.util.Locale.ROOT,"%.2f",2/s.cycle),String.format(java.util.Locale.ROOT,"%.2f",s.duty),
                String.format(java.util.Locale.ROOT,"%.1f",f.x),String.format(java.util.Locale.ROOT,"%.1f",f.y),String.format(java.util.Locale.ROOT,"%.1f",f.z));
        if(eva.isSilent()||!eva.onGround())return;
        long now=AircraftRenderClockR21.frameNanos();
        if(now-s.lastSound<120_000_000L)return;
        s.lastSound=now;
        var level=eva.level();
        var state=level.getBlockState(BlockPos.containing(f.x,f.y-.2,f.z));
        boolean soil=state.is(BlockTags.DIRT)||state.is(BlockTags.SAND)||state.is(BlockTags.LEAVES);
        float run=Mth.clamp(eva.rifleRunBlend(1),0,1);
        // A step back under a standing body is set down, not stamped.
        float load=s.moving?1+.28F*run:.55F;
        SoundEvent sound=(soil?ModSounds.EVA_FOOT_SOIL:ModSounds.EVA_FOOT_CONCRETE).get();
        level.playLocalSound(f.x,f.y,f.z,SoundEvent.createFixedRangeEvent(sound.getLocation(),384F),SoundSource.PLAYERS,2.5F*load,1F,false);
        if(EvaSprintR50.blend(eva,1)>.5F&&!state.isAir())
        {
            // A sprinting footfall throws the ground up behind it.
            var random=eva.getRandom();
            for(int i=0;i<42;i++)
                level.addParticle(new BlockParticleOption(ParticleTypes.BLOCK,state),f.x+random.nextGaussian()*2.6,f.y+.3+random.nextDouble()*.2,
                        f.z+random.nextGaussian()*2.6,random.nextGaussian()*.16,random.nextDouble()*.16,random.nextGaussian()*.16);
            for(int i=0;i<9;i++)
                level.addParticle(ParticleTypes.POOF,f.x+random.nextGaussian()*2.2,f.y+.6,f.z+random.nextGaussian()*2.2,
                        random.nextGaussian()*.05,random.nextDouble()*.05,random.nextGaussian()*.05);
        }
    }

    private static GeoBone bone(BakedGeoModel model,String name){return model.getBone(name).orElse(null);}

    /** The rig's lengths as drawn; the sole from the unit's own mesh where it has one. */
    private static Rig measure(EvaUnit01Entity eva,GeoBone leg,GeoBone shin,GeoBone foot,Matrix4f root)
    {
        float scale=root.getScale(new Vector3f()).y;
        Vector3f hip=EvaRigTransforms.pivot(leg),knee=EvaRigTransforms.knee(shin),ankle=EvaRigTransforms.pivot(foot);
        float length=(hip.distance(knee)+knee.distance(ankle))*scale;
        float height=ankle.y*scale,toe=height*1.9F,heel=height*.75F;
        var points=EvaMeshPointsR63.of(eva,EvaGroundContactR56.PARTS).feet().get("l");
        if(points!=null&&points.length>0)
        {
            float low=Float.POSITIVE_INFINITY;
            for(Vector3f p:points)low=Math.min(low,p.y);
            float front=0,rear=0;
            // What stands on the ground: the part of the foot within half a block of its lowest point.
            for(Vector3f p:points)
            {
                if(p.y>low+.5F/scale)continue;
                front=Math.max(front,ankle.z-p.z);rear=Math.max(rear,p.z-ankle.z);
            }
            height=(ankle.y-low)*scale;toe=front*scale;heel=rear*scale;
        }
        Rig rig=new Rig(scale,Math.abs(hip.x)*scale,Math.abs(ankle.x)*scale,length,height,toe,heel);
        ProjectSeele.LOGGER.info("R64PLANT rig of unit {}: scale {} leg {} hip half {} foot half {} ankle {} toe {} heel {} (mesh {})",
                eva.getUnitVariant(),rig.scale(),rig.leg(),rig.hipHalf(),rig.footHalf(),rig.ankle(),rig.toe(),rig.heel(),points!=null&&points.length>0);
        return rig;
    }

    /** The ankle of a foot whose flat sole would stand at a place, rolled over its heel (pitch above 0) or its toes (below). */
    private static Vector3f ankleAt(Rig rig,double x,double y,double z,float yaw,float pitch,Vector3f out)
    {
        float radians=yaw*Mth.DEG_TO_RAD;double hx=-Mth.sin(radians),hz=Mth.cos(radians);
        double along,up;
        if(pitch>=0)
        {
            float a=pitch*Mth.DEG_TO_RAD;
            along=-rig.heel()+rig.heel()*Mth.cos(a)-rig.ankle()*Mth.sin(a);up=rig.heel()*Mth.sin(a)+rig.ankle()*Mth.cos(a);
        }
        else
        {
            float a=-pitch*Mth.DEG_TO_RAD;
            along=rig.toe()-rig.toe()*Mth.cos(a)+rig.ankle()*Mth.sin(a);up=rig.toe()*Mth.sin(a)+rig.ankle()*Mth.cos(a);
        }
        return out.set((float)(x+hx*along),(float)(y+up),(float)(z+hz*along));
    }

    /**
     * The pitch a standing foot has of itself: down from its heel strike in the time set as it landed, flat, and up
     * onto its toes as its hip goes on ahead of it.
     */
    private static float scheduled(State s,Foot f,Rig rig,double hipX,double hipZ)
    {
        if(f.strike>0&&f.stood<f.roll)
        {
            double t=f.stood/f.roll;
            return (float)(f.strike*(1-t*t*(3-2*t)));
        }
        return heel(s,rig,f.x,f.z,f.yaw,hipX,hipZ);
    }

    /** How far the heel of a foot standing at a place is up for a hip that has gone on ahead of it (degrees, below 0). */
    private static float heel(State s,Rig rig,double x,double z,float yaw,double hipX,double hipZ)
    {
        float radians=yaw*Mth.DEG_TO_RAD;
        double ahead=(hipX-x)*-Mth.sin(radians)+(hipZ-z)*Mth.cos(radians);
        // A fast run stands on a foot for a sixth of a second and leaves it far behind: its heel comes up from
        // the moment the hip passes over it, further, and over more of the way. Over the walk's short span the
        // fast run's heel came up 28 degrees in a frame and a third.
        double fast=Mth.clamp((s.speed-FAST_FROM)/(EvaMotionModelR64.SPRINT-FAST_FROM),0,1);
        double from=Mth.lerp(fast,HEEL_FROM,0),full=Mth.lerp(fast,HEEL_FULL,HEEL_FULL_FAST);
        double t=Mth.clamp((ahead/rig.leg()-from)/(full-from),0,1);
        return (float)(-Mth.lerp(fast,HEEL_OFF,HEEL_OFF_FAST)*t*t*(3-2*t));
    }

    /**
     * A standing foot's pitch where the leg does not reach it from the height the gait carries the hips at: the
     * foot rolls toward the body, onto its toes where the body has gone on ahead of it, onto its heel where the
     * body is behind it, as far as the leg needs and no further than an ankle gives.
     */
    private static float rolled(Rig rig,double x,double y,double z,float yaw,float pitch,double hipX,double hipZ,double above,double nominal)
    {
        Vector3f probe=new Vector3f();
        if(reach(rig,ankleAt(rig,x,y,z,yaw,pitch,probe),hipX,hipZ,above)>=nominal)return pitch;
        float radians=yaw*Mth.DEG_TO_RAD;
        double along=(hipX-x)*-Mth.sin(radians)+(hipZ-z)*Mth.cos(radians);
        boolean ahead=along>0;
        // A roll brings the ankle toward a hip that is ahead of the foot or behind it, not one beside it: a foot
        // set down wide of the body rolled to its limit in the frame it landed (25 degrees) and gained nothing.
        float limit=(ahead?-HEEL_OFF_MOST:TOES_UP_MOST)*(float)Mth.clamp(Math.abs(along)/(.25*rig.leg()),0,1);
        if(ahead?pitch<=limit:pitch>=limit)return pitch;
        if(reach(rig,ankleAt(rig,x,y,z,yaw,limit,probe),hipX,hipZ,above)<nominal)return limit;
        float low=pitch,high=limit;
        for(int k=0;k<9;k++)
        {
            float mid=(low+high)*.5F;
            if(reach(rig,ankleAt(rig,x,y,z,yaw,mid,probe),hipX,hipZ,above)<nominal)low=mid;else high=mid;
        }
        return high;
    }

    /** How high the middle of the hips may stand over a foot: its ankle, and what the leg reaches above it. */
    private static double reach(Rig rig,Vector3f ankle,double hipX,double hipZ,double hipAboveCentre)
    {
        double most=rig.leg()*REACH,flat=Math.hypot(hipX-ankle.x,hipZ-ankle.z);
        return ankle.y+(flat>=most?0:Math.sqrt(most*most-flat*flat))-hipAboveCentre;
    }

    /**
     * Poses the pelvis and the legs for this frame, over whatever the clips have written.
     */
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        State s=STATES.get(eva);
        long now=AircraftRenderClockR21.frameNanos();
        if(s==null||s.begun!=now||root==null)return EvaMotionEngineV2.BoneWrites.empty();
        GeoBone pelvis=bone(model,"root");
        GeoBone[] legs={bone(model,"leg_l"),bone(model,"leg_r")},shins={bone(model,"shin_l"),bone(model,"shin_r")};
        GeoBone[] ankles={bone(model,"ankle_l"),bone(model,"ankle_r")},feet={bone(model,"foot_l"),bone(model,"foot_r")};
        if(pelvis==null||legs[0]==null||legs[1]==null||shins[0]==null||shins[1]==null||ankles[0]==null||ankles[1]==null||feet[0]==null||feet[1]==null)
        {
            // A rig without ankles (the public model): the old model walks it.
            s.live=false;eva.plantedClipReleaseR64();
            return EvaMotionEngineV2.BoneWrites.empty();
        }
        boolean fresh=now!=s.posed;
        Foot[] both={s.left,s.right};
        if(s.rig==null||Math.abs(s.rig.scale()-root.getScale(new Vector3f()).y)>1e-4F)s.rig=measure(eva,legs[0],shins[0],feet[0],root);
        Rig rig=s.rig;
        Quaternionf frame=EvaRigTransforms.rotation(root);
        if(!s.live)
        {
            // Taken over: the feet stand where the pose before this left them, and step under the body from there.
            s.live=true;s.running=false;s.phase=0;s.still=0;s.yawRate=0;s.lean=s.leanRate=s.bank=s.bankRate=0;s.sway=0;
            s.originX=root.m30();s.originZ=root.m32();s.dip=s.dipRate=0;s.startAge=99;
            s.vx=(eva.getX()-eva.xOld)*20;s.vz=(eva.getZ()-eva.zOld)*20;s.fast=s.slow=0;
            s.yaw=Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot);
            // Which hip is on the body's left: from where the hips are, not from what the bones are called.
            Vector3f hipL=EvaRigTransforms.point(legs[0],EvaRigTransforms.pivot(legs[0]),root),hipR=EvaRigTransforms.point(legs[1],EvaRigTransforms.pivot(legs[1]),root);
            s.left.lat=(hipL.x-hipR.x)*leftX(s.yaw)+(hipL.z-hipR.z)*leftZ(s.yaw)>=0?1:-1;s.right.lat=-s.left.lat;
            double sum=0;
            for(int i=0;i<2;i++)
            {
                Foot f=both[i];
                Matrix4f world=new Matrix4f(root).mul(EvaRigTransforms.model(feet[i]));
                Vector3f at=world.transformPosition(EvaRigTransforms.pivot(feet[i]));
                Vector3f toes=EvaRigTransforms.rotation(world).transform(new Vector3f(0,0,-1));
                f.down=true;f.swing=0;f.quick=false;f.stood=1;f.strike=0;f.support=1;f.reachShort=0;
                f.yaw=Math.hypot(toes.x,toes.z)>.2?(float)(Mth.atan2(-toes.x,toes.z)*Mth.RAD_TO_DEG):s.yaw;
                f.x=at.x;f.z=at.z;
                f.y=soleGround(eva,rig,f.x,f.z,f.yaw,at.y-rig.ankle());
                f.pitch=0;f.drawnYaw=f.yaw;f.ankleX=at.x;f.ankleY=f.y+rig.ankle();f.ankleZ=at.z;
                sum+=f.y;
            }
            s.ground=sum/2;s.height=Double.NaN;
            s.half=rig.footHalf();s.sink=.35;s.bounce=0;s.duty=SETTLE_DUTY;s.cycle=SETTLE_SWING/(1-SETTLE_DUTY);
            s.swingSeconds=SETTLE_SWING;s.stanceSeconds=s.cycle*s.duty;s.moving=false;s.speed=0;s.landPitch=0;
            fresh=true;
        }
        s.applied=now;s.posed=now;
        float dt=fresh?s.dt:0;

        // The trunk tips with what the body gathers and banks into its turn, about the hips.
        if(Math.abs(s.lean)>.02F||Math.abs(s.bank)>.02F)
        {
            var q=new Quaternionf().rotationZYX(pelvis.getRotZ(),pelvis.getRotY(),pelvis.getRotX());
            EvaRigTransforms.rotate(pelvis,q.rotateX(-s.lean*Mth.DEG_TO_RAD).rotateZ(-s.bank*Mth.DEG_TO_RAD));
        }
        Vector3f[] hips={EvaRigTransforms.point(legs[0],EvaRigTransforms.pivot(legs[0]),root),EvaRigTransforms.point(legs[1],EvaRigTransforms.pivot(legs[1]),root)};
        Vector3f centre=new Vector3f(hips[0]).add(hips[1]).mul(.5F);

        // Over the body, toward the foot that bears it.
        double bearing=s.left.support*s.left.lat+s.right.support*s.right.lat;
        double share=s.moving?Mth.lerp(Mth.clamp((.62-s.duty)/.22,0,1),SWAY_WALK,SWAY_RUN):SWAY_SPOT;
        double swayTarget=bearing*share*s.half;
        if(fresh)s.sway+=(swayTarget-s.sway)*(1-Math.exp(-dt/.12));
        double originX=root.m30(),originZ=root.m32();
        double wantX=originX+leftX(s.yaw)*s.sway,wantZ=originZ+leftZ(s.yaw)*s.sway;
        double shiftX=wantX-centre.x,shiftZ=wantZ-centre.z;

        // The level the pelvis is carried over: the feet's own ground.
        double level=0;
        for(Foot f:both)level+=f.down?f.y:Mth.lerp(smooth(f.swing),f.fromGround,f.toY);
        level/=2;
        if(fresh)s.ground=Double.isFinite(s.ground)?s.ground+(level-s.ground)*(1-Math.exp(-dt/GROUND_EASE)):level;
        double nominal=s.ground+rig.ankle()+rig.leg()-s.sink;
        // A run rises between its footfalls and is lowest over each foot.
        if(s.bounce>0&&s.running)nominal-=s.bounce*Math.cos(4*Math.PI*(s.phase-s.duty*.5));
        nominal+=Math.min(0,s.dip);

        // The feet: where each ankle is and how the foot lies.
        Vector3f[] anklesAt={new Vector3f(),new Vector3f()};
        double[] reaches=new double[2];
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];
            double hipX=hips[i].x+shiftX,hipZ=hips[i].z+shiftZ,above=hips[i].y-centre.y;
            if(f.down)
            {
                float pitch=rolled(rig,f.x,f.y,f.z,f.yaw,scheduled(s,f,rig,hipX,hipZ),hipX,hipZ,above,nominal);
                ankleAt(rig,f.x,f.y,f.z,f.yaw,pitch,anklesAt[i]);
                f.pitch=pitch;f.drawnYaw=f.yaw;reaches[i]=reach(rig,anklesAt[i],hipX,hipZ,above);
            }
            else
            {
                float t=smooth(f.swing);
                float yaw=f.fromYaw+Mth.wrapDegrees(f.toYaw-f.fromYaw)*t;
                // The foot comes down as it will stand: with the roll the leg will need there. Set down at the
                // gait's own pitch and rolled a frame later, it turned 13 degrees in that frame.
                // (Stepping backward the hip is ahead of the footfall: the toes come down first.)
                // Rolled for where its hip will be as it lands, which the footfall was chosen from: read off where
                // the hip is now, a fast run's foot came down rolled for a hip still far behind it and lost 14
                // degrees in its last frame.
                double thenX=hipX+s.vx*f.timeLeft,thenZ=hipZ+s.vz*f.timeLeft;
                f.landWith=rolled(rig,f.toX,f.toY,f.toZ,f.toYaw,s.landPitch>0?s.landPitch:heel(s,rig,f.toX,f.toZ,f.toYaw,thenX,thenZ),thenX,thenZ,above,nominal);
                float pitch=Mth.lerp(t,f.fromPitch,f.landWith);
                Vector3f to=ankleAt(rig,f.toX,f.toY,f.toZ,f.toYaw,f.landWith,new Vector3f());
                double distance=Math.hypot(to.x-f.fromX,to.z-f.fromZ);
                // Over the ground the ankle leaves at the body's own speed, as the toes that it rolled over let it
                // go, and is over its footfall a little before it is down on it, so it comes down and does not
                // skid in. Eased from rest it fell 5 blocks further behind a fast run's hip in its first frames,
                // past the leg's reach, and the thigh whipped after it (34 degrees in a frame); eased to the very
                // end it was within a quarter block of the ground with 0.8 blocks still to go.
                float over=Math.min(1,f.swing/OVER_BY);
                double carried=Mth.clamp(s.speed*f.swingTime*OVER_BY/Math.max(distance,1e-3),0,1.2);
                double along=(over*over*over-2*over*over+over)*carried+(3-2*over)*over*over;
                // A fast run folds the leg up behind it at once: the lift comes early.
                double fast=Mth.clamp((s.speed-FAST_FROM)/(EvaMotionModelR64.SPRINT-FAST_FROM),0,1);
                double lift=s.lift*Mth.clamp(distance/4,.35,1)*Math.sin(Math.PI*Math.pow(f.swing,Mth.lerp(fast,1,.62)));
                anklesAt[i].set((float)Mth.lerp(along,f.fromX,to.x),(float)(Mth.lerp(t,f.fromY,to.y)+lift),(float)Mth.lerp(along,f.fromZ,to.z));
                f.pitch=pitch;f.drawnYaw=yaw;
                // A foot in the air holds the pelvis down only as it comes to land: a foot just lifted is far
                // behind, and held to its reach the pelvis was pulled 3 to 9 blocks down at each lift-off of a
                // fast run. (A leg that does not reach its foot in the air draws it a little short, unseen.)
                double landing=smooth((f.swing-.6F)/.4F);
                reaches[i]=Mth.lerp(landing,Math.max(nominal+2,reach(rig,anklesAt[i],hipX,hipZ,above)),reach(rig,anklesAt[i],hipX,hipZ,above));
            }
            f.ankleX=anklesAt[i].x;f.ankleY=anklesAt[i].y;f.ankleZ=anklesAt[i].z;
        }
        // As high as both legs reach, and no higher than the gait carries it.
        double most=Math.min(reaches[0],reaches[1]);
        double wanted=softMin(nominal,softMin(reaches[0],reaches[1],.35),.35);
        if(fresh)s.height=Double.isFinite(s.height)?s.height+(wanted-s.height)*(1-Math.exp(-dt/HEIGHT_EASE)):Math.min(centre.y,most);
        if(s.height>most)s.height=most;
        double shiftY=s.height-centre.y;

        shift(pelvis,frame,rig.scale(),shiftX,shiftY,shiftZ);
        for(int i=0;i<2;i++)hips[i].add((float)shiftX,(float)shiftY,(float)shiftZ);
        solve(s,both,legs,shins,ankles,feet,hips,anklesAt,frame,root);
        if(fresh)witness(eva,s,hips,anklesAt);
        return new EvaMotionEngineV2.BoneWrites(BONES,POSITIONS,"MOTION_ENGINE_LIVE_ACTION");
    }

    private static final Set<String> BONES=Set.of("root","leg_l","leg_r","shin_l","shin_r","ankle_l","ankle_r","foot_l","foot_r");
    private static final Set<String> POSITIONS=Set.of("root","shin_l","shin_r");

    private static float smooth(float t){t=Mth.clamp(t,0,1);return t*t*(3-2*t);}

    /** Under both, and rounded where they cross. */
    private static double softMin(double a,double b,double width)
    {
        double low=Math.min(a,b),gap=Math.abs(a-b);
        return low-width*Math.log1p(Math.exp(-gap/width));
    }

    /** Moves the whole body by a world offset: the root bone has no parent, and its own turn does not carry its place. */
    private static void shift(GeoBone pelvis,Quaternionf frame,float scale,double x,double y,double z)
    {
        Vector3f local=new Quaternionf(frame).conjugate().transform(new Vector3f((float)x,(float)y,(float)z)).div(scale);
        pelvis.setPosX(pelvis.getPosX()-local.x*16);pelvis.setPosY(pelvis.getPosY()+local.y*16);pelvis.setPosZ(pelvis.getPosZ()+local.z*16);
    }

    private static void solve(State s,Foot[] both,GeoBone[] legs,GeoBone[] shins,GeoBone[] ankles,GeoBone[] feet,Vector3f[] hips,Vector3f[] anklesAt,Quaternionf frame,Matrix4f root)
    {
        float body=s.yaw*Mth.DEG_TO_RAD;
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];
            // Minecraft yaw grows clockwise from above, world rotations the other way.
            var turn=new Quaternionf().rotationY(Mth.wrapDegrees(s.yaw-f.drawnYaw)*Mth.DEG_TO_RAD).mul(frame).rotateX(f.pitch*Mth.DEG_TO_RAD);
            float heading=f.drawnYaw*Mth.DEG_TO_RAD;
            // The knee bends the way the foot and the body point.
            var pole=new Vector3f(-Mth.sin(heading)-Mth.sin(body),0,Mth.cos(heading)+Mth.cos(body));
            if(pole.lengthSquared()<1e-4F)pole.set(-Mth.sin(body),0,Mth.cos(body));
            double off=EvaRigTransforms.solveLeg(legs[i],shins[i],ankles[i],feet[i],anklesAt[i],turn,pole.normalize(),root);
            f.reachShort=Math.max(0,hips[i].distance(anklesAt[i])-s.rig.leg()*REACH);
            if(DIAG&&off>.05)ProjectSeele.LOGGER.info("R64PLANT leg {} is {} blocks short of its foot",f.side,String.format(java.util.Locale.ROOT,"%.2f",off));
        }
    }

    /**
     * After the pose has been blended with the one before it: the pelvis may have been moved, the legs turned. The
     * feet are put back exactly where they stand, the pelvis lowered if a leg no longer reaches.
     */
    static void finishLegs(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root)
    {
        State s=STATES.get(eva);
        if(s==null||!s.live||s.applied!=AircraftRenderClockR21.frameNanos()||root==null)return;
        GeoBone pelvis=bone(model,"root");
        GeoBone[] legs={bone(model,"leg_l"),bone(model,"leg_r")},shins={bone(model,"shin_l"),bone(model,"shin_r")};
        GeoBone[] ankles={bone(model,"ankle_l"),bone(model,"ankle_r")},feet={bone(model,"foot_l"),bone(model,"foot_r")};
        Foot[] both={s.left,s.right};
        Quaternionf frame=EvaRigTransforms.rotation(root);
        Vector3f[] hips={EvaRigTransforms.point(legs[0],EvaRigTransforms.pivot(legs[0]),root),EvaRigTransforms.point(legs[1],EvaRigTransforms.pivot(legs[1]),root)};
        Vector3f centre=new Vector3f(hips[0]).add(hips[1]).mul(.5F);
        Vector3f[] anklesAt={new Vector3f((float)s.left.ankleX,(float)s.left.ankleY,(float)s.left.ankleZ),new Vector3f((float)s.right.ankleX,(float)s.right.ankleY,(float)s.right.ankleZ)};
        double most=Double.POSITIVE_INFINITY;
        for(int i=0;i<2;i++)most=Math.min(most,reach(s.rig,anklesAt[i],hips[i].x,hips[i].z,hips[i].y-centre.y));
        if(centre.y>most)
        {
            double down=most-centre.y;
            shift(pelvis,frame,s.rig.scale(),0,down,0);
            for(int i=0;i<2;i++)hips[i].add(0,(float)down,0);
        }
        solve(s,both,legs,shins,ankles,feet,hips,anklesAt,frame,root);
    }

    /**
     * For the review's pose records: [0] the clock's phase, [1] it runs, [2] the body moves, [3] speed, [4] steps a
     * second, [5] duty; then for the left foot and the right: on the ground, how far through its swing, its pitch,
     * where it stands or lands (x, y, z), its ankle (x, y, z), how far its leg is short; [28] pelvis height over the
     * feet's ground, [29] its sway, [30] lean, [31] bank.
     */
    private static void witness(EvaUnit01Entity eva,State s,Vector3f[] hips,Vector3f[] anklesAt)
    {
        if(LAST.size()>32)LAST.clear();
        double[] w=new double[32];
        w[0]=frac(s.phase);w[1]=s.running?1:0;w[2]=s.moving?1:0;w[3]=s.speed;w[4]=2/s.cycle;w[5]=s.duty;
        Foot[] both={s.left,s.right};
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];int at=6+i*11;
            w[at]=f.down?1:0;w[at+1]=f.swing;w[at+2]=f.pitch;
            w[at+3]=f.down?f.x:f.toX;w[at+4]=f.down?f.y:f.toY;w[at+5]=f.down?f.z:f.toZ;
            w[at+6]=anklesAt[i].x;w[at+7]=anklesAt[i].y;w[at+8]=anklesAt[i].z;w[at+9]=f.reachShort;w[at+10]=f.drawnYaw;
        }
        w[28]=(hips[0].y+hips[1].y)*.5-s.ground;w[29]=s.sway;w[30]=s.lean;w[31]=s.bank;
        LAST.put(eva.getId(),w);
    }

    private EvaPlantedGaitR64(){}
}

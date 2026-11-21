package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.entity.CombatReactionsR36;
import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaCombatR31;
import com.projectseele.entity.EvaGameplayMotionR32;
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
    /** A foot stands at least this long (seconds), and is not lifted for a swing shorter than this. */
    private static final double MIN_STANCE=.06,MIN_SWING=.12;
    /** A step taken out of turn, because the leg no longer reached its foot (seconds). */
    private static final double QUICK_SWING=.22;
    /** A leg is drawn out to this share of its length at most. */
    private static final float REACH=.985F;
    /**
     * R64: a walk goes over its standing leg. The owner, 2026-11-18: "走路现在有点像提线木偶，腿软的感觉，可能是膝关节
     * 动作缺失". Measured on the gait tour's walk: the standing knee was bent 19 to 26 degrees from footfall to
     * lift and never less (no leg is drawn out past REACH, which is a knee of 20 degrees), and the hips went up
     * and down 0.6 of a block in a step, a fiftieth of the leg: a body carried level over legs that only fold.
     * A walking body is highest over the foot it stands on, that knee all but straight, and lowest while both
     * feet are down; the knee gives as the weight comes onto it and straightens as the body goes over.
     * VAULT_REACH: a walking leg is drawn out to this share of its length (a knee of 9 degrees). VAULT_SINK: how
     * far under the leg's length the hips are over the standing foot. VAULT_BOB: how far they come down between
     * footfalls (blocks, at a step of VAULT_STEP of the leg; less for a shorter step, by its square). A run
     * keeps its own rise and fall, and a body that stands stands as it did.
     * -Dprojectseele.walkVaultR64=false: as before, to capture the two beside each other.
     */
    /**
     * R64, STOPPED: a body that is stopped dead (the owner, 2026-11-18: "冲刺遇到障碍物，腿部还是会出问题") has one
     * foot in the air, timed by a clock that goes at a standing step's pace from the moment the body stands: a
     * fast run's foot, due down in a tenth of a second, hung for 0.8 (measured against the review world's wall),
     * and the other stood a stride ahead of the hips until its turn came round. The foot in the air comes down at
     * once, as a step taken out of turn does (QUICK_SWING), under the body; and the clock is then set for the
     * other foot, if it is not where a standing foot belongs, to step next.
     * -Dprojectseele.stoppedStepR64=false: as before.
     */
    private static final boolean STOPPED=!"false".equals(System.getProperty("projectseele.stoppedStepR64"));
    private static final boolean VAULT=!"false".equals(System.getProperty("projectseele.walkVaultR64"));
    private static final float VAULT_REACH=.9965F;
    private static final double VAULT_SINK=.12,VAULT_BOB=1.4,VAULT_STEP=.85,VAULT_EASE=.12;
    /** The share of its length a leg is drawn out to in the frame in hand (REACH, or more at a walk). */
    private static float reachShare=REACH;
    /** The heel comes up this far at most as the body leaves a foot behind, the toes this far as it lands (degrees). */
    private static final float HEEL_OFF_MOST=55F,TOES_UP_MOST=16F;
    /** A foot further from the body than this share of the leg has been left by something else: the feet are set anew. */
    private static final double LOST_SHARE=1.6;
    /** Seconds over which the measured speed, the pelvis height, the bearing foot and the ground level are eased. */
    private static final double VELOCITY_EASE=.07,HEIGHT_EASE=.045,SUPPORT_EASE=.09,GROUND_EASE=.15;
    /** Seconds of the body's trail its pace is read over, over which that is eased, and over which its place is eased for its steps. */
    private static final double PACE_WINDOW=.4,PACE_EASE=.12,PLACE_EASE=.15;
    /** Frames of the body's drawn place kept for its pace. */
    private static final int TRAIL=96;
    /** Each foot is turned out by this (degrees). */
    private static final float TOE_OUT=3F;
    /** Going sideways the feet are set this far either side of the body (blocks) and step at least this often a second. */
    private static final double WIDE_HALF=7,SIDE_CADENCE=1.9;
    /** Steps a second in a turn of TURN_FULL degrees a second or more (see where the cadence is set). */
    private static final double TURN_CADENCE=2.6,TURN_FULL=80;
    /** A step backward is this long at most (blocks). */
    private static final double BACK_STEP=15;
    /** The pelvis goes this share of the way toward the bearing foot: on the spot, walking, running. */
    private static final double SWAY_SPOT=.20,SWAY_WALK=.12,SWAY_RUN=.06;
    /**
     * The owner's first play of the planted model (2026-11-16): "the legs come out of line" and "the crotch swings
     * from side to side". Neither was on the scorecard, which measured what the feet do on the ground and never
     * how the leg between hip and foot is turned, nor how far the pelvis is carried sideways.
     * <p>
     * The legs: a walking Unit turns up to nine degrees a tick and a foot stands for most of a second, so a foot
     * planted before a turn was left pointing up to 160 degrees off the body, and the knee, which is pointed
     * halfway between foot and body, with it. A planted foot now turns on the ground with the body once it is this
     * many degrees off it (as a foot does on its ball in a turn): the scorecard's "foot turns on the ground" was
     * held under two degrees by never letting it.
     * <p>
     * The pelvis: it was carried 0.30 of the half-width of the stance toward the standing foot at a walk (1.2
     * blocks either way, a quarter of the distance between the hips), eased in an eighth of a second. A walking
     * body carries it about a third of that. Now 0.12 (0.20 standing, 0.06 running), eased in a fifth of a second.
     */
    /**
     * (Above STEP_TURN and the toe-out, so that a foot standing through a turn on the spot is still asked to step
     * first, as before: held at 18 it turned on the ground instead of stepping, 20 degrees at the median.)
     */
    private static final float TWIST_MOST=24;
    private static final double SWAY_EASE=.20;
    /** The trunk tips this many degrees for each block a second squared it gathers, and banks as much into a turn; at most. */
    private static final float LEAN_GAIN=.045F,LEAN_MOST=7F,BANK_GAIN=.05F,BANK_MOST=9F;
    private static final float LEAN_RATE=9F;
    /**
     * R64 (M2), the ground a sole stands on. It is read at this many stations from heel to toes, each side of the
     * sole's middle line by this much (blocks). Under this rise the ground is level. A rise of more than
     * KERB_RISE of which one step between two stations holds KERB_SHARE is a kerb: the sole stands on one level,
     * moved on or back until all of it does (by SHIFT_MOST at most, EDGE_MARGIN clear of the edge). Anything else
     * is a slope, and the sole lies along it as far as an ankle gives (degrees).
     */
    private static final int STATIONS=7;
    private static final double FLAT_RISE=.6,KERB_RISE=2.5,KERB_SHARE=.65,SHIFT_MOST=7,EDGE_MARGIN=.6;
    private static final float SOLE_SLOPE_MOST=30F;
    private static final double SLOPE_SINK=.1;
    /** On a slope the pelvis is carried lower by this share of what half a step rises or falls there. */
    private static final double SLOPE_DROP=.45;
    /** How much of a sole lying on a slope is on the block it rests on, at the least (blocks). */
    private static final double SOLE_HOLD=.5;
    /**
     * Where ground is looked for about the body's own level, how far over that level a footfall may be, and the
     * rise from one station under a sole to the next that is a wall and not a kerb (blocks). Up a slope of one in
     * one a running footfall lies up to 25 blocks over the box's own level; held to the box's step of 21 the
     * toes' stations found "a wall", the footfall was taken at half the step instead, and it went between the
     * two from frame to frame, 6 blocks up and down the slope.
     */
    private static final double GROUND_ABOVE=30,GROUND_BELOW=48,STEP_MOST=29,WALL=20.5;
    /**
     * The rise over run from which a slope shortens the step, the step a footfall on level ground is never over
     * and the step on a slope of one in one (blocks), and the cadence that is not passed for it (steps a second).
     */
    private static final double STEEP_FROM=.3,STEP_LEVEL=48,STEP_STEEP=15,STEEP_CADENCE=3.2;
    /** A swinging sole passes this far over the ground on its way (blocks). */
    private static final double CLEARANCE=1.2;
    /** The trunk leans into a slope by this share of its angle, at most this far forward and back (degrees). */
    private static final float SLOPE_LEAN=.35F,SLOPE_LEAN_UP=14F,SLOPE_LEAN_DOWN=6F;
    /** Landing from a fall the pelvis gives this much for each block a second over LAND_FROM, at most LAND_MOST (blocks). */
    private static final double LAND_FROM=12,LAND_GIVE=.075,LAND_MOST=5.5;
    /**
     * R64 (EvaLeapR64): the hardest landing lets the pelvis down this far (blocks; the hips stand 35 up), on a
     * spring this slow (a second; the footfalls' own is DIP_RATE), and a body gathering to jump carries its hips
     * this far back over its heels at the bottom of its squat.
     */
    private static final double ABSORB_MOST=12,ABSORB_RATE=5.5,SQUAT_BACK=2.5,SQUAT_EASE=.035;
    /**
     * R64: a body that comes down going faster over the ground than SKID_FROM of its walk slides on its feet, set
     * as they came down, until it is slower than SKID_UNTIL of it (or for SKID_LONGEST seconds). Its feet used to
     * be planted where it came down: from a fast run the body went on 30 blocks in the next six ticks, and with
     * its feet left that far behind it was drawn flat on the ground until they were set anew.
     */
    private static final double SKID_FROM=1.3,SKID_UNTIL=.6,SKID_LONGEST=.6,SKID_AIR=.35;
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
        /** Swinging: it left the ground while the body was going somewhere (see STOPPED). */
        boolean travelling;
        /** As drawn in the last frame: the ankle, the pitch (degrees, toes up). */
        double ankleX,ankleY,ankleZ;
        float pitch,drawnYaw,landWith;
        /** The lie of the ground under the sole (degrees, rising toward the toes): standing, as it left, where it lands, as drawn. */
        float slope,fromSlope,toSlope,drawnSlope;
        /** Swinging: how much higher than its own arc it goes to clear what stands in its way; a footfall has been chosen. */
        double clear;
        boolean targeted,settled;
        // Body position at the last stationary footfall, even if a wall displaced its nominal target.
        double restBodyX=Double.NaN,restBodyZ;
        float restBodyYaw;
        /** Swinging: the share of its step it takes (less where the whole step had nothing to stand on). */
        double share=1;
        /** Swinging: seconds until it lands, and how long the swing was to be as it began. */
        double timeLeft,swingTime=.4;
        float support=1;
        double reachShort;
        Foot(String side,float sign,double offset){this.side=side;this.sign=sign;this.offset=offset;}
    }

    /** Lengths of the rig as it is drawn (blocks). */
    private record Rig(float scale,float hipHalf,float footHalf,float leg,float ankle,float toe,float heel,float sole,float tip,float tipUp){}

    private static final class State
    {
        long begun=Long.MIN_VALUE/2,applied=Long.MIN_VALUE/2,posed=Long.MIN_VALUE/2;
        float dt;
        boolean live,running,moving;
        Rig rig;
        double phase,cycle=1.5,duty=.62,swingSeconds=.5,stanceSeconds=.9,half=4,speed,land=.5,lift=3,sink=.4,bounce,forwardSpeed,lateral;
        double vx,vz,originX,originZ,pace,px,pz;
        /** Where the body is for its steps: its place eased, and carried on by what the easing lags at this pace. */
        double easedX,easedZ,atX,atZ;
        final long[] trailTime=new long[TRAIL];
        final double[] trailX=new double[TRAIL],trailZ=new double[TRAIL];
        int trailAt,trailFilled;
        float yaw,yawRate,still,landPitch,startAge=99;
        /** How far the ground is carrying the box up and down (0 on level ground, 1 over terraces and kerbs), eased. */
        float rough,carried;
        double height=Double.NaN,ground=Double.NaN,sway,fast,slow;
        /** R64: how much of a walk's going over its standing leg the body has (VAULT), eased. */
        double vault;
        float lean,leanRate,bank,bankRate;
        double lastStep,dip,dipRate;long lastSound;
        /** R64: the rate of the pelvis' spring now (slower while a hard landing is taken up), and how far a squat lets the pelvis down. */
        double dipStiff=DIP_RATE,squat;
        /** R64: sliding on its feet after coming down fast, for how long, where each foot is from the body, and when dust was last thrown. */
        boolean skidding;
        /** When the stretch off the ground that airAt is the last frame of began. */
        long airFrom=Long.MIN_VALUE/2;
        double skidAge;
        final double[] skidX=new double[2],skidZ=new double[2];
        long skidDust;
        /** Ground heights by block column, kept a second: a footfall is chosen anew every frame of a swing. */
        final HashMap<Long,Double> columns=new HashMap<>();
        long columnsAt;
        double columnsNear=Double.NaN;
        /** The lie of the ground along the body's heading (degrees, eased); the fastest it fell while off the ground, and when. */
        double slopeAhead,fall,bodyGround=Double.NaN;
        long airAt=Long.MIN_VALUE/2;
        final Foot left=new Foot("l",1,.5),right=new Foot("r",-1,0);
    }

    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    private static boolean wanted(EvaUnit01Entity e,float partial)
    {
        boolean punch=EvaGameplayMotionR32.activeSupportedPunchR64(e);
        return EvaMotionModelR64.walks(e)&&EvaBodyPose.hasTerrainStances()
                &&(punch||!e.hasLegacyStrikeForRender()&&!e.hasLiveActionForRender(partial)&&e.getOrdinaryAttackStage()<0)
                &&e.getMotionLabPhysicsPreview()==0&&!e.isVisuallyAirborneForRender()
                &&!e.hasActiveCarrierMotion()&&e.rifleStanceLevel(partial)<.02F
                &&!e.isHeavyMotionActive()&&!e.isKickMotionActive(partial)&&!e.fixedCannonOperatingR52()
                &&EvaCombatR31.action(e)==EvaCombatR31.NONE&&!CombatReactionsR36.active(e)
                &&!EvaMechanicalFrameR52.serviceSourceHeldR52(e)&&!EvaShutdownR30.displayed(e)
                &&!com.projectseele.anim.EvaAnimator.canSupplyGait(e,partial);
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
        long began=DIAG?System.nanoTime():0;
        try
        {
            return begun(eva,partial);
        }
        finally
        {
            if(DIAG)cost(System.nanoTime()-began,true);
        }
    }

    /** -Dprojectseele.plantedDiagR64=true: what this model costs a frame, logged every 600 frames it poses. */
    private static long costNanos,costFrames,costMost;
    private static void cost(long nanos,boolean first)
    {
        costNanos+=nanos;
        if(!first)return;
        if(++costFrames>=600)
        {
            ProjectSeele.LOGGER.info("R64PLANT cost: {} microseconds a frame over {} frames (steps, pelvis and legs of every Unit it walks)",costNanos/costFrames/1000,costFrames);
            costNanos=0;costFrames=0;
        }
    }

    private static boolean begun(EvaUnit01Entity eva,float partial)
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
            if(s!=null)
            {
                s.live=false;
                // Off the ground: how fast it comes down is what its legs will take up as it lands.
                if(!eva.onGround()||eva.isVisuallyAirborneForRender())
                {
                    if(now-s.airAt>120_000_000L)s.airFrom=now;
                    s.fall=Math.max(s.fall,(eva.yOld-eva.getY())*20);s.airAt=now;
                }
            }
            LAST.remove(eva.getId());
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
        double going=Math.hypot(s.vx,s.vz);
        // A teleport, or a correction of the body's place: not a speed to step by.
        if(going>400){s.live=false;return;}
        // The pace the gait goes by: what the body has covered over the last three tenths of a second, by its
        // drawn place. Over terraces the box is carried up a step in one tick and stands in the next (3.3 blocks,
        // none, 3.3, none, up a slope of one in one): stepped by the speed of the tick, cadence, stance and
        // footfall changed with every tick and the legs were thrown about, and that speed eased came to 56
        // blocks a second where the body made 37, so every footfall was chosen half a step too far up the slope
        // and the legs did not reach.
        int at=s.trailAt=(s.trailAt+1)%TRAIL;
        s.trailTime[at]=AircraftRenderClockR21.frameNanos();s.trailX[at]=s.originX;s.trailZ[at]=s.originZ;
        s.trailFilled=Math.min(TRAIL,s.trailFilled+1);
        double span=0;int count=1;
        for(int i=1;i<s.trailFilled;i++)
        {
            int newer=(at-i+1+TRAIL)%TRAIL,older=(at-i+TRAIL)%TRAIL;
            double stepped=Math.hypot(s.trailX[newer]-s.trailX[older],s.trailZ[newer]-s.trailZ[older]);
            // A jump of the body's place, or a gap in the frames: the trail starts anew from here.
            if(stepped>40||s.trailTime[newer]-s.trailTime[older]>250_000_000L){s.trailFilled=i;break;}
            count=i+1;span=(s.trailTime[at]-s.trailTime[older])/1e9;
            if(span>=PACE_WINDOW)break;
        }
        // The line through that trail (least squares), not its length. Up a slope of one in one the body's place
        // is set back a tick's travel every tick or two and forward again (its driver's side and the server's
        // do not agree on a terrace; M3), 3.3 blocks back and forth: by its length the trail made 54 blocks a
        // second where the body made 38, and every footfall was chosen a third of a step too far up the slope.
        double meanT=0,meanX=0,meanZ=0;
        for(int i=0;i<count;i++)
        {
            int k=(at-i+TRAIL)%TRAIL;
            meanT+=(s.trailTime[k]-s.trailTime[at])/1e9;meanX+=s.trailX[k];meanZ+=s.trailZ[k];
        }
        meanT/=count;meanX/=count;meanZ/=count;
        double overT=0,fitX=0,fitZ=0;
        for(int i=0;i<count;i++)
        {
            int k=(at-i+TRAIL)%TRAIL;double t=(s.trailTime[k]-s.trailTime[at])/1e9-meanT;
            overT+=t*t;fitX+=t*(s.trailX[k]-meanX);fitZ+=t*(s.trailZ[k]-meanZ);
        }
        if(overT>1e-6){fitX/=overT;fitZ/=overT;}else{fitX=s.vx;fitZ=s.vz;}
        double fit=Math.hypot(fitX,fitZ);
        // Until there is a tenth of a second of trail, and whenever the body has all but stopped, the speed of the tick.
        // And never far from it: a body that brakes is not carried on at the pace it had (the trail lags it by
        // half its length), while a tick's speed over terraces stays within this of the trail's.
        double measured=span>=.1&&going>MOVE_AT?Mth.clamp(fit,going*.5,going*2):going;
        // Only where the ground carries the box up and down, though. On level ground the tick's own speed is the
        // body's, and the trail lags a body that gathers way: read off it, a fast run's feet were chosen and
        // swung for 113 blocks a second while the body made 160, and a leg was 10 blocks short of its foot.
        float stepped=Math.abs(eva.getY()-eva.yOld)*20>2?1:0;
        s.rough+=(stepped-s.rough)*(float)(1-Math.exp(-dt/(stepped>s.rough?.05:.5)));
        // What the pelvis stands over follows that more slowly: taken up as quickly as the pace is, the pelvis
        // went from over the feet's own level to over the ground under the body in two frames at the foot of a
        // hill, 4 blocks up in one of them.
        s.carried+=(s.rough-s.carried)*(float)(1-Math.exp(-dt/.35));
        double wanted=Mth.lerp(s.rough,going,measured),easedOver=s.rough*PACE_EASE;
        s.pace=easedOver<1e-3?wanted:s.pace+(wanted-s.pace)*(1-Math.exp(-dt/easedOver));
        double speed=s.pace;
        s.speed=speed;
        // Where the body is going, at that pace: the way it has gone over that trail, or the way of the tick.
        if(s.rough>.5F&&span>=.1&&fit>1){s.px=fitX/fit*speed;s.pz=fitZ/fit*speed;}
        else{s.px=going>.5?s.vx/going*speed:s.vx;s.pz=going>.5?s.vz/going*speed:s.vz;}
        // And where it is, for its steps and its pelvis. The box hops up a terrace every tick or two and its place
        // between ticks goes back and forth by a block; a footfall chosen from it went with it, 4 to 7 blocks up
        // and down a steep slope from frame to frame. The place is eased over a tenth of a second and carried on
        // by what that lags at the pace, which on level ground is the place itself.
        double place=1-Math.exp(-dt/PLACE_EASE);
        s.easedX+=(s.originX-s.easedX)*place;s.easedZ+=(s.originZ-s.easedZ)*place;
        if(Math.hypot(s.originX-s.easedX,s.originZ-s.easedZ)>60){s.easedX=s.originX;s.easedZ=s.originZ;}
        s.atX=Mth.lerp(s.rough,s.originX,s.easedX+s.px*PLACE_EASE);s.atZ=Mth.lerp(s.rough,s.originZ,s.easedZ+s.pz*PLACE_EASE);
        float radians=s.yaw*Mth.DEG_TO_RAD;
        double fx=-Mth.sin(radians),fz=Mth.cos(radians),lx=Mth.cos(radians),lz=Mth.sin(radians);
        s.forwardSpeed=s.vx*fx+s.vz*fz;
        double sideSpeed=s.vx*lx+s.vz*lz;
        s.lateral=going>1e-3?Math.min(1,Math.abs(sideSpeed)/going):0;
        s.moving=going>MOVE_AT&&eva.groundGaitTravelR64(going);
        if(s.skidding)
        {
            s.skidAge+=dt;
            if(going<EvaMotionModelR64.tier(eva).walk()*SKID_UNTIL||s.skidAge>SKID_LONGEST)s.skidding=false;
            else
            {
                // The feet go with the body, set as they came down, and no step is taken.
                Foot[] feet={s.left,s.right};
                long nanos=AircraftRenderClockR21.frameNanos();
                boolean dust=nanos-s.skidDust>50_000_000L&&!eva.isSilent();
                if(dust)s.skidDust=nanos;
                for(int i=0;i<2;i++)
                {
                    Foot f=feet[i];
                    f.x=s.atX+s.skidX[i];f.z=s.atZ+s.skidZ[i];f.down=true;f.swing=0;f.quick=false;
                    double under=column(s,eva,f.x,f.z);
                    if(Double.isFinite(under)&&Math.abs(under-f.y)<rig.leg()*.3)f.y=under;
                    if(!dust)continue;
                    // What the soles tear up is thrown ahead of them.
                    var state=eva.level().getBlockState(BlockPos.containing(f.x,f.y-.2,f.z));
                    if(state.isAir())continue;
                    var random=eva.getRandom();
                    double ax=s.vx/Math.max(going,1e-3),az=s.vz/Math.max(going,1e-3);
                    for(int k=0;k<14;k++)
                        eva.level().addParticle(new BlockParticleOption(ParticleTypes.BLOCK,state),f.x+random.nextGaussian()*2.2,f.y+.3+random.nextDouble()*.3,
                                f.z+random.nextGaussian()*2.2,ax*.35+random.nextGaussian()*.12,.1+random.nextDouble()*.2,az*.35+random.nextGaussian()*.12);
                    for(int k=0;k<3;k++)
                        eva.level().addParticle(ParticleTypes.POOF,f.x+random.nextGaussian()*2,f.y+.6,f.z+random.nextGaussian()*2,
                                ax*.08+random.nextGaussian()*.04,random.nextDouble()*.05,az*.08+random.nextGaussian()*.04);
                }
                s.moving=false;s.running=false;
            }
        }
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
            // In a turn the steps come quicker, and so shorter. A foot planted a long stride ahead is carried across
            // the body as the body turns over it: at a walk turning 80 degrees a second the body turned 59 degrees
            // in one step and the legs crossed. At TURN_CADENCE steps a second it turns 31 in one.
            cadence=Math.max(cadence,TURN_CADENCE*Math.min(1,Math.abs(s.yawRate)/TURN_FULL));
            if(s.forwardSpeed<0)cadence=Math.max(cadence,-s.forwardSpeed/BACK_STEP);
            // Nor up or down a steep slope: a step of level ground's length is as much up as along on a slope of
            // one in one, further than a leg is long. More steps of less, as far as legs go quicker.
            double steep=Mth.clamp((Math.abs(Math.tan(Math.toRadians(s.slopeAhead)))-STEEP_FROM)/(1-STEEP_FROM),0,1);
            if(steep>0)cadence=Math.max(cadence,Math.min(STEEP_CADENCE,speed/Mth.lerp(steep,STEP_LEVEL,STEP_STEEP)));
            s.duty=gait.duty();s.cycle=2/cadence;s.land=gait.land();s.lift=gait.lift();s.sink=gait.sink();s.bounce=gait.bounce();
            double half=rig.footHalf()*gait.width();
            s.half=Mth.lerp(s.lateral*Math.min(1,speed/8),half,Math.max(half,WIDE_HALF));
            // Heel first at a walk going forward; flat at a run, and going sideways or backward.
            double walking=Mth.clamp((s.duty-.40)/.22,0,1),ahead=Mth.clamp(s.forwardSpeed/Math.max(going,1e-3)*2-1,0,1);
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
            if(f.down&&Math.hypot(f.x-s.atX,f.z-s.atZ)>lost){s.live=false;return;}
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
                    boolean over=!due&&s.moving&&f.reachShort>.6&&stays&&f.stood>MIN_STANCE;
                    if(due||over)lift(s,f,over);
                    if(due){f.liftLocal=local;f.swingTime=(1-local)*s.cycle;f.travelling=s.moving;}
                }
                if(!f.down)
                {
                    boolean landed,stopped=STOPPED&&f.travelling&&!s.moving;
                    if(stopped&&!f.quick)f.quick=true;
                    if(f.quick){f.swing+=dt/(float)QUICK_SWING;landed=f.swing>=1;}
                    else
                    {
                        landed=local<f.liftLocal;
                        f.swing=landed?1:(float)((local-f.liftLocal)/Math.max(1e-3,1-f.liftLocal));
                    }
                    retarget(s,eva,f,local);
                    if(landed)
                    {
                        land(s,eva,f);f.travelling=false;
                        if(stopped&&other.down&&lag(s,other)>=1)s.phase=frac(other.offset+s.duty-WEIGHT_SHIFT/s.cycle);
                    }
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
        // And into a slope: forward going up it, a little back coming down.
        double before=column(s,eva,s.atX-fx*6,s.atZ-fz*6),after=column(s,eva,s.atX+fx*6,s.atZ+fz*6);
        double lie=Double.isFinite(before)&&Double.isFinite(after)?Math.toDegrees(Math.atan2(after-before,12)):0;
        s.slopeAhead+=(lie-s.slopeAhead)*(1-Math.exp(-dt/.3));
        leanTarget+=Mth.clamp((float)s.slopeAhead*SLOPE_LEAN,-SLOPE_LEAN_DOWN,SLOPE_LEAN_UP)*(float)Mth.clamp(s.forwardSpeed/walk,-1,1);
        float bankTarget=Mth.clamp(s.yawRate*Mth.DEG_TO_RAD*(float)s.fast*BANK_GAIN,-BANK_MOST,BANK_MOST);
        int steps=Math.max(1,Mth.ceil(dt/.004F));float h=dt/steps;
        for(int i=0;i<steps;i++)
        {
            s.dipRate+=(-2*s.dipStiff*s.dipRate-s.dipStiff*s.dipStiff*s.dip)*h;s.dip+=s.dipRate*h;
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
        if(!s.moving&&Math.hypot(s.atX-f.restBodyX,s.atZ-f.restBodyZ)<TIDY_AT
                &&Math.abs(Mth.wrapDegrees(s.yaw-f.restBodyYaw))<TIDY_TURN)return 0;
        boolean tidy=s.still>TIDY_AFTER;
        double side=f.lat*s.rig.footHalf();
        double x=s.atX+leftX(s.yaw)*side,z=s.atZ+leftZ(s.yaw)*side;
        double distance=Math.hypot(x-f.x,z-f.z),turn=Math.abs(Mth.wrapDegrees(s.yaw-f.lat*TOE_OUT-f.yaw));
        return Math.max(distance/(tidy?TIDY_AT:STEP_AT),turn/(tidy?TIDY_TURN:STEP_TURN));
    }

    /** From standing, the foot that is further behind on the way the body goes steps first; level, the one on the side it goes to. */
    private static Foot firstToStep(State s)
    {
        double speed=Math.max(Math.hypot(s.vx,s.vz),1e-3),dx=s.vx/speed,dz=s.vz/speed;
        double left=(s.left.x-s.atX)*dx+(s.left.z-s.atZ)*dz,right=(s.right.x-s.atX)*dx+(s.right.z-s.atZ)*dz;
        if(Math.abs(left-right)>1)return left<right?s.left:s.right;
        double toLeft=dx*leftX(s.yaw)+dz*leftZ(s.yaw);
        if(Math.abs(toLeft)>.3)return (toLeft>0)==(s.left.lat>0)?s.left:s.right;
        return s.lastStep>0?s.right:s.left;
    }

    private static void lift(State s,Foot f,boolean quick)
    {
        f.down=false;f.swing=0;f.quick=quick;f.liftLocal=0;f.landWith=0;f.swingTime=QUICK_SWING;
        f.fromX=f.ankleX;f.fromY=f.ankleY;f.fromZ=f.ankleZ;f.fromYaw=f.yaw;f.fromPitch=f.pitch;f.fromGround=f.y;f.fromSlope=f.slope;
        f.toX=f.x;f.toY=f.y;f.toZ=f.z;f.toYaw=f.yaw;f.toSlope=f.slope;f.clear=0;f.targeted=false;f.settled=false;f.share=1;
        s.lastStep=f.sign;
    }

    /** The footfall of a swinging foot: under where its hip will be when the body is over it, on its own side. */
    private static void retarget(State s,EvaUnit01Entity eva,Foot f,double local)
    {
        double left=f.quick?(1-f.swing)*QUICK_SWING:f.swing>=1?0:(1-local)*s.cycle,ahead=left+s.land*s.stanceSeconds;
        f.timeLeft=left;
        // Over its footfall the foot only comes down: the footfall is settled. Chosen anew to the last frame, a
        // foot coming down through a curve went 0.9 blocks over the ground in its last quarter block of height.
        if(f.swing>=(f.quick?.8F:OVER_BY))
        {
            // Settled where it is, on the ground as it is there: taken up over a twentieth of a second, the height
            // of a footfall that had just moved onto a kerb was still a block short of the kerb's top when the
            // foot stopped looking, and the foot stood a block inside the kerb.
            if(!f.settled)
            {
                Footing last=footing(s,eva,s.rig,f.toX,f.toZ,f.toYaw,f.toY);
                if(last.found())
                {
                    f.toY=last.y();f.toSlope=last.slope();
                    // What is left of a small move along the sole goes with it (that height is the moved footfall's).
                    if(Math.abs(last.shift())<=1)
                    {
                        f.toX+=-Mth.sin(f.toYaw*Mth.DEG_TO_RAD)*last.shift();f.toZ+=Mth.cos(f.toYaw*Mth.DEG_TO_RAD)*last.shift();
                    }
                }
                f.settled=true;
            }
            return;
        }
        // Where the body will face over that foot. No further ahead than a third of a second: a body coming to rest
        // has a long cycle, and a turn begun then read on over all of it swung the footfall 50 degrees round and
        // back within two frames.
        float yaw=s.yaw+Mth.clamp(s.yawRate*(float)Math.min(TURN_AHEAD,left+s.stanceSeconds*.5),-30,30);
        double side=f.lat*s.half,near=Double.isFinite(s.ground)?s.ground:eva.getY();
        float heading=yaw-f.lat*TOE_OUT;
        double x=s.atX+s.px*ahead*f.share+leftX(yaw)*side,z=s.atZ+s.pz*ahead*f.share+leftZ(yaw)*side;
        Footing ground=footing(s,eva,s.rig,x,z,heading,near);
        // Nothing to stand on there (a wall, a drop past the leg's reach): a shorter step, down to one under the
        // hip, and for the rest of this swing (a footfall that went back and forth between the two carried the foot with it).
        while(!ground.found()&&f.share>0)
        {
            f.share=f.share>.5?.5:0;
            x=s.atX+s.px*ahead*f.share+leftX(yaw)*side;z=s.atZ+s.pz*ahead*f.share+leftZ(yaw)*side;
            ground=footing(s,eva,s.rig,x,z,heading,near);
        }
        if(ground.shift()!=0)
        {
            // Across a kerb's edge: on, or back, until the whole sole stands on one level.
            x+=-Mth.sin(heading*Mth.DEG_TO_RAD)*ground.shift();z+=Mth.cos(heading*Mth.DEG_TO_RAD)*ground.shift();
        }
        if(STOPPED&&ground.found())
        {
            double knee=s.rig.leg()*.5;
            Vec3 body=new Vec3(s.atX,near+knee,s.atZ),foot=new Vec3(x,ground.y()+knee,z);
            Vec3 clear=EvaFootfallWalls.constrain(body,foot,heading,s.rig.tip(),s.rig.heel(),s.rig.sole(),
                    (from,to)->eva.level().clip(new ClipContext(from,to,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,eva)));
            if(!clear.equals(foot))
            {
                Footing support=footing(s,eva,s.rig,clear.x,clear.z,heading,near);
                if(support.found())
                {
                    x=clear.x;z=clear.z;ground=support;
                }
                else
                {
                    // The clear side borders a drop. This foot can return to the surface it pushed off.
                    x=f.x;z=f.z;heading=f.yaw;ground=new Footing(f.y,f.slope,0,true);
                }
            }
        }
        if(f.targeted)
        {
            // Chosen anew every frame as the ground under it changes: taken up over a twentieth of a second, so a
            // footfall that goes from one side of an edge to the other does not carry the foot with it in one frame.
            // (Quicker as the foot nears its footfall: by then it is where it will be.)
            double take=1-Math.exp(-s.dt/(.01+.04*Math.max(0,1-f.swing/OVER_BY)));
            f.toX+=(x-f.toX)*take;f.toZ+=(z-f.toZ)*take;f.toY+=(ground.y()-f.toY)*take;f.toSlope+=(ground.slope()-f.toSlope)*(float)take;
            f.toYaw+=Mth.wrapDegrees(heading-f.toYaw)*(float)take;
        }
        else
        {
            f.toX=x;f.toZ=z;f.toY=ground.y();f.toSlope=ground.slope();f.toYaw=heading;f.targeted=true;
        }
        // The way there: how much higher than its own arc the foot must go to clear what stands between.
        Vector3f to=ankleAt(s.rig,f.toX,f.toY,f.toZ,f.toYaw,f.toSlope,0,new Vector3f());
        double distance=Math.hypot(to.x-f.fromX,to.z-f.fromZ),need=0;
        for(float at:new float[]{.2F,.35F,.5F,.65F,.8F})
        {
            double along=along(s,f,at,distance);
            double px=Mth.lerp(along,f.fromX,to.x),pz=Mth.lerp(along,f.fromZ,to.z);
            // Under the ankle, the toes and the heel: the ankle cleared a terrace's edge and the toes went 3 blocks into it.
            double ux=distance>1e-3?(to.x-f.fromX)/distance:0,uz=distance>1e-3?(to.z-f.fromZ)/distance:0;
            for(double reach:new double[]{-s.rig.heel()*.8,0,s.rig.toe()*.8})
            {
                double under=column(s,eva,px+ux*reach,pz+uz*reach);
                if(Double.isFinite(under))need=Math.max(need,under+s.rig.ankle()+CLEARANCE-swingHeight(s,f,at,to.y,distance));
            }
        }
        // Taken up quickly and let go slowly, never in one frame: what it needs changes block by block.
        f.clear+=(need-f.clear)*(1-Math.exp(-s.dt/(need>f.clear?.05:.2)));
    }

    /**
     * The run's swing, read off the capture's own run (the run up to R63, tools/fr_swing.py): the toes stay where
     * they pushed off while the body flies on, so the leg trails out behind the hips (the ankle 13 behind as it
     * leaves the ground, 20 behind two tenths of the swing later) and the heel comes up there, 16 blocks at four
     * tenths of the swing with the ankle still 15 behind; then the foot comes through quickly and low, is ahead of
     * the hips from two thirds of the swing and waits there for the ground. The thigh is never raised more than 48
     * degrees. Lifted evenly and carried forward from the first frame, as a walk's foot is, the foot was under the
     * hips at three tenths of the swing and 15 high there: the thigh went up to 104 degrees, over level, and the
     * leg behind was never seen. The Unit ran on the spot with its knees up.
     * RUN_TRAIL: how late the foot starts over the ground (the power its eased way is raised to). RUN_KICK_AT and
     * RUN_KICK_SHARP: where in the swing the heel is highest (0.72: at four tenths) and how narrow that is.
     */
    private static final double RUN_TRAIL=1.7,RUN_KICK_AT=.72,RUN_KICK_SHARP=2.2;

    /** How much of the run's own swing a foot has: all of it at a run, none at a walk or at the fast run's full speed. */
    private static double running(State s)
    {
        return Mth.clamp((.62-s.duty)/(.62-EvaMotionModelR64.RUN_DUTY),0,1)*(1-Mth.clamp((s.speed-FAST_FROM)/(EvaMotionModelR64.SPRINT-FAST_FROM),0,1));
    }

    /** How far along its way over the ground a swinging foot is (0 to 1). */
    private static double along(State s,Foot f,float swing,double distance)
    {
        // Over the ground the ankle leaves at the body's own speed, as the toes that it rolled over let it
        // go, and is over its footfall a little before it is down on it, so it comes down and does not
        // skid in. Eased from rest it fell 5 blocks further behind a fast run's hip in its first frames,
        // past the leg's reach, and the thigh whipped after it (34 degrees in a frame); eased to the very
        // end it was within a quarter block of the ground with 0.8 blocks still to go.
        float over=Math.min(1,swing/OVER_BY);
        double carried=Mth.clamp(s.speed*f.swingTime*OVER_BY/Math.max(distance,1e-3),0,1.2);
        double eased=(3-2*over)*over*over,walked=(over*over*over-2*over*over+over)*carried+eased,running=running(s);
        return running<=0?walked:Mth.lerp(running,walked,Math.pow(eased,RUN_TRAIL));
    }

    /** How high a swinging foot's ankle is, before what it adds to clear the ground on its way. */
    private static double swingHeight(State s,Foot f,float swing,double toY,double distance)
    {
        // Up or down by as much of the way as it has gone over the ground: along a slope it follows the slope. (What
        // stands in its way, a kerb's edge, is cleared by what the foot adds for that.) Risen first and gone over
        // after, a foot climbing a slope of one in one was level with its own hip while still behind it and passed
        // through the hip's place on its way forward: with no line left from hip to ankle the leg turned over, 150
        // to 180 degrees in a frame, once a step.
        double height=Mth.lerp(along(s,f,swing,distance),f.fromY,toY);
        // A fast run folds the leg up behind it at once: the lift comes early.
        double fast=Mth.clamp((s.speed-FAST_FROM)/(EvaMotionModelR64.SPRINT-FAST_FROM),0,1);
        double even=Math.sin(Math.PI*Math.pow(swing,Mth.lerp(fast,1,.62))),running=running(s);
        // A run's heel comes up behind the body and is down again as the foot comes through.
        if(running>0)even=Mth.lerp(running,even,Math.pow(Math.sin(Math.PI*Math.pow(swing,RUN_KICK_AT)),RUN_KICK_SHARP));
        return height+s.lift*Mth.clamp(distance/4,.35,1)*even;
    }

    private static void land(State s,EvaUnit01Entity eva,Foot f)
    {
        double step=Math.hypot(f.toX-f.fromX,f.toZ-f.fromZ);
        f.down=true;f.x=f.toX;f.y=f.toY;f.z=f.toZ;f.yaw=f.toYaw;f.slope=f.toSlope;f.stood=0;f.strike=Math.max(0,f.landWith);f.swing=0;f.quick=false;
        f.restBodyX=s.moving?Double.NaN:s.atX;f.restBodyZ=s.atZ;f.restBodyYaw=s.yaw;
        f.roll=Mth.clamp(.2*s.stanceSeconds,.05,.2);
        // The weight comes down on the foot: the pelvis gives by this much and comes back (a damped spring).
        double give=s.moving?Mth.lerp(Mth.clamp((.62-s.duty)/.32,0,1),DIP_WALK,DIP_RUN)*Mth.clamp(s.speed/20,.3,1):DIP_SPOT;
        s.dipRate-=give*s.dipStiff*Math.E;
        footfall(s,eva,f,step);
    }

    /**
     * What a sole stands on at a place: the height under its ankle, the lie of the ground along it, how far the
     * footfall should move along the sole to stand on one level of a kerb, and whether there is ground at all.
     */
    private record Footing(double y,float slope,double shift,boolean found){}

    private static Footing footing(State s,EvaUnit01Entity eva,Rig rig,double x,double z,float yaw,double near)
    {
        float radians=yaw*Mth.DEG_TO_RAD;double hx=-Mth.sin(radians),hz=Mth.cos(radians),lx=Mth.cos(radians),lz=Mth.sin(radians);
        double[] at=new double[STATIONS],high=new double[STATIONS];int found=0;
        // Each block read, by where along the sole it begins and ends: its top and those two.
        double[] tops=new double[STATIONS*3],begins=new double[STATIONS*3],ends=new double[STATIONS*3];int blocks=0;
        // Half of what a block one across measures along the sole's heading.
        double span=(Math.abs(hx)+Math.abs(hz))*.5;
        for(int i=0;i<STATIONS;i++)
        {
            at[i]=Mth.lerp(i/(STATIONS-1D),-rig.heel()*.92,rig.toe()*.92);
            double best=Double.NaN;
            for(double side:new double[]{-rig.sole()*.8,0,rig.sole()*.8})
            {
                double px=x+hx*at[i]+lx*side,pz=z+hz*at[i]+lz*side,under=column(s,eva,px,pz);
                if(!Double.isFinite(under))continue;
                if(!(best>=under))best=under;
                double middle=(Mth.floor(px)+.5-x)*hx+(Mth.floor(pz)+.5-z)*hz;
                tops[blocks]=under;begins[blocks]=middle-span;ends[blocks++]=middle+span;
            }
            high[i]=best;if(Double.isFinite(best))found++;
        }
        if(found*2<STATIONS)return new Footing(near,0,0,false);
        // A station over a gap or in a wall: as the nearest one that found ground.
        for(int i=0;i<STATIONS;i++)
        {
            if(Double.isFinite(high[i]))continue;
            for(int d=1;d<STATIONS&&!Double.isFinite(high[i]);d++)
            {
                if(i-d>=0&&Double.isFinite(high[i-d]))high[i]=high[i-d];
                else if(i+d<STATIONS&&Double.isFinite(high[i+d]))high[i]=high[i+d];
            }
        }
        double low=Double.POSITIVE_INFINITY,top=Double.NEGATIVE_INFINITY;
        for(double h:high){low=Math.min(low,h);top=Math.max(top,h);}
        double rise=top-low;
        if(rise<FLAT_RISE)return new Footing(top,0,0,true);
        int edge=0;double jump=0;
        for(int i=0;i+1<STATIONS;i++)if(Math.abs(high[i+1]-high[i])>jump){jump=Math.abs(high[i+1]-high[i]);edge=i;}
        if(rise>KERB_RISE&&jump>=KERB_SHARE*rise)
        {
            // A kerb: the sole stands on one level, the one more of it is over.
            double where=(at[edge]+at[edge+1])*.5;
            boolean beyond=(STATIONS-1-edge)*2>=STATIONS;
            // A rise the body itself could not step is a wall: the sole stands on the near side of it, whichever way it faces.
            if(jump>WALL)beyond=high[edge+1]<high[edge];
            double level=Double.NEGATIVE_INFINITY;
            for(int i=beyond?edge+1:0;i<(beyond?STATIONS:edge+1);i++)level=Math.max(level,high[i]);
            double shift=beyond?where+rig.heel()+EDGE_MARGIN:where-rig.toe()-EDGE_MARGIN;
            return new Footing(level,0,Mth.clamp(shift,-SHIFT_MOST,SHIFT_MOST),true);
        }
        // A slope (terraces are one): the sole lies along it, on its highest points.
        double meanAt=0,meanHigh=0;
        for(int i=0;i<STATIONS;i++){meanAt+=at[i];meanHigh+=high[i];}
        meanAt/=STATIONS;meanHigh/=STATIONS;
        double over=0,under=0;
        for(int i=0;i<STATIONS;i++){over+=(at[i]-meanAt)*(high[i]-meanHigh);under+=(at[i]-meanAt)*(at[i]-meanAt);}
        double most=Math.tan(SOLE_SLOPE_MOST*Mth.DEG_TO_RAD),lie=Mth.clamp(over/under,-most,most);
        // It rests on the block that stands highest over its line, at that block's downhill edge: a terrace's
        // corner. Taken where the block happened to be read, up to a block in from its corner, the sole lay half a
        // block inside every corner of a slope of one in two and a half.
        // And only on blocks under it as it lies: along a slope it covers less ground than it is long. Read to
        // its full length, a sole lying at 30 degrees on a slope of one in one rested on a block half a block
        // past its toes and stood half a block over the ground.
        double flat=1/Math.sqrt(1+lie*lie),from=-rig.heel()*flat,to=rig.toe()*flat;
        double rest=Double.NEGATIVE_INFINITY,where=0;
        for(int i=0;i<blocks;i++)
        {
            if(begins[i]>to||ends[i]<from)continue;
            double touch=lie>0?Math.max(begins[i],from):Math.min(ends[i],to),stands=tops[i]-lie*touch;
            if(stands>rest){rest=stands;where=touch;}
        }
        if(rest==Double.NEGATIVE_INFINITY)return new Footing(meanHigh-lie*meanAt-SLOPE_SINK,(float)Math.toDegrees(Math.atan(lie)),0,true);
        // A block under no more than the last of its toes (or of its heel, the ground falling toward the toes)
        // does not carry it: the flat of the sole ends a tenth of a block short of the foot's length, and resting
        // on such a block it stood 0.8 blocks over the one before. The footfall moves on until half a block of
        // the sole is on what it rests on.
        double shift=lie>0?Math.max(0,where-(to-SOLE_HOLD)):Math.min(0,where-(from+SOLE_HOLD));
        if(shift!=0)rest+=lie*shift;
        // On the corners of terraces a sole lying on the highest of them stands clear of all the rest: it is let
        // a tenth of a block into them, between standing in the ground and standing over it.
        return new Footing(rest-SLOPE_SINK,(float)Math.toDegrees(Math.atan(lie)),shift,true);
    }

    /** The ground in a block column, as last read within a second and with the body at about the same level. */
    private static double column(State s,EvaUnit01Entity eva,double x,double z)
    {
        long now=AircraftRenderClockR21.frameNanos();
        double level=eva.getY();
        if(now-s.columnsAt>1_000_000_000L||!(Math.abs(level-s.columnsNear)<3)||s.columns.size()>4096)
        {
            s.columns.clear();s.columnsAt=now;s.columnsNear=level;
        }
        long key=((long)Mth.floor(x)<<32)^(Mth.floor(z)&0xffffffffL);
        Double known=s.columns.get(key);
        if(known!=null)return known;
        double y=ground(eva,Mth.floor(x)+.5,Mth.floor(z)+.5,s.columnsNear);
        s.columns.put(key,y);
        return y;
    }

    /**
     * The ground at a place, looked for about the body's own level: from GROUND_ABOVE over it down to GROUND_BELOW
     * under it. Ground more than STEP_MOST over the body's level is a wall and not a step, as it is for the body
     * itself; a place roofed over at the top of the search is one too.
     * <p>
     * Up to M1 it was looked for 21 blocks either side of the level the feet stood on. Running up a slope of one
     * in one the next footfall lies further above the feet than that: the search began inside the hill, found
     * nothing, and the foot was set down at the feet's old level. From then on every footfall was, and the body,
     * carried by its feet, was drawn 60 to 87 blocks down inside the slope while the Unit stood on its top.
     */
    private static double ground(EvaUnit01Entity eva,double x,double z,double level)
    {
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

    /**
     * R64 (M3): what the Unit walks through (a fence, a lamp's foot, anything its body does not stop at) is seen
     * and heard to give under a foot set down on it: the block's own fragments and its breaking sound, four
     * blocks a footfall at most. Nothing in the world is changed: the map is not the Unit's to break.
     */
    private static void trodden(State s,EvaUnit01Entity eva,Foot f)
    {
        var level=eva.level();var random=eva.getRandom();
        float radians=f.yaw*Mth.DEG_TO_RAD;double hx=-Mth.sin(radians),hz=Mth.cos(radians);
        int found=0;long last=Long.MIN_VALUE;
        for(double along=-s.rig.heel();along<=s.rig.toe()&&found<4;along+=1)
            for(double side:new double[]{-s.rig.sole()*.6,0,s.rig.sole()*.6})
                for(int up=0;up<3&&found<4;up++)
                {
                    BlockPos pos=BlockPos.containing(f.x+hx*along+hz*side,f.y+.1+up,f.z+hz*along-hx*side);
                    if(pos.asLong()==last)continue;
                    var state=level.getBlockState(pos);
                    if(state.isAir())continue;
                    var shape=state.getCollisionShape(level,pos,CollisionContext.of(eva));
                    if(shape.isEmpty()||!EvaObstacleCollision.ignores(eva,state,pos,shape))continue;
                    last=pos.asLong();found++;
                    for(int i=0;i<10;i++)
                        level.addParticle(new BlockParticleOption(ParticleTypes.BLOCK,state),pos.getX()+random.nextDouble(),pos.getY()+random.nextDouble(),
                                pos.getZ()+random.nextDouble(),random.nextGaussian()*.12,random.nextDouble()*.2,random.nextGaussian()*.12);
                    if(found==1)level.playLocalSound(pos.getX()+.5,pos.getY()+.5,pos.getZ()+.5,state.getSoundType().getBreakSound(),SoundSource.BLOCKS,1.6F,.8F,false);
                }
    }

    /** A footfall is heard and seen where it is drawn: each client sounds its own (the server sounds none for this model). */
    private static void footfall(State s,EvaUnit01Entity eva,Foot f,double step)
    {
        if(DIAG)ProjectSeele.LOGGER.info("R64PLANT land {} step {} speed {} cadence {} duty {} at {} {} {}",f.side,
                String.format(java.util.Locale.ROOT,"%.1f",step),String.format(java.util.Locale.ROOT,"%.1f",s.speed),
                String.format(java.util.Locale.ROOT,"%.2f",2/s.cycle),String.format(java.util.Locale.ROOT,"%.2f",s.duty),
                String.format(java.util.Locale.ROOT,"%.1f",f.x),String.format(java.util.Locale.ROOT,"%.1f",f.y),String.format(java.util.Locale.ROOT,"%.1f",f.z));
        if(eva.isSilent()||eva.isVisuallyAirborneForRender())return;
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
        trodden(s,eva,f);
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
        float height=ankle.y*scale,toe=height*1.9F,heel=height*.75F,wide=height*.45F,tip=toe,tipUp=0;
        var points=EvaMeshPointsR63.of(eva,EvaGroundContactR56.PARTS).feet().get("l");
        if(points!=null&&points.length>0)
        {
            float low=Float.POSITIVE_INFINITY;
            for(Vector3f p:points)low=Math.min(low,p.y);
            float front=0,rear=0,side=0;
            // What stands on the ground: the part of the foot within half a block of its lowest point.
            for(Vector3f p:points)
            {
                if(p.y>low+.5F/scale)continue;
                front=Math.max(front,ankle.z-p.z);rear=Math.max(rear,p.z-ankle.z);side=Math.max(side,Math.abs(p.x-ankle.x));
            }
            height=(ankle.y-low)*scale;toe=front*scale;heel=rear*scale;wide=side*scale;
            // The foremost point of the whole foot: the toe cap, which stands up off the ground ahead of the sole.
            float foremost=Float.NEGATIVE_INFINITY;
            for(Vector3f p:points)if(ankle.z-p.z>foremost){foremost=ankle.z-p.z;tipUp=(p.y-low)*scale;}
            tip=Math.max(toe,foremost*scale);
        }
        Rig rig=new Rig(scale,Math.abs(hip.x)*scale,Math.abs(ankle.x)*scale,length,height,toe,heel,wide,tip,tipUp);
        ProjectSeele.LOGGER.info("R64PLANT rig of unit {}: scale {} leg {} hip half {} foot half {} ankle {} toe {} heel {} sole half {} (mesh {})",
                eva.getUnitVariant(),rig.scale(),rig.leg(),rig.hipHalf(),rig.footHalf(),rig.ankle(),rig.toe(),rig.heel(),rig.sole(),points!=null&&points.length>0);
        return rig;
    }

    /**
     * The ankle of a foot whose sole would lie on the ground at a place (the ground rising toward its toes by
     * {@code slope} degrees), rolled from there over its heel (pitch above 0) or its toes (below).
     */
    private static Vector3f ankleAt(Rig rig,double x,double y,double z,float yaw,float slope,float pitch,Vector3f out)
    {
        float radians=yaw*Mth.DEG_TO_RAD;double hx=-Mth.sin(radians),hz=Mth.cos(radians);
        float lie=slope*Mth.DEG_TO_RAD,turn=(slope+pitch)*Mth.DEG_TO_RAD;
        // The point it rolls over, on the line of the ground through the place; from there to the ankle in the turned foot.
        double reach=pitch>=0?-rig.heel():rig.toe();
        double along=reach*Mth.cos(lie)-reach*Mth.cos(turn)-rig.ankle()*Mth.sin(turn);
        double up=reach*Mth.sin(lie)-reach*Mth.sin(turn)+rig.ankle()*Mth.cos(turn);
        // Far up on its toes the foot stands on its toe cap, not on the front of its sole: rolled about the
        // sole's front the cap went a block into the ground (a foot left behind by a body that had just stopped).
        if(pitch<0)up+=Math.max(0,(rig.tip()-rig.toe())*Mth.sin(-pitch*Mth.DEG_TO_RAD)-rig.tipUp()*Mth.cos(-pitch*Mth.DEG_TO_RAD));
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

    /** A heel strike can pivot only where the heel itself has support. On steep terraces the
     * uphill end can carry a flat sole while the downhill heel hangs over a lower tread. */
    private static float supportedHeelRoll(State s,EvaUnit01Entity eva,double x,double y,double z,float yaw,float slope,float pitch)
    {
        if(pitch<=0||slope<=0)return pitch;
        double lie=slope*Mth.DEG_TO_RAD,heading=yaw*Mth.DEG_TO_RAD;
        double heel=s.rig.heel(),back=heel*Math.cos(lie),width=s.rig.sole()*.8;
        double hx=x+Math.sin(heading)*back,hz=z-Math.cos(heading)*back;
        double sideX=Math.cos(heading)*width,sideZ=Math.sin(heading)*width;
        double highest=Double.NEGATIVE_INFINITY;
        for(int side=-1;side<=1;side++)
        {
            double under=column(s,eva,hx+side*sideX,hz+side*sideZ);
            if(Double.isFinite(under))highest=Math.max(highest,under);
        }
        double gap=y-heel*Math.sin(lie)-highest;
        return (float)(pitch*Mth.clamp((FLAT_RISE-gap)/(FLAT_RISE-SLOPE_SINK),0,1));
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
    private static float rolled(Rig rig,double x,double y,double z,float yaw,float slope,float pitch,double hipX,double hipZ,double above,double nominal)
    {
        Vector3f probe=new Vector3f();
        if(reach(rig,ankleAt(rig,x,y,z,yaw,slope,pitch,probe),hipX,hipZ,above)>=nominal)return pitch;
        float radians=yaw*Mth.DEG_TO_RAD;
        double along=(hipX-x)*-Mth.sin(radians)+(hipZ-z)*Mth.cos(radians);
        boolean ahead=along>0;
        // A roll brings the ankle toward a hip that is ahead of the foot or behind it, not one beside it: a foot
        // set down wide of the body rolled to its limit in the frame it landed (25 degrees) and gained nothing.
        float limit=(ahead?-HEEL_OFF_MOST:TOES_UP_MOST)*(float)Mth.clamp(Math.abs(along)/(.25*rig.leg()),0,1);
        if(ahead?pitch<=limit:pitch>=limit)return pitch;
        if(reach(rig,ankleAt(rig,x,y,z,yaw,slope,limit,probe),hipX,hipZ,above)<nominal)return limit;
        float low=pitch,high=limit;
        for(int k=0;k<9;k++)
        {
            float mid=(low+high)*.5F;
            if(reach(rig,ankleAt(rig,x,y,z,yaw,slope,mid,probe),hipX,hipZ,above)<nominal)low=mid;else high=mid;
        }
        return high;
    }

    /** How high the middle of the hips may stand over a foot: its ankle, and what the leg reaches above it. */
    private static double reach(Rig rig,Vector3f ankle,double hipX,double hipZ,double hipAboveCentre)
    {
        double most=rig.leg()*reachShare,flat=Math.hypot(hipX-ankle.x,hipZ-ankle.z);
        return ankle.y+(flat>=most?0:Math.sqrt(most*most-flat*flat))-hipAboveCentre;
    }

    /**
     * Poses the pelvis and the legs for this frame, over whatever the clips have written.
     */
    static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        long began=DIAG?System.nanoTime():0;
        try
        {
            return applying(eva,model,partial,root);
        }
        finally
        {
            if(DIAG)cost(System.nanoTime()-began,false);
        }
    }

    private static EvaMotionEngineV2.BoneWrites applying(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
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
            s.pace=Math.hypot(s.vx,s.vz);s.px=s.vx;s.pz=s.vz;s.trailFilled=0;s.rough=0;s.carried=0;
            s.easedX=s.originX-s.px*PLACE_EASE;s.easedZ=s.originZ-s.pz*PLACE_EASE;s.atX=s.originX;s.atZ=s.originZ;
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
                f.restBodyX=Double.NaN;f.down=true;f.swing=0;f.quick=false;f.stood=1;f.strike=0;f.support=1;f.reachShort=0;
                f.yaw=Math.hypot(toes.x,toes.z)>.2?(float)(Mth.atan2(-toes.x,toes.z)*Mth.RAD_TO_DEG):s.yaw;
                f.x=at.x;f.z=at.z;
                Footing ground=footing(s,eva,rig,f.x,f.z,f.yaw,at.y-rig.ankle());
                f.y=ground.y();f.slope=f.drawnSlope=ground.slope();f.clear=0;
                f.pitch=0;f.drawnYaw=f.yaw;f.ankleX=at.x;f.ankleY=f.y+rig.ankle();f.ankleZ=at.z;
                sum+=f.y;
            }
            s.ground=sum/2;s.height=Double.NaN;s.slopeAhead=0;s.bodyGround=Double.NaN;
            // Come down from a fall: the legs take it up, the pelvis giving by how fast it fell.
            s.dipStiff=DIP_RATE;s.squat=0;
            // R64: down from the air too fast over the ground for a step to catch, it slides on its feet.
            // (Out of the air, that is: SKID_AIR seconds off the ground at least. A fast run is off it for a tick at a kerb.)
            s.skidding=now-s.airAt<400_000_000L&&s.airAt-s.airFrom>=(long)(SKID_AIR*1e9)&&Math.hypot(s.vx,s.vz)>EvaMotionModelR64.tier(eva).walk()*SKID_FROM;s.skidAge=0;
            s.skidX[0]=s.left.x-s.atX;s.skidZ[0]=s.left.z-s.atZ;s.skidX[1]=s.right.x-s.atX;s.skidZ[1]=s.right.z-s.atZ;
            if(now-s.airAt<400_000_000L&&s.fall>LAND_FROM)
            {
                double give=Math.min(LAND_MOST,(s.fall-LAND_FROM)*LAND_GIVE);
                // R64: a hard landing goes deeper and comes up slowly.
                float hard=com.projectseele.entity.EvaLeapR64.on(eva)?com.projectseele.entity.EvaLeapR64.hard(s.fall/20):0;
                give=Mth.lerp(hard,give,ABSORB_MOST);s.dipStiff=Mth.lerp(hard,DIP_RATE,ABSORB_RATE);
                s.dipRate-=give*s.dipStiff*Math.E;
            }
            s.fall=0;
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
        if(fresh)s.sway+=(swayTarget-s.sway)*(1-Math.exp(-dt/SWAY_EASE));
        // Over the body's eased place (which is the frame's own place where this is its first frame).
        double originX=s.atX,originZ=s.atZ;
        double wantX=originX+leftX(s.yaw)*s.sway,wantZ=originZ+leftZ(s.yaw)*s.sway;
        double shiftX=wantX-centre.x,shiftZ=wantZ-centre.z;

        // The level the pelvis is carried over: the feet's own ground.
        double level=0;
        for(Foot f:both)level+=f.down?f.y:Mth.lerp(smooth(f.swing),f.fromGround,f.toY);
        level/=2;
        if(fresh)s.ground=Double.isFinite(s.ground)?s.ground+(level-s.ground)*(1-Math.exp(-dt/GROUND_EASE)):level;
        // Carried over the ground under the body, where the feet stand about it: over the feet's own mean it went
        // up a stair with every footfall on a slope. And lower on a slope by what half a step rises or falls
        // there: the downhill leg does not reach further, and held at that leg's full length the pelvis went
        // from one leg's limit to the other's with each step.
        double under=column(s,eva,s.atX,s.atZ);
        if(!Double.isFinite(under)||Math.abs(under-level)>rig.leg()*.6)under=level;
        if(fresh)s.bodyGround=Double.isFinite(s.bodyGround)&&Math.abs(s.bodyGround-under)<rig.leg()?s.bodyGround+(under-s.bodyGround)*(1-Math.exp(-dt/GROUND_EASE)):under;
        double drop=Math.abs(Math.tan(Math.toRadians(s.slopeAhead)))*s.speed*s.cycle*.25*SLOPE_DROP;
        double nominal=Mth.lerp(s.carried,s.ground,s.bodyGround)+rig.ankle()+rig.leg()-s.sink-Math.min(drop,rig.leg()*.45);
        // A run rises between its footfalls and is lowest over each foot.
        if(s.bounce>0&&s.running)nominal-=s.bounce*Math.cos(4*Math.PI*(s.phase-s.duty*.5));
        // R64: a walk is highest over each foot and lowest between its footfalls (VAULT).
        double vaulting=VAULT&&s.moving?Mth.clamp((s.duty-.40)/.22,0,1)*Mth.clamp(s.speed/6,0,1):0;
        if(fresh)s.vault+=(vaulting-s.vault)*(1-Math.exp(-dt/VAULT_EASE));
        reachShare=(float)Mth.lerp(s.vault,REACH,VAULT_REACH);
        if(s.vault>1e-3)
        {
            double step=.5*s.speed*s.cycle/(VAULT_STEP*rig.leg()),bob=VAULT_BOB*Math.min(1.2,step*step);
            nominal+=s.vault*(s.sink-VAULT_SINK-.5*bob*(1-Math.cos(4*Math.PI*(s.phase-s.duty*.5))));
        }
        nominal+=Math.min(0,s.dip);
        // The landing taken up, the spring is the footfalls' own again.
        if(fresh&&s.dipStiff<DIP_RATE&&s.dip>-.3&&Math.abs(s.dipRate)<2)s.dipStiff=Math.min(DIP_RATE,s.dipStiff+dt*20);
        // R64: gathering to jump, the pelvis is let down over the planted feet and driven up again, the hips back over the heels.
        float gather=com.projectseele.entity.EvaLeapR64.on(eva)?com.projectseele.entity.EvaGameplayMotionR32.takeoffProgressR64(eva,partial):-1;
        double depth=Mth.lerp(Mth.clamp(s.speed/EvaMotionModelR64.tier(eva).run(),0,1),com.projectseele.entity.EvaLeapR64.SQUAT_STANDING,com.projectseele.entity.EvaLeapR64.SQUAT_RUNNING);
        double squatTarget=depth*com.projectseele.entity.EvaLeapR64.squat(gather);
        if(fresh)s.squat+=(squatTarget-s.squat)*(1-Math.exp(-dt/SQUAT_EASE));
        if(s.squat>1e-3)
        {
            nominal-=s.squat;
            double back=SQUAT_BACK*s.squat/com.projectseele.entity.EvaLeapR64.SQUAT_STANDING*(1-Mth.clamp(s.speed/EvaMotionModelR64.tier(eva).walk(),0,1));
            shiftX+=Mth.sin(s.yaw*Mth.DEG_TO_RAD)*back;shiftZ-=Mth.cos(s.yaw*Mth.DEG_TO_RAD)*back;
        }

        // The feet: where each ankle is and how the foot lies.
        Vector3f[] anklesAt={new Vector3f(),new Vector3f()};
        double[] reaches=new double[2];
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];
            double hipX=hips[i].x+shiftX,hipZ=hips[i].z+shiftZ,above=hips[i].y-centre.y;
            if(f.down)
            {
                // A planted foot turns on the ground with the body once the body has turned TWIST_MOST past it.
                float twisted=Mth.wrapDegrees(f.yaw-s.yaw);
                if(Math.abs(twisted)>TWIST_MOST)f.yaw=s.yaw+Math.copySign(TWIST_MOST,twisted);
                float pitch=rolled(rig,f.x,f.y,f.z,f.yaw,f.slope,scheduled(s,f,rig,hipX,hipZ),hipX,hipZ,above,nominal);
                pitch=supportedHeelRoll(s,eva,f.x,f.y,f.z,f.yaw,f.slope,pitch);
                ankleAt(rig,f.x,f.y,f.z,f.yaw,f.slope,pitch,anklesAt[i]);
                f.pitch=pitch;f.drawnYaw=f.yaw;f.drawnSlope=f.slope;reaches[i]=reach(rig,anklesAt[i],hipX,hipZ,above);
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
                double thenX=hipX+s.px*f.timeLeft,thenZ=hipZ+s.pz*f.timeLeft;
                f.landWith=rolled(rig,f.toX,f.toY,f.toZ,f.toYaw,f.toSlope,s.landPitch>0?s.landPitch:heel(s,rig,f.toX,f.toZ,f.toYaw,thenX,thenZ),thenX,thenZ,above,nominal);
                f.landWith=supportedHeelRoll(s,eva,f.toX,f.toY,f.toZ,f.toYaw,f.toSlope,f.landWith);
                float pitch=Mth.lerp(t,f.fromPitch,f.landWith);
                Vector3f to=ankleAt(rig,f.toX,f.toY,f.toZ,f.toYaw,f.toSlope,f.landWith,new Vector3f());
                double distance=Math.hypot(to.x-f.fromX,to.z-f.fromZ),along=along(s,f,f.swing,distance);
                // Higher by what stands in its way, from soon after it leaves until it is over its footfall.
                double cleared=f.clear*smooth(f.swing/.18F)*smooth((1-f.swing)/.12F);
                anklesAt[i].set((float)Mth.lerp(along,f.fromX,to.x),(float)(swingHeight(s,f,f.swing,to.y,distance)+cleared),(float)Mth.lerp(along,f.fromZ,to.z));
                f.drawnSlope=Mth.lerp(t,f.fromSlope,f.toSlope);
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

    /** Review (plantedDiagR64), twenty times a second: R64TWIST. See the hand-in of 2026-11-16 for why these three. */
    private static final float[] twistTold=new float[2],kneeTold=new float[2];
    private static long twistToldAt;
    private static void solve(State s,Foot[] both,GeoBone[] legs,GeoBone[] shins,GeoBone[] ankles,GeoBone[] feet,Vector3f[] hips,Vector3f[] anklesAt,Quaternionf frame,Matrix4f root)
    {
        solveLegs(s,both,legs,shins,ankles,feet,hips,anklesAt,frame,root);
        long now=System.nanoTime();
        if(DIAG&&now-twistToldAt>=50_000_000L)
        {
            twistToldAt=now;
            double across=Math.hypot(hips[0].x-hips[1].x,hips[0].z-hips[1].z)*.5,feetAcross=Math.hypot(anklesAt[0].x-anklesAt[1].x,anklesAt[0].z-anklesAt[1].z)*.5;
            ProjectSeele.LOGGER.info("R64TWIST moving {} speed {} foot {} {} down {} {} knee {} {} sway {} half {} hips {} ankles {}",s.moving,
                    String.format(java.util.Locale.ROOT,"%.1f",s.speed),String.format(java.util.Locale.ROOT,"%.1f",twistTold[0]),String.format(java.util.Locale.ROOT,"%.1f",twistTold[1]),
                    both[0].down,both[1].down,String.format(java.util.Locale.ROOT,"%.1f",kneeTold[0]),String.format(java.util.Locale.ROOT,"%.1f",kneeTold[1]),
                    String.format(java.util.Locale.ROOT,"%.2f",s.sway),String.format(java.util.Locale.ROOT,"%.2f",s.half),
                    String.format(java.util.Locale.ROOT,"%.2f",across),String.format(java.util.Locale.ROOT,"%.2f",feetAcross));
        }
    }
    private static void solveLegs(State s,Foot[] both,GeoBone[] legs,GeoBone[] shins,GeoBone[] ankles,GeoBone[] feet,Vector3f[] hips,Vector3f[] anklesAt,Quaternionf frame,Matrix4f root)
    {
        float body=s.yaw*Mth.DEG_TO_RAD;
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];
            // Minecraft yaw grows clockwise from above, world rotations the other way.
            var turn=new Quaternionf().rotationY(Mth.wrapDegrees(s.yaw-f.drawnYaw)*Mth.DEG_TO_RAD).mul(frame).rotateX((f.drawnSlope+f.pitch)*Mth.DEG_TO_RAD);
            float heading=f.drawnYaw*Mth.DEG_TO_RAD;
            // The knee bends the way the foot and the body point: it lies on the one side of the line from hip to
            // ankle that a knee can, the side reached by turning that line a quarter turn from forward toward up.
            // Given only "forward", a leg reaching forward and up a steep slope had its hip-to-ankle line along
            // that pole; the solver then went by the toes, which said up in one frame and down in the next, and
            // thigh and shin turned 160 degrees and back within three frames.
            var ahead=new Vector3f(-Mth.sin(heading)-Mth.sin(body),0,Mth.cos(heading)+Mth.cos(body));
            if(ahead.lengthSquared()<1e-4F)ahead.set(-Mth.sin(body),0,Mth.cos(body));
            ahead.normalize();
            var line=new Vector3f(anklesAt[i]).sub(hips[i]);
            var pole=new Vector3f(ahead).mul(-line.y).add(0,line.dot(ahead),0);
            if(pole.lengthSquared()<1e-4F)pole.set(ahead);
            double off=EvaRigTransforms.solveLeg(legs[i],shins[i],ankles[i],feet[i],anklesAt[i],turn,pole.normalize(),root);
            f.reachShort=Math.max(0,hips[i].distance(anklesAt[i])-s.rig.leg()*reachShare);
            twistTold[i]=Mth.wrapDegrees(f.drawnYaw-s.yaw);
            kneeTold[i]=Mth.wrapDegrees((float)(Mth.atan2(-ahead.x,ahead.z)*Mth.RAD_TO_DEG)-s.yaw);
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
        reachShare=(float)Mth.lerp(s.vault,REACH,VAULT_REACH);
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
        // (32 to 35 are the arms': how far each hand must be drawn in to clear a wall, and whether it is in one as drawn.)
        double[] w=new double[36];
        w[0]=frac(s.phase);w[1]=s.running?1:0;w[2]=s.moving?1:0;w[3]=s.speed;w[4]=2/s.cycle;w[5]=s.duty;
        Foot[] both={s.left,s.right};
        for(int i=0;i<2;i++)
        {
            Foot f=both[i];int at=6+i*11;
            w[at]=f.down?1:0;w[at+1]=f.swing;w[at+2]=f.drawnSlope+f.pitch;
            w[at+3]=f.down?f.x:f.toX;w[at+4]=f.down?f.y:f.toY;w[at+5]=f.down?f.z:f.toZ;
            w[at+6]=anklesAt[i].x;w[at+7]=anklesAt[i].y;w[at+8]=anklesAt[i].z;w[at+9]=f.reachShort;w[at+10]=f.drawnYaw;
        }
        w[28]=(hips[0].y+hips[1].y)*.5-s.ground;w[29]=s.sway;w[30]=s.lean;w[31]=s.bank;
        LAST.put(eva.getId(),w);
    }

    private EvaPlantedGaitR64(){}
}

package com.projectseele.entity;

import com.projectseele.config.SeeleConfig;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.util.Mth;

/**
 * R64 (M1): which movement model a Unit runs, and the gait table of the new one.
 * <p>
 * The model up to R63 slides one box over the ground and plays clips of a human walking on the level by the
 * distance covered; whatever the feet do on the ground is put right afterwards, layer upon layer. In the new
 * model the feet decide: a foot on the ground stays where it was set down, the next footfall is chosen ahead of
 * the body, and the pelvis is solved from the feet. For a foot not to slide, speed must be cadence times
 * step length, so the three are one table here and the step is whatever it comes to.
 * <p>
 * The server's config decides ([eva_motion] model and gaitTier) and every Unit carries the answer to its
 * clients, so all of them draw the same model. The old model stays the default until the owner says otherwise.
 */
public final class EvaMotionModelR64
{
    public static final byte LEGACY=0,PLANTED=1;
    private static final EntityDataAccessor<Byte> MODEL=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BYTE);
    private static final EntityDataAccessor<Byte> TIER=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.BYTE);
    /**
     * R64 (M3): the server's [eva_gait] walkSpeedScale and runSpeedScale and its [eva_synchronization]
     * maxMobilityBonus, carried to every client. They are common config, which is not sent to clients: the side
     * that moves a Unit read its own file, so a pilot whose file differed from the server's drove at their own
     * speed, and at the server's whenever the server took the Unit over (an Angel near, a strike), with a jump
     * in speed at each change.
     */
    private static final EntityDataAccessor<Float> WALK_KEY=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> RUN_KEY=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    private static final EntityDataAccessor<Float> MOBILITY_KEY=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    /** R64: the server's [eva_motion] jumpHeight, for the side that flies a jump, which is the pilot's own (EvaLeapR64). */
    private static final EntityDataAccessor<Float> JUMP_KEY=SynchedEntityData.defineId(EvaUnit01Entity.class,EntityDataSerializers.FLOAT);
    /** Review only: -Dprojectseele.jumpHeightR64=<blocks> stands in for the config (0: the jump as up to R63). */
    private static final String REVIEW_JUMP=System.getProperty("projectseele.jumpHeightR64");
    /** Review only: -Dprojectseele.motionModelR64=planted and -Dprojectseele.gaitTierR64=A, B or C stand in for the config. */
    private static final String REVIEW_MODEL=System.getProperty("projectseele.motionModelR64"),REVIEW_TIER=System.getProperty("projectseele.gaitTierR64");

    /**
     * One row of the gait table: Unit-01's speed (blocks a second, at a synchronisation that adds nothing) and
     * steps a second, walking and running. The fast run is the same in every row.
     */
    public record Tier(String name,double walk,double run,double walkCadence,double runCadence){}
    /** A: steps of 0.8 leg at the cadence approved on 2026-11-13. B: the cadence up to R63. C: the speeds up to R63. */
    private static final Tier[] TIERS={new Tier("A",32,66,1.35,2.0),new Tier("B",43,88,1.78,2.68),new Tier("C",22.6,41.9,1.25,1.75)};
    /** The fast run (dash held): blocks a second and steps a second, as up to R63 (cadence as since R64's 0.7 key). */
    public static final double SPRINT=189,SPRINT_CADENCE=3.8;
    /** What the built-in speeds come to in the game (blocks a second), which the tiers are scaled from. */
    private static final double LEGACY_WALK=22.6,LEGACY_RUN=41.9;
    /**
     * Ticks from rest to full input and back, walking and running; up to R63 ten up, eight down. With the two
     * ticks a key takes to reach the body and the two the ground's friction adds, the body is at nine tenths of
     * its speed 0.35 and 0.6 seconds after the key (measured at 7 and 12 ticks: 0.5 and 0.7).
     */
    public static final double WALK_RAMP_TICKS=5,RUN_RAMP_TICKS=10;
    /** Degrees a tick the body may turn: standing, walking, running, at the fast run (up to R63: 2.5 standing, 6 moving). */
    /**
     * (2026-11-16, after the owner's first play: walking was 9 and running 6. At nine degrees a tick the body turns
     * half a circle in a second while a foot stands for most of one: the feet were left wherever the body had
     * been facing, the legs crossed, and no placing of the next step can keep up with it. A body this heavy does
     * not turn like that either. Now a walk turns 80 degrees a second, a run 60, a fast run 40.)
     */
    public static final float TURN_STANDING=4F,TURN_WALK=4F,TURN_RUN=3F,TURN_SPRINT=2F;

    /** Sideways and backward, as a share of the walking speed (up to R63: 0.7 and 0.6 of the walk or the run, whichever was held). */
    public static final double SIDE_SHARE=.45,BACK_SHARE=.6;

    /** A Unit the planted model walks is falling only with no ground within this far under its box (blocks: its step, and what a slope of one in one drops over half its box). */
    public static final double FALL_GROUND=24;

    /**
     * R64 (M2): the slope in the controller. A slope takes a share of the speed, from a rise over run of
     * SLOPE_FROM on, up to SLOPE_UP of it going up one in one and SLOPE_DOWN coming down it; and the body rises
     * no more than CLIMB_MOST blocks a second and drops no more than DESCENT_MOST, which is what holds a fast
     * run. On a slope of one in one: walk 32 to 16 up and 22 down, run 66 to 33 and 46, fast run 189 to 40 and
     * 60. (Up to M1 a slope took nothing off: a footfall of level ground's length up one in one is as far up as
     * along, which no leg reaches.)
     */
    public static final double CLIMB_MOST=40,DESCENT_MOST=60,SLOPE_FROM=.3,SLOPE_UP=.5,SLOPE_DOWN=.3;
    /** How far ahead of the body the ground's rise is read (blocks), and the rise over that run past which it is a ledge or a drop and no slope. */
    public static final double SLOPE_AHEAD=12,SLOPE_MOST=1.5;

    /** What a slope leaves of the speed (rise over run of the ground ahead, up positive): all of it on gentle ground. */
    public static float slopeScale(EvaUnit01Entity e,boolean running,float slope)
    {
        if(Math.abs(slope)<1e-3||!walks(e))return 1;
        Tier t=tier(e);
        double nominal=(running?t.run():t.walk())*EvaSprintR50.speed(e),steep=Mth.clamp((Math.abs(slope)-SLOPE_FROM)/(1-SLOPE_FROM),0,1);
        double share=1-(slope>0?SLOPE_UP:SLOPE_DOWN)*steep;
        return (float)Math.min(share,(slope>0?CLIMB_MOST:DESCENT_MOST)/Math.abs(slope)/nominal);
    }

    /**
     * R64 (M3): an edge is a drop of more than EDGE_DROP blocks under where the toes (EDGE_TOE ahead of the body's
     * middle) or the heels (EDGE_HEEL behind it) of the feet (EDGE_HALF to either side) stand. A Unit left
     * standing over one walks back from it at EDGE_INPUT of its walking input.
     */
    public static final double EDGE_DROP=10,EDGE_TOE=5.5,EDGE_HEEL=5.3,EDGE_HALF=4.8,EDGE_INPUT=.2;

    /** Register base accessors before any subclass allocates its own IDs. */
    public static boolean bootstrap(){return true;}
    public static void define(SynchedEntityData data)
    {
        data.define(MODEL,LEGACY);data.define(TIER,(byte)0);
        data.define(WALK_KEY,1F);data.define(RUN_KEY,1F);data.define(MOBILITY_KEY,.25F);data.define(JUMP_KEY,0F);
    }

    /** Server, every tick: its own speed keys (as the Unit reads them) and mobility bonus, for the clients. */
    public static void serverKeys(EvaUnit01Entity e,float walk,float run)
    {
        if(e.level().isClientSide)return;
        float mobility=SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_SYNC_MAX_MOBILITY_BONUS.get().floatValue():.25F;
        if(e.getEntityData().get(WALK_KEY)!=walk)e.getEntityData().set(WALK_KEY,walk);
        if(e.getEntityData().get(RUN_KEY)!=run)e.getEntityData().set(RUN_KEY,run);
        if(e.getEntityData().get(MOBILITY_KEY)!=mobility)e.getEntityData().set(MOBILITY_KEY,mobility);
    }

    /** The speed key a Unit is driven by: the server's for a Unit of the planted model, this side's own otherwise. */
    public static double speedKey(EvaUnit01Entity e,boolean running,double own)
    {
        return planted(e)?e.getEntityData().get(running?RUN_KEY:WALK_KEY):own;
    }

    /** What the pilot's synchronisation adds to the speed, by the server's bonus for a Unit of the planted model. */
    public static float mobility(EvaUnit01Entity e,float synchronization)
    {
        return planted(e)?com.projectseele.capability.EvaPilotCapability.mobilityMultiplier(synchronization,e.getEntityData().get(MOBILITY_KEY))
                :com.projectseele.capability.EvaPilotCapability.mobilityMultiplier(synchronization);
    }

    /** Server, every tick: the config decides. */
    public static void tick(EvaUnit01Entity e)
    {
        if(e.level().isClientSide)return;
        byte model=configuredModel(),tier=configuredTier();
        if(e.getEntityData().get(MODEL)!=model)e.getEntityData().set(MODEL,model);
        if(e.getEntityData().get(TIER)!=tier)e.getEntityData().set(TIER,tier);
        float jump=REVIEW_JUMP!=null?Float.parseFloat(REVIEW_JUMP):SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_JUMP_HEIGHT.get().floatValue():0F;
        if(e.getEntityData().get(JUMP_KEY)!=jump)e.getEntityData().set(JUMP_KEY,jump);
    }

    /**
     * R64: going to the ground and crawling, for a Unit of the planted model bare handed or with the knife.
     * <p>
     * The owner (2026-11-16): going down is very bad and slow. Three things that were so in every version: it took
     * 64 ticks to get down and as long to get up (now DOWN_GATHER and DOWN_RATE on the stance clock: 35); held
     * forward, the body went on 37 to 46 blocks through that with no step under it (now it does not move between
     * its crouch and the ground); and it crawled 5.4 blocks a second (now CRAWL_SPEED on the speed key that was
     * 0.10: 8.6). The crawl itself is tools/finale/crawl.py.
     */
    public static final float DOWN_GATHER=.015F,DOWN_RATE=.10F,CRAWL_SPEED=.16F;

    /** Goes to the ground as this model has it: bare handed or with the knife (with the rifle it lies behind the gun as before). */
    public static boolean ground(EvaUnit01Entity e)
    {
        return planted(e)&&(e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE);
    }

    /** Between its crouch and the ground, where no clip steps: it does not move. (The crawl comes in from 2.5.) */
    public static boolean goingDown(EvaUnit01Entity e)
    {
        if(!ground(e))return false;
        float stance=e.rifleStanceLevel(0);
        return stance>1.05F&&stance<2.55F;
    }

    /** Blocks a Unit of the planted model jumps (the server's); 0 for a Unit that jumps as up to R63. */
    public static float jumpHeight(EvaUnit01Entity e){return planted(e)?e.getEntityData().get(JUMP_KEY):0F;}

    private static byte configuredModel()
    {
        String value=REVIEW_MODEL!=null?REVIEW_MODEL:SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_MOTION_MODEL.get():"legacy";
        return "planted".equalsIgnoreCase(value)?PLANTED:LEGACY;
    }

    private static byte configuredTier()
    {
        String value=REVIEW_TIER!=null?REVIEW_TIER:SeeleConfig.COMMON_SPEC.isLoaded()?SeeleConfig.EVA_GAIT_TIER.get():"A";
        for(byte i=0;i<TIERS.length;i++)if(TIERS[i].name().equalsIgnoreCase(value))return i;
        return 0;
    }

    /** The new model is this Unit's: asked for, and a Unit it is built for (Unit-01 until the others' rigs are measured). */
    public static boolean planted(EvaUnit01Entity e)
    {
        return e.getEntityData().get(MODEL)==PLANTED&&!e.isExperimentalUnit()&&e.getUnitVariant()==EvaUnit01Entity.UNIT_01
                &&!(e instanceof EvaPrototypeEntity);
    }

    public static Tier tier(EvaUnit01Entity e)
    {
        return TIERS[Mth.clamp(e.getEntityData().get(TIER),0,TIERS.length-1)];
    }

    /**
     * Whether the new model walks this Unit now, as far as both sides know: piloted freely on its feet, bare
     * handed or with the knife, nothing else owning the body. The client asks more of what it draws.
     */
    public static boolean walks(EvaUnit01Entity e)
    {
        return planted(e)&&e.isPoweredOn()&&!e.isFirstBattleActive()&&!e.isBerserk()&&!e.isCrucified()&&!e.isNervLogisticsLocked()
                &&!e.isLaunchSequenceActive()&&e.getActivationTicks()<=0&&e.getVisualPose()==0
                &&(e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE)
                &&!e.isPilotProne()&&!e.isPilotCrouching()&&!e.hasLiveActionForRender(0)
                &&!com.projectseele.physics.CombatBodyDynamics.active(e);
    }

    /** What the built-in walking or running speed is multiplied by. */
    public static float speedScale(EvaUnit01Entity e,boolean running)
    {
        if(!planted(e))return 1;
        Tier t=tier(e);
        return (float)(running?t.run()/LEGACY_RUN:t.walk()/LEGACY_WALK);
    }

    /** The walking speed over the speed of the gait that is held: 1 at a walk. */
    public static double walkShare(EvaUnit01Entity e,boolean running)
    {
        Tier t=tier(e);
        return running?t.walk()/t.run():1;
    }

    /** The fast run as a multiple of the run: the fast run itself keeps its speed whatever the run's is. */
    public static float sprintGain(EvaUnit01Entity e,float legacy)
    {
        return planted(e)?(float)(SPRINT/tier(e).run()):legacy;
    }

    /**
     * How a body going at a speed steps. All of it follows the speed alone, so a body gathering way or running
     * out of it passes through every gait between.
     *
     * @param cadence steps a second
     * @param duty    the share of a cycle (two steps) a foot is on the ground: over a half there is a time on both
     *                feet, under it a time in the air
     * @param land    the share of what the body covers over a standing foot that the foot is set down ahead of the hip
     * @param lift    how high the swinging foot is carried (blocks)
     * @param sink    how far under its straight-legged height the pelvis is carried (blocks)
     * @param bounce  the rise and fall of a run about that height (blocks)
     * @param width   how far apart the feet are set, as a share of their standing width
     */
    public record Gait(double cadence,double duty,double land,double lift,double sink,double bounce,double width){}

    /**
     * The run (2026-11-17). The owner, after his second play: the run looks crouched at the waist and furtive.
     * Measured against the run up to R63: the hips were carried at 94% of their standing height where R63 had
     * them at 104%, a foot was on the ground for all but 11% of the time where R63 was in the air for 59%, and the
     * swinging foot was carried 5 blocks high where R63's went 26. A foot stood for 0.40 of the cycle while the
     * body went 26 blocks over it, on a leg 30 long: the pelvis had to be let down to reach both ends of that, the
     * knees bent to carry it there, and nothing was left for the body to rise on.
     * <p>
     * Now a foot stands for RUN_DUTY of the cycle (the body goes 15 blocks over it and is in the air for half
     * the time), is set down RUN_LAND of that ahead of the hip, and its heel is carried RUN_LIFT high; the pelvis
     * is carried RUN_SINK under its straight-legged height (over it: the body is off the ground between footfalls)
     * and rises and falls RUN_BOUNCE about that. Where the foot goes while it is off the ground is the capture's
     * own run again: EvaPlantedGaitR64.RUN_TRAIL.
     */
    public static final double RUN_DUTY=.23,RUN_LAND=.32,RUN_LIFT=16,RUN_SINK=-.6,RUN_BOUNCE=2.3;

    /** @param speed blocks a second over the ground, with the pilot's synchronisation bonus taken out */
    public static Gait gait(Tier t,double speed)
    {
        double v=Math.max(0,speed);
        if(v<=t.walk())
        {
            double u=v/t.walk();
            // (R64 M2: the slowest steps at three quarters of the walk's cadence, not 0.55 of it: a body
            // running out of a fast run hung a foot in the air for most of a second.)
            return new Gait(t.walkCadence()*(.75+.25*u),.66-.04*u,.5-.05*u,1.6+1.8*u,.35+.65*u,0,1-.2*u);
        }
        if(v<=t.run())
        {
            double r=(v-t.walk())/(t.run()-t.walk()),s=r*r*(3-2*r);
            return new Gait(Mth.lerp(r,t.walkCadence(),t.runCadence()),Mth.lerp(s,.62,RUN_DUTY),Mth.lerp(s,.45,RUN_LAND),
                    Mth.lerp(s,3.4,RUN_LIFT),Mth.lerp(s,1.0,RUN_SINK),Mth.lerp(s,0,RUN_BOUNCE),Mth.lerp(s,.8,.55));
        }
        double d=Math.min(1,(v-t.run())/(SPRINT-t.run()));
        return new Gait(Mth.lerp(d,t.runCadence(),SPRINT_CADENCE),Mth.lerp(d,RUN_DUTY,.30),Mth.lerp(d,RUN_LAND,.32),
                Mth.lerp(d,RUN_LIFT,10),Mth.lerp(d,RUN_SINK,3.6),Mth.lerp(d,RUN_BOUNCE,1.8),Mth.lerp(d,.55,.4));
    }

    private EvaMotionModelR64(){}
}

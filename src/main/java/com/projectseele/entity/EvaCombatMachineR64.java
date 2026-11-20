package com.projectseele.entity;

import com.projectseele.ProjectSeele;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.entity.EvaMoveTableR64.Row;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

import java.util.HashMap;
import java.util.Map;

/**
 * R64 (M4): the one machine that plays a Unit's blows from {@link EvaMoveTableR64}.
 * <p>
 * The pilot's presses go into a buffer of {@link #BUFFER} ticks. Each tick the machine asks one question: may the
 * press in the buffer begin a row now? From standing, yes. From a row in hand, from the tick that row allows: sooner
 * when it has landed than when it has not. Nothing else begins a blow, so what follows what, and when, is read off
 * the table and nowhere else.
 * <p>
 * The body is still moved by the old core's clips and flags; the machine begins them, sets their length, and takes
 * their clock: a row's wind-up, live and recovery ticks are laid over its clip so that the clip's contact falls in
 * the live ticks, and the limb's swept capsule is tested on each live tick until it lands. A blow that has not
 * landed when the live ticks end is told once as a miss.
 * <p>
 * Server only. The old core keeps every case the table has no row for: crouched fists, the aerial
 * blows, the grapple, the sword, and every Unit but Unit-01.
 */
public final class EvaCombatMachineR64
{
    public static final int LIGHT=0,HEAVY=1;
    /** Ticks a press is kept; ticks after a row ends in which the next press still follows it; ticks after an evade a light press is the counter. */
    public static final int BUFFER=8,LINK=8,AFTER_EVADE=12;
    /** Soft lock: how far and how far off the body's facing an Angel may be to be turned onto. */
    public static final double LOCK_RANGE=64,LOCK_HEIGHT=40;
    public static final float LOCK_CONE=75;
    /** Review only: -Dprojectseele.combatDiagR64=true tells every blow of either core in the log (R64BLOW, R64MOVE). */
    private static final boolean DIAG=Boolean.getBoolean("projectseele.combatDiagR64");

    private final EvaUnit01Entity e;
    private Row row,last;
    private int startup,active,recovery,serial;
    /** Ticks the row in hand begins its live part later than its table has it (the kick's step in): what the table counts from the row's beginning past its start-up comes that much later. */
    private int late;
    private float open,close,rate=1;
    private boolean hit,whiffed;
    /** R64 (flow): this row's stages lie on its clip along the smooth curve (the switch as it stood when the row began). */
    private boolean curve;
    private int button=-1,held,sinceEnd=1000,sinceEvade=1000;
    private boolean evading;
    private LivingEntity target;
    private final Map<String,Long> readyAt=new HashMap<>();

    EvaCombatMachineR64(EvaUnit01Entity e){this.e=e;}

    /** The row in hand, or null. */
    public Row row(){return row;}
    public boolean busy(){return row!=null;}
    /** Goes up by one with every blow begun: what Sachiel watches for a new blow in a string. */
    public int serial(){return serial;}

    /** The machine takes this Unit's presses now: on the frames core, standing, with bare hands or the knife. */
    public boolean owns()
    {
        return EvaCombatModelR64.frames(e)&&EvaGameplayMotionR32.phrases(e)
                &&(e.getWeapon()==EvaUnit01Entity.WEAPON_FISTS||e.getWeapon()==EvaUnit01Entity.WEAPON_KNIFE)
                &&!e.isPilotProne()&&!e.isPilotCrouching()&&!EvaCombatR31.active(e)
                &&(e.onGround()||!e.isVisuallyAirborneForRender())&&!e.isBerserk()&&!e.isFirstBattleActive();
    }

    /** A press from the pilot. True: the machine has it and the old core must not also act on it. */
    public boolean press(LivingEntity pilot,int pressed)
    {
        if(!owns()||e.level().isClientSide)return false;
        if(pilot==null||pilot!=e.getPilotEntity())return true;
        button=pressed;held=0;
        return true;
    }

    void clearStanceBuffer(){button=-1;last=null;sinceEnd=1000;}

    private int n(int ticks){return ticks<=0?ticks:Math.max(1,Math.round(ticks/rate));}
    private boolean ready(Row next){return e.level().getGameTime()>=readyAt.getOrDefault(next.name(),0L);}
    private Row follow(Row from,int pressed){return EvaMoveTableR64.get(pressed==HEAVY?from.heavy():from.light());}

    /** Server, each tick the Unit is not held on a hit, before the old core's clocks run: what begins, what ends. */
    void before(LivingEntity pilot)
    {
        boolean was=evading;evading=EvaFieldActionsR45.active(e);
        if(was&&!evading)sinceEvade=0;else if(sinceEvade<1000)sinceEvade++;
        // Played out, or taken from the Unit: a stagger, a change of stance, a jump, an evade.
        if(row!=null&&!e.rowLiveR64(row))end(e.rowElapsedR64(row)>=startup+active+recovery?"played out":"taken");
        if(row==null&&sinceEnd<1000)sinceEnd++;
        if(button>=0&&++held>BUFFER)
        {
            if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} press {} dropped: nothing took it in {} ticks",e.level().getGameTime(),button==HEAVY?"heavy":"light",BUFFER);
            button=-1;
        }
        if(!EvaCombatModelR64.frames(e)){button=-1;if(row!=null){row=null;last=null;EvaRowClockR64.end(e);}return;}
        if(pilot==null||e.isPilotControlLocked()||CombatFeelR31.restrained(e))return;
        if(row==null)
        {
            if(button<0||!owns()||e.hasLiveActionForRender(0)||e.leapLockedR64())return;
            Row next=sinceEnd<=LINK&&last!=null?follow(last,button):null;
            if(next==null)next=EvaMoveTableR64.opener(e.getWeapon(),button==HEAVY,sinceEvade<=AFTER_EVADE,EvaGameplayMotionR32.knifeCutsReadyR64(e),
                    EvaGameplayMotionR32.bodyReadyR64(e),e.isPilotSprinting()&&e.pilotLocomotionRequestedR45());
            if(next!=null&&ready(next))start(next,"standing");
            return;
        }
        int k=e.rowElapsedR64(row)+1;
        if(button>=0)
        {
            int from=n(hit?row.cancelHit():row.cancelWhiff());Row next=follow(row,button);
            if(next!=null&&from>0&&k>=from+late&&ready(next)&&owns())start(next,row.name()+(hit?" landed":" missed")+" at tick "+k);
        }
        else if(pilot instanceof ServerPlayer player&&(player.zza<-.15F&&k<=n(row.feint())
                ||(player.zza<-.15F||Math.abs(player.xxa)>.15F)&&k>=n(row.moveFrom())+late))
        {
            // A step back in the first ticks withdraws the blow; a step back or aside in its recovery ends it.
            if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} left at tick {} for a step",e.level().getGameTime(),row.name(),k);
            e.leaveRowR64();end("left");
        }
    }

    /**
     * R64 (flow, "step"). KICK_BEST: the kick lands best with its mark's side this far from the Unit's middle
     * (blocks; a mark's side is half its width from its own middle). Measured on a still Sachiel, nine blocks to
     * its side (tourKickR64, 2026-11-18): kicked from where the Unit stands it is hit with its middle 30 off and
     * missed at 38; after a step it is hit at 36, the sole meeting it as the leg comes straight. Three blocks
     * nearer than that, the sole meets it a little before. KICK_STEP: the stride of the step in, as
     * tools/finale/kick.py writes it. KICK_STEP_LEAST: the least share of the stride that is worth a step (two
     * blocks); a mark nearer than that is kicked from where the Unit stands. KICK_STEP_TICKS: the ticks a step in
     * adds to the kick's start-up (the leg has a stride further to come).
     */
    private static final double KICK_BEST=24,KICK_STEP=10;
    private static final float KICK_STEP_LEAST=.2F;
    private static final int KICK_STEP_TICKS=3;
    /**
     * The hard kick (flow, "step" without "kick"; tools/finale/hardkick.py). HARD_BEST: with no stride its sole
     * meets a mark whose side is this far from where the Unit's middle was as the kick began in the row's second
     * live tick, on its way up and at its fastest (measured against a still Sachiel: a side 21 blocks off is met
     * at phase .33 of the clip, 31 at .39, 40 at .42, where the leg is all but at its highest and slowing; the
     * hold then stood it there for three ticks). A nearer mark is met earlier in the swing, lower, and the body
     * is stopped by it where it stands.
     * HARD_STRIDE: what the whole step in adds, as the clip's stride_m has it. HARD_LEAST: the share is never
     * nothing: the kick changes feet and carries the body even on the spot, and the clients, who are told a
     * stride, carry the body through it by the row's clock (EvaUnit01Entity.stepRootR64). Its start-up is longer
     * by up to KICK_STEP_TICKS, by the share.
     */
    private static final double HARD_BEST=32,HARD_STRIDE=15.2;
    private static final float HARD_LEAST=.001F;
    /**
     * R64 (flow, "body"): the strides of the Unit's own bare-handed blows, as tools/finale/unarmed.py writes them.
     * best: how far the mark's side is from the Unit's middle where the blow lands as it is written, once the
     * stride is made; length: the stride; least: the least share of it worth making.
     */
    private record Stride(double best,double length,float least){}
    // (Thrown forward as it is in the pounce, the trunk is itself 22 blocks ahead of the hips, and two bodies are
    // kept that far apart (CombatSpacingR32): a pounce asked to end nearer was stopped 32 blocks from a Sachiel's
    // middle whatever it was asked. So it ends with its hand out, and the knee that follows springs the rest.)
    private static final java.util.Map<String,Stride> STRIDES=java.util.Map.of("pounce",new Stride(22,8,.2F),"knee",new Stride(7,17,.2F),"charge",new Stride(15,16,.2F));
    private void start(Row next,String from)
    {
        rate=Math.min(1.12F,EvaPilotCapability.attackSpeedMultiplier(e.getPilotSynchronization()));
        // R64 (flow, "step"): the kick's step in is as long as brings its mark to the leg's length, a stride at the
        // most, and none against a body already near enough. Against nothing it is the whole stride. Which of the
        // kick's two clips is played goes by it, so it is settled before the row's ticks are.
        float step=0;int longer=0;
        var stride=STRIDES.get(next.name());
        boolean strides=EvaCombatModelR64.flowStep(e)&&(next.kind()==EvaMoveTableR64.KICK||stride!=null&&EvaCombatModelR64.flowBody(e));
        // A punch made while the pilot walks is laid over the walk (EvaGameplayMotionR32.movementMayComposeR45): the
        // ground it covers is the walk's, and it takes no stride of its own.
        boolean walking=next.kind()==EvaMoveTableR64.PUNCH&&stride!=null&&!next.name().equals("charge")&&e.pilotLocomotionRequestedR45();
        if(strides&&!walking)
        {
            var mark=lock();
            if(next.kind()==EvaMoveTableR64.KICK&&EvaCombatModelR64.flowHardKick(e)&&EvaGameplayMotionR32.kickReady(e))
            {
                step=mark==null?0:(float)Mth.clamp((Math.hypot(mark.getX()-e.getX(),mark.getZ()-e.getZ())-.5*mark.getBbWidth()-HARD_BEST)/HARD_STRIDE,0,1);
                longer=Math.round(KICK_STEP_TICKS*step);step=Math.max(step,HARD_LEAST);
            }
            else
            {
                double best=stride==null?KICK_BEST:stride.best(),length=stride==null?KICK_STEP:stride.length();
                step=mark==null?1F:(float)Mth.clamp((Math.hypot(mark.getX()-e.getX(),mark.getZ()-e.getZ())-.5*mark.getBbWidth()-best)/length,0,1);
                if(step<(stride==null?KICK_STEP_LEAST:stride.least()))step=0;
                longer=step>0&&next.kind()==EvaMoveTableR64.KICK?KICK_STEP_TICKS:0;
            }
        }
        if(next.kind()==EvaMoveTableR64.KICK)e.rowStepShareR64=step;
        startup=n(next.startup()+longer);active=Math.max(2,n(next.active()));recovery=n(next.recovery());
        late=startup-n(next.startup());
        float contact=e.rowContactPhaseR64(next);
        open=Mth.clamp(contact-next.lead(),.02F,.9F);close=Mth.clamp(contact+next.tail(),open+.02F,.97F);
        // R64 (flow): the recovery is as long as its part of the clip takes at RECOVERY_PACE (the punches' was played
        // at 1.5 times its own pace: the arm was snatched back). The ticks a row may be left from stay where they are.
        curve=EvaCombatModelR64.flowCurve(e);
        float seconds=curve?e.rowClipSecondsR64(next):0;
        if(seconds>0)recovery=Math.max(recovery,(int)Math.ceil((1-close)*seconds*20/(EvaMoveTableR64.RECOVERY_PACE*rate)));
        row=next;last=null;hit=false;whiffed=false;serial++;target=lock();
        e.beginRowR64(next,startup+active+recovery);
        // R64 (flow): the row's clock, for the clients that play it themselves (nothing is told where they do not).
        if(EvaCombatModelR64.flowClock(e))EvaRowClockR64.begin(e,serial,next.name(),EvaUnit01Entity.rowClipR64(next),startup,active,recovery,open,close,curve,
                next.kind()==EvaMoveTableR64.KICK?EvaCombatModelR64.flowKickClip(e)&&EvaGameplayMotionR32.kickReady(e)
                        :stride!=null);
        else EvaRowClockR64.end(e);
        if(strides)EvaRowClockR64.step(e,step);
        // The Unit's turn for this tick has been made (the ridden body turns before the blows are looked at):
        // without this the first of a row's wind-up ticks was lost to the turn onto its target.
        if(target!=null&&pilotView!=NO_VIEW)e.faceR64(yaw(e.getYRot(),e.getYRot(),pilotView,true));
        if(next.cooldown()>0)readyAt.put(next.name(),e.level().getGameTime()+n(next.cooldown()));
        if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} begun from {}: press held {} ticks, {}+{}+{} ticks, clip {}..{}{}, target {}",
                e.level().getGameTime(),next.name(),from,held,startup,active,recovery,String.format(java.util.Locale.ROOT,"%.3f",open),
                String.format(java.util.Locale.ROOT,"%.3f",close),curve?" along the curve":"",target==null?"none":target.getType().toShortString());
        button=-1;
    }

    private void end(String how)
    {
        if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} over ({}) after {} ticks",e.level().getGameTime(),row.name(),how,e.rowElapsedR64(row));
        // A row that played out, or was left, may be followed for a few ticks; one taken from the Unit may not.
        last="taken".equals(how)?null:row;row=null;sinceEnd=0;target=null;
        EvaRowClockR64.end(e);
    }

    /** Where in its clip the row is after this many ticks: the wind-up to the opening of the live part, the live ticks across it, the recovery to the end. */
    float phase(int elapsed,float linear)
    {
        return row==null?linear:curve?EvaRowClockR64.phase(elapsed,startup,active,recovery,open,close,true)
                :EvaMoveTableR64.phase(elapsed,startup,active,recovery,open,close);
    }

    /** Server, the same tick, after the old core has moved the body to this tick's place in the clip: does it land? */
    void contact(LivingEntity pilot)
    {
        if(row==null||pilot==null||e.isPilotControlLocked()||!e.rowLiveR64(row))return;
        int now=e.rowElapsedR64(row);
        if(now==startup)e.rowSwingR64(row);
        if(now>startup&&now<=startup+active&&!hit&&e.rowContactR64(row,pilot,now==startup+1))
        {
            hit=true;
            // R64 (flow): the clients are told where the limb met its mark and how long both bodies are held (the
            // hold is the Unit's own beat of this tick, if the blow gave it one).
            var beat=CombatFeelR31.beat(e);
            EvaRowClockR64.hit(e,now,e.combatPhaseR31(),beat!=null&&beat.kind()==CombatFeelR31.CONTACT&&beat.start()==e.level().getGameTime()?Math.max(0,beat.stopTicks()-1):0);
            if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} landed at tick {} (live {}..{})",e.level().getGameTime(),row.name(),now,startup+1,startup+active);
        }
        else if(!hit&&now>=startup&&now<startup+active&&EvaCombatModelR64.flowClock(e))expect(pilot,now);
        // R64 (M5): a finisher's weight comes down, landed or not.
        if(now==startup+active&&row.level()==EvaMoveTableR64.FINISHER)e.rowGroundR64(hit);
        if(now==startup+active&&!hit&&!whiffed)
        {
            whiffed=true;e.rowWhiffR64(row);
            if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} missed (live {}..{})",e.level().getGameTime(),row.name(),startup+1,startup+active);
        }
    }

    /**
     * R64 (flow): will the limb meet a body in the tick to come? Its sweep from where it is to where the next tick
     * puts it is tried against the bodies as they stand, and nothing is struck. If it meets one, the clients are
     * told at what phase: they slow the limb into its mark in time, where without this they drew it a tick's
     * travel into the body before they heard of the hit. The hit itself is still made by the next tick's test.
     */
    private void expect(LivingEntity pilot,int now)
    {
        float here=e.combatPhaseR31(),next=phase(now+1,0);
        Vec3 from=e.blowLimbR64();
        if(from==null||next<=here)return;
        e.rowPhaseR64(next);Vec3 to=e.blowLimbR64();e.rowPhaseR64(here);
        if(to==null)return;
        Vec3 met=e.rowProbeR64(row,pilot,from,to);
        if(met==null)return;
        Vec3 along=to.subtract(from);double length=along.lengthSqr();
        double part=length<1.0e-6?0:Mth.clamp(met.subtract(from).dot(along)/length,0,1);
        EvaRowClockR64.due(e,now+1,(float)(here+(next-here)*part));
        if(DIAG)ProjectSeele.LOGGER.info("R64MOVE tick {} {} expected to land in tick {} at phase {}",e.level().getGameTime(),row.name(),now+1,
                String.format(java.util.Locale.ROOT,"%.3f",here+(next-here)*part));
    }

    private boolean sweeping;
    /** The contact being tested is the limb's end swept over this tick (not the length of the kicking leg). */
    void sweeps(boolean on){sweeping=on;}
    /**
     * The sweep of this tick first met a body here. The blow is held at that moment of its clip, not at the tick's
     * end: a limb moves ten blocks and more in a tick, and held at the tick's end it stood that deep in the body
     * for as long as the hit-stop lasted.
     */
    void meets(Vec3 from,Vec3 to,Vec3 at)
    {
        if(row==null||from==null||!sweeping||hit)return;
        double whole=to.distanceTo(from);
        if(whole<1.0e-3)return;
        int now=e.rowElapsedR64(row);
        // The limb does not cross the tick at an even pace (it is still being blended in from the pose before the
        // blow): the moment it reached the contact is searched for between the two ticks.
        // (From three ticks back: a blow's first ticks are drawn ahead of their phase by that blend, and the phase
        // of the tick before still stood the limb past the contact.)
        // R64 (M5): and it is the moment the limb is nearest the contact that is looked for, not the one it crosses
        // a plane at: a mark that stands inside the Unit's guard is met by the limb where the tick began, and a
        // search that only ran on from there took the opening jab seven blocks back into its wind-up.
        // R64 (flow, "kick"): the kick's own clip is not blended in through its live ticks, and its foot passes
        // near a body that stands close on its way up: only this tick's sweep is searched.
        int back=row.kind()==EvaMoveTableR64.KICK&&EvaCombatModelR64.flowKickClip(e)?1:3;
        float lo=phase(Math.max(0,now-back),0),hi=phase(now,0),best=hi;double least=Double.MAX_VALUE;
        for(int i=0;i<=8;i++)
        {
            float tried=lo+(hi-lo)*i/8F;e.rowPhaseR64(tried);Vec3 limb=e.blowLimbR64();
            if(limb==null){e.rowPhaseR64(hi);return;}
            double d=limb.distanceToSqr(at);
            if(d<least){least=d;best=tried;}
        }
        float span=(hi-lo)/8F;
        for(int i=0;i<4;i++)
        {
            span*=.5F;
            for(float tried:new float[]{best-span,best+span})
            {
                if(tried<lo||tried>hi)continue;
                e.rowPhaseR64(tried);Vec3 limb=e.blowLimbR64();
                if(limb==null)continue;
                double d=limb.distanceToSqr(at);
                if(d<least){least=d;best=tried;}
            }
        }
        e.rowPhaseR64(best);
    }

    /** The blow in hand has landed. */
    public boolean landed(){return row!=null&&hit;}
    /** Ticks of the row in hand still to play. */
    public int recoveryLeft(){return row==null?0:Math.max(0,startup+active+recovery-e.rowElapsedR64(row));}
    /** The blow in hand has landed or missed and only its recovery is left. */
    public boolean spent(){return row!=null&&(hit||e.rowElapsedR64(row)>=startup+active);}
    /** An evade or a jump may take the row's place now. With nothing in hand, always. */
    public boolean evadeOpen()
    {
        if(row==null)return true;
        int k=e.rowElapsedR64(row)+1;
        return k>=n(hit?row.evadeHit():row.evadeWhiff())+late||k<=n(row.feint());
    }
    /** In these ticks a blow that would stagger the Unit only makes it flinch. */
    public boolean armored()
    {
        if(row==null||row.armorFrom()<0)return false;
        int k=e.rowElapsedR64(row);
        return k>=n(row.armorFrom())+late&&k<=n(row.armorTo())+late;
    }

    private LivingEntity lock()
    {
        Vec3 forward=Vec3.directionFromRotation(0,e.getYRot());LivingEntity best=null;double bestScore=Double.MAX_VALUE;
        for(LivingEntity other:e.level().getEntitiesOfClass(LivingEntity.class,e.getBoundingBox().inflate(LOCK_RANGE,LOCK_HEIGHT,LOCK_RANGE),
                o->o instanceof Angel&&o.isAlive()))
        {
            Vec3 to=other.position().subtract(e.position()).multiply(1,0,1);double range=to.length();
            if(range>LOCK_RANGE||range<1.0e-3)continue;
            double off=Math.toDegrees(Math.acos(Mth.clamp(to.normalize().dot(forward),-1,1)));
            if(off>LOCK_CONE)continue;
            double score=range+off*.4;
            if(score<bestScore){bestScore=score;best=other;}
        }
        return best;
    }
    /** Degrees from the body's facing to the nearest Angel in range, or NaN: what the review reads as the aim. */
    private double aim()
    {
        LivingEntity near=null;double d=Double.MAX_VALUE;
        for(LivingEntity other:e.level().getEntitiesOfClass(LivingEntity.class,e.getBoundingBox().inflate(96,LOCK_HEIGHT,96),o->o instanceof Angel&&o.isAlive()))
        {double r=other.distanceToSqr(e);if(r<d){d=r;near=other;}}
        if(near==null)return Double.NaN;
        Vec3 to=near.position().subtract(e.position()).multiply(1,0,1);
        return to.lengthSqr()<1.0e-6?0:Math.toDegrees(Math.acos(Mth.clamp(to.normalize().dot(Vec3.directionFromRotation(0,e.getYRot())),-1,1)));
    }

    /**
     * Soft lock. While a row winds up the body turns onto its target at the row's rate; while it can land the body
     * is committed; through the recovery it keeps facing the target unless the pilot has looked well away from it.
     */
    float yaw(float previous,float wanted,float view)
    {pilotView=view;return yaw(previous,wanted,view,false);}
    private static final float NO_VIEW=Float.MAX_VALUE;
    private float pilotView=NO_VIEW;
    private float yaw(float previous,float wanted,float view,boolean beginning)
    {
        if(row==null||target==null||!target.isAlive()||e.level().isClientSide)return wanted;
        double dx=target.getX()-e.getX(),dz=target.getZ()-e.getZ();
        if(dx*dx+dz*dz<1.0e-4)return wanted;
        float bearing=(float)(Mth.atan2(dz,dx)*Mth.RAD_TO_DEG)-90;
        if(Math.abs(Mth.wrapDegrees(view-bearing))>LOCK_CONE+15){target=null;return wanted;}
        int now=e.rowElapsedR64(row);
        if(now<startup&&(now>0||beginning))return Mth.approachDegrees(previous,bearing,row.track()*rate);
        return previous;
    }

    // ---- what the review reads, for either core -------------------------------------------------------------

    private String toldName="";private int toldStamp;private long toldStart;private boolean toldHit;private int toldHeld;

    /** Server, every tick, held or not: the blows as the flags show them, the same for both cores. */
    void told(boolean heldThisTick)
    {
        if(!DIAG||!e.isVehicle())return;
        long now=e.level().getGameTime();
        if(heldThisTick){toldHeld++;return;}
        if(toldHeld>0){ProjectSeele.LOGGER.info("R64BLOW tick {} unit {} held {} ticks",now,e.getId(),toldHeld);toldHeldIn+=toldHeld;toldHeld=0;}
        String name=e.blowNameR64();int stamp=e.blowStampR64();
        if(!name.isEmpty()&&!name.equals("evade"))
        {
            // Where the striking limb's end is on every tick of a blow: its reach past the body, and how far it is from the nearest Angel.
            Vec3 limb=e.blowLimbR64();LivingEntity near=nearest();
            if(limb!=null)ProjectSeele.LOGGER.info("R64LIMB tick {} {} phase {} reach {} up {} angel {} unit to angel {}",now,name,
                    String.format(java.util.Locale.ROOT,"%.3f",e.combatPhaseR31()),
                    String.format(java.util.Locale.ROOT,"%.1f",limb.subtract(e.position()).multiply(1,0,1).length()),
                    String.format(java.util.Locale.ROOT,"%.1f",limb.y-e.getY()),
                    near==null?"-":String.format(java.util.Locale.ROOT,"%.1f",limb.subtract(near.position()).multiply(1,0,1).length()),
                    near==null?"-":String.format(java.util.Locale.ROOT,"%.1f",near.position().subtract(e.position()).multiply(1,0,1).length()));
        }
        if(name.equals(toldName)&&(stamp==toldStamp||name.isEmpty()))return;
        if(!toldName.isEmpty())ProjectSeele.LOGGER.info("R64BLOW tick {} unit {} end {} after {} ticks{}",now,e.getId(),toldName,now-toldStart-toldHeldIn,toldHit?"":" without landing");
        if(!name.isEmpty())ProjectSeele.LOGGER.info("R64BLOW tick {} unit {} start {} aim {}",now,e.getId(),name,String.format(java.util.Locale.ROOT,"%.1f",aim()));
        toldName=name;toldStamp=stamp;toldStart=now;toldHit=toldHitAt==now;toldHeldIn=0;
    }
    private int toldHeldIn;private long toldHitAt=-1;
    private LivingEntity nearest()
    {
        LivingEntity near=null;double d=Double.MAX_VALUE;
        for(LivingEntity other:e.level().getEntitiesOfClass(LivingEntity.class,e.getBoundingBox().inflate(96,LOCK_HEIGHT,96),o->o instanceof Angel&&o.isAlive()))
        {double r=other.distanceToSqr(e);if(r<d){d=r;near=other;}}
        return near;
    }
    void toldPress(boolean heavy)
    {if(DIAG&&!e.level().isClientSide)ProjectSeele.LOGGER.info("R64BLOW tick {} unit {} press {}",e.level().getGameTime(),e.getId(),heavy?"heavy":"light");}
    /** A blow of this Unit has been taken by a body: where the limb was, and where on the body it met it. */
    void toldLanded(Entity struck,Vec3 body,Vec3 limb,boolean blood)
    {
        if(!DIAG||e.level().isClientSide)return;
        toldHit=true;toldHitAt=e.level().getGameTime();
        // Where the limb is drawn while the blow is held: the phase the hold froze, which the old core leaves at the
        // tick's end and the frames core has set back to the first contact.
        Vec3 drawn=e.blowLimbR64();
        String name=toldName.isEmpty()||!e.blowNameR64().equals(toldName)?e.blowNameR64():toldName;
        ProjectSeele.LOGGER.info("R64BLOW tick {} unit {} hit {} after {} ticks on {} gap {} aim {} {} drawn {}",e.level().getGameTime(),e.getId(),
                name,name.equals(toldName)?e.level().getGameTime()-toldStart-toldHeldIn+1:1,struck.getType().toShortString(),
                String.format(java.util.Locale.ROOT,"%.2f",limb.distanceTo(body)),String.format(java.util.Locale.ROOT,"%.1f",aim()),blood?"body":"field",
                drawn==null?"-":String.format(java.util.Locale.ROOT,"%.2f",drawn.distanceTo(body)));
    }
}

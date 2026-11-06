package com.projectseele.client.render;

import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaSprintR50;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * The mass of the upper body riding on the legs.
 * <p>
 * The gait clips carry the rise and fall of a stride but no load. Here each
 * footfall drives the pelvis down on a damped spring, which the planted leg
 * takes up through {@link EvaGroundContactR56}, and nods the chest; starting,
 * stopping and turning tip the chest into the change of motion. Weapons on
 * target and strikes keep their authored trunk.
 */
final class EvaBodyWeightR59
{
    /** Pelvis spring (1/s) and damping; the peak drop after an impulse J is PEAK_PER_IMPULSE*J. */
    private static final float DROP_RATE=16F,DROP_DAMP=.75F,PEAK_PER_IMPULSE=.0274F;
    /** Peak pelvis drop at a footfall (blocks) walking, running and dashing. */
    private static final float WALK_DROP=.7F,RUN_DROP=.6F,DASH_DROP=1.2F;
    /** Chest nod per model pixel of pelvis drop (degrees), and how much the neck gives back to keep the head level. */
    private static final float NOD=.75F,NECK_BACK=.45F;
    /** Speed filters (seconds): their difference measures a change of speed. */
    private static final float SPEED_FAST=.06F,SPEED_SLOW=.45F;
    /** Lean per block/second of speed change (degrees), its limit, and the lean spring. */
    private static final float LEAN_GAIN=.22F,LEAN_MAX=8F,LEAN_RATE=6F,LEAN_DAMP=.7F;
    /** Bank per block/second^2 of turning acceleration (degrees), its limit, and the bank spring. */
    private static final float BANK_GAIN=.10F,BANK_MAX=7F,BANK_RATE=8F,BANK_DAMP=.8F;
    /** How fast the trunk effects fade in and out around weapons and strikes (1/s). */
    private static final float TRUNK_FADE=9F;
    /** How fast a foot takes and sheds the ground (1/s). */
    private static final float CONTACT_RATE=40F;

    private static final class State
    {
        long time,faded;
        float dt,drop,dropRate,fast,slow,lean,leanRate,bank,bankRate,trunk,contactL,contactR;
        boolean left,right;
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    /** Advances the body once per frame; returns the pelvis offset to draw (model pixels, down is negative). */
    static float pelvis(EvaUnit01Entity eva,float partial,long now,float walking)
    {
        State s=STATES.computeIfAbsent(eva,key->new State());
        if(now==s.time)return s.drop;
        float dt=(now-s.time)/1e9F;
        s.time=now;s.dt=dt;
        boolean left=EvaBodyPose.gaitFootDownR59(eva,"l",partial),right=EvaBodyPose.gaitFootDownR59(eva,"r",partial);
        if(dt<=0||dt>.2F)
        {
            s.drop=s.dropRate=s.lean=s.leanRate=s.bank=s.bankRate=0;s.left=left;s.right=right;
            s.fast=s.slow=forwardSpeed(eva);
            return 0;
        }
        if(walking>.3F)
        {
            float run=eva.rifleRunBlend(partial),dash=EvaSprintR50.blend(eva,partial);
            float peak=Mth.lerp(dash,Mth.lerp(run,WALK_DROP,RUN_DROP),DASH_DROP)*walking;
            float impulse=peak*16/EvaScale.RENDER_SCALE/PEAK_PER_IMPULSE;
            if(left&&!s.left)s.dropRate-=impulse;
            if(right&&!s.right)s.dropRate-=impulse;
        }
        s.left=left;s.right=right;
        float settle=1-(float)Math.exp(-dt*CONTACT_RATE);
        s.contactL+=((left?1:0)-s.contactL)*settle;s.contactR+=((right?1:0)-s.contactR)*settle;
        int steps=Math.max(1,Mth.ceil(dt/.004F));float h=dt/steps;
        for(int i=0;i<steps;i++)
        {
            s.dropRate+=(-2*DROP_DAMP*DROP_RATE*s.dropRate-DROP_RATE*DROP_RATE*s.drop)*h;
            s.drop+=s.dropRate*h;
            float[] lean=spring(s.lean,s.leanRate,leanTarget(s),LEAN_RATE,LEAN_DAMP,h);s.lean=lean[0];s.leanRate=lean[1];
            float[] bank=spring(s.bank,s.bankRate,bankTarget(s,eva),BANK_RATE,BANK_DAMP,h);s.bank=bank[0];s.bankRate=bank[1];
        }
        float forward=forwardSpeed(eva);
        s.fast+=(forward-s.fast)*(1-(float)Math.exp(-dt/SPEED_FAST));
        s.slow+=(forward-s.slow)*(1-(float)Math.exp(-dt/SPEED_SLOW));
        return s.drop;
    }

    /** Tips the chest and steadies the head, after the legs have taken the pelvis. */
    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        State s=STATES.get(eva);
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();
        // Off the ground the jump owns the trunk; the pelvis was not advanced this frame.
        if(s==null||s.time!=now)return;
        boolean armed=eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||eva.getWeapon()==EvaUnit01Entity.WEAPON_CANNON||eva.fixedCannonOperatingR52();
        boolean striking=eva.hasLiveActionForRender(partial)||eva.getOrdinaryAttackStage()>=0||eva.isHeavyMotionActive()
                ||eva.hasLegacyStrikeForRender()||eva.isKickMotionActive(partial);
        float wanted=armed||striking||eva.isPilotProne()?0:1;
        if(s.faded!=now)
        {
            s.trunk+=(wanted-s.trunk)*(1-(float)Math.exp(-Mth.clamp(s.dt,0,.2F)*TRUNK_FADE));
            s.faded=now;
        }
        if(s.trunk<.01F)return;
        float pitch=(s.lean-s.drop*NOD)*s.trunk,bank=s.bank*s.trunk;
        if(Math.abs(pitch)<.02F&&Math.abs(bank)<.02F)return;
        var chest=model.getBone("torso_upper").orElse(null);var neck=model.getBone("neck").orElse(null);
        if(chest==null)return;
        var q=new Quaternionf().rotationZYX(chest.getRotZ(),chest.getRotY(),chest.getRotX());
        EvaRigTransforms.rotate(chest,q.rotateX(-pitch*Mth.DEG_TO_RAD).rotateZ(-bank*Mth.DEG_TO_RAD));
        if(neck!=null)
        {
            var n=new Quaternionf().rotationZYX(neck.getRotZ(),neck.getRotY(),neck.getRotX());
            EvaRigTransforms.rotate(neck,n.rotateX(pitch*NECK_BACK*Mth.DEG_TO_RAD).rotateZ(bank*NECK_BACK*Mth.DEG_TO_RAD));
        }
    }

    /** How firmly a foot stands by the clip's support mask, eased so a leg takes and sheds the ground smoothly. */
    static float contact(EvaUnit01Entity eva,String side)
    {
        State s=STATES.get(eva);
        return s==null?0:side.equals("l")?s.contactL:s.contactR;
    }

    private static float forwardSpeed(EvaUnit01Entity eva)
    {
        float yaw=eva.yBodyRot*Mth.DEG_TO_RAD;
        return (float)((eva.getX()-eva.xOld)*20*-Mth.sin(yaw)+(eva.getZ()-eva.zOld)*20*Mth.cos(yaw));
    }

    /** Speeding up and stopping both tip the chest the way the body is going: into the stride, then over the planted feet. */
    private static float leanTarget(State s)
    {
        float change=Math.abs(s.fast-s.slow)*LEAN_GAIN;
        return Math.min(change,LEAN_MAX)*(s.fast+s.slow>=0?1:-1);
    }

    private static float bankTarget(State s,EvaUnit01Entity eva)
    {
        float turning=Mth.wrapDegrees(eva.yBodyRot-eva.yBodyRotO)*20*Mth.DEG_TO_RAD*s.fast;
        return Mth.clamp(turning*BANK_GAIN,-BANK_MAX,BANK_MAX);
    }

    private static float[] spring(float x,float v,float target,float rate,float damp,float h)
    {
        v+=(-2*damp*rate*v-rate*rate*(x-target))*h;
        return new float[]{x+v*h,v};
    }

    private EvaBodyWeightR59() {}
}

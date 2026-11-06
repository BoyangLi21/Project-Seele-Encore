package com.projectseele.entity;

import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import org.joml.Quaternionf;

/**
 * The legs go the way the body travels.
 * <p>
 * Every gait clip walks straight ahead, so moving sideways played a forward
 * walk while the body slid across the ground. Here the hips turn onto the
 * line of travel and the spine takes the turn back, chest halfway and head
 * nearly all of it, so the pilot still faces forward. Past
 * {@link #REVERSE_FROM} degrees the legs walk backward instead, which the gait
 * phase has to agree with: see {@link #backward}. A held firearm keeps the
 * chest on the sight line and the hips only go as far as the waist can twist.
 */
final class EvaStrideHeadingR59
{
    /** Travel this far (degrees) from straight ahead is walked backward, the hips turning the other way. */
    private static final float REVERSE_FROM=100;
    /** Share of the distance to the wanted heading covered each tick, gathering and letting go. */
    private static final float FOLLOW=.2F,RELEASE=.14F;
    /** Share of the hips' turn the chest follows; share of the chest's the neck gives back. */
    private static final float CHEST=.5F,NECK=.75F;
    /** Hip turn a firearm allows (degrees): the chest stays where it is, inside the waist's 45 degree twist. */
    private static final float ARMED_LIMIT=40;
    /** Slowest travel that counts (blocks per tick). */
    private static final double MOVING=.04D;

    private static final class State {double x,z;float heading,previous;boolean seen;}
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    /** Once per tick on either side, from the entity's own travel. */
    static void tick(EvaUnit01Entity e)
    {
        var s=STATES.computeIfAbsent(e,k->new State());
        double dx=e.getX()-s.x,dz=e.getZ()-s.z,distance=Math.hypot(dx,dz);
        boolean first=!s.seen;
        s.x=e.getX();s.z=e.getZ();s.seen=true;s.previous=s.heading;
        if(first)return;
        float wanted=0;
        if(distance>MOVING&&distance<8&&e.onGround()&&free(e))
        {
            float across=Mth.wrapDegrees((float)Math.toDegrees(Math.atan2(-dx,dz))-e.yBodyRot);
            wanted=Math.abs(across)>REVERSE_FROM?Mth.wrapDegrees(across-180):across;
        }
        s.heading+=(wanted-s.heading)*(wanted==0?RELEASE:FOLLOW);
    }

    /** Whether this travel is walked backward. */
    static boolean backward(EvaUnit01Entity e,double dx,double dz)
    {
        var forward=e.getForward();
        return (dx*forward.x+dz*forward.z)/Math.max(1e-6,Math.hypot(dx,dz))<Math.cos(Math.toRadians(REVERSE_FROM));
    }

    static void apply(EvaUnit01Entity e,EvaBodyPose.Sample body,float partial)
    {
        var s=STATES.get(e);
        if(s==null)return;
        float heading=Mth.lerp(partial,s.previous,s.heading)*(1-EvaPoseBlendR51.smooth((e.rifleStanceLevel(partial)-1)/.4F));
        if(Math.abs(heading)<.2F)return;
        boolean armed=e.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE||e.getWeapon()==EvaUnit01Entity.WEAPON_CANNON;
        if(armed)heading=Mth.clamp(heading,-ARMED_LIMIT,ARMED_LIMIT);
        EvaRifleKinematics.turnHips(body,heading);
        if(armed)return;
        turn(body,"torso_upper",heading*CHEST);
        turn(body,"neck",-heading*CHEST*NECK);
    }

    /** Turns a bone about the vertical (degrees, Minecraft sense), carrying everything above it. */
    private static void turn(EvaBodyPose.Sample body,String name,float degrees)
    {
        var bone=body.rig.get(name);
        if(bone==null||bone.parent()==null)return;
        var parent=body.matrix(bone.parent()).getNormalizedRotation(new Quaternionf());
        var yaw=new Quaternionf().rotationY(-degrees*Mth.DEG_TO_RAD);
        body.rotations.put(name,new Quaternionf(parent).invert().mul(yaw).mul(parent).mul(body.rotations.get(name)));
        body.dirty();
    }

    private static boolean free(EvaUnit01Entity e)
    {
        return !(e.isExperimentalUnit()||e.isPilotProne()||e.isFirstBattleActive()||e.isCrucified()||e.isNervLogisticsLocked()
                ||e.hasLiveActionForRender(0)||e.getOrdinaryAttackStage()>=0||e.isHeavyMotionActive()||e.isKickMotionActive(0)
                ||EvaCombatR31.action(e)!=EvaCombatR31.NONE||EvaCombatSupportR33.gaitWeight(e,1)>.5F
                ||EvaFieldActionsR45.active(e)||EvaSwordActionsR45.active(e));
    }

    private EvaStrideHeadingR59(){}
}

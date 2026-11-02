package com.projectseele.client.render;

import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaShutdownR30;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.HashMap;
import java.util.Map;

/**
 * Overlapping action for the upper body, whichever pose owner drew it. Each
 * joint follows its drawn target with a short lag that grows from the chest
 * out to the hands, so the limbs trail the core like heavy limbs instead of
 * moving as one stiff piece, and a target that jumps within a frame (a combo
 * strike taking over, a support hand switching contacts) is spread over the
 * next few frames. Legs keep their exact pose for the planted feet; arms on
 * a rifle or cannon keep theirs, the hands being on the weapon. Strikes
 * shorten the lag to keep their snap.
 */
final class EvaFollowThroughR56
{
    private static final boolean ENABLED=!Boolean.getBoolean("projectseele.noFollowThroughR56");
    private static final String[] BONES={"torso_upper","neck","head","clavicle_l","clavicle_r","arm_l","arm_r",
            "forearm_l","forearm_r","wrist_l","wrist_r","hand_l","hand_r"};
    /** Seconds each joint trails its target by. */
    private static final float[] LAG={.030F,.040F,.055F,.035F,.035F,.040F,.040F,.050F,.050F,.055F,.055F,.060F,.060F};
    /** Lag scale while a strike plays. */
    private static final float STRIKE_LAG=.4F;

    private static final class State
    {
        final Map<String,Quaternionf> drawn=new HashMap<>();
        long time;
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial)
    {
        if(!ENABLED||!applies(eva))
        {
            STATES.remove(eva);
            return;
        }
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();
        State state=STATES.get(eva);
        if(state==null)
        {
            state=new State();
            STATES.put(eva,state);
        }
        // A second pass of the same frame (shadow map) draws the same pose.
        boolean repeat=now==state.time;
        float dt=(now-state.time)/1e9F;
        boolean fresh=state.time==0||dt<=0||dt>.2F;
        boolean striking=eva.hasLiveActionForRender(partial)||eva.getOrdinaryAttackStage()>=0||eva.isHeavyMotionActive()
                ||eva.hasLegacyStrikeForRender()||eva.isKickMotionActive(partial);
        int weapon=eva.getWeapon();
        boolean armed=weapon==EvaUnit01Entity.WEAPON_RIFLE||weapon==EvaUnit01Entity.WEAPON_CANNON||eva.fixedCannonOperatingR52();
        for(int i=0;i<BONES.length;i++)
        {
            String name=BONES[i];
            if(armed&&i>=3)continue;
            var bone=model.getBone(name).orElse(null);
            if(bone==null)continue;
            var last=state.drawn.get(name);
            Quaternionf drawn;
            if(repeat&&last!=null)drawn=last;
            else
            {
                var target=new Quaternionf().rotationZYX(bone.getRotZ(),bone.getRotY(),bone.getRotX());
                float lag=LAG[i]*(striking?STRIKE_LAG:1);
                drawn=fresh||last==null?target:new Quaternionf(last).slerp(target,1-(float)Math.exp(-dt/lag));
                state.drawn.put(name,drawn);
            }
            EvaRigTransforms.rotate(bone,drawn);
        }
        state.time=now;
    }

    private static boolean applies(EvaUnit01Entity eva)
    {
        return eva.isPoweredOn()&&!eva.isCrucified()&&!eva.isFirstBattleActive()&&!eva.isNervLogisticsLocked()
                &&!eva.isLaunchSequenceActive()&&eva.getActivationTicks()<=0&&eva.getVisualPose()==0
                &&!EvaShutdownR30.displayed(eva)&&!EvaAirTransportR31.active(eva)
                &&!com.projectseele.physics.CombatBodyDynamics.active(eva);
    }

    private EvaFollowThroughR56() {}
}

package com.projectseele.entity;

import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import static com.projectseele.entity.EvaKeyPosesR57.*;

/**
 * The jump and its aerial attacks as hand-set key poses on one continuous
 * timeline: squat, drive, tuck, reach for the ground, absorb, recover.
 * <p>
 * Stitched capture clips held one pose through the whole flight (legs
 * folded as if sitting, arms hanging) and stood upright in the air before
 * dropping into the landing. Here the timeline follows the body: the squat
 * by the take-off clock, the rise by time to the apex, the fall by the
 * height left to the ground, the landing by time since touchdown. Keys are
 * joined by Catmull-Rom curves, so the body never stops on a key. Angle
 * conventions are EvaKeyPosesR57's.
 */
final class EvaJumpChoreographyR57
{
    // Jump.
    private static final Key CROUCH=key(-21.06F,-20,0,0,-14,0,0,14,0,0,72,0,-6,72,0,6,-98,0,0,-98,0,0,24,0,0,24,0,0,-40,0,-8,-40,0,8,30,0,0,30,0,0);
    private static final Key LAUNCH=key(9.87F,-4,0,0,6,0,0,-5,0,0,-6,0,-3,-2,0,3,-6,0,0,-10,0,0,-30,0,0,-30,0,0,150,0,-15,150,0,15,20,0,0,20,0,0);
    private static final Key TUCK=key(0,-10,0,0,-8,0,0,4,0,0,65,0,-8,90,0,8,-95,0,0,-115,0,0,-15,0,0,-15,0,0,70,0,-45,70,0,45,40,0,0,40,0,0);
    private static final Key REACH=key(4.55F,-8,0,0,-4,0,0,6,0,0,12,0,-5,32,0,5,-22,0,0,-38,0,0,10,0,0,10,0,0,45,0,-70,45,0,70,25,0,0,25,0,0);
    private static final Key IMPACT=key(-29.06F,-26,0,0,-16,0,0,22,0,0,86,0,-12,78,0,12,-116,0,0,-108,0,0,30,0,0,30,0,0,40,0,-35,25,0,35,35,0,0,30,0,0);
    // Air hammer: both fists raised over the head, then driven down in front.
    private static final Key H_CHAMBER=key(0,8,0,0,14,0,0,-10,0,0,35,0,-8,45,0,8,-105,0,0,-115,0,0,-20,0,0,-20,0,0,160,0,14,160,0,-14,35,0,0,35,0,0);
    // Waiting for the drop, the hammer keeps drawing back.
    private static final Key H_DRAW=key(0,12,0,0,24,0,0,-16,0,0,28,0,-8,38,0,8,-115,0,0,-122,0,0,-25,0,0,-25,0,0,172,0,10,172,0,-10,55,0,0,55,0,0);
    private static final Key H_STRIKE=key(0,-20,0,0,-26,0,0,22,0,0,62,0,-8,70,0,8,-95,0,0,-100,0,0,-10,0,0,-10,0,0,95,0,16,95,0,-16,10,0,0,10,0,0);
    private static final Key H_LAND=key(-37.65F,-24,0,0,-18,0,0,26,0,0,92,0,-16,86,0,16,-122,0,0,-118,0,0,32,0,0,32,0,0,38,0,12,38,0,-12,4,0,0,4,0,0);
    // Air kick: right knee drawn to the chest, then the leg driven out, chest back.
    private static final Key K_CHAMBER=key(0,8,0,0,6,0,0,-6,0,0,55,0,-10,110,0,4,-110,0,0,-130,0,0,-20,0,0,10,0,0,60,0,-55,30,0,60,50,0,0,40,0,0);
    private static final Key K_STRIKE=key(0,0,0,0,22,0,0,-12,0,0,40,0,-10,88,0,4,-115,0,0,-4,0,0,-20,0,0,20,0,0,-30,0,-60,-30,0,60,30,0,0,30,0,0);
    private static final Key K_LAND=key(-7.72F,-14,0,0,-10,0,0,12,0,0,-25,0,-6,60,0,6,-30,0,0,-60,0,0,-10,0,0,10,0,0,50,0,-40,20,0,55,35,0,0,25,0,0);

    /** Ticks from take-off to the apex at the EVA's jump speed and gravity. */
    private static final float APEX_TICKS=12;
    /** Landing: touchdown to the deepest bend, then back to the ground pose. */
    private static final float IMPACT_TICKS=3,RECOVER_TICKS=14;
    static final float LANDING_TICKS=IMPACT_TICKS+1+RECOVER_TICKS;

    private static final class State {long air=-1,takeoff=-1;float top=-1,highest;int attack;}
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    private static State state(EvaUnit01Entity e){return STATES.computeIfAbsent(e,k->new State());}

    /** The squat and drive before leaving the ground; progress 0..1 over the take-off ticks. */
    static EvaBodyPose.Sample takeoff(EvaUnit01Entity e,EvaBodyPose.Sample base,float progress)
    {
        state(e).takeoff=e.level().getGameTime();
        // Sink slowly into the squat, then drive up hard through the extension.
        // It starts from the live pose: the pose frozen at the press on the
        // server was a little off the frame the client had just drawn.
        float s=progress<.65F?ease(progress/.65F):1+(progress-.65F)/.35F;
        return play(base,new Key[]{null,CROUCH,LAUNCH,TUCK},s);
    }

    /** Flight, with the aerial attack carried through to the ground. */
    static EvaBodyPose.Sample flight(EvaUnit01Entity e,EvaBodyPose.Sample base,float air,long airStart,float clearance,boolean descending,int action,float age,float stroke)
    {
        // The jump is known by its synced start tick: recomputing it from the
        // float age flipped between two ticks and reset the fall every frame.
        var st=state(e);
        if(st.air!=airStart){st.air=airStart;st.top=-1;st.highest=0;st.attack=0;}
        st.highest=Math.max(st.highest,clearance);
        boolean jumped=st.takeoff>=0&&airStart-st.takeoff<=3;
        float rising=2+(1-(1-Math.min(1,air/APEX_TICKS))*(1-Math.min(1,air/APEX_TICKS)));
        if(!jumped&&st.top<0)st.top=3.4F;
        float s;
        if(!descending&&st.top<0)s=rising;
        else
        {
            if(st.top<0)st.top=rising;
            // The legs unfold as the ground comes up: slowly at the top, fully at touchdown.
            float fall=st.highest>1?Mth.clamp(1-clearance/st.highest,0,1):1;
            s=Mth.lerp(fall*fall*(3-2*fall),st.top,4);
        }
        // A fall without a take-off eases in from the ground pose.
        var pose=jumped?play(base,new Key[]{null,CROUCH,LAUNCH,TUCK,REACH,IMPACT},s)
                :EvaBodyPose.blend(base,play(base,new Key[]{null,CROUCH,LAUNCH,TUCK,REACH,IMPACT},s),ease(Math.min(1,air/4)));
        if(action!=EvaCombatR31.AIR_STRIKE&&action!=EvaCombatR31.AIR_SLAM)return pose;
        boolean kick=action==EvaCombatR31.AIR_SLAM;st.attack=kick?2:1;
        float fall=st.highest>1?Mth.clamp(1-clearance/st.highest,0,1):1;
        // Chamber over four ticks and hold it; the stroke snaps out in three
        // and then eases on towards the landing as the ground comes up.
        if(kick)
        {
            float a=stroke<0?ease(Math.min(1,age/4)):1+ease(Math.min(1,stroke/3))+(stroke>=3?.45F*fall:0);
            return play(pose,new Key[]{null,K_CHAMBER,K_STRIKE,K_LAND},a);
        }
        // Raise, keep drawing back until the drop, then strike from wherever the draw had reached.
        float drawn=stroke<0?draw(age):draw(age-stroke);
        float a=stroke<0?drawn:drawn+(3-drawn)*ease(Math.min(1,stroke/3))+(stroke>=3?.45F*fall:0);
        return play(pose,new Key[]{null,H_CHAMBER,H_DRAW,H_STRIKE,H_LAND},a);
    }

    private static float draw(float age){return age<4?ease(age/4):1+out(Math.min(1,(age-4)/12));}

    /** Touchdown: from the pose the body landed in, into the bend and back up to the ground pose. */
    static EvaBodyPose.Sample landing(EvaUnit01Entity e,EvaBodyPose.Sample from,EvaBodyPose.Sample ground,float land)
    {
        int attack=state(e).attack;
        Key impact=attack==1?H_LAND:attack==2?K_LAND:IMPACT;
        float s=land<IMPACT_TICKS?out(land/IMPACT_TICKS):land<IMPACT_TICKS+1?1:1+ease(Math.min(1,(land-IMPACT_TICKS-1)/RECOVER_TICKS));
        // Both ends are live poses: interpolate the touchdown key between them.
        var into=play(from,new Key[]{null,impact},Math.min(1,s));
        return s<=1?into:EvaBodyPose.blend(into,ground,ease(s-1));
    }

    private EvaJumpChoreographyR57(){}
}

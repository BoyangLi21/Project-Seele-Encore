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
    // R64 (EvaLeapR64), the planted model's jump, as a Unit gathers and leaps in the original: hunched low over
    // its knees with the head up before it goes, the arms swept back and out as it climbs (not reached overhead),
    // and folded far over its knees where it comes down hard. The legs and the lift are those of the keys they
    // stand in for, so a body that is not on planted feet keeps its soles on the ground.
    private static final Key LEAP_CROUCH=key(-21.06F,-32,0,0,-22,0,0,26,0,0,72,0,-6,72,0,6,-98,0,0,-98,0,0,24,0,0,24,0,0,-28,0,-14,-28,0,14,48,0,0,48,0,0);
    // Going up the body is long: the back arched, the legs trailing with the toes pointed, the arms swept back.
    private static final Key LEAP_LAUNCH=key(9.87F,6,0,0,12,0,0,-14,0,0,-16,0,-4,-4,0,4,-16,0,0,-34,0,0,-36,0,0,-36,0,0,-52,0,-30,-52,0,30,22,0,0,22,0,0);
    // At the top it is gathered like an animal about to come down on something: hunched over knees drawn up to
    // the chest, the head up, the arms back and out. (Up to R63 the trunk stayed upright with the arms held out
    // ahead, which over two seconds in the air reads as sitting on a chair.)
    private static final Key LEAP_TUCK=key(0,-30,0,0,-20,0,0,32,0,0,84,0,-10,104,0,10,-112,0,0,-128,0,0,-10,0,0,-10,0,0,-34,0,-46,-34,0,46,44,0,0,44,0,0);
    // Coming down the legs go to the ground a little apart, and the arms are held out wide of the body.
    private static final Key LEAP_REACH=key(4.55F,-16,0,0,-8,0,0,16,0,0,12,0,-10,32,0,10,-22,0,0,-38,0,0,10,0,0,10,0,0,8,0,-78,8,0,78,32,0,0,32,0,0);
    private static final Key LEAP_IMPACT=key(-29.06F,-38,0,0,-24,0,0,28,0,0,86,0,-12,78,0,12,-116,0,0,-108,0,0,30,0,0,30,0,0,28,0,-52,16,0,52,52,0,0,46,0,0);
    private static final Key IMPACT=key(-29.06F,-26,0,0,-16,0,0,22,0,0,86,0,-12,78,0,12,-116,0,0,-108,0,0,30,0,0,30,0,0,40,0,-35,25,0,35,35,0,0,30,0,0);
    // Air hammer: the hands clasped over the head, the back arched; then the
    // clasped fists swing down in front through the fall and strike the
    // ground in front of the knees at touchdown.
    private static final Key H_RAISE=key(0,8,0,0,12,0,0,-8,0,0,42,0,-8,52,0,8,-112,0,0,-118,0,0,-20,0,0,-20,0,0,170,0,-17,170,0,17,24,0,0,24,0,0);
    // Cocked: drawn back like a bow from the heels to the fists behind the head.
    private static final Key H_RAISE2=key(0,20,0,0,22,0,0,-18,0,0,8,0,-6,20,0,6,-120,0,0,-128,0,0,-25,0,0,-25,0,0,178,0,-18,178,0,18,50,0,0,50,0,0);
    // The bow lets go: the body jackknifes over the arms and the elbows straighten as a whip.
    private static final Key H_SWING=key(0,-26,0,0,-24,0,0,18,0,0,62,0,-8,72,0,8,-95,0,0,-102,0,0,-10,0,0,-10,0,0,100,-16,0,100,16,0,20,0,0,20,0,0);
    private static final Key H_SLAM=key(-34.51F,-34,0,0,-30,0,0,34,0,0,92,0,-16,86,0,16,-122,0,0,-116,0,0,32,0,0,32,0,0,58,-10,0,58,10,0,0,0,0,0,0,0);
    // Struck: knees wide, the fists driven into the ground in front of the feet.
    private static final Key H_SLAM_DEEP=key(-39.21F,-32,0,0,-26,0,0,34,0,0,96,0,-20,90,0,20,-124,0,0,-120,0,0,34,0,0,34,0,0,88,-12,0,88,12,0,0,0,0,0,0,0);
    // Air kick: coiled tight behind a guard, both knees to the chest; the leg
    // snaps out heel first and the whole body lies back along it, one line from
    // the head to the heel diving at the target, the other leg folded and the
    // arms flung behind. The landing drops onto the kicking foot, rear knee to
    // the ground, the right fist planted in front. With the body upright and
    // the leg held out level, it hung in the air with nothing behind it.
    private static final Key K_CHAMBER=key(0,22,0,0,-16,0,0,8,0,0,72,0,-8,110,0,4,-128,0,0,-140,0,0,-30,0,0,25,0,0,66,0,-16,56,0,16,118,0,0,112,0,0);
    private static final Key K_STRIKE=key(0,46,0,0,-8,0,0,-28,0,0,80,0,-10,18,0,4,-130,0,0,-3,0,0,-25,0,0,30,0,0,-58,0,-36,-52,0,36,22,0,0,28,0,0);
    private static final Key K_LAND=key(-26.61F,-32,0,0,-22,0,0,30,0,0,37,0,-10,112,0,8,-90,0,0,-90,0,0,-10,0,0,10,0,0,-25,0,-45,62,0,10,30,0,0,8,0,0);

    /** Ticks from take-off to the apex at the EVA's jump speed and gravity. */
    private static final float APEX_TICKS=14;
    /**
     * Landing: touchdown to the deepest bend, held, then back to the ground
     * pose. An aerial attack drives into its strike faster and holds it
     * longer, in the same total.
     */
    private static final float IMPACT_TICKS=3,HOLD_TICKS=1,RECOVER_TICKS=14;
    private static final float STRIKE_IMPACT_TICKS=2,STRIKE_HOLD_TICKS=4;
    static final float LANDING_TICKS=IMPACT_TICKS+HOLD_TICKS+RECOVER_TICKS;

    private static final class State {long air=-1,takeoff=-1;float top=-1,highest,swingFrom=-1,fallAt=-1;int attack;}
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
        return play(base,EvaLeapR64.on(e)?new Key[]{null,LEAP_CROUCH,LEAP_LAUNCH,LEAP_TUCK}:new Key[]{null,CROUCH,LAUNCH,TUCK},s);
    }

    /** Flight, with the aerial attack carried through to the ground. */
    static EvaBodyPose.Sample flight(EvaUnit01Entity e,EvaBodyPose.Sample base,float air,long airStart,float clearance,boolean descending,int action,float age,float stroke)
    {
        // The jump is known by its synced start tick: recomputing it from the
        // float age flipped between two ticks and reset the fall every frame.
        var st=state(e);
        if(st.air!=airStart){st.air=airStart;st.top=-1;st.highest=0;st.attack=0;st.swingFrom=-1;st.fallAt=-1;}
        if(descending&&st.fallAt<0)st.fallAt=air;
        st.highest=Math.max(st.highest,clearance);
        boolean jumped=st.takeoff>=0&&airStart-st.takeoff<=3;
        boolean leap=EvaLeapR64.on(e);
        float apex=leap?EvaLeapR64.riseTicks(e):APEX_TICKS;
        // (R64: a jump that goes this high stays long for the first of its rise and gathers as it slows.)
        float rising=leap?2+ease(air/apex):2+(1-(1-Math.min(1,air/apex))*(1-Math.min(1,air/apex)));
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
        Key[] keys=leap?new Key[]{null,LEAP_CROUCH,LEAP_LAUNCH,LEAP_TUCK,LEAP_REACH,IMPACT}:new Key[]{null,CROUCH,LAUNCH,TUCK,REACH,IMPACT};
        var pose=jumped?play(base,keys,s):EvaBodyPose.blend(base,play(base,keys,s),ease(Math.min(1,air/4)));
        if(action!=EvaCombatR31.AIR_STRIKE&&action!=EvaCombatR31.AIR_SLAM)return pose;
        boolean kick=action==EvaCombatR31.AIR_SLAM;st.attack=kick?2:1;
        float fall=st.highest>1?Mth.clamp(1-clearance/st.highest,0,1):1;
        // Coil over four ticks and hold it; the leg snaps out in two, fastest
        // at the start, and stays out through the fall, coming down to plant
        // only as the ground comes up. Eased in and out over three, then
        // drifting halfway to the landing, the kick had no snap.
        if(kick)
        {
            float a=stroke<0?ease(Math.min(1,age/3)):1+out(Math.min(1,stroke/2))+(stroke>=2?.3F*fall*fall*fall:0);
            return play(pose,new Key[]{null,K_CHAMBER,K_STRIKE,K_LAND},a);
        }
        // Raise the clasped hands in three ticks, arch back in three more, then
        // swing through the drop so the fists strike the ground at touchdown.
        boolean dropping=stroke>=0;
        float since=Math.max(0,stroke);
        if(dropping&&st.swingFrom<0)st.swingFrom=fall;
        float raised=raise(dropping?age-since:age);
        // From the drop the arms come down gathering speed, as a blow does,
        // and are fastest as the fists reach the ground.
        float swing=!dropping?0:(float)Math.pow(Math.max(Math.min(1,since/SWING_TICKS),
                Mth.clamp((fall-st.swingFrom)/Math.max(.05F,1-st.swingFrom),0,1)),1.6);
        float from=dropping?raised+Math.max(0,1.9F-raised)*Math.min(1,since/2):raised;
        var hammer=play(pose,new Key[]{null,H_RAISE,H_RAISE2,H_SWING,H_SLAM},from+(4-from)*swing);
        clasp(hammer,CLASP,ease(Math.min(1,age/3)));
        return hammer;
    }
    /** Wrist to wrist, model units, of the fists clasped for the hammer. */
    private static final float CLASP=.55F;
    /** Ticks of the swing if the ground is further off than that. */
    private static final float SWING_TICKS=6;

    private static float raise(float age){return age<3?ease(age/3):1+out(Math.min(1,(age-3)/3));}

    /** How far the hammer's wrists are straightened into closed fists in line with the forearms. */
    static float hammerFists(EvaUnit01Entity e,float partial)
    {
        int action=EvaCombatR31.action(e);
        if(action==EvaCombatR31.AIR_STRIKE)return EvaPoseBlendR51.smooth(EvaCombatR31.age(e,partial)/3F);
        return action==EvaCombatR31.LAND&&state(e).attack==1?1-EvaPoseBlendR51.smooth((EvaCombatR31.age(e,partial)-7)/5F):0;
    }

    /** Touchdown: from the pose the body landed in, into the bend and back up to the ground pose. */
    static EvaBodyPose.Sample landing(EvaUnit01Entity e,EvaBodyPose.Sample from,EvaBodyPose.Sample ground,float land)
    {
        int attack=state(e).attack;
        // R64: a hard landing folds further, is held longer and comes up more slowly.
        float hard=EvaGameplayMotionR32.impactR64(e),all=EvaGameplayMotionR32.landingTicksR64(e);
        Key impact=attack==1?H_SLAM_DEEP:attack==2?K_LAND:hard>0?mix(IMPACT,LEAP_IMPACT,hard):IMPACT;
        float in=attack==0?IMPACT_TICKS+hard:STRIKE_IMPACT_TICKS,hold=attack==0?HOLD_TICKS+4*hard:STRIKE_HOLD_TICKS;
        float s=land<in?out(land/in):land<in+hold?1:1+ease(Math.min(1,(land-in-hold)/(all-in-hold)));
        // Both ends are live poses: interpolate the touchdown key between them.
        var into=play(from,new Key[]{null,impact},Math.min(1,s));
        // The hammer's fists stay clasped into the strike, and part as the body rises.
        if(attack==1)clasp(into,CLASP,1);
        return s<=1?into:EvaBodyPose.blend(into,ground,ease(s-1));
    }

    private static Key mix(Key a,Key b,float t)
    {
        float[] d=new float[a.degrees().length];
        for(int i=0;i<d.length;i++)d[i]=Mth.lerp(t,a.degrees()[i],b.degrees()[i]);
        return key(Mth.lerp(t,a.lift(),b.lift()),d);
    }

    private EvaJumpChoreographyR57(){}
}

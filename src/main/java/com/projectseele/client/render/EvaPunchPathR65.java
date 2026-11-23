package com.projectseele.client.render;

import com.projectseele.entity.EvaBodyPose;
import com.projectseele.entity.EvaGameplayMotionR32;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleSignals;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

import java.util.HashMap;
import java.util.Map;

/**
 * R65: the way the fist goes in a punch thrown from a stand.
 * <p>
 * The owner, 2026-11-23, of the left and right punches: "还是要靠拢一下向前攻击，现在普通攻击两端有点像是抬胳膊，
 * 没有那种向前攻击的感觉". Measured on the jab as R65 shipped it: the upper arm is raised in front of the chest and the
 * fist is carried up 23 blocks to the height of the shoulder, three quarters of that way upward; from there to its
 * mark, 4 blocks over the shoulder, it goes 10 blocks, two thirds of them upward and outward; and after the blow the
 * arm is let down straight, the fist out ahead as it sinks. At both ends an arm is raised and lowered; nothing is
 * thrust.
 * <p>
 * Here the punching hand goes a way of its own (the trunk, the hips and the legs are the clip's and
 * EvaPunchBodyR65's). By the row's own ticks: the forearm folds and the fist is drawn to the chamber, in front of
 * the chest under its own shoulder, the elbow down; from there it is thrust in a straight line to the mark, nine
 * tenths of the way ahead, and is on it as the row's first live tick ends (a target that is nearer is met earlier in
 * the clip, with the arm not yet out, as the row's clock has it); it stays on the mark while the row is live; it is
 * taken straight back to the chamber, from where the other hand's blow follows (that hand is thrust from its own
 * chamber, and this one waits in its chamber until the string is over); and it is let down from the chamber along
 * the body. The mark is where the clip itself has the fist at its contact, but no higher than the shoulder: a blow
 * goes at the middle of what stands in front of the Unit, an Angel's core, not over it. The arm is solved to the
 * way as a held Angel's is (EvaRigTransforms.solveArm); the hand keeps the turn the clip gives it against its
 * forearm. What lands is decided on the server from the row and is not touched.
 * <p>
 * The path is the arm's own continuity: it begins where the hand is and ends where it hangs. Two later layers
 * that soften quick changes stand aside for the arm while the path has it, because they took the quick fold to
 * the chamber and the way back for jumps and the fist never came to its chamber: the follow-through trails it
 * less (lag), the continuity blend does not watch it (bones). The path goes by the row's clock (the flow, on by
 * default); without that clock a punch is drawn as R65 shipped it.
 */
final class EvaPunchPathR65
{
    private static final boolean ENABLED=!Boolean.getBoolean("projectseele.noPunchPathR65");
    private static final boolean DIAG=Boolean.getBoolean("projectseele.punchPathDiagR65");
    /**
     * The chamber: the fist from its own shoulder as the chest has it (toward the other shoulder, down, forward), in
     * the model's units (five blocks each). Tried on the Unit's meshes (tools penlab/exp_punch.py): no part of the
     * arm beyond the shoulder's cap is in the chest or under the pylon anywhere on the way.
     */
    private static final float IN=.2F,UNDER=.9F,AHEAD=1.2F;
    /**
     * The elbow on the whole way, as the chest has it: outward, down, forward. Down and a little back: further out
     * (.8, 1, .2 was tried) the forearm lay across the chest like a bar when seen from ahead.
     */
    private static final float ELBOW_OUT=.35F,ELBOW_DOWN=1F,ELBOW_AHEAD=-.25F;
    /** A blow's mark is no higher over the middle of the hips than this (the shoulders are 2.5 over them). */
    private static final float LEVEL=2.4F;
    /**
     * Ticks of the row: the fist is on its mark this long after the start-up; the thrust takes this long; back to
     * the chamber in this; held there; let down; and given back to the clip.
     */
    private static final float REACH=.7F,THRUST=2.2F,BACK=3F,HOLD=1F,DOWN=5F,FREE=1.5F;
    /** Ticks in which a hand is given back when its blow is broken off. */
    private static final float CUT=2F;
    /**
     * The arm on the path trails its pose by this share of a strike's usual lag (EvaFollowThroughR56). At the full
     * lag the forearm had not folded when the thrust began: the fist swung out ahead in an arc and never came to
     * the chamber (measured: the elbow no nearer than 80 degrees, 45 asked).
     */
    private static final float LAG=.35F;

    /** One hand: the blow it is in or coming back from. */
    private static final class Hand
    {
        String clip;
        int serial,startup,live;
        /** Where in that blow's row the hand is: the row's own place, and the hand's own count once the row is another's or over. */
        double place;
        /** Where the hand was as the blow began, from the middle of the hips, and how much of it was this path's. */
        final Vector3f from=new Vector3f();float fromWeight;
        /** The same in the frame before. */
        final Vector3f at=new Vector3f();float weight;
        /** How far the hand has been given back after its blow was broken off. */
        float cut;
        /**
         * Where the hand hangs when the blow is over, from the middle of the hips: where it hung as a blow last
         * began with neither hand on a path. (EvaBodyPose.ordinaryReleaseTargetR52 is not for asking here: it
         * throws unless the Unit stands still with bare fists, and stopped a client in the second punch.)
         */
        final Vector3f rest=new Vector3f();
        /** How much of the arm was the path's in the frame drawn last. */
        float drawn;
    }
    private static final class State{final Hand[] hands={new Hand(),new Hand()};double time;}
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();
    /** Where a clip has a hand at a phase, from the middle of the hips (model units), by Unit, clip and phase. */
    private static final Map<String,Vector3f> PLACES=new HashMap<>();

    private static final java.util.Set<String> LEFT=java.util.Set.of("arm_l","forearm_l"),RIGHT=java.util.Set.of("arm_r","forearm_r"),
            BOTH=java.util.Set.of("arm_l","forearm_l","arm_r","forearm_r");
    /** The arm bones this path has in the frame in hand. It keeps them continuous itself (EvaPoseContinuity leaves them be). */
    static java.util.Set<String> bones(EvaUnit01Entity eva)
    {
        State state=STATES.get(eva);
        if(state==null)return java.util.Set.of();
        boolean l=state.hands[0].clip!=null&&state.hands[0].drawn>0,r=state.hands[1].clip!=null&&state.hands[1].drawn>0;
        return l&&r?BOTH:l?LEFT:r?RIGHT:java.util.Set.of();
    }

    /** The share of its usual lag an arm's joint trails by: less while this path has the arm (EvaFollowThroughR56). */
    static float lag(EvaUnit01Entity eva,String bone)
    {
        State state=STATES.get(eva);
        if(state==null)return 1;
        int side=bone.endsWith("_l")?0:bone.endsWith("_r")?1:-1;
        if(side<0||!bone.startsWith("arm_")&&!bone.startsWith("forearm_"))return 1;
        Hand hand=state.hands[side];
        return hand.clip==null?1:Mth.lerp(hand.drawn,1F,LAG);
    }

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(!ENABLED||root==null)return;
        State state=STATES.get(eva);
        if(!EvaGameplayMotionR32.ready(eva)){if(state!=null)STATES.remove(eva);return;}
        String clip=EvaGameplayMotionR32.activeGroundClip(eva,partial);
        var clock=eva.rowClockR65();
        boolean punch=(clip.equals("jab")||clip.equals("cross"))&&clock!=null&&clock.clip().equals(clip);
        if(state==null)
        {
            if(!punch)return;
            state=new State();STATES.put(eva,state);
        }
        double time=FirstBattleSignals.clientFrameTime()/5.0e7D;
        // A second pass of one frame (the shadow's) moves nothing on; a long gap (another pose owner had the body) ends what was left.
        double dt=state.time==0?0:time-state.time;
        state.time=time;
        if(dt<0||dt>6){dt=0;for(Hand hand:state.hands){hand.clip=null;hand.drawn=0;}}
        GeoBone legL=model.getBone("leg_l").orElse(null),legR=model.getBone("leg_r").orElse(null),chest=model.getBone("torso_upper").orElse(null);
        if(legL==null||legR==null||chest==null)return;

        Vector3f hips=point(legL).add(point(legR)).mul(.5F);
        int puncher=-1;double place=0;int startup=0,live=0;
        if(punch)
        {
            // Where the row is, from the phase it is drawn at: a blow held for its hit holds the fist with it.
            float phase=EvaGameplayMotionR32.activeGroundPhase(eva,partial);
            int serial=clock.serial();
            startup=clock.startup();live=clock.live();
            place=clock.place(phase,0,clock.total());
            puncher=EvaGameplayMotionR32.side(eva,clip).equals("l")?0:1;
            Hand hand=state.hands[puncher];
            if(state.hands[0].clip==null&&state.hands[1].clip==null)for(int i=0;i<2;i++)
            {
                Hand each=state.hands[i];
                model.getBone(i==0?"hand_l":"hand_r").ifPresent(b->each.rest.set(point(b).sub(hips)));
            }
            if(hand.clip==null||hand.serial!=serial||!hand.clip.equals(clip)||place<hand.place-1.5)
            {
                hand.fromWeight=hand.clip==null?0:hand.weight*(1-hand.cut);hand.from.set(hand.at);
                hand.clip=clip;hand.serial=serial;hand.startup=startup;hand.live=live;hand.cut=0;
            }
            hand.place=place;
        }
        for(int i=0;i<2;i++)
        {
            Hand hand=state.hands[i];
            if(hand.clip==null||i==puncher)continue;
            double back=hand.startup+hand.live+BACK,held=back+HOLD;
            if(punch)
            {
                // The other hand of a string: back to its chamber, there until the blow in hand is let down, and down with it.
                hand.place=hand.place<=held?Math.min(hand.place+dt,held):hand.place+dt;
                double down=place-(startup+live+BACK+HOLD);
                if(down>0)hand.place=Math.max(hand.place,held+down);
            }
            else
            {
                // The row is over, or was broken off: a hand not yet back is given back to whatever has the body now.
                if(hand.place<back||!clip.isEmpty())hand.cut=Math.min(1,hand.cut+(float)dt/CUT);
                hand.place=Math.max(hand.place+dt,hand.startup+hand.live);
            }
        }

        Matrix4f chestNow=EvaRigTransforms.model(chest);
        for(int i=0;i<2;i++)
        {
            Hand hand=state.hands[i];
            if(hand.clip==null)continue;
            String side=i==0?"l":"r";float k=i==0?-1:1;
            GeoBone upper=model.getBone("arm_"+side).orElse(null),lower=model.getBone("forearm_"+side).orElse(null);
            GeoBone wrist=model.getBone("wrist_"+side).orElse(null),fist=model.getBone("hand_"+side).orElse(null);
            Vector3f mark=mark(eva,hand.clip,side),rest=hand.rest;
            hand.drawn=0;
            if(upper==null||lower==null||wrist==null||fist==null||mark==null){hand.clip=null;continue;}
            // The model's right is +x and it faces -z.
            Vector3f chamber=point(upper).add(chestNow.transformDirection(new Vector3f(-k*IN,-UNDER,-AHEAD))).sub(hips);
            Vector3f own=point(fist).sub(hips);
            float p=(float)hand.place,out=hand.startup+REACH,drawn=out-THRUST,end=hand.startup+hand.live;
            Vector3f at;float weight=1;String part;
            if(p<drawn)
            {
                part="draw";
                at=new Vector3f(hand.fromWeight>0?hand.from:own).lerp(chamber,smooth(p/drawn));
                weight=Mth.lerp(smooth(p/(.6F*drawn)),hand.fromWeight,1F);
            }
            else if(p<out){part="thrust";at=new Vector3f(chamber).lerp(mark,(float)Math.pow((p-drawn)/(out-drawn),1.7));}
            else if(p<end){part="mark";at=new Vector3f(mark);}
            else if(p<end+BACK){part="back";float v=1-(p-end)/BACK;at=new Vector3f(mark).lerp(chamber,1-v*v);}
            else if(p<end+BACK+HOLD){part="hold";at=chamber;}
            else if(p<end+BACK+HOLD+DOWN){part="down";at=new Vector3f(chamber).lerp(rest,smooth((p-end-BACK-HOLD)/DOWN));}
            else if(p<end+BACK+HOLD+DOWN+FREE){part="free";at=new Vector3f(rest);weight=1-smooth((p-end-BACK-HOLD-DOWN)/FREE);}
            else{hand.clip=null;hand.weight=0;continue;}
            hand.at.set(at);hand.weight=weight;
            weight*=1-hand.cut;
            if(hand.cut>=1){hand.clip=null;hand.weight=0;continue;}
            if(DIAG)com.projectseele.ProjectSeele.LOGGER.info("R65PUNCH path {} {} {} place {} {} weight {} at {} {} {}",String.format(java.util.Locale.ROOT,"%.2f",time),
                    side,hand.clip,String.format(java.util.Locale.ROOT,"%.2f",p),part,String.format(java.util.Locale.ROOT,"%.2f",weight),
                    String.format(java.util.Locale.ROOT,"%.2f",at.x),String.format(java.util.Locale.ROOT,"%.2f",at.y),String.format(java.util.Locale.ROOT,"%.2f",at.z));
            if(weight<=.001F)continue;
            hand.drawn=weight;
            GeoBone[] bones={upper,lower,wrist,fist};float[][] before=new float[4][];
            for(int b=0;b<4;b++)before[b]=new float[]{bones[b].getRotX(),bones[b].getRotY(),bones[b].getRotZ(),bones[b].getPosX(),bones[b].getPosY(),bones[b].getPosZ()};
            var pole=new Matrix4f(root).mul(chestNow).transformDirection(new Vector3f(k*ELBOW_OUT,-ELBOW_DOWN,-ELBOW_AHEAD)).normalize();
            var handNow=EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(fist)));
            EvaRigTransforms.solveArm(upper,lower,wrist,fist,side,root.transformPosition(new Vector3f(hips).add(at)),handNow,pole,root);
            // the hand as the clip turns it against its forearm (a punch's wrist is put straight after this, EvaAnatomicalHandsR45)
            for(int b=2;b<4;b++){bones[b].setRotX(before[b][0]);bones[b].setRotY(before[b][1]);bones[b].setRotZ(before[b][2]);}
            if(weight<1)for(int b=0;b<2;b++)
            {
                var was=new Quaternionf().rotationZYX(before[b][2],before[b][1],before[b][0]);
                var now=new Quaternionf().rotationZYX(bones[b].getRotZ(),bones[b].getRotY(),bones[b].getRotX());
                EvaRigTransforms.rotate(bones[b],was.slerp(now,weight));
                bones[b].setPosX(Mth.lerp(weight,before[b][3],bones[b].getPosX()));bones[b].setPosY(Mth.lerp(weight,before[b][4],bones[b].getPosY()));
                bones[b].setPosZ(Mth.lerp(weight,before[b][5],bones[b].getPosZ()));
            }
            EvaRigTransforms.hinge(lower,EvaRigTransforms.elbow(lower,side));
        }
    }

    /**
     * A blow's mark from the middle of the hips: where the clip has the fist at its contact, held to LEVEL; a fist
     * that is brought down goes as much further ahead as keeps it as far from its shoulder, so the arm is as
     * straight on the mark as the clip has it.
     */
    private static Vector3f mark(EvaUnit01Entity eva,String clip,String side)
    {
        String key=eva.getUnitVariant()+":"+clip+":mark";
        Vector3f known=PLACES.get(key);
        if(known!=null)return known;
        float contact=EvaGameplayMotionR32.contactPhase(eva,clip);
        Vector3f fist=where(eva,clip,side,contact),shoulder=where(eva,clip,"arm_"+side,contact);
        if(fist==null||shoulder==null)return null;
        Vector3f mark=new Vector3f(fist);
        if(mark.y>LEVEL)
        {
            Vector3f reach=new Vector3f(fist).sub(shoulder);
            float down=LEVEL-shoulder.y,flat=reach.lengthSquared()-down*down-reach.x*reach.x;
            mark.y=LEVEL;
            if(flat>reach.z*reach.z)mark.z=shoulder.z-Mth.sqrt(flat);
        }
        PLACES.put(key,mark);
        com.projectseele.ProjectSeele.LOGGER.info("R65PUNCH unit {} {}: the clip's fist at its contact is {} from the hips, the mark {} (model units: right, up, back)",
                eva.getUnitVariant(),clip,text(fist),text(mark));
        return mark;
    }

    /**
     * Where a clip has a hand ("l", "r") or another bone at a phase, from the middle of the hips, in the pose as it
     * is drawn: the strike's chest as the model has it over the legs the Unit stands on
     * (EvaBodyPose.strikeOverSupportR64), the waist held to its range (EvaJointLimitsR57), the arm as the clip has
     * it. Found once for a Unit, a clip and a phase.
     */
    private static Vector3f where(EvaUnit01Entity eva,String clip,String bone,float phase)
    {
        String name=bone.length()==1?"hand_"+bone:bone,key=eva.getUnitVariant()+":"+clip+":"+name+":"+phase;
        Vector3f known=PLACES.get(key);
        if(known!=null)return known;
        var strike=EvaBodyPose.copy(EvaBodyPose.gameplayClip(eva,clip,phase));
        var support=EvaBodyPose.sample(eva,0);
        String chest="torso_upper";
        if(!strike.rig.containsKey(chest)||!strike.rig.containsKey(name)||!strike.rig.containsKey("leg_l")||!strike.rig.containsKey("leg_r"))return null;
        var facing=strike.matrix(chest).getUnnormalizedRotation(new Quaternionf()).normalize();
        for(String each:support.rig.keySet())if(EvaBodyPose.locomotionBoneR51(each)&&strike.rotations.containsKey(each))
        {
            strike.rotations.get(each).set(support.rotations.get(each));
            strike.positions.get(each).set(support.positions.get(each));
        }
        strike.dirty();
        var under=strike.matrix(strike.rig.get(chest).parent()).getUnnormalizedRotation(new Quaternionf()).normalize();
        strike.rotations.get(chest).set(EvaJointLimitsR57.limited(chest,under.invert().mul(facing)));
        strike.dirty();
        Vector3f at=strike.matrix(name).transformPosition(new Vector3f(strike.rig.get(name).pivot()));
        Vector3f hips=strike.matrix("leg_l").transformPosition(new Vector3f(strike.rig.get("leg_l").pivot()))
                .add(strike.matrix("leg_r").transformPosition(new Vector3f(strike.rig.get("leg_r").pivot()))).mul(.5F);
        at.sub(hips);
        PLACES.put(key,at);
        return at;
    }

    private static String text(Vector3f v){return String.format(java.util.Locale.ROOT,"%.2f %.2f %.2f",v.x,v.y,v.z);}
    private static Vector3f point(GeoBone bone){return EvaRigTransforms.model(bone).transformPosition(EvaRigTransforms.pivot(bone));}
    private static float smooth(float t){t=Mth.clamp(t,0,1);return t*t*(3-2*t);}

    private EvaPunchPathR65(){}
}

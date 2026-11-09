package com.projectseele.client.render;

import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.util.Mth;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * Last touches on a crouched or prone body, whichever pose owner drew it.
 * <p>
 * The shoulder pylons keep their authored motion (riding the arms is off by
 * default: it set them swinging through every walk). The dorsal cover folds
 * back as the helmet tips back toward it, and further as the chest lies
 * down, where the neck also reaches out of the collar (feet:
 * {@link EvaGroundContactR56}). Free hands
 * reach for the ground on the way down and lie palm down on it; the captured
 * pose rolled them onto their edges with the wrist bent outward.
 * <p>
 * Crouched, empty hands hang in line with the forearm instead of turning
 * their palms back and out.
 */
final class EvaStanceFinishR56
{
    /** Share of the upper arm's swing each shoulder pylon takes up. */
    private static final float PYLON_FOLLOW=Float.parseFloat(System.getProperty("projectseele.pylonFollowR56","0"));
    private static final float COVER_TILT=Float.parseFloat(System.getProperty("projectseele.proneCoverTiltR56","90"));
    /** Helmet tip-back (degrees from the chest) the cover allows before folding, and its fold per degree beyond. */
    private static final float COVER_FREE=8,COVER_PER_DEGREE=1.3F,COVER_MAX=100;
    /** The neck reaches this far along the chest (model pixels), lifting the helmet out of the collar. */
    private static final float NECK_REACH=2.5F,NECK_DROP=2.5F;
    /** Chest tilt from upright (degrees) from which the back folds, and by which it is folded. */
    private static final float FOLD_FROM=25,FOLD_FULL=70;
    /** A flat prone hand turns its fingers this far outward from the forearm. */
    private static final float PALM_TURN=10*Mth.DEG_TO_RAD;
    /** A hand turns palm down from this height above the ground and is flat by the first (blocks). */
    private static final float PALM_NEAR=1.5F,PALM_FAR=8F;
    /** How far a free hand is turned from the captured pose toward its palm and toward its thumb (degrees). */
    private static final float WRIST_TOWARD_PALM=20,WRIST_TOWARD_THUMB=12;
    /** Where a reaching hand lands: ahead of and outside its shoulder, a palm's thickness up (blocks). */
    private static final float REACH_AHEAD=9F,REACH_OUT=1.5F,PALM_REST=1F;

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(eva instanceof EvaPrototypeEntity||eva.isNervLogisticsLocked()||eva.isFirstBattleActive())return;
        float prone=smooth(Math.max(eva.rifleProneBlend(partial),EvaFixedCannonBodyR55.applies(eva)?1F:0F));
        followArms(model);
        float fold=prone>.01F?fold(model)*smooth(prone/.15F):0;
        float cover=Math.max(COVER_TILT*fold,Mth.clamp((headTipBack(model)-COVER_FREE)*COVER_PER_DEGREE,0,COVER_MAX));
        if(cover>.5F)model.getBone("dorsal_cover").ifPresent(b->b.setRotX(b.getRotX()+cover*Mth.DEG_TO_RAD));
        if(fold>.01F)
            model.getBone("neck").ifPresent(b->{b.setPosY(b.getPosY()+NECK_REACH*fold);b.setPosZ(b.getPosZ()-NECK_DROP*fold);});
        if(eva.hasLiveActionForRender(partial)||eva.hasLegacyStrikeForRender()||eva.getOrdinaryAttackStage()>=0)return;
        int weapon=eva.getWeapon();
        boolean emptyLeft=weapon==EvaUnit01Entity.WEAPON_FISTS||weapon==EvaUnit01Entity.WEAPON_KNIFE;
        boolean emptyRight=weapon==EvaUnit01Entity.WEAPON_FISTS;
        if(prone>.01F&&root!=null)
        {
            // Going down, and getting up, the free hands reach for the ground
            // that will take the body's weight; they only turn palm down as
            // they arrive. Turning them by the prone progress alone bent the
            // wrists of arms still hanging at the sides.
            float raw=Math.max(eva.rifleProneBlend(partial),EvaFixedCannonBodyR55.applies(eva)?1F:0F);
            float reach=smooth((raw-.08F)/.3F)*(1-smooth((raw-.75F)/.22F));
            if(emptyLeft)plantHand(model,root,"l",reach,prone);
            if(emptyRight)plantHand(model,root,"r",reach,prone);
        }
        float crouch=smooth(eva.rifleCrouchBlend(partial))*(1-prone);
        if(crouch>.01F&&weapon==EvaUnit01Entity.WEAPON_FISTS)
            for(String side:new String[]{"l","r"})
                model.getBone("hand_"+side).ifPresent(b->EvaRigTransforms.rotate(b,
                        new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX()).slerp(new Quaternionf(),crouch)));
        float relaxed=(1-prone)*(1-crouch);
        if(emptyLeft)relaxWrist(model,"l",relaxed);
        if(emptyRight)relaxWrist(model,"r",relaxed);
    }

    /**
     * A free hand hangs relaxed: bent a little toward the palm and in line with the forearm. The
     * captured hands stood cocked back toward the knuckles and out to the side, and with the
     * fingers open the wrist read as broken. Measured in the game on the posed hand: +X bends
     * either hand toward its palm, and Z turns it toward the thumb (-Z on bone hand_r, +Z on
     * hand_l). The two hands mirror each other, so only Z changes sign.
     */
    private static void relaxWrist(BakedGeoModel model,String side,float weight)
    {
        if(weight<=.01F)return;
        model.getBone("hand_"+side).ifPresent(b->EvaRigTransforms.rotate(b,
                new Quaternionf().rotationZYX(b.getRotZ(),b.getRotY(),b.getRotX())
                        .rotateX(WRIST_TOWARD_PALM*Mth.DEG_TO_RAD*weight)
                        .rotateZ((side.equals("l")?1:-1)*WRIST_TOWARD_THUMB*Mth.DEG_TO_RAD*weight)));
    }

    private static void plantHand(BakedGeoModel model,Matrix4f root,String side,float reach,float prone)
    {
        var arm=model.getBone("arm_"+side).orElse(null);var forearm=model.getBone("forearm_"+side).orElse(null);
        var wrist=model.getBone("wrist_"+side).orElse(null);var hand=model.getBone("hand_"+side).orElse(null);
        if(arm==null||forearm==null||wrist==null||hand==null||hand.getParent()==null)return;
        float ground=root.m31();
        var shoulder=EvaRigTransforms.point(arm,EvaRigTransforms.pivot(arm),root);
        var palm=EvaRigTransforms.point(hand,EvaRigTransforms.pivot(hand),root);
        var forward=root.transformDirection(new Vector3f(0,0,-1));forward.y=0;
        // Model +X is the EVA's right.
        var outward=root.transformDirection(new Vector3f(side.equals("l")?-1:1,0,0));outward.y=0;
        if(forward.lengthSquared()<1e-6F||outward.lengthSquared()<1e-6F)return;
        forward.normalize();outward.normalize();
        var handWorld=EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(hand)));
        var fingers=new Vector3f(forward).mul((float)Math.cos(PALM_TURN)).fma((float)Math.sin(PALM_TURN),outward);
        // Bind: fingers along local -Y, the left palm faces local +X and the right palm local -X.
        Vector3f x=new Vector3f(0,side.equals("l")?-1:1,0),y=new Vector3f(fingers).negate(),z=new Vector3f(x).cross(y);
        var palmDown=new Quaternionf().setFromNormalized(new Matrix3f().setColumn(0,x).setColumn(1,y).setColumn(2,z));
        float near=1-smooth((palm.y-ground-PALM_NEAR)/(PALM_FAR-PALM_NEAR));
        var wanted=new Quaternionf(handWorld).slerp(palmDown,near*prone);
        var target=new Vector3f(shoulder.x,ground+PALM_REST,shoulder.z).fma(REACH_AHEAD,forward).fma(REACH_OUT,outward);
        // A hand reaches for ground its arm can reach. From a body still
        // standing, the solver pulled the straightened arms up and out
        // toward a ground far below: the shoulders shrugged on the way down.
        var elbow=EvaRigTransforms.point(forearm,EvaRigTransforms.elbow(forearm,side),root);
        float span=elbow.distance(shoulder)+palm.distance(elbow);
        reach*=smooth((span*1.05F-target.distance(shoulder))/(span*.35F));
        if(reach>.01F)
        {
            var goal=new Vector3f(palm).lerp(target,reach);
            // Elbows bend out and back, as hands do that catch the body.
            var pole=new Vector3f(outward).mul(.7F).fma(-.5F,forward).add(0,-.2F,0);
            EvaRigTransforms.solveArm(arm,forearm,wrist,hand,side,goal,wanted,pole,root);
            return;
        }
        var parent=EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(hand.getParent())));
        EvaRigTransforms.rotate(hand,parent.invert().mul(wanted));
    }

    /** Each pylon turns with its upper arm by {@link #PYLON_FOLLOW} of the arm's swing (its twist ignored). */
    private static void followArms(BakedGeoModel model)
    {
        var chest=model.getBone("torso_upper").orElse(null);
        if(chest==null||PYLON_FOLLOW<=0)return;
        var chestRotation=EvaRigTransforms.rotation(EvaRigTransforms.model(chest));
        for(String side:new String[]{"l","r"})
        {
            var arm=model.getBone("arm_"+side).orElse(null);var pylon=model.getBone("pylon_"+side).orElse(null);
            if(arm==null||pylon==null||pylon.getParent()!=chest)continue;
            var relative=new Quaternionf(chestRotation).invert().mul(EvaRigTransforms.rotation(EvaRigTransforms.model(arm)));
            // At rest the arm hangs along -Y.
            var swing=new Quaternionf().rotationTo(new Vector3f(0,-1,0),relative.transform(new Vector3f(0,-1,0)));
            var follow=new Quaternionf().slerp(swing,PYLON_FOLLOW);
            EvaRigTransforms.rotate(pylon,follow.mul(new Quaternionf().rotationZYX(pylon.getRotZ(),pylon.getRotY(),pylon.getRotX())));
        }
    }

    /** Degrees the helmet is tipped back from the chest, toward the dorsal cover. */
    private static float headTipBack(BakedGeoModel model)
    {
        var chest=model.getBone("torso_upper").orElse(null);var head=model.getBone("head").orElse(null);
        if(chest==null||head==null)return 0;
        var relative=new Quaternionf(EvaRigTransforms.rotation(EvaRigTransforms.model(chest))).invert()
                .mul(EvaRigTransforms.rotation(EvaRigTransforms.model(head)));
        // The helmet's up axis leans toward +Z (the back) as it tips back.
        var up=relative.transform(new Vector3f(0,1,0));
        return (float)Math.toDegrees(Math.atan2(up.z,up.y));
    }

    /**
     * How far the chest lies down: zero upright, squatting or kneeling tall,
     * one once it leans past {@link #FOLD_FULL}. Folding by the prone
     * progress swung the pylons back over a body still squatting upright.
     */
    private static float fold(BakedGeoModel model)
    {
        var chest=model.getBone("torso_upper").orElse(null);
        if(chest==null)return 0;
        var up=EvaRigTransforms.rotation(EvaRigTransforms.model(chest)).transform(new Vector3f(0,1,0));
        float tilt=(float)Math.toDegrees(Math.acos(Mth.clamp(up.y,-1,1)));
        return smooth((tilt-FOLD_FROM)/(FOLD_FULL-FOLD_FROM));
    }

    private static float smooth(float t)
    {
        t=Mth.clamp(t,0,1);
        return t*t*(3-2*t);
    }

    private EvaStanceFinishR56() {}
}

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
 * Lying flat turns the shoulder pylons and the dorsal cover from upright to
 * pointing past the raised helmet, hiding it and crowding its back: as the
 * chest goes down, fold them back flat over the shoulders and lift the
 * helmet clear of the collar (feet: {@link EvaGroundContactR56}). Free hands
 * reach for the ground on the way down and lie palm down on it; the captured
 * pose rolled them onto their edges with the wrist bent outward.
 * <p>
 * Crouched, empty hands hang in line with the forearm instead of turning
 * their palms back and out.
 */
final class EvaStanceFinishR56
{
    private static final float PYLON_TILT=Float.parseFloat(System.getProperty("projectseele.proneTiltR56","110"));
    /** Pylons also splay outward this far, opening the gap over the helmet. */
    private static final float PYLON_SPLAY=12;
    private static final float COVER_TILT=Float.parseFloat(System.getProperty("projectseele.proneCoverTiltR56","90"));
    /** The neck reaches this far along the chest (model pixels), lifting the helmet out of the collar. */
    private static final float NECK_REACH=2.5F,NECK_DROP=2.5F;
    /** Chest tilt from upright (degrees) from which the back folds, and by which it is folded. */
    private static final float FOLD_FROM=25,FOLD_FULL=70;
    /** A flat prone hand turns its fingers this far outward from the forearm. */
    private static final float PALM_TURN=10*Mth.DEG_TO_RAD;
    /** A hand turns palm down from this height above the ground and is flat by the first (blocks). */
    private static final float PALM_NEAR=1.5F,PALM_FAR=8F;
    /** Where a reaching hand lands: ahead of and outside its shoulder, a palm's thickness up (blocks). */
    private static final float REACH_AHEAD=9F,REACH_OUT=1.5F,PALM_REST=1F;

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(eva instanceof EvaPrototypeEntity||eva.isNervLogisticsLocked()||eva.isFirstBattleActive())return;
        float prone=smooth(Math.max(eva.rifleProneBlend(partial),EvaFixedCannonBodyR55.applies(eva)?1F:0F));
        float fold=prone>.01F?fold(model)*smooth(prone/.15F):0;
        if(fold>.01F)
        {
            float tilt=PYLON_TILT*Mth.DEG_TO_RAD*fold,splay=PYLON_SPLAY*Mth.DEG_TO_RAD*fold;
            model.getBone("pylon_l").ifPresent(b->{b.setRotX(b.getRotX()+tilt);b.setRotZ(b.getRotZ()+splay);});
            model.getBone("pylon_r").ifPresent(b->{b.setRotX(b.getRotX()+tilt);b.setRotZ(b.getRotZ()-splay);});
            model.getBone("dorsal_cover").ifPresent(b->b.setRotX(b.getRotX()+COVER_TILT*Mth.DEG_TO_RAD*fold));
            model.getBone("neck").ifPresent(b->{b.setPosY(b.getPosY()+NECK_REACH*fold);b.setPosZ(b.getPosZ()-NECK_DROP*fold);});
        }
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
        if(reach>.01F)
        {
            var target=new Vector3f(shoulder.x,ground+PALM_REST,shoulder.z).fma(REACH_AHEAD,forward).fma(REACH_OUT,outward);
            var goal=new Vector3f(palm).lerp(target,reach);
            // Elbows bend out and back, as hands do that catch the body.
            var pole=new Vector3f(outward).mul(.7F).fma(-.5F,forward).add(0,-.2F,0);
            EvaRigTransforms.solveArm(arm,forearm,wrist,hand,side,goal,wanted,pole,root);
            return;
        }
        var parent=EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(hand.getParent())));
        EvaRigTransforms.rotate(hand,parent.invert().mul(wanted));
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

package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.util.WeakIdentityMap;
import net.minecraft.util.Mth;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;

/**
 * Standing feet stay on the ground while the body turns above them, and step
 * round after it.
 * <p>
 * Turning on the spot used to carry the whole standing pose round like a
 * statue on a turntable, both soles skating over the road. Here each foot
 * holds its place and heading until the body has left it behind, then lifts
 * and sets down under the body again, one foot at a time. When the body has
 * stopped, one last step tidies the stance. Walking, kneeling and strikes own
 * their feet: this fades out for them.
 */
final class EvaTurnStepR59
{
    /** A foot steps once left this far behind (blocks) or turned this far from its leg (degrees). */
    private static final float STEP_AT=2.2F,STEP_TURN=20;
    /** With the body still for this long (seconds), a smaller leftover gets one tidying step. */
    private static final float TIDY_AT=.7F,TIDY_TURN=6,TIDY_AFTER=.2F;
    /** One step: its length in seconds and how high the foot lifts (blocks). */
    private static final float STEP_SECONDS=.5F,LIFT=2.4F;
    /** How fast the feet are taken over and handed back (1/s). */
    private static final float FADE_RATE=10F;
    /** A foot further than this from its place has been moved by something else (blocks). */
    private static final float LOST=12F;

    private static final class Foot
    {
        final Vector3f at=new Vector3f(),from=new Vector3f();
        float yaw,fromYaw,step=-1;
    }
    private static final class State
    {
        long time;float weight,still;boolean live;
        final Foot left=new Foot(),right=new Foot();
    }
    private static final WeakIdentityMap<EvaUnit01Entity,State> STATES=new WeakIdentityMap<>();

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(root==null)return;
        boolean standing=standing(eva,partial);
        var s=STATES.get(eva);
        if(s==null)
        {
            if(!standing)return;
            s=new State();STATES.put(eva,s);
        }
        var legL=model.getBone("leg_l").orElse(null);var shinL=model.getBone("shin_l").orElse(null);
        var ankleL=model.getBone("ankle_l").orElse(null);var footL=model.getBone("foot_l").orElse(null);
        var legR=model.getBone("leg_r").orElse(null);var shinR=model.getBone("shin_r").orElse(null);
        var ankleR=model.getBone("ankle_r").orElse(null);var footR=model.getBone("foot_r").orElse(null);
        if(legL==null||shinL==null||ankleL==null||footL==null||legR==null||shinR==null||ankleR==null||footR==null)return;
        long now=com.projectseele.client.AircraftRenderClockR21.frameNanos();
        boolean fresh=now!=s.time;
        float dt=fresh?Mth.clamp((now-s.time)/1e9F,0,.1F):0;
        s.time=now;
        if(fresh)s.weight+=((standing?1:0)-s.weight)*(1-(float)Math.exp(-dt*FADE_RATE));
        if(!standing&&s.weight<.01F){s.live=false;s.weight=0;s.left.step=s.right.step=-1;return;}
        float body=Mth.rotLerp(partial,eva.yBodyRotO,eva.yBodyRot);
        var worldL=new Matrix4f(root).mul(EvaRigTransforms.model(footL));var worldR=new Matrix4f(root).mul(EvaRigTransforms.model(footR));
        var restL=worldL.transformPosition(EvaRigTransforms.pivot(footL));var restR=worldR.transformPosition(EvaRigTransforms.pivot(footR));
        if(s.live&&(restL.distance(s.left.at)>LOST||restR.distance(s.right.at)>LOST))s.live=false;
        if(!s.live)
        {
            s.live=true;s.still=0;
            s.left.at.set(restL);s.right.at.set(restR);s.left.yaw=s.right.yaw=body;s.left.step=s.right.step=-1;
        }
        if(fresh)
        {
            s.still=Math.abs(Mth.wrapDegrees(eva.yBodyRot-eva.yBodyRotO))>.05F?0:s.still+dt;
            advance(s.left,restL,body,dt);advance(s.right,restR,body,dt);
            if(standing&&s.left.step<0&&s.right.step<0)chooseStep(s,restL,restR,body);
        }
        plant(s.left,restL,body,EvaRigTransforms.rotation(worldL),legL,shinL,ankleL,footL,root,s.weight);
        plant(s.right,restR,body,EvaRigTransforms.rotation(worldR),legR,shinR,ankleR,footR,root,s.weight);
    }

    private static void advance(Foot foot,Vector3f rest,float body,float dt)
    {
        if(foot.step<0)return;
        foot.step+=dt/STEP_SECONDS;
        if(foot.step>=1){foot.step=-1;foot.at.set(rest);foot.yaw=body;}
    }

    private static void chooseStep(State s,Vector3f restL,Vector3f restR,float body)
    {
        boolean tidy=s.still>TIDY_AFTER;
        float left=lag(s.left,restL,body,tidy),right=lag(s.right,restR,body,tidy);
        if(Math.max(left,right)<1)return;
        var foot=left>=right?s.left:s.right;
        foot.step=0;foot.from.set(foot.at);foot.fromYaw=foot.yaw;
    }

    /** How overdue a foot is for a step: 1 is due. */
    private static float lag(Foot foot,Vector3f rest,float body,boolean tidy)
    {
        float distance=(float)Math.hypot(rest.x-foot.at.x,rest.z-foot.at.z),turn=Math.abs(Mth.wrapDegrees(body-foot.yaw));
        return Math.max(distance/(tidy?TIDY_AT:STEP_AT),turn/(tidy?TIDY_TURN:STEP_TURN));
    }

    private static void plant(Foot foot,Vector3f rest,float body,Quaternionf restTurn,GeoBone leg,GeoBone shin,GeoBone ankle,GeoBone bone,Matrix4f root,float weight)
    {
        var target=new Vector3f();float yaw;
        if(foot.step>=0)
        {
            float t=foot.step*foot.step*(3-2*foot.step);
            target.set(foot.from).lerp(rest,t);
            target.y=rest.y+(foot.from.y-rest.y)*(1-t)+LIFT*Mth.sin(foot.step*Mth.PI);
            yaw=foot.fromYaw+Mth.wrapDegrees(body-foot.fromYaw)*t;
        }
        else
        {
            target.set(foot.at.x,rest.y,foot.at.z);
            yaw=foot.yaw;
        }
        // Minecraft yaw grows clockwise from above, world rotations the other way.
        var turn=new Quaternionf().rotationY(Mth.wrapDegrees(body-yaw)*Mth.DEG_TO_RAD).mul(restTurn);
        var hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);
        var knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
        EvaRigTransforms.solveLegFaded(leg,shin,ankle,bone,target,turn,knee.sub(hip),root,weight);
    }

    private static boolean standing(EvaUnit01Entity eva,float partial)
    {
        return EvaGroundContactR56.applies(eva)&&eva.rifleMoveBlend(partial)<.05F&&eva.rifleStanceLevel(partial)<.02F
                &&eva.getOrdinaryAttackStage()<0&&!eva.isHeavyMotionActive()&&!eva.isKickMotionActive(partial)
                &&!eva.hasLiveActionForRender(partial)&&!eva.hasLegacyStrikeForRender()
                &&!eva.fixedCannonOperatingR52()&&!eva.isBerserk();
    }

    private EvaTurnStepR59(){}
}

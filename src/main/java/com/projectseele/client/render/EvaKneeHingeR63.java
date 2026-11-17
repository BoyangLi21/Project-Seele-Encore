package com.projectseele.client.render;

import com.projectseele.entity.EvaUnit01Entity;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import software.bernie.geckolib.cache.object.BakedGeoModel;

/**
 * A knee is a hinge: it bends about one axis and nothing else.
 * <p>
 * The kick clips turn a shin sideways and about its own length as well: the supporting knee of
 * the heavy kick stood 12 degrees out to the side and the kicking knee 20, with 22 of twist, on
 * all three units. A shin that far off its hinge is solved again as a two-bone leg onto the same
 * foot, with the knee pointing where it pointed: the foot stays, the thigh takes up the turn and
 * the knee bends about its axis. Up to seven degrees nothing changes.
 * <p>
 * Strikes only (a climb or a roll sets its feet against the ledge or the ground itself). Standing
 * and walking legs come from the clips and from foot placement, whose own
 * solve already makes the knee a hinge; measured this way they read up to ten degrees off, and
 * solved again every frame they shook on a hillside (leg jitter up by a third, one knee flipped).
 */
final class EvaKneeHingeR63
{
    /** Off the hinge by less than the first (radians: seven degrees) a knee is left as it is; from the second (twelve) it is solved in full. */
    private static final float FROM=.122F,FULL=.209F;
    /** A knee nearer the line from hip to ankle than this share of its length is straight. */
    private static final float STRAIGHT=.05F;
    private static final boolean ENABLED=Boolean.parseBoolean(System.getProperty("projectseele.kneeHingeR63","true"));

    static void apply(EvaUnit01Entity eva,BakedGeoModel model,Matrix4f root,float partial)
    {
        if(!ENABLED||root==null||!eva.hasLiveActionForRender(partial)||com.projectseele.entity.EvaFieldActionsR45.active(eva))return;
        for(String side:new String[]{"l","r"})
        {
            var leg=model.getBone("leg_"+side).orElse(null);var shin=model.getBone("shin_"+side).orElse(null);
            var ankle=model.getBone("ankle_"+side).orElse(null);var foot=model.getBone("foot_"+side).orElse(null);
            if(leg==null||shin==null||ankle==null||foot==null)continue;
            var turn=new Quaternionf().rotationZYX(shin.getRotZ(),shin.getRotY(),shin.getRotX());
            // The part of the shin's turn about the hinge (its X axis), and what is left over.
            float length=(float)Math.sqrt(turn.x*turn.x+turn.w*turn.w);
            if(length<1e-6F)continue;
            var hinge=new Quaternionf(turn.x/length,0,0,turn.w/length);
            var rest=new Quaternionf(turn).mul(hinge.conjugate());
            float off=2*(float)Math.acos(Math.min(1,Math.abs(rest.w)));
            if(off<=FROM)continue;
            float t=Math.min(1,(off-FROM)/(FULL-FROM)),weight=t*t*(3-2*t);
            var target=EvaRigTransforms.point(foot,EvaRigTransforms.pivot(foot),root);
            var hip=EvaRigTransforms.point(leg,EvaRigTransforms.pivot(leg),root);
            var knee=EvaRigTransforms.point(leg,EvaRigTransforms.knee(shin),root);
            // A straight leg's knee lies on the line from hip to ankle and points nowhere.
            var along=new org.joml.Vector3f(target).sub(hip);
            float span=along.length();
            if(span<1e-3F)continue;
            var offLine=new org.joml.Vector3f(knee).sub(hip);
            offLine.fma(-offLine.dot(along)/(span*span),along);
            if(offLine.length()<STRAIGHT*span)continue;
            EvaRigTransforms.solveLegFaded(leg,shin,ankle,foot,target,
                    EvaRigTransforms.rotation(new Matrix4f(root).mul(EvaRigTransforms.model(foot))),knee.sub(hip),root,weight);
        }
    }

    private EvaKneeHingeR63() {}
}

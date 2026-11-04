package com.projectseele.entity;

import net.minecraft.util.Mth;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/**
 * Hand-set key poses played on a continuous timeline, and a two-bone reach
 * in pose space, shared by the jump and the ledge climb.
 * <p>
 * Key angles are GeckoLib local Euler degrees of this rig (model forward -Z,
 * the right side +X): torso X- bends forward, leg X+ raises the thigh, shin
 * X- bends the knee, arm X+ raises the arm forward, arm_r Z+ / arm_l Z-
 * raise it sideways, forearm X+ bends the elbow. Lift moves the pelvis
 * (model pixels) so a grounded key keeps its soles on the ground. Pose
 * space is in model units: five blocks each at the EVA's render scale.
 */
final class EvaKeyPosesR57
{
    static final String[] BONES={"torso_lower","torso_upper","neck","leg_l","leg_r","shin_l","shin_r",
            "foot_l","foot_r","arm_l","arm_r","forearm_l","forearm_r"};
    record Key(float[] degrees,float lift) {}
    static Key key(float lift,float... d){return new Key(d,lift);}

    /**
     * The pose at timeline position s, where key i sits at s=i and a null key
     * is the base pose. Keys are joined by Catmull-Rom curves, so the body
     * passes through each key without stopping on it. Bones a key does not
     * name, and the root's turn, keep the base.
     */
    static EvaBodyPose.Sample play(EvaBodyPose.Sample base,Key[] keys,float s)
    {
        var pose=EvaBodyPose.copy(base);
        s=Mth.clamp(s,0,keys.length-1);int i=Math.min(keys.length-2,(int)Math.floor(s));float t=s-i;
        Key k0=keys[Math.max(0,i-1)],k1=keys[i],k2=keys[i+1],k3=keys[Math.min(keys.length-1,i+2)];
        var euler=new Vector3f();
        for(int b=0;b<BONES.length;b++)
        {
            String name=BONES[b];var q=pose.rotations.get(name);if(q==null)continue;
            var own=base.rotations.get(name).getEulerAnglesZYX(euler);
            float[] v=new float[3];
            for(int axis=0;axis<3;axis++)
            {
                float rest=Mth.RAD_TO_DEG*(axis==0?own.x:axis==1?own.y:own.z);
                v[axis]=catmull(value(k0,b,axis,rest),value(k1,b,axis,rest),value(k2,b,axis,rest),value(k3,b,axis,rest),t)*Mth.DEG_TO_RAD;
            }
            q.rotationZYX(v[2],v[1],v[0]);
        }
        // The keys hold the root level; the base pose's own sway eases out
        // and back in along the timeline instead of switching at a key.
        var turn=pose.rotations.get("root");
        if(turn!=null)
        {
            var own=base.rotations.get("root").getEulerAnglesZYX(euler);
            float x=catmull(k0==null?own.x:0,k1==null?own.x:0,k2==null?own.x:0,k3==null?own.x:0,t);
            float y=catmull(k0==null?own.y:0,k1==null?own.y:0,k2==null?own.y:0,k3==null?own.y:0,t);
            float z=catmull(k0==null?own.z:0,k1==null?own.z:0,k2==null?own.z:0,k3==null?own.z:0,t);
            turn.rotationZYX(z,y,x);
        }
        var root=pose.positions.get("root");
        if(root!=null)root.y+=catmull(lift(k0),lift(k1),lift(k2),lift(k3),t)/16F;
        EvaBodyPose.preserveJointCentres(pose);
        return pose;
    }

    /**
     * Turn upper and lower so the end bone's pivot reaches target (pose
     * space), the middle joint bending towards pole. Weight 0 leaves the
     * pose, 1 reaches fully; out of reach, the limb points at the target.
     */
    static void reach(EvaBodyPose.Sample pose,String upper,String lower,String end,Vector3f target,Vector3f pole,float weight)
    {
        if(weight<=0||!pose.rig.containsKey(upper)||!pose.rig.containsKey(lower)||!pose.rig.containsKey(end))return;
        pose.dirty();
        var s=point(pose,upper);var e=point(pose,lower);var h=point(pose,end);
        float a=e.distance(s),b=h.distance(e);
        var toward=new Vector3f(target).sub(s);float d=toward.length();
        if(d<1e-5F||a<1e-5F||b<1e-5F)return;
        var dir=new Vector3f(toward).div(d);
        d=Mth.clamp(d,Math.abs(a-b)+1e-3F,a+b-1e-3F);
        float along=(a*a-b*b+d*d)/(2*d),height=(float)Math.sqrt(Math.max(0,a*a-along*along));
        var bend=new Vector3f(pole).sub(new Vector3f(dir).mul(pole.dot(dir)));
        if(bend.lengthSquared()<1e-8F)bend.set(0,0,-1).sub(new Vector3f(dir).mul(-dir.z));
        bend.normalize();
        var joint=new Vector3f(s).fma(along,dir).fma(height,bend);
        turn(pose,upper,new Vector3f(e).sub(s),new Vector3f(joint).sub(s),weight);
        pose.dirty();
        var e2=point(pose,lower);var h2=point(pose,end);
        var goal=new Vector3f(s).fma(d,dir);
        turn(pose,lower,new Vector3f(h2).sub(e2),goal.sub(e2),weight);
        EvaBodyPose.preserveJointCentres(pose);
    }
    /**
     * The two wrists brought to gap apart, about the point between where the
     * keys put them, elbows bent the way the keys bent them: clasped hands
     * stay clasped while interpolated keys swing the arms. Swinging from
     * overhead to the front the arms' Euler angles passed through poses that
     * spread the hands a body's width apart.
     */
    static void clasp(EvaBodyPose.Sample pose,float gap,float weight)
    {
        if(weight<=0||!pose.rig.containsKey("hand_l")||!pose.rig.containsKey("hand_r"))return;
        var l=point(pose,"hand_l");var r=point(pose,"hand_r");
        var middle=new Vector3f(l).add(r).mul(.5F);var across=new Vector3f(r).sub(l);
        if(across.lengthSquared()<1e-6F)across.set(1,0,0);
        across.normalize().mul(gap*.5F);
        for(String side:new String[]{"l","r"})
        {
            var bend=point(pose,"forearm_"+side).sub(point(pose,"arm_"+side));
            var target=side.equals("l")?new Vector3f(middle).sub(across):new Vector3f(middle).add(across);
            reach(pose,"arm_"+side,"forearm_"+side,"hand_"+side,target,bend,weight);
        }
    }
    /** Turn a bone so it lies level with the root (a foot set flat on a top), by weight. */
    static void level(EvaBodyPose.Sample pose,String name,float weight)
    {
        if(weight<=0||!pose.rig.containsKey(name))return;
        String parent=pose.rig.get(name).parent();
        var world=parent==null?new Quaternionf():pose.matrix(parent).getNormalizedRotation(new Quaternionf());
        var root=pose.matrix("root").getNormalizedRotation(new Quaternionf());
        pose.rotations.get(name).slerp(world.invert().mul(root),Mth.clamp(weight,0,1));
        pose.dirty();
    }
    private static Vector3f point(EvaBodyPose.Sample pose,String name)
    {return pose.matrix(name).transformPosition(new Vector3f(pose.rig.get(name).pivot()));}
    /** Rotate a bone in pose space so from turns onto to, as a local rotation under its parent. */
    private static void turn(EvaBodyPose.Sample pose,String name,Vector3f from,Vector3f to,float weight)
    {
        if(from.lengthSquared()<1e-10F||to.lengthSquared()<1e-10F)return;
        var delta=new Quaternionf().rotationTo(new Vector3f(from).normalize(),new Vector3f(to).normalize());
        String parent=pose.rig.get(name).parent();
        var world=parent==null?new Quaternionf():pose.matrix(parent).getNormalizedRotation(new Quaternionf());
        var local=pose.rotations.get(name);
        var turned=new Quaternionf(world).invert().mul(delta).mul(world).mul(local);
        local.slerp(turned,Mth.clamp(weight,0,1));
        pose.dirty();
    }

    private static float value(Key k,int bone,int axis,float rest){return k==null?rest:k.degrees()[bone*3+axis];}
    private static float lift(Key k){return k==null?0:k.lift();}
    private static float catmull(float p0,float p1,float p2,float p3,float t)
    {
        float t2=t*t,t3=t2*t;
        return .5F*(2*p1+(p2-p0)*t+(2*p0-5*p1+4*p2-p3)*t2+(3*p1-p0-3*p2+p3)*t3);
    }
    static float ease(float x){x=Mth.clamp(x,0,1);return x*x*(3-2*x);}
    static float out(float x){x=Mth.clamp(x,0,1);return 1-(1-x)*(1-x);}
    /** Piecewise-linear map of x through (xs[i], i). */
    static float stations(float x,float... xs)
    {
        if(x<=xs[0])return 0;
        for(int i=1;i<xs.length;i++)if(x<=xs[i])return i-1+(x-xs[i-1])/Math.max(1e-6F,xs[i]-xs[i-1]);
        return xs.length-1;
    }
    private EvaKeyPosesR57(){}
}

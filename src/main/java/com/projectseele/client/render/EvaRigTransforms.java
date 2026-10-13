package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import java.util.ArrayList;
import java.util.Collections;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.util.RenderUtils;

final class EvaRigTransforms
{
    static Vector3f pivot(GeoBone bone) { return new Vector3f(bone.getPivotX(),bone.getPivotY(),bone.getPivotZ()).div(16); }
    static Matrix4f model(GeoBone bone)
    {
        var chain=new ArrayList<GeoBone>();for(var b=bone;b!=null;b=b.getParent())chain.add(b);
        Collections.reverse(chain);var pose=new PoseStack();for(var b:chain)RenderUtils.prepMatrixForBone(pose,b);
        return new Matrix4f(pose.last().pose());
    }
    static Matrix4f model(GeoBone bone,GeoBone excludedAncestor)
    {
        var pose=new PoseStack();prepBelow(bone,excludedAncestor,pose);return new Matrix4f(pose.last().pose());
    }
    private static void prepBelow(GeoBone bone,GeoBone excludedAncestor,PoseStack pose)
    {
        if(bone==excludedAncestor)return;
        if(bone.getParent()!=null)prepBelow(bone.getParent(),excludedAncestor,pose);
        software.bernie.geckolib.util.RenderUtils.prepMatrixForBone(pose,bone);
    }
    static Matrix4f parent(GeoBone bone,Matrix4f root) { return bone.getParent()==null?new Matrix4f(root):new Matrix4f(root).mul(model(bone.getParent())); }
    static Quaternionf rotation(Matrix4f matrix) { return matrix.getUnnormalizedRotation(new Quaternionf()).normalize(); }
    static void rotate(GeoBone bone,Quaternionf q)
    {
        var a=EvaMotionEngineV2.motionQuaternionToAuthoredEuler(q);bone.setRotX(a.x);bone.setRotY(a.y);bone.setRotZ(a.z);
    }
    static Vector3f point(GeoBone bone,Vector3f point,Matrix4f root) { return new Matrix4f(root).mul(model(bone)).transformPosition(new Vector3f(point)); }
    static Vector3f elbow(String side) { return new Vector3f(side.equals("l")?-23.489652F:23.489652F,123.435069F,7.737214F).div(16); }
    static Vector3f elbow(GeoBone lower,String side)
    {for(var child:lower.getChildBones())if(child.getName().equals("r30_elbow_socket_"+side))return pivot(child);return elbow(side);}
    static Vector3f knee(GeoBone lower)
    {for(var child:lower.getChildBones())if(child.getName().startsWith("r30_knee_socket_"))return pivot(child);return pivot(lower).add(0,11.4F/16,0);}
    static void hinge(GeoBone bone,Vector3f centre)
    {
        var delta=new Vector3f(centre).sub(pivot(bone));var q=new Quaternionf().rotationZYX(bone.getRotZ(),bone.getRotY(),bone.getRotX());
        var offset=new Vector3f(delta).sub(q.transform(new Vector3f(delta)));
        bone.setPosX(-offset.x*16);bone.setPosY(offset.y*16);bone.setPosZ(offset.z*16);
    }
    private static Matrix3f frame(Vector3f direction,Vector3f axis)
    {
        var y=new Vector3f(direction).normalize();var x=new Vector3f(axis).sub(new Vector3f(y).mul(axis.dot(y))).normalize();
        return new Matrix3f().setColumn(0,x).setColumn(1,y).setColumn(2,new Vector3f(x).cross(y));
    }
    private static void orient(GeoBone bone,Vector3f rest,Vector3f direction,Vector3f hingeAxis,Matrix4f root)
    {orient(bone,rest,direction,hingeAxis,new Vector3f(1,0,0),root);}
    private static void orient(GeoBone bone,Vector3f rest,Vector3f direction,Vector3f hingeAxis,Vector3f restAxis,Matrix4f root)
    {
        var q=new Quaternionf().setFromNormalized(frame(direction,hingeAxis).mul(frame(rest,restAxis).transpose()));
        rotate(bone,rotation(parent(bone,root)).invert().mul(q));
    }
    static double solveArm(GeoBone upper,GeoBone lower,GeoBone wrist,GeoBone hand,String side,
                           Vector3f target,Quaternionf handRotation,Vector3f pole,Matrix4f root)
    {
        boolean anatomical=lower.getChildBones().stream().anyMatch(b->b.getName().equals("r30_elbow_socket_"+side));
        return solveChain(upper,lower,wrist,hand,elbow(lower,side),target,handRotation,pole,root,anatomical);
    }
    static double solveLeg(GeoBone upper,GeoBone lower,GeoBone ankle,GeoBone foot,Vector3f target,Quaternionf rotation,Vector3f pole,Matrix4f root)
    {
        return solveChain(upper,lower,ankle,foot,knee(lower),target,rotation,pole,root);
    }
    static double solveGenericArm(GeoBone upper,GeoBone lower,GeoBone hand,Vector3f target,Quaternionf rotation,Vector3f pole,Matrix4f root)
    {return solveChain(upper,lower,hand,hand,pivot(lower),target,rotation,pole,root);}
    private static double solveChain(GeoBone upper,GeoBone lower,GeoBone wrist,GeoBone hand,Vector3f centre,Vector3f target,Quaternionf handRotation,Vector3f pole,Matrix4f root)
    {return solveChain(upper,lower,wrist,hand,centre,target,handRotation,pole,root,false);}
    private static double solveChain(GeoBone upper,GeoBone lower,GeoBone wrist,GeoBone hand,Vector3f centre,Vector3f target,Quaternionf handRotation,Vector3f pole,Matrix4f root,boolean anatomical)
    {
        var shoulder=point(upper,pivot(upper),root);
        float scale=root.getScale(new Vector3f()).y;var u=new Vector3f(centre).sub(pivot(upper));var v=pivot(hand).sub(centre);
        float a=u.length()*scale,b=v.length()*scale;var direction=new Vector3f(target).sub(shoulder);float length=direction.length();
        if(length<1e-6F)direction.set(0,-1,0);else direction.div(length);
        float distance=Math.max(Math.abs(a-b)+.001F,Math.min(a+b-.001F,length));
        float along=(a*a-b*b+distance*distance)/(2*distance),height=(float)Math.sqrt(Math.max(0,a*a-along*along));
        var bend=new Vector3f(pole).sub(new Vector3f(direction).mul(pole.dot(direction)));
        if(bend.lengthSquared()<1e-8F)bend.set(0,0,1).sub(new Vector3f(direction).mul(direction.z));
        bend.normalize();var joint=new Vector3f(shoulder).fma(along,direction).fma(height,bend);
        var du=new Vector3f(joint).sub(shoulder);var dl=new Vector3f(target).sub(joint);var axis=new Vector3f(du).cross(dl);
        if(axis.lengthSquared()<1e-8F)axis.set(du).cross(bend);
        axis.normalize();Vector3f restAxis=new Vector3f(1,0,0);
        if(anatomical)
        {
            // The UN bind elbow bends in its measured XY plane, whose normal
            // is Z, unlike the older rig's X-axis elbow. Using dot(axis, X)
            // there is mathematically zero: a two-degree dormant torso tilt
            // flips its floating-point sign and spins both arms by 180 degrees.
            restAxis.set(u).cross(v);
            if(restAxis.lengthSquared()<1e-8F)restAxis.set(u).cross(new Vector3f(0,0,1));
            restAxis.normalize();
        }
        var localSide=rotation(new Matrix4f(root).mul(model(upper))).transform(new Vector3f(restAxis));if(axis.dot(localSide)<0)axis.negate();
        for(var bone:new GeoBone[]{lower,wrist,hand}){bone.setPosX(0);bone.setPosY(0);bone.setPosZ(0);}
        wrist.setRotX(0);wrist.setRotY(0);wrist.setRotZ(0);
        orient(upper,u,du,axis,restAxis,root);var actual=parent(lower,root).transformPosition(new Vector3f(centre));
        orient(lower,v,new Vector3f(target).sub(actual),axis,restAxis,root);hinge(lower,centre);
        rotate(hand,rotation(parent(hand,root)).invert().mul(handRotation));
        return point(hand,pivot(hand),root).distance(target);
    }
}

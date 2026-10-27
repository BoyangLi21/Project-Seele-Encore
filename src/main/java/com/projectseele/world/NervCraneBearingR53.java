package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Split replaceable shoes bridge the measured gap to the capsule's cylindrical tail.
 * The imported clamp, its hinges and all source surfaces remain unchanged. */
public final class NervCraneBearingR53
{
    public static final double WINCH_DECK=6;
    private static final Map<String,double[]> PARTS=Map.of(
        "body",sector(55,125),"jaw_left",sector(190,245),"jaw_right",sector(-65,-10));
    public static Set<String> names(){return PARTS.keySet();}
    public static double[] triangles(String part)
    {var value=PARTS.get(part);if(value==null)throw new IllegalArgumentException("Unknown bearing shoe");return value.clone();}

    /** The capsule rotates inside the split bearing; the suspended clamp retains
     * its transverse runway orientation. Projection is bounded on the authored plane. */
    public static NervCranePoseR52.Pose pose(NervCranePoseR52.State state,Vec3 mount)
    {
        var plug=state.plug();var reference=state.referenceRotation();
        if(plug!=null)
        {
            var local=state.machine().inverse().compose(plug);var aligned=axisFrame(local);
            plug=state.machine().compose(new RigidTransform(local.translation(),aligned.qx(),aligned.qy(),aligned.qz(),aligned.qw()));
        }
        if(reference!=null)
        {
            var local=state.machine().inverse().compose(RigidTransform.of(state.referenceWorld(),reference));
            reference=state.machine().compose(axisFrame(local)).rotation();
        }
        return NervCranePoseR52.evaluate(state.machine(),state.bottom(),plug,state.coupled(),state.referenceWorld(),reference,mount);
    }
    private static RigidTransform axisFrame(RigidTransform local)
    {
        var z=local.transformVector(new Vec3(0,0,1)).normalize();var projection=new Vec3(1,0,0).subtract(z.scale(z.x));
        if(projection.length()<.99)throw new IllegalArgumentException("Bearing motion left the surveyed insertion plane");
        var x=projection.normalize();return RigidTransform.fromAxes(Vec3.ZERO,x,z.cross(x).normalize(),z);
    }
    private static double[] sector(double start,double end)
    {
        var xyz=new ArrayList<Double>();int steps=(int)Math.ceil((end-start)/5);
        for(int i=0;i<steps;i++)
        {
            double a=Math.toRadians(start+(end-start)*i/steps),b=Math.toRadians(start+(end-start)*(i+1)/steps);
            var p=point(.77,a,-.6);var q=point(.77,b,-.6);var r=point(1.38,b,-.6);var s=point(1.38,a,-.6);
            var P=p.add(0,0,.38);var Q=q.add(0,0,.38);var R=r.add(0,0,.38);var S=s.add(0,0,.38);
            quad(xyz,p,P,Q,q);quad(xyz,s,r,R,S);quad(xyz,p,q,r,s);quad(xyz,P,S,R,Q);
            if(i==0)quad(xyz,p,s,S,P);if(i==steps-1)quad(xyz,q,Q,R,r);
        }
        return xyz.stream().mapToDouble(Double::doubleValue).toArray();
    }
    private static Vec3 point(double r,double a,double z){return new Vec3(r*Math.cos(a),r*Math.sin(a),z);}
    private static void quad(List<Double> values,Vec3 a,Vec3 b,Vec3 c,Vec3 d)
    {for(var p:List.of(a,b,c,a,c,d)){values.add(p.x);values.add(p.y);values.add(p.z);}}
    private NervCraneBearingR53(){}
}

package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Replaceable bearing shoes for the unchanged imported clamp, review only. */
final class CandidateCraneSleevesR53
{
    static Map<String,double[]> parts()
    {
        return Map.of("body",sector(55,125),"jaw_left",sector(190,245),"jaw_right",sector(-65,-10));
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
}

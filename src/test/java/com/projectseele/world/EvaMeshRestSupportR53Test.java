package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

public final class EvaMeshRestSupportR53Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static EvaOriginalMeshGeometryR52.Geometry source(double[] vertices)
    {
        AABB bounds=null;
        for(int i=0;i<vertices.length;i+=3){var p=new Vec3(vertices[i],vertices[i+1],vertices[i+2]);var b=new AABB(p,p);bounds=bounds==null?b:bounds.minmax(b);}
        return new EvaOriginalMeshGeometryR52.Geometry(2,"synthetic",List.of(new EvaOriginalMeshGeometryR52.Part("forearm_r","synthetic","synthetic",vertices,bounds)));
    }
    public static void main(String[] args)
    {
        var seam=source(new double[]{0,-.583,0,1,-.583,0,0,-.583,1});
        var floor=new AABB(-2,-1,-2,2,0,2);var result=EvaMeshRestSupportR53.solve(seam,RigidTransform.identity(),List.of(floor),.025);
        check(Math.abs(result.lift()-.608)<1e-10,"Skin below proxy is raised to native top plus existing gap");
        check(Math.abs(result.bounds().minY-.025)<1e-10,"Saved bounds include corrected actual seam");
        var slope=source(new double[]{0,-2,0,2,0,0,0,0,2});
        var narrow=new AABB(.75,-1,.75,1,0,1);
        var interior=EvaMeshRestSupportR53.solve(slope,RigidTransform.identity(),List.of(narrow),.025);
        check(Math.abs(interior.lift()-.525)<1e-10,"Triangle interior above a small support is checked without requiring a vertex on it");
        check(interior.bounds().minY< -1,"Lowest source corner over empty space does not lift the entire hull to that height");
        check(EvaMeshRestSupportR53.solve(slope,RigidTransform.identity(),List.of(new AABB(1.5,-1,1.5,2,0,2)),.025).lift()==0,"Empty triangle-AABB corner is not a support");
        check(EvaMeshRestSupportR53.solve(seam,RigidTransform.identity(),List.of(),.025).lift()==0,"No native support cannot invent a surface");
        var root=new RigidTransform(new Vec3(72,81.025,297),0,1,0,0);
        var moved=EvaMeshRestSupportR53.solve(seam,root,List.of(new AABB(70,80,295,74,81,299)),.025);
        check(Math.abs(moved.lift()-.583)<1e-6,"Actual world root and yaw preserve ground deficit");
        check(EvaMeshRestSupportR53.solve(seam,RigidTransform.identity(),List.of(floor,floor),.025).lift()==result.lift(),"Duplicate native shapes do not accumulate lift");
        System.out.println("R53 actual-skin rest support PASS checks="+checks+"; pure support geometry, no world mutation");
    }
}

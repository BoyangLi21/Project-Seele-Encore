package com.projectseele.world;

import net.minecraft.world.phys.Vec3;
import org.joml.Quaternionf;

public final class NervRigidPairMemoR53Test
{
    private static int checks;
    private static void check(boolean b,String message){checks++;if(!b)throw new AssertionError(message);}
    private static RigidTransform frame(double x,double y,double z)
    {return new RigidTransform(new Vec3(x,y,z),0,0,0,1);}
    public static void main(String[] args)
    {
        var triangles=new double[]{0,0,0,1,0,0,0,1,0};
        var a=new NervRigidMeshSweepR52(triangles);var b=new NervRigidMeshSweepR52(triangles);
        var memo=new NervRigidPairMemoR53(3);var query=new NervRigidMeshSweepR52.PairQuery();
        var zero=frame(0,0,0);var pad=new Vec3(.0001,.0001,.0001);
        check(!memo.intersects(a,frame(0,0,2),frame(0,0,2),b,zero,zero,.003,pad,query),"Separated source members");
        long count=memo.evaluations();
        check(!memo.intersects(a,frame(72,-930,177),frame(72,-900,177),b,frame(72,-930,175),frame(72,-900,175),.003,pad,query),"Common translation preserves clear result");
        check(memo.evaluations()==count,"Identical relative motion reuses completed source result");
        check(memo.intersects(a,frame(0,0,-1),frame(0,0,1),b,zero,zero,.003,pad,query),"New intermediate collision remains checked");
        check(memo.intersects(a,zero,zero,b,zero,zero,.003,pad,query),"Changed relative pose reaches real contact");
        count=memo.evaluations();
        memo.intersects(new NervRigidMeshSweepR52(triangles),zero,zero,b,zero,zero,.003,pad,query);
        check(memo.evaluations()==count+1,"Changed source identity invalidates result");
        count=memo.evaluations();memo.intersects(a,zero,zero,b,zero,zero,.003,new Vec3(.002,.002,.002),query);
        check(memo.evaluations()==count+1,"Changed outward error invalidates result");
        var turn=RigidTransform.of(Vec3.ZERO,new Quaternionf().rotateY(.1f));
        count=memo.evaluations();memo.intersects(a,zero,turn,b,zero,zero,.003,pad,query);
        check(memo.evaluations()==count+1,"Changed rotation invalidates result");
        check(memo.size()==3,"Source result memory remains bounded");
        System.out.println("NervRigidPairMemoR53 PASS "+checks);
    }
}

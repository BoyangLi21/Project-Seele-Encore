package com.projectseele.world;
import net.minecraft.world.phys.Vec3;

public final class NervRigidPairSweepR52Test
{
    private static int checks;
    private static void check(boolean b,String text){checks++;if(!b)throw new AssertionError(text);}
    public static void main(String[] args)
    {
        var a=new NervRigidMeshSweepR52(new double[]{0,0,0,10,0,0,0,10,0});var b=new NervRigidMeshSweepR52(new double[]{9,9,-1,9.1,9,1,9,9.1,1});var id=RigidTransform.identity();
        check(a.bounds().intersects(b.bounds()),"Empty triangle corner is inside both broad BVH boxes");check(!a.intersects(id,id,b,id,id,.005,Vec3.ZERO),"Actual paired triangle SAT permits that empty corner");
        a=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});b=new NervRigidMeshSweepR52(new double[]{5,.1,-1,5,.1,1,5,.9,0});var end=new RigidTransform(new Vec3(10,0,0),0,0,0,1);
        check(!a.intersects(id,id,b,id,id,.005,Vec3.ZERO)&&!a.intersects(end,end,b,id,id,.005,Vec3.ZERO),"Both actual stopped mesh pairs are separated");check(a.intersects(id,end,b,id,id,.005,Vec3.ZERO),"Same-time continuous real triangle chord detects the collision between stopped endpoints");
        Vec3[] stopped={new Vec3(5,.1,-1),new Vec3(5,.1,1),new Vec3(5,.9,0),new Vec3(5,.1,-1),new Vec3(5,.1,1),new Vec3(5,.9,0)};check(!a.intersectsChord(stopped,Vec3.ZERO,id)&&!a.intersectsChord(stopped,Vec3.ZERO,end),"A moving external source mesh is clear at both endpoint samples");check(a.intersectsChord(stopped,Vec3.ZERO,id,end),"Moving external source cannot disappear between two clear endpoint samples");
        System.out.println("PASS R52 paired actual triangle BVH/chord checks: "+checks);
    }
}

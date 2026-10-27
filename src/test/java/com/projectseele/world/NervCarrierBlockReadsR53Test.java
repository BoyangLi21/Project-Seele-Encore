package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

public final class NervCarrierBlockReadsR53Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static NervOriginalCarrierR52.Part part(String name,NervRigidMeshSweepR52 mesh,RigidTransform frame)
    {return new NervOriginalCarrierR52.Part(name,NervOriginalCarrierR52.Role.STRUCTURE,mesh,frame);}
    private static void liveBlockSemantics()
    {
        var mesh=new NervRigidMeshSweepR52(new double[]{0,0,0,1,0,0,0,1,0});
        var start=RigidTransform.identity();var end=new RigidTransform(new Vec3(10,0,0),0,0,0,1);
        var first=new ArrayList<NervOriginalCarrierR52.Part>();var last=new ArrayList<NervOriginalCarrierR52.Part>();
        for(int i=0;i<100;i++){first.add(part("member/"+i,mesh,start));last.add(part("member/"+i,mesh,end));}
        int[] reads={0};var obstacles=new ArrayList<AABB>();
        java.util.function.Function<AABB,List<AABB>> reader=box->{reads[0]++;return List.copyOf(obstacles);};
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(first,last,0,box->true,reader)==null,"Empty live world clears");
        check(reads[0]==1,"Coincident source members must share one native read");
        var middle=new AABB(5,.1,-.1,5.2,.7,.1);obstacles.add(middle);
        check(!mesh.intersects(start,start,middle,.003)&&!mesh.intersects(end,end,middle,.003),"Middle blocker is clear at both endpoints");
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(first,last,0,box->true,reader)!=null,"A new live blocker between endpoints must reject the next call");
        obstacles.clear();
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(first,last,0,box->true,reader)==null,"Removed obstacles must not survive into another call");
        reads[0]=0;
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(first,last,0,box->false,reader)!=null&&reads[0]==0,"Unloaded source area cannot authorize motion or trigger loading");
        var triangle=new NervRigidMeshSweepR52(new double[]{0,0,0,10,0,0,0,10,0});
        obstacles.add(new AABB(8,8,-1,9,9,1));
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(List.of(part("triangle",triangle,start)),List.of(part("triangle",triangle,start)),0,box->true,reader)==null,"A merged bounding box must not turn an empty triangle corner into a collision");
        obstacles.clear();
        var left=new RigidTransform(new Vec3(-2,0,0),0,0,0,1);var right=new RigidTransform(new Vec3(1,0,0),0,0,0,1);
        var split=List.of(part("left",mesh,left),part("right",mesh,right));reads[0]=0;
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(split,split,0,box->!(box.minX<0&&box.maxX>0),reader)==null&&reads[0]==2,"An unreadable merged gap falls back to each readable original volume");
    }
    private static void wholeAssemblySemantics()
    {
        var volume=new AABB(0,0,0,10,10,10);
        var obstacle=new AABB(5,2,2,6,3,3);
        var pieces=Collections.nCopies(100,volume);
        int[] reads={0},checksOfSource={0};
        var live=new ArrayList<AABB>();live.add(obstacle);live.add(obstacle);
        java.util.function.Function<AABB,List<AABB>> reader=b->{reads[0]++;return List.copyOf(live);};
        var clear=BoundedNativeCollisionGroupsR52.clearWholeSource(pieces,b->true,reader,b->{checksOfSource[0]++;return false;});
        check(clear.clear()&&reads[0]==1&&checksOfSource[0]==1,"Complete-source queries visit a repeated live obstacle once, regardless of source part count");
        check(!BoundedNativeCollisionGroupsR52.clearWholeSource(pieces,b->true,reader,b->b.intersects(obstacle)).clear(),"Complete-source collision still rejects motion");
        live.clear();
        check(BoundedNativeCollisionGroupsR52.clearWholeSource(pieces,b->true,reader,b->true).clear(),"A removed obstacle is not cached into the next tick");
        var left=new AABB(-2,0,0,-1,1,1);var right=new AABB(1,0,0,2,1,1);reads[0]=0;
        check(BoundedNativeCollisionGroupsR52.clearWholeSource(List.of(left,right),b->!(b.minX<0&&b.maxX>0),reader,b->true).clear()&&reads[0]==2,"An unreadable merged gap reads only the original two volumes");
        reads[0]=0;
        check(!BoundedNativeCollisionGroupsR52.clearWholeSource(pieces,b->false,reader,b->false).clear()&&reads[0]==0,"Unreadable original geometry cannot authorize movement or force native reads");
    }
    public static void main(String[] args)throws Exception
    {
        wholeAssemblySemantics();
        if(args.length>0&&args[0].equals("--whole-source")){System.out.println("Whole assembly native block sweep: "+checks+" checks passed");return;}
        liveBlockSemantics();
        for(int unit=0;unit<3;unit++)
        {
            var root=new RigidTransform(new Vec3(72.5-42*unit,-1062,328.5),0,1,0,0);
            var a=NervOriginalCarrierR52.partsAtR52(unit,root,.91F,new Vec3(0,1,0));
            var b=NervOriginalCarrierR52.partsAtR52(unit,root,.92F,new Vec3(0,1,0));
            var boxes=new ArrayList<AABB>();long maximum=0;String largest="";
            for(int i=0;i<a.size();i++)
            {
                var p=a.get(i);var q=b.get(i);var box=p.mesh().envelope(p.frame(),q.frame()).inflate(.00102);
                boxes.add(box);long cost=BoundedNativeCollisionGroupsR52.voxelEstimate(box);
                if(cost>maximum){maximum=cost;largest=p.name()+" "+box;}
            }
            var plan=BoundedNativeCollisionGroupsR52.plan(boxes);
            check(plan.groupedCellEstimate()<plan.originalCellEstimate(),"Measured original carrier must reduce repeated native cursor reads");
            for(double t:new double[]{.25,.5,.75})
            {
                var actual=NervOriginalCarrierR52.partsAtR52(unit,root,(float)(.91F+(.92F-.91F)*t),new Vec3(0,1,0));
                for(int i=0;i<a.size();i++)
                {
                    var expected=a.get(i).frame().interpolate(b.get(i).frame(),t);
                    check(actual.get(i).mesh()==a.get(i).mesh()&&actual.get(i).name().equals(a.get(i).name()),"Actual carrier rise retains source topology");
                    check(actual.get(i).frame().translation().distanceTo(expected.translation())<.00001&&actual.get(i).frame().rotationErrorDegrees(expected)<.00001,"Every actual member follows the complete affine rise used by the block proof");
                }
            }
            System.out.println("unit="+unit+" parts="+a.size()+" groups="+plan.groups().size()+" original="+plan.originalCellEstimate()+" grouped="+plan.groupedCellEstimate()+" maximum="+maximum+" largest="+largest);
        }
        System.out.println("Carrier native block sweep: "+checks+" checks passed");
    }
}

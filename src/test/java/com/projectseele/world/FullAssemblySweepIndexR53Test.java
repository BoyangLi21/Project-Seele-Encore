package com.projectseele.world;

import java.lang.reflect.*;
import java.util.*;
import net.minecraft.world.phys.*;

/** Compare indexed source clearance with an exhaustive source/pilot oracle. */
public final class FullAssemblySweepIndexR53Test
{
    private static int checks;
    private static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    private static double[] box(AABB b)
    {
        var p=new Vec3[8];for(int i=0;i<8;i++)p[i]=new Vec3((i&1)==0?b.minX:b.maxX,(i&2)==0?b.minY:b.maxY,(i&4)==0?b.minZ:b.maxZ);
        int[][] faces={{0,1,3,2},{4,6,7,5},{0,4,5,1},{2,3,7,6},{0,2,6,4},{1,5,7,3}};var result=new double[108];int n=0;
        for(var f:faces)for(int i:new int[]{f[0],f[1],f[2],f[0],f[2],f[3]}){result[n++]=p[i].x;result[n++]=p[i].y;result[n++]=p[i].z;}return result;
    }
    private static Object create(String name,Object... args)throws Exception
    {
        var constructor=Class.forName("com.projectseele.world.FullAssemblyGeometryR52$"+name).getDeclaredConstructors()[0];constructor.setAccessible(true);return constructor.newInstance(args);
    }
    private static List<AABB> pilot(List<DirectoryTrajectoryR52> paths,Vec3 seat,Vec3 half)
    {
        var boxes=new ArrayList<AABB>();for(var path:paths){double radius=seat.distanceTo(path.footCentreLocal());int n=path.divisions(radius,.005);double error=path.error(radius,n);
            for(int i=0;i<n;i++){var a=path.sample((double)i/n).evaRoot().transformPoint(seat);var b=path.sample((double)(i+1)/n).evaRoot().transformPoint(seat);boxes.add(new AABB(a.subtract(half),a.add(half)).minmax(new AABB(b.subtract(half),b.add(half))).inflate(error));}}return boxes;
    }
    public static void main(String[] args)throws Exception
    {
        var json=NervRouteCoreR52Test.rootFixtureForNativeBindingTest();var directory=NervRouteDirectoryR52.parse(json);
        var binding=new FootSupportFrameR52.Binding(new Vec3(-1,-2,1),new Vec3(1,-2,1),RigidTransform.identity());
        var paths=new ArrayList<DirectoryTrajectoryR52>();for(int i=0;i<24;i++)paths.add(new DirectoryTrajectoryR52(directory,directory.leg("original1"),binding,i/24D,(i+1)/24D));
        var meshes=new ArrayList<TriangleSweepMeshR52>();var surfaces=new ArrayList<Object>();
        for(int i=0;i<12;i++){var mesh=new TriangleSweepMeshR52(box(new AABB(i*8-40,-.5,-.5,i*8-39,.5,.5)));meshes.add(mesh);surfaces.add(create("Surface","fixture/"+i,"fixture",mesh));}
        var seat=new Vec3(0,4,0);var half=new Vec3(.3,.9,.3);var captured=(FullAssemblyGeometryR52.Captured)create("Captured",null,binding,surfaces,create("NativePilot",UUID.randomUUID(),half,seat),"fixture",TransportMembershipR52.Kind.OCCUPIED);
        var indexed=captured.sweep(paths,.005);Method test=indexed.getClass().getDeclaredMethod("intersects",AABB.class);test.setAccessible(true);
        var exhaustive=new ArrayList<TriangleSweepMeshR52.PreparedSweep>();for(var path:paths)for(var mesh:meshes)exhaustive.add(mesh.prepare(path,.005));var pilots=pilot(paths,seat,half);
        var random=new Random(530040);var obstacles=new ArrayList<AABB>();var start=paths.get(0).sample(0).evaRoot().translation();
        for(int i=0;i<1600;i++){var at=start.add(random.nextDouble()*140-70,random.nextDouble()*20-8,random.nextDouble()*60-15);obstacles.add(new AABB(at,at.add(.1+random.nextDouble(),.1+random.nextDouble(),.1+random.nextDouble())));}
        for(var path:paths){var at=path.sample(.5).evaRoot().transformPoint(new Vec3(-39.5,0,0));obstacles.add(new AABB(at.add(-.05,-.05,-.05),at.add(.05,.05,.05)));var rider=path.sample(.5).evaRoot().transformPoint(seat);obstacles.add(new AABB(rider.add(-.05,-.05,-.05),rider.add(.05,.05,.05)));}
        int hits=0;for(var obstacle:obstacles){boolean expected=exhaustive.stream().anyMatch(mesh->mesh.intersects(obstacle))||pilots.stream().anyMatch(body->body.intersects(obstacle));boolean actual=(Boolean)test.invoke(indexed,obstacle);check(actual==expected,"Indexed sweep differs from exhaustive geometry at "+obstacle);if(actual)hits++;}
        check(hits>=48,"Surface and seated-pilot intrusions were not represented");
        Method paired=indexed.getClass().getDeclaredMethod("intersects",NervFlightProofR52.ObstacleMesh.class);paired.setAccessible(true);
        for(int i=0;i<120;i++){var obstacle=obstacles.get(i<72?i:obstacles.size()-1-(i-72));var rigid=new NervRigidMeshSweepR52(box(obstacle));var frame=RigidTransform.identity();
            boolean expected=exhaustive.stream().anyMatch(mesh->mesh.intersects(rigid,frame,frame))||pilots.stream().anyMatch(body->rigid.intersects(frame,frame,body,.005));
            check((Boolean)paired.invoke(indexed,new NervFlightProofR52.ObstacleMesh(rigid,frame))==expected,"Indexed native actor mesh differs from exhaustive geometry");}
        // A fresh obstacle is checked on every call; the index only holds source bounds.
        var far=new AABB(10000,10000,10000,10001,10001,10001);for(int i=0;i<80;i++){check(!(Boolean)test.invoke(indexed,far),"Distant block entered source bounds");check((Boolean)test.invoke(indexed,obstacles.get(obstacles.size()-1)),"Live pilot intrusion was cached away");}
        System.out.println("Full assembly indexed/exhaustive clearance PASS checks="+checks);
    }
}

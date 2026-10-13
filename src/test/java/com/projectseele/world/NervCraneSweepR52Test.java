package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Actual full source mesh negative tests: middle-curve obstacles and true
 * rolling-floor contact; no world fixture or native acceptance. */
public final class NervCraneSweepR52Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    public static void main(String[] args)throws Exception
    {
        var geometry=NervCraneGeometryR52.loadClasspath();var sweep=new NervCraneSweepR52(geometry);
        for(float yaw:new float[]{0,(float)Math.PI,.73F})
        {
            var machine=RigidTransform.of(new Vec3(12.5,-609.25,317.5),new Quaternionf().rotationY(yaw));var plug=RigidTransform.of(machine.translation().add(0,-28.25,3.75),new Quaternionf().rotationZYX(.19F,.63F,-.21F));
            var eye=plug.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P);var from=new NervCranePoseR52.State(machine,-24,null,false,eye,plug.rotation());var to=new NervCranePoseR52.State(machine,-23.5,null,false,eye,plug.rotation());var curve=sweep.between(from,to);check(curve.names().size()==19,"Missing actual rig part");
            for(String name:curve.names())
            {
                var xyz=geometry.sourceFor(name);var envelope=curve.envelope(name).inflate(.00003);
                for(double t:new double[]{0,.01,.1,.23,.5,.77,.9,.99,1})
                {var transform=geometry.transforms(from.interpolate(to,t).pose(geometry.mount())).get(name);for(int index:new int[]{0,xyz.length/2/3*3,xyz.length-3}){var p=transform.point(new Vec3(xyz[index],xyz[index+1],xyz[index+2]));check(envelope.contains(p),"Actual curved vertex escaped "+name);}}
                var f=geometry.transforms(from.interpolate(to,.5).pose(geometry.mount())).get(name);var point=f.point(new Vec3(xyz[0],xyz[1],xyz[2]));check(curve.intersects(name,new AABB(point,point).inflate(.001)),"Middle-curve obstruction accepted: "+name);
            }
            var coupled=new NervCranePoseR52.State(machine,-28.25,plug,true,null,null);var stopped=sweep.between(coupled,coupled);
            for(String wheel:stopped.names())if(wheel.startsWith("wheel/"))
            {var b=stopped.envelope(wheel);check(!stopped.intersects(wheel,new AABB(b.minX,b.minY-2,b.minZ,b.maxX,machine.translation().y-.00002,b.maxZ)),"Actual wheel running contact falsely blocked");check(stopped.intersects(wheel,new AABB(b.minX,b.minY-2,b.minZ,b.maxX,machine.translation().y+.002,b.maxZ)),"2mm wheel/rail penetration accepted");}
        }
        System.out.println("Actual complete crane curve/floor negative tests PASS checks="+checks+" source="+geometry.sourceFingerprint()+"; no world/native acceptance");
    }
}

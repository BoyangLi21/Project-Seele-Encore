package com.projectseele.world;

import java.util.List;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Existing contact resolves within a bounded prefix of the captured vertical line. */
public final class NervRescueContactEgressR53Test
{
    private static int checks;
    private static void check(boolean value,String message)
    {checks++;if(!value)throw new AssertionError(message);}
    private static RigidTransform at(double x,double y,double z)
    {return new RigidTransform(new Vec3(x,y,z),0,0,0,1);}
    private static NervRescueContactEgressR53 surface(double... xyz)
    {
        return new NervRescueContactEgressR53(new EvaOriginalMeshGeometryR52.Geometry(2,"test",List.of(
                new EvaOriginalMeshGeometryR52.Part("arm_r","test","test",xyz,new AABB(-10,-10,-10,10,10,10)))));
    }
    public static void main(String[] args)
    {
        var root=at(0,0,0);var up=at(0,2,0);var floor=new AABB(-1,0,-1,1,1,1);
        var low=surface(-.5,.5,-.5,.5,.5,-.5,0,.5,.5);
        check(low.separates(root,root,root,floor),"Stationary clamp preserves the captured support contact");
        check(low.separates(root,root,up,floor),"Upward translation removes the existing contact");
        check(low.separates(root,at(0,.1,0),up,floor),"Subsequent lift segment retains the original certificate");
        check(!low.separates(root,root,at(.01,2,0),floor),"Horizontal motion cannot reuse a vertical escape");
        check(!low.separates(root,root,at(0,-.01,0),floor),"Downward motion cannot deepen contact");
        check(!low.separates(root,at(.01,0,0),up,floor),"Moved starting frame cannot reuse captured contact");
        check(!low.separates(root,root,RigidTransform.of(new Vec3(0,2,0),new Quaternionf().rotationY(.1F)),floor),"Rotation cannot reuse captured contact");
        var ceiling=new AABB(-1,1,-1,1,2,1);
        check(!low.separates(root,root,up,ceiling),"New overhead obstacle remains blocked");
        check(!low.separates(root,at(0,1,0),up,ceiling),"Later segments cannot relabel a new obstacle as existing contact");
        var below=surface(-.5,-.5,-.5,.5,.5,-.5,0,.5,.5);
        check(below.separates(root,root,up,floor),"An initially intersecting source component resolves a thin-floor penetration");
        var mixed=surface(-.5,.5,-.5,.5,.5,-.5,0,.5,.5,-.5,-.5,-.5,.5,-.5,-.5,0,-.5,.5);
        check(mixed.separates(root,root,up,floor),"Unwelded patches of the same captured rigid body share its initial solid contact");
        check(mixed.separates(root,at(0,.06304849684238,0),at(0,.64480835199356,0),floor),"Later sole patch entry remains the complete body's bounded exit");
        var latePatch=surface(-.5,.5,-.5,.5,.5,-.5,0,.5,.5,-.5,-.1,-.5,.5,-.1,-.5,0,-.1,.5);
        check(latePatch.separates(root,at(0,.06304849684238,0),at(0,.14480835199356,0),floor),"Actual first lifted prefix does not mistake a new exported patch for a new solid");
        check(!mixed.separates(root,at(0,1.51,0),at(0,2,0),floor),"Permission ends after the lowest actual clipped patch clears");
        check(!mixed.separates(root,root,up,new AABB(-1,1.1,-1,1,2.1,1)),"Aggregate contact does not admit a new overhead solid");
        var outside=surface(2,-2,2,3,-2,2,2,-2,3,-.5,.5,-.5,.5,.5,-.5,0,.5,.5);
        check(outside.separates(root,root,up,floor),"Empty concave space is not filled by a global minimum");
        var clipped=surface(-3,-1,0,3,2,0,3,2,.5);
        check(clipped.separates(root,root,up,new AABB(0,0,-1,1,1,1)),"Exact footprint clips away the low outside part of a triangle");
        check(surface(-.5,.004,-.5,.5,.004,-.5,0,.004,.5).separates(root,root,up,floor),"An actual initial contact near the bottom remains a finite depenetration");
        check(!low.separates(root,root,up,new AABB(3,0,3,4,1,4)),"No actual contact produces no exemption");
        var rotated=RigidTransform.of(new Vec3(10,20,30),new Quaternionf().rotationY(.7F));
        var raised=new RigidTransform(rotated.translation().add(0,2,0),rotated.qx(),rotated.qy(),rotated.qz(),rotated.qw());
        check(low.separates(rotated,rotated,raised,new AABB(9,20,29,11,21,31)),"Captured actual world rotation and translation are respected");
        check(!below.separates(root,at(0,1.51,0),at(0,2,0),floor),"No depenetration permission survives complete separation");
        check(!surface(-.5,-.5,-.5,.5,-.5,-.5,0,-.5,.5).separates(root,root,up,floor),"A wholly below-floor component has no initial contact and remains blocked");
        var joined=surface(-.5,.5,-.5,.5,.5,-.5,0,.5,.5,-.5,.5,-.5,0,.5,.5,0,-.5,0);
        check(joined.separates(root,root,up,floor),"Shared original vertices identify the same initially penetrating component");
        check(!joined.separates(root,root,up,new AABB(-1,1.1,-1,1,2,1)),"A new shape above the same source component remains blocked");
        check(low.separates(root,root,up,floor),"Returning to an earlier captured frame rebuilds its exact clipping");
        check(!low.separates(root,at(0,.51,0),up,floor),"A warm shape result cannot retain permission past separation");
        check(!low.separates(root,root,up,new AABB(-1,.6,-1,1,1.6,1)),"Changed native shape height is not the cached initial contact");
        var shifted=at(10,0,0);
        check(!low.separates(shifted,shifted,at(10,2,0),floor),"Captured translation invalidates earlier footprint clipping");
        var ground=new AABB(-1,-1,-1,1,0,1);
        var submerged=new EvaOriginalMeshGeometryR52.Geometry(2,"test",List.of(
                new EvaOriginalMeshGeometryR52.Part("foot","test","test",
                        new double[]{-.5,-1.2,-.5,.5,-1.2,-.5,0,-1.2,.5},new AABB(-1,-2,-1,1,0,1))));
        var floorExit=new NervRescueContactEgressR53(submerged,java.util.Set.of(ground));
        check(floorExit.separates(root,at(0,.27,0),at(0,.46,0),ground),"Captured connected floor admits the complete sole's finite upward exit");
        check(!floorExit.separates(root,root,up,new AABB(-1,0,-1,1,1,1)),"Uncaptured raised floor remains a new obstruction");
        check(!floorExit.separates(root,at(0,1.21,0),up,ground),"Ground support permission ends once the lowest sole clears");
        System.out.println("PASS R53 original wreck support-contact egress: "+checks);
    }
}

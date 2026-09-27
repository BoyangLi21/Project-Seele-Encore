package com.projectseele.world;

import java.util.*;
import net.minecraft.world.phys.*;

public final class VerticalCarrierSweepR40Test
{
    private static List<Vec3> box(AABB a)
    {
        var points=new ArrayList<Vec3>();
        for(double x:new double[]{a.minX,a.maxX})for(double y:new double[]{a.minY,a.maxY})for(double z:new double[]{a.minZ,a.maxZ})points.add(new Vec3(x,y,z));
        return points;
    }
    private static void check(boolean condition,String text){if(!condition)throw new AssertionError(text);}
    public static void main(String[] args)
    {
        var body=box(new AABB(-1,0,-1,1,2,1));
        check(!VerticalCarrierSweepR40.obstructed(body,new AABB(-5,-1,-5,5,0,5),100),"Bearing floor blocked upward separation");
        check(!VerticalCarrierSweepR40.obstructed(body,new AABB(-5,-1,-5,5,0,5),new Vec3(2,0,0)),"Parallel supported ground translation was blocked");
        check(VerticalCarrierSweepR40.obstructed(body,new AABB(-5,5,-5,5,6,5),100),"Real roof was ignored");
        check(VerticalCarrierSweepR40.obstructed(body,new AABB(-5,5,-5,5,5.04,5),300),"Long sweep tunneled through thin roof");
        check(VerticalCarrierSweepR40.obstructed(body,new AABB(-5,1.95,-5,5,2.1,5),100),"Initial overhead contact was ignored");
        var sloped=new ArrayList<Vec3>();
        for(double x:new double[]{-4,4})for(double y:new double[]{0,.5})for(double z:new double[]{-.5,.5})sloped.add(new Vec3(x,2-x*.5+y,z));
        check(!VerticalCarrierSweepR40.obstructed(sloped,new AABB(-3,0,-.5,-2,1,.5),100),"Empty AABB corner below the sloping limb blocked rescue");
        check(VerticalCarrierSweepR40.obstructed(sloped,new AABB(-3,5,-.5,-2,6,.5),100),"Obstacle above the actual sloping limb was ignored");
        check(VerticalCarrierSweepR40.obstructed(body,new AABB(3,0,-2,3.04,4,2),new Vec3(100,0,0)),"Ground transfer tunneled through thin side wall");
        check(!VerticalCarrierSweepR40.obstructed(sloped,new AABB(-3,0,-.5,-2,1,.5),new Vec3(0,0,2)),"Ground translation hit an empty sloping-hull AABB corner");
        var shoulderShells=List.of(box(new AABB(-5,0,-1,-3,3,1)),box(new AABB(3,0,-1,5,3,1)));
        check(!VerticalCarrierSweepR40.obstructedCompound(shoulderShells,new AABB(-1,1,-.5,1,2,.5),new Vec3(0,100,0)),"Compound torso's real central gap became solid");
        check(VerticalCarrierSweepR40.obstructedCompound(shoulderShells,new AABB(3.5,5,-.5,4.5,6,.5),new Vec3(0,100,0)),"A real shoulder shell obstruction was ignored");
        System.out.println("Vertical carrier sweep: support separation, thin roofs, overhead contact and sloped-hull empty corners PASS");
    }
    private VerticalCarrierSweepR40Test(){}
}

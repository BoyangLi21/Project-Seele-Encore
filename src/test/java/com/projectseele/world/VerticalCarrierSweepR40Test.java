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
    public static void main(String[] args) throws Exception
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
        var needle=new ArrayList<Vec3>();
        for(double x:new double[]{0,1e-9})for(double z:new double[]{0,1})
        {needle.add(new Vec3(x,-1,z));needle.add(new Vec3(x,x==0?2:0,z));}
        // At the low edge old upperY=0. Upward1 enters new solid y(0,1].
        // Coordinate tolerance must not borrow the high edge's y=2 witness.
        check(!new CarrierSupportEscapeR50(needle).separatesUp(new AABB(-1,-.1,-1,1,1,2),new Vec3(0,1,0)),
                "Degenerate narrow hull borrowed an invalid support witness");
        var diagonalNeedle=new ArrayList<Vec3>();
        for(var v:needle)diagonalNeedle.add(new Vec3((v.x-v.z)/Math.sqrt(2),v.y,(v.x+v.z)/Math.sqrt(2)));
        check(!new CarrierSupportEscapeR50(diagonalNeedle).separatesUp(new AABB(-2,-.1,-2,2,1,2),new Vec3(0,1,0)),
                "Rotated degenerate hull bypassed the axis-span guard");
        var nonFinite=box(new AABB(-1,0,-1,1,2,1));nonFinite.add(new Vec3(Double.NaN,2,0));
        check(!new CarrierSupportEscapeR50(nonFinite).separatesUp(new AABB(-5,-1,-5,5,0,5),new Vec3(0,100,0)),
                "Nonfinite geometry created a support escape witness");
        check(!CarrierSupportEscapeR50.pureUp(new Vec3(1e-10,1,0)),"Support proof accepted a horizontal component");
        try(var stream=VerticalCarrierSweepR40Test.class.getResourceAsStream("/physics/field_foot_r50.json"))
        {
            check(stream!=null,"Recorded field-foot regression fixture missing");
            var record=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            var foot=new ArrayList<Vec3>();
            for(var vertex:record.getAsJsonArray("vertices"))
            {var p=vertex.getAsJsonArray();foot.add(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()));}
            check(!VerticalCarrierSweepR40.obstructed(foot,new AABB(0,0,0,1,1,1),234.975),"Numerical skin trapped the recorded clear foot at a platform corner");
            check(VerticalCarrierSweepR40.obstructed(foot,new AABB(0,6,0,1,7,1),234.975),"A real roof above the same foot was ignored");
            check(!VerticalCarrierSweepR40.obstructed(foot,new AABB(-1,0,0,0,1,1),new Vec3(0,234.975,0)),"Existing supporting contact blocked a proven upward exit");
            check(VerticalCarrierSweepR40.obstructed(foot,new AABB(-1,6,0,0,7,1),new Vec3(0,234.975,0)),"Support exit bypassed a genuine new roof collision");
            check(VerticalCarrierSweepR40.obstructed(foot,new AABB(-1,3,0,0,4,1),new Vec3(0,234.975,0)),"Support exit bypassed an initial overhead intersection");
        }
        try(var stream=VerticalCarrierSweepR40Test.class.getResourceAsStream("/physics/field_hand_r50.json"))
        {
            check(stream!=null,"Recorded field-hand regression fixture missing");
            var record=com.google.gson.JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            var hand=new ArrayList<Vec3>();for(var vertex:record.getAsJsonArray("vertices"))
            {var p=vertex.getAsJsonArray();hand.add(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()));}
            check(!VerticalCarrierSweepR40.obstructed(hand,new AABB(0,0,0,1,1,1),234.975),
                    "Recorded shallow hand support intrusion could not exit upward");
            check(VerticalCarrierSweepR40.obstructed(hand,new AABB(0,4,0,1,5,1),234.975),
                    "Shallow hand support escape bypassed a new roof");
        }
        System.out.println("Vertical carrier sweep: support separation, thin roofs, overhead contact and sloped-hull empty corners PASS");
    }
    private VerticalCarrierSweepR40Test(){}
}

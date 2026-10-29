package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

public final class TvYashimaGuardR54Test
{
    private static void check(boolean condition,String message)
    {if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)
    {
        Vec3 position=new Vec3(-1189.205,175,-1378.938),goal=new Vec3(-1203.79,175,-1366.55);
        for(int i=0;i<20;i++)
        {
            Vec3 next=TvYashimaArrivalR50.guardStepR54(position,goal);
            check(next.distanceTo(position)<=8.000001,"Continuous bounded displacement");
            check(next.distanceToSqr(goal)<=position.distanceToSqr(goal),"No overshoot");position=next;
        }
        check(position.equals(goal),"Defender reaches its single fixed station");
        for(int i=0;i<160+60+600;i++)
        {
            position=TvYashimaArrivalR50.guardStepR54(position,goal);
            check(position.equals(goal),"Warning, beam and recovery never move an arrived defender");
        }
        System.out.println("Yashima fixed-station approach and settled-position checks passed");
    }
}

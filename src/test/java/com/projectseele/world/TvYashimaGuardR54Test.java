package com.projectseele.world;

import net.minecraft.world.phys.Vec3;

public final class TvYashimaGuardR54Test
{
    private static void check(boolean condition,String message)
    {if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)
    {
        Vec3 position=new Vec3(-1189.205,175,-1378.938),goal=new Vec3(-1203.79,175,-1366.55);
        check(TvYashimaArrivalR50.guardStepR54(position,goal).equals(goal),"Walking controller receives the fixed destination");
        position=goal.add(.8,.2,.5);
        for(int i=0;i<160+60+600;i++)
        {
            check(TvYashimaArrivalR50.guardStepR54(position,goal).equals(position),"Arrival keeps the real grounded position; no snap to the station");
        }
        System.out.println("Yashima fixed-station approach and settled-position checks passed");
    }
}

package com.projectseele.world;

import com.projectseele.entity.EvaShieldRigR47;
import net.minecraft.world.phys.Vec3;

public final class TvYashimaGuardR54Test
{
    private static void check(boolean condition,String message)
    {if(!condition)throw new AssertionError(message);}
    public static void main(String[] args)
    {
        check(!TvYashimaArrivalR50.enterCoverR54(true,160,0),"Early warning stays clear");
        check(TvYashimaArrivalR50.enterCoverR54(true,20,0),"Final second enters protection");
        check(TvYashimaArrivalR50.enterCoverR54(false,0,60),"Whole live beam remains protected");
        check(!TvYashimaArrivalR50.enterCoverR54(false,0,0),"Beam end withdraws");
        var plate=new EvaShieldRigR47.GuardPlaneR54(new Vec3(0,5,10),new Vec3(0,0,1),
                new Vec3(1,0,0),new Vec3(0,1,0),12,8);
        Vec3 boss=new Vec3(0,5,200),body=new Vec3(0,5,0),eye=new Vec3(0,5,25),muzzle=new Vec3(0,5,50);
        check(plate.intersects(Vec3.ZERO,boss,body,2),"Rear plate intercepts the body ray");
        check(!plate.intersects(Vec3.ZERO,eye,boss,-4),"Optical ray starts ahead of plate");
        check(!plate.intersects(Vec3.ZERO,muzzle,boss,-2),"Cannon ray starts ahead of plate");
        var fitted=new EvaShieldRigR47.GuardPlaneR54(new Vec3(0,20,10),new Vec3(0,0,1),
                new Vec3(1,0,0),new Vec3(0,1,0),44*5D/32,116*5D/32);
        Vec3 solved=TvYashimaArrivalR50.guardPositionR54(fitted,Vec3.ZERO,body,eye,muzzle,boss,0);
        check(solved!=null,"Original 44x116 shield has a concrete rear solution");
        check(fitted.intersects(solved,boss,body,1),"Solved plate protects body");
        check(!fitted.intersects(solved,eye,boss,-4)&&!fitted.intersects(solved,muzzle,boss,-2),"Solved plate leaves both real ray origins clear");
        Vec3 position=Vec3.ZERO,goal=new Vec3(100,0,0);
        for(int i=0;i<20;i++)
        {
            Vec3 next=TvYashimaArrivalR50.guardStepR54(position,goal);
            check(next.distanceTo(position)<=8.000001,"Continuous bounded displacement");
            check(next.distanceToSqr(goal)<=position.distanceToSqr(goal),"No overshoot");position=next;
        }
        check(position.equals(goal),"Guard transfer completes within final-second budget");
        System.out.println("Yashima guard timing, rear plate and finite motion checks passed");
    }
}

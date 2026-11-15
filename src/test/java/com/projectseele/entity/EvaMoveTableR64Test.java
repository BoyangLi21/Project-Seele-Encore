package com.projectseele.entity;

import com.projectseele.entity.EvaMoveTableR64.Row;

import java.util.HashSet;
import java.util.Set;

/** The frames core's table: every row can be played, left and followed as it says, and the strings end. */
public final class EvaMoveTableR64Test
{
    private static void check(boolean condition,String message)
    {
        if(!condition)throw new AssertionError(message);
    }

    public static void main(String[] args)
    {
        int rows=0;
        for(Row r:EvaMoveTableR64.rows())
        {
            rows++;
            String n=r.name();
            check(r.startup()>=2&&r.active()>=2&&r.recovery()>=1,n+": a row winds up, is live and recovers");
            check(r.lead()>=0&&r.tail()>=0&&r.lead()+r.tail()<.5F,n+": the live ticks cover a part of the clip around its contact");
            check(r.damage()>0&&r.radius()>0&&r.stop()>=1&&r.stop()<=8,n+": damage, reach and hold");
            check(r.level()>=EvaMoveTableR64.LIGHT&&r.level()<=EvaMoveTableR64.FINISHER,n+": level");
            int live=r.startup()+r.active(),total=r.total();
            check(r.feint()<r.startup(),n+": a blow is withdrawn only before it can land");
            // A blow is never left for another before its live ticks are over, and sooner when it has landed.
            if(r.cancelHit()>0)check(r.cancelHit()>live&&r.cancelHit()<=total,n+": cancel on a hit after the live ticks");
            if(r.cancelWhiff()>0)check(r.cancelHit()>0&&r.cancelWhiff()>=r.cancelHit()&&r.cancelWhiff()<=total,n+": cancel on a miss no sooner than on a hit");
            check(r.cancelHit()>0==(r.cancelWhiff()>0),n+": a row that may be left on a hit may be left on a miss");
            check(r.evadeHit()>=live&&r.evadeWhiff()>=r.evadeHit()&&r.evadeWhiff()<=total,n+": an evade leaves it once it can no longer land");
            check(r.moveFrom()>live&&r.moveFrom()<=total,n+": a step ends it in its recovery");
            if(r.armorFrom()>=0)check(r.armorFrom()>=1&&r.armorTo()>=r.armorFrom()&&r.armorTo()<=total,n+": armour inside the row");
            check(r.light()==null||EvaMoveTableR64.get(r.light())!=null,n+": the light press goes to a row");
            check(r.heavy()==null||EvaMoveTableR64.get(r.heavy())!=null,n+": the heavy press goes to a row");
            check(r.cancelHit()>0||r.light()==null&&r.heavy()==null,n+": a row that cannot be left names nothing to follow it");
            // The clip is crossed once, forward, and its contact lies in the live ticks.
            float open=.3F-r.lead(),close=.3F+r.tail(),before=0;
            for(int k=1;k<=total;k++)
            {
                float at=EvaMoveTableR64.phase(k,r.startup(),r.active(),r.recovery(),open,close);
                check(at>before&&at<=1F,n+": the clip runs forward at tick "+k);
                before=at;
            }
            check(Math.abs(EvaMoveTableR64.phase(r.startup(),r.startup(),r.active(),r.recovery(),open,close)-open)<1e-5F,n+": the live part opens as the wind-up ends");
            check(Math.abs(EvaMoveTableR64.phase(live,r.startup(),r.active(),r.recovery(),open,close)-close)<1e-5F,n+": and closes with the live ticks");
            check(Math.abs(EvaMoveTableR64.phase(total,r.startup(),r.active(),r.recovery(),open,close)-1F)<1e-5F,n+": the clip ends with the row");
        }
        check(rows==8,"eight rows");

        // The light string from standing: four blows, 95 points, and it ends.
        Set<String> seen=new HashSet<>();
        float damage=0;int blows=0;
        for(Row r=EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,false,false);r!=null;r=EvaMoveTableR64.get(r.light()))
        {
            check(seen.add(r.name()),"the light string does not come back to "+r.name());
            damage+=r.damage();blows++;
            check(r.heavy()==null||r.heavy().equals("kick"),r.name()+": the heavy press out of a punch is the kick");
        }
        check(blows==4&&damage==95F,"jab, cross, jab, slam: 95 points, found "+blows+" blows and "+damage);
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,true,false).name().equals("kick"),"the heavy press from standing is the kick");
        check(EvaMoveTableR64.get("kick").cooldown()==44&&EvaMoveTableR64.get("knife_reverse").cooldown()==53,"the cooldowns of R63 stand");

        // The knife: the cut, the counter after an evade, the reverse cut; one cancel, cut into reverse cut.
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_KNIFE,false,false).name().equals("knife_slash"),"knife light");
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_KNIFE,false,true).name().equals("knife_counter"),"knife light after an evade");
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_KNIFE,true,true).name().equals("knife_reverse"),"knife heavy");
        check(EvaMoveTableR64.get("knife_slash").light()==null&&"knife_reverse".equals(EvaMoveTableR64.get("knife_slash").heavy()),"a cut is left only for the reverse cut");
        check(EvaMoveTableR64.get("knife_reverse").cancelHit()<0,"the reverse cut is played out");
        System.out.println("Frames core table: "+rows+" rows, strings end, clips run forward PASS");
    }

    private EvaMoveTableR64Test(){}
}

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
        check(rows==13,"thirteen rows");

        for(boolean body:new boolean[]{false,true})
        {
            Row punch=EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,false,false,true,body,false);
            for(int i=0;i<8;i++)
            {
                check(punch.name().equals(i%2==0?"jab":"cross")&&punch.stage()==i%2,"held light alternates the two R63 fist clips");
                check("kick".equals(punch.heavy()),"either fist may lead into the heavy kick");
                punch=EvaMoveTableR64.get(punch.light());
            }
        }
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,false,true,true,false,false).name().equals("jab2"),
                "without the body special the evade counter still leads to a slam");
        Set<String> seen=new HashSet<>();
        float damage=0;int blows=0;
        for(Row r=EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,false,true,true,true,false);r!=null;r=EvaMoveTableR64.get(r.light()))
        {
            check(seen.add(r.name()),"the Unit's own string does not come back to "+r.name());
            damage+=r.damage();blows++;
            check(r.heavy()==null||r.heavy().equals("kick"),r.name()+": the heavy press out of it is the kick");
        }
        check(blows==3&&damage==75F,"pounce, knee, slam: 75 points, found "+blows+" blows and "+damage);
        Row sprint=EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,false,false,true,true,true);
        check(sprint.name().equals("charge"),"a sprinting light starts the shoulder charge");
        for(String[] pair:new String[][]{{"pounce","jab"},{"knee","cross"},{"charge","jab"}})
        {
            Row move=EvaMoveTableR64.get(pair[0]),old=EvaMoveTableR64.get(pair[1]);
            check(move.damage()==old.damage()&&move.cooldown()==old.cooldown()&&move.radius()==old.radius()
                    &&move.knock()==old.knock()&&move.level()==old.level(),move.name()+": preserves the light attack's balance");
        }
        check(EvaMoveTableR64.opener(EvaUnit01Entity.WEAPON_FISTS,true,false,true).name().equals("kick"),"the heavy press from standing is the kick");
        check(EvaMoveTableR64.get("kick").cooldown()==44&&EvaMoveTableR64.get("knife_reverse").cooldown()==53,"the cooldowns of R63 stand");

        // The knife (the owner, 2026-11-16): the light press is the cut and then the cut back, 55 points; the heavy
        // press is the thrust that was the light press, and out of it the reverse grip; a heavy press out of a cut
        // is the thrust; the counter after an evade stands.
        int knife=EvaUnit01Entity.WEAPON_KNIFE;
        check(EvaMoveTableR64.opener(knife,false,false,true).name().equals("knife_cut"),"knife light");
        check(EvaMoveTableR64.opener(knife,false,true,true).name().equals("knife_counter"),"knife light after an evade");
        check(EvaMoveTableR64.opener(knife,true,false,true).name().equals("knife_slash")&&EvaMoveTableR64.opener(knife,true,true,true).name().equals("knife_slash"),"knife heavy");
        seen.clear();damage=0;blows=0;
        for(Row r=EvaMoveTableR64.opener(knife,false,false,true);r!=null;r=EvaMoveTableR64.get(r.light()))
        {
            check(seen.add(r.name()),"the knife's light string does not come back to "+r.name());
            damage+=r.damage();blows++;
            check("knife_slash".equals(r.heavy()),r.name()+": the heavy press out of a cut is the thrust");
        }
        check(blows==2&&damage==55F,"cut, cut back: 55 points, found "+blows+" blows and "+damage);
        check(EvaMoveTableR64.get("knife_slash").light()==null&&"knife_reverse".equals(EvaMoveTableR64.get("knife_slash").heavy()),"the thrust is left only for the reverse grip");
        check(EvaMoveTableR64.get("knife_reverse").cancelHit()<0,"the reverse grip is played out");
        check(EvaMoveTableR64.get("knife_slash").damage()==60F&&EvaMoveTableR64.get("knife_reverse").damage()==80F,"the thrust and the reverse grip strike as they did");
        // A Unit without the cuts has the knife as it was.
        check(EvaMoveTableR64.opener(knife,false,false,false).name().equals("knife_slash"),"knife light without the cuts");
        check(EvaMoveTableR64.opener(knife,false,true,false).name().equals("knife_counter"),"knife light after an evade without the cuts");
        check(EvaMoveTableR64.opener(knife,true,false,false).name().equals("knife_reverse"),"knife heavy without the cuts");
        System.out.println("Frames core table: "+rows+" rows, punch loop and finishers, clips run forward PASS");
    }

    private EvaMoveTableR64Test(){}
}

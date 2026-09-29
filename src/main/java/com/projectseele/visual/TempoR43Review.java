package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import net.minecraft.server.level.ServerPlayer;

/** Measures accepted production key inputs and authoritative start/end phases. */
public final class TempoR43Review
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r43Tempo");
    private static final String[] NAMES={"jab","cross","knife_forward","knife_reverse","kick_first","kick_repeat"};
    private static final int[] WEAPONS={0,0,1,1,0,0},INPUTS={1,1,1,2,5,5};
    private static int index,readyAt=-1,requestedAt=-1,startedAt=-1,lastKickStart=-1,lastPhaseTick;
    private static float previousPhase,maxPhase;
    private static boolean requested;
    private static final JsonArray RESULTS=new JsonArray();

    private static boolean active(EvaUnit01Entity eva)
    {return index<2?eva.getOrdinaryAttackStage()>=0:index<4?eva.getKnifeMotionType(0)>=0:eva.isKickMotionActive(0);}
    public static boolean tick(EvaUnit01Entity eva,ServerPlayer pilot,int tick)
    {
        if(readyAt<0){readyAt=tick+20;eva.selectMotionLabWeapon(WEAPONS[index]);}
        if(tick<readyAt)return false;
        if(!requested){requestedAt=tick;requested=true;CombatR31Review.inputR42(INPUTS[index]);}
        if(startedAt<0)
        {
            if(active(eva)){startedAt=tick;maxPhase=0;previousPhase=-1;lastPhaseTick=tick;}
            else
            {
                if(tick-requestedAt>220)throw new IllegalStateException("Tempo input not accepted: "+NAMES[index]);
                // Ordinary/knife inputs have a combo buffer. Resending before
                // the first packet is acknowledged queues an unwanted second
                // action. Only the unbuffered repeated B kick needs polling.
                if(index==5)CombatR31Review.inputR42(INPUTS[index]);
                return false;
            }
        }
        if(active(eva))
        {
            float phase=eva.combatPhaseR31();
            if(phase+1e-5<previousPhase)throw new IllegalStateException("Action phase reversed: "+NAMES[index]+" tick="+tick+" start="+startedAt+" ordinary="+eva.getOrdinaryAttackStage()+" phase="+previousPhase+"->"+phase);
            maxPhase=Math.max(maxPhase,phase);previousPhase=phase;lastPhaseTick=tick;
            if(tick-startedAt>160)throw new IllegalStateException("Action never finished: "+NAMES[index]);
            return false;
        }
        var row=new JsonObject();row.addProperty("name",NAMES[index]);row.addProperty("passed",maxPhase>.85F);
        row.addProperty("input_tick",requestedAt);row.addProperty("accepted_tick",startedAt);row.addProperty("ended_tick",tick);
        row.addProperty("duration_ticks",tick-startedAt);row.addProperty("last_phase_tick",lastPhaseTick);row.addProperty("maximum_phase",maxPhase);
        if(index>=4){if(lastKickStart>=0)row.addProperty("repeat_interval_ticks",startedAt-lastKickStart);lastKickStart=startedAt;}
        RESULTS.add(row);index++;
        if(index==NAMES.length)return true;
        readyAt=tick+(index==1||index==5?1:15);requestedAt=startedAt=-1;requested=false;
        eva.selectMotionLabWeapon(WEAPONS[index]);return false;
    }
    public static JsonArray results(){return RESULTS;}
    private TempoR43Review(){}
}

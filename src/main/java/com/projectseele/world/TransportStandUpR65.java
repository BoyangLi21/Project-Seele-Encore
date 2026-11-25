package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * R65 (playtest 2, item 19): a transport asked for while its Unit lies prone or crouches does not refuse. The
 * Unit is stood up (EvaUnit01Entity.standForTransportR65) and the same request is made again once it stands; its
 * answer goes to whoever asked. A Unit that cannot get up within twenty seconds is given up on, with a word.
 */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class TransportStandUpR65
{
    private record Pending(ServerLevel level,UUID eva,UUID caller,long until,Supplier<String> retry){}
    private static final List<Pending> PENDING=new ArrayList<>();
    private static final String WAITING="机体正在起身，站稳后自动安排运输。";
    private static final String GAVE_UP="机体未能起身，运输没有安排。请移到开阔处后重新申请。";

    /**
     * Null when the Unit stands and the request may go on; otherwise the request waits, and this is the note to
     * answer with now: that the Unit is getting up, or what keeps it from getting up (no room above it, knocked
     * down), which the pilot can see to while the request waits.
     */
    public static String standFirst(ServerLevel level,EvaUnit01Entity eva,UUID caller,Supplier<String> retry)
    {
        String why=eva==null?"":eva.standForTransportR65();
        if(why.isEmpty())return null;
        UUID id=eva.getUUID();
        PENDING.removeIf(p->p.eva().equals(id));
        PENDING.add(new Pending(level,id,caller,level.getGameTime()+400,retry));
        ProjectSeele.LOGGER.info("Transport waits for the Unit to stand: eva={} why={}",id,why);
        return why.equals(EvaUnit01Entity.STANDING_UP_R65)?WAITING:why;
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||PENDING.isEmpty())return;
        for(var pending:List.copyOf(PENDING))
        {
            var level=pending.level();
            String reply;
            if(!(level.getEntity(pending.eva()) instanceof EvaUnit01Entity eva))reply=null;
            else if(eva.standForTransportR65().isEmpty())
            {
                PENDING.remove(pending);
                try{reply=pending.retry().get();}
                catch(IllegalArgumentException|IllegalStateException refused){reply=refused.getMessage();}
            }
            else if(level.getGameTime()>pending.until()){PENDING.remove(pending);reply=GAVE_UP;}
            else continue;
            if(reply==null){PENDING.remove(pending);continue;}
            var caller=pending.caller()==null?null:level.getServer().getPlayerList().getPlayer(pending.caller());
            if(caller!=null)caller.sendSystemMessage(OperationText.read(reply));
        }
    }

    private TransportStandUpR65(){}
}

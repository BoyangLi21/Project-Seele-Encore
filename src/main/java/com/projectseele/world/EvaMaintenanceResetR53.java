package com.projectseele.world;

import java.util.*;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Operator reset waits for the installed world instead of dropping the command. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class EvaMaintenanceResetR53
{
    private static final Map<ServerLevel,Map<Integer,CommandSourceStack>> PENDING=new WeakHashMap<>();
    private EvaMaintenanceResetR53() {}

    public static int request(CommandSourceStack source,ServerLevel level,int requested)
    {
        int accepted=0;
        for(int variant=0;variant<3;variant++)
        {
            if(requested>=0&&requested!=variant)continue;
            if(NervRouteRuntimeR52.controllerLoadedR52(level)&&NervRouteRuntimeR52.ready(level))
            {
                try { reset(source,level,variant);accepted++;continue; }
                catch(IllegalStateException held) { source.sendFailure(Component.literal(held.getMessage()));continue; }
            }
            PENDING.computeIfAbsent(level,l->new LinkedHashMap<>()).put(variant,source);accepted++;
        }
        if(PENDING.containsKey(level))source.sendSuccess(()->Component.literal("复位请求已保留，场地加载完成后自动执行。"),false);
        return accepted;
    }
    private static void reset(CommandSourceStack source,ServerLevel level,int variant)
    {
        EvaLogisticsDirector.forceReset(level,variant);
        source.sendSuccess(()->Component.literal(String.format(Locale.ROOT,"EVA-%02d 已复位：插入栓、驾驶员、登机桥和运输任务同步恢复。",variant)),false);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%20!=0)return;
        for(var level:event.getServer().getAllLevels())
        {
            var pending=PENDING.get(level);
            if(pending==null||!NervRouteRuntimeR52.controllerLoadedR52(level)||!NervRouteRuntimeR52.ready(level))continue;
            for(var entry:new ArrayList<>(pending.entrySet()))
            {
                try { reset(entry.getValue(),level,entry.getKey()); }
                catch(IllegalStateException held) { entry.getValue().sendFailure(Component.literal("复位未完成："+held.getMessage())); }
                pending.remove(entry.getKey());
            }
            if(pending.isEmpty())PENDING.remove(level);
        }
    }
}

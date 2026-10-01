package com.projectseele.network;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.CombatMotionResourcesR44;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/** New wire protocol plus a required private-motion identity handshake. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CombatBundleGateR44
{
    private static final Map<UUID,Integer> PENDING=new HashMap<>();
    @SubscribeEvent public static void login(PlayerEvent.PlayerLoggedInEvent event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player))return;
        try
        {
            var resources=CombatMotionResourcesR44.fingerprints();
            PENDING.put(player.getUUID(),player.tickCount);
            SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(()->player),new ClientboundCombatContractR44(resources));
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("Required combat bundle is unavailable for login",failure);
            player.connection.disconnect(Component.literal("服务器 EVA 动作资源合同无法读取，请检查本批动作包及 SHA 清单。"));
        }
    }
    public static void accept(ServerPlayer player,Map<String,String> resources)
    {
        if(player==null||!PENDING.containsKey(player.getUUID()))return;
        var expected=CombatMotionResourcesR44.fingerprints();
        if(!expected.equals(resources))
        {
            String difference=mismatch(expected,resources);
            ProjectSeele.LOGGER.warn("Combat resource login rejected: player={} {}",player.getUUID(),difference);
            player.connection.disconnect(Component.literal(difference));
        }
        else ProjectSeele.LOGGER.info("Combat resource login matched: player={} profiles={}",player.getUUID(),expected.size());
        PENDING.remove(player.getUUID());
    }
    public static String mismatch(Map<String,String> server,Map<String,String> client)
    {
        for(var entry:new java.util.TreeMap<>(server).entrySet())
            if(!entry.getValue().equals(client.get(entry.getKey())))
                return "EVA 动作资源不匹配："+entry.getKey()+"。服务器 SHA="+entry.getValue()
                        +"；客户端 SHA="+client.getOrDefault(entry.getKey(),"缺失")+"。请使用与服务器同批的动作资源包。";
        return "EVA 动作资源索引不匹配，请使用与服务器同批的动作资源包。";
    }
    @SubscribeEvent public static void tick(TickEvent.PlayerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||!(event.player instanceof ServerPlayer player))return;
        Integer since=PENDING.get(player.getUUID());
        if(since!=null&&player.tickCount-since>200)
        {
            PENDING.remove(player.getUUID());
            player.connection.disconnect(Component.literal("客户端未确认 EVA 动作资源 SHA，请更新与服务器同批的模组及动作包。"));
        }
    }
    @SubscribeEvent public static void logout(PlayerEvent.PlayerLoggedOutEvent event)
    {PENDING.remove(event.getEntity().getUUID());}
    private CombatBundleGateR44(){}
}

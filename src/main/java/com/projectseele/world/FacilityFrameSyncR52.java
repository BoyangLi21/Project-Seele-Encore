package com.projectseele.world;

import com.projectseele.network.ClientboundFacilityFrameR52;
import com.projectseele.network.SeeleNetwork;
import java.util.Map;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.network.PacketDistributor;

/** Sends a tiny map claim at login and when its real commissioning epoch changes. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class FacilityFrameSyncR52
{
    private static final Map<ServerPlayer,ClientboundFacilityFrameR52> SENT=new WeakHashMap<>();
    private static void send(ServerPlayer player,boolean force)
    {
        var level=player.server.getLevel(FacilitySchemaV2.DIMENSION);
        boolean claimed=level!=null&&NervRouteRuntimeR52.claimed(level);
        long epoch=claimed?NervRouteRuntimeR52.commissioningEpoch(level):0;
        if(claimed&&epoch==0)return;
        var headquarters=claimed?NervHeadquartersFrameR52.frame(level):null;
        var value=new ClientboundFacilityFrameR52(FacilitySchemaV2.DIMENSION.location(),claimed,epoch,
                headquarters!=null,headquarters==null?net.minecraft.core.BlockPos.ZERO:headquarters.translation(),claimed?NervRouteRuntimeR52.uprightGuideSourceR52(level):"");
        if(force||!value.equals(SENT.get(player)))
        {SeeleNetwork.CHANNEL.send(PacketDistributor.PLAYER.with(()->player),value);SENT.put(player,value);}
    }
    @SubscribeEvent public static void login(PlayerEvent.PlayerLoggedInEvent e){if(e.getEntity()instanceof ServerPlayer p)send(p,true);}
    @SubscribeEvent public static void dimension(PlayerEvent.PlayerChangedDimensionEvent e){if(e.getEntity()instanceof ServerPlayer p)send(p,true);}
    @SubscribeEvent public static void respawn(PlayerEvent.PlayerRespawnEvent e){if(e.getEntity()instanceof ServerPlayer p)send(p,true);}
    @SubscribeEvent public static void logout(PlayerEvent.PlayerLoggedOutEvent e){if(e.getEntity()instanceof ServerPlayer p)SENT.remove(p);}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent e)
    {if(e.phase==TickEvent.Phase.END&&e.getServer().getTickCount()%20==0)for(var p:e.getServer().getPlayerList().getPlayers())send(p,false);}
    private FacilityFrameSyncR52(){}
}

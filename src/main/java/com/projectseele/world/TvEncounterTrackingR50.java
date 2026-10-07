package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.GaghielEntity;
import com.projectseele.entity.RamielEntity;
import java.lang.ref.WeakReference;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Actual native entity pairings, not a radius estimate or an observer command. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class TvEncounterTrackingR50
{
    private static final Map<ServerPlayer,Map<UUID,WeakReference<Entity>>> TRACKED=new WeakHashMap<>();
    @SubscribeEvent public static void start(PlayerEvent.StartTracking event)
    {
        var target=event.getTarget();
        if(!(event.getEntity() instanceof ServerPlayer player)||target.level()!=player.level()
                ||!(target instanceof RamielEntity||target instanceof GaghielEntity))return;
        // Pairing may precede both the mission UUID and ownership tags. Only
        // the actual instance is retained; current mission proof is read later.
        TRACKED.computeIfAbsent(player,ignored->new HashMap<>()).put(target.getUUID(),new WeakReference<>(target));
    }
    @SubscribeEvent public static void stop(PlayerEvent.StopTracking event)
    {
        if(!(event.getEntity() instanceof ServerPlayer player))return;
        var map=TRACKED.get(player);var target=event.getTarget();
        if(map!=null)
        {
            var ref=map.get(target.getUUID());
            if(ref!=null&&ref.get()==target){map.remove(target.getUUID());TvEncounterRulesR45.forgetTargetFrameR50(player,target.getUUID());}
            if(map.isEmpty())TRACKED.remove(player);
        }
    }
    public static boolean tracks(ServerLevel level,ServerPlayer player,Entity target)
    {
        if(player==null||target==null||player.level()!=level||target.level()!=level||target.isRemoved())return false;
        var ref=TRACKED.getOrDefault(player,Map.of()).get(target.getUUID());
        return ref!=null&&ref.get()==target&&level.getEntity(target.getUUID())==target;
    }
    public static void clearPlayer(ServerPlayer player){TRACKED.remove(player);}
    private static void keepCurrentPairings(ServerPlayer player)
    {
        TRACKED.keySet().removeIf(old->old!=player&&old.getUUID().equals(player.getUUID()));
        var map=TRACKED.get(player);
        if(map!=null)map.values().removeIf(ref->{var entity=ref.get();return entity==null||entity.isRemoved()||entity.level()!=player.level();});
    }
    public static void clearLevel(ServerLevel level)
    {
        for(var map:TRACKED.values())map.values().removeIf(ref->{var entity=ref.get();return entity==null||entity.level()==level;});
        TRACKED.values().removeIf(Map::isEmpty);
    }
    @SubscribeEvent public static void logout(PlayerEvent.PlayerLoggedOutEvent event)
    {if(event.getEntity() instanceof ServerPlayer player){clearPlayer(player);TvEncounterRulesR45.logout(player);}}
    @SubscribeEvent public static void dimension(PlayerEvent.PlayerChangedDimensionEvent event)
    {if(event.getEntity() instanceof ServerPlayer player){keepCurrentPairings(player);TvEncounterRulesR45.logout(player);}}
    @SubscribeEvent public static void respawn(PlayerEvent.PlayerRespawnEvent event)
    {if(event.getEntity() instanceof ServerPlayer player){keepCurrentPairings(player);TvEncounterRulesR45.logout(player);}}
    @SubscribeEvent public static void unload(LevelEvent.Unload event)
    {if(event.getLevel() instanceof ServerLevel level){clearLevel(level);TvEncounterRulesR45.clearSession(level);}}
    private TvEncounterTrackingR50(){}
}

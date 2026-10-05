package com.projectseele.world;

import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.Level;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppedEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Preserve one button press while the dependency initializes loaded controllers. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NativeLiftCallRetryR43
{
    private record Call(UUID player,java.lang.ref.WeakReference<ServerPlayer> fake,ResourceKey<Level> dimension,String lift,BlockPos button,Integer gatewayTarget,int created,int expires) {}
    private static final Map<MinecraftServer,Map<String,Call>> PENDING=new WeakHashMap<>();

    public static void external(ServerPlayer player,String lift,BlockPos button)
    {enqueue(player,lift,button.immutable(),null,80);}
    public static void gateway(ServerPlayer player,int target)
    {enqueue(player,NervLiftPassengerSync.GATEWAY,null,target,80);}
    public static void externalWhileMovingR47(ServerPlayer player,String lift,BlockPos button)
    {enqueue(player,lift,button.immutable(),null,2000);}
    public static void gatewayWhileMovingR47(ServerPlayer player,int target)
    {enqueue(player,NervLiftPassengerSync.GATEWAY,null,target,2000);}
    private static void enqueue(ServerPlayer player,String lift,BlockPos button,Integer target,int lifetime)
    {
        var server=player.getServer();var jobs=PENDING.computeIfAbsent(server,k->new LinkedHashMap<>());
        String key=player.getUUID()+":"+lift;var previous=jobs.get(key);
        if(previous!=null&&Objects.equals(previous.button,button)&&Objects.equals(previous.gatewayTarget,target))return;
        var fake=player instanceof net.minecraftforge.common.util.FakePlayer?new java.lang.ref.WeakReference<ServerPlayer>(player):null;
        int tick=server.getTickCount();jobs.put(key,new Call(player.getUUID(),fake,player.level().dimension(),lift,button,target,tick,tick+lifetime));
        player.displayClientMessage(Component.literal("呼叫已登记，请稍候。"),true);
        ProjectSeele.LOGGER.info("Lift call waiting for native initialization: lift={} target={}",lift,target==null?button:target);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();var jobs=PENDING.get(server);if(jobs==null)return;
        for(var entry:new ArrayList<>(jobs.entrySet()))
        {
            var call=entry.getValue();int tick=server.getTickCount();if(tick<=call.created)continue;
            var player=server.getPlayerList().getPlayer(call.player);var level=server.getLevel(call.dimension);
            if(player==null&&call.fake!=null)player=call.fake.get();
            if(player==null||level==null||player.serverLevel()!=level){jobs.remove(entry.getKey());continue;}
            boolean ready=call.gatewayTarget!=null?RegionalGatewayDirector.controllersReadyR43(level):S20MovingElevatorsAdapter.callControllersReadyR43(level,call.lift);
            if(ready)
                for(var spec:NervLiftPassengerSync.managedLifts(level))if(spec.id().equals(call.lift))
                {
                    var at=S20MovingElevatorsAdapter.controllerPosition(spec,spec.lower());
                    if(level.getBlockEntity(at) instanceof com.supermartijn642.movingelevators.blocks.ControllerBlockEntity block
                            &&block.hasGroup()&&block.getGroup().isMoving())ready=false;
                    break;
                }
            if(!ready&&tick<call.expires)continue;
            jobs.remove(entry.getKey());
            if(!ready)
            {
                player.displayClientMessage(Component.literal("电梯暂时无法响应，请检查控制台。"),true);
                ProjectSeele.LOGGER.warn("Native lift call initialization timed out: lift={}",call.lift);continue;
            }
            // Re-enter the normal handler so card/egress, cage identity and
            // placement checks still apply. Never move a car directly here.
            if(call.gatewayTarget!=null)RegionalGatewayDirector.request(level,call.gatewayTarget,player);
            else S20MovingElevatorsAdapter.handleExternalCall(player,call.button);
        }
        if(jobs.isEmpty())PENDING.remove(server);
    }
    @SubscribeEvent public static void stop(ServerStoppedEvent event){PENDING.remove(event.getServer());}
    private NativeLiftCallRetryR43(){}
}

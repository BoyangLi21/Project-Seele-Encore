package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.supermartijn642.movingelevators.blocks.ControllerBlockEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.network.protocol.game.ClientboundBlockUpdatePacket;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

/** Replays authoritative aperture states after the client has placed its captured cage. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervLiftArrivalSyncR44
{
    private record Pending(String lift,BlockPos controller,Direction facing,int floor,long until) { }
    private record RequestKey(UUID player,String lift) { }
    private static final Map<ServerLevel,Map<RequestKey,Pending>> PENDING=new WeakHashMap<>();
    private static final Map<ServerPlayer,Map<String,Long>> LAST_REQUEST=new WeakHashMap<>();

    public static void request(ServerPlayer player,BlockPos controller,Direction facing)
    {
        if(player==null || !player.isAlive() || facing.getAxis().isVertical())return;
        ServerLevel level=player.serverLevel();
        if(!level.dimension().equals(FacilitySchemaV2.DIMENSION))return;
        long now=level.getGameTime();
        for(var spec:NervLiftPassengerSync.managedLifts(level))
        {
            for(var landing:spec.stops())
            {
                if(landing.walkY()!=controller.getY())continue;
                var actual=S20MovingElevatorsAdapter.controllerPosition(spec,landing);
                if(actual.getX()!=controller.getX() || actual.getZ()!=controller.getZ()
                        || !level.hasChunkAt(actual) || player.distanceToSqr(landing.cabinCentre().getCenter())>4096)continue;
                if(!(level.getBlockEntity(actual) instanceof ControllerBlockEntity block) || !block.hasGroup())return;
                var group=block.getGroup();
                if(group.x!=controller.getX() || group.z!=controller.getZ() || group.facing!=facing)return;
                var prior=LAST_REQUEST.computeIfAbsent(player,key->new HashMap<>());
                if(now-prior.getOrDefault(spec.id(),-100L)<10)return;
                prior.put(spec.id(),now);
                PENDING.computeIfAbsent(level,key->new HashMap<>()).put(new RequestKey(player.getUUID(),spec.id()),
                        new Pending(spec.id(),actual.immutable(),facing,landing.walkY(),now+100));
                return;
            }
        }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END || PENDING.isEmpty())return;
        for(var entry:PENDING.entrySet())
        {
            var level=entry.getKey();if(level.getServer()!=event.getServer())continue;
            var iterator=entry.getValue().entrySet().iterator();
            while(iterator.hasNext())
            {
                var row=iterator.next();var request=row.getValue();var player=level.getServer().getPlayerList().getPlayer(row.getKey().player);
                if(player==null || player.level()!=level || !player.isAlive() || level.getGameTime()>request.until
                        || !level.hasChunkAt(request.controller)){iterator.remove();continue;}
                var spec=NervLiftPassengerSync.managedLifts(level).stream().filter(s->s.id().equals(request.lift)).findFirst().orElse(null);
                if(spec==null){iterator.remove();continue;}
                var landing=spec.stops().stream().filter(s->s.walkY()==request.floor).findFirst().orElse(null);
                if(landing==null || player.distanceToSqr(landing.cabinCentre().getCenter())>4096
                        || !(level.getBlockEntity(request.controller) instanceof ControllerBlockEntity block) || !block.hasGroup())
                {iterator.remove();continue;}
                var group=block.getGroup();
                if(group.facing!=request.facing || group.isMoving() || !NervLiftPassengerSync.carPresent(level,spec,landing))continue;
                var cells=spec.id().equals(NervLiftPassengerSync.GATEWAY)
                        ?RegionalGatewayDirector.arrivalDoorCells(request.floor)
                        :S20PhysicalElevatorDirector.movingDoorCells(spec,landing);
                for(var pos:cells)
                    player.connection.send(new ClientboundBlockUpdatePacket(pos,level.getBlockState(pos)));
                if(Boolean.getBoolean("projectseele.r43LiftCallTrace"))
                    ProjectSeele.LOGGER.info("R44 authoritative lift aperture replay after client cage placement: lift={} floor={} cells={} player={}",
                            spec.id(),landing.walkY(),cells.size(),player.getUUID());
                iterator.remove();
            }
        }
    }
    private NervLiftArrivalSyncR44() { }
}

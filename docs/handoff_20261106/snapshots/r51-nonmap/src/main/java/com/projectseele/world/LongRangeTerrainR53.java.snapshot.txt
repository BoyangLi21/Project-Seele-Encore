package com.projectseele.world;

import java.util.*;
import java.util.concurrent.CompletableFuture;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Load real shot terrain gradually; intermediate chunks do not run entities. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class LongRangeTerrainR53
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_long_ray",Comparator.comparingLong(ChunkPos::toLong),100);
    private static final Map<ServerLevel,State> LEVELS=new WeakHashMap<>();
    private static final class Ray
    {
        final Set<Long> chunks; final BlockPos from,to; long touched;
        Ray(Vec3 start,Vec3 end,long now)
        {
            from=BlockPos.containing(start);to=BlockPos.containing(end);touched=now;
            chunks=new LinkedHashSet<>();
            int steps=Math.max(1,(int)Math.ceil(start.subtract(end).horizontalDistance()/8));
            for(int i=0;i<=steps;i++)
            {
                var p=new ChunkPos(BlockPos.containing(start.lerp(end,i/(double)steps)));
                // Adjacent cells include collision shapes extending over a boundary.
                for(int x=-1;x<=1;x++)for(int z=-1;z<=1;z++)chunks.add(ChunkPos.asLong(p.x+x,p.z+z));
            }
        }
    }
    private static final class State
    {
        final Map<String,Ray> rays=new LinkedHashMap<>();
        final Map<Long,CompletableFuture<?>> pending=new HashMap<>();
    }
    public static boolean ready(ServerLevel level,String key,Vec3 from,Vec3 to)
    {
        if(from.distanceToSqr(to)<=1024D*1024)return true;
        if(!Double.isFinite(from.lengthSqr()+to.lengthSqr())||from.distanceToSqr(to)>8192D*8192)return false;
        var state=LEVELS.computeIfAbsent(level,l->new State());var ray=state.rays.get(key);
        if(ray==null||!ray.from.equals(BlockPos.containing(from))||!ray.to.equals(BlockPos.containing(to)))
        {
            ray=new Ray(from,to,level.getGameTime());state.rays.put(key,ray);
            while(state.rays.size()>16)state.rays.remove(state.rays.keySet().iterator().next());
        }
        ray.touched=level.getGameTime();
        for(long packed:ray.chunks)
        {var p=new ChunkPos(packed);if(level.getChunkSource().getChunkNow(p.x,p.z)==null)return false;}
        return true;
    }
    @SubscribeEvent public static void tick(TickEvent.LevelTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||!(event.level instanceof ServerLevel level))return;
        var state=LEVELS.get(level);if(state==null)return;long now=level.getGameTime();
        state.rays.values().removeIf(ray->now-ray.touched>100);
        state.pending.entrySet().removeIf(entry->entry.getValue().isDone());
        var wanted=new LinkedHashSet<Long>();for(var ray:state.rays.values())wanted.addAll(ray.chunks);
        int issued=0;
        for(long packed:wanted)
        {
            var p=new ChunkPos(packed);var chunks=level.getChunkSource();
            if(chunks.getChunkNow(p.x,p.z)!=null)
            {if(now%20==0)chunks.addRegionTicket(TICKET,p,0,p);continue;}
            if(issued>=2||state.pending.size()>=4||state.pending.containsKey(packed))continue;
            chunks.addRegionTicket(TICKET,p,0,p);
            state.pending.put(packed,chunks.getChunkFuture(p.x,p.z,ChunkStatus.FULL,true));issued++;
        }
    }
    private LongRangeTerrainR53(){}
}

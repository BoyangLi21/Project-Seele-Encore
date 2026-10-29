package com.projectseele.world;

import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.material.FluidState;
import net.minecraft.world.level.material.Fluids;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.Vec3;

/** Keep collision blocks along the two real firing rays, without ticking a 2 km entity corridor. */
public final class TvYashimaFirelineR53
{
    private static final TicketType<ChunkPos> TICKET = TicketType.create("yashima_fireline_blocks", Comparator.comparingLong(ChunkPos::toLong), 100);
    private static final Map<ServerLevel, Line> LINES = new WeakHashMap<>();
    private static final class Line
    {
        final long generation;
        final List<ChunkPos> chunks;
        int requested;
        Line(long generation, List<ChunkPos> chunks) { this.generation = generation;this.chunks = chunks; }
    }

    public static void retain(ServerLevel level, TvCampaignSavedData data, TvEncounterSitesR45.Site site)
    {
        var line = LINES.get(level);
        if (line == null || line.generation != data.generationR43)
        {
            clear(level);
            var chunks = new LinkedHashSet<ChunkPos>();
            var station = TvYashimaStationR52.plan(level).orElse(null);
            Vec3 muzzle = station == null ? site.hero() : station.geometry().point(station.raised(), new org.joml.Quaternionf(), station.geometry().muzzle());
            // Keep only the actual emplacement-to-target segment, not both
            // full weapon ranges and a three-chunk-wide unused corridor.
            addRay(chunks, muzzle, site.angel(), site.attackRange());
            addRay(chunks, site.angel(), site.hero(), site.attackRange());
            line = new Line(data.generationR43, List.copyOf(chunks));LINES.put(level, line);
        }
        int pending=0;
        for (int i = 0; i < line.requested; i++)
        {
            var chunk = line.chunks.get(i);
            // Distance zero gives a FULL block chunk, not an entity-ticking ticket.
            level.getChunkSource().addRegionTicket(TICKET, chunk, 0, chunk);
            if(level.getChunkSource().getChunkNow(chunk.x,chunk.z)==null)pending++;
        }
        for(int budget=4;budget>0&&pending<8&&line.requested<line.chunks.size();budget--)
        {
            var chunk=line.chunks.get(line.requested++);
            level.getChunkSource().addRegionTicket(TICKET,chunk,0,chunk);
            if(level.getChunkSource().getChunkNow(chunk.x,chunk.z)==null)pending++;
        }
    }

    static void addRay(Set<ChunkPos> result, Vec3 from, Vec3 target, double range)
    {
        Vec3 end = from.add(target.subtract(from).normalize().scale(Math.min(range,from.distanceTo(target))));
        BlockGetter.traverseBlocks(from,end,result,(chunks,pos)->{chunks.add(new ChunkPos(pos));return null;},chunks->null);
    }

    public static boolean ready(ServerLevel level, TvCampaignSavedData data)
    {
        // Loading is background work; it never gates the normal combat clock.
        if(!NervTraversalPolicyR53.strict(level))return true;
        var line = LINES.get(level);
        return line != null && line.generation == data.generationR43 && line.requested == line.chunks.size()
                && line.chunks.stream().allMatch(c -> level.getChunkSource().hasChunk(c.x, c.z));
    }

    /** Loaded blocks keep vanilla clipping. Normal play crosses unloaded gaps
     * without inventing walls; complete records whether terrain was unknown. */
    public record Trace(BlockHitResult hit,boolean complete) { }
    public static Trace clip(ServerLevel level,ClipContext context)
    {
        BlockGetter loaded=new BlockGetter()
        {
            @Override public BlockEntity getBlockEntity(BlockPos pos)
            {var chunk=level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4);return chunk==null?null:chunk.getBlockEntity(pos);}
            @Override public BlockState getBlockState(BlockPos pos)
            {var chunk=level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4);return chunk==null?Blocks.AIR.defaultBlockState():chunk.getBlockState(pos);}
            @Override public FluidState getFluidState(BlockPos pos)
            {var chunk=level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4);return chunk==null?Fluids.EMPTY.defaultFluidState():chunk.getFluidState(pos);}
            @Override public int getHeight(){return level.getHeight();}
            @Override public int getMinBuildHeight(){return level.getMinBuildHeight();}
        };
        Vec3 from=context.getFrom(),to=context.getTo();
        var direction=Direction.getNearest(from.x-to.x,from.y-to.y,from.z-to.z);
        boolean strict=NervTraversalPolicyR53.strict(level);
        boolean[] gap={false};
        return BlockGetter.traverseBlocks(from,to,context,(ray,pos)->
        {
            if(level.isOutsideBuildHeight(pos))return null;
            var chunk=level.getChunkSource().getChunkNow(pos.getX()>>4,pos.getZ()>>4);
            if(chunk==null)
            {
                // A changed aim can leave the retained corridor. Request only
                // this first missing chunk; never load it in the firing tick.
                if(!gap[0]){var missing=new ChunkPos(pos);level.getChunkSource().addRegionTicket(TICKET,missing,0,missing);}
                gap[0]=true;
                if(!strict)return null;
                var at=new AABB(pos).clip(from,to).orElse(from);
                return new Trace(BlockHitResult.miss(at,direction,pos.immutable()),false);
            }
            var state=chunk.getBlockState(pos);
            var block=loaded.clipWithInteractionOverride(from,to,pos,ray.getBlockShape(state,loaded,pos),state);
            var fluid=ray.getFluidShape(chunk.getFluidState(pos),loaded,pos).clip(from,to,pos);
            double blockDistance=block==null?Double.MAX_VALUE:from.distanceToSqr(block.getLocation());
            double fluidDistance=fluid==null?Double.MAX_VALUE:from.distanceToSqr(fluid.getLocation());
            var hit=blockDistance<=fluidDistance?block:fluid;
            return hit==null?null:new Trace(hit,!gap[0]);
        },ray->new Trace(BlockHitResult.miss(to,direction,BlockPos.containing(to)),!gap[0]));
    }

    public static void clear(ServerLevel level)
    {
        var line = LINES.remove(level);if (line == null) return;
        for (int i = 0; i < line.requested; i++)
        {
            var chunk = line.chunks.get(i);level.getChunkSource().removeRegionTicket(TICKET, chunk, 0, chunk);
        }
    }
    private TvYashimaFirelineR53() { }
}

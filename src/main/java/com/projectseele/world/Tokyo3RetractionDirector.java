package com.projectseele.world;

import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.registry.ModBlocks;
import com.projectseele.world.Tokyo3RetractionSavedData.StoredDistrict;
import net.minecraft.core.BlockPos;
import net.minecraft.core.SectionPos;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Tick-budgeted, persistent travel of every generated Tokyo-3 high-rise. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class Tokyo3RetractionDirector
{
    /**
     * A complete emergency descent must read as a coordinated mechanical
     * operation, not a nine-minute background migration.  Five ticks still
     * leaves several rendered frames between committed layers while the
     * bounded imported-tower cursor keeps individual server ticks small.
     */
    public static final int TICKS_PER_LAYER = 5;
    /**
     * Towers of one layer are stepped across this many ticks. The client
     * retraction audit needs a settled skyline for twelve consecutive ticks
     * inside every layer period, so this has to stay a small fraction of
     * {@link #TICKS_PER_LAYER}.
     */
    private static final int LAYER_SPREAD_TICKS = 2;
    /**
     * Long-lived, non-persistent load ticket. The order is given from the
     * GeoFront command centre some five hundred blocks below the skyline,
     * where none of the district is resident: without a ticket the travel
     * either never starts or makes every placement block on a chunk load.
     * One claim covers the complete 312-layer route and is released at the end.
     */
    private static final TicketType<ChunkPos> TRAVEL_TICKET = TicketType.create(
            "projectseele_tokyo3_travel", Comparator.comparingLong(ChunkPos::toLong),
            // A complete cargo transfer may outlast the former six-minute TTL.
            // Runtime tickets are removed at completion/fault and vanish when
            // the server closes; an acquired cursor must never outlive its ticket.
            0);
    private static final int TICKET_CLAIMS_PER_TICK = 12;
    private static final Map<TravelKey, long[]> TRAVEL_CHUNKS = new ConcurrentHashMap<>();
    /** How much of {@link #travelChunks} each district has claimed so far. */
    private static final Map<TravelKey, Integer> TICKET_CURSOR = new ConcurrentHashMap<>();
    /** Block-work cost of the travel in progress, per district origin. */
    private static final Map<TravelKey, TravelCost> TRAVEL_COST = new ConcurrentHashMap<>();
    /** Districts whose stray masts have been swept this server session. */
    private static final java.util.Set<TravelKey> SWEPT_ORIGINS =
            java.util.concurrent.ConcurrentHashMap.newKeySet();
    private static final double CORE_CONTROL_RANGE = 150.0D;

    private Tokyo3RetractionDirector() {}

    public static void register(ServerLevel level, BlockPos origin)
    {
        if(CityCreateDistrictR45.owns(level,origin))return;
        retireLegacyS20Districts(level, origin);
        StoredDistrict district = ensure(level, origin);
        if (!SeeleConfig.dynamicTokyo3RetractionEnabled())
        {
            return;
        }
        updateCoreStates(level, origin,
                district.depth() > 0 || district.targetDepth() > 0);
        // During a journalled layer some roofs have already moved while the
        // shared depth still describes the preceding frame. They are cargo,
        // not stale caps that startup maintenance may erase.
        if (district.depth() != district.targetDepth()
                || district.cursor() != 0 || district.voxelCursor() != 0) return;
        // Self-heal the lightning-rod pillars a pre-fix ascent left behind,
        // once per district per session, without waiting for a retract order.
        if (SWEPT_ORIGINS.add(travelKey(level,origin)))
        {
            acquireTravelTickets(level, origin);
            if (districtLoaded(level, origin))
            {
                int removedCaps = ThirdTokyoSurfaceBuilder.sweepLegacySurfaceCaps(level,
                        origin, district.depth());
                ThirdTokyoSurfaceBuilder.sweepStrayMasts(level, origin,
                        district.depth());
                if (district.depth() == district.targetDepth()
                        && district.cursor() == 0
                        && district.voxelCursor() == 0)
                {
                    releaseTravelTickets(level, origin);
                }
                ProjectSeele.LOGGER.info(
                        "Tokyo-3 exact legacy surface maintenance completed at {}: removedCaps={}",
                        origin.toShortString(), removedCaps);
            }
            else
            {
                // Chunks not resident yet; let a later register() retry.
                SWEPT_ORIGINS.remove(travelKey(level,origin));
            }
        }
    }

    /** Deterministic reset reserved for isolated unattended visual fixtures. */
    public static void reset(ServerLevel level, BlockPos origin)
    {
        if(CityCreateDistrictR45.owns(level,origin))throw new IllegalStateException("Installed rigid city requires its explicit recovery transaction");
        Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                origin, 0, 0, level.getGameTime()));
        updateCoreStates(level, origin, false);
    }

    public static int depth(ServerLevel level, BlockPos origin)
    {
        if(CityCreateDistrictR45.owns(level,origin))return CityCreateDistrictR45.status(level,origin).depth();
        return ensure(level, origin).depth();
    }

    public static RequestResult request(ServerLevel level, BlockPos origin,
                                        boolean retract)
    {
        if (!retract && CityBattlefieldR29.combatActive(level))
            return new RequestResult(false, "城市中心正在交战，请先结束或取消作战，再恢复城市。");
        if(CityCreateDistrictR45.owns(level,origin))
        {
            if(!SeeleConfig.dynamicTokyo3RetractionEnabled())return new RequestResult(false,"城市升降已在设置中关闭。");
            if(!retract&&BattlefieldR21.deferRestore(level))return new RequestResult(true,"先恢复街面设施，再展开城市。");
            return CityCreateDistrictR45.request(level,origin,retract);
        }
        retireLegacyS20Districts(level, origin);
        if (!SeeleConfig.dynamicTokyo3RetractionEnabled())
        {
            return new RequestResult(false,
                    "Tokyo-3 tower motion is inhibited by performance rescue mode.");
        }
        StoredDistrict current = ensure(level, origin);
        if (current.faulted())
        {
            return new RequestResult(false,
                    "Tokyo-3 travel is fail-closed: " + current.fault()
                            + " Use the explicit maintenance command after repairing the obstruction.");
        }
        int target = retract
                ? ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin) : 0;
        boolean layerInFlight = current.cursor() > 0
                || current.voxelCursor() > 0;
        if (layerInFlight)
        {
            if (current.queuedTargetDepth() == target
                    || (current.queuedTargetDepth() < 0
                        && current.targetDepth() == target))
            {
                return new RequestResult(false, retract
                        ? "Tokyo-3 armour towers are already descending."
                        : "Tokyo-3 armour towers are already rising.");
            }
            // Never synchronously finish a half-written building merely because
            // the operator reverses direction.  Preserve the active layer's
            // traversal order and persist the desired direction for the first
            // safe boundary after that layer commits.
            Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                    current.origin(), current.depth(), current.targetDepth(),
                    current.nextStepAt(), current.cursor(),
                    current.voxelCursor(), target));
            return new RequestResult(true, retract
                    ? "Tokyo-3 reversal queued: active layer will finish before descent."
                    : "Tokyo-3 reversal queued: active layer will finish before ascent.");
        }
        if (current.depth() == target && current.targetDepth() == target)
        {
            return new RequestResult(false, retract
                    ? "Tokyo-3 armour towers are already fully retracted."
                    : "Tokyo-3 armour towers are already at street level.");
        }
        if (current.depth() == target)
        {
            // A held request has not started a layer. Cancelling it reaches
            // the current endpoint immediately, so no later layer tick exists
            // to release the tickets on our behalf.
            Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                    origin, target, target, level.getGameTime()));
            updateCoreStates(level, origin, retract);
            releaseTravelTickets(level, origin);
            return new RequestResult(true, "Tokyo-3 held movement cancelled at its unchanged endpoint.");
        }
        if (current.targetDepth() == target && current.depth() != target)
        {
            return new RequestResult(false, retract
                    ? "Tokyo-3 armour towers are already descending."
                    : "Tokyo-3 armour towers are already rising.");
        }

        if(!retract&&BattlefieldR21.deferRestore(level))return new RequestResult(true,"Restoring street fixtures before the city rises.");
        acquireTravelTickets(level, origin);
        if (current.depth() == current.targetDepth())
        {
            LocalMapAssetLoader.repairTokyo3TravelArtifacts(level, origin, current.depth());
            ThirdTokyoSurfaceBuilder.sweepLegacySurfaceCaps(level, origin, current.depth());
            ThirdTokyoSurfaceBuilder.sweepStrayMasts(level, origin, current.depth());
        }
        Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                origin, current.depth(), target, level.getGameTime() + TICKS_PER_LAYER));
        updateCoreStates(level, origin, retract);
        level.playSound(null, origin, retract ? SoundEvents.PISTON_CONTRACT
                : SoundEvents.PISTON_EXTEND, SoundSource.BLOCKS, 4.0F, 0.55F);
        ProjectSeele.LOGGER.info("Tokyo-3 armour towers {} requested at {} depth={}/{}",
                retract ? "retraction" : "restoration", origin.toShortString(),
                current.depth(), target);
        return new RequestResult(true, retract
                ? "Tokyo-3 emergency configuration: armour towers descending."
                : "Tokyo-3 all-clear configuration: armour towers rising.");
    }

    /** Retires state-only legacy origins; never edits the human-authored map. */
    private static void retireLegacyS20Districts(ServerLevel level,
                                                  BlockPos retainedOrigin)
    {
        if (!FacilityWorldPolicy.isS20Rebuild(level.getServer())
                || !retainedOrigin.equals(
                IntegratedNervMapBuilder.tokyo3Origin(level)))
        {
            return;
        }
        for (StoredDistrict retired
                : Tokyo3RetractionSavedData.get(level)
                .removeAllExcept(retainedOrigin))
        {
            releaseTravelTickets(level, retired.origin());
            TravelKey key = travelKey(level,retired.origin());
            TRAVEL_CHUNKS.remove(key);
            TICKET_CURSOR.remove(key);
            TRAVEL_COST.remove(key);
            SWEPT_ORIGINS.remove(key);
            ProjectSeele.LOGGER.warn(
                    "Retired legacy Tokyo-3 movement origin {} in S20; canonical origin is {}",
                    retired.origin().toShortString(),
                    retainedOrigin.toShortString());
        }
    }

    /**
     * Queues an operator-requested maintenance movement on the same bounded,
     * journalled path as the cinematic control.  This method deliberately does
     * no synchronous district rewrite: command, recovery and control-console
     * entry points must not create a second transaction implementation.
     */
    public static RequestResult forceDepth(ServerLevel level, BlockPos origin,
                                           boolean retract)
    {
        if(CityCreateDistrictR45.owns(level,origin))return request(level,origin,retract);
        if (!SeeleConfig.dynamicTokyo3RetractionEnabled())
        {
            return new RequestResult(false,
                    "Tokyo-3 rapid block travel is inhibited by performance rescue mode.");
        }
        StoredDistrict current = ensure(level, origin);
        int target = retract
                ? ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin) : 0;
        if (current.faulted())
        {
            acquireTravelTickets(level, origin);
            Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                    current.origin(), current.depth(), current.targetDepth(),
                    level.getGameTime(), current.cursor(),
                    current.voxelCursor(), target, ""));
            return new RequestResult(true,
                    "Tokyo-3 fail-closed layer retry armed; the saved cursor and source direction are preserved.");
        }
        if (current.cursor() > 0 || current.voxelCursor() > 0)
        {
            Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                    current.origin(), current.depth(), current.targetDepth(),
                    current.nextStepAt(), current.cursor(),
                    current.voxelCursor(), target));
            return new RequestResult(true,
                    "Tokyo-3 bounded maintenance queued after the active layer transaction.");
        }
        if (current.depth() == target)
        {
            Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                    origin, target, target, level.getGameTime()));
            updateCoreStates(level, origin, retract);
            return new RequestResult(false, retract
                    ? "Tokyo-3 armour towers are already fully retracted."
                    : "Tokyo-3 armour towers are already at street level.");
        }

        acquireTravelTickets(level, origin);
        Tokyo3RetractionSavedData.get(level).put(new StoredDistrict(
                origin, current.depth(), target, level.getGameTime()));
        updateCoreStates(level, origin, retract);
        return new RequestResult(true, retract
                ? "Tokyo-3 bounded maintenance: armour towers are descending."
                : "Tokyo-3 bounded maintenance: armour towers are rising.");
    }
    public static RequestResult toggleNearest(ServerLevel level, BlockPos position)
    {
        var rigid=CityCreateDistrictR45.requestCore(level,position);if(rigid!=null)return rigid;
        return Tokyo3RetractionSavedData.get(level)
                .nearest(position, CORE_CONTROL_RANGE)
                .map(district -> request(level, district.origin(),
                        district.targetDepth() == 0))
                .orElseGet(() -> new RequestResult(false,
                        "No registered Tokyo-3 district is linked to this core."));
    }

    public static Status status(ServerLevel level, BlockPos origin)
    {
        if(CityCreateDistrictR45.owns(level,origin))return CityCreateDistrictR45.status(level,origin);
        StoredDistrict district = ensure(level, origin);
        String phase;
        if (district.faulted())
        {
            phase = "FAULT";
        }
        else if (district.queuedTargetDepth() >= 0)
        {
            phase = district.queuedTargetDepth() > district.depth()
                    ? "REVERSAL_QUEUED_DESCENT"
                    : "REVERSAL_QUEUED_ASCENT";
        }
        else if (district.depth() == district.targetDepth())
        {
            phase = district.depth() == 0 ? "DEPLOYED" : "RETRACTED";
        }
        else
        {
            phase = district.targetDepth() > district.depth()
                    ? "DESCENDING" : "RISING";
        }
        return new Status(phase, district.depth(), district.targetDepth(),
                ThirdTokyoSurfaceBuilder.maximumRetractionDepth(origin));
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END
                || !SeeleConfig.dynamicTokyo3RetractionEnabled())
        {
            return;
        }
        MinecraftServer server = event.getServer();
        for (ServerLevel level : server.getAllLevels())
        {
            tickLevel(level);
        }
    }

    private static void tickLevel(ServerLevel level)
    {
        Tokyo3RetractionSavedData data = Tokyo3RetractionSavedData.get(level);
        long gameTime = level.getGameTime();
        for (StoredDistrict district : data.districts())
        {
            if(CityCreateDistrictR45.owns(level,district.origin()))continue;
            if (district.faulted())
            {
                continue;
            }
            if (district.depth() == district.targetDepth())
            {
                continue;
            }
            boolean layerInFlight = district.cursor() > 0
                    || district.voxelCursor() > 0;
            if (!layerInFlight && gameTime < district.nextStepAt())
            {
                continue;
            }
            /*
             * Ticket claims are runtime-only, while the per-building cursor
             * is persistent.  Reacquire even for an in-flight layer after a
             * save reload; otherwise a city saved halfway through an imported
             * tower (for example cursor 94 / voxel 14516) can never load the
             * chunks required to finish that same transaction.
             */
            acquireTravelTickets(level, district.origin());
            if (!districtLoaded(level, district.origin()))
            {
                // The tickets were only just issued; retry once they resolve.
                continue;
            }

            int direction = Integer.signum(district.targetDepth() - district.depth());
            int nextDepth = district.depth() + direction;
            if (travelOccupied(
                    level, district.origin(), district.depth(), nextDepth))
            {
                data.put(new StoredDistrict(district.origin(), district.depth(),
                        district.targetDepth(), gameTime + TICKS_PER_LAYER,
                        district.cursor(), district.voxelCursor(), district.queuedTargetDepth()));
                continue;
            }

            int generatedTowers = ThirdTokyoSurfaceBuilder.movableBuildings().size();
            int importedTowers = LocalMapAssetLoader.tokyo3SkyscraperCount();
            int towers = generatedTowers + importedTowers;
            int reached = district.cursor();
            int voxelCursor = district.voxelCursor();
            long started = System.nanoTime();
            if (reached < generatedTowers)
            {
                int writes=0;
                while(reached<generatedTowers&&writes<4096
                        &&System.nanoTime()-started<8_000_000L)
                {
                    Tokyo3BuildingArchiveR44.TravelStep step=
                            ThirdTokyoSurfaceBuilder.stepRetractionDepthR44(level,
                            district.origin(), district.depth(), nextDepth,
                            reached,voxelCursor);
                    writes+=step.writes();voxelCursor=step.cursor();
                    if(step.failed())
                    {
                        String fault="generatedTower="+reached+" depth="+district.depth()
                                +"->"+nextDepth+" cursor="+step.cursor()+" "+step.fault();
                        data.put(new StoredDistrict(district.origin(),district.depth(),
                                district.targetDepth(),gameTime+TICKS_PER_LAYER,reached,
                                voxelCursor,district.queuedTargetDepth(),fault));
                        releaseTravelTickets(level,district.origin());
                        TRAVEL_COST.remove(travelKey(level,district.origin()));
                        ProjectSeele.LOGGER.error("Tokyo-3 cargo stopped fail-closed at {} {}",
                                district.origin().toShortString(),fault);
                        break;
                    }
                    if(!step.complete())break;
                    reached++;voxelCursor=0;
                }
                if(data.get(district.origin()).map(StoredDistrict::faulted).orElse(false))continue;
            }
            else if (reached < towers)
            {
                LocalMapAssetLoader.SkyscraperTravelStep step =
                        LocalMapAssetLoader.stepTokyo3RetractionDepth(level,
                                district.origin(), district.depth(), nextDepth,
                                reached - generatedTowers, voxelCursor);
                if (step.failed())
                {
                    String fault = "tower=" + (reached - generatedTowers)
                            + " depth=" + district.depth() + "->" + nextDepth
                            + " cursor=" + step.cursor();
                    data.put(new StoredDistrict(district.origin(),
                            district.depth(), district.targetDepth(),
                            gameTime + TICKS_PER_LAYER, reached,
                            step.cursor(), district.queuedTargetDepth(), fault));
                    releaseTravelTickets(level, district.origin());
                    TRAVEL_COST.remove(travelKey(level,district.origin()));
                    ProjectSeele.LOGGER.error(
                            "Tokyo-3 travel stopped fail-closed at {} {}",
                            district.origin().toShortString(), fault);
                    continue;
                }
                voxelCursor = step.cursor();
                if (step.complete())
                {
                    reached++;
                    voxelCursor = 0;
                }
            }
            TRAVEL_COST.computeIfAbsent(travelKey(level,district.origin()), key -> new TravelCost())
                    .layerNanos += System.nanoTime() - started;
            // The next layer's dwell begins when this one starts. A detailed
            // imported building may legitimately take longer: bounded world
            // writes are more important than forcing a one-second tick spike.
            long nextStepAt = layerInFlight
                    ? district.nextStepAt() : gameTime + TICKS_PER_LAYER;
            if (reached < towers)
            {
                data.put(new StoredDistrict(district.origin(), district.depth(),
                        district.targetDepth(), nextStepAt, reached,
                        voxelCursor, district.queuedTargetDepth()));
                continue;
            }

            emitLayerEffect(level, district.origin(), direction > 0);
            boolean targetChanged = district.queuedTargetDepth() >= 0;
            int committedTarget = targetChanged
                    ? district.queuedTargetDepth() : district.targetDepth();
            data.put(new StoredDistrict(district.origin(), nextDepth,
                    committedTarget, nextStepAt));
            if (targetChanged)
            {
                updateCoreStates(level, district.origin(),
                        committedTarget > nextDepth);
            }
            TravelCost cost = TRAVEL_COST.get(travelKey(level,district.origin()));
            cost.closeLayer();
            if (nextDepth == committedTarget)
            {
                boolean retracted = nextDepth > 0;
                updateCoreStates(level, district.origin(), retracted);
                releaseTravelTickets(level, district.origin());
                level.playSound(null, district.origin(), SoundEvents.IRON_DOOR_CLOSE,
                        SoundSource.BLOCKS, 5.0F, retracted ? 0.55F : 0.85F);
                TRAVEL_COST.remove(travelKey(level,district.origin()));
                // A layer has to stay small against the 50ms tick budget. Peak
                // is the number that matters: it used to be the whole district
                // rewritten inside a single tick.
                ProjectSeele.LOGGER.info(
                        "Tokyo-3 armour towers {} at {} depth={} towers={} "
                                + "layers={} blockWork={}ms peakLayer={}ms",
                        retracted ? "fully retracted" : "fully restored",
                        district.origin().toShortString(), nextDepth, towers,
                        cost.layers, cost.totalNanos / 1_000_000L,
                        cost.peakNanos / 1_000_000L);
            }
        }
    }

    /** Every chunk a tower lot touches, so travel never waits on a chunk load. */
    private static TravelKey travelKey(ServerLevel level,BlockPos origin)
    {
        return new TravelKey(Tokyo3BuildingWorldIdentityR44.get(level),
                level.dimension().location().toString(),origin.asLong());
    }

    private record TravelKey(String worldUUID,String dimension,long origin) {}

    private static long[] travelChunks(ServerLevel level,BlockPos origin)
    {
        return TRAVEL_CHUNKS.computeIfAbsent(travelKey(level,origin), key ->
        {
            Set<Long> chunks = new LinkedHashSet<>();
            for (ThirdTokyoSurfaceBuilder.TowerSpec tower
                    : ThirdTokyoSurfaceBuilder.movableBuildings(level))
            {
                int half = tower.halfSize();
                int centreX = origin.getX() + tower.x();
                int centreZ = origin.getZ() + tower.z();
                for (int x = SectionPos.blockToSectionCoord(centreX - half);
                     x <= SectionPos.blockToSectionCoord(centreX + half); x++)
                {
                    for (int z = SectionPos.blockToSectionCoord(centreZ - half);
                         z <= SectionPos.blockToSectionCoord(centreZ + half); z++)
                    {
                        chunks.add(ChunkPos.asLong(x, z));
                    }
                }
            }
            LocalMapAssetLoader.addTokyo3SkyscraperTravelChunks(origin, chunks);
            return chunks.stream().mapToLong(Long::longValue).toArray();
        });
    }

    /**
     * Claims the travel chunks a slice at a time. A cold district is some three
     * hundred chunks, and claiming them in one tick costs a second of chunk
     * loading up front; {@link #districtLoaded} holds the first layer back
     * until they have all arrived either way, so the ramp is free.
     */
    static void acquireTravelTickets(ServerLevel level, BlockPos origin)
    {
        long[] chunks = travelChunks(level,origin);
        int claimed = TICKET_CURSOR.getOrDefault(travelKey(level,origin), 0);
        if (claimed >= chunks.length)
        {
            return;
        }
        int end = Math.min(chunks.length,
                claimed + TICKET_CLAIMS_PER_TICK);
        for (int index = claimed; index < end; index++)
        {
            ChunkPos chunk = new ChunkPos(chunks[index]);
            level.getChunkSource().addRegionTicket(TRAVEL_TICKET, chunk, 0, chunk);
        }
        TICKET_CURSOR.put(travelKey(level,origin), end);
    }

    private static void releaseTravelTickets(ServerLevel level, BlockPos origin)
    {
        TICKET_CURSOR.remove(travelKey(level,origin));
        for (long packed : travelChunks(level,origin))
        {
            ChunkPos chunk = new ChunkPos(packed);
            level.getChunkSource().removeRegionTicket(TRAVEL_TICKET, chunk, 0, chunk);
        }
    }

    private static StoredDistrict ensure(ServerLevel level, BlockPos origin)
    {
        Tokyo3RetractionSavedData data = Tokyo3RetractionSavedData.get(level);
        return data.get(origin).orElseGet(() -> {
            StoredDistrict created = new StoredDistrict(origin, 0, 0,
                    level.getGameTime());
            data.put(created);
            return created;
        });
    }

    /**
     * Only the tower lots are written, and only those are ticketed. Gating on
     * the far district corners instead would stall the travel forever whenever
     * the order is given from underground.
     */
    static boolean districtLoaded(ServerLevel level, BlockPos origin)
    {
        for (long packed : travelChunks(level,origin))
        {
            ChunkPos chunk = new ChunkPos(packed);
            if (!level.hasChunk(chunk.x, chunk.z))
            {
                return false;
            }
        }
        return true;
    }

    static boolean travelOccupied(ServerLevel level, BlockPos origin,
                                          int oldDepth, int newDepth)
    {
        for (ThirdTokyoSurfaceBuilder.TowerSpec tower
                : ThirdTokyoSurfaceBuilder.movableBuildings(level))
        {
            int oldVisible = Math.max(0, tower.height() - oldDepth);
            int newVisible = Math.max(0, tower.height() - newDepth);
            BlockPos centre = origin.offset(tower.x(), 0, tower.z());
            int half = tower.halfSize();
            int maximumVisible = Math.max(oldVisible, newVisible);
            AABB layer = new AABB(
                    centre.getX() - half, centre.getY(),
                    centre.getZ() - half,
                    centre.getX() + half + 1,
                    centre.getY() + maximumVisible + 5,
                    centre.getZ() + half + 1);
            if (!level.getEntitiesOfClass(LivingEntity.class, layer,
                    entity -> entity.isAlive() && !entity.isSpectator()).isEmpty())
            {
                return true;
            }
            int roof=origin.getY()+ThirdTokyoSurfaceBuilder.ceilingRoofRelativeY(tower,origin);
            int travel=Math.max(tower.height(),origin.getY()-roof);
            int below=Math.max(0,Math.min(tower.height(),Math.max(oldDepth,newDepth)-travel));
            if(below>0&&!level.getEntitiesOfClass(LivingEntity.class,new AABB(
                    centre.getX()-half,roof-below-2,centre.getZ()-half,
                    centre.getX()+half+1,roof+4,centre.getZ()+half+1),
                    entity->entity.isAlive()&&!entity.isSpectator()).isEmpty())return true;
        }
        return LocalMapAssetLoader.tokyo3SkyscraperTravelOccupied(
                level, origin, oldDepth, newDepth);
    }

    private static void emitLayerEffect(ServerLevel level, BlockPos origin,
                                        boolean retracting)
    {
        BlockParticleOption dust = new BlockParticleOption(ParticleTypes.BLOCK,
                net.minecraft.world.level.block.Blocks.DEEPSLATE_TILES.defaultBlockState());
        int index = 0;
        for (ThirdTokyoSurfaceBuilder.TowerSpec tower
                : ThirdTokyoSurfaceBuilder.movableBuildings())
        {
            if ((index++ & 3) != 0)
            {
                continue;
            }
            BlockPos centre = origin.offset(tower.x(), 1, tower.z());
            level.sendParticles(dust, centre.getX() + 0.5D,
                    centre.getY() + 0.25D, centre.getZ() + 0.5D,
                    6, tower.halfSize() * 0.6D, 0.3D,
                    tower.halfSize() * 0.6D, 0.04D);
        }
        level.playSound(null, origin, retracting ? SoundEvents.PISTON_CONTRACT
                : SoundEvents.PISTON_EXTEND, SoundSource.BLOCKS, 3.2F,
                retracting ? 0.48F : 0.65F);
    }

    private static void updateCoreStates(ServerLevel level, BlockPos origin, boolean armed)
    {
        if(CityCreateDistrictR45.owns(level,origin))return;
        for (ThirdTokyoSurfaceBuilder.TowerSpec tower
                : ThirdTokyoSurfaceBuilder.armouredTowers())
        {
            BlockPos core = origin.offset(tower.x(), 0, tower.z());
            // This status refresh also runs while the player is deep below or
            // far from the city. Never synchronously acquire a remote chunk
            // from inside the server-tick registration pass.
            var loaded = level.getChunkSource().getChunkNow(core.getX() >> 4, core.getZ() >> 4);
            if (loaded == null) continue;
            BlockState state = loaded.getBlockState(core);
            if (state.is(ModBlocks.RETRACTABLE_BUILDING_CORE.get())
                    && state.getValue(RetractableBuildingCoreBlock.ARMED) != armed)
            {
                level.setBlock(core,
                        state.setValue(RetractableBuildingCoreBlock.ARMED, armed),
                        net.minecraft.world.level.block.Block.UPDATE_CLIENTS);
                PerformanceCounters.recordWorldBlockWrites(1);
            }
        }
    }

    private static final class TravelCost
    {
        private long layerNanos;
        private long totalNanos;
        private long peakNanos;
        private int layers;

        private void closeLayer()
        {
            this.totalNanos += this.layerNanos;
            this.peakNanos = Math.max(this.peakNanos, this.layerNanos);
            this.layerNanos = 0L;
            this.layers++;
        }
    }

    public record RequestResult(boolean accepted, String message) {}

    /** Endpoint depth is transaction metadata, not the distance travelled by a rigid building. */
    public record Status(String phase, int depth, int targetDepth, int maximumDepth, Motion motion)
    {
        public Status(String phase, int depth, int targetDepth, int maximumDepth)
        {
            this(phase, depth, targetDepth, maximumDepth, Motion.UNAVAILABLE);
        }

        public String motionReport()
        {
            String direction = targetDepth > depth ? "下降" : "上升";
            if (motion.total() > 0 && motion.observed() > 0)
            {
                direction = motion.descending() ? "下降" : "上升";
                String distance = Math.abs(motion.maximumMetres() - motion.minimumMetres()) < .05
                        ? String.format(java.util.Locale.ROOT, "%.1f", motion.minimumMetres())
                        : String.format(java.util.Locale.ROOT, "%.1f～%.1f", motion.minimumMetres(), motion.maximumMetres());
                String state = phase.contains("FAULT") ? "，故障停止"
                        : phase.contains("OCCUPIED") ? "，受阻暂停"
                        : phase.contains("HOLD") ? "，检查暂停"
                        : phase.contains("MOVE") ? "，正在移动"
                        : phase.contains("REPLAY") ? "，正在恢复升降事务"
                        : phase.contains("SPAWN") || phase.contains("READY") ? "，正在接入升降机构" : "，正在归位校验";
                String coverage = motion.observed() == motion.total() ? ""
                        : "（已核实 " + motion.observed() + "/" + motion.total() + " 栋，其余待确认）";
                return "城市楼体实际已" + direction + " " + distance + " 米" + coverage + state + "。";
            }
            if (phase.contains("FAULT")) return "城市升降故障停止；实际楼体位置尚未完整核实。";
            if (phase.equals("RIGID_IDLE") || phase.equals("DEPLOYED") || phase.equals("RETRACTED"))
                return depth == 0 ? "城市已上升到地表。" : "城市已下降到地下。";
            if (phase.contains("MOVE") || phase.contains("LOADING") || phase.contains("DISABLED"))
                return "城市升降状态读取尚未就绪；实际楼体位置尚未完整核实。";
            if (phase.contains("REPLAY") || phase.contains("RECONCILE"))
                return "城市正在恢复升降事务；实际楼体位置尚未完整核实。";
            if (phase.contains("FLUSH") || phase.contains("COMMIT"))
                return "城市楼体已到达" + (targetDepth == 0 ? "地表" : "地下") + "，正在归位校验。";
            if (phase.contains("PLACE") || phase.contains("COVER"))
                return "城市楼体正在归位校验；实际楼体位置尚未完整核实。";
            return "城市正在准备" + direction + (phase.contains("BLOCKED") ? "，请求受阻，楼体尚未开始移动。"
                    : phase.contains("OCCUPIED") ? "，等待运动区域清空。" : "，楼体尚未开始移动。");
        }

        /** Mean of the 96 original owners' actual positions, only when all are observed. */
        public float physicalRetractionFraction()
        {
            if (motion.total() > 0 && motion.observed() == motion.total())
                return (float) motion.meanRetractionFraction();
            if (phase.equals("RIGID_IDLE") || phase.equals("DEPLOYED") || phase.equals("RETRACTED"))
                return depth == 0 ? 0F : 1F;
            return -1F;
        }
    }

    /** Metres come only from the original server-side moving owners' current Y positions. */
    public record Motion(boolean descending, double minimumMetres, double maximumMetres, int observed, int total,
                         double meanRetractionFraction)
    {
        public static final Motion UNAVAILABLE = new Motion(false, 0, 0, 0, 0, -1);
    }
}

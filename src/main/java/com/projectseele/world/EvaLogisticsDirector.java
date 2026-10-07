package com.projectseele.world;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.Comparator;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.registry.ModEntities;
import com.projectseele.visual.GeoFrontCommands;
import com.projectseele.world.EvaFleetSavedData.FleetEntry;
import com.projectseele.world.EvaFleetSavedData.Phase;
import net.minecraft.ChatFormatting;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.world.ForgeChunkManager;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Persistent wet-cage, rail-transfer, launch and recovery state machine. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class EvaLogisticsDirector
{
    private static final int FLUID_LAYER_TICKS = 4;
    private static final int BRIDGE_RETRACTION_TICKS = 40;
    private static final int PLUG_LOCK_TICKS = 60;
    /** Two seconds for the opposed wet-cage clamps to fold clear. */
    private static final int RESTRAINT_TRAVEL_TICKS = 40;
    private static final int INSERTION_ABORT_TICKS =
            EntryPlugDirector.INSERTION_TICKS + 80;
    /** Slow, readable wet-cage rail speed; duration is derived from route length. */
    private static final double HORIZONTAL_BLOCKS_PER_TICK = 0.35D;
    private static final double VERTICAL_BLOCKS_PER_TICK = 2.0D;
    private static final double RECOVERY_RADIUS = 10.0D;
    private static final double RECOVERY_MAX_SPEED_SQR = 0.0025D;
    private static final int MAP_RADIUS = 400;
    private static final int ROUTE_CHUNK_MARGIN = 16;
    /** Keep station entity attachment alive until the readiness check completes. */
    private static final TicketType<ChunkPos> STATION_LOAD_TICKET = TicketType.create(
            "projectseele_station_attach", Comparator.comparingLong(ChunkPos::toLong), 100);
    private static final Map<UUID, Boolean> ROUTE_TICKET_STATE = new HashMap<>();
    private static final Map<UUID, Long> PHASE_STARTED_AT = new HashMap<>();
    private static final Map<UUID, Integer> LAST_ENTITY_TICK = new HashMap<>();
    private static final Map<UUID, Integer> DORMANT_LAUNCH_TICKS = new HashMap<>();
    private static final Map<UUID, Integer> DRAIN_ZERO_TICKS = new HashMap<>();
    private static final Set<ServerLevel> VERIFIED_INFRASTRUCTURE =
            Collections.newSetFromMap(new IdentityHashMap<>());
    private static final Set<ServerLevel> RESCUE_TICKETS_RELEASED =
            Collections.newSetFromMap(new IdentityHashMap<>());
    private static final Map<ServerLevel, Long> FLEET_STATION_LOAD_DEADLINE =
            new IdentityHashMap<>();
    private static final Set<ServerLevel> FLEET_STATIONS_SETTLED =
            Collections.newSetFromMap(new IdentityHashMap<>());

    private EvaLogisticsDirector() {}

    /** Enforces the world-global UUID contract as entities enter loaded chunks. */
    public static boolean validateCanonical(EvaUnit01Entity unit)
    {
        if(com.projectseele.visual.CombatR31Review.ownsFixture(unit))return true;
        if(com.projectseele.visual.RuntimeR44ServerProbe.ownsFixture(unit))return true;
        if (unit.isExperimentalUnit()) return true;
        if (!(unit.level() instanceof ServerLevel level))
        {
            return true;
        }
        int variant = unit.getUnitVariant();
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        FleetEntry current = data.entry(variant).orElse(null);
        if (current == null)
        {
            ProjectSeele.LOGGER.warn(
                    "EVA-0{} {} entered a loaded chunk without a fleet receipt; "
                            + "leaving the legacy entity unchanged",
                    variant, unit.getStringUUID());
            return true;
        }
        boolean accepted = current.canonicalId().equals(unit.getUUID());
        if (!accepted)
        {
            ProjectSeele.LOGGER.warn(
                    "Rejecting non-canonical EVA-0{} {} (canonical={}); "
                            + "the world-global one-airframe contract is fail-closed",
                    variant, unit.getStringUUID(), current.canonicalId());
        }
        return accepted;
    }

    /** Migrates an old three-airframe map into the new canonical wet cages. */
    public static List<EvaUnit01Entity> ensureFleet(ServerLevel level)
    {
        if (FacilityV2EvaRuntime.readyAll(level))
        {
            if (!fleetStationEntitiesSettled(level))
            {
                return List.of();
            }
            return ensureFleetV2(level);
        }
        requireCompactLogistics(level, "ensureFleet");
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer())
                && !fleetStationEntitiesSettled(level))
        {
            /*
             * Chunk futures complete before their entity sections attach.
             * Repairing a PARKED UUID in that short window creates a second
             * airframe, after which the real persisted EVA is rejected as a
             * duplicate. Both runtimes wait for actual entity-section attachment
             * before they are allowed to create or replace anything.
             */
            return List.of();
        }
        /*
         * S20 is the user's hand-corrected world.  Re-running the legacy
         * hangar builder here silently repainted those corrections whenever
         * an EVA receipt needed repair.  S20 may reconcile runtime entities
         * and the explicitly moving bridge/LCL cells, but it must never use a
         * fleet repair as permission to regenerate civil geometry.
         */
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            if (!EvaHangarBuilder.runtimeInfrastructurePresent(level,
                    RegionalFacilityLayout.evaOrigin(level)))
            {
                ProjectSeele.LOGGER.error(
                        "S20 fleet reconciliation refused: compact EVA plant markers are incomplete");
                return List.of();
            }
        }
        else
        {
            EvaHangarBuilder.ensure(level,
                    RegionalFacilityLayout.evaOrigin(level));
        }
        loadFleetStations(level);
        EntryPlugDirector.sweepStrayPlugs(level);
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        List<EvaUnit01Entity> result = new ArrayList<>(3);
        List<EvaUnit01Entity> loaded = loadedFleet(level);
        for (int variant = 0; variant < 3; variant++)
        {
            final int wantedVariant = variant;
            List<EvaUnit01Entity> candidates = loaded.stream()
                    .filter(unit -> unit.getUnitVariant() == wantedVariant)
                    .toList();
            UUID canonical = data.canonicalId(variant).orElse(null);
            EvaUnit01Entity globalCanonical = canonical == null ? null
                    : canonicalAnywhere(level.getServer(), canonical);
            EvaUnit01Entity unit = globalCanonical != null
                    && globalCanonical.level() == level ? globalCanonical : null;
            if (unit == null && canonical == null && !candidates.isEmpty())
            {
                BlockPos bed = EvaHangarBuilder.hangarBed(
                        RegionalFacilityLayout.evaOrigin(level), variant);
                unit = candidates.stream().min(Comparator.comparingDouble(
                        candidate -> candidate.distanceToSqr(bed.getCenter()))).orElse(null);
                if (unit != null)
                {
                    canonical = unit.getUUID();
                    Phase initialPhase = isAtAssignedHangar(level, unit, variant)
                            && !unit.isVehicle() && !unit.isLaunchSequenceActive()
                            ? Phase.PARKED : Phase.DEPLOYED;
                    data.put(variant, new FleetEntry(canonical, initialPhase, 0,
                            bed.getZ(), initialPhase == Phase.PARKED
                            ? EvaHangarBuilder.LCL_SHOULDER_LAYERS : 0));
                }
            }
            FleetEntry persisted = data.entry(variant).orElse(null);
            if (unit == null && globalCanonical == null && canonical != null
                    && persisted != null && persisted.phase() == Phase.PARKED)
            {
                // The hangar chunk was loaded above, so a PARKED canonical
                // that is still absent cannot merely be in an unloaded chunk.
                // This specifically repairs UUIDs left behind by old visual
                // cleanup code without ever cloning a deployed/in-transit EVA.
                ProjectSeele.LOGGER.warn(
                        "Repairing missing PARKED canonical EVA-0{} {} in its wet cage",
                        variant, canonical);
                unit = createParkedCanonical(level, data, variant);
                loaded.add(unit);
                canonical = unit.getUUID();
            }
            if (unit == null && canonical == null)
            {
                unit = createParkedCanonical(level, data, variant);
                loaded.add(unit);
            }
            if (unit == null)
            {
                // A deployed canonical may be in an unloaded chunk. Never
                // clone it merely to satisfy a local readiness screen.
                continue;
            }
            for (EvaUnit01Entity duplicate : candidates)
            {
                if (duplicate != unit)
                {
                    duplicate.discard();
                }
            }
            FleetEntry entry = data.entry(variant).orElseThrow();
            if (entry.phase() == Phase.PARKED && !unit.isVehicle())
            {
                BlockPos bed = EvaHangarBuilder.hangarBed(
                        RegionalFacilityLayout.evaOrigin(level), variant);
                placeAt(unit, bed);
                unit.setSortieDestination(level.dimension(),
                        surfaceLiftBed(level, variant));
                unit.setSortieParkingBed(bed);
                unit.setNervLogisticsLocked(true);
                unit.enterHangarStandby();
                EvaHangarBuilder.setBoardingBridgeExtension(level,
                        RegionalFacilityLayout.evaOrigin(level), variant,
                        EvaHangarBuilder.BRIDGE_SEGMENTS);
                EntryPlugDirector.ensureSuspended(level, variant, unit);
            }
            result.add(unit);
        }
        return result;
    }

    private static List<EvaUnit01Entity> ensureFleetV2(ServerLevel level)
    {
        loadFleetStations(level);
        EntryPlugDirector.sweepStrayPlugs(level);
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        List<EvaUnit01Entity> result = new ArrayList<>(3);
        List<EvaUnit01Entity> loaded = loadedFleet(level);
        for (int variant = 0; variant < 3; variant++)
        {
            /*
             * Controls are a bounded runtime surface rather than part of the
             * immutable cage receipt.  Install them here as well as in a
             * freshly generated a2 cage so an already commissioned a1 save
             * receives working PREPARE / RECALL / STATUS buttons without
             * repainting the whole hangar.
             */
            FacilityV2EvaRuntime.ensureControls(level, variant);
            final int wantedVariant = variant;
            FleetEntry saved = data.entry(variant).orElse(null);
            EvaUnit01Entity unit = saved == null ? null
                    : canonicalAnywhere(level.getServer(),
                    saved.canonicalId());
            if (unit != null && unit.level() != level)
            {
                unit = null;
            }
            if (unit == null)
            {
                if (saved == null)
                {
                    unit = createParkedCanonicalV2(level, data, variant);
                    loaded.add(unit);
                    saved = data.entry(variant).orElseThrow();
                }
                else if (saved.phase() == Phase.PARKED)
                {
                    /*
                     * fleetStationEntitiesSettled() has already loaded the
                     * assigned cage and waited for its entity section. A
                     * PARKED airframe can only live in that cage, so an absent
                     * UUID here is a stale receipt rather than a legitimately
                     * unloaded sortie. Repairing only PARKED preserves the
                     * one-airframe contract while keeping deployed and moving
                     * receipts strictly fail-closed.
                     */
                    ProjectSeele.LOGGER.warn(
                            "Repairing missing S19 PARKED canonical EVA-0{} {} in its commissioned wet cage",
                            variant, saved.canonicalId());
                    unit = createParkedCanonicalV2(level, data, variant);
                    loaded.add(unit);
                    FacilityV2EvaRuntime.restoreLclEnvelope(level, variant);
                    saved = data.entry(variant).orElseThrow();
                }
                else
                {
                    /*
                     * UUID does not encode an entity's last chunk and entity
                     * sections attach after their chunks. A canonical may be
                     * parked, deployed or moving but still absent from the
                     * loaded index at this instant. Never rewrite an existing
                     * receipt automatically; the explicit force-reset command
                     * is the sole recovery authority for a truly lost unit.
                     */
                    ProjectSeele.LOGGER.warn(
                            "S19 canonical EVA-0{} is not yet loaded; preserving {} receipt {} without cloning",
                            variant, saved.phase(), saved.canonicalId());
                    continue;
                }
            }
            for (EvaUnit01Entity candidate : List.copyOf(loaded))
            {
                if (candidate != unit
                        && candidate.getUnitVariant() == wantedVariant)
                {
                    candidate.discard();
                    loaded.remove(candidate);
                }
            }
            if (saved.phase() == Phase.PARKED && !unit.isVehicle())
            {
                BlockPos bed = hangarBed(level, variant);
                placeAt(unit, bed);
                unit.setSortieDestination(level.dimension(),
                        surfaceLiftBed(level, variant));
                unit.setSortieParkingBed(bed);
                unit.setNervLogisticsLocked(true);
                unit.enterHangarStandby();
                setBoardingBridgeExtension(level, variant,
                        FacilityV2EvaRuntime.BRIDGE_SEGMENTS);
                restoreStaticCarrier(level, variant, bed);
                restoreStaticCarrier(level, variant,
                        lowerLiftBed(level, variant));
                restoreStaticCarrier(level, variant,
                        surfaceLiftBed(level, variant));
                EntryPlugDirector.ensureSuspended(level, variant, unit);
            }
            result.add(unit);
        }
        return result;
    }

    private static EvaUnit01Entity createParkedCanonical(
            ServerLevel level, EvaFleetSavedData data, int variant)
    {
        EvaUnit01Entity unit = createUnit(level, variant);
        if (unit == null)
        {
            throw new IllegalStateException("Failed to create canonical EVA-0" + variant);
        }
        BlockPos bed = hangarBed(level, variant);
        placeAt(unit, bed);
        unit.setNervLogisticsLocked(true);
        unit.enterHangarStandby();
        unit.setPersistenceRequired();
        data.put(variant, new FleetEntry(unit.getUUID(), Phase.PARKED,
                0, bed.getZ(), EvaHangarBuilder.LCL_SHOULDER_LAYERS));
        if (!level.addFreshEntity(unit))
        {
            throw new IllegalStateException("Server rejected canonical EVA-0" + variant);
        }
        return unit;
    }

    private static EvaUnit01Entity createParkedCanonicalV2(
            ServerLevel level, EvaFleetSavedData data, int variant)
    {
        EvaUnit01Entity unit = createUnit(level, variant);
        if (unit == null)
        {
            throw new IllegalStateException(
                    "Failed to create canonical EVA-0" + variant);
        }
        BlockPos bed = hangarBed(level, variant);
        placeAt(unit, bed);
        unit.setNervLogisticsLocked(true);
        unit.enterHangarStandby();
        unit.setPersistenceRequired();
        data.put(variant, new FleetEntry(unit.getUUID(), Phase.PARKED,
                0, bed.getZ(), FacilityV2EvaRuntime.LCL_SHOULDER_LAYERS));
        if (!level.addFreshEntity(unit))
        {
            throw new IllegalStateException(
                    "Server rejected canonical EVA-0" + variant);
        }
        setBoardingBridgeExtension(level, variant,
                FacilityV2EvaRuntime.BRIDGE_SEGMENTS);
        restoreStaticCarrier(level, variant, bed);
        restoreStaticCarrier(level, variant,
                lowerLiftBed(level, variant));
        restoreStaticCarrier(level, variant,
                surfaceLiftBed(level, variant));
        return unit;
    }

    public static ActionResult requestPrepare(ServerLevel level, int variant)
    {
        if(variant<0||variant>2)return new ActionResult(false,"请指定原零号/初号/二号机。");
        loadControlTarget(level,variant);
        var rearFault=EntryPlugBridgeLayoutR48.retractionFaultR48(level,variant);
        if(rearFault.isPresent())return new ActionResult(false,rearFault.get());
        var staffFault=TvPersonnelPlatformInterlockR44.prepareFault(level,variant);
        if(staffFault.isPresent())return new ActionResult(false,staffFault.get());
        if (!logisticsReady(level, variant))
        {
            return v2MigrationInhibit("preparation");
        }
        /*
         * PARKED routes deliberately release their long-lived chunk tickets.
         * The operations room is eight chunks from the wet cages, so a remote
         * PREPARE must synchronously load this one assigned station before the
         * read-only readiness gate resolves the saved EVA UUID.  Loading after
         * the gate made a healthy parked EVA fail as CANONICAL_ENTITY_NOT_LOADED
         * every time the commander was not standing beside its cage.
         */
        loadControlTarget(level, variant);
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level,
                        FacilityReadinessService.Operation.PREPARE, variant);
        if (!readiness.accepted())
        {
            return new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
        }
        if (!SeeleConfig.dynamicEvaFacilityBlocksEnabled())
        {
            return rescueInhibit(label(variant) + " preparation");
        }
        EvaUnit01Entity unit = canonical(level, variant);
        FleetEntry entry = entry(level, variant);
        if (unit == null || entry == null)
        {
            return new ActionResult(false, label(variant) + " is not loaded; use force reset.");
        }
        if(unit.refreshTvPersonnelClockHoldR44())return new ActionResult(false,unit.tvPersonnelClockFaultR44());
        if (com.projectseele.entity.EvaBayRepairR33.active(unit))return new ActionResult(false,"机体正在检修，机械臂撤回后即可出动。");
        if (entry.phase() != Phase.PARKED)
        {
            return new ActionResult(false, label(variant) + " is " + entry.phase() + ".");
        }
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer())
                && !EvaHangarBuilder.ensureRuntimePowerPylon(level,
                RegionalFacilityLayout.evaOrigin(level), variant))
        {
            return new ActionResult(false, label(variant)
                    + " cage external-power socket is obstructed.");
        }
        if (EntryPlugDirector.ensureSuspended(level, variant, unit) == null)
        {
            return new ActionResult(false, label(variant)
                    + " entry-plug authority is unavailable; use force reset.");
        }
        if (!EntryPlugDirector.hasBoardedPilot(level, variant, unit))
        {
            return new ActionResult(false, label(variant)
                    + " pilot must board the suspended external entry plug first.");
        }
        unit.clearSortieDestination();
        unit.setNervLogisticsLocked(true);
        EntryPlugDirector.beginCabinPreparation(level, variant, unit);
        int lcl = lclLevel(level, variant);
        put(level, variant, entry.withPhase(Phase.BRIDGE_RETRACTING, 0,
                hangarBed(level, variant).getZ(), lcl));
        level.playSound(null, unit.blockPosition(), SoundEvents.PISTON_CONTRACT,
                SoundSource.BLOCKS, 2.5F, 0.62F);
        return new ActionResult(true, label(variant)
                + " boarding bridge retraction and entry-plug insertion started.");
    }

    /**
     * Command-room launch authority with a bounded reload repair.  SavedData
     * owns SILO_READY; if the matching entity lost only its transient launch
     * lock during a save/reload, rebuild that lock at the exact assigned lower
     * lodestone before releasing it.  No earlier phase or empty EVA can use
     * this path.
     */
    public static ActionResult requestLaunch(ServerLevel level, int variant)
    {
        var staffFault=TvPersonnelPlatformInterlockR44.prepareFault(level,variant);
        if(staffFault.isPresent())return new ActionResult(false,staffFault.get());
        if (!logisticsReady(level, variant))
        {
            return v2MigrationInhibit("launch");
        }
        loadControlTarget(level, variant);
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level,
                        FacilityReadinessService.Operation.LAUNCH, variant);
        if (!readiness.accepted())
        {
            return new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
        }
        EvaUnit01Entity unit = canonical(level, variant);
        FleetEntry entry = entry(level, variant);
        if (unit == null || entry == null)
        {
            return new ActionResult(false,
                    label(variant) + " is not linked to the command network.");
        }
        if(unit.refreshTvPersonnelClockHoldR44())return new ActionResult(false,unit.tvPersonnelClockFaultR44());
        if(UndergroundSortieR48.reservesLaunchR48(level,variant,unit))
            return new ActionResult(false,"地下出口正在开门/转移，未释放地表弹射。");
        if (entry.phase() != Phase.SILO_READY)
        {
            return new ActionResult(false, label(variant) + " is "
                    + entry.phase() + "; launch requires SILO READY.");
        }
        BlockPos bed = lowerLiftBed(level, variant);
        double dx = unit.getX() - (bed.getX() + 0.5D);
        double dz = unit.getZ() - (bed.getZ() + 0.5D);
        boolean atAssignedBed = dx * dx + dz * dz <= 4.0D
                && Math.abs(unit.getY() - (bed.getY() + 1.0D)) <= 2.0D;
        if (!atAssignedBed || !EntryPlugDirector.hasLaunchLock(
                level, variant, unit))
        {
            return new ActionResult(false, label(variant)
                    + " launch interlock is incomplete at the assigned silo.");
        }
        if (unit.getLaunchPhase() != EvaUnit01Entity.LAUNCH_LOCKED
                && !unit.armPreparedLaunch(bed))
        {
            return new ActionResult(false, label(variant)
                    + " could not restore its silo launch lock.");
        }
        if (!unit.releaseLaunchFromCommand())
        {
            return new ActionResult(false, label(variant)
                    + " catapult release was rejected by the occupied airframe.");
        }
        return new ActionResult(true,
                label(variant) + " catapult release authorized.");
    }
    /** Only the installed underground service may begin a bound original carrier trip. */
    public static ActionResult requestUndergroundDepartureR48(ServerPlayer caller,int variant,UUID expected)
    {
        var level=caller.serverLevel();var unit=canonical(level,variant);var entry=entry(level,variant);
        if(!logisticsReady(level,variant)||unit==null||entry==null||!entry.canonicalId().equals(expected)
                ||!unit.getUUID().equals(expected)||entry.phase()!=Phase.SILO_READY
                ||!UndergroundSortieR48.departureAuthorizedR48(caller,variant,unit))
            return new ActionResult(false,"地下出击的原机体与准备许可已变化。");
        var ready=FacilityReadinessService.read(level,FacilityReadinessService.Operation.LAUNCH,variant);
        if(!ready.accepted())return new ActionResult(false,ready.faultCode()+": "+ready.message());
        var bed=lowerLiftBed(level,variant);
        if(unit.position().distanceToSqr(new Vec3(bed.getX()+.5,bed.getY()+1,bed.getZ()+.5))>.25
                ||!EntryPlugDirector.hasLaunchLock(level,variant,unit)||unit.isLaunchCommandReleased())
            return new ActionResult(false,"原插入栓/下层承载床尚未锁定。");
        if(unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_IDLE&&UndergroundSortieR48.cancelledReservationR48(level,variant,unit))
            return new ActionResult(true,"原地下弹射取消许可保持，承载板等待真实门全开。");
        if(unit.getLaunchPhase()!=EvaUnit01Entity.LAUNCH_LOCKED&&!unit.armPreparedLaunch(bed))
            return new ActionResult(false,"原下层预备锁尚未恢复。");
        if(!unit.cancelPreparedLaunch())return new ActionResult(false,"弹射已释放，不能切换地下出口。");
        unit.clearSortieDestination();unit.setNervLogisticsLocked(true);unit.setNoGravity(true);
        return new ActionResult(true,"预备弹射已取消，原承载板转向地下接应平台。");
    }
    public static ActionResult completeUndergroundDepartureR48(ServerLevel level,int variant,UUID expected)
    {
        var unit=canonical(level,variant);var entry=entry(level,variant);
        if(unit==null||entry==null||!expected.equals(entry.canonicalId())||!expected.equals(unit.getUUID())
                ||entry.phase()!=Phase.SILO_READY||!UndergroundSortieR48.finishAuthorizedR48(level,variant,unit,false)
                ||!EntryPlugDirector.hasLaunchLock(level,variant,unit))
            return new ActionResult(false,"地下平台到达许可或原插入栓连接已变化。");
        unit.endNervCarrierMotion();unit.clearSortieDestination();unit.setCarrierRiseProgress(0);
        put(level,variant,entry.withPhase(Phase.DEPLOYED,0,lowerLiftBed(level,variant).getY(),0));
        unit.setNervLogisticsLocked(false);unit.setNoGravity(false);
        return new ActionResult(true,"原机体已到实心地下平台，可驾驶沿台阶驶向草地。");
    }
    public static ActionResult requestUndergroundRecoveryR48(ServerLevel level,int variant,UUID expected)
    {
        var unit=canonical(level,variant);var entry=entry(level,variant);
        if(unit==null||entry==null||!expected.equals(entry.canonicalId())||!expected.equals(unit.getUUID())
                ||entry.phase()!=Phase.DEPLOYED||!UndergroundSortieR48.recoveryAuthorizedR48(level,variant,unit)
                ||!recoveryMotionSettled(unit)||!EntryPlugDirector.hasLaunchLock(level,variant,unit)
                    &&!UndergroundSortieR48.emptyRecoveryR49(level,variant,unit))
            return new ActionResult(false,"原地下接应平台回收条件尚未满足。");
        if(!HangarEmergencyR47.releaseForRecoveryR47(level,variant))
            return new ActionResult(false,"湿舱后门仍在通行，地下回收暂缓。");
        unit.prepareForNervRecovery();unit.setNervLogisticsLocked(true);
        return new ActionResult(true,"地下承载板开始连续返回原下层床。");
    }
    public static ActionResult completeUndergroundRecoveryR48(ServerLevel level,int variant,UUID expected)
    {
        var unit=canonical(level,variant);var entry=entry(level,variant);var bed=lowerLiftBed(level,variant);
        if(unit==null||entry==null||!expected.equals(entry.canonicalId())||!expected.equals(unit.getUUID())
                ||entry.phase()!=Phase.DEPLOYED||!UndergroundSortieR48.finishAuthorizedR48(level,variant,unit,true)
                ||unit.position().distanceToSqr(new Vec3(bed.getX()+.5,bed.getY()+1,bed.getZ()+.5))>.25)
            return new ActionResult(false,"原下层床返回许可尚未满足。");
        unit.endNervCarrierMotion();unit.clearSortieDestination();unit.setNervLogisticsLocked(true);
        setGate(level,variant,true);put(level,variant,entry.withPhase(Phase.TO_HANGAR,0,bed.getZ(),0));
        return new ActionResult(true,"已回到原下层床，沿正常通路返回同一湿舱。");
    }

    public static boolean recoveryMotionSettled(EvaUnit01Entity unit)
    {
        Vec3 motion=unit.getDeltaMovement();
        if(motion.horizontalDistanceSqr()>RECOVERY_MAX_SPEED_SQR)return false;
        if(NervAirLiftR30.waitingAtHead(unit)&&!NervAirLiftR30.ownsMotion(unit)&&motion.lengthSqr()<.001)return true;
        // An unpiloted, grounded EVA retains the next gravity impulse in
        // deltaMovement. Its magnitude follows the airframe's gravity attribute.
        // Verify actual support; a stale onGround bit is insufficient.
        double gravity=unit.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get());
        if(motion.y>Math.sqrt(RECOVERY_MAX_SPEED_SQR)||motion.y<-(gravity+.07))return false;
        if(motion.y<-Math.sqrt(RECOVERY_MAX_SPEED_SQR)&&!unit.onGround())return false;
        int supported=0;
        for(double[] offset:new double[][]{{0,0},{-3,0},{3,0},{0,-2},{0,2}})
        {
            double x=unit.getX()+offset[0],y=unit.getY(),z=unit.getZ()+offset[1];
            if(unit.level().getBlockCollisions(unit,new AABB(x-.6,y-.16,z-.6,x+.6,y+.005,z+.6)).iterator().hasNext())supported++;
        }
        return supported>=3;
    }

    /** A naturally faulted empty original already at its own bay can use the normal hoist, never a reset. */
    public static boolean emptyFaultBayRecoveryReadyR50(ServerLevel level,EvaUnit01Entity unit)
    {
        int variant=unit.getUnitVariant();var receipt=entry(level,variant);var plug=EntryPlugDirector.canonical(level,variant);
        if(receipt==null||receipt.phase()!=Phase.PLUG_FAULT||!receipt.canonicalId().equals(unit.getUUID())
                ||canonical(level,variant)!=unit||unit.getPilotEntity()!=null||unit.isLaunchSequenceActive()
                ||unit.hasActiveCarrierMotion()||EvaAirTransportR31.active(unit)||!recoveryMotionSettled(unit)
                ||unit.position().distanceToSqr(Vec3.atBottomCenterOf(hangarBed(level,variant).above()))>.25D
                ||plug==null||plug.isVehicle()||receipt.entryPlugId()==null||!receipt.entryPlugId().equals(plug.getUUID())
                ||plug.getVehicle()!=unit||plug.getLinkedEva()!=unit||unit.getLockedEntryPlug()!=plug
                ||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_LOCKED||plug.getInsertionProgress()!=100
                ||!plug.isHatchFullySealed())return false;
        var actual=plug.getCanonicalTransform();var expected=EntryPlugKinematics.lockedTransform(unit);
        return actual.translation().distanceToSqr(expected.translation())<=.04D&&actual.rotationErrorDegrees(expected)<=.5D;
    }
    public static ActionResult recoverEmptyFaultAtBayR50(ServerPlayer caller,int variant)
    {
        var level=caller.serverLevel();
        var unit=canonical(level,variant);var receipt=entry(level,variant);
        if(unit==null||receipt==null||!AutoSortieR32.releaseEmptyFaultBayDelegationR50(caller,unit))
            return new ActionResult(false,"故障原机尚未在所属湿舱停稳，原空栓或实际锁姿不符，未复位或替换。");
        if(!HangarEmergencyR47.releaseForRecoveryR47(level,variant)||!EntryPlugDirector.extractEmptyCapsule(level,variant,unit))
            return new ActionResult(false,"原空栓的正常抽出联锁尚未满足，机体与原栓保持当前状态。");
        unit.setNervLogisticsLocked(true);unit.setNoGravity(true);unit.setDeltaMovement(Vec3.ZERO);
        unit.getPersistentData().putBoolean("R50EmptyFaultBayRecovery",true);
        put(level,variant,receipt.withPhase(Phase.FILLING,0,hangarBed(level,variant).getZ(),receipt.lclLayers()));
        return new ActionResult(true,"原空栓沿现有吊架抽出，回到原吊位后按正常湿舱注液与栈桥流程完成回收。");
    }
    public static ActionResult requestRecovery(ServerLevel level, int variant)
    {
        if (!logisticsReady(level, variant))
        {
            return v2MigrationInhibit("recovery");
        }
        /*
         * Surface recovery is normally authorized from the buried operations
         * room.  The deployed EVA and its recovery deck can therefore be eight
         * or more chunks away and unloaded, exactly like a parked wet cage
         * during PREPARE.  Load this line's three physical stations before the
         * read-only gate resolves the SavedData UUID; otherwise a healthy EVA
         * standing motionless on its pad is reported as missing.
         */
        loadControlTarget(level, variant);
        FleetEntry parkedFault=entry(level,variant);
        if(parkedFault!=null&&parkedFault.phase()==Phase.PLUG_FAULT)
            return new ActionResult(false,"故障原机回收需要原调用者与完整借用联锁，请通过电话美里或律子的正常回收入口请求；未执行旁路抽栓。");
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level,
                        FacilityReadinessService.Operation.RECOVERY, variant);
        if (!readiness.accepted())
        {
            return new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
        }
        if (!SeeleConfig.dynamicEvaFacilityBlocksEnabled())
        {
            return rescueInhibit(label(variant) + " recovery");
        }
        EvaUnit01Entity unit = canonical(level, variant);
        FleetEntry entry = entry(level, variant);
        if (unit == null || entry == null)
        {
            return new ActionResult(false, label(variant) + " is not loaded; use force reset.");
        }
        if (entry.phase() != Phase.DEPLOYED)
        {
            return new ActionResult(false, label(variant) + " is " + entry.phase()
                    + "; recovery requires DEPLOYED.");
        }
        if(UndergroundSortieR48.deployedBindingR48(level,variant,unit))
            return UndergroundSortieR48.recoverR48(level,variant,unit);
        BlockPos surface = surfaceLiftBed(level, variant);
        double dx = unit.getX() - (surface.getX() + 0.5D);
        double dz = unit.getZ() - (surface.getZ() + 0.5D);
        double horizontal = Math.sqrt(dx * dx + dz * dz);
        if (horizontal > RECOVERY_RADIUS
                || Math.abs(unit.getY() - (surface.getY() + 2.0D)) > 8.0D)
        {
            return new ActionResult(false, label(variant)
                    + " must stand on its own Tokyo-3 recovery deck.");
        }
        if (!recoveryMotionSettled(unit))
        {
            return new ActionResult(false, label(variant)
                    + " must be motionless before surface command authorizes recovery.");
        }
        if(!HangarEmergencyR47.releaseForRecoveryR47(level,variant))
            return new ActionResult(false,"机库后门正在通行，请清空门域后回收。");
        unit.getPersistentData().remove("R30AwaitingNervRecovery");
        unit.getPersistentData().putBoolean("RecoveryRiseR39",true);
        unit.setCarrierRiseProgress(0);
        unit.prepareForNervRecovery();
        unit.setNervLogisticsLocked(true);
        unit.moveOnNervCarrier(surface.getX() + 0.5D,
                surface.getY() + 2.0D, surface.getZ() + 0.5D,
                EvaUnit01Entity.SILO_BAY_YAW);
        put(level, variant, entry.withPhase(Phase.DESCENDING, 0,
                surface.getY() + 1, 0));
        level.playSound(null, surface, SoundEvents.PISTON_CONTRACT,
                SoundSource.BLOCKS, 4.0F, 0.48F);
        return new ActionResult(true, label(variant)
                + " 回收已开始：支撑架升起、舱门开启，然后下降。");
    }

    /**
     * Recalls a launch-locked airframe from the silo back into its wet cage.
     *
     * <p>Only valid at {@link Phase#SILO_READY}, before command releases the
     * catapult. It reuses the recovery {@link Phase#TO_HANGAR}/{@link
     * Phase#FILLING} path, so the plug is re-suspended and the cage refloods on
     * arrival, sparing a pilot who armed the sortie from being stranded on the
     * catapult when no command-room operator is available to launch.
     */
    public static ActionResult requestCancel(ServerLevel level, int variant)
    {
        if (!logisticsReady(level, variant))
        {
            return v2MigrationInhibit("launch cancel");
        }
        // SILO READY keeps route tickets while the server is running, but an
        // interrupted/reloaded session must still resolve the exact lower
        // station before the readiness gate checks the canonical airframe.
        loadVariantStations(level, variant);
        FacilityReadinessService.FacilityReadiness readiness =
                FacilityReadinessService.read(level,
                        FacilityReadinessService.Operation.RECOVERY, variant);
        if (!readiness.accepted())
        {
            return new ActionResult(false,
                    readiness.faultCode() + ": " + readiness.message());
        }
        if (!SeeleConfig.dynamicEvaFacilityBlocksEnabled())
        {
            return rescueInhibit(label(variant) + " launch cancel");
        }
        EvaUnit01Entity unit = canonical(level, variant);
        FleetEntry entry = entry(level, variant);
        if (unit == null || entry == null)
        {
            return new ActionResult(false, label(variant) + " is not loaded; use force reset.");
        }
        if (entry.phase() != Phase.SILO_READY)
        {
            return new ActionResult(false, label(variant) + " is " + entry.phase()
                    + "; launch cancel is only available at SILO READY (launch lock).");
        }
        if (!unit.cancelPreparedLaunch())
        {
            return new ActionResult(false, label(variant)
                    + " has already released; recovery must be commanded from Tokyo-3.");
        }
        BlockPos silo = lowerLiftBed(level, variant);
        // Open the wet-cage gate before the airframe slides home. The recovery
        // path opens it during descent; a launch cancel jumps straight to the
        // horizontal return, so without this the EVA is dragged through a shut
        // gate instead of a clear tunnel.
        setGate(level, variant, true);
        unit.setNervLogisticsLocked(true);
        unit.clearSortieDestination();
        unit.moveOnNervCarrier(silo.getX() + 0.5D, silo.getY() + 1.0D,
                silo.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW);
        put(level, variant, entry.withPhase(Phase.TO_HANGAR, 0, silo.getZ(), 0));
        level.playSound(null, silo, SoundEvents.PISTON_CONTRACT,
                SoundSource.BLOCKS, 2.5F, 0.55F);
        return new ActionResult(true, label(variant)
                + " launch cancelled; airframe returning to its wet cage.");
    }

    /** Maintenance of the original empty wet-cage assembly, never replacement actors. */
    public static EvaUnit01Entity forceReset(ServerLevel level, int variant)
    {
        requireCompactLogistics(level, "forceReset");
        FleetEntry previous=entry(level,variant);
        EvaUnit01Entity unit=canonical(level,variant);
        EntryPlugCarrierEntity plug=EntryPlugDirector.canonical(level,variant);
        if(previous==null||unit==null||plug==null||!previous.canonicalId().equals(unit.getUUID()))
            throw new IllegalStateException(label(variant)+"：原机体或插入栓尚未加载，未创建替代对象。");
        BlockPos bed=hangarBed(level,variant);
        if(unit.level()!=level||unit.distanceToSqr(Vec3.atBottomCenterOf(bed.above()))>36
                ||com.projectseele.entity.EvaAirTransportR31.active(unit)||NervAirLiftR30.ownsMotion(unit))
            throw new IllegalStateException(label(variant)+"：请先回收至原机库；运输中的机体不能直接复位。");
        if(unit.getPilotEntity()!=null||plug.getFirstPassenger()!=null)
            throw new IllegalStateException(label(variant)+"：请先让驾驶员离栓，再维护复位。");
        if(!NervAirLiftR30.abortForMaintenanceR47(level,variant,unit.getUUID()))
            throw new IllegalStateException("原运输机未就绪，维护复位等待运输收尾。");
        maintainRouteChunks(level,variant,previous.canonicalId(),false);
        ROUTE_TICKET_STATE.remove(previous.canonicalId());
        NervCarrierVisuals.removeAll(level,unit);
        placeAt(unit,bed);unit.setPersistenceRequired();unit.setHealth(unit.getMaxHealth());unit.deathTime=0;
        unit.setNervLogisticsLocked(true);unit.enterHangarStandby();
        int lcl=FacilityV2EvaRuntime.ready(level,variant)?FacilityV2EvaRuntime.LCL_SHOULDER_LAYERS:EvaHangarBuilder.LCL_SHOULDER_LAYERS;
        put(level,variant,new FleetEntry(unit.getUUID(),Phase.PARKED,0,bed.getZ(),lcl));
        EntryPlugDirector.reset(level,variant,unit);
        setBoardingBridgeExtension(level,variant,FacilityV2EvaRuntime.ready(level,variant)?FacilityV2EvaRuntime.BRIDGE_SEGMENTS:EvaHangarBuilder.BRIDGE_SEGMENTS);
        setGate(level,variant,false);
        if(FacilityV2EvaRuntime.ready(level,variant))FacilityV2EvaRuntime.restoreLclEnvelope(level,variant);
        else EvaHangarBuilder.setLclLevel(level,RegionalFacilityLayout.evaOrigin(level),variant,lcl);
        restoreStaticCarrier(level,variant,bed);
        restoreStaticCarrier(level,variant,lowerLiftBed(level,variant));
        restoreStaticCarrier(level,variant,surfaceLiftBed(level,variant));
        unit.setSortieDestination(level.dimension(),surfaceLiftBed(level,variant));unit.setSortieParkingBed(bed);
        TrainingPilotDirector.stop(level,variant);
        ProjectSeele.LOGGER.info("NERV original assembly maintained: eva={} plug={} bed={}",unit.getUUID(),plug.getUUID(),bed);
        return unit;
    }

    public static Status status(ServerLevel level, int variant)
    {
        FleetEntry entry = entry(level, variant);
        EvaUnit01Entity unit = canonical(level, variant);
        return entry == null
                ? new Status(variant, "UNREGISTERED", false, null, 0, 0)
                : new Status(variant, entry.phase().name(), unit != null,
                        entry.canonicalId(), entry.lclLayers(), entry.ticks());
    }

    /** Read-only canonical lookup shared by training and command systems. */
    public static EvaUnit01Entity canonicalUnit(ServerLevel level, int variant)
    {
        return canonical(level, variant);
    }

    /** Keeps deterministic screenshot fixtures out of the live parking loop. */
    public static void markDeployedForVisual(ServerLevel level,
                                             EvaUnit01Entity unit)
    {
        requireCompactLogistics(level, "markDeployedForVisual");
        int variant = unit.getUnitVariant();
        FleetEntry current = entry(level, variant);
        if (current == null || !current.canonicalId().equals(unit.getUUID()))
        {
            EvaFleetSavedData.get(level.getServer()).put(variant,
                    new FleetEntry(unit.getUUID(), Phase.DEPLOYED, 0,
                            unit.blockPosition().getY(), 0));
        }
        else
        {
            put(level, variant, current.withPhase(Phase.DEPLOYED,
                    0, unit.blockPosition().getY(), 0));
        }
        unit.clearSortieDestination();
        unit.setNervLogisticsLocked(false);
    }
    /** Hangar preparation controls plus three supported Tokyo-3 recovery keys. */
    public static boolean handleUse(ServerPlayer player, BlockPos position)
    {
        ServerLevel level = player.serverLevel();
        boolean modern = FacilityWorldPolicy.isCleanRebuild(
                level.getServer());
        boolean compact = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        if (!modern && !compact
                && !FacilityWorldPolicy.legacyGenerationAllowed(
                        level.getServer()))
        {
            return false;
        }
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return false;
        }
        if(HangarEmergencyR47.handleUse(player,position))return true;
        var installedControl = HangarOperationsR44.match(level, position);
        if (installedControl.isPresent())
        {
            var control = installedControl.get();
            switch (control.action())
            {
                case PREPARE -> handleHangarControl(player, control.variant(), true);
                case STATUS -> handleHangarControl(player, control.variant(), false);
                case CANCEL ->
                {
                    ActionResult result = requestCancel(level, control.variant());
                    player.displayClientMessage(Component.literal(
                            "[NERV HANGAR] " + result.message()).withStyle(
                            result.accepted() ? ChatFormatting.GREEN : ChatFormatting.RED), false);
                }
            }
            // These physical keys use the same guarded requests and fleet
            // identities as the retained controls. Vanilla still depresses
            // and sounds the actual button; no launch authority is added.
            return true;
        }
        if (modern)
        {
            for (int variant = 0; variant < 3; variant++)
            {
                if (!FacilityV2EvaRuntime.ready(level, variant))
                {
                    continue;
                }
                if (FacilityV2EvaRuntime.cancelControl(level, variant)
                        .equals(position))
                {
                    ActionResult result = requestCancel(level, variant);
                    player.displayClientMessage(Component.literal(
                            "[NERV HANGAR] " + result.message())
                            .withStyle(result.accepted()
                                    ? ChatFormatting.GREEN
                                    : ChatFormatting.RED), false);
                    return true;
                }
                if (FacilityV2EvaRuntime.prepareControl(level, variant)
                        .equals(position))
                {
                    handleHangarControl(player, variant, true);
                    return true;
                }
                if (FacilityV2EvaRuntime.statusControl(level, variant)
                        .equals(position))
                {
                    handleHangarControl(player, variant, false);
                    return true;
                }
            }
            return false;
        }
        for (int variant = 0; variant < 3; variant++)
        {
            if (!Tokyo3RecoveryConsole.controlPosition(
                    IntegratedNervMapBuilder.tokyo3Origin(level), variant)
                    .equals(position))
            {
                continue;
            }
            ActionResult result = requestRecovery(player.serverLevel(), variant);
            player.displayClientMessage(Component.literal("[TOKYO-3 RECOVERY] "
                    + result.message()).withStyle(result.accepted()
                    ? ChatFormatting.GREEN : ChatFormatting.RED), false);
            return true;
        }

        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        for (int variant = 0; variant < 3; variant++)
        {
            if (EvaHangarBuilder.cancelControlPosition(origin, variant)
                    .equals(position))
            {
                ActionResult result = requestCancel(player.serverLevel(), variant);
                player.displayClientMessage(Component.literal("[NERV HANGAR] "
                        + result.message()).withStyle(result.accepted()
                        ? ChatFormatting.GREEN : ChatFormatting.RED), false);
                return true;
            }
            for (boolean prepare : new boolean[] {true, false})
            {
                if (!EvaHangarBuilder.controlPosition(origin, variant, prepare)
                        .equals(position))
                {
                    continue;
                }
                handleHangarControl(player, variant, prepare);
                return true;
            }
        }
        return false;
    }

    /** The cyan underground key is deliberately read-only; recovery authority
     * lives exclusively at the supported Tokyo-3 surface command post. */
    private static void handleHangarControl(ServerPlayer player, int variant,
                                            boolean prepare)
    {
        if (prepare)
        {
            ActionResult result = requestPrepare(player.serverLevel(), variant);
            player.displayClientMessage(Component.literal("[NERV HANGAR] "
                    + result.message()).withStyle(result.accepted()
                    ? ChatFormatting.GREEN : ChatFormatting.RED), false);
            return;
        }
        Status snapshot = status(player.serverLevel(), variant);
        player.displayClientMessage(Component.literal(String.format(Locale.ROOT,
                "[NERV HANGAR STATUS] %s phase=%s loaded=%s LCL=%d/%d ticks=%d",
                label(variant), snapshot.phase(), snapshot.loaded(),
                snapshot.lclLayers(), EvaHangarBuilder.LCL_SHOULDER_LAYERS,
                snapshot.ticks())).withStyle(ChatFormatting.AQUA), false);
    }

    @SubscribeEvent
    public static void onServerTick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END)
        {
            return;
        }
        ServerLevel level = event.getServer().getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            return;
        }
        boolean modern = FacilityWorldPolicy.isCleanRebuild(
                event.getServer());
        boolean compactS20 = FacilityWorldPolicy.isS20Rebuild(
                event.getServer());
        if (!FacilityWorldPolicy.legacyGenerationAllowed(event.getServer())
                && !compactS20
                && !(modern && FacilityV2EvaRuntime.readyAll(level)))
        {
            if (RESCUE_TICKETS_RELEASED.add(level))
            {
                releaseRouteTickets(event.getServer());
                ProjectSeele.LOGGER.warn(
                        "Retired EVA logistics frozen in {} while the "
                                + "Facility v2 anchor contract is rebuilt",
                        event.getServer().getWorldData().getLevelName());
            }
            return;
        }
        if (compactS20 && event.getServer().getTickCount() % 20 == 0)
        {
            /*
             * These no-save visual gates must exist before the delayed fleet
             * reconciliation finishes.  Otherwise a freshly opened world
             * shows only invisible barrier collision while the saved entity
             * sections are still attaching inside a wet cage.
             */
            for (int variant = 0; variant < 3; variant++)
            {
                maintainHangarDoor(level, variant, false);
            }
        }
        if (!SeeleConfig.dynamicEvaFacilityBlocksEnabled())
        {
            if (RESCUE_TICKETS_RELEASED.add(level))
            {
                for (int variant = 0; variant < 3; variant++)
                {
                    FleetEntry entry = entry(level, variant);
                    if (entry != null)
                    {
                        maintainRouteChunks(level, variant,
                                entry.canonicalId(), false);
                    }
                }
                ProjectSeele.LOGGER.warn(
                        "NERV rescue mode froze dynamic cage/LCL/carrier logistics and released route tickets");
            }
            return;
        }
        if (compactS20 && event.getServer().getTickCount() % 20 == 0
                && !VERIFIED_INFRASTRUCTURE.contains(level))
        {
            maintainKnownParkedBayVisuals(level);
        }
        if (!VERIFIED_INFRASTRUCTURE.contains(level))
        {
            if (modern)
            {
                if (!fleetStationEntitiesSettled(level))
                {
                    return;
                }
                ensureFleetV2(level);
                VERIFIED_INFRASTRUCTURE.add(level);
            }
            else
            {
            /*
             * The full-rebuild save intentionally retires the old integrated
             * map receipt: command, civil exterior and Dogma are Facility-v2
             * owners while the three proven EVA lines are restored by the
             * narrow mechanical-only entry point. Requiring isInstalled()
             * here silently stopped every plug/LCL/carrier phase even though
             * the actual cages and shafts were complete.
             */
            if (event.getServer().getTickCount() % 20 != 0)
            {
                return;
            }
            boolean ready = compactS20
                    ? EvaHangarBuilder.runtimeInfrastructurePresent(
                    level, RegionalFacilityLayout.evaOrigin(level))
                    && compactLiftMarkersPresent(level)
                    : FacilityV2RescueDirector.isTargetWorld(
                    event.getServer())
                    ? IntegratedNervMapBuilder.rescueMechanicalReady(level)
                    : IntegratedNervMapBuilder.isInstalled(level)
                    && EvaHangarBuilder.runtimeInfrastructurePresent(level,
                    RegionalFacilityLayout.evaOrigin(level));
            if (!ready)
            {
                return;
            }
            if (compactS20)
            {
                if (!fleetStationEntitiesSettled(level))return;
                ensureFleet(level);
                // A deployed canonical may live in an unloaded field chunk.
                // Its saved identity is sufficient here; requiring three
                // locally loaded airframes froze every other preparation.
                boolean receiptsReady=true;
                for(int variant=0;variant<3;variant++)receiptsReady&=entry(level,variant)!=null;
                if (!receiptsReady)
                {
                    return;
                }
            }
            VERIFIED_INFRASTRUCTURE.add(level);
            }
        }
        // Self-heal phantom sky-borne plugs a pre-fix crane left behind, once
        // their chunks are resident. Cheap and bounded: a handful of carriers.
        if (event.getServer().getTickCount() % 200 == 0)
        {
            EntryPlugDirector.sweepStrayPlugs(level);
        }
        boolean maintenanceTick = event.getServer().getTickCount() % 20 == 0;
        for (int variant = 0; variant < 3; variant++)
        {
            FleetEntry fleet = entry(level, variant);
            if (maintenanceTick
                    || fleet != null && fleet.phase() != Phase.PARKED)
            {
                maintainSurfaceSiloDoor(level, variant);
            }
            tickUnit(level, variant);
        }
    }

    private static void maintainKnownParkedBayVisuals(ServerLevel level)
    {
        // The global fleet-repair barrier waits for entity sections at all
        // wet, launch and surface stations before it may replace a missing
        // identity. It must not hide a fixed installed bay while those remote
        // sections attach. Reuse only already-loaded, actually parked
        // canonical originals; no actor/phase/pose/ticket repair occurs here.
        for (int variant = 0; variant < 3; variant++)
        {
            FleetEntry known = entry(level, variant);
            if (known == null || known.phase() != Phase.PARKED)
            {
                continue;
            }
            Entity actual = level.getEntity(known.canonicalId());
            if (!(actual instanceof EvaUnit01Entity unit) || !unit.isAlive()
                    || unit.isExperimentalUnit() || unit.getUnitVariant() != variant)
            {
                continue;
            }
            BlockPos bed = hangarBed(level, variant);
            Vec3 expected = new Vec3(bed.getX() + .5, bed.getY() + 1, bed.getZ() + .5);
            if (unit.position().distanceToSqr(expected) > .05 * .05)
            {
                continue;
            }
            // Rack height is derived from the fleet phase. A canonical cold
            // bay can load before distant station sections, so reconcile
            // only its inactive visual channel before the fleet repair gate.
            if (!unit.isVehicle() && !unit.isLaunchSequenceActive()
                    && !unit.hasActiveCarrierMotion())
            {
                unit.setCarrierRiseProgress(0F);
                unit.setRecoveryRackR39(false);
            }
            NervCarrierVisuals.updateRestraints(level, unit,
                    expected.x, bed.getY(), expected.z, 1F);
            NervCarrierVisuals.updateLclSurface(level, unit,
                    expected.x, bed.getY(), expected.z, known.lclLayers());
        }
    }

    private static void maintainSurfaceSiloDoor(ServerLevel level,
                                                int variant)
    {
        if(com.projectseele.visual.TvFacilityR16Review.controlsSurfaceHatches(level))return;
        FleetEntry fleet = entry(level, variant);
        BlockPos surface = surfaceLiftBed(level, variant);
        boolean active = fleet != null && fleet.phase() != Phase.PARKED;
        if (!active && !level.hasChunkAt(surface))
        {
            return;
        }
        EvaUnit01Entity unit = fleet == null ? null
                : canonical(level, variant);
        float target = 0.0F;
        if (unit != null)
        {
            if (unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_LOCKED
                    && unit.isLaunchCommandReleased())
            {
                target = 1.0F;
            }
            else if (unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_ASCENT
                    || fleet.phase() == Phase.DESCENDING
                       && (!unit.getPersistentData().getBoolean("RecoveryRiseR39") || fleet.ticks() >= 100))
            {
                // Once command releases a sortie, the owned hatch remains
                // fully open for the complete ascent/descent.  Closing it at
                // the bottom of the shaft and reopening near the surface
                // created a race with the final route check and served no
                // mechanical purpose.
                target = 1.0F;
            }
            else if (unit.getLaunchPhase() == EvaUnit01Entity.LAUNCH_CLEAR)
            {
                target = Mth.clamp(unit.getLaunchTicks() / 18.0F,
                        0.0F, 1.0F);
            }
        }
        NervSiloDoorEntity.reconcile(level, variant, surface, target);
    }

    private static void tickUnit(ServerLevel level, int variant)
    {
        FleetEntry entry = entry(level, variant);
        if (entry == null)
        {
            return;
        }
        boolean active = entry.phase() != Phase.PARKED
                && entry.phase() != Phase.DEPLOYED;
        active = active || TrainingPilotDirector.requiresRouteTicket(variant);
        maintainRouteChunks(level, variant, entry.canonicalId(), active);
        if (entry.phase() != Phase.PARKED && entry.phase() != Phase.DEPLOYED)
        {
            var staffMotionFault=TvPersonnelPlatformInterlockR44.movementFault(level,variant);
            EvaUnit01Entity staffUnit=canonical(level,variant);
            boolean independentClockHeld=staffUnit!=null&&staffUnit.refreshTvPersonnelClockHoldR44();
            if(staffMotionFault.isPresent()||independentClockHeld)
            {
                // Pause before the hangar door, rack, fluid, boarding bridge,
                // plug and phase clock. A stable clamp endpoint alone cannot
                // authorize another owned machine to move through workers.
                if(staffUnit!=null)
                {
                    staffUnit.refreshTvPersonnelClockHoldR44();
                    staffUnit.getPersistentData().putString("TvPersonnelMotionBlockedR44",staffMotionFault.orElse(staffUnit.tvPersonnelClockFaultR44()));
                }
                TvPersonnelOwnedMotionR44.keepWetMachines(level,variant);
                return;
            }
            if(staffUnit!=null)staffUnit.getPersistentData().remove("TvPersonnelMotionBlockedR44");
        }
        // PARKED used to run the complete standby/plug reconciliation on all
        // three cages every server tick.  Besides resending unchanged entity
        // data, ensureSuspended performs an entity query in each cage.  A
        // stationary facility only needs this self-heal once per second;
        // every animated logistics phase below remains full 20 Hz.
        boolean maintenanceTick = level.getServer().getTickCount() % 20 == 0;
        if (maintenanceTick && entry.phase() == Phase.PARKED)
        {
            TrainingPilotDirector.ensureStandby(level, variant);
        }
        boolean hangarDoorMoving = entry.phase() == Phase.TO_SILO
                || entry.phase() == Phase.TO_HANGAR;
        if (maintenanceTick || hangarDoorMoving)
        {
            maintainHangarDoor(level, variant, entry);
        }
        if (entry.phase() == Phase.PARKED && !maintenanceTick)
        {
            return;
        }
        EvaUnit01Entity unit = canonical(level, variant);
        if (unit == null || !unit.isAlive())
        {
            if (active && entry.ticks() % 40 == 0)
            {
                ProjectSeele.LOGGER.warn(
                        "NERV EVA-0{} logistics waiting for canonical entity: phase={} ticks={} uuid={}",
                        variant, entry.phase(), entry.ticks(), entry.canonicalId());
            }
            return;
        }
        maintainDormantLaunch(unit, entry);
        if (active && entry.ticks() > 0 && entry.ticks() % 40 == 0)
        {
            long started = PHASE_STARTED_AT.getOrDefault(
                    entry.canonicalId(), System.nanoTime());
            ProjectSeele.LOGGER.info(
                    "NERV EVA-0{} logistics progress: phase={} ticks={} elapsedMs={} carrier={} lcl={}",
                    variant, entry.phase(), entry.ticks(),
                    (System.nanoTime() - started) / 1_000_000L,
                    entry.carrier(), entry.lclLayers());
        }
        BlockPos hangar = hangarBed(level, variant);
        BlockPos silo = lowerLiftBed(level, variant);
        BlockPos surface = surfaceLiftBed(level, variant);
        float rackRise = switch(entry.phase())
        {
            case DRAINING -> com.projectseele.entity.EvaDorsalMechanism.smooth(entry.ticks()/100F);
            case TO_SILO, SILO_READY, TO_HANGAR -> 1F;
            case DESCENDING -> unit.getPersistentData().getBoolean("RecoveryRiseR39") ? com.projectseele.entity.EvaDorsalMechanism.smooth(entry.ticks()/100F) : 1F;
            case FILLING -> 1-com.projectseele.entity.EvaDorsalMechanism.smooth(entry.ticks()/80F);
            case DEPLOYED -> unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR ? 1F : 0F;
            default -> 0F;
        };
        unit.setRecoveryRackR39(entry.phase()==Phase.DESCENDING&&unit.getPersistentData().getBoolean("RecoveryRiseR39"));
        unit.setCarrierRiseProgress(rackRise);
        NervCarrierVisuals.updateLclSurface(level, unit,
                hangar.getX() + 0.5D, hangar.getY(),
                hangar.getZ() + 0.5D, visualLclLevel(entry));
        FacilityAudioR21.tick(level,variant,entry,unit,hangar,silo);
        if (isHangarConstrained(entry.phase()))
        {
            holdOnHangarBed(unit, hangar);
        }
        /*
         * The wet-cage towers belong to the hangar, not to the carrier deck.
         * Keep their fixed visual entity alive throughout plug insertion,
         * transfer, launch and recovery; once released their jaws retract but
         * the machinery itself remains in the bay.
         */
        if (entry.phase() != Phase.PARKED
                && entry.phase() != Phase.DRAINING
                && entry.phase() != Phase.FILLING)
        {
            float hangarRestraint = switch (entry.phase())
            {
                case BRIDGE_RETRACTING, PLUG_INSERTING,
                        PLUG_ABORT_RETURNING, PLUG_ABORT_DOCKED,
                        PLUG_FAULT, PLUG_LOCKING -> 1.0F;
                default -> 0.0F;
            };
            if (!NervCarrierVisuals.updateRestraints(level, unit,
                    hangar.getX() + 0.5D, hangar.getY(),
                    hangar.getZ() + 0.5D, hangarRestraint))
            {
                // The real phase clock and carrier wait with the visible
                // restraints; a blocked actuator cannot grant departure.
                return;
            }
        }
        switch (entry.phase())
        {
            case PARKED ->
            {
                unit.setNervLogisticsLocked(true);
                unit.enterHangarStandby();
                unit.setSortieDestination(level.dimension(), surface);
                unit.setSortieParkingBed(hangar);
                NervCarrierVisuals.update(level, unit,
                        hangar.getX() + 0.5D, hangar.getY(),
                        hangar.getZ() + 0.5D, 1.0F);
                EntryPlugDirector.ensureSuspended(level, variant, unit);
            }
            case BRIDGE_RETRACTING ->
            {
                var rearFault=EntryPlugBridgeLayoutR48.retractionFaultR48(level,variant);
                if(rearFault.isPresent())break;
                unit.setNervLogisticsLocked(true);
                int ticks = entry.ticks() + 1;
                if (ticks % 5 == 0 || ticks >= BRIDGE_RETRACTION_TICKS)
                {
                    int remaining = FacilityV2EvaRuntime.BRIDGE_SEGMENTS
                            - Mth.ceil(ticks
                            * FacilityV2EvaRuntime.BRIDGE_SEGMENTS
                            / (double) BRIDGE_RETRACTION_TICKS);
                    if(EntryPlugBridgeLayoutR48.enabled(level))
                    {
                        if(!EntryPlugBridgeLayoutR48.apply(level,hangar,Math.max(0,remaining)))break;
                    }
                    else setBoardingBridgeExtension(level,variant,Math.max(0,remaining));
                }
                // Cabin progress is committed only after the actual bridge write succeeds.
                EntryPlugDirector.tickCabinPreparation(level,variant,unit,ticks,BRIDGE_RETRACTION_TICKS);
                if (ticks >= BRIDGE_RETRACTION_TICKS)
                {
                    if (EntryPlugDirector.beginInsertion(level, variant, unit))
                    {
                        put(level, variant, entry.withPhase(
                                Phase.PLUG_INSERTING, 0,
                                entry.carrier(), entry.lclLayers()));
                        unit.playSound(SoundEvents.PISTON_EXTEND,
                                2.4F, 0.54F);
                    }
                    else
                    {
                        // Route preflight is deterministic for the current
                        // world snapshot. Re-running it every tick only spammed
                        // the log and made the suspended capsule/yoke appear to
                        // shiver for six seconds before the same abort.
                        abortPlugSequence(level, variant, unit,
                                entry, hangar,
                                "hatch/crane interlock did not arm");
                    }
                }
                else
                {
                    put(level, variant, entry.withPhase(
                            Phase.BRIDGE_RETRACTING, ticks,
                            entry.carrier(), entry.lclLayers()));
                }
            }
            case PLUG_INSERTING ->
            {
                unit.setNervLogisticsLocked(true);
                int ticks = entry.ticks() + 1;
                EntryPlugCarrierEntity activePlug =
                        EntryPlugDirector.canonical(level, variant);
                if (activePlug != null
                        && activePlug.isInsertionAbortRequested())
                {
                    abortPlugSequence(level, variant, unit, entry,
                            hangar, "entry-plug pilot requested abort");
                    break;
                }
                if (!EntryPlugDirector.hasBoardedPilot(level, variant, unit))
                {
                    abortPlugSequence(level, variant, unit, entry,
                            hangar, "pilot left the entry plug");
                    break;
                }
                boolean seated = EntryPlugDirector.tickInsertion(level,
                        variant, unit, ticks);
                activePlug = EntryPlugDirector.canonical(
                        level, variant);
                if (seated)
                {
                    put(level, variant, entry.withPhase(Phase.PLUG_LOCKING,
                            0, entry.carrier(), entry.lclLayers()));
                    unit.playSound(SoundEvents.IRON_DOOR_CLOSE, 2.8F, 0.66F);
                }
                else if (activePlug != null
                        && activePlug.getInsertionStage()
                                == EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)
                {
                    abortPlugSequence(level, variant, unit, entry,
                            hangar, "entry-plug swept-clearance interlock opened");
                }
                else if (ticks >= INSERTION_ABORT_TICKS)
                {
                    abortPlugSequence(level, variant, unit, entry,
                            hangar, EntryPlugDirector.hasBoardedPilot(level,
                                    variant, unit)
                                    ? "socket lock could not be established"
                                    : "pilot left the entry plug");
                }
                else
                {
                    put(level, variant, entry.withPhase(Phase.PLUG_INSERTING,
                            ticks, entry.carrier(), entry.lclLayers()));
                }
            }
            case PLUG_ABORT_RETURNING ->
            {
                unit.setNervLogisticsLocked(true);
                int ticks = entry.ticks() + 1;
                boolean returned = EntryPlugDirector.tickAbortReturn(
                        level, variant, unit, ticks);
                if (returned)
                {
                    put(level, variant, entry.withPhase(
                            Phase.PLUG_ABORT_DOCKED, 0,
                            entry.carrier(), entry.lclLayers()));
                }
                else
                {
                    put(level, variant, entry.withPhase(
                            Phase.PLUG_ABORT_RETURNING, ticks,
                            entry.carrier(), entry.lclLayers()));
                }
            }
            case PLUG_ABORT_DOCKED ->
            {
                unit.setNervLogisticsLocked(true);
                int ticks = entry.ticks() + 1;
                int bridge = entry.carrier();
                if (ticks % 5 == 0)
                {
                    bridge = Math.min(
                            FacilityV2EvaRuntime.BRIDGE_SEGMENTS,
                            bridge + 1);
                    setBoardingBridgeExtension(level, variant, bridge);
                }
                if (bridge >= FacilityV2EvaRuntime.BRIDGE_SEGMENTS)
                {
                    if (!EntryPlugDirector.completeAbortDocking(
                            level, variant, unit))
                    {
                        holdPlugFault(level, variant, unit, entry,
                                "returned capsule failed dock-pose release interlock");
                        break;
                    }
                    unit.enterHangarStandby();
                    put(level, variant, entry.withPhase(Phase.PARKED, 0,
                            hangar.getZ(), entry.lclLayers()));
                }
                else
                {
                    put(level, variant, entry.withPhase(
                            Phase.PLUG_ABORT_DOCKED, ticks,
                            bridge, entry.lclLayers()));
                }
            }
            case PLUG_FAULT ->
            {
                // Fail closed.  A missing canonical capsule or a broken
                // pilot/plug/EVA ride chain must never be converted into a
                // teleport, an open pressure hatch or continued catapult
                // motion.  Force-reset remains the explicit recovery path.
                unit.setNervLogisticsLocked(true);
                unit.setNoGravity(true);unit.setDeltaMovement(Vec3.ZERO);unit.getNavigation().stop();unit.stopAutonomousR30();
                if (level.getServer().getTickCount() % 200 == 0)
                {
                    ProjectSeele.LOGGER.error(
                            "NERV EVA-0{} entry-plug sequence is in fail-closed hold",
                            variant);
                }
            }
            case PLUG_LOCKING ->
            {
                unit.setNervLogisticsLocked(true);
                int ticks = entry.ticks() + 1;
                com.projectseele.entity.EvaDorsalMechanism.seal(unit,ticks);
                // Recover the coupling before the cover seals. The S20
                // model hoist advances half a block per tick and eases its
                // visible return; the lane is clear before locking ends.
                EntryPlugDirector.ensureCraneStowed(level, variant);
                if (!EntryPlugDirector.hasLaunchLock(level, variant, unit))
                {
                    abortPlugSequence(level, variant, unit, entry,
                            hangar, "entry-plug launch interlock opened");
                    break;
                }
                if (ticks >= PLUG_LOCK_TICKS)
                {
                    setGate(level, variant, false);
                    setBoardingBridgeExtension(level, variant, 0);
                    put(level, variant, entry.withPhase(Phase.DRAINING, 0,
                            entry.carrier(), entry.lclLayers()));
                }
                else
                {
                    put(level, variant, entry.withPhase(Phase.PLUG_LOCKING,
                            ticks, entry.carrier(), entry.lclLayers()));
                }
            }
            case DRAINING ->
            {
                unit.setNervLogisticsLocked(true);
                EntryPlugDirector.ensureCraneStowed(level, variant);
                // The fixed wet-cage gantry stays closed until the LCL is
                // fully drained, then opens mechanically.  It must remain in
                // the bay after opening; the moving deck has separate
                // ownership and cannot delete it.
                if (!EntryPlugDirector.hasLaunchLock(level, variant, unit))
                {
                    holdPlugFault(level, variant, unit, entry,
                            "pilot/plug lock opened during hangar drain");
                    break;
                }
                int ticks = entry.ticks() + 1;
                int lcl = entry.lclLayers();
                int confirmedDry = DRAIN_ZERO_TICKS.getOrDefault(
                        entry.canonicalId(), 0);
                float restraint = lcl > 0 ? 1.0F
                        : 1.0F - Mth.clamp(confirmedDry
                                / (float) RESTRAINT_TRAVEL_TICKS,
                                0.0F, 1.0F);
                if (!NervCarrierVisuals.updateRestraints(level, unit,
                        hangar.getX() + 0.5D, hangar.getY(),
                        hangar.getZ() + 0.5D, restraint))
                {
                    // Keep confirmedDry unchanged, so occupied travel never
                    // reaches TO_SILO merely because its visual was stopped.
                    break;
                }
                // Remove each physical top layer at the start of its interval;
                // the client surface then descends continuously to the next
                // real layer instead of waiting and dropping one full block.
                if ((ticks - 1) % FLUID_LAYER_TICKS == 0 && lcl > 0)
                {
                    setLclLayer(level, variant, lcl, false);
                    lcl--;
                }
                if (lcl <= 0)
                {
                    int remaining = drainLclEnvelope(level, variant);
                    if (remaining == 0)
                    {
                        int confirmations = DRAIN_ZERO_TICKS.merge(
                                entry.canonicalId(), 1, Integer::sum);
                        if (confirmations >= RESTRAINT_TRAVEL_TICKS)
                        {
                            DRAIN_ZERO_TICKS.remove(entry.canonicalId());
                            setGate(level, variant, true);
                            restoreStaticCarrier(level, variant, hangar);
                            put(level, variant, entry.withPhase(Phase.TO_SILO,
                                    0, hangar.getZ(), 0));
                            unit.playSound(SoundEvents.IRON_DOOR_OPEN,
                                    2.8F, 0.62F);
                        }
                        else
                        {
                            put(level, variant, entry.withPhase(
                                    Phase.DRAINING, ticks,
                                    entry.carrier(), 0));
                        }
                    }
                    else
                    {
                        DRAIN_ZERO_TICKS.remove(entry.canonicalId());
                        ProjectSeele.LOGGER.warn(
                                "NERV EVA-0{} drain interlock holding: {} LCL cells remain",
                                variant, remaining);
                        put(level, variant, entry.withPhase(Phase.DRAINING,
                                ticks, entry.carrier(), 0));
                    }
                }
                else
                {
                    DRAIN_ZERO_TICKS.remove(entry.canonicalId());
                    put(level, variant, entry.withPhase(Phase.DRAINING,
                            ticks, entry.carrier(), lcl));
                }
            }
            case TO_SILO ->
            {
                EntryPlugDirector.ensureCraneStowed(level, variant);
                if (!EntryPlugDirector.hasLaunchLock(level, variant, unit))
                {
                    holdPlugFault(level, variant, unit, entry,
                            "pilot/plug lock opened during linear transfer");
                    break;
                }
                tickHorizontal(level, variant, unit, entry,
                        hangar, silo, true);
            }
            case SILO_READY ->
            {
                if(UndergroundSortieR48.tickMotionR48(level,variant,unit))break;
                unit.setNervLogisticsLocked(true);
                EntryPlugDirector.ensureCraneStowed(level, variant);
                if (!EntryPlugDirector.hasLaunchLock(level, variant, unit))
                {
                    holdPlugFault(level, variant, unit, entry,
                            "pilot/plug lock opened in the launch cage");
                    break;
                }
                if (!unit.isLaunchSequenceActive() && unit.getY() >= surface.getY() - 2.0D)
                {
                    // Launch completion must not re-arm the old underground
                    // parking lease before publishing the deployed receipt.
                    unit.clearSortieDestination();
                    unit.setNervLogisticsLocked(false);
                    put(level, variant, entry.withPhase(Phase.DEPLOYED,
                            0, surface.getY(), 0));
                    break;
                }
                unit.setSortieDestination(level.dimension(), surface);
                unit.setSortieParkingBed(silo);
                if (unit.isLaunchSequenceActive())
                {
                    return;
                }
            }
            case DEPLOYED ->
            {
                if(UndergroundSortieR48.tickMotionR48(level,variant,unit))break;
                if(NervAirLiftR30.ownsMotion(unit)||NervAirLiftR30.waitingAtHead(unit))break;
                double dx = unit.getX() - (surface.getX() + 0.5D);
                double dz = unit.getZ() - (surface.getZ() + 0.5D);
                boolean trainingStandby = unit.isTrainingPilotActive()&&!NervPilotCombatR30.controls(unit)
                        && dx * dx + dz * dz <= 2.25D
                        && Math.abs(unit.getY() - (surface.getY() + 1.0D)) <= 8.0D;
                if (trainingStandby)
                {
                    // A synthetic pilot has no real movement packets to hold
                    // the enormous chassis against mob AI and gravity. Treat
                    // its exact recovery-pad arrival as a stationary MAGI
                    // standby state until the surface console authorizes
                    // descent. Human pilots remain fully released.
                    unit.setNervLogisticsLocked(true);
                    unit.moveOnNervCarrier(surface.getX() + 0.5D,
                            surface.getY() + 2.0D, surface.getZ() + 0.5D,
                            EvaUnit01Entity.SILO_BAY_YAW);
                }
                else
                {
                    unit.setNervLogisticsLocked(false);
                }
            }
            case DESCENDING -> tickDescent(level, variant, unit, entry,
                    surface, silo);
            case TO_HANGAR -> tickHorizontal(level, variant, unit, entry,
                    silo, hangar, false);
            case FILLING ->
            {
                unit.setNervLogisticsLocked(true);
                if(unit.getPersistentData().getBoolean("R50EmptyFaultBayRecovery"))
                {
                    var returningPlug=EntryPlugDirector.canonical(level,variant);
                    if(returningPlug==null||returningPlug.isVehicle()||returningPlug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_SUSPENDED
                            ||!EntryPlugDirector.originalCageDockR50(level,variant,unit,returningPlug))break;
                    unit.getPersistentData().remove("R50EmptyFaultBayRecovery");
                }
                setGate(level, variant, false);
                setBoardingBridgeExtension(level, variant, 0);
                int ticks = entry.ticks() + 1;
                float restraint = Mth.clamp(
                        ticks / (float) RESTRAINT_TRAVEL_TICKS,
                        0.0F, 1.0F);
                if (!NervCarrierVisuals.updateRestraints(level, unit,
                        hangar.getX() + 0.5D, hangar.getY(),
                        hangar.getZ() + 0.5D, restraint))
                {
                    // Do not refill or extract through an occupied closing
                    // sleeve/shoulder sweep, and retain the exact phase tick.
                    break;
                }
                if(ticks<80)
                {
                    // Close the fixed restraints and sink the transfer rack
                    // before the reverse capsule sweep enters that volume.
                    put(level,variant,entry.withPhase(Phase.FILLING,ticks,entry.carrier(),entry.lclLayers()));
                    break;
                }
                EntryPlugCarrierEntity plug =
                        EntryPlugDirector.canonical(level, variant);
                if (plug == null)
                {
                    holdPlugFault(level, variant, unit, entry,
                            "canonical capsule unavailable during wet-cage extraction");
                    break;
                }
                if (plug.getInsertionStage()
                        == EntryPlugCarrierEntity.STAGE_LOCKED)
                {
                    net.minecraft.world.entity.LivingEntity pilot =
                            unit.getPilotEntity();
                    boolean extracted=pilot==null?EntryPlugDirector.extractEmptyCapsule(level,variant,unit)
                            :EntryPlugDirector.ejectPilotToPlug(level,variant,unit,pilot);
                    if (!extracted)
                    {
                        holdPlugFault(level, variant, unit, entry,
                                "wet-cage crane could not begin capsule extraction");
                        break;
                    }
                }
                if (plug.getInsertionStage()
                        == EntryPlugCarrierEntity.STAGE_EJECTING)
                {
                    /*
                     * The same occupied capsule is physically drawn out of
                     * the dorsal socket before the wet cage refills.  Filling
                     * while it was still LOCKED left a PARKED airframe with
                     * its plug inside; the next PREPARE then tried to insert
                     * that capsule a second time and failed its dock-pose
                     * interlock.
                     */
                    put(level, variant, entry.withPhase(Phase.FILLING,
                            ticks, entry.carrier(), 0));
                    break;
                }
                // Extraction has reached the parked dock but LCL refill and
                // bridge restoration continue for several seconds.  Keep the
                // same crane lease alive at the capsule instead of letting it
                // time out and respawn only when PARKED begins.
                EntryPlugDirector.maintainCraneAtCurrentPlug(
                        level, variant, plug);
                int lcl = entry.lclLayers();
                if (ticks >= RESTRAINT_TRAVEL_TICKS
                        && ticks % FLUID_LAYER_TICKS == 0
                        && lcl
                        < FacilityV2EvaRuntime.LCL_SHOULDER_LAYERS)
                {
                    lcl++;
                    setLclLayer(level, variant, lcl, true);
                }
                if (lcl
                        >= FacilityV2EvaRuntime.LCL_SHOULDER_LAYERS)
                {
                    unit.setCarrierRiseProgress(0F);
                    unit.setRecoveryRackR39(false);
                    unit.setSortieDestination(level.dimension(), surface);
                    unit.setSortieParkingBed(hangar);
                    setBoardingBridgeExtension(level, variant,
                            FacilityV2EvaRuntime.BRIDGE_SEGMENTS);
                    EntryPlugDirector.ensureSuspended(level, variant, unit);
                    put(level, variant, entry.withPhase(Phase.PARKED,
                            0, hangar.getZ(), lcl));
                    TvMissionEquipmentR45.recoveryCompleted(unit);
                    unit.refreshTvMissionEquipmentR45();
                    unit.playSound(SoundEvents.BEACON_ACTIVATE, 2.8F, 0.82F);
                }
                else
                {
                    put(level, variant, entry.withPhase(Phase.FILLING,
                            ticks, entry.carrier(), lcl));
                }
            }
        }
    }

    private static void maintainHangarDoor(ServerLevel level, int variant,
                                           FleetEntry entry)
    {
        // R28 retains the compact, human-approved three-cage pressure doors
        // even when partial Facility-v2 receipts are present elsewhere.
        boolean moving = entry.phase() == Phase.TO_SILO
                || entry.phase() == Phase.TO_HANGAR;
        maintainHangarDoor(level, variant, moving);
    }

    private static void maintainHangarDoor(ServerLevel level, int variant,
                                           boolean moving)
    {
        BlockPos bed = EvaHangarBuilder.hangarBed(
                RegionalFacilityLayout.evaOrigin(level), variant);
        if (!moving && !level.hasChunkAt(bed))
        {
            return;
        }
        Vec3 centre = new Vec3(bed.getX() + 0.5D,
                bed.getY() + 1.0D,
                EvaHangarBuilder.gateZ(
                        RegionalFacilityLayout.evaOrigin(level)) + 0.5D);
        NervHangarDoorEntity.reconcile(level,variant,centre,HangarEmergencyR47.desiredOpenR47(level,variant,centre,moving));
    }

    private static void requireCompactLogistics(
            ServerLevel level, String operation)
    {
        if (!FacilityWorldPolicy.legacyGenerationAllowed(level.getServer())
                && !FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            throw new IllegalStateException(
                    "Retired EVA logistics operation '" + operation
                            + "' is disabled until Facility v2 cage and "
                            + "silo anchors have completion receipts.");
        }
    }

    private static boolean logisticsReady(ServerLevel level, int variant)
    {
        return FacilityWorldPolicy.legacyGenerationAllowed(level.getServer())
                || FacilityWorldPolicy.isS20Rebuild(level.getServer())
                || FacilityV2EvaRuntime.ready(level, variant);
    }

    private static boolean compactLiftMarkersPresent(ServerLevel level)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            if (!level.getBlockState(
                    IntegratedNervMapBuilder.lowerLiftBed(level, variant))
                    .is(net.minecraft.world.level.block.Blocks.LODESTONE))
            {
                return false;
            }
            // Surface stations are logical coordinates.  Their Y=79 cells
            // must stay open; the synchronized hatch and collision seal live
            // one block above them.
            if (!level.getBlockState(
                    IntegratedNervMapBuilder.surfaceLiftBed(level, variant))
                    .isAir())
            {
                return false;
            }
        }
        return true;
    }

    public static BlockPos assignedHangarBedR33(ServerLevel level,int variant){return hangarBed(level,variant);}
    public static boolean inAssignedHangarR33(ServerLevel level,EvaUnit01Entity unit)
    {var bed=hangarBed(level,unit.getUnitVariant());return unit.position().distanceToSqr(new net.minecraft.world.phys.Vec3(bed.getX()+.5,bed.getY()+1,bed.getZ()+.5))<16;}

    private static BlockPos hangarBed(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.hangarBed(level, variant);
        }
        return EvaHangarBuilder.hangarBed(
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    private static BlockPos lowerLiftBed(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.lowerLiftBed(level, variant);
        }
        return IntegratedNervMapBuilder.lowerLiftBed(level, variant);
    }

    /**
     * Validates the exact lower launch marker in the active facility frame.
     * Clean S19 worlds must never fall back to the retired integrated-map
     * coordinates merely because both stations use a lodestone.
     */
    public static boolean isAssignedLowerLaunchBed(
            ServerLevel level, int variant, BlockPos bed)
    {
        if (FacilityWorldPolicy.isCleanRebuild(level.getServer()))
        {
            return FacilityV2EvaRuntime.ready(level, variant)
                    && FacilityV2EvaRuntime.lowerLiftBed(level, variant)
                    .equals(bed);
        }
        return IntegratedNervMapBuilder.lowerLiftBed(level,variant).equals(bed);
    }

    public static BlockPos surfaceTransportBedR30(ServerLevel level,int variant)
    {
        if(variant<0||variant>2)throw new IllegalArgumentException("Invalid NERV unit");
        return surfaceLiftBed(level,variant);
    }
    private static BlockPos surfaceLiftBed(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.surfaceLiftBed(level, variant);
        }
        return IntegratedNervMapBuilder.surfaceLiftBed(level, variant);
    }

    private static int lclLevel(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.lclLevel(level, variant);
        }
        return EvaHangarBuilder.lclLevel(level,
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    private static void setLclLayer(ServerLevel level, int variant,
                                    int layer, boolean filled)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.setLclLayer(
                    level, variant, layer, filled);
            return;
        }
        EvaHangarBuilder.setLclLayer(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, layer, filled);
    }

    private static int drainLclEnvelope(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.drainLclEnvelope(level, variant);
        }
        return EvaHangarBuilder.drainLclEnvelope(level,
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    private static void setBoardingBridgeExtension(
            ServerLevel level, int variant, int segments)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.setBoardingBridgeExtension(
                    level, variant, segments);
            return;
        }
        EvaHangarBuilder.setBoardingBridgeExtension(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, segments);
    }

    private static void setGate(ServerLevel level, int variant,
                                boolean open)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.setGate(level, variant, open);
            return;
        }
        EvaHangarBuilder.setGate(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, open);
    }

    private static void setCarrier(ServerLevel level, int variant,
                                   BlockPos centre, boolean present)
    {
        if(FacilityLayoutR20.active(level.getServer()))return;
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.setCarrier(
                    level, variant, centre, present);
            return;
        }
        EvaHangarBuilder.setCarrier(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, centre.getZ(), present);
    }

    private static void ensureTransportGuideway(ServerLevel level, int variant,
                                                BlockPos start, BlockPos end)
    {
        if(FacilityLayoutR20.active(level.getServer()))return;
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.ensureTransportGuideway(
                    level, variant, start, end);
            return;
        }
        EvaHangarBuilder.ensureTransportGuideway(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, start, end);
    }

    private static void restoreStaticCarrier(
            ServerLevel level, int variant, BlockPos centre)
    {
        if(FacilityLayoutR20.active(level.getServer()))return;
        // The surface head is closed by NervSiloDoorEntity at Y+1.  A second
        // 29x29 carrier at the logical Y=79 anchor is redundant, obstructs
        // the shaft and used to leave a visible centre block after opening.
        if (centre.equals(surfaceLiftBed(level, variant)))
        {
            return;
        }
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.restoreStaticCarrier(
                    level, variant, centre);
            return;
        }
        EvaHangarBuilder.restoreStaticCarrier(level,
                RegionalFacilityLayout.evaOrigin(level),
                variant, centre);
    }

    private static ActionResult v2MigrationInhibit(String operation)
    {
        return new ActionResult(false,
                "Facility v2 " + operation
                        + " is locked until the new cage/silo anchor "
                        + "contract is complete.");
    }

    /**
     * Returns a failed PREPARE to one coherent wet-cage state. The same saved
     * plug UUID is moved back under the crane; no replacement capsule or EVA
     * is spawned. This prevents a missing hatch/ride-chain interlock from
     * holding route chunks and a retracted boarding bridge forever.
     */
    private static void abortPlugSequence(ServerLevel level, int variant,
                                          EvaUnit01Entity unit,
                                          FleetEntry entry,
                                          BlockPos hangar,
                                          String reason)
    {
        boolean started = EntryPlugDirector.abortInsertionToDock(
                level, variant, unit);
        if (!started)
        {
            started = EntryPlugDirector.abortDockedPreparation(
                    level, variant, unit);
        }
        unit.setNervLogisticsLocked(true);
        setBoardingBridgeExtension(level, variant, 0);
        if (!started)
        {
            holdPlugFault(level, variant, unit, entry,
                    reason + "; canonical capsule unavailable");
            return;
        }
        EntryPlugCarrierEntity plug = EntryPlugDirector.canonical(
                level, variant);
        Phase rollback = plug != null && plug.getInsertionStage()
                == EntryPlugCarrierEntity.STAGE_ABORT_DOCKED
                ? Phase.PLUG_ABORT_DOCKED : Phase.PLUG_ABORT_RETURNING;
        put(level, variant, entry.withPhase(
                rollback, 0, 0, entry.lclLayers()));
        ProjectSeele.LOGGER.warn(
                "NERV EVA-0{} PREPARE abort return started: {}",
                variant, reason);
        unit.playSound(SoundEvents.PISTON_CONTRACT, 2.0F, 0.58F);
    }

    private static void holdPlugFault(ServerLevel level, int variant,
                                      EvaUnit01Entity unit,
                                      FleetEntry entry, String reason)
    {
        unit.setNervLogisticsLocked(true);
        put(level, variant, entry.withPhase(Phase.PLUG_FAULT, 0,
                entry.carrier(), entry.lclLayers()));
        ProjectSeele.LOGGER.error(
                "NERV EVA-0{} entry-plug fail-closed hold: {}",
                variant, reason);
        unit.playSound(SoundEvents.IRON_DOOR_CLOSE, 1.8F, 0.48F);
    }

    private static void tickHorizontal(ServerLevel level, int variant,
                                       EvaUnit01Entity unit, FleetEntry entry,
                                       BlockPos start, BlockPos end,
                                       boolean outbound)
    {
        double dx = end.getX() - start.getX();
        double dy = end.getY() - start.getY();
        double dz = end.getZ() - start.getZ();
        int duration = Math.max(80, Mth.ceil(
                Math.sqrt(dx * dx + dy * dy + dz * dz)
                        / HORIZONTAL_BLOCKS_PER_TICK));
        int ticks = Math.min(duration, entry.ticks() + 1);
        double progress = smoothCarrierProgress(ticks / (double) duration);
        double exactX = Mth.lerp(progress, start.getX(), end.getX());
        double exactY = CarrierGuidePath.height(Vec3.atLowerCornerOf(start),Vec3.atLowerCornerOf(end),progress);
        double exactZ = Mth.lerp(progress, start.getZ(), end.getZ());
        int carrierZ = Mth.floor(exactZ + 0.5D);
        if (entry.ticks() == 0)
        {
            /*
             * The mechanical-only rebuild already owns and clears the complete
             * 33 x 68 transport envelope.  Runtime used to erase every unknown
             * block in that volume again on the first transfer tick.  Besides
             * hiding real obstructions, that could delete observation glazing,
             * lights or a later scene revision.  From here onward the logistics
             * state machine moves only its carrier/entity; authored scenery is
             * never destructively "repaired" during a sortie.
             */
            ensureTransportGuideway(level, variant, start, end);
            setCarrier(level, variant, start, false);
            unit.beginNervCarrierMotion(
                    new Vec3(start.getX() + 0.5D, start.getY() + 1.0D,
                            start.getZ() + 0.5D),
                    new Vec3(end.getX() + 0.5D, end.getY() + 1.0D,
                            end.getZ() + 0.5D), duration);
        }
        NervCarrierVisuals.update(level, unit, exactX + 0.5D,
                exactY, exactZ + 0.5D);
        unit.setNervLogisticsLocked(true);
        unit.moveOnNervCarrier(exactX + 0.5D, exactY + 1.0D,
                exactZ + 0.5D, EvaUnit01Entity.SILO_BAY_YAW);
        if (ticks < duration)
        {
            put(level, variant, entry.withPhase(entry.phase(), ticks,
                    carrierZ, entry.lclLayers()));
            return;
        }
        // The final moving footprint is already centred on the station.
        // Repainting it as AIR and immediately rebuilding it doubled the
        // largest block update spike for no visible result.
        NervCarrierVisuals.remove(level, unit);
        unit.endNervCarrierMotion();
        restoreStaticCarrier(level, variant, end);
        unit.moveOnNervCarrier(end.getX() + 0.5D, end.getY() + 1.0D,
                end.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW);
        if (outbound)
        {
            setGate(level, variant, false);
            unit.setSortieDestination(level.dimension(),
                    surfaceLiftBed(level, variant));
            unit.setSortieParkingBed(end);
            if (!unit.armPreparedLaunch(end))
            {
                /*
                 * Do not publish SILO_READY unless the entity itself owns a
                 * real launch lock. Otherwise the operations button appears
                 * dead because releaseLaunchFromCommand() correctly refuses
                 * an unarmed chassis. Bring the same airframe and plug back
                 * through the physical recovery path instead of cloning or
                 * teleporting either one.
                 */
                ProjectSeele.LOGGER.error(
                        "NERV EVA-0{} could not arm at lower silo {}; returning to wet cage",
                        variant, end.toShortString());
                put(level, variant, entry.withPhase(Phase.TO_HANGAR,
                        0, end.getZ(), 0));
                return;
            }
            put(level, variant, entry.withPhase(Phase.SILO_READY,
                    0, end.getZ(), 0));
            level.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    end.getX() + 0.5D, end.getY() + 1.2D, end.getZ() + 0.5D,
                    32, 4.0D, 0.5D, 4.0D, 0.05D);
        }
        else
        {
            setGate(level, variant, false);
            unit.setSortieDestination(level.dimension(),
                    surfaceLiftBed(level, variant));
            unit.setSortieParkingBed(end);
            put(level, variant, entry.withPhase(Phase.FILLING,
                    0, end.getZ(), 0));
        }
    }

    private static void tickDescent(ServerLevel level, int variant,
                                    EvaUnit01Entity unit, FleetEntry entry,
                                    BlockPos surface, BlockPos silo)
    {
        boolean staged=unit.getPersistentData().getBoolean("RecoveryRiseR39");
        int offset=staged?100:0;
        if(staged && entry.ticks()<=100)
        {
            unit.setNervLogisticsLocked(true);unit.setNoGravity(true);unit.setDeltaMovement(Vec3.ZERO);
            if(entry.ticks()<100)
                put(level,variant,entry.withPhase(Phase.DESCENDING,entry.ticks()+1,surface.getY()+1,0));
            else if(NervSiloDoorEntity.hasOpenRecoveryRoute(level,variant,surface))
            {
                put(level,variant,entry.withPhase(Phase.DESCENDING,101,surface.getY()+1,0));
                ProjectSeele.LOGGER.info("R39 recovery descent released variant={} support=1 hatch=open",variant);
            }
            return;
        }
        int surfaceCarrierY = surface.getY() + 1;
        int distance = surfaceCarrierY - silo.getY();
        int duration = Math.max(1, Mth.ceil(distance / VERTICAL_BLOCKS_PER_TICK));
        int ticks = Math.min(duration, entry.ticks() - offset + 1);
        double progress = smoothCarrierProgress(ticks / (double) duration);
        double exactY = Mth.lerp(progress, surfaceCarrierY, silo.getY());
        int carrierY = Mth.floor(exactY + 0.5D);
        if (entry.ticks() == (staged?101:0))
        {
            unit.beginNervCarrierMotion(
                    new Vec3(surface.getX() + 0.5D,
                            surface.getY() + 2.0D,
                            surface.getZ() + 0.5D),
                    new Vec3(silo.getX() + 0.5D,
                            silo.getY() + 1.0D,
                            silo.getZ() + 0.5D), duration);
        }
        NervCarrierVisuals.update(level, unit, surface.getX() + 0.5D,
                exactY, surface.getZ() + 0.5D);
        unit.setNervLogisticsLocked(true);
        unit.moveOnNervCarrier(surface.getX() + 0.5D, exactY + 1.0D,
                surface.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW);
        if (ticks < duration)
        {
            put(level, variant, entry.withPhase(Phase.DESCENDING,
                    ticks + offset, carrierY, 0));
            return;
        }
        unit.getPersistentData().remove("RecoveryRiseR39");
        NervCarrierVisuals.remove(level, unit);
        unit.endNervCarrierMotion();
        restoreStaticCarrier(level, variant, silo);
        setGate(level, variant, true);
        unit.moveOnNervCarrier(silo.getX() + 0.5D, silo.getY() + 1.0D,
                silo.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW);
        put(level, variant, entry.withPhase(Phase.TO_HANGAR,
                0, silo.getZ(), 0));
    }

    /** Quintic S-curve: zero jerk at both carrier endpoints. */
    private static double smoothCarrierProgress(double progress)
    {
        double t = Mth.clamp(progress, 0.0D, 1.0D);
        return t * t * t * (t * (t * 6.0D - 15.0D) + 10.0D);
    }

    private static float visualLclLevel(FleetEntry entry)
    {
        float layers = entry.lclLayers();
        if (entry.phase() == Phase.DRAINING && layers > 0.0F)
        {
            int phase = Math.floorMod(entry.ticks(), FLUID_LAYER_TICKS);
            if (phase != 0)
            {
                layers += (FLUID_LAYER_TICKS - phase)
                        / (float) FLUID_LAYER_TICKS;
            }
        }
        else if (entry.phase() == Phase.FILLING)
        {
            int visualStart = RESTRAINT_TRAVEL_TICKS - FLUID_LAYER_TICKS;
            if (entry.ticks() >= visualStart)
            {
                int phase = Math.floorMod(entry.ticks() - visualStart,
                        FLUID_LAYER_TICKS);
                layers += phase / (float) FLUID_LAYER_TICKS;
            }
        }
        return Mth.clamp(layers, 0.0F,
                FacilityV2EvaRuntime.LCL_SHOULDER_LAYERS);
    }

    private static void setVerticalCarrier(ServerLevel level, BlockPos shaft,
                                           int y, boolean present)
    {
        int half = EvaHangarBuilder.CARRIER_HALF_EXTENT;
        for (int x = -half; x <= half; x++)
        {
            for (int z = -half; z <= half; z++)
            {
                BlockPos position = new BlockPos(shaft.getX() + x, y,
                        shaft.getZ() + z);
                if (present)
                {
                    boolean rim = Math.abs(x) == half
                            || Math.abs(z) == half;
                    level.setBlock(position, rim
                            ? net.minecraft.world.level.block.Blocks.IRON_BLOCK.defaultBlockState()
                            : net.minecraft.world.level.block.Blocks.LIGHT_GRAY_CONCRETE.defaultBlockState(), 2);
                    PerformanceCounters.recordWorldBlockWrites(1);
                }
                else
                {
                    level.setBlock(position,
                            net.minecraft.world.level.block.Blocks.AIR.defaultBlockState(), 2);
                    PerformanceCounters.recordWorldBlockWrites(1);
                }
            }
        }
        if (present && y == shaft.getY())
        {
            level.setBlock(new BlockPos(shaft.getX(), y, shaft.getZ()),
                    net.minecraft.world.level.block.Blocks.LODESTONE.defaultBlockState(), 2);
            PerformanceCounters.recordWorldBlockWrites(1);
        }
    }

    private static void setVerticalCarrier(
            ServerLevel level, int variant, BlockPos shaft,
            int y, boolean present)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            FacilityV2EvaRuntime.setCarrier(level, variant,
                    new BlockPos(shaft.getX(), y, shaft.getZ()), present);
            return;
        }
        setVerticalCarrier(level, shaft, y, present);
    }

    private static boolean isAtAssignedHangar(ServerLevel level,
                                               EvaUnit01Entity unit,
                                               int variant)
    {
        if (!level.dimension().equals(GeoFrontCommands.GEOFRONT))
        {
            return false;
        }
        BlockPos bed = hangarBed(level, variant);
        double horizontal = new Vec3(unit.getX(), 0.0D, unit.getZ())
                .distanceTo(new Vec3(bed.getX() + 0.5D, 0.0D,
                        bed.getZ() + 0.5D));
        return horizontal <= 12.0D
                && Math.abs(unit.getY() - (bed.getY() + 1.0D)) <= 8.0D;
    }

    private static EvaUnit01Entity canonicalAnywhere(MinecraftServer server,
                                                      UUID id)
    {
        for (ServerLevel dimension : server.getAllLevels())
        {
            Entity direct = dimension.getEntity(id);
            if (direct instanceof EvaUnit01Entity unit && unit.isAlive())
            {
                return unit;
            }
            for (EvaUnit01Entity unit : loadedFleet(dimension))
            {
                if (unit.getUUID().equals(id))
                {
                    return unit;
                }
            }
        }
        return null;
    }

    private static void maintainDormantLaunch(EvaUnit01Entity unit,
                                               FleetEntry entry)
    {
        UUID id = entry.canonicalId();
        if (entry.phase() != Phase.SILO_READY
                || !unit.isLaunchSequenceActive())
        {
            LAST_ENTITY_TICK.remove(id);
            DORMANT_LAUNCH_TICKS.remove(id);
            return;
        }
        int current = unit.tickCount;
        Integer previous = LAST_ENTITY_TICK.put(id, current);
        if (previous == null || previous != current)
        {
            int recovered = DORMANT_LAUNCH_TICKS.getOrDefault(id, 0);
            if (recovered > 0)
            {
                ProjectSeele.LOGGER.info(
                        "NERV dormant launch watchdog released: eva={} assistedTicks={}",
                        unit.getStringUUID(), recovered);
            }
            DORMANT_LAUNCH_TICKS.remove(id);
            return;
        }
        int assisted = DORMANT_LAUNCH_TICKS.merge(id, 1, Integer::sum);
        if (assisted == 1)
        {
            ProjectSeele.LOGGER.warn(
                    "NERV dormant launch watchdog engaged: eva={} y={} launchTicks={}",
                    unit.getStringUUID(),
                    String.format(Locale.ROOT, "%.3f", unit.getY()),
                    unit.getLaunchTicks());
        }
        unit.tickDormantNervLaunch();
    }

    /** Clears process-local UUID/tick state when an integrated server stops. */
    public static void resetRuntime()
    {
        ROUTE_TICKET_STATE.clear();
        PHASE_STARTED_AT.clear();
        LAST_ENTITY_TICK.clear();
        DORMANT_LAUNCH_TICKS.clear();
        DRAIN_ZERO_TICKS.clear();
        VERIFIED_INFRASTRUCTURE.clear();
        RESCUE_TICKETS_RELEASED.clear();
        FLEET_STATION_LOAD_DEADLINE.clear();
        FLEET_STATIONS_SETTLED.clear();
    }

    /**
     * Releases persistent Forge tickets before the integrated server closes.
     * Clearing the process-local cache alone leaves an interrupted PREPARE
     * route force-loaded in the next session.
     */
    public static void releaseRouteTickets(MinecraftServer server)
    {
        ServerLevel level = server.getLevel(GeoFrontCommands.GEOFRONT);
        if (level == null)
        {
            return;
        }
        EvaFleetSavedData data = EvaFleetSavedData.get(server);
        for (int variant = 0; variant < 3; variant++)
        {
            FleetEntry entry = data.entry(variant).orElse(null);
            if (entry != null)
            {
                maintainRouteChunks(level, variant,
                        entry.canonicalId(), false);
            }
        }
    }

    private static void maintainRouteChunks(ServerLevel level, int variant,
                                            UUID canonicalId, boolean forced)
    {
        Boolean previous = ROUTE_TICKET_STATE.put(canonicalId, forced);
        if (previous != null && previous == forced)
        {
            return;
        }
        BlockPos hangar = hangarBed(level, variant);
        BlockPos surface = surfaceLiftBed(level, variant);
        BlockPos boardingStart = FacilityV2EvaRuntime.ready(level, variant)
                ? FacilityV2EvaRuntime.statusControl(level, variant)
                        .offset(0, 0, -5)
                : RegionalFacilityLayout.evaOrigin(level).offset(
                        IntegratedNervMapBuilder.LIFT_X[variant],
                        EvaHangarBuilder.GALLERY_Y + 1,
                        EvaHangarBuilder.GALLERY_Z - 1);
        int minX = Math.min(boardingStart.getX(),
                Math.min(hangar.getX(), surface.getX()));
        int maxX = Math.max(boardingStart.getX(),
                Math.max(hangar.getX(), surface.getX()));
        int minZ = Math.min(boardingStart.getZ(),
                Math.min(hangar.getZ(), surface.getZ()));
        int maxZ = Math.max(boardingStart.getZ(),
                Math.max(hangar.getZ(), surface.getZ()));
        int minChunkX = (minX
                - ROUTE_CHUNK_MARGIN) >> 4;
        int maxChunkX = (maxX
                + ROUTE_CHUNK_MARGIN) >> 4;
        int minChunkZ = (minZ
                - ROUTE_CHUNK_MARGIN) >> 4;
        int maxChunkZ = (maxZ
                + ROUTE_CHUNK_MARGIN) >> 4;
        int changed = 0;
        for (int chunkX = minChunkX; chunkX <= maxChunkX; chunkX++)
        {
            for (int chunkZ = minChunkZ; chunkZ <= maxChunkZ; chunkZ++)
            {
                if (ForgeChunkManager.forceChunk(level, ProjectSeele.MODID,
                        canonicalId, chunkX, chunkZ, forced, true))
                {
                    changed++;
                }
            }
        }

        ProjectSeele.LOGGER.info(
                "NERV EVA-0{} logistics route tickets {}: changed={} range=[{},{}]..[{},{}]",
                variant, forced ? "ACQUIRED" : "RELEASED", changed,
                minChunkX, minChunkZ, maxChunkX, maxChunkZ);
        PerformanceCounters.recordForcedChunkDelta(
                forced ? changed : -changed);
    }

    private static void loadFleetStations(ServerLevel level)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            loadVariantStations(level, variant);
        }
    }

    /** Block chunks and saved entities attach on different server tasks. */
    private static boolean fleetStationEntitiesSettled(ServerLevel level)
    {
        if (FLEET_STATIONS_SETTLED.contains(level) && fleetStationEntityDataReady(level))
        {
            return true;
        }
        loadFleetStations(level);
        if (!fleetStationEntityDataReady(level))
        {
            if (!FLEET_STATION_LOAD_DEADLINE.containsKey(level))
            {
                FLEET_STATION_LOAD_DEADLINE.put(level, System.nanoTime());
                ProjectSeele.LOGGER.info("NERV fleet reconciliation waiting for saved station entities");
            }
            return false;
        }
        FLEET_STATION_LOAD_DEADLINE.remove(level);
        FLEET_STATIONS_SETTLED.add(level);
        return true;
    }

    private static boolean fleetStationEntityDataReady(ServerLevel level)
    {
        for (int variant = 0; variant < 3; variant++)
        {
            if (!level.areEntitiesLoaded(ChunkPos.asLong(hangarBed(level, variant)))
                    || !level.areEntitiesLoaded(ChunkPos.asLong(lowerLiftBed(level, variant)))
                    || !level.areEntitiesLoaded(ChunkPos.asLong(surfaceLiftBed(level, variant)))
                    || !level.areEntitiesLoaded(ChunkPos.asLong(BlockPos.containing(EntryPlugDirector.plugRestPosition(level, variant)))))
            {
                return false;
            }
            if (!level.areEntitiesLoaded(ChunkPos.asLong(TrainingPilotDirector.requestedStandby(level, variant))))
            {
                return false;
            }
        }
        return true;
    }

    /** Loads one requested EVA line and its pilot waiting area. */
    public static void loadControlTarget(ServerLevel level, int variant)
    {
        if (variant < EvaUnit01Entity.UNIT_00
                || variant > EvaUnit01Entity.UNIT_02)
        {
            return;
        }
        loadVariantStations(level, variant);
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            if (!fleetStationEntitiesSettled(level))
            {
                return;
            }
            FleetEntry receipt = entry(level, variant);
            EvaUnit01Entity unit = canonical(level, variant);
            /*
             * A PARKED (or not-yet-created) airframe has exactly one legal
             * location: its loaded wet cage.  Repairing that narrow case is
             * safe and makes the physical command buttons self-heal after an
             * old renderer/cleanup pass removed the entity.  In-transit and
             * deployed receipts remain fail-closed so this can never clone a
             * real sortie elsewhere in the world.
             */
            if (unit == null && (receipt == null
                    || receipt.phase() == Phase.PARKED))
            {
                ensureFleet(level);
            }
        }
    }

    /** Temporary tickets cover station terrain and the separately saved pilot. */
    private static void loadVariantStations(ServerLevel level, int variant)
    {
        PerformanceCounters.recordSyncChunkLoads(5);
        for (BlockPos station : List.of(hangarBed(level, variant),
                lowerLiftBed(level, variant), surfaceLiftBed(level, variant),
                BlockPos.containing(EntryPlugDirector.plugRestPosition(level, variant)),
                TrainingPilotDirector.requestedStandby(level, variant)))
        {
            ChunkPos chunk = new ChunkPos(station);
            level.getChunkSource().addRegionTicket(STATION_LOAD_TICKET, chunk, 2, chunk);
            level.getChunkAt(station);
        }
    }

    private static List<EvaUnit01Entity> loadedFleet(ServerLevel level)
    {
        PerformanceCounters.recordGlobalEntityScan();
        List<EvaUnit01Entity> units = new ArrayList<>();
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof EvaUnit01Entity unit && unit.isAlive() && !unit.isExperimentalUnit())
            {
                units.add(unit);
            }
        }
        return units;
    }
    private static EvaUnit01Entity canonical(ServerLevel level, int variant)
    {
        UUID id = EvaFleetSavedData.get(level.getServer())
                .canonicalId(variant).orElse(null);
        if (id == null)
        {
            return null;
        }
        Entity direct = level.getEntity(id);
        if (direct instanceof EvaUnit01Entity unit && unit.isAlive())
        {
            return unit;
        }
        // ServerLevel#getEntity(UUID) is already the authoritative loaded
        // entity index.  The former fallback walked every loaded entity on
        // every tick for each unloaded parked EVA.  Legacy GeoFront saves can
        // contain thousands of construction drops, turning an idle facility
        // into three full-world scans per tick.  Active routes hold their
        // chunks and resolve through the UUID index as soon as they load.
        return null;
    }

    private static ActionResult rescueInhibit(String operation)
    {
        return new ActionResult(false, operation
                + " is inhibited by performance rescue mode.");
    }

    private static FleetEntry entry(ServerLevel level, int variant)
    {
        return EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
    }

    private static void put(ServerLevel level, int variant, FleetEntry entry)
    {
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        FleetEntry previous = data.entry(variant).orElse(null);
        long now = System.nanoTime();
        if (previous == null || previous.phase() != entry.phase())
        {
            long started = PHASE_STARTED_AT.getOrDefault(
                    entry.canonicalId(), now);
            ProjectSeele.LOGGER.info(
                    "NERV EVA-0{} logistics phase: {} -> {} elapsedMs={} phaseTicks={} carrier={} lcl={}",
                    variant, previous == null ? "UNREGISTERED" : previous.phase(),
                    entry.phase(), (now - started) / 1_000_000L,
                    previous == null ? 0 : previous.ticks(),
                    entry.carrier(), entry.lclLayers());
            PHASE_STARTED_AT.put(entry.canonicalId(), now);
        }
        else
        {
            PHASE_STARTED_AT.putIfAbsent(entry.canonicalId(), now);
        }
        data.put(variant, entry);
    }

    private static EvaUnit01Entity createUnit(ServerLevel level, int variant)
    {
        return switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> ModEntities.EVA_UNIT00.get().create(level);
            case EvaUnit01Entity.UNIT_02 -> ModEntities.EVA_UNIT02.get().create(level);
            default -> ModEntities.EVA_UNIT01.get().create(level);
        };
    }

    private static void placeAt(EvaUnit01Entity unit, BlockPos bed)
    {
        unit.moveTo(bed.getX() + 0.5D, bed.getY() + 1.0D,
                bed.getZ() + 0.5D, EvaUnit01Entity.SILO_BAY_YAW, 0.0F);
        unit.setYRot(EvaUnit01Entity.SILO_BAY_YAW);
        unit.setYBodyRot(EvaUnit01Entity.SILO_BAY_YAW);
        unit.setYHeadRot(EvaUnit01Entity.SILO_BAY_YAW);
        unit.yRotO = EvaUnit01Entity.SILO_BAY_YAW;
        unit.yBodyRotO = EvaUnit01Entity.SILO_BAY_YAW;
        unit.yHeadRotO = EvaUnit01Entity.SILO_BAY_YAW;
        unit.setDeltaMovement(Vec3.ZERO);
        unit.setNoGravity(true);
        unit.setNervLogisticsLocked(true);
    }

    /**
     * Keeps the airframe and cage civil works in one fixed world frame until
     * horizontal transfer starts.  This is intentionally conditional: a
     * stable cage does not publish a redundant entity move every server tick.
     */
    private static void holdOnHangarBed(EvaUnit01Entity unit, BlockPos bed)
    {
        double x = bed.getX() + 0.5D;
        double y = bed.getY() + 1.0D;
        double z = bed.getZ() + 0.5D;
        boolean positionDrift = unit.position().distanceToSqr(x, y, z)
                > 1.0D / (4096.0D * 4096.0D);
        boolean rotationDrift = Math.abs(Mth.wrapDegrees(unit.getYRot()
                - EvaUnit01Entity.SILO_BAY_YAW)) > 0.01F
                || Math.abs(unit.getXRot()) > 0.01F;
        if (positionDrift || rotationDrift
                || unit.getDeltaMovement().lengthSqr() > 1.0E-8D)
        {
            unit.moveOnNervCarrier(x, y, z,
                    EvaUnit01Entity.SILO_BAY_YAW);
        }
    }

    private static boolean isHangarConstrained(Phase phase)
    {
        return switch (phase)
        {
            case PARKED, BRIDGE_RETRACTING, PLUG_INSERTING,
                    PLUG_ABORT_RETURNING, PLUG_ABORT_DOCKED,
                    PLUG_LOCKING, DRAINING, FILLING -> true;
            default -> false;
        };
    }

    private static String label(int variant)
    {
        return String.format(Locale.ROOT, "EVA-%02d", variant);
    }

    public record ActionResult(boolean accepted, String message) {}

    public record Status(int variant, String phase, boolean loaded,
                         UUID canonicalId, int lclLayers, int ticks) {}
}

package com.projectseele.world;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** Owns the external entry plug from the overhead rack to the dorsal socket. */
public final class EntryPlugDirector
{
    public static final int INSERTION_TICKS = 190;
    /** Brief hard hold at the upper dock so the crane/yoke can settle before
     * the capsule starts its swept insertion path. */
    private static final int INSERTION_SETTLE_TICKS = 36;
    /** Ticks the crane takes to draw a seated capsule back out to its cage. */
    public static final int EJECTION_TICKS = 197;
    /** Pyrotechnic extraction, ballistic clearance and landing. */
    public static final int FIELD_EJECTION_TICKS = 70;
    private static final Map<ResourceKey<Level>, Map<Integer, UUID>>
            CACHED_PLUGS = new HashMap<>();
    /** Last crane frame drawn per cage, so identical ticks cost nothing. */
    private static final Map<Integer, Long> CRANE_SIGNATURE = new HashMap<>();
    /** Process-local pose of the transient S20 crane visual. */
    private static final Map<ResourceKey<Level>, CranePose[]> S20_CRANE_POSES =
            new HashMap<>();
    private static final Map<ServerLevel, java.util.Set<UUID>> EXPECTED_FIELD_WAITING_R50 =
            new java.util.WeakHashMap<>();

    private EntryPlugDirector() {}

    /**
     * Signed Z offset of the dorsal socket from the bed for an airframe parked
     * at {@link EvaUnit01Entity#SILO_BAY_YAW}. The hangar geometry gate reads
     * this rather than hard-coding which side the back is on: an earlier
     * revision asserted -Z and so certified a bridge built at the EVA's face.
     */
    public static double socketZOffset()
    {
        double yaw = Math.toRadians(EvaUnit01Entity.SILO_BAY_YAW);
        return -Math.cos(yaw)
                * EntryPlugKinematics.SOCKET_REAR_BLOCKS;
    }

    public static EntryPlugCarrierEntity ensureSuspended(
            ServerLevel level, int variant, EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null)
        {
            UUID savedId = savedPlugId(level, variant);
            if (savedId != null)
            {
                var receipt = unit.getPersistentData();
                if (!unit.isEntryPlugInserted() && receipt.hasUUID("R49EjectedPlug")
                        && savedId.equals(receipt.getUUID("R49EjectedPlug")))
                {
                    if (EXPECTED_FIELD_WAITING_R50.computeIfAbsent(level,
                            ignored -> new java.util.HashSet<>()).add(savedId))
                        ProjectSeele.LOGGER.info(
                                "NERV original emergency capsule awaiting loaded field entity or explicit disposal: EVA-0{} plug={}; no replacement created",
                                variant, savedId);
                    return null;
                }
                ProjectSeele.LOGGER.error(
                        "NERV entry-plug authority fault: EVA-0{} saved capsule {} cannot be resolved; replacement inhibited",
                        variant, savedId);
                return null;
            }
            if (unit.isEntryPlugInserted())
            {
                ProjectSeele.LOGGER.error(
                        "NERV entry-plug authority fault: EVA-0{} reports a seated capsule but its UUID cannot be resolved; replacement inhibited",
                        variant);
                return null;
            }
            plug = ModEntities.ENTRY_PLUG_CARRIER.get().create(level);
            if (plug == null)
            {
                return null;
            }
            plug.assignVariant(variant);
            plug.setPersistenceRequired();
            positionSuspended(plug, unit);
            if (!level.addFreshEntity(plug))
            {
                return null;
            }
            remember(level, variant, plug);
            ProjectSeele.LOGGER.info(
                    "NERV external entry plug suspended: eva={} plug={} pos={}",
                    variant, plug.getStringUUID(), plug.blockPosition().toShortString());
        }
        int stage = plug.getInsertionStage();
        if (stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED)
        {
            // PARKED may already have been saved by the previous runtime;
            // its remote emergency capsule still cannot own a cage crane.
            retireEmergencyCraneR50(level, variant);
        }
        if (stage != EntryPlugCarrierEntity.STAGE_INSERTING
                && stage != EntryPlugCarrierEntity.STAGE_EJECTING
                && stage != EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                && stage != EntryPlugCarrierEntity.STAGE_FIELD_LANDED
                && stage != EntryPlugCarrierEntity.STAGE_LOCKED
                && stage != EntryPlugCarrierEntity.STAGE_ABORT_RETURNING
                && stage != EntryPlugCarrierEntity.STAGE_ABORT_DOCKED)
        {
            RigidTransform wanted = cageDockTransform(unit);
            // A suspended capsule is cage hardware, not a child of the EVA's
            // live look direction. Re-solving its quaternion from the unit on
            // every logistics tick made it visibly oscillate while parked.
            if (!plug.hasCanonicalPose()
                    || plug.position().distanceToSqr(wanted.translation())
                            > 1.0E-4D
                    || plug.getCanonicalTransform()
                            .rotationErrorDegrees(wanted) > 0.1D)
            {
                plug.setCanonicalTransform(wanted);
            }
            if (plug.getInsertionProgress() != 0)
            {
                plug.setInsertionProgress(0);
            }
            int wantedStage = plug.isVehicle()
                    ? EntryPlugCarrierEntity.STAGE_OCCUPIED
                    : EntryPlugCarrierEntity.STAGE_SUSPENDED;
            if (plug.getInsertionStage() != wantedStage)
            {
                if (!plug.transitionInsertionStage(stage,
                        plug.getInsertionEpoch(), wantedStage))
                {
                    ProjectSeele.LOGGER.error(
                            "NERV entry-plug dock reconciliation refused illegal stage edge: eva={} from={} to={} epoch={}",
                            variant, stage, wantedStage,
                            plug.getInsertionEpoch());
                    return plug;
                }
            }
            /* The one authoritative crane remains visibly clamped to the
             * parked capsule. setPlugCrane owns stale-frame cleanup, so this
             * does not recreate the retired duplicate mechanism. */
            Vec3 craneEye = wanted.transformPoint(
                    EntryPlugKinematics.CRANE_ATTACHMENT_P);
            updateCables(level, variant, craneEye.y, craneEye.z, true);
        }
        return plug;
    }

    public static EntryPlugCarrierEntity canonical(ServerLevel level,
                                                    int variant)
    {
        Map<Integer, UUID> dimensionCache = CACHED_PLUGS.computeIfAbsent(
                level.dimension(), ignored -> new HashMap<>());
        UUID savedId = savedPlugId(level, variant);
        if (savedId != null)
        {
            Entity saved = level.getEntity(savedId);
            if (saved instanceof EntryPlugCarrierEntity plug
                    && plug.isAlive()
                    && nervOwnedCarrierR47(plug) && plug.getAssignedVariant() == variant)
            {
                dimensionCache.put(variant, savedId);
                return plug;
            }
            /*
             * A persisted identity is stronger than a nearby cosmetic shell.
             * Its chunk is forced by an active logistics phase; until it is
             * available we fail closed instead of silently swapping capsules.
             */
            return null;
        }
        UUID cachedId = dimensionCache.get(variant);
        if (cachedId != null)
        {
            Entity cached = level.getEntity(cachedId);
            if (cached instanceof EntryPlugCarrierEntity plug
                    && plug.isAlive() && nervOwnedCarrierR47(plug) && plug.getAssignedVariant() == variant)
            {
                return plug;
            }
            dimensionCache.remove(variant);
        }

        // Reload recovery: a seated plug may be hundreds of blocks from its
        // wet cage. Scan loaded entities only on a cache miss, then retain the
        // UUID so normal ticks return in O(1).
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof EntryPlugCarrierEntity plug
                    && plug.isAlive()
                    && nervOwnedCarrierR47(plug) && plug.getAssignedVariant() == variant
                    && plug.isLockedToEva())
            {
                remember(level, variant, plug);
                return plug;
            }
        }

        // A PARKED/INSERTING plug never leaves its assigned wet cage. A local
        // section query avoids scanning every entity in the 640-block cavern
        // three times per server tick.
        net.minecraft.core.BlockPos bed = hangarBed(level, variant);
        AABB search = new AABB(bed).inflate(32.0D, 64.0D, 48.0D);
        List<EntryPlugCarrierEntity> matches = new ArrayList<>(
                level.getEntitiesOfClass(EntryPlugCarrierEntity.class, search,
                        plug -> plug.isAlive()
                                && nervOwnedCarrierR47(plug) && plug.getAssignedVariant() == variant));
        if (matches.isEmpty())
        {
            return null;
        }
        /*
         * Never let UUID ordering choose an empty cosmetic shell over the
         * capsule that already contains the pilot or is midway through the
         * mechanical sequence.  That old tie-break was the source of several
         * "prepare did nothing" reports after a reload.
         */
        matches.sort(Comparator
                .comparingInt(EntryPlugDirector::canonicalPriority)
                .thenComparingDouble(plug ->
                        plug.position().distanceToSqr(
                                plugRestPosition(level, variant)))
                .thenComparing(Entity::getUUID));
        EntryPlugCarrierEntity keep = matches.get(0);
        for (int index = 1; index < matches.size(); index++)
        {
            EntryPlugCarrierEntity duplicate = matches.get(index);
            for (Entity passenger : List.copyOf(duplicate.getPassengers()))
            {
                passenger.stopRiding();
                keep.boardPassenger(passenger);
            }
            duplicate.discard();
        }
        remember(level, variant, keep);
        return keep;
    }

    private static boolean nervOwnedCarrierR47(EntryPlugCarrierEntity plug)
    {
        return plug.laboratorySlotR47()<0 && !plug.isIndependentUNPlug()
                && plug.getAssignedVariant()>=0 && plug.getAssignedVariant()<3;
    }

    private static int canonicalPriority(EntryPlugCarrierEntity plug)
    {
        if (plug.isLockedToEva()
                || plug.getInsertionStage()
                        == EntryPlugCarrierEntity.STAGE_LOCKED)
        {
            return 0;
        }
        if (plug.isVehicle() || !plug.getPassengers().isEmpty())
        {
            return 1;
        }
        int stage = plug.getInsertionStage();
        if (stage == EntryPlugCarrierEntity.STAGE_INSERTING
                || stage == EntryPlugCarrierEntity.STAGE_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED)
        {
            return 2;
        }
        return 3;
    }

    public static void resetRuntime()
    {
        CACHED_PLUGS.clear();
        CRANE_SIGNATURE.clear();
        S20_CRANE_POSES.clear();
        EXPECTED_FIELD_WAITING_R50.clear();
        EvaHangarBuilder.resetRuntime();
        FacilityV2EvaRuntime.resetRuntime();
    }

    /**
     * Returns an empty capsule left behind by a synthetic training session to
     * its wet-cage dock without replacing its persistent entity identity.
     *
     * <p>The caller must first prove the airframe is PARKED. A real passenger
     * is an absolute inhibit. This narrowly repairs the restart case where the
     * old dummy was removed but the chain EVA -> plug remained LOCKED, making
     * every later dummy request report the otherwise-empty EVA as occupied.</p>
     */
    public static boolean releaseEmptyTrainingPlugAtDock(
            ServerLevel level, int variant, EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null || !plug.getPassengers().isEmpty())
        {
            return false;
        }
        int stage = plug.getInsertionStage();
        if (stage == EntryPlugCarrierEntity.STAGE_LOCKED)
        {
            if (plug.getVehicle() != unit)
            {
                return false;
            }
            unit.clearEntryPlugLink(plug);
            plug.unlockFromEva();
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_LOCKED,
                    EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)
                    || !plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_ABORT_RETURNING,
                    EntryPlugCarrierEntity.STAGE_ABORT_DOCKED))
            {
                return false;
            }
            stage = EntryPlugCarrierEntity.STAGE_ABORT_DOCKED;
        }
        if (stage == EntryPlugCarrierEntity.STAGE_OCCUPIED)
        {
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_OCCUPIED,
                    EntryPlugCarrierEntity.STAGE_SUSPENDED))
            {
                return false;
            }
        }
        else if (stage == EntryPlugCarrierEntity.STAGE_ABORT_DOCKED)
        {
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_ABORT_DOCKED,
                    EntryPlugCarrierEntity.STAGE_SUSPENDED))
            {
                return false;
            }
        }
        else if (stage != EntryPlugCarrierEntity.STAGE_SUSPENDED)
        {
            return false;
        }
        positionSuspended(plug, unit);
        plug.setInsertionProgress(0);
        plug.setCabinSequenceProgress(0);
        plug.clearInsertionAbortRequest();
        plug.openCabin();
        remember(level, variant, plug);
        RigidTransform dock = cageDockTransform(unit);
        Vec3 craneEye = dock.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        updateCables(level, variant, craneEye.y, craneEye.z, true);
        ProjectSeele.LOGGER.info(
                "Released empty stale training capsule at wet cage: eva={} plug={}",
                variant, plug.getStringUUID());
        return true;
    }

    /**
     * Discards entry-plug carriers stranded away from their cage crane.
     *
     * <p>An earlier revision derived the suspended plug's rest point from the
     * airframe, so a deployed unit dragged a phantom capsule hundreds of blocks
     * up into the Tokyo-3 sky. Those persistent strays outlive the code fix;
     * this removes any empty carrier sitting far from its own wet cage, leaving
     * the single canonical plug {@link #canonical} maintains. A carrier that
     * still holds a pilot is left alone so nobody is discarded mid-flight.
     *
     * @return how many stray carriers were removed.
     */
    public static int sweepStrayPlugs(ServerLevel level)
    {
        int removed = 0;
        // Entry plugs are intentionally unique (one per EVA), so iterating the
        // already-loaded entity list is much cheaper and more reliable than a
        // huge AABB. It also reaches both the old phantom capsules above
        // Tokyo-3 and the same-position duplicates left in each wet cage.
        for (int variant = 0; variant < 3; variant++)
        {
            UUID savedId = savedPlugId(level, variant);
            List<EntryPlugCarrierEntity> candidates = new ArrayList<>();
            EntryPlugCarrierEntity saved = null;
            Vec3 rest = plugRestPosition(level, variant);
            for (Entity entity : level.getAllEntities())
            {
                if (!(entity instanceof EntryPlugCarrierEntity plug)
                        || !plug.isAlive()
                        || !nervOwnedCarrierR47(plug)
                        || plug.getAssignedVariant() != variant)
                {
                    continue;
                }
                candidates.add(plug);
                if (plug.getUUID().equals(savedId))
                {
                    saved = plug;
                }
            }
            if (candidates.isEmpty())
            {
                continue;
            }
            /*
             * A saved identity that is merely in an unloaded chunk remains
             * authoritative.  Never replace it with a cosmetic cage shell.
             */
            if (savedId != null && saved == null)
            {
                continue;
            }
            candidates.sort(Comparator
                    .comparingInt(EntryPlugDirector::canonicalPriority)
                    .thenComparingInt(plug -> plug.getUUID().equals(savedId)
                            ? 0 : 1)
                    .thenComparingDouble(plug ->
                            plug.position().distanceToSqr(rest))
                    .thenComparing(Entity::getUUID));
            EntryPlugCarrierEntity keep = candidates.get(0);
            for (int index = 1; index < candidates.size(); index++)
            {
                EntryPlugCarrierEntity duplicate = candidates.get(index);
                for (Entity passenger
                        : List.copyOf(duplicate.getPassengers()))
                {
                    passenger.stopRiding();
                    keep.boardPassenger(passenger);
                }
                duplicate.discard();
                removed++;
            }
            remember(level, variant, keep);
        }
        if (removed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV swept {} stray entry-plug carrier(s) in {}",
                    removed, level.dimension().location());
        }
        return removed;
    }

    /** Seals the boarded capsule and starts its local PREPARE sequence. */
    public static void beginCabinPreparation(ServerLevel level, int variant,
                                             EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = ensureSuspended(level, variant, unit);
        if (plug != null)
        {
            plug.beginCabinPreparation();
        }
    }

    /**
     * PREPARE starts while the split boarding bridge retracts. Run the first
     * thirty percent of the continuous sequence here so LCL is already rising
     * before the crane moves.
     */
    public static void tickCabinPreparation(ServerLevel level, int variant,
                                            EvaUnit01Entity unit, int ticks,
                                            int totalTicks)
    {
        // PREPARE owns the exact occupied capsule that requestPrepare
        // authenticated. Never manufacture a replacement midway through the
        // sealed-cabin sequence if that entity temporarily cannot be resolved.
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null || !plug.isVehicle())
        {
            return;
        }
        if (!plug.isHatchFullySealed())
        {
            plug.setCabinSequenceProgress(0);
            return;
        }
        int preparationTicks = Math.max(1,
                ticks - EntryPlugCarrierEntity.HATCH_SEAL_TICKS + 1);
        int preparationWindow = Math.max(1,
                totalTicks - EntryPlugCarrierEntity.HATCH_SEAL_TICKS + 1);
        int progress = Mth.clamp((int) Math.round(
                30.0D * preparationTicks / preparationWindow), 1, 30);
        plug.setCabinSequenceProgress(progress);
    }

    public static boolean hasBoardedPilot(ServerLevel level, int variant,
                                          EvaUnit01Entity unit)
    {
        if (isSupportedPilot(unit.getPilotEntity()))
        {
            return true;
        }
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug != null && isSupportedPilot(plug.getFirstPassenger()))
        {
            return true;
        }
        // Save-upgrade recovery: a player may already be riding the visible
        // capsule from before boarding began claiming fleet authority. Adopt
        // that exact occupied entity instead of asking the player to dismount
        // and repeat the interaction.
        for (Entity entity : level.getAllEntities())
        {
            if (entity instanceof EntryPlugCarrierEntity occupied
                    && occupied.isAlive()
                    && nervOwnedCarrierR47(occupied)
                    && occupied.getAssignedVariant() == variant
                    && isSupportedPilot(occupied.getFirstPassenger()))
            {
                claimBoardedPlug(level, occupied);
                return true;
            }
        }
        return false;
    }

    /**
     * Makes the capsule a real player just boarded the fleet authority.
     *
     * <p>Old saves can retain an empty duplicate whose UUID still sits in
     * fleet data.  Rendering and interaction then target the visible capsule,
     * while PREPARE resolves the stale empty one and reports no pilot.  The
     * successful server-side ride operation is the strongest possible proof
     * of identity, so claim it immediately and remove only an empty, idle
     * duplicate of the same EVA.</p>
     */
    public static void claimBoardedPlug(ServerLevel level,
                                        EntryPlugCarrierEntity boarded)
    {
        if(!nervOwnedCarrierR47(boarded))return;
        int variant = boarded.getAssignedVariant();
        EntryPlugCarrierEntity former = canonical(level, variant);
        if (former != null && former != boarded
                && !former.isVehicle()
                && former.getInsertionStage()
                        == EntryPlugCarrierEntity.STAGE_SUSPENDED)
        {
            former.discard();
        }
        remember(level, variant, boarded);
        if(boarded.getFirstPassenger() instanceof ServerPlayer actual)
        {
            var unit=EvaLogisticsDirector.canonicalUnit(level,variant);
            if(unit!=null)AutoSortieR32.acceptOriginalHumanBoardingR50(level,unit,actual);
        }
        ProjectSeele.LOGGER.info(
                "NERV entry-plug pilot authority claimed: eva={} plug={} pilot={}",
                variant, boarded.getStringUUID(),
                boarded.getFirstPassenger() == null ? "none"
                        : boarded.getFirstPassenger().getStringUUID());
    }

    public static boolean beginInsertion(ServerLevel level, int variant,
                                         EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null || !plug.isVehicle()
                || !plug.isHatchFullySealed()
                || plug.getCabinProgress() < 30
                || plug.getCabinStage()
                        < EntryPlugCarrierEntity.CABIN_LCL_FILLING)
        {
            return false;
        }
        RigidTransform dock = cageDockTransform(unit);
        RigidTransform actual = plug.getCanonicalTransform();
        if (actual.translation().distanceToSqr(dock.translation())
                > 1.0D / (1024.0D * 1024.0D)
                || actual.rotationErrorDegrees(dock) > 0.1D)
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug dock-pose interlock refused EVA-0{} insertion",
                    variant);
            return false;
        }
        if (!insertionRouteClear(level, unit, plug, dock))
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug full-route interlock refused EVA-0{} insertion",
                    variant);
            return false;
        }
        if (!plug.transitionInsertionStage(
                EntryPlugCarrierEntity.STAGE_OCCUPIED,
                EntryPlugCarrierEntity.STAGE_INSERTING))
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug insertion authority refused stale EVA-0{} stage={} epoch={}",
                    variant, plug.getInsertionStage(),
                    plug.getInsertionEpoch());
            return false;
        }
        plug.clearInsertionAbortRequest();
        // PREPARE holds the capsule at the exact cage-dock transform.  Keep
        // that identical pose for insertion tick zero so the renderer never
        // receives a one-frame dock->route snap before motion begins.
        plug.setCanonicalTransform(dock);
        Vec3 craneEye = dock.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        // Publish the identical trolley/yoke frame on the stage edge.  The
        // capsule was already stationary here, but retaining the previous
        // parked hardware frame made the top mechanism visibly kick once.
        updateCables(level, variant, craneEye.y, craneEye.z, true);
        plug.setInsertionProgress(0);
        plug.setCabinSequenceProgress(Math.max(30,
                plug.getCabinProgress()));
        return true;
    }

    /** Returns true only after the same occupied capsule is locked in the EVA. */
    public static boolean tickInsertion(ServerLevel level, int variant,
                                        EvaUnit01Entity unit, int ticks)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null)
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug insertion authority fault: EVA-0{} capsule vanished at tick {}; replacement inhibited",
                    variant, ticks);
            return false;
        }
        if (plug.getInsertionStage()
                != EntryPlugCarrierEntity.STAGE_INSERTING
                || plug.isInsertionAbortRequested()
                || !isSupportedPilot(plug.getFirstPassenger()))
        {
            return false;
        }
        // Drive translation and orientation from one eased clock. Rotating the
        // capsule in place for twelve ticks at the ceiling looked like a
        // mechanical twitch even though its centre was stationary.
        com.projectseele.entity.EvaDorsalMechanism.prepare(unit,ticks);
        double linear = insertionProgress(ticks);
        RigidTransform pose = EntryPlugKinematics.insertionTransform(
                unit, cageDockTransform(unit), linear);
        RigidTransform previous = plug.getCanonicalTransform();
        if (!insertionSweepClear(level, unit, plug, previous, pose))
        {
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_INSERTING,
                    EntryPlugCarrierEntity.STAGE_ABORT_RETURNING))
            {
                return false;
            }
            plug.sealCabin();
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug swept-clearance interlock: EVA-0{} halted at {}% and will return to dock",
                    variant, plug.getInsertionProgress());
            return false;
        }
        plug.setCanonicalTransform(pose);
        plug.setInsertionProgress((int) Math.round(linear * 100.0D));
        plug.setCabinSequenceProgress(30 + (int) Math.round(linear
                * (EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT - 30)));
        Vec3 craneEye = pose.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        updateCables(level, variant, craneEye.y,
                craneEye.z, true);
        if (ticks < INSERTION_TICKS)
        {
            return false;
        }

        Entity passenger = plug.getFirstPassenger();
        if (!isSupportedPilot(passenger))
        {
            ProjectSeele.LOGGER.warn(
                    "NERV entry plug insertion aborted without pilot: eva={} plug={}",
                    variant, plug.getStringUUID());
            return false;
        }
        int cabinProgress = plug.getCabinProgress();
        if (!plug.lockToEva(unit))
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry plug could not establish nested ride chain: eva={} plug={}",
                    variant, plug.getStringUUID());
            return false;
        }
        if (!unit.bindEntryPlug(plug, cabinProgress))
        {
            plug.unlockFromEva();
            plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_LOCKED,
                    EntryPlugCarrierEntity.STAGE_INSERTING);
            ProjectSeele.LOGGER.error(
                    "NERV EVA rejected persistent entry-plug link: eva={} plug={}",
                    variant, plug.getStringUUID());
            return false;
        }
        ProjectSeele.LOGGER.info(
                "NERV entry plug seated: eva={} plug={} passenger={}",
                variant, plug.getStringUUID(), passenger.getStringUUID());
        remember(level, variant, plug);
        stowCrane(level, variant);
        return true;
    }

    private static double insertionProgress(int ticks)
    {
        double clamped = Mth.clamp((ticks - INSERTION_SETTLE_TICKS)
                        / (double) (INSERTION_TICKS
                                - INSERTION_SETTLE_TICKS),
                0.0D, 1.0D);
        return smootherstep(clamped);
    }

    /**
     * The capsule is no-physics for deterministic crane motion, therefore the
     * director must explicitly perform the collision interlock before moving
     * it. The host EVA and seated pilot are the only authored overlaps.
     */
    private static boolean insertionSweepClear(ServerLevel level,
                                                EvaUnit01Entity unit,
                                                EntryPlugCarrierEntity plug,
                                                RigidTransform previous,
                                                RigidTransform next)
    {
        Vec3 craneEye = previous.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        return insertionSweepClear(level, unit, plug, previous, next,
                craneEye);
    }

    private static boolean insertionSweepClear(ServerLevel level,
                                                EvaUnit01Entity unit,
                                                EntryPlugCarrierEntity plug,
                                                RigidTransform previous,
                                                RigidTransform next,
                                                Vec3 craneEye)
    {
        /*
         * The suspended capsule legitimately overlaps its fixed dock collar.
         * Testing the union of the old and new bounds therefore rejected every
         * insertion forever: the union still contained the collar even while
         * the plug was moving away from it. Sample the actual motion instead
         * and reject only collision volume that increases. Existing dock
         * overlap may shrink, but the capsule may never enter a new solid.
         */
        AABB priorBounds = EntryPlugKinematics.worldBounds(previous,
                EntryPlugKinematics.BODY_OBB_CENTRE_P,
                EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(0.04D);
        for (int sample = 1; sample <= 4; sample++)
        {
            RigidTransform pose = previous.interpolate(next,
                    sample / 4.0D);
            AABB currentBounds = EntryPlugKinematics.worldBounds(pose,
                    EntryPlugKinematics.BODY_OBB_CENTRE_P,
                    EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(0.04D);
            if (!blockMotionClear(level, plug.getAssignedVariant(),
                    craneEye, priorBounds, currentBounds))
            {
                return false;
            }
            if (!level.getEntities(plug, currentBounds, entity ->
                    entity.isAlive() && entity != unit
                            && !plug.hasPassenger(entity)
                            && entity.isPickable()).isEmpty())
            {
                return false;
            }
            priorBounds = currentBounds;
        }
        return true;
    }

    private static boolean blockMotionClear(ServerLevel level, int variant,
                                            Vec3 craneEye,
                                            AABB previous,
                                            AABB current)
    {
        BlockPos min = BlockPos.containing(current.minX, current.minY,
                current.minZ);
        BlockPos max = BlockPos.containing(current.maxX, current.maxY,
                current.maxZ);
        boolean modern=FacilityV2EvaRuntime.ready(level,variant);
        BlockPos origin=RegionalFacilityLayout.evaOrigin(level);
        BlockPos cage=hangarBed(level,variant);
        for (BlockPos position : BlockPos.betweenClosed(min, max))
        {
            BlockState state=level.getBlockState(position);
            var shape=state.getCollisionShape(level,position);
            // Most of the swept box is air. Air cannot obstruct a capsule and
            // must not trigger repeated filesystem-backed layout resolution.
            if(shape.isEmpty())continue;
            // The active trolley/yoke/collar is the mechanism carrying this
            // capsule and is repositioned immediately after the accepted
            // motion step. It must not interlock against itself.
            boolean craneCell = modern
                    ? FacilityV2EvaRuntime.isPlugCraneCell(
                            level, variant, craneEye.y, craneEye.z, position)
                    : EvaHangarBuilder.isPlugCraneCell(
                            origin,
                            variant, craneEye.y, craneEye.z, position);
            if (craneCell
                    || EvaHangarBuilder.isActivePlugCraneCell(
                            variant, position))
            {
                continue;
            }
            /*
             * A restart loses the process-local crane frame cache while the
             * last visible yoke remains persisted in the save.  Its vertical
             * position need not match the newly calculated cable bottom, so
             * the exact-frame test above cannot recognise it.  Limit this
             * fallback to the narrow, elevated centre crane lane and to the
             * materials used exclusively by its moving yoke/ram.  This keeps
             * real cage walls and floors fail-closed while preventing the
             * capsule from interlocking against the machine carrying it.
             */
            if (isPersistedCraneHardware(cage, position, state))
            {
                continue;
            }
            for (AABB local : shape.toAabbs())
            {
                AABB solid = local.move(position);
                double before = intersectionVolume(previous, solid);
                double after = intersectionVolume(current, solid);
                if (after > before + 1.0E-4D)
                {
                    ProjectSeele.LOGGER.error(
                            "NERV entry-plug route obstruction at {} block={} overlap {} -> {}",
                            position.toShortString(), state.getBlock(),
                            before, after);
                    return false;
                }
            }
        }
        return true;
    }

    private static double intersectionVolume(AABB first, AABB second)
    {
        double x = Math.max(0.0D,
                Math.min(first.maxX, second.maxX)
                        - Math.max(first.minX, second.minX));
        double y = Math.max(0.0D,
                Math.min(first.maxY, second.maxY)
                        - Math.max(first.minY, second.minY));
        double z = Math.max(0.0D,
                Math.min(first.maxZ, second.maxZ)
                        - Math.max(first.minZ, second.minZ));
        return x * y * z;
    }

    /**
     * Checks the complete authored route before the crane leaves its brake.
     * Per-tick swept checks remain active as a second interlock for entities
     * entering the volume after PREPARE.
     */
    private static boolean insertionRouteClear(ServerLevel level,
                                                EvaUnit01Entity unit,
                                                EntryPlugCarrierEntity plug,
                                                RigidTransform dock)
    {
        // This is a brake-on preflight: the physical crane is still at the
        // dock while every future capsule pose is simulated. Keep ignoring
        // that one real mechanism instead of following a hypothetical crane
        // along the route before PREPARE has authorised any motion.
        Vec3 dockCraneEye = dock.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        RigidTransform previous = dock;
        for (int sample = 1; sample <= 24; sample++)
        {
            int simulatedTick = Mth.ceil(INSERTION_TICKS
                    * sample / 24.0D);
            RigidTransform next = EntryPlugKinematics.insertionTransform(
                    unit, dock, insertionProgress(simulatedTick));
            if (!insertionSweepClear(level, unit, plug, previous, next,
                    dockCraneEye))
            {
                return false;
            }
            previous = next;
        }
        return true;
    }

    /**
     * True only while the SavedData-authoritative occupied capsule owns the
     * complete EVA -> plug -> pilot launch chain at the reviewed socket pose.
     *
     * <p>The mechanical lock pause is not merely a timer. A reload, passenger
     * dismount or rejected nested ride during that pause must stop the cage
     * drain instead of sending an empty airframe to the launch silo.</p>
     */
    public static boolean hasLaunchLock(ServerLevel level, int variant,
                                        EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        UUID saved = savedPlugId(level, variant);
        if (plug == null || saved == null || !saved.equals(plug.getUUID())
                || plug.getAssignedVariant() != variant
                || plug.getInsertionStage()
                        != EntryPlugCarrierEntity.STAGE_LOCKED
                || plug.getInsertionProgress() != 100
                || plug.getVehicle() != unit
                || plug.getLinkedEva() != unit
                || !unit.getUUID().equals(plug.getHostEvaUuid())
                || unit.getLockedEntryPlug() != plug
                || !unit.isEntryPlugInserted()
                || !isSupportedPilot(plug.getFirstPassenger())
                || !plug.isHatchFullySealed())
        {
            return false;
        }
        RigidTransform expected = EntryPlugKinematics.lockedTransform(unit);
        RigidTransform actual = plug.getCanonicalTransform();
        return actual.translation().distanceToSqr(expected.translation())
                <= 0.04D
                && actual.rotationErrorDegrees(expected) <= 0.5D;
    }

    /**
     * Rewinds a failed PREPARE to the crane dock without changing capsule
     * identity. An occupied capsule remains sealed and keeps its pilot; an
     * empty capsule reopens for boarding.
     */
    public static boolean abortInsertionToDock(ServerLevel level, int variant,
                                               EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null)
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug rollback inhibited: EVA-0{} canonical capsule is unavailable",
                    variant);
            return false;
        }
        int stage = plug.getInsertionStage();
        if (stage == EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)
        {
            return true;
        }
        if (stage != EntryPlugCarrierEntity.STAGE_INSERTING
                && stage != EntryPlugCarrierEntity.STAGE_LOCKED)
        {
            return false;
        }
        if (!plug.transitionInsertionStage(stage,
                EntryPlugCarrierEntity.STAGE_ABORT_RETURNING))
        {
            return false;
        }
        if (plug.getLinkedEva() == unit
                || plug.getVehicle() instanceof EvaUnit01Entity)
        {
            plug.unlockFromEva();
        }
        plug.clearInsertionAbortRequest();
        plug.sealCabin();
        remember(level, variant, plug);
        return true;
    }

    private static boolean isPersistedCraneHardware(
            BlockPos bed, BlockPos position,
            BlockState state)
    {
        int dx = position.getX() - bed.getX();
        int dy = position.getY() - bed.getY();
        int dz = position.getZ() - bed.getZ();
        if (Math.abs(dx) > 4 || dy < 45 || dy > 74
                || dz < 0 || dz > 32)
        {
            return false;
        }
        return state.is(Blocks.CHAIN)
                || state.is(Blocks.PISTON)
                || state.is(Blocks.STICKY_PISTON)
                || state.is(Blocks.COPPER_BLOCK)
                || state.is(Blocks.EXPOSED_COPPER)
                || state.is(Blocks.POLISHED_BLACKSTONE)
                || state.is(Blocks.LIGHT_GRAY_CONCRETE)
                || state.is(Blocks.ORANGE_CONCRETE)
                || state.is(Blocks.PURPLE_CONCRETE)
                || state.is(Blocks.RED_CONCRETE);
    }

    /**
     * Converts a PREPARE that failed before motion into the same sealed docked
     * rollback state used after a swept-clearance abort.  Without this path an
     * OCCUPIED human capsule could never enter the return state and logistics
     * mislabeled a recoverable route interlock as a missing canonical plug.
     */
    public static boolean abortDockedPreparation(ServerLevel level, int variant,
                                                 EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null
                || plug.getInsertionStage()
                        != EntryPlugCarrierEntity.STAGE_OCCUPIED
                || !plug.isVehicle())
        {
            return false;
        }
        RigidTransform dock = cageDockTransform(unit);
        RigidTransform actual = plug.getCanonicalTransform();
        if (actual.translation().distanceToSqr(dock.translation())
                > 1.0D / (1024.0D * 1024.0D)
                || actual.rotationErrorDegrees(dock) > 0.1D
                || !plug.transitionInsertionStage(
                        EntryPlugCarrierEntity.STAGE_OCCUPIED,
                        EntryPlugCarrierEntity.STAGE_ABORT_DOCKED))
        {
            return false;
        }
        plug.setInsertionProgress(0);
        plug.setCabinSequenceProgress(0);
        plug.clearInsertionAbortRequest();
        plug.sealCabin();
        remember(level, variant, plug);
        return true;
    }

    /**
     * Brakes a failed insertion and returns the same capsule along the exact
     * authored curve.  No teleport, replacement capsule or open hatch is
     * permitted inside the crane/EVA sweep volume.
     */
    public static boolean tickAbortReturn(ServerLevel level, int variant,
                                          EvaUnit01Entity unit,
                                          int abortTicks)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null)
        {
            return false;
        }
        if (plug.getInsertionStage()
                != EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)
        {
            return false;
        }
        // Six ticks of physical braking prevent an insertion moving at +1%
        // per tick from reversing direction discontinuously on the first
        // abort frame.  The same persistent transform is held meanwhile.
        int progress = plug.getInsertionProgress();
        if (abortTicks > 6)
        {
            progress = Math.max(0, progress - 1);
        }
        double linear = progress / 100.0D;
        float hold=com.projectseele.entity.EvaDorsalMechanism.smooth(progress/28F);
        com.projectseele.entity.EvaDorsalMechanism.set(unit,Math.min(com.projectseele.entity.EvaDorsalMechanism.open(unit),hold),Math.min(com.projectseele.entity.EvaDorsalMechanism.bow(unit),hold));
        RigidTransform pose = EntryPlugKinematics.insertionTransform(
                unit, cageDockTransform(unit), linear);
        plug.setCanonicalTransform(pose);
        plug.setInsertionProgress(progress);
        Vec3 craneEye = pose.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        updateCables(level, variant, craneEye.y, craneEye.z, true);
        if (progress > 0)
        {
            return false;
        }

        positionSuspended(plug, unit);
        plug.setCabinSequenceProgress(0);
        // The capsule is physically home, but the access bridge still occupies
        // its retracted state.  Keep a distinct sealed docking state until the
        // logistics authority proves the bridge fully extended.
        if (!plug.transitionInsertionStage(
                EntryPlugCarrierEntity.STAGE_ABORT_RETURNING,
                EntryPlugCarrierEntity.STAGE_ABORT_DOCKED))
        {
            return false;
        }
        plug.sealCabin();
        remember(level, variant, plug);
        return true;
    }

    /** Releases a returned capsule only after the boarding bridge is safe. */
    public static boolean completeAbortDocking(ServerLevel level, int variant,
                                               EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug == null || plug.getInsertionStage()
                != EntryPlugCarrierEntity.STAGE_ABORT_DOCKED
                || plug.getInsertionProgress() != 0)
        {
            return false;
        }
        RigidTransform expected = cageDockTransform(unit);
        RigidTransform actual = plug.getCanonicalTransform();
        if (actual.translation().distanceToSqr(expected.translation())
                > 1.0D / (1024.0D * 1024.0D)
                || actual.rotationErrorDegrees(expected) > 0.1D)
        {
            return false;
        }
        plug.setCabinSequenceProgress(0);
        plug.clearInsertionAbortRequest();
        if (plug.isVehicle())
        {
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_ABORT_DOCKED,
                    EntryPlugCarrierEntity.STAGE_OCCUPIED))
            {
                return false;
            }
            plug.sealCabin();
        }
        else
        {
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_ABORT_DOCKED,
                    EntryPlugCarrierEntity.STAGE_SUSPENDED))
            {
                return false;
            }
            plug.openCabin();
        }
        remember(level, variant, plug);
        return true;
    }

    /** Same hoist path for a correctly docked capsule whose driver disconnected. */
    public static boolean extractEmptyCapsule(ServerLevel level, int variant, EvaUnit01Entity unit)
    {
        if (unit.isExperimentalUnit() || !isInsideAssignedCage(level,unit,variant) || unit.getPilotEntity()!=null) return false;
        EntryPlugCarrierEntity plug=unit.getLockedEntryPlug();
        if(plug==null||plug.isVehicle()||plug.getLinkedEva()!=unit||unit.getLockedEntryPlug()!=plug
                ||plug.getInsertionStage()!=EntryPlugCarrierEntity.STAGE_LOCKED) return false;
        RigidTransform seated=EntryPlugKinematics.lockedTransform(unit);
        if(plug.getCanonicalTransform().translation().distanceToSqr(seated.translation())>.25) return false;
        String blocker=EntryPlugEjectionR48.blocker(level,variant,unit,plug,null,true);
        if(!blocker.isEmpty())
        {ProjectSeele.LOGGER.warn("NERV empty capsule extraction held: eva={} plug={} reason={}",unit.getUUID(),plug.getUUID(),blocker);return false;}
        var before=EntryPlugEjectionR48.snapshot(plug);
        if(!plug.transitionInsertionStage(EntryPlugCarrierEntity.STAGE_LOCKED,plug.getInsertionEpoch(),EntryPlugCarrierEntity.STAGE_EJECTING)) return false;
        if(!EntryPlugEjectionR48.detach(unit,plug,before))return false;
        plug.setCanonicalTransform(seated);
        plug.setInsertionProgress(100);remember(level,variant,plug);
        level.playSound(null,plug.blockPosition(),SoundEvents.PISTON_EXTEND,SoundSource.BLOCKS,2.4F,.58F);
        ProjectSeele.LOGGER.info("NERV empty canonical capsule extraction started: eva={} plug={}",unit.getUUID(),plug.getUUID());
        return true;
    }

    public static boolean ejectPilotToPlug(ServerLevel level, int variant,
                                           EvaUnit01Entity unit,
                                           LivingEntity pilot)
    {
        if (level.isClientSide || unit == null || pilot == null || unit.level() != level || pilot.level() != level)
        {
            return false;
        }
        boolean inHangar = unit instanceof com.projectseele.entity.EvaPrototypeEntity un ? UNPlugDirector.atDock(un) : isInsideAssignedCage(level, unit, variant);
        Vec3 socket = unit.getEntryPlugSocketPosition();
        Vec3 outward = unit.getForward()
                .multiply(-1.0D, 0.0D, -1.0D).normalize();
        if (outward.lengthSqr() < 1.0E-4D)
        {
            outward = new Vec3(0.0D, 0.0D, 1.0D);
        }
        // Reuse this cage's plug. The logistics tick re-suspends a capsule as
        // soon as the previous one is consumed, so spawning a second here left
        // two plugs in the cage — and made canonical() pick the one the pilot
        // was not in, which is why a later prepare refused to start.
        EntryPlugCarrierEntity plug =
                pilot.getVehicle() instanceof EntryPlugCarrierEntity ridden
                        && ridden.laboratorySlotR47()<0
                        && ridden.getLinkedEva() == unit
                        ? ridden : unit.getLockedEntryPlug();
        if (plug != null && plug.laboratorySlotR47()>=0)
        {
            return false; // Generic EVA extraction never adopts an independent lab owner.
        }
        if (plug == null)
        {
            ProjectSeele.LOGGER.error(
                    "NERV entry-plug ejection inhibited: EVA-0{} has no resolvable canonical capsule; replacement inhibited",
                    variant);
            return false;
        }
        String blocker = EntryPlugEjectionR48.blocker(level, variant, unit, plug, pilot, inHangar);
        if (!blocker.isEmpty())
        {
            ProjectSeele.LOGGER.warn("NERV entry-plug ejection held without detaching: eva={} plug={} pilot={} stage={} epoch={} launch={} reason={}",
                    unit.getUUID(), plug.getUUID(), pilot.getUUID(), plug.getInsertionStage(), plug.getInsertionEpoch(), unit.getLaunchPhase(), blocker);
            return false;
        }
        RigidTransform seated = plug.getCanonicalTransform();
        int epoch = plug.getInsertionEpoch();
        Vec3 escape = null, landing = null;
        if (!inHangar)
        {
            Vec3 mouth = socket.add(outward.scale(EvaScale.ENTRY_PLUG_LENGTH * 0.54D))
                    .add(0.0D, EvaScale.ENTRY_PLUG_LENGTH * 0.12D, 0.0D);
            escape = mouth.add(outward.scale(12.0D)).add(0.0D, 9.0D, 0.0D);
            Vec3 probe = unit.position().add(outward.scale(EvaScale.ENTRY_PLUG_LENGTH + 12.0D));
            landing = findClearFieldEjectionLandingR50(level,unit,plug,seated,escape,probe);
            if (landing == null)
            {
                ProjectSeele.LOGGER.warn("NERV field ejection held without detaching: eva={} plug={} reason=no_loaded_safe_landing_or_sweep",unit.getUUID(),plug.getUUID());
                return false;
            }
        }
        if (plug.getInsertionStage() != EntryPlugCarrierEntity.STAGE_LOCKED || plug.getInsertionEpoch() != epoch) return false;
        var before = EntryPlugEjectionR48.snapshot(plug);
        if (inHangar)
        {
            // Play the insertion path backwards under the wet-cage hoist.
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_LOCKED,
                    epoch,
                    EntryPlugCarrierEntity.STAGE_EJECTING))
            {
                ProjectSeele.LOGGER.error(
                        "NERV wet-cage extraction rejected stale plug stage: eva={} plug={} stage={} epoch={}",
                        variant, plug.getStringUUID(),
                        plug.getInsertionStage(), plug.getInsertionEpoch());
                return false;
            }
            if (!EntryPlugEjectionR48.detach(unit,plug,before)) return false;
            if (unit instanceof com.projectseele.entity.EvaPrototypeEntity un && plug.isIndependentUNPlug()) plug.assignIndependentEva(un);
            plug.setCanonicalTransform(seated);
            plug.setInsertionProgress(100);
            if (!plug.isIndependentUNPlug()) remember(level, variant, plug);
            level.playSound(null, plug.blockPosition(),
                    SoundEvents.PISTON_EXTEND, SoundSource.BLOCKS,
                    2.4F, 0.58F);
            ProjectSeele.LOGGER.info(
                    "NERV wet-cage entry plug extraction started: eva={} plug={} pilot={}",
                    variant, plug.getStringUUID(), pilot.getStringUUID());
        }
        else
        {
            if (!plug.beginFieldEjection(
                    seated.translation(), escape, landing))
            {
                ProjectSeele.LOGGER.error(
                        "NERV field ejection rejected stale plug stage: eva={} plug={} stage={} epoch={}",
                        variant, plug.getStringUUID(),
                        plug.getInsertionStage(), plug.getInsertionEpoch());
                return false;
            }
            if (!EntryPlugEjectionR48.detach(unit,plug,before)) return false;
            if (unit instanceof com.projectseele.entity.EvaPrototypeEntity un && plug.isIndependentUNPlug()) plug.assignIndependentEva(un);
            plug.setCanonicalTransform(seated);
            level.playSound(null, plug.blockPosition(),
                    SoundEvents.GENERIC_EXPLODE, SoundSource.BLOCKS,
                    3.4F, 1.28F);
            level.sendParticles(ParticleTypes.EXPLOSION,
                    socket.x, socket.y, socket.z, 8,
                    1.4D, 1.4D, 1.4D, 0.08D);
            ProjectSeele.LOGGER.info(
                    "NERV field entry plug emergency ejection started: eva={} plug={} pilot={} landing={}",
                    variant, plug.getStringUUID(), pilot.getStringUUID(),
                    BlockPos.containing(landing).toShortString());
        }
        return true;
    }

    /**
     * Withdraws a seated capsule to its cage: the insertion path played back.
     * The pilot rides it out, so they leave inside the plug and then climb down
     * from it at the boarding deck instead of being dropped at the EVA's feet.
     */
    public static void tickEjection(EntryPlugCarrierEntity plug, int ticks)
    {
        if(plug.laboratorySlotR47()>=0)return;
        if(plug.isIndependentUNPlug()){UNPlugDirector.extract(plug,ticks);return;}
        if (!(plug.level() instanceof ServerLevel level))
        {
            return;
        }
        int variant = plug.getAssignedVariant();
        EvaUnit01Entity unit = EvaLogisticsDirector.canonicalUnit(level, variant);
        Vec3 rest = plugRestPosition(level, variant);
        double linear = Mth.clamp((ticks-36) / 105.0D, 0.0D, 1.0D);
        if (unit == null)
        {
            return;
        }
        if(ticks<=36)com.projectseele.entity.EvaDorsalMechanism.prepare(unit,ticks);
        else if(ticks>=137)com.projectseele.entity.EvaDorsalMechanism.seal(unit,ticks-137);
        RigidTransform pose = EntryPlugKinematics.insertionTransform(
                unit, EntryPlugKinematics.cageDockTransform(rest),
                1.0D - linear);
        plug.setCanonicalTransform(pose);
        plug.setInsertionProgress((int) Math.round((1.0D - linear) * 100.0D));
        plug.setCabinRecoveryProgress((int) Math.round(
                EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT
                        * (1.0D - linear)));
        Vec3 craneEye = pose.transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        double hookY=craneEye.y;
        if(ticks<=36)
        {
            double stowed=hangarBed(level,variant).getY()+EvaHangarBuilder.craneRailAboveBed()-2;
            hookY=stowed+(hookY-stowed)*smootherstep(ticks/36D);
        }
        updateCables(level, variant, hookY, craneEye.z, true);
        if (ticks >= EJECTION_TICKS)
        {
            int nextStage = plug.isVehicle()
                    ? EntryPlugCarrierEntity.STAGE_OCCUPIED
                    : EntryPlugCarrierEntity.STAGE_SUSPENDED;
            if (!plug.transitionInsertionStage(
                    EntryPlugCarrierEntity.STAGE_EJECTING,
                    plug.getInsertionEpoch(), nextStage))
            {
                ProjectSeele.LOGGER.error(
                        "NERV wet-cage extraction completion rejected stale plug stage: eva={} plug={} stage={} epoch={}",
                        variant, plug.getStringUUID(),
                        plug.getInsertionStage(), plug.getInsertionEpoch());
                return;
            }
            plug.setInsertionProgress(0);
            plug.setCabinRecoveryProgress(0);
            level.playSound(null, plug.blockPosition(),
                    SoundEvents.IRON_TRAPDOOR_OPEN, SoundSource.BLOCKS,
                    1.6F, 0.7F);
        }
    }

    /**
     * Throws an occupied emergency capsule clear of the airframe and down a
     * deterministic landing arc. The landed capsule remains in the world and
     * is never registered as the wet cage's canonical spare.
     */
    public static void tickFieldEjection(EntryPlugCarrierEntity plug, int ticks)
    {
        if(plug.laboratorySlotR47()>=0)return;
        if (!(plug.level() instanceof ServerLevel level))
        {
            return;
        }
        double linear = Mth.clamp(
                ticks / (double) FIELD_EJECTION_TICKS, 0.0D, 1.0D);
        Vec3 start = plug.getFieldEjectionStart();
        Vec3 escape = plug.getFieldEjectionEscape();
        Vec3 landing = plug.getFieldEjectionLanding();
        Vec3 position;
        if (linear <= 0.38D)
        {
            double phase = smoothstep(linear / 0.38D);
            position = start.lerp(escape, phase);
        }
        else
        {
            double phase = smoothstep((linear - 0.38D) / 0.62D);
            position = escape.lerp(landing, phase)
                    .add(0.0D, Math.sin(Math.PI * phase) * 8.0D, 0.0D);
        }
        RigidTransform current = plug.getCanonicalTransform();
        plug.setCanonicalTransform(new RigidTransform(position,
                current.qx(), current.qy(), current.qz(), current.qw()));
        plug.setInsertionProgress(
                (int) Math.round((1.0D - linear) * 100.0D));
        if (ticks % 3 == 0)
        {
            level.sendParticles(ParticleTypes.CLOUD,
                    position.x, position.y, position.z, 4,
                    0.55D, 0.35D, 0.55D, 0.02D);
            level.sendParticles(ParticleTypes.ELECTRIC_SPARK,
                    position.x, position.y, position.z, 3,
                    0.45D, 0.25D, 0.45D, 0.08D);
        }
        if (linear < 1.0D)
        {
            return;
        }

        RigidTransform landedRotation = plug.getCanonicalTransform();
        plug.setCanonicalTransform(new RigidTransform(landing,
                landedRotation.qx(), landedRotation.qy(),
                landedRotation.qz(), landedRotation.qw()));
        plug.setInsertionProgress(0);
        if (!plug.transitionInsertionStage(
                EntryPlugCarrierEntity.STAGE_FIELD_EJECTING,
                plug.getInsertionEpoch(),
                EntryPlugCarrierEntity.STAGE_FIELD_LANDED))
        {
            ProjectSeele.LOGGER.error(
                    "NERV field ejection landing rejected stale plug stage: eva={} plug={} stage={} epoch={}",
                    plug.getAssignedVariant(), plug.getStringUUID(),
                    plug.getInsertionStage(), plug.getInsertionEpoch());
            return;
        }
        Entity passenger = plug.getFirstPassenger();
        if (passenger instanceof Player pilot)
        {
            pilot.stopRiding();
            pilot.setHealth(Math.max(1.0F,
                    pilot.getHealth() - pilot.getMaxHealth() * 0.5F));
            pilot.displayClientMessage(Component.translatable(
                    "message.projectseele.field_ejection_landed"), true);
        }
        level.playSound(null, plug.blockPosition(),
                SoundEvents.GENERIC_EXPLODE, SoundSource.BLOCKS,
                2.8F, 0.72F);
        level.sendParticles(ParticleTypes.CLOUD,
                landing.x, landing.y, landing.z, 28,
                2.6D, 0.6D, 2.6D, 0.12D);
        ProjectSeele.LOGGER.info(
                "NERV field entry plug landed: eva={} plug={} pilot={} remainingHealth={}",
                plug.getAssignedVariant(), plug.getStringUUID(),
                passenger == null ? "none" : passenger.getStringUUID(),
                passenger instanceof Player player
                        ? String.format("%.1f", player.getHealth()) : "n/a");
    }

    public static void reset(ServerLevel level, int variant,
                             EvaUnit01Entity unit)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if(plug==null||plug.laboratorySlotR47()>=0||plug.getFirstPassenger()!=null)
            throw new IllegalStateException("Original empty capsule is required for maintenance");
        plug.unlockFromEva();plug.clearInsertionAbortRequest();plug.setInsertionProgress(0);
        plug.transitionInsertionStage(plug.getInsertionStage(),plug.getInsertionEpoch(),EntryPlugCarrierEntity.STAGE_SUSPENDED);
        positionSuspended(plug,unit);plug.openCabin();remember(level,variant,plug);
    }

    public static void remove(ServerLevel level, int variant)
    {
        EntryPlugCarrierEntity plug = canonical(level, variant);
        if (plug != null)
        {
            plug.discard();
        }
        forget(level, variant);
        clearSavedPlug(level, variant);
    }

    public static void keepPassengerState(EntryPlugCarrierEntity plug)
    {
        if(plug.laboratorySlotR47()>=0)return;
        Entity passenger = plug.getFirstPassenger();
        if (passenger != null
                && plug.getCabinStage() == EntryPlugCarrierEntity.CABIN_OPEN)
        {
            plug.sealCabin();
        }
        if (passenger instanceof TrainingPilotEntity pilot)
        {
            pilot.setInvisible(plug.isLockedToEva());
            pilot.setTrainingStage(TrainingPilotEntity.STAGE_IN_PLUG);
        }
        else if (passenger instanceof Player player)
        {
            // A docked capsule has a real passenger seat. Hide its occupant only
            // after insertion switches the rider to the internal EVA camera.
            player.setInvisible(plug.isLockedToEva());
        }
        boolean emptyUNLoading=plug.isIndependentUNPlug()
                &&plug.getLinkedEva() instanceof com.projectseele.entity.EvaPrototypeEntity un
                &&UNAirLiftR29.emptyLoading(un)
                &&un.getPersistentData().getUUID("UNPlug").equals(plug.getUUID());
        if (passenger == null && !emptyUNLoading && (plug.getInsertionStage()
                == EntryPlugCarrierEntity.STAGE_OCCUPIED
                || plug.getInsertionStage()
                == EntryPlugCarrierEntity.STAGE_SUSPENDED))
        {
            if (plug.getInsertionStage()
                    == EntryPlugCarrierEntity.STAGE_OCCUPIED)
            {
                plug.transitionInsertionStage(
                        EntryPlugCarrierEntity.STAGE_OCCUPIED,
                        plug.getInsertionEpoch(),
                        EntryPlugCarrierEntity.STAGE_SUSPENDED);
            }
            plug.openCabin();
        }
    }

    private static void positionSuspended(EntryPlugCarrierEntity plug,
                                          EvaUnit01Entity unit)
    {
        plug.setCanonicalTransform(cageDockTransform(unit));
    }

    private static RigidTransform cageDockTransform(EvaUnit01Entity unit)
    {
        return EntryPlugKinematics.cageDockTransform(suspendedPosition(unit));
    }
    /** The uninserted original is owned by its real cage dock, before a host ride link exists. */
    public static boolean originalCageDockR50(ServerLevel level,int variant,EvaUnit01Entity unit,EntryPlugCarrierEntity plug)
    {
        var fleet=EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        if(fleet==null||!fleet.canonicalId().equals(unit.getUUID())||fleet.entryPlugId()==null
                ||!fleet.entryPlugId().equals(plug.getUUID())||canonical(level,variant)!=plug||!nervOwnedCarrierR47(plug)
                ||plug.getAssignedVariant()!=variant||plug.getVehicle()!=null||!plug.hasCanonicalPose()
                ||plug.getLinkedEva()!=null&&plug.getLinkedEva()!=unit)return false;
        var actual=plug.getCanonicalTransform();var dock=cageDockTransform(unit);
        return actual.translation().distanceToSqr(dock.translation())<=1.0D/(1024.0D*1024.0D)
                &&actual.rotationErrorDegrees(dock)<=.1D;
    }

    /**
     * Resting point of the suspended plug — always its cage crane.
     *
     * <p>The plug is hangar hardware and never leaves the wet cage. An earlier
     * version derived the rest point from the airframe's own position, so once
     * a unit deployed to the surface the crane drew a stray capsule hundreds of
     * blocks up in the Tokyo-3 sky. It is anchored to the cage regardless of
     * where the airframe is.
     */
    private static Vec3 suspendedPosition(EvaUnit01Entity unit)
    {
        if (unit.level() instanceof ServerLevel level
                && FacilityV2EvaRuntime.ready(level,
                        unit.getUnitVariant()))
        {
            return FacilityV2EvaRuntime.plugRestPosition(
                    level, unit.getUnitVariant());
        }
        return EvaHangarBuilder.plugRestPosition(
                unit.level() instanceof ServerLevel serverLevel ? RegionalFacilityLayout.evaOrigin(serverLevel) : IntegratedNervMapBuilder.GEOFRONT_ORIGIN,
                unit.getUnitVariant());
    }

    /**
     * Finds solid ground near the EVA instead of using the dimension heightmap.
     * In GeoFront the heightmap points at the cavern roof, not the floor.
     */
    private static Vec3 findClearFieldEjectionLandingR50(ServerLevel level,EvaUnit01Entity unit,
                                                        EntryPlugCarrierEntity plug,RigidTransform seated,Vec3 escape,Vec3 probe)
    {
        List<FieldLandingR50> candidates=new ArrayList<>();
        Vec3 original=findFieldLanding(level,probe,unit.getY(),seated);
        if(original!=null)candidates.add(new FieldLandingR50(original,0,0));
        // A rear-facing probe may fall outside a commissioned underground pad
        // and hit its surrounding wall. Search only this finite local ring;
        // each endpoint retains the same full-volume and native arc admission.
        for(int radius:new int[]{4,8,12})
            for(int[] offset:new int[][]{{radius,0},{-radius,0},{0,radius},{0,-radius},
                    {radius,radius},{radius,-radius},{-radius,radius},{-radius,-radius}})
            {
                Vec3 candidate=findFieldLanding(level,probe.add(offset[0],0,offset[1]),unit.getY(),seated);
                if(candidate!=null)candidates.add(new FieldLandingR50(candidate,offset[0],offset[1]));
            }
        candidates.sort(Comparator.comparingDouble((FieldLandingR50 c)->Math.abs(c.position().y-unit.getY()))
                .thenComparingDouble(c->c.position().subtract(probe).horizontalDistanceSqr()));
        for(var candidate:candidates)
        {
            if(!fieldEjectionRouteClear(level,unit,plug,seated,escape,candidate.position()))continue;
            ProjectSeele.LOGGER.info("NERV field ejection local landing admitted: eva={} plug={} offset=[{},{}] landing={}",
                    unit.getUUID(),plug.getUUID(),candidate.dx(),candidate.dz(),candidate.position());return candidate.position();
        }
        return null;
    }
    private record FieldLandingR50(Vec3 position,int dx,int dz) {}
    private static Vec3 findFieldLanding(ServerLevel level, Vec3 probe,
                                         double unitY, RigidTransform seated)
    {
        int x = Mth.floor(probe.x);
        int z = Mth.floor(probe.z);
        int top = Math.min(level.getMaxBuildHeight() - 3,
                Mth.floor(unitY) + 18);
        int bottom = Math.max(level.getMinBuildHeight() + 1,
                Mth.floor(unitY) - 128);
        BlockPos.MutableBlockPos floor = new BlockPos.MutableBlockPos();
        for (int y = top; y >= bottom; y--)
        {
            floor.set(x, y, z);
            if (!level.hasChunkAt(floor)) return null;
            if (!level.getBlockState(floor)
                    .isFaceSturdy(level, floor, Direction.UP))
            {
                continue;
            }
            BlockPos above = floor.above();
            BlockPos head = above.above();
            if (!level.getFluidState(above).isEmpty()
                    || !level.getFluidState(head).isEmpty()
                    || !level.getBlockState(above)
                            .getCollisionShape(level, above).isEmpty()
                    || !level.getBlockState(head)
                            .getCollisionShape(level, head).isEmpty())
            {
                continue;
            }
            Vec3 position = new Vec3(x + 0.5D, y + 2.4D, z + 0.5D);
            RigidTransform pose = new RigidTransform(position, seated.qx(), seated.qy(), seated.qz(), seated.qw());
            AABB bounds = EntryPlugKinematics.worldBounds(pose,
                    EntryPlugKinematics.BODY_OBB_CENTRE_P, EntryPlugKinematics.BODY_OBB_HALF_EXTENTS);
            position = position.add(0, y + 1.04D - bounds.minY, 0);
            pose = new RigidTransform(position, seated.qx(), seated.qy(), seated.qz(), seated.qw());
            bounds = EntryPlugKinematics.worldBounds(pose,
                    EntryPlugKinematics.BODY_OBB_CENTRE_P, EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(.04);
            if (!EntryPlugEjectionR48.loaded(level, bounds.inflate(.1))) continue;
            boolean clear = true;
            for (var shape : level.getBlockCollisions(null, bounds)) if (!shape.isEmpty()) { clear = false; break; }
            if (!clear) continue;
            for (BlockPos point : BlockPos.betweenClosed(BlockPos.containing(bounds.minX,bounds.minY,bounds.minZ),
                    BlockPos.containing(bounds.maxX,bounds.maxY,bounds.maxZ)))
                if (!level.getFluidState(point).isEmpty()) { clear = false; break; }
            if (clear) return position;
        }
        // A missing floor is not a permitted airborne "landed" endpoint.
        return null;
    }

    /** Validate the same complete capsule arc before publishing its ejection stage. */
    private static boolean fieldEjectionRouteClear(ServerLevel level, EvaUnit01Entity unit,
                                                  EntryPlugCarrierEntity plug, RigidTransform seated,
                                                  Vec3 escape, Vec3 landing)
    {
        AABB previous = EntryPlugKinematics.worldBounds(seated,
                EntryPlugKinematics.BODY_OBB_CENTRE_P, EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(.04);
        for (int sample = 1; sample <= FIELD_EJECTION_TICKS; sample++)
        {
            double linear = sample / (double) FIELD_EJECTION_TICKS;
            Vec3 position = linear <= .38 ? seated.translation().lerp(escape, smoothstep(linear / .38))
                    : escape.lerp(landing, smoothstep((linear - .38) / .62))
                        .add(0, Math.sin(Math.PI * smoothstep((linear - .38) / .62)) * 8, 0);
            RigidTransform pose = new RigidTransform(position, seated.qx(), seated.qy(), seated.qz(), seated.qw());
            AABB current = EntryPlugKinematics.worldBounds(pose,
                    EntryPlugKinematics.BODY_OBB_CENTRE_P, EntryPlugKinematics.BODY_OBB_HALF_EXTENTS).deflate(.04);
            if (!EntryPlugEjectionR48.loaded(level, previous.minmax(current).inflate(.1))) return false;
            for (var shape : level.getBlockCollisions(plug, current))
                for (AABB solid : shape.toAabbs())
                    if (intersectionVolume(current,solid) > intersectionVolume(previous,solid) + 1e-4)
                    {
                        ProjectSeele.LOGGER.warn("NERV field ejection preflight obstruction: eva={} plug={} sample={} capsuleBounds={} nativeSolid={}",
                                unit.getUUID(),plug.getUUID(),sample,current,solid);return false;
                    }
            var occupants = level.getEntities(plug,current,e -> e.isAlive() && e != unit && !plug.hasPassenger(e) && e.isPickable());
            if (!occupants.isEmpty())
            {
                ProjectSeele.LOGGER.warn("NERV field ejection preflight occupant: eva={} plug={} sample={} obstacle={}",
                        unit.getUUID(),plug.getUUID(),sample,occupants.get(0).getUUID());return false;
            }
            previous = current;
        }
        return true;
    }

    private static double smoothstep(double value)
    {
        double clamped = Mth.clamp(value, 0.0D, 1.0D);
        return clamped * clamped * (3.0D - 2.0D * clamped);
    }

    /** Zero velocity and acceleration at both ends of the crane route. */
    private static double smootherstep(double value)
    {
        double clamped = Mth.clamp(value, 0.0D, 1.0D);
        return clamped * clamped * clamped
                * (clamped * (clamped * 6.0D - 15.0D) + 10.0D);
    }

    /** Keeps the visible suspension in step with the capsule it carries. */
    private static void updateCables(ServerLevel level, int variant, double plugY)
    {
        updateCables(level, variant, plugY, Double.NaN, false);
    }

    /**
     * @param travelling true while the crane is driving the plug, which is when
     *                   the telescoping arm is extended behind it.
     */
    private static void updateCables(ServerLevel level, int variant,
                                     double plugY, double plugZ,
                                     boolean travelling)
    {
        BlockPos bed = hangarBed(level, variant);
        if (!level.hasChunkAt(bed))
        {
            return;
        }
        // Skip identical frames: the parked logistics tick asks for this every
        // tick for all three cages, and repainting the crane each time is what
        // put the server seconds behind.
        boolean facilityRuntime =
                FacilityV2EvaRuntime.supportsPlugCrane(level, variant);
        boolean s20Runtime = FacilityWorldPolicy.isS20Rebuild(
                level.getServer());
        // FacilityV2's block crane is driven only by the measured attachment
        // point.  The old travelling bit belongs to the legacy visual arm and
        // does not alter FacilityV2 geometry.  Including it in the signature
        // erased and repainted an identical top frame exactly when insertion
        // began, which appeared as a one-frame kick of the suspended plug.
        boolean visualArm = !facilityRuntime && !s20Runtime && travelling
                && SeeleConfig.PLUG_MECHANICAL_ARM.get();
        long signature = craneSignature(plugY, plugZ, visualArm);
        if (CRANE_SIGNATURE.get(variant) != null
                && CRANE_SIGNATURE.get(variant) == signature)
        {
            /*
             * S20 uses a transient visual entity rather than persistent
             * crane blocks.  An unchanged geometry signature may skip the
             * expensive legacy-block sweep, but it must still refresh that
             * entity before its control timeout expires.  Otherwise the
             * parked crane disappears after two seconds and only reappears
             * when PREPARE changes the signature.
             */
            if (s20Runtime)
            {
                CranePose[] poses = S20_CRANE_POSES.get(level.dimension());
                CranePose pose = poses == null ? null : poses[variant];
                if (pose != null)
                {
                    int trolleyY = bed.getY()
                            + EvaHangarBuilder.craneRailAboveBed();
                    NervCarrierVisuals.updatePlugCrane(level, variant,
                            HangarStructuralFrameR44.trolleyOrigin(bed, pose.z()).x,
                            trolleyY, pose.z(), pose.bottomY());
                }
            }
            return;
        }
        CRANE_SIGNATURE.put(variant, signature);
        if (facilityRuntime)
        {
            FacilityV2EvaRuntime.setPlugCrane(level, variant,
                     plugY, plugZ, travelling);
            return;
        }
        if (s20Runtime)
        {
            updateS20Crane(level, variant, bed, plugY, plugZ);
            return;
        }
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        EvaHangarBuilder.setPlugCrane(level, origin, variant, plugY, plugZ,
                visualArm);
    }

    private static long craneSignature(double plugY, double plugZ,
                                       boolean travelling)
    {
        // Preserve sub-block motion.  Quarter-block signatures held the
        // trolley still for several ticks near both ends of smootherstep.
        long y = Math.round(plugY * 1000.0D);
        long z = Double.isNaN(plugZ) ? Long.MIN_VALUE / 4L
                : Math.round(plugZ * 1000.0D);
        return (y * 1_000_003L + z) * 2L + (travelling ? 1L : 0L);
    }

    /** Retracts the crane once the capsule is no longer in the cage's hands. */
    private static void stowCrane(ServerLevel level, int variant)
    {
        BlockPos bed = hangarBed(level, variant);
        if (FacilityV2EvaRuntime.supportsPlugCrane(level, variant))
        {
            CRANE_SIGNATURE.remove(variant);
            FacilityV2EvaRuntime.stowPlugCrane(level, variant);
            return;
        }
        if (FacilityWorldPolicy.isS20Rebuild(level.getServer()))
        {
            stowS20Crane(level, variant, bed);
            return;
        }
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        if (level.hasChunkAt(bed))
        {
            CRANE_SIGNATURE.remove(variant);
            EvaHangarBuilder.stowPlugCrane(level, origin, variant);
        }
    }

    private static void updateS20Crane(ServerLevel level, int variant,
                                       BlockPos bed, double plugY,
                                       double plugZ)
    {
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        int removed = EvaHangarBuilder.retirePersistedPlugCrane(
                level, origin, variant);
        if (removed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV retired {} persisted block-crane cells for EVA-0{}",
                    removed, variant);
        }
        int trolleyY = bed.getY() + EvaHangarBuilder.craneRailAboveBed();
        double z = Double.isNaN(plugZ)
                ? plugRestPosition(level, variant).z : plugZ;
        z = Mth.clamp(z, bed.getZ() - 25.0D, bed.getZ() + 25.0D);
        double bottomY = Mth.clamp(plugY,
                bed.getY() + 1.0D, trolleyY - 2.0D);
        CranePose pose = new CranePose(z, bottomY);
        S20_CRANE_POSES.computeIfAbsent(level.dimension(),
                ignored -> new CranePose[3])[variant] = pose;
        NervCarrierVisuals.updatePlugCrane(level, variant,
                HangarStructuralFrameR44.trolleyOrigin(bed, pose.z()).x,
                trolleyY, pose.z(), pose.bottomY());
    }

    private static void stowS20Crane(ServerLevel level, int variant,
                                     BlockPos bed)
    {
        BlockPos origin = RegionalFacilityLayout.evaOrigin(level);
        int removed = EvaHangarBuilder.retirePersistedPlugCrane(
                level, origin, variant);
        if (removed > 0)
        {
            ProjectSeele.LOGGER.info(
                    "NERV retired {} persisted block-crane cells for EVA-0{}",
                    removed, variant);
        }
        int trolleyY = bed.getY() + EvaHangarBuilder.craneRailAboveBed();
        CranePose[] poses = S20_CRANE_POSES.computeIfAbsent(
                level.dimension(), ignored -> new CranePose[3]);
        CranePose previous = poses[variant];
        if (previous == null)
        {
            Vec3 rest = plugRestPosition(level, variant);
            previous = new CranePose(rest.z, rest.y);
        }
        CranePose stowed = new CranePose(previous.z(),
                Math.min(trolleyY - 2, previous.bottomY() + .5));
        poses[variant] = stowed;
        CRANE_SIGNATURE.remove(variant);
        NervCarrierVisuals.updatePlugCrane(level, variant,
                HangarStructuralFrameR44.trolleyOrigin(bed, stowed.z()).x,
                trolleyY, stowed.z(), stowed.bottomY());
    }

    /**
     * Reasserts the compact ceiling frame after the capsule is seated.
     *
     * <p>This public, idempotent boundary is used by the logistics state
     * machine as a save-upgrade repair: older worlds may already be in
     * PLUG_LOCKING with a full-height crane persisted in the transfer lane,
     * so the one-shot call at the end of insertion was never observed by the
     * new runtime.</p>
     */
    public static void ensureCraneStowed(ServerLevel level, int variant)
    {
        stowCrane(level, variant);
    }

    /** Keeps the recovered occupied capsule clamped while the cage refills. */
    public static void maintainCraneAtCurrentPlug(
            ServerLevel level, int variant, EntryPlugCarrierEntity plug)
    {
        if (plug == null || !plug.isAlive() || plug.level() != level
                || variant < 0 || variant > 2 || !nervOwnedCarrierR47(plug)
                || plug.getAssignedVariant() != variant || !plug.hasCanonicalPose())
        {
            return;
        }
        int stage = plug.getInsertionStage();
        // Emergency capsules are no longer crane payloads, even though their
        // original UUID remains the fleet's authority until explicit disposal.
        if (stage == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED)
        {
            var original = EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
            if (original != null && plug.getUUID().equals(original.entryPlugId()))
                retireEmergencyCraneR50(level, variant);
            return;
        }
        var fleet = EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
        if (fleet == null || !plug.getUUID().equals(fleet.entryPlugId())
                || !(level.getEntity(fleet.canonicalId()) instanceof EvaUnit01Entity unit)
                || !unit.isAlive() || unit.isExperimentalUnit() || unit.getUnitVariant() != variant
                || !isInsideAssignedCage(level, unit, variant))return;
        if (stage == EntryPlugCarrierEntity.STAGE_SUSPENDED
                || stage == EntryPlugCarrierEntity.STAGE_OCCUPIED
                || stage == EntryPlugCarrierEntity.STAGE_ABORT_DOCKED)
        {
            if (!originalCageDockR50(level, variant, unit, plug))return;
        }
        else
        {
            if (stage != EntryPlugCarrierEntity.STAGE_INSERTING
                    && stage != EntryPlugCarrierEntity.STAGE_EJECTING
                    && stage != EntryPlugCarrierEntity.STAGE_ABORT_RETURNING)return;
            if (plug.getVehicle() != null && plug.getVehicle() != unit
                    || plug.getLinkedEva() != null && plug.getLinkedEva() != unit)return;
            var dock = cageDockTransform(unit);
            var socket = EntryPlugKinematics.socketTransform(unit);
            var approach = socket.transformPoint(new Vec3(0, 0, 3));
            var locked = EntryPlugKinematics.lockedTransform(unit);
            // The authored insertion curve stays inside these actual endpoint
            // and mouth-approach bounds; a stage label cannot extend the crane
            // to a capsule outside its own cage's mechanical travel domain.
            var domain = new AABB(dock.translation(), approach)
                    .minmax(new AABB(socket.translation(), locked.translation())).inflate(.001);
            if (!domain.contains(plug.getCanonicalTransform().translation()))return;
        }
        Vec3 craneEye = plug.getCanonicalTransform().transformPoint(
                EntryPlugKinematics.CRANE_ATTACHMENT_P);
        updateCables(level, variant, craneEye.y, craneEye.z, true);
    }

    /** Stop only existing display machinery; the ordinary stow path may create a new crane. */
    private static void retireEmergencyCraneR50(ServerLevel level, int variant)
    {
        CRANE_SIGNATURE.remove(variant);
        CranePose[] poses = S20_CRANE_POSES.get(level.dimension());
        if (poses != null)poses[variant] = null;
        List<com.projectseele.entity.NervCarrierPlatformEntity> obsolete = new ArrayList<>();
        for (Entity entity : level.getAllEntities())
            if (entity instanceof com.projectseele.entity.NervCarrierPlatformEntity crane
                    && crane.isAlive() && crane.isPlugCrane() && crane.getUnitVariant() == variant
                    && !crane.isVehicle() && !crane.isPassenger())obsolete.add(crane);
        for (var crane : obsolete)crane.discard();
    }

    private static BlockPos hangarBed(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.supportsPlugCrane(level, variant))
        {
            return FacilityV2EvaRuntime.hangarBed(level, variant);
        }
        return EvaHangarBuilder.hangarBed(
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    public static Vec3 plugRestPosition(ServerLevel level, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return FacilityV2EvaRuntime.plugRestPosition(level, variant);
        }
        return EvaHangarBuilder.plugRestPosition(
                RegionalFacilityLayout.evaOrigin(level), variant);
    }

    private static boolean isInsideAssignedCage(
            ServerLevel level, EvaUnit01Entity unit, int variant)
    {
        if (FacilityV2EvaRuntime.ready(level, variant))
        {
            return unit.getUnitVariant() == variant
                    && FacilityV2EvaRuntime.isInsideAssignedCage(
                            level, unit.position(), variant);
        }
        return EvaHangarBuilder.isInsideAssignedCage(
                level, unit, variant);
    }

    private static boolean isSupportedPilot(Entity entity)
    {
        return entity instanceof Player || entity instanceof TrainingPilotEntity;
    }

    private static void remember(ServerLevel level, int variant,
                                 EntryPlugCarrierEntity plug)
    {
        if(!nervOwnedCarrierR47(plug)||plug.getAssignedVariant()!=variant)return;
        CACHED_PLUGS.computeIfAbsent(level.dimension(), ignored -> new HashMap<>())
                .put(variant, plug.getUUID());
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        EvaFleetSavedData.FleetEntry entry = data.entry(variant).orElse(null);
        if (entry != null && !plug.getUUID().equals(entry.entryPlugId()))
        {
            data.put(variant, entry.withEntryPlug(plug.getUUID()));
        }
    }

    private static void forget(ServerLevel level, int variant)
    {
        Map<Integer, UUID> dimension = CACHED_PLUGS.get(level.dimension());
        if (dimension != null)
        {
            dimension.remove(variant);
        }
    }

    private static UUID savedPlugId(ServerLevel level, int variant)
    {
        EvaFleetSavedData.FleetEntry entry =
                EvaFleetSavedData.get(level.getServer())
                        .entry(variant).orElse(null);
        return entry == null ? null : entry.entryPlugId();
    }

    private static void clearSavedPlug(ServerLevel level, int variant)
    {
        EvaFleetSavedData data = EvaFleetSavedData.get(level.getServer());
        EvaFleetSavedData.FleetEntry entry = data.entry(variant).orElse(null);
        if (entry != null && entry.entryPlugId() != null)
        {
            data.put(variant, entry.withEntryPlug(null));
        }
    }

    private record CranePose(double z, double bottomY) {}
}

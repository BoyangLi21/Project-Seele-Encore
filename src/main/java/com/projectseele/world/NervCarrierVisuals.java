package com.projectseele.world;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.phys.AABB;

/** Runtime ownership for non-saving mag-lev carrier display entities. */
public final class NervCarrierVisuals
{
    private static final Map<UUID, UUID> PLATFORM_BY_EVA = new HashMap<>();
    private static final Map<UUID, UUID> GANTRY_BY_EVA = new HashMap<>();
    private static final Map<ServerLevel, UUID[]> PLUG_CRANE_BY_LEVEL =
            new WeakHashMap<>();

    private NervCarrierVisuals() {}

    public static void update(ServerLevel level, EvaUnit01Entity unit,
                              double x, double y, double z)
    {
        /*
         * Moving Elevators does not represent a travelling cage as a normal
         * entity.  It renders the captured structure directly from the same
         * client-side motion state that drives its group.  Follow that proven
         * architecture: EvaUnit01Renderer draws the deck in the EVA's exact
         * render transform.  Retire any transient deck from an older runtime;
         * fixed restraint gantries use GANTRY_BY_EVA and are never touched.
         */
        discard(level, PLATFORM_BY_EVA.remove(unit.getUUID()));
    }

    public static void update(ServerLevel level, EvaUnit01Entity unit,
                              double x, double y, double z,
                              float restraintProgress)
    {
        updateRestraints(level, unit, x, y, z, restraintProgress);
    }

    /** Keeps the wet-cage machinery fixed in its authored hangar. */
    public static boolean updateRestraints(ServerLevel level,
                                        EvaUnit01Entity unit,
                                        double x, double y, double z,
                                        float restraintProgress)
    {
        // A deployed EVA can be ticking hundreds of metres from this bay.
        // In an inactive entity chunk, addFreshEntity followed by a UUID
        // lookup cannot establish ownership; recreating the non-saving
        // visual every tick churns entities and starves remote loads.
        if (!level.isPositionEntityTicking(net.minecraft.core.BlockPos.containing(x, y, z))) return !TvCageCollisionR44.enabled();
        NervCarrierPlatformEntity gantry = resolve(level,
                GANTRY_BY_EVA, unit.getUUID());
        if (gantry == null)
        {
            gantry = adoptOrClearLegacyGantry(level, unit, x, y, z);
        }
        if (gantry == null)
        {
            gantry = createRestraintGantry(level, unit, x, y, z);
            if (gantry == null)
            {
                return !TvCageCollisionR44.enabled();
            }
            GANTRY_BY_EVA.put(unit.getUUID(), gantry.getUUID());
            ProjectSeele.LOGGER.info(
                    "NERV fixed restraint gantry engaged: eva={} gantry={}",
                    unit.getStringUUID(), gantry.getStringUUID());
        }
        gantry.configureRestraintGantry();
        gantry.assignVariant(unit.getUnitVariant());
        gantry.holdStatic(x, y + 0.04D, z);
        if (!TvCageCollisionR44.canMove(level, unit, gantry, restraintProgress))
        {
            return false;
        }
        gantry.setRestraintProgress(restraintProgress);
        gantry.setRepairProgressR33(com.projectseele.entity.EvaBayRepairR33.active(unit)?com.projectseele.entity.EvaBayRepairR33.progress(unit,0):-1);
        gantry.holdStatic(x, y + 0.04D, z);
        if (level.getGameTime() % 5L == 0L)
        {
            discardDuplicateGantries(level, gantry, x, y + 0.04D, z);
        }
        return true;
    }

    /** Publishes a fractional wet-cage liquid surface on the fixed gantry. */
    public static void updateLclSurface(ServerLevel level,
                                        EvaUnit01Entity unit,
                                        double x, double y, double z,
                                        float layers)
    {
        if (!level.isPositionEntityTicking(net.minecraft.core.BlockPos.containing(x, y, z))) return;
        NervCarrierPlatformEntity gantry = resolve(level,
                GANTRY_BY_EVA, unit.getUUID());
        if (gantry == null)
        {
            gantry = adoptOrClearLegacyGantry(level, unit, x, y, z);
        }
        if (gantry == null)
        {
            gantry = createRestraintGantry(level, unit, x, y, z);
            if (gantry == null)
            {
                return;
            }
            GANTRY_BY_EVA.put(unit.getUUID(), gantry.getUUID());
        }
        gantry.configureRestraintGantry();
        gantry.assignVariant(unit.getUnitVariant());
        gantry.setLclVisualLevel(layers);
        gantry.holdStatic(x, y + 0.04D, z);
    }

    /**
     * Publishes one non-saving crane mesh instead of repainting moving stone,
     * copper and chain blocks into the authoritative world every tick.
     */
    public static void updatePlugCrane(ServerLevel level, int variant,
                                       double x, double trolleyY, double z,
                                       double bottomY)
    {
        if (!level.isPositionEntityTicking(net.minecraft.core.BlockPos.containing(x, trolleyY, z))) return;
        int safeVariant = Math.max(EvaUnit01Entity.UNIT_00,
                Math.min(EvaUnit01Entity.UNIT_02, variant));
        UUID[] owners = PLUG_CRANE_BY_LEVEL.computeIfAbsent(level,
                ignored -> new UUID[3]);
        NervCarrierPlatformEntity crane = null;
        UUID craneId = owners[safeVariant];
        if (craneId != null)
        {
            Entity candidate = level.getEntity(craneId);
            if (candidate instanceof NervCarrierPlatformEntity visual
                    && visual.isAlive() && visual.isPlugCrane())
            {
                crane = visual;
            }
        }
        if (crane == null)
        {
            crane = ModEntities.NERV_CARRIER_PLATFORM.get().create(level);
            if (crane == null)
            {
                return;
            }
            crane.configurePlugCrane(safeVariant,
                    bottomY - trolleyY);
            crane.moveControlled(x, trolleyY, z);
            if (!level.addFreshEntity(crane))
            {
                return;
            }
            owners[safeVariant] = crane.getUUID();
            ProjectSeele.LOGGER.info(
                    "NERV transient entry-plug crane engaged: eva={} crane={}",
                    safeVariant, crane.getStringUUID());
        }
        crane.configurePlugCrane(safeVariant,
                bottomY - trolleyY);
        // Unlike holdStatic(), this preserves the previous client frame so
        // vanilla can interpolate the trolley's horizontal travel.
        crane.moveControlled(x, trolleyY, z);
        var plug=EntryPlugDirector.canonical(level,safeVariant);
        crane.linkCranePlug(plug);

        // Runtime reloads used to leave multiple opaque crane meshes at the
        // same anchor. Keep one deterministic owner per machine.
        AABB envelope = new AABB(x - 2.0D, trolleyY - 2.0D, z - 2.0D,
                x + 2.0D, trolleyY + 2.0D, z + 2.0D);
        for (NervCarrierPlatformEntity other : level.getEntitiesOfClass(
                NervCarrierPlatformEntity.class, envelope))
        {
            if (other != crane && other.isPlugCrane()
                    && other.getUnitVariant() == safeVariant)
            {
                other.discard();
            }
        }
    }

    /**
     * A runtime cache reset must not leave two client-rendered gantries at the
     * same wet-cage anchor.  Identical opaque faces z-fight as the camera
     * moves even though neither entity itself changes position.
     */
    private static void discardDuplicateGantries(
            ServerLevel level, NervCarrierPlatformEntity canonical,
            double x, double y, double z)
    {
        AABB anchor = new AABB(x - 1.5D, y - 1.5D, z - 1.5D,
                x + 1.5D, y + 1.5D, z + 1.5D);
        for (NervCarrierPlatformEntity candidate : level.getEntitiesOfClass(
                NervCarrierPlatformEntity.class, anchor))
        {
            if (candidate != canonical && candidate.isRestraintGantry())
            {
                if (candidate.position().distanceToSqr(canonical.position()) < .01)
                {
                    candidate.discard();
                }
            }
        }
    }

    /**
     * Reconciles copies saved by builds from before gantries became
     * non-persistent.  Only the exact wet-cage anchor is inspected; personnel
     * lifts and an in-flight carrier are never candidates.
     */
    private static NervCarrierPlatformEntity adoptOrClearLegacyGantry(
            ServerLevel level, EvaUnit01Entity unit,
            double x, double y, double z)
    {
        AABB anchor = new AABB(x - 1.5D, y - 1.5D, z - 1.5D,
                x + 1.5D, y + 2.0D, z + 1.5D);
        UUID activeCarrier = PLATFORM_BY_EVA.get(unit.getUUID());
        NervCarrierPlatformEntity adopted = null;
        for (NervCarrierPlatformEntity candidate : level.getEntitiesOfClass(
                NervCarrierPlatformEntity.class, anchor))
        {
            // The query tests the carrier's broad physical box, not its
            // anchor. Ownership/adoption is by this exact fixed bay centre.
            if (candidate.position().distanceToSqr(new net.minecraft.world.phys.Vec3(x, y + .04, z)) > .25)
            {
                continue;
            }
            // A parked transfer deck and its fixed gantry deliberately share
            // the same anchor.  Cache recovery may adopt/clean gantries, but
            // must never discard that separately-owned moving deck.
            if (candidate.getUUID().equals(activeCarrier))
            {
                continue;
            }
            if (candidate.isPersistentLift()
                    || candidate.isPersonnelLift())
            {
                continue;
            }
            if (candidate.isRestraintGantry()
                    && candidate.getUnitVariant() == unit.getUnitVariant()
                    && adopted == null)
            {
                adopted = candidate;
                continue;
            }
            // Old transient copies did not save their gantry discriminator.
            // At this exact fixed anchor they cannot be an active transfer
            // deck, so remove them rather than render two identical towers.
            candidate.discard();
        }
        if (adopted != null)
        {
            GANTRY_BY_EVA.put(unit.getUUID(), adopted.getUUID());
        }
        return adopted;
    }

    public static void remove(ServerLevel level, EvaUnit01Entity unit)
    {
        discard(level, PLATFORM_BY_EVA.remove(unit.getUUID()));
    }

    /** Used only when the owning airframe itself is deleted or reset. */
    public static void removeAll(ServerLevel level, EvaUnit01Entity unit)
    {
        discard(level, PLATFORM_BY_EVA.remove(unit.getUUID()));
        discard(level, GANTRY_BY_EVA.remove(unit.getUUID()));
    }

    public static void resetRuntime()
    {
        PLATFORM_BY_EVA.clear();
        GANTRY_BY_EVA.clear();
        PLUG_CRANE_BY_LEVEL.clear();
    }

    private static NervCarrierPlatformEntity createRestraintGantry(
            ServerLevel level, EvaUnit01Entity unit,
            double x, double y, double z)
    {
        NervCarrierPlatformEntity visual =
                ModEntities.NERV_CARRIER_PLATFORM.get().create(level);
        if (visual == null)
        {
            return null;
        }
        // Configure before spawning: clients must never observe one frame of
        // the default moving carrier deck at this fixed hangar anchor.
        visual.configureRestraintGantry();
        visual.assignVariant(unit.getUnitVariant());
        visual.holdStatic(x, y + 0.04D, z);
        return level.addFreshEntity(visual) ? visual : null;
    }

    private static void discard(ServerLevel level, UUID entityId)
    {
        if (entityId == null)
        {
            return;
        }
        Entity entity = level.getEntity(entityId);
        if (entity instanceof NervCarrierPlatformEntity platform)
        {
            platform.discard();
        }
    }

    private static NervCarrierPlatformEntity resolve(ServerLevel level,
                                                      Map<UUID, UUID> owners,
                                                      UUID evaId)
    {
        UUID platformId = owners.get(evaId);
        if (platformId == null)
        {
            return null;
        }
        Entity entity = level.getEntity(platformId);
        if (entity instanceof NervCarrierPlatformEntity platform
                && platform.isAlive())
        {
            return platform;
        }
        owners.remove(evaId);
        return null;
    }
}

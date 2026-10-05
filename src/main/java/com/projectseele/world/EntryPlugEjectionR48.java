package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervSiloDoorEntity;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.AABB;
import java.util.List;
import java.util.UUID;

/** Exact-target extraction admission; no replacement capsule, gravity lease or recovery teleport. */
public final class EntryPlugEjectionR48
{
    public record Snapshot(CompoundTag nbt, UUID plug, UUID host, int epoch, List<UUID> passengers) {}
    private EntryPlugEjectionR48() {}

    public static String blocker(ServerLevel level, int variant, EvaUnit01Entity unit,
                                 EntryPlugCarrierEntity plug, LivingEntity pilot, boolean inHangar)
    {
        if (unit.level() != level || plug.level() != level || unit.isRemoved() || !plug.isAlive()
                || level.getEntity(unit.getUUID()) != unit || level.getEntity(plug.getUUID()) != plug)
            return "original_owner_unavailable";
        if (plug.laboratorySlotR47() >= 0 || plug.getInsertionStage() != EntryPlugCarrierEntity.STAGE_LOCKED
                || !plug.isLockedToEva() || plug.getLinkedEva() != unit || plug.getVehicle() != unit
                || unit.getLockedEntryPlug() != plug)
            return "original_locked_capsule_chain_mismatch";
        if (unit instanceof EvaPrototypeEntity)
        {
            if (!plug.isIndependentUNPlug() || !unit.getPersistentData().hasUUID("UNPlug")
                    || !unit.getPersistentData().getUUID("UNPlug").equals(plug.getUUID()))
                return "independent_capsule_identity_mismatch";
        }
        else
        {
            var fleet = EvaFleetSavedData.get(level.getServer()).entry(variant).orElse(null);
            if (unit.isExperimentalUnit() || variant != unit.getUnitVariant() || plug.isIndependentUNPlug()
                    || plug.getAssignedVariant() != variant || fleet == null || !unit.getUUID().equals(fleet.canonicalId())
                    || !plug.getUUID().equals(fleet.entryPlugId()))
                return "canonical_airframe_identity_mismatch";
        }
        if (pilot == null)
        {
            if (unit.getPilotEntity() != null || plug.isVehicle()) return "empty_capsule_is_occupied";
        }
        else if (pilot.level() != level || !pilot.isAlive() || level.getEntity(pilot.getUUID()) != pilot
                || unit.getPilotEntity() != pilot || pilot.getVehicle() != plug
                || plug.getFirstPassenger() != pilot || plug.getPassengers().size() != 1)
            return "actual_pilot_chain_mismatch";
        // Unmounting invokes EvaUnit.removePassenger. During ASCENT it would
        // reset the launch and return the airframe to its original lower bed.
        if (unit.isLaunchSequenceActive() || unit.hasActiveCarrierMotion() || EvaAirTransportR31.active(unit)
                || unit.isCrucified() || unit.isNervLogisticsLocked() && !inHangar)
            return "mechanical_motion_or_handoff_owns_airframe";
        if (!inHangar)
        {
            AABB feet = unit.getBoundingBox();
            for (var link : IntegratedNervMapBuilder.liftLinks(level))
            {
                var bed = link.surfaceBed();
                // Only a footprint projected onto a known commissioned shaft
                // needs its actual hatch receipt; ordinary field ground is not
                // transformed into another launch station.
                if (unit.getY() >= bed.getY() + 1 && feet.maxX > bed.getX() - 15
                        && feet.minX < bed.getX() + 16 && feet.maxZ > bed.getZ() - 15 && feet.minZ < bed.getZ() + 16
                        && !NervSiloDoorEntity.hasClosedSurfaceSupport(level, bed))
                    return "projected_shaft_has_no_closed_physical_support";
            }
        }
        if (unit.isNoGravity() && !unit.isNervLogisticsLocked() && !nativeSupport(level, unit))
            return "gravity_release_has_no_loaded_physical_support";
        return "";
    }

    private static boolean nativeSupport(ServerLevel level, EvaUnit01Entity unit)
    {
        AABB body = unit.getBoundingBox();
        AABB feet = new AABB(body.minX, body.minY - .12, body.minZ, body.maxX, body.minY + .01, body.maxZ);
        if (!loaded(level, feet)) return false;
        for (var shape : level.getBlockCollisions(unit, feet)) if (!shape.isEmpty()) return true;
        return false;
    }

    public static boolean loaded(ServerLevel level, AABB bounds)
    {
        for (int x = ((int) Math.floor(bounds.minX)) >> 4; x <= ((int) Math.floor(bounds.maxX)) >> 4; x++)
            for (int z = ((int) Math.floor(bounds.minZ)) >> 4; z <= ((int) Math.floor(bounds.maxZ)) >> 4; z++)
                if (level.getChunkSource().getChunkNow(x, z) == null) return false;
        return bounds.minY >= level.getMinBuildHeight() && bounds.maxY < level.getMaxBuildHeight();
    }

    /** Full capsule preimage is local to this one server-thread transaction. */
    public static Snapshot snapshot(EntryPlugCarrierEntity plug)
    {
        return new Snapshot(plug.saveWithoutId(new CompoundTag()).copy(), plug.getUUID(),
                plug.getVehicle() == null ? null : plug.getVehicle().getUUID(), plug.getInsertionEpoch(),
                plug.getPassengers().stream().map(entity -> entity.getUUID()).toList());
    }

    /** Only a cancelled unmount with the original graph still intact may undo the stage publication. */
    public static boolean detach(EvaUnit01Entity unit, EntryPlugCarrierEntity plug, Snapshot before)
    {
        plug.unlockFromEva();
        if (plug.getVehicle() == null && before.plug().equals(plug.getUUID()) && !plug.isRemoved()
                && plug.level() == unit.level()
                && plug.getPassengers().stream().map(entity -> entity.getUUID()).toList().equals(before.passengers())) return true;
        if (plug.getVehicle() == unit && unit.getUUID().equals(before.host()) && before.plug().equals(plug.getUUID())
                && plug.getPassengers().stream().map(entity -> entity.getUUID()).toList().equals(before.passengers())
                && plug.getInsertionEpoch() == (before.epoch() == Integer.MAX_VALUE ? 1 : before.epoch() + 1)
                && (plug.getInsertionStage() == EntryPlugCarrierEntity.STAGE_EJECTING
                    || plug.getInsertionStage() == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING))
        {
            plug.load(before.nbt().copy());
            ProjectSeele.LOGGER.warn("Entry-plug extraction rolled back cancelled unmount: eva={} plug={} stage={} epoch={}",
                    unit.getUUID(), plug.getUUID(), plug.getInsertionStage(), plug.getInsertionEpoch());
        }
        else ProjectSeele.LOGGER.error("Entry-plug extraction unmount changed owner; explicit repair required: eva={} plug={} vehicle={}",
                unit.getUUID(), plug.getUUID(), plug.getVehicle() == null ? "none" : plug.getVehicle().getUUID());
        return false;
    }
}

package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.Angel;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.monster.Enemy;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * Parked vehicles that nobody is near skip their tick.
 *
 * A vehicle's tick costs the same whether it drives or stands, and the bases hold a hundred of them standing.
 * A vehicle is passed over only while all of this holds: nobody rides it and it rides nothing, its engine and
 * weapons are off with no target, it tows nothing, it is undamaged, it stands on the ground and has not moved or
 * turned for five seconds, no story or transport event runs, nothing hostile is within 256 blocks, and every player
 * is more than 160 blocks away. Each condition is looked at again every tick, so the vehicle ticks again in the tick
 * one of them fails.
 *
 * An auto-aiming tower that is switched on looks for targets in its own tick, so one that is passed over sees
 * nothing. It is woken by the same two things as any vehicle: a player within 160 blocks, or something hostile
 * within 256, which is as far as the HPJ-11 looks. What that list of hostile things leaves out, a shell fired from
 * further off for one, reaches a base whose towers are still asleep.
 *
 * Nothing is stored and nothing is moved: a vehicle that ticks again carries on from where it stood. While it is
 * passed over, the chunk ticket its own tick would have asked for is kept alive, so what is loaded and what the
 * directors can find stays as it was.
 */
public final class SbwIdlePause
{
    /** A vehicle's own state, read through the mixin on its class. */
    public interface Vehicle
    {
        /** Engine and weapons off, no target, nothing towed, full health. */
        boolean projectseele$atRest();
        /** Ask for the chunk ticket the vehicle's last ticks asked for, if they did. */
        void projectseele$holdChunk();
    }

    /** An auto-aiming tower. One that holds a target is working, whatever its weapon is doing this tick. */
    public interface Tower
    {
        boolean projectseele$hasTarget();
    }

    private static final boolean DISABLED = Boolean.getBoolean("projectseele.tickIdleVehicles");
    private static final double PLAYER_RANGE = 160, THREAT_RANGE = 256;
    private static final int SETTLE_TICKS = 100, THREAT_TICKS = 20;
    private static final String[] REASONS = {"paused", "ridden_or_riding", "moving_or_unsupported", "engine_weapon_target_towing_or_damaged",
            "tower_has_target", "story_or_transport", "player_within_160", "settling", "hostile_within_256"};
    private static final int PAUSED = 0, RIDDEN = 1, MOVING = 2, WORKING = 3, TOWER_TARGET = 4, EVENT = 5, PLAYER = 6, SETTLING = 7, THREAT = 8;

    // Server thread only.
    private static final Map<Entity, Rest> REST = new WeakHashMap<>();
    private static final Map<ServerLevel, Scene> SCENES = new WeakHashMap<>();
    private static final long[] COUNTS = new long[REASONS.length];
    private static boolean reported;

    /** Where a vehicle stood when it was last seen to have moved, and since when. The position is compared by identity. */
    private record Rest(Vec3 position, float yaw, float pitch, long since) {}

    /** What is the same for every vehicle of a level in one tick. */
    private static final class Scene
    {
        long eventTick = Long.MIN_VALUE, threatTick;
        /** Whether the hostile things have been listed at all: before that there is no tick to count from. */
        boolean event, listed;
        final List<AABB> threats = new ArrayList<>();
    }

    private SbwIdlePause() {}

    public static boolean paused(ServerLevel level, Entity entity, Vehicle vehicle)
    {
        if (DISABLED) return false;
        if (!entity.isAlive() || entity.isVehicle() || entity.isPassenger()) return moved(entity, RIDDEN);
        Vec3 motion = entity.getDeltaMovement();
        if (!entity.onGround() || entity.isOnFire() || entity.isInWaterOrBubble() || entity.hurtMarked
                || motion.horizontalDistanceSqr() > 1.0E-6D || Math.abs(motion.y) > 0.12D) return moved(entity, MOVING);
        if (!vehicle.projectseele$atRest()) return moved(entity, WORKING);
        if (entity instanceof Tower tower && tower.projectseele$hasTarget()) return moved(entity, TOWER_TARGET);
        long now = level.getGameTime();
        Scene scene = SCENES.computeIfAbsent(level, key -> new Scene());
        if (scene.eventTick != now) { scene.eventTick = now; scene.event = event(level); }
        if (scene.event) return count(EVENT);
        for (ServerPlayer player : level.players())
        {
            double dx = player.getX() - entity.getX(), dz = player.getZ() - entity.getZ();
            if (dx * dx + dz * dz <= PLAYER_RANGE * PLAYER_RANGE) return count(PLAYER);
        }
        Rest rest = REST.get(entity);
        if (rest == null || rest.position != entity.position() || rest.yaw != entity.getYRot() || rest.pitch != entity.getXRot())
        {
            REST.put(entity, new Rest(entity.position(), entity.getYRot(), entity.getXRot(), now));
            return count(SETTLING);
        }
        if (now - rest.since < SETTLE_TICKS) return count(SETTLING);
        if (!scene.listed || now - scene.threatTick >= THREAT_TICKS || now < scene.threatTick)
        {
            scene.listed = true; scene.threatTick = now; threats(level, scene.threats);
        }
        if (!scene.threats.isEmpty())
        {
            AABB reach = entity.getBoundingBox().inflate(THREAT_RANGE);
            for (AABB threat : scene.threats) if (threat.intersects(reach)) return count(THREAT);
        }
        // SBW's ticket lasts five ticks, so asking on every other tick keeps it without a gap.
        if ((now + entity.getId() & 1) == 0) vehicle.projectseele$holdChunk();
        if (!reported)
        {
            reported = true;
            ProjectSeele.LOGGER.info("Idle vehicle pause active: {} at {} is the first vehicle passed over", EntityType.getKey(entity.getType()), entity.blockPosition().toShortString());
        }
        COUNTS[PAUSED]++;
        return true;
    }

    private static boolean moved(Entity entity, int reason)
    {
        REST.remove(entity);
        return count(reason);
    }

    private static boolean count(int reason)
    {
        COUNTS[reason]++;
        return false;
    }

    /** A campaign scene or an air transport may give any vehicle work at any moment. */
    private static boolean event(ServerLevel level)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION)) return false;
        return !TvCampaignSavedData.get(level).active.isBlank() || UNAirLiftR29.active(level, 0) || UNAirLiftR29.active(level, 1)
                || !NervAirLiftR30.phaseName(level).equals("IDLE");
    }

    /** Loaded entities only: Angels, monsters, and any mob that has picked a target. */
    private static void threats(ServerLevel level, List<AABB> into)
    {
        into.clear();
        for (Entity entity : level.getAllEntities())
        {
            if (!entity.isAlive() || entity.isSpectator()) continue;
            if (entity instanceof Angel || entity instanceof Enemy || entity instanceof Mob mob && mob.getTarget() != null) into.add(entity.getBoundingBox());
        }
    }

    /** Vehicle ticks since the server started, by what was decided for them. */
    public static Map<String, Long> diagnostics()
    {
        Map<String, Long> result = new TreeMap<>();
        for (int reason = 0; reason < REASONS.length; reason++) result.put(REASONS[reason], COUNTS[reason]);
        return result;
    }
}

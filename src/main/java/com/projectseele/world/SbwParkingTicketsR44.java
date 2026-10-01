package com.projectseele.world;

import com.projectseele.entity.Angel;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.monster.Enemy;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.WeakHashMap;
import java.util.concurrent.atomic.LongAdder;

/** Parked project vehicles may unload; their original identity and AI settings persist. */
public final class SbwParkingTicketsR44
{
    private static final boolean DISABLED = Boolean.getBoolean("projectseele.keepIdleVehicleTickets");
    private static final Map<Entity, Rest> REST = new WeakHashMap<>();
    private static final Map<String, LongAdder> REASONS = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Set<Entity> SKIPPED = java.util.Collections.newSetFromMap(new WeakHashMap<>());
    private static final LongAdder CALLS = new LongAdder(), CANCELLED = new LongAdder();
    private static final Map<String, LongAdder> NATIVE_FLAGS = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Map<Entity, Map<String, Object>> NATIVE_SAMPLES = new WeakHashMap<>();
    private record Rest(net.minecraft.world.phys.Vec3 position, float yaw, float pitch,
                        long since, long threatTick, boolean threat) {}

    private static boolean retain(String reason)
    {
        REASONS.computeIfAbsent(reason, key -> new LongAdder()).increment();
        return false;
    }
    public static boolean disabled(){return DISABLED;}
    private static boolean nativeTargetPresent(String value)
    {
        // The pinned SBW defineSynchedData explicitly uses "undefined" for
        // both target fields. It is a known no-target value, not a UUID.
        // Every other nonblank string remains conservative, including unknown
        // or malformed values. No engine, weapon or identity field is changed.
        return !value.isBlank()&&!value.equals("undefined");
    }
    private static void observe(Entity e,boolean engine,boolean firing,boolean input,String turret,String passenger,String towing,java.util.List<String> towed)
    {
        flag("engine_running",engine);flag("weapon_firing",firing);flag("fire_input",input);
        flag("turret_target",nativeTargetPresent(turret));flag("passenger_target",nativeTargetPresent(passenger));
        flag("towing",!towing.isBlank());flag("towed",!towed.isEmpty());
        if(Math.floorMod(e.level().getGameTime()+e.getId(),20)==0||!NATIVE_SAMPLES.containsKey(e))
        {
            var state=new java.util.LinkedHashMap<String,Object>();state.put("uuid",e.getUUID().toString());state.put("type",String.valueOf(e.getType()));state.put("engine_running",engine);state.put("weapon_firing",firing);state.put("fire_input",input);state.put("turret_target_raw",turret);state.put("passenger_target_raw",passenger);state.put("towing_raw",towing);state.put("towed_raw",java.util.List.copyOf(towed));state.put("position",e.position().toString());state.put("observed_tick",e.level().getGameTime());NATIVE_SAMPLES.put(e,java.util.Collections.unmodifiableMap(state));
        }
    }
    private static void flag(String key,boolean value){if(value)NATIVE_FLAGS.computeIfAbsent(key,k->new LongAdder()).increment();}

    public static boolean skip(Entity vehicle, boolean engine, boolean firing,
            boolean fireInput, String turretTarget, String passengerTarget,
            String towing, java.util.List<String> towed)
    {
        CALLS.increment();
        if (DISABLED || !(vehicle.level() instanceof ServerLevel level)
                || !level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return retain("disabled_or_outside_project_dimension");
        }
        if (!vehicle.getTags().contains("seele_r07_owned")
                || !MilitaryR07Director.state(level).entities.containsValue(vehicle.getUUID()))
        {
            return retain("not_registered_project_vehicle");
        }
        if (turretTarget == null || passengerTarget == null || towing == null || towed == null)
        {
            return retain("unknown_native_state");
        }
        observe(vehicle,engine,firing,fireInput,turretTarget,passengerTarget,towing,towed);
        if (!vehicle.isAlive() || !vehicle.onGround() || vehicle.isVehicle() || vehicle.isPassenger()
                || vehicle.isOnFire() || vehicle.isInWaterOrBubble() || vehicle.hurtMarked
                || vehicle.getDeltaMovement().horizontalDistanceSqr() > 1.0E-6D
                || Math.abs(vehicle.getDeltaMovement().y) > 0.12D)
        {
            REST.remove(vehicle);
            return retain("occupied_moving_unsupported_or_damaged");
        }
        if (engine || firing || fireInput || nativeTargetPresent(turretTarget) || nativeTargetPresent(passengerTarget)
                || !towing.isBlank() || !towed.isEmpty())
        {
            REST.remove(vehicle);
            return retain("engine_weapon_target_or_towing");
        }
        if (!TvCampaignSavedData.get(level).active.isBlank()
                || UNAirLiftR29.active(level, 0) || UNAirLiftR29.active(level, 1)
                || !NervAirLiftR30.phaseName(level).equals("IDLE"))
        {
            return retain("campaign_or_transport");
        }
        double radius = Math.max(256D,
                (level.getServer().getPlayerList().getViewDistance() + 2) * 16D);
        for (var player : level.players())
        {
            double dx = player.getX() - vehicle.getX(), dz = player.getZ() - vehicle.getZ();
            if (dx * dx + dz * dz <= radius * radius)
            {
                return retain("player_simulation_or_approach");
            }
        }
        long now = level.getGameTime();
        Rest previous = REST.get(vehicle);
        if (previous == null || previous.position.distanceToSqr(vehicle.position()) > 1.0E-8D
                || previous.yaw != vehicle.getYRot() || previous.pitch != vehicle.getXRot())
        {
            REST.put(vehicle, new Rest(vehicle.position(), vehicle.getYRot(), vehicle.getXRot(), now, -1, true));
            return retain("settling");
        }
        boolean threat = previous.threat;
        long threatTick = previous.threatTick;
        if (threatTick < 0 || now - threatTick >= 20)
        {
            // This is an already loaded entity query. It never loads terrain
            // to find work, and an independently spawned combatant keeps the
            // native tickets even outside an authored campaign.
            threat = !level.getEntities(vehicle, vehicle.getBoundingBox().inflate(256D),
                    entity -> entity.isAlive() && !entity.isSpectator()
                            && (entity instanceof Angel || entity instanceof Enemy
                            || entity instanceof Mob mob && mob.getTarget() != null)).isEmpty();
            threatTick = now;
            REST.put(vehicle, new Rest(previous.position, previous.yaw, previous.pitch,
                    previous.since, threatTick, threat));
        }
        if (threat)
        {
            return retain("loaded_hostile_or_combat_target");
        }
        if (now - previous.since < 100)
        {
            return retain("settling");
        }
        // Suppress only SBW's own refresh. POST_TELEPORT expires through the
        // vanilla lifecycle; no other subsystem's ticket is removed here.
        CANCELLED.increment();
        SKIPPED.add(vehicle);
        return true;
    }

    public static Map<String, Object> diagnostics()
    {
        Map<String, Long> reasons = new TreeMap<>();
        REASONS.forEach((key, count) -> reasons.put(key, count.sum()));
        long loaded = SKIPPED.stream().filter(entity -> entity.level() instanceof ServerLevel level
                && level.getEntity(entity.getUUID()) == entity).count();
        Map<String,Long> flags=new TreeMap<>();NATIVE_FLAGS.forEach((k,v)->flags.put(k,v.sum()));
        var current=new java.util.ArrayList<Map<String,Object>>();NATIVE_SAMPLES.forEach((e,state)->{if(e.level() instanceof ServerLevel l&&l.getEntity(e.getUUID())==e)current.add(state);});
        return Map.of("refresh_calls", CALLS.sum(), "suppressed_refresh_calls", CANCELLED.sum(),
                "currently_loaded_suppressed_vehicles", loaded, "retained_reasons", reasons,
                "native_true_flags",flags,"current_native_samples",current,
                "performance", "NOT_DEMONSTRATED: initial R44 A/B suppressed zero and was slower; sentinel fix needs fresh A/B and real approach/boarding resume");
    }

    public static void unknownNativeState()
    {
        retain("native_state_read_failed");
    }

    private SbwParkingTicketsR44() {}
}

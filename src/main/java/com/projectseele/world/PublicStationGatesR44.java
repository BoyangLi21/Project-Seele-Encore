package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.sounds.SoundSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;

import java.nio.file.Files;
import java.lang.reflect.Field;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.UUID;
import java.util.HashSet;

/** Exact installed public barriers retain native bodies/shapes and the existing free service. */
public final class PublicStationGatesR44
{
    private static final Set<String> TYPES = Set.of(
            "mtr:ticket_barrier_entrance_1", "mtr:ticket_barrier_exit_1");
    private static final Map<MinecraftServer, Map<BlockPos, String>> INSTALLED = new WeakHashMap<>();
    private static final int OPEN_TICKS = 40;
    public record ReviewCounters(long opened, long held, long closed,
                                 UUID lastOpener, Set<UUID> heldActors) { }
    private static final Map<MinecraftServer, Map<BlockPos, ReviewCounters>> REVIEW = new WeakHashMap<>();

    public static ReviewCounters reviewCounters(ServerLevel level, BlockPos position)
    {
        return REVIEW.getOrDefault(level.getServer(), Map.of()).getOrDefault(position,
                new ReviewCounters(0, 0, 0, null, Set.of()));
    }

    private static void observed(ServerLevel level, BlockPos position, int kind, Entity actor, List<Entity> occupied)
    {
        if (!Boolean.getBoolean("projectseele.r44PublicGateReview")) return;
        var rows = REVIEW.computeIfAbsent(level.getServer(), ignored -> new HashMap<>());
        var old = reviewCounters(level, position);
        var holders = new HashSet<>(old.heldActors());
        if (occupied != null) for (var entity : occupied) holders.add(entity.getUUID());
        rows.put(position.immutable(), new ReviewCounters(old.opened() + (kind == 0 ? 1 : 0),
                old.held() + (kind == 1 ? 1 : 0), old.closed() + (kind == 2 ? 1 : 0),
                kind == 0 && actor != null ? actor.getUUID() : old.lastOpener(), Set.copyOf(holders)));
    }
    private static final ClassValue<Field> HOLDER_DATA = new ClassValue<>()
    {
        @Override protected Field computeValue(Class<?> type)
        {
            try
            {
                // Pinned MTR 4.0.5 HolderBase<T> exposes public final T data.
                // Cache the public accessor without linking MTR's optional
                // runtime jar into this project's compilation classpath.
                return type.getField("data");
            }
            catch (NoSuchFieldException failure)
            {
                throw new IllegalStateException("Unsupported actual MTR holder", failure);
            }
        }
    };

    public static boolean collisionBridge(Object state, Object world,
                                          Object position, Object actor)
    {
        try
        {
            if (!(unwrap(world) instanceof ServerLevel level)
                    || !(unwrap(state) instanceof BlockState nativeState)
                    || !(unwrap(position) instanceof BlockPos nativePosition)
                    || !(unwrap(actor) instanceof Entity nativeActor))
            {
                return false;
            }
            return collision(level, nativePosition, nativeState, nativeActor);
        }
        catch (ReflectiveOperationException failure)
        {
            throw new IllegalStateException("Actual MTR public-barrier holder rejected", failure);
        }
    }

    public static boolean scheduledBridge(Object state, Object world, Object position)
    {
        try
        {
            if (!(unwrap(world) instanceof ServerLevel level)
                    || !(unwrap(state) instanceof BlockState nativeState)
                    || !(unwrap(position) instanceof BlockPos nativePosition))
            {
                return false;
            }
            return scheduled(level, nativePosition, nativeState);
        }
        catch (ReflectiveOperationException failure)
        {
            throw new IllegalStateException("Actual MTR scheduled-barrier holder rejected", failure);
        }
    }

    private static Object unwrap(Object holder) throws ReflectiveOperationException
    {
        return HOLDER_DATA.get(holder.getClass()).get(holder);
    }

    public static boolean collision(ServerLevel level, BlockPos position,
                                    BlockState state, Entity actor)
    {
        if (!owned(level, position, state))
        {
            return false;
        }
        // Public automatic passage is separate from a NERV access reader.
        // Ordinary MTR barriers outside this finite manifest keep their own
        // ticket/balance logic. No score or ticket-system method is called.
        if (actor.isAlive() && (actor instanceof Player || actor instanceof NervStaffEntity))
        {
            BlockState opened = withOpen(state, "open");
            if (opened != state)
            {
                level.setBlockAndUpdate(position, opened);
                observed(level, position, 0, actor, null);
                level.playSound(null, position, SoundEvents.IRON_DOOR_OPEN,
                        SoundSource.BLOCKS, .40F, 1.35F);
            }
            if (!level.getBlockTicks().hasScheduledTick(position, state.getBlock()))
            {
                level.scheduleTick(position, state.getBlock(), OPEN_TICKS);
            }
        }
        return true;
    }

    public static boolean scheduled(ServerLevel level, BlockPos position, BlockState state)
    {
        if (!owned(level, position, state))
        {
            return false;
        }
        BlockState closed = withOpen(state, "closed");
        var shape = closed.getCollisionShape(level, position);
        boolean occupied = false;
        var allOccupants = new java.util.ArrayList<Entity>();
        for (AABB local : shape.toAabbs())
        {
            var world = local.move(position).inflate(.08);
            List<Entity> actors = level.getEntities((Entity) null, world,
                    entity -> entity.isAlive() && !entity.isSpectator());
            if (!actors.isEmpty())
            {
                occupied = true;
                allOccupants.addAll(actors);
            }
        }
        if (occupied)
        {
            observed(level, position, 1, null, allOccupants);
            // Never close an actual native leaf through any occupied body,
            // including an actor standing still inside the passage.
            if (state != withOpen(state, "open"))
            {
                level.setBlockAndUpdate(position, withOpen(state, "open"));
            }
            level.scheduleTick(position, state.getBlock(), 10);
        }
        else if (closed != state)
        {
            level.setBlockAndUpdate(position, closed);
            observed(level, position, 2, null, null);
            level.playSound(null, position, SoundEvents.IRON_DOOR_CLOSE,
                    SoundSource.BLOCKS, .35F, 1.35F);
        }
        return true;
    }

    public static boolean owned(ServerLevel level, BlockPos position, BlockState state)
    {
        if (!level.dimension().equals(FacilitySchemaV2.DIMENSION))
        {
            return false;
        }
        String actual = BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
        if (!TYPES.contains(actual))
        {
            return false;
        }
        return actual.equals(INSTALLED.computeIfAbsent(level.getServer(),
                PublicStationGatesR44::load).get(position));
    }

    private static Map<BlockPos, String> load(MinecraftServer server)
    {
        var path = server.getWorldPath(LevelResource.ROOT).resolve("r44_public_station_gates.json");
        if (!Files.isRegularFile(path))
        {
            return Map.of();
        }
        try
        {
            var document = JsonParser.parseString(Files.readString(path)).getAsJsonObject();
            if (document.get("schema").getAsInt() != 44
                    || !document.get("service").getAsString().equals("existing_free_public_service")
                    || !document.get("dimension").getAsString().equals("projectseele:geofront"))
            {
                throw new IllegalArgumentException("Wrong installed public-gate service boundary");
            }
            var result = new HashMap<BlockPos, String>();
            for (var item : document.getAsJsonArray("gates"))
            {
                var row = item.getAsJsonObject();
                String type = row.get("block").getAsString();
                var q = row.getAsJsonArray("position");
                var bounds = row.getAsJsonArray("station_bounds");
                if (!TYPES.contains(type) || q.size() != 3 || bounds.size() != 2
                        || row.get("station_id").getAsString().isBlank())
                {
                    throw new IllegalArgumentException("Invalid public station component");
                }
                int[] position = {q.get(0).getAsInt(), q.get(1).getAsInt(), q.get(2).getAsInt()};
                for (int axis = 0; axis < 3; axis++)
                {
                    if (position[axis] < bounds.get(0).getAsJsonArray().get(axis).getAsInt()
                            || position[axis] > bounds.get(1).getAsJsonArray().get(axis).getAsInt())
                    {
                        throw new IllegalArgumentException("Gate outside its actual public station bounds");
                    }
                }
                if (result.put(new BlockPos(position[0], position[1], position[2]), type) != null)
                {
                    throw new IllegalArgumentException("Duplicate native gate position");
                }
            }
            return Map.copyOf(result);
        }
        catch (Exception failure)
        {
            ProjectSeele.LOGGER.error("R44 public station gate contract unavailable; ordinary native MTR policy retained", failure);
            return Map.of();
        }
    }

    private static BlockState withOpen(BlockState state, String value)
    {
        for (Property<?> property : state.getProperties())
        {
            if (property.getName().equals("open"))
            {
                return withProperty(state, property, value);
            }
        }
        throw new IllegalStateException("Actual installed MTR barrier has no native open property");
    }

    private static <T extends Comparable<T>> BlockState withProperty(
            BlockState state, Property<T> property, String value)
    {
        return state.setValue(property, property.getValue(value).orElseThrow(() ->
                new IllegalStateException("Actual installed MTR barrier state rejected: " + value)));
    }

    private PublicStationGatesR44() {}
}

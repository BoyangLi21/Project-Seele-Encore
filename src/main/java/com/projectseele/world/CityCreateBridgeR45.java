package com.projectseele.world;

import com.google.gson.JsonObject;
import io.netty.buffer.Unpooled;
import java.lang.reflect.Method;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.fml.ModList;

/** Version-checked stock Create bridge; no compile-time dependency or generic disassembly. */
public final class CityCreateBridgeR45
{
    private CityCreateBridgeR45() {}

    public static int backendBlockLimit() throws Exception
    {
        if (!ModList.get().isLoaded("create") || !ModList.get().getModContainerById("create").orElseThrow()
                .getModInfo().getVersion().toString().contains("6.0.8"))
            throw new IllegalStateException("Reviewed Create6.0.8 backend required before any city detachment");
        Object config = Class.forName("com.simibubi.create.infrastructure.config.AllConfigs").getMethod("server").invoke(null);
        Object kinetics = config.getClass().getField("kinetics").get(config);
        Object max = kinetics.getClass().getField("maxBlocksMoved").get(kinetics);
        return ((Number) max.getClass().getMethod("get").invoke(max)).intValue();
    }

    public static void preflight(CityCreateCargoR45.Cargo cargo, BlockPos anchor) throws Exception
    {
        preflight(cargo, anchor, backendBlockLimit(), backendSpawnLimit());
    }

    public static int backendSpawnLimit() throws Exception
    {
        return Class.forName("com.simibubi.create.content.contraptions.data.ContraptionSyncLimiting").getField("LIMIT").getInt(null);
    }

    /** Pure encoding after main-thread backend/config validation; safe in the existing WAL worker. */
    public static void preflight(CityCreateCargoR45.Cargo cargo, BlockPos anchor, int blockLimit, int spawnLimit)
    {
        if (blockLimit <= 0 || spawnLimit <= 4096 || cargo.cells() > blockLimit)
            throw new IllegalStateException("Complete city cargo exceeds reviewed block limit");
        CompoundTag payload = CityCreateCargoR45.pulley(cargo, anchor);
        for (var raw : payload.getCompound("Blocks").getList("BlockList", net.minecraft.nbt.Tag.TAG_COMPOUND))
        {
            CompoundTag cell = (CompoundTag) raw;
            if (cell.contains("UpdateTag")) { cell.put("Data", cell.getCompound("UpdateTag").copy()); cell.remove("UpdateTag"); }
        }
        CompoundTag spawn = new CompoundTag(); spawn.put("Contraption", payload);
        FriendlyByteBuf bytes = new FriendlyByteBuf(Unpooled.buffer());
        try
        {
            bytes.writeNbt(spawn);
            if (bytes.readableBytes() + 4096 > spawnLimit) throw new IllegalStateException("Complete raw city spawn plus wrapper allowance exceeds network limit before detachment");
        }
        finally { bytes.release(); }
    }

    public static Entity create(ServerLevel level, CityCreateCargoR45.Cargo cargo, BlockPos anchor, UUID owner) throws Exception
    {
        if (cargo.cells() > backendBlockLimit())
            throw new IllegalStateException("Full measured cargo exceeds reviewed Create maxBlocksMoved");
        Class<?> base = Class.forName("com.simibubi.create.content.contraptions.Contraption");
        Class<?> pulley = Class.forName("com.simibubi.create.content.contraptions.pulley.PulleyContraption");
        Object contraption = pulley.getConstructor().newInstance();
        pulley.getMethod("readNBT", Level.class, CompoundTag.class, boolean.class)
                .invoke(contraption, level, CityCreateCargoR45.pulley(cargo, anchor), false);
        Entity entity = (Entity) Class.forName("com.simibubi.create.content.contraptions.OrientedContraptionEntity")
                .getMethod("create", Level.class, base, Direction.class).invoke(null, level, contraption, Direction.SOUTH);
        entity.setUUID(owner); entity.setPos(anchor.getX() + .5, anchor.getY(), anchor.getZ() + .5);
        verify(entity, cargo);
        FriendlyByteBuf bytes = new FriendlyByteBuf(Unpooled.buffer());
        try
        {
            entity.getClass().getMethod("writeSpawnData", FriendlyByteBuf.class).invoke(entity, bytes);
            int limit = Class.forName("com.simibubi.create.content.contraptions.data.ContraptionSyncLimiting").getField("LIMIT").getInt(null);
            if (bytes.readableBytes() > limit) throw new IllegalStateException("Whole cargo exceeds raw stock network budget");
            CompoundTag delivered = bytes.readAnySizeNbt();
            if (delivered == null) throw new IllegalStateException("Create silently rejected cargo network payload");
            CityCreateCargoR45.verify(cargo, delivered.getCompound("Contraption"));
        }
        catch (Exception failure) { entity.discard(); throw failure; }
        finally { bytes.release(); }
        return entity;
    }

    public static void verify(Entity entity, CityCreateCargoR45.Cargo cargo) throws Exception
    {
        CompoundTag tag = new CompoundTag();
        if (!entity.save(tag)) throw new IllegalStateException("Moving cargo cannot persist original owner UUID/NBT");
        CityCreateCargoR45.verify(cargo, tag.getCompound("Contraption"));
    }

    public static boolean collisionReady(Entity entity) throws Exception
    {
        Object contraption = entity.getClass().getMethod("getContraption").invoke(entity);
        return ((java.util.Optional<?>) contraption.getClass().getMethod("getSimplifiedEntityColliders").invoke(contraption)).isPresent();
    }

    /** QA observation only: never starts, cancels, joins pending work or supplies surrogate colliders. */
    public static JsonObject collisionDiagnostics(Entity entity) throws Exception
    {
        Object contraption = entity.getClass().getMethod("getContraption").invoke(entity);
        Class<?> base = Class.forName("com.simibubi.create.content.contraptions.Contraption");
        var field = base.getDeclaredField("simplifiedEntityColliderProvider");
        field.setAccessible(true);
        var future = (java.util.concurrent.CompletableFuture<?>) field.get(contraption);
        JsonObject row = new JsonObject(); row.addProperty("owner_uuid", entity.getUUID().toString());
        row.addProperty("alive", entity.isAlive()); row.addProperty("future_created", future != null);
        row.addProperty("colliders_present", ((java.util.Optional<?>) contraption.getClass()
                .getMethod("getSimplifiedEntityColliders").invoke(contraption)).isPresent());
        if (future != null)
        {
            boolean done = future.isDone(), exceptional = done && future.isCompletedExceptionally(), cancelled = done && future.isCancelled();
            row.addProperty("future_done", done); row.addProperty("future_pending", !done);
            row.addProperty("future_exceptional", exceptional); row.addProperty("future_cancelled", cancelled);
            row.addProperty("colliders_present_after_future_sample", ((java.util.Optional<?>) contraption.getClass()
                    .getMethod("getSimplifiedEntityColliders").invoke(contraption)).isPresent());
            if (done && exceptional)
            {
                try { future.join(); }
                catch (java.util.concurrent.CompletionException | java.util.concurrent.CancellationException failure)
                {
                    java.io.StringWriter text = new java.io.StringWriter();
                    failure.printStackTrace(new java.io.PrintWriter(text)); row.addProperty("completed_failure_stack", text.toString());
                }
            }
        }
        return row;
    }

    public static void move(Entity entity, Vec3 target) throws Exception
    {
        Vec3 delta = target.subtract(entity.position());
        entity.setPos(target.x, target.y, target.z);
        Method motion = entity.getClass().getMethod("setContraptionMotion", Vec3.class);
        motion.invoke(entity, delta);
    }

    public static void stop(Entity entity) throws Exception
    {
        entity.getClass().getMethod("setContraptionMotion", Vec3.class).invoke(entity, Vec3.ZERO);
    }

    public static boolean blockedByTerrain(Entity entity, Vec3 target, boolean endpoint) throws Exception
    {
        Vec3 delta = target.subtract(entity.position());
        if (delta.lengthSqr() == 0) return false;
        entity.getClass().getMethod("setContraptionMotion", Vec3.class).invoke(entity, delta);
        Class<?> base = Class.forName("com.simibubi.create.content.contraptions.AbstractContraptionEntity");
        boolean blocked = (Boolean) Class.forName("com.simibubi.create.content.contraptions.ContraptionCollider")
                .getMethod("collideBlocks", base).invoke(null, entity);
        // Stock integer leading-voxel prediction may include a lower saddle
        // whose top only touches the exact final floor. Native full bounding
        // collision must prove the final prism clear before allowing contact.
        if (blocked && endpoint && !entity.level().getBlockCollisions(entity,
                entity.getBoundingBox().move(delta)).iterator().hasNext()) return false;
        return blocked;
    }

    /** First blocked fact only. Stock returns a boolean, never a clipped/returned dy. */
    public static JsonObject stockBlockedFact(Entity entity, Vec3 target) throws Exception
    {
        JsonObject row = new JsonObject(); Vec3 delta = target.subtract(entity.position());
        row.addProperty("owner_uuid", entity.getUUID().toString()); row.addProperty("position", entity.position().toString());
        row.addProperty("target", target.toString()); row.addProperty("requested_delta", delta.toString());
        row.addProperty("requested_dy", delta.y); row.addProperty("stock_motion_after_call", entity.getDeltaMovement().toString());
        row.addProperty("stock_motion_dy_after_call", entity.getDeltaMovement().y);
        row.addProperty("stock_return_type", "boolean"); row.addProperty("stock_blocked_return", true);
        row.addProperty("source_world_AABB", entity.getBoundingBox().toString());
        row.addProperty("target_world_AABB", entity.getBoundingBox().move(delta).toString());
        Direction direction = Direction.getNearest(delta.x, delta.y, delta.z); BlockPos anchor = BlockPos.containing(entity.position());
        row.addProperty("integer_position_anchor", anchor.toString());
        if (direction.getAxisDirection() == Direction.AxisDirection.POSITIVE) anchor = anchor.relative(direction);
        row.addProperty("actual_stock_integer_query_anchor", anchor.toString()); row.addProperty("movement_direction", direction.toString());
        row.addProperty("saved_before_stop", true); row.addProperty("world_written", false); return row;
    }

    /** Bounded non-authoritative per-face native replay; never modifies the actual owner/provider/block map. */
    public static JsonObject locateStockWorldBlocker(Entity entity, Vec3 target) throws Exception
    {
        long began = System.nanoTime(); Vec3 delta = target.subtract(entity.position());
        Direction direction = Direction.getNearest(delta.x, delta.y, delta.z); BlockPos anchor = BlockPos.containing(entity.position());
        if (direction.getAxisDirection() == Direction.AxisDirection.POSITIVE) anchor = anchor.relative(direction);
        Class<?> base = Class.forName("com.simibubi.create.content.contraptions.Contraption");
        Class<?> translating = Class.forName("com.simibubi.create.content.contraptions.TranslatingContraption");
        Object original = entity.getClass().getMethod("getContraption").invoke(entity);
        @SuppressWarnings("unchecked") java.util.Map<BlockPos, net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.StructureBlockInfo> blocks =
                (java.util.Map<BlockPos, net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.StructureBlockInfo>) base.getMethod("getBlocks").invoke(original);
        @SuppressWarnings("unchecked") java.util.Set<BlockPos> faces = (java.util.Set<BlockPos>) translating
                .getMethod("getOrCreateColliders", Level.class, Direction.class).invoke(original, entity.level(), direction);
        Object observer = Class.forName("com.simibubi.create.content.contraptions.pulley.PulleyContraption").getConstructor().newInstance();
        var blockField = base.getDeclaredField("blocks"); blockField.setAccessible(true);
        blockField.set(observer, java.util.Collections.unmodifiableMap(blocks));
        var colliderField = translating.getDeclaredField("cachedColliders"); colliderField.setAccessible(true);
        var directionField = translating.getDeclaredField("cachedColliderDirection"); directionField.setAccessible(true); directionField.set(observer, direction);
        Method predicate = Class.forName("com.simibubi.create.content.contraptions.ContraptionCollider")
                .getMethod("isCollidingWithWorld", Level.class, translating, BlockPos.class, Direction.class);
        JsonObject result = new JsonObject(); com.google.gson.JsonArray inspected = new com.google.gson.JsonArray();
        int visited = 0; boolean found = false;
        for (BlockPos local : faces)
        {
            if (visited >= 64 || System.nanoTime() - began > 10_000_000L) break;
            colliderField.set(observer, java.util.Set.of(local));
            boolean blocked = (Boolean) predicate.invoke(null, entity.level(), observer, anchor, direction);
            BlockPos world = local.offset(anchor); var state = entity.level().getBlockState(world);
            JsonObject face = new JsonObject(); face.addProperty("sequence", visited++); face.addProperty("face_local_pos", local.toString());
            face.addProperty("actual_world_query_pos", world.toString()); face.addProperty("actual_stock_shape_query_pos", local.toString());
            face.addProperty("native_single_face_predicate", blocked); face.addProperty("world_chunk_loaded", entity.level().isLoaded(world));
            face.addProperty("actual_state_full_NBT", net.minecraft.nbt.NbtUtils.writeBlockState(state).toString());
            var be = entity.level().getBlockEntity(world); face.addProperty("actual_world_BE_present", be != null);
            if (be != null) face.addProperty("actual_world_BE_full_NBT", be.saveWithFullMetadata().toString());
            face.addProperty("original_face_state_full_NBT", net.minecraft.nbt.NbtUtils.writeBlockState(blocks.get(local).state()).toString());
            face.addProperty("stock_query_collision_AABBs", state.getCollisionShape(entity.level(), local).toAabbs().toString());
            face.addProperty("physical_world_pos_collision_AABBs", state.getCollisionShape(entity.level(), world).toAabbs().toString());
            inspected.add(face);
            if (blocked) { found = true; result.add("first_positive_native_world_face", face); break; }
        }
        result.add("inspected_faces", inspected); result.addProperty("total_native_faces", faces.size()); result.addProperty("visited_faces", visited);
        result.addProperty("positive_native_world_face_found", found); result.addProperty("all_faces_visited", visited == faces.size());
        result.addProperty("elapsed_ms", (System.nanoTime() - began) / 1e6); result.addProperty("face_limit", 64); result.addProperty("time_limit_ms", 10);
        result.addProperty("native_original_iteration_order_preserved", true); result.addProperty("observer_spawned", false);
        result.addProperty("full_original_cargo_map_used_readonly", true); result.addProperty("actual_owner_cache_or_provider_or_block_map_modified", false);
        result.addProperty("world_written", false); result.addProperty("localization_is_not_motion_authority", true);
        result.addProperty("world_collision_absence_proved", !found && visited == faces.size());
        return result;
    }
}

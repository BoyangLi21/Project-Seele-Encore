package com.projectseele.world;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import io.netty.buffer.Unpooled;
import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.fml.ModList;
import net.minecraftforge.fml.common.Mod;

/** Default-off native cargo transport probe; never removes source city blocks. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityCreateRigidLiftR45
{
    private static final String JOB = System.getProperty("projectseele.r45CityCreateProbe", "");
    private static final TicketType<ChunkPos> TICKET = TicketType.create(
            "projectseele_r45_create_cargo_probe", Comparator.comparingLong(ChunkPos::toLong), 0);
    private static final int ENTITY_TICKET_DISTANCE = 2;
    private static JsonObject input;
    private static final JsonArray samples = new JsonArray();
    private static final JsonArray physics = new JsonArray();
    private static JsonObject firstDeviation, maximumDeviation;
    private static ServerLevel level;
    private static Entity entity;
    private static ArmorStand collisionProbe;
    private static CityCreateCargoR45.Cargo cargo;
    private static Method motion, getContraption, writeContraption;
    private static Vec3 start;
    private static AABB route;
    private static Path output;
    private static String phase = "LOAD", mode, identity, sourceHash;
    private static int age, timer, packetBytes, createLimit, assemblyLimit;
    private static int configuredDuration, settleTicks, holdTicks;
    private static double distance, peakControllerMs, maxProbeFeetError;
    private static double peakContactTranslation;
    private static int collisionSamples;
    private static String motionProfile;
    private static int rampTicks;
    private static int outDuration;
    private static BlockPos observerSupportLocal;
    private static AABB observerSupportShape;
    private static CompoundTag observerSupportState;
    private static long begun, latestTick;
    private static boolean done, checkpoint;

    private CityCreateRigidLiftR45() {}

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void levelEnd(TickEvent.LevelTickEvent event)
    {
        if (JOB.isEmpty() || done || level == null || event.level != level
                || event.phase != TickEvent.Phase.END) return;
        try
        {
            long tickStart = System.nanoTime();
            trace("before_controller");
            drive();
            trace("after_controller_before_stock_collision");
            if (entity != null && getContraption != null)
            {
                Vec3 previous = (Vec3) entity.getClass().getMethod("getPrevPositionVec").invoke(entity);
                peakContactTranslation = Math.max(peakContactTranslation, entity.position().distanceTo(previous));
            }
            peakControllerMs = Math.max(peakControllerMs, (System.nanoTime() - tickStart) / 1e6);
        }
        catch (Throwable failure) { fail(failure); }
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void afterLevelEnd(TickEvent.LevelTickEvent event)
    {
        if (JOB.isEmpty() || done || level == null || event.level != level || event.phase != TickEvent.Phase.END) return;
        try { trace("after_stock_collision"); }
        catch (Throwable failure) { fail(failure); }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (JOB.isEmpty() || done) return;
        try
        {
            if (event.phase != TickEvent.Phase.END) return;
            if (++age < 40) return;
            long now = System.nanoTime();
            if (latestTick != 0 && age % 20 == 0)
            {
                JsonObject sample = new JsonObject();
                sample.addProperty("age", age); sample.addProperty("phase", phase);
                sample.addProperty("preceding_tick_ms", (now - latestTick) / 1e6);
                if (entity != null) sample.addProperty("y", entity.getY());
                samples.add(sample);
            }
            latestTick = now;
            if (input == null) initialise(event.getServer());
            level.resetEmptyTime();
            if (age > input.get("timeout_ticks").getAsInt()) throw new IllegalStateException("Probe timeout");
            switch (phase)
            {
                case "LOAD" ->
                {
                    if (!resident()) return;
                    verifyEmptyRoute();
                    createEntity();
                    phase = "WAIT_READY";
                }
                case "WAIT_READY" ->
                {
                    if (!entity.isAlive()) throw new IllegalStateException("Create entity disappeared without vehicle");
                    Object contraption = getContraption.invoke(entity);
                    var boxes = (java.util.Optional<?>) contraption.getClass().getMethod("getSimplifiedEntityColliders").invoke(contraption);
                    if (boxes.isEmpty()) return;
                    snapshot("ready");
                    if (input.get("spawn_collision_probe").getAsBoolean()) spawnCollisionProbe();
                    phase = "SETTLE"; timer = 0;
                }
                case "SETTLE" ->
                {
                    if (++timer >= settleTicks) { phase = "OUT"; timer = 0; }
                }
                case "OUT" ->
                {
                    if (++timer >= (mode.equals("interrupt") ? configuredDuration / 2 : outDuration))
                    {
                        phase = "HOLD"; timer = 0;
                        snapshot("translated");
                    }
                }
                case "HOLD" ->
                {
                    if (++timer >= holdTicks)
                    {
                        if (mode.equals("interrupt"))
                        {
                            persistCheckpoint();
                            checkpoint = true;
                            finish("checkpoint", true);
                        }
                        else { phase = "BACK"; timer = 0; }
                    }
                }
                case "BACK" ->
                {
                    if (++timer >= configuredDuration)
                    {
                        phase = "FINAL_SETTLE"; timer = 0;
                        snapshot("returned");
                    }
                }
                case "RESUME_WAIT" -> { return; }
                case "FINAL_SETTLE" ->
                {
                    if (++timer >= settleTicks) finish("complete", true);
                }
                default -> throw new IllegalStateException("Unknown native phase " + phase);
            }
            if (collisionProbe != null)
            {
                double expected = supportBox().maxY;
                maxProbeFeetError = Math.max(maxProbeFeetError, Math.abs(collisionProbe.getY() - expected));
                collisionSamples++;
                trace("server_end");
            }
        }
        catch (Throwable failure) { fail(failure); }
    }

    private static void fail(Throwable failure)
    {
        try
        {
            if (input != null)
            {
                JsonObject report = report(false);
                report.addProperty("error", failure.toString());
                writeReport("failed", report);
            }
        }
        catch (Throwable reportFailure) { failure.addSuppressed(reportFailure); }
        checkpoint = false;
        cleanup(); done = true;
        ProjectSeele.LOGGER.error("R45 Create rigid cargo probe failed closed", failure);
    }

    private static void initialise(MinecraftServer server) throws Exception
    {
        input = JsonParser.parseString(Files.readString(Path.of(JOB))).getAsJsonObject();
        if (!input.get("enable_native_probe").getAsBoolean()) throw new IllegalStateException("Explicit probe enable required");
        Path world = server.getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
        if (!world.getFileName().toString().equals("SEELE_FIELD_R45_REVIEW")
                || !world.equals(Path.of(input.get("world").getAsString()).toAbsolutePath().normalize()))
            throw new IllegalStateException("Disposable R45 review world only");
        level = server.getLevel(ResourceKey.create(Registries.DIMENSION,
                new ResourceLocation(input.get("dimension").getAsString())));
        if (level == null || level.getSeed() != input.get("world_seed").getAsLong()) throw new IllegalStateException("Wrong dimension/seed");
        identity = input.get("world_id").getAsString();
        if (!identity.equals(Tokyo3BuildingWorldIdentityR44.get(level))) throw new IllegalStateException("Foreign world identity");
        output = Path.of(input.get("output").getAsString()).toAbsolutePath().normalize();
        Files.createDirectories(output);
        if (!ModList.get().isLoaded("create")) throw new IllegalStateException("Create not installed; no stock fallback armed");
        String createVersion = ModList.get().getModContainerById("create").orElseThrow().getModInfo().getVersion().toString();
        if (!createVersion.contains("6.0.8")) throw new IllegalStateException("Unverified Create API epoch " + createVersion);
        mode = input.get("mode").getAsString();
        if (!java.util.Set.of("roundtrip", "interrupt", "resume").contains(mode)) throw new IllegalStateException("Unknown probe mode");
        JsonArray archives = input.getAsJsonArray("archives");
        if (archives.size() != 93) throw new IllegalStateException("Complete 93-tower cargo input required");
        for (var raw : archives)
        {
            JsonObject archive = raw.getAsJsonObject();
            if (!hash(Path.of(archive.get("path").getAsString())).equals(archive.get("sha256").getAsString()))
                throw new IllegalStateException("Measured archive changed; refreeze before runtime");
        }
        JsonObject selected = archives.get(input.get("tower_index").getAsInt()).getAsJsonObject();
        sourceHash = selected.get("sha256").getAsString();
        cargo = CityCreateCargoR45.read(Path.of(selected.get("path").getAsString()), identity);
        Object serverConfig = Class.forName("com.simibubi.create.infrastructure.config.AllConfigs").getMethod("server").invoke(null);
        Object kinetics = serverConfig.getClass().getField("kinetics").get(serverConfig);
        Object config = kinetics.getClass().getField("maxBlocksMoved").get(kinetics);
        assemblyLimit = ((Number) config.getClass().getMethod("get").invoke(config)).intValue();
        if (cargo.cells() > assemblyLimit)
            throw new IllegalStateException("Full tower requires reviewed Create maxBlocksMoved >= " + cargo.cells() + "; current " + assemblyLimit);
        createLimit = Class.forName("com.simibubi.create.content.contraptions.data.ContraptionSyncLimiting").getField("LIMIT").getInt(null);
        JsonArray anchor = input.getAsJsonArray("anchor");
        start = new Vec3(anchor.get(0).getAsDouble() + .5, anchor.get(1).getAsDouble(), anchor.get(2).getAsDouble() + .5);
        if (start.x % 1 != .5 || start.y % 1 != 0 || start.z % 1 != .5) throw new IllegalStateException("Integer block anchor required");
        distance = input.get("delta_y").getAsDouble();
        configuredDuration = input.get("duration_ticks").getAsInt();
        outDuration = mode.equals("resume") ? configuredDuration / 2 : configuredDuration;
        motionProfile = input.has("motion_profile") ? input.get("motion_profile").getAsString() : "c1_trapezoid";
        rampTicks = input.has("ramp_ticks") ? input.get("ramp_ticks").getAsInt() : Math.min(16, configuredDuration / 4);
        if (!java.util.Set.of("constant", "c1_trapezoid").contains(motionProfile)) throw new IllegalStateException("Unknown mechanical velocity profile");
        settleTicks = input.get("settle_ticks").getAsInt(); holdTicks = input.get("hold_ticks").getAsInt();
        if (configuredDuration < 20 || configuredDuration > 4800 || configuredDuration % 2 != 0
                || Math.abs(distance / configuredDuration) > .5 || distance == 0 || settleTicks < 20 || holdTicks < 20)
            throw new IllegalStateException("Unsafe/invalid mechanical probe timing");
        if (motionProfile.equals("c1_trapezoid") && (rampTicks < 2 || rampTicks > configuredDuration / 4
                || Math.abs(distance / (configuredDuration - rampTicks)) > .5
                || Math.abs(distance / ((configuredDuration - rampTicks) * (double) rampTicks)) > .04))
            throw new IllegalStateException("C1 ramp exceeds reviewed velocity/acceleration limits");
        int half = cargo.building().getInt("Half"), height = cargo.building().getInt("Height");
        route = new AABB(start.x - .5 - half, start.y + Math.min(0, distance), start.z - .5 - half,
                start.x - .5 + half + 1, start.y + height + 4 + Math.max(0, distance), start.z - .5 + half + 1);
        if (route.minY < level.getMinBuildHeight() || route.maxY >= level.getMaxBuildHeight()) throw new IllegalStateException("Route leaves dimension envelope");
        if (Math.abs(start.x - BlockPos.of(cargo.building().getLong("Centre")).getX()) < 600
                && Math.abs(start.z - BlockPos.of(cargo.building().getLong("Centre")).getZ()) < 600)
            throw new IllegalStateException("Probe must be isolated from the actual city; source blocks never removed");
        ticket(true); begun = System.nanoTime();
        if (mode.equals("resume"))
        {
            phase = "RESUME_WAIT";
            // Waiting is handled in drive only after the route chunks become
            // resident. The saved original entity UUID must resolve, never clone.
        }
    }

    private static void createEntity() throws Exception
    {
        Class<?> contraptionClass = Class.forName("com.simibubi.create.content.contraptions.Contraption");
        Class<?> pulleyClass = Class.forName("com.simibubi.create.content.contraptions.pulley.PulleyContraption");
        Object pulley = pulleyClass.getConstructor().newInstance();
        CompoundTag tag = CityCreateCargoR45.pulley(cargo, BlockPos.containing(start.subtract(.5, 0, .5)));
        pulleyClass.getMethod("readNBT", Level.class, CompoundTag.class, boolean.class).invoke(pulley, level, tag, false);
        writeContraption = contraptionClass.getMethod("writeNBT", boolean.class);
        CityCreateCargoR45.verify(cargo, (CompoundTag) writeContraption.invoke(pulley, false));
        entity = (Entity) Class.forName("com.simibubi.create.content.contraptions.OrientedContraptionEntity")
                .getMethod("create", Level.class, contraptionClass, Direction.class).invoke(null, level, pulley, Direction.SOUTH);
        bindMethods();
        entity.setPos(start.x, start.y, start.z);
        entity.addTag("r45_city_create_probe/" + identity);
        entity.getPersistentData().putString("R45CargoSHA256", sourceHash);
        checkSpawnPacket();
        if (!level.addFreshEntity(entity)) throw new IllegalStateException("Create cargo entity insertion rejected");
        snapshot("inserted");
    }

    private static void bindMethods() throws Exception
    {
        motion = entity.getClass().getMethod("setContraptionMotion", Vec3.class);
        getContraption = entity.getClass().getMethod("getContraption");
        writeContraption = Class.forName("com.simibubi.create.content.contraptions.Contraption").getMethod("writeNBT", boolean.class);
    }

    private static void checkSpawnPacket() throws Exception
    {
        FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
        try
        {
            entity.getClass().getMethod("writeSpawnData", FriendlyByteBuf.class).invoke(entity, buffer);
            packetBytes = buffer.readableBytes();
            CompoundTag delivered = buffer.readAnySizeNbt();
            if (delivered == null || delivered.getCompound("Contraption").isEmpty() || packetBytes > createLimit)
                throw new IllegalStateException("Complete Create spawn data exceeded stock network budget; no block/NBT truncation allowed");
            CityCreateCargoR45.verify(cargo, delivered.getCompound("Contraption"));
        }
        finally { buffer.release(); }
    }

    private static void drive() throws Exception
    {
        if (phase.equals("RESUME_WAIT"))
        {
            if (!resident()) return;
            CompoundTag saved = NbtIo.readCompressed(output.resolve("checkpoint.nbt").toFile());
            if (!identity.equals(saved.getString("WorldUUID")) || !sourceHash.equals(saved.getString("CargoSHA256")))
                throw new IllegalStateException("Foreign reload checkpoint");
            Entity restored = level.getEntity(saved.getUUID("EntityUUID"));
            if (restored == null) return;
            if (!restored.getTags().contains("r45_city_create_probe/" + identity)
                    || !sourceHash.equals(restored.getPersistentData().getString("R45CargoSHA256")))
                throw new IllegalStateException("Reload UUID resolves to a foreign actor");
            entity = restored; bindMethods();
            if (entity.position().distanceTo(new Vec3(saved.getDouble("X"), saved.getDouble("Y"), saved.getDouble("Z"))) > 1e-5)
                throw new IllegalStateException("Entity/control save epochs disagree; explicit recovery required, never teleport cargo or occupants");
            checkSpawnPacket(); snapshot("reloaded_original_uuid");
            if (saved.hasUUID("CollisionProbeUUID"))
            {
                Entity probe = level.getEntity(saved.getUUID("CollisionProbeUUID"));
                if (!(probe instanceof ArmorStand stand) || !probe.getTags().contains("r45_city_create_probe/" + identity))
                    throw new IllegalStateException("Saved collision probe identity missing/foreign");
                collisionProbe = stand;
            }
            phase = "OUT"; timer = 0;
            return;
        }
        if (entity == null || done) return;
        if (!entity.isAlive() || entity.getVehicle() != null) throw new IllegalStateException("Cargo identity/vehicle changed");
        double offset = phase.equals("OUT") ? (mode.equals("resume") ? distance / 2 + distance / 2 * fraction(timer + 1, outDuration) : distance * fraction(timer + 1, outDuration))
                : phase.equals("BACK") ? distance * (1D - fraction(timer + 1, configuredDuration))
                : phase.equals("HOLD") ? (mode.equals("interrupt") ? distance / 2 : distance)
                : 0;
        Vec3 target = start.add(0, offset, 0);
        Vec3 delta = target.subtract(entity.position());
        if (delta.length() > .500001) throw new IllegalStateException("Unexpected position divergence or motion quantum");
        if (!level.getEntities(entity, entity.getBoundingBox().expandTowards(delta).inflate(.05),
                actor -> !actor.getTags().contains("r45_city_create_probe/" + identity)
                        && !input.getAsJsonArray("allowed_probe_actor_uuids").contains(new com.google.gson.JsonPrimitive(actor.getUUID().toString()))).isEmpty())
            throw new IllegalStateException("Probe envelope became occupied; preserve actor and cargo for explicit retry");
        // Highest-priority Level END follows the entity tick and precedes
        // Create CommonEvents.onServerWorldTick's normal-priority collider.
        // Moving at Server START would let Create reset xo/yo/zo to the new
        // position and erase contact/platform motion before collision.
        entity.setPos(target.x, target.y, target.z);
        motion.invoke(entity, delta);
    }

    private static double fraction(int tick, int duration)
    {
        double t = Math.max(0, Math.min(duration, tick));
        if (motionProfile.equals("constant")) return t / duration;
        int ramp = Math.min(rampTicks, duration / 4);
        double normalisation = duration - ramp;
        if (t <= ramp) return t * t / (2D * ramp * normalisation);
        if (t >= duration - ramp)
        {
            double remaining = duration - t;
            return 1D - remaining * remaining / (2D * ramp * normalisation);
        }
        return (t - ramp / 2D) / normalisation;
    }

    private static AABB supportBox() throws Exception
    {
        if (observerSupportShape == null)
        {
            JsonArray support = input.getAsJsonArray("support_local");
            observerSupportLocal = new BlockPos(support.get(0).getAsInt(), support.get(1).getAsInt(), support.get(2).getAsInt());
            for (var raw : cargo.building().getList("Cargo", net.minecraft.nbt.Tag.TAG_COMPOUND))
                if (((CompoundTag) raw).getLong("Pos") == observerSupportLocal.asLong())
                { observerSupportState = ((CompoundTag) raw).getCompound("State").copy(); break; }
            if (observerSupportState == null) throw new IllegalStateException("No measured observer support cell");
            BlockState state = NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(), observerSupportState);
            Object contraption = getContraption.invoke(entity);
            BlockGetter view = (BlockGetter) contraption.getClass().getMethod("getContraptionWorld").invoke(contraption);
            VoxelShape shape = state.getCollisionShape(view, observerSupportLocal);
            if (shape.isEmpty()) throw new IllegalStateException("Observer support has empty native collision shape");
            observerSupportShape = shape.bounds();
        }
        return observerSupportShape.move(entity.getX() - .5 + observerSupportLocal.getX(), entity.getY() + observerSupportLocal.getY(), entity.getZ() - .5 + observerSupportLocal.getZ());
    }

    private static void trace(String stage) throws Exception
    {
        if (collisionProbe == null || entity == null) return;
        AABB support = supportBox();
        JsonObject row = new JsonObject();
        row.addProperty("stage", stage); row.addProperty("age", age); row.addProperty("game_time", level.getGameTime());
        row.addProperty("phase", phase); row.addProperty("timer", timer); row.addProperty("motion_profile", motionProfile);
        row.add("support_local", input.getAsJsonArray("support_local").deepCopy());
        row.add("entity_position", vector(entity.position())); row.add("entity_velocity", vector(entity.getDeltaMovement()));
        row.add("entity_previous_position", vector((Vec3) entity.getClass().getMethod("getPrevPositionVec").invoke(entity)));
        row.add("entity_box", box(entity.getBoundingBox())); row.add("native_support_world_box", box(support));
        row.addProperty("native_support_state", observerSupportState.toString()); row.add("native_support_local_box", box(observerSupportShape));
        row.add("actor_position", vector(collisionProbe.position())); row.add("actor_velocity", vector(collisionProbe.getDeltaMovement()));
        row.add("actor_box", box(collisionProbe.getBoundingBox())); row.addProperty("actor_on_ground", collisionProbe.onGround());
        row.addProperty("actor_no_gravity", collisionProbe.isNoGravity()); row.addProperty("actor_no_physics", collisionProbe.noPhysics);
        row.addProperty("expected_y", support.maxY); row.addProperty("actual_y", collisionProbe.getY());
        double error = Math.abs(collisionProbe.getY() - support.maxY);
        row.addProperty("signed_feet_error", collisionProbe.getY() - support.maxY); row.addProperty("absolute_feet_error", error);
        if (physics.size() < 16000) physics.add(row);
        if (stage.equals("server_end"))
        {
            if (firstDeviation == null && error > .35) firstDeviation = row.deepCopy();
            if (maximumDeviation == null || maximumDeviation.get("absolute_feet_error").getAsDouble() < error) maximumDeviation = row.deepCopy();
        }
    }

    private static JsonArray vector(Vec3 value)
    {
        JsonArray result = new JsonArray(); result.add(value.x); result.add(value.y); result.add(value.z); return result;
    }

    private static JsonArray box(AABB value)
    {
        JsonArray result = new JsonArray();
        for (double item : new double[] {value.minX, value.minY, value.minZ, value.maxX, value.maxY, value.maxZ}) result.add(item);
        return result;
    }

    private static void spawnCollisionProbe()
    {
        JsonArray support = input.getAsJsonArray("support_local");
        BlockPos pos = new BlockPos(support.get(0).getAsInt(), support.get(1).getAsInt(), support.get(2).getAsInt());
        boolean owned = false;
        for (var raw : cargo.building().getList("Cargo", net.minecraft.nbt.Tag.TAG_COMPOUND))
            if (((CompoundTag) raw).getLong("Pos") == pos.asLong()) owned = true;
        if (!owned) throw new IllegalStateException("Collision support must be a measured cargo cell");
        collisionProbe = EntityType.ARMOR_STAND.create(level);
        if (collisionProbe == null) throw new IllegalStateException("Cannot create native collision observer");
        collisionProbe.setInvulnerable(true);
        collisionProbe.setNoGravity(false);
        collisionProbe.noPhysics = false;
        collisionProbe.addTag("r45_city_create_probe/" + identity);
        collisionProbe.setPos(entity.getX() + pos.getX(), entity.getY() + pos.getY() + 1.01, entity.getZ() + pos.getZ());
        if (!level.addFreshEntity(collisionProbe)) throw new IllegalStateException("Collision observer spawn rejected");
    }

    private static void snapshot(String name) throws Exception
    {
        CompoundTag saved = new CompoundTag();
        if (!entity.save(saved)) throw new IllegalStateException("Create entity could not serialize");
        CityCreateCargoR45.verify(cargo, saved.getCompound("Contraption"));
        Entity restored = EntityType.loadEntityRecursive(saved.copy(), level, actor -> actor);
        if (restored == null || !restored.getUUID().equals(entity.getUUID())) throw new IllegalStateException("Create entity NBT reload lost original UUID");
        CompoundTag reserialized = new CompoundTag();
        if (!restored.save(reserialized)) throw new IllegalStateException("Reloaded entity cannot serialize");
        CityCreateCargoR45.verify(cargo, reserialized.getCompound("Contraption"));
        restored.discard();
        atomic(output.resolve(name + ".entity.nbt"), saved);
        JsonObject sample = new JsonObject();
        sample.addProperty("kind", name); sample.addProperty("age", age);
        sample.addProperty("entity_uuid", entity.getUUID().toString()); sample.addProperty("position", entity.position().toString());
        sample.addProperty("full_cargo_verified", true); samples.add(sample);
    }

    private static void persistCheckpoint() throws Exception
    {
        motion.invoke(entity, Vec3.ZERO);
        snapshot("checkpoint");
        CompoundTag saved = new CompoundTag();
        saved.putString("WorldUUID", identity); saved.putString("CargoSHA256", sourceHash);
        saved.putUUID("EntityUUID", entity.getUUID());
        if (collisionProbe != null) saved.putUUID("CollisionProbeUUID", collisionProbe.getUUID());
        saved.putDouble("X", entity.getX()); saved.putDouble("Y", entity.getY()); saved.putDouble("Z", entity.getZ());
        atomic(output.resolve("checkpoint.nbt"), saved);
    }

    private static void verifyEmptyRoute()
    {
        for (int x = (int) route.minX; x < route.maxX; x++)
            for (int z = (int) route.minZ; z < route.maxZ; z++)
                for (int y = (int) route.minY; y < route.maxY; y++)
                {
                    BlockPos pos = new BlockPos(x, y, z);
                    if (!level.getBlockState(pos).isAir() || level.getBlockEntity(pos) != null)
                        throw new IllegalStateException("Measured fixture route is not empty at " + pos + "; no automatic clearing permitted");
                }
        if (!level.getEntities((Entity) null, route.inflate(1)).isEmpty()) throw new IllegalStateException("Fixture route is occupied");
    }

    private static boolean resident()
    {
        for (int x = Math.floorDiv((int) route.minX, 16); x <= Math.floorDiv((int) route.maxX, 16); x++)
            for (int z = Math.floorDiv((int) route.minZ, 16); z <= Math.floorDiv((int) route.maxZ, 16); z++)
                if (!level.hasChunk(x, z)) return false;
        return true;
    }

    private static void ticket(boolean acquire)
    {
        if (level == null || route == null) return;
        for (int x = Math.floorDiv((int) route.minX, 16); x <= Math.floorDiv((int) route.maxX, 16); x++)
            for (int z = Math.floorDiv((int) route.minZ, 16); z <= Math.floorDiv((int) route.maxZ, 16); z++)
            {
                ChunkPos pos = new ChunkPos(x, z);
                // addRegionTicket distance 2 maps to level31 ENTITY_TICKING.
                // Distance0 only promises FULL blocks; a remote headless probe
                // then would not tick the contraption or collision observer.
                if (acquire) level.getChunkSource().addRegionTicket(TICKET, pos, ENTITY_TICKET_DISTANCE, pos);
                else level.getChunkSource().removeRegionTicket(TICKET, pos, ENTITY_TICKET_DISTANCE, pos);
            }
    }

    private static JsonObject report(boolean passed)
    {
        JsonObject report = new JsonObject();
        report.addProperty("schema", "projectseele.create-rigid-lift-probe-r45.v1");
        report.addProperty("passed", passed); report.addProperty("phase", phase); report.addProperty("age", age);
        report.addProperty("world_id", identity); report.addProperty("cargo_sha256", sourceHash);
        if (cargo != null) { report.addProperty("cargo_cells", cargo.cells()); report.addProperty("full_block_entities", cargo.blockEntities()); }
        report.addProperty("spawn_bytes", packetBytes); report.addProperty("create_spawn_limit", createLimit);
        report.addProperty("create_assembly_limit", assemblyLimit); report.addProperty("peak_controller_ms", peakControllerMs);
        report.addProperty("peak_native_contact_translation", peakContactTranslation);
        report.addProperty("server_armorstand_collision_samples", collisionSamples);
        report.addProperty("server_armorstand_max_feet_error", maxProbeFeetError);
        report.addProperty("motion_profile", motionProfile); report.addProperty("ramp_ticks", rampTicks);
        report.addProperty("physics_trace_capped", physics.size() >= 16000); report.add("physics_trace", physics);
        if (firstDeviation != null) report.add("first_deviation_over_0_35", firstDeviation);
        if (maximumDeviation != null) report.add("maximum_deviation", maximumDeviation);
        report.addProperty("elapsed_seconds", begun == 0 ? 0 : (System.nanoTime() - begun) / 1e9);
        report.addProperty("controller_world_block_placements", 0); report.addProperty("original_city_written", false);
        report.addProperty("native_client_collision_verified", false); report.addProperty("production_endpoint_transaction_ready", false);
        report.add("samples", samples); return report;
    }

    private static void finish(String marker, boolean passed) throws Exception
    {
        if (collisionProbe != null && (collisionSamples < 20 || maxProbeFeetError > .35))
            throw new IllegalStateException("Native moving-floor collision observer exceeded .35m or lacks samples: " + maxProbeFeetError);
        writeReport(marker, report(passed));
        if (!checkpoint) cleanup();
        done = true;
        ProjectSeele.LOGGER.info("R45 Create rigid cargo probe {}: {}", marker, output);
    }

    private static void writeReport(String marker, JsonObject report) throws IOException
    {
        if (output == null) return;
        Files.writeString(output.resolve(marker + ".json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }

    @SubscribeEvent
    public static void stopping(ServerStoppingEvent event)
    {
        if (JOB.isEmpty()) return;
        if (!checkpoint) cleanup();
        else ticket(false);
    }

    private static void cleanup()
    {
        if (entity != null && entity.getTags().contains("r45_city_create_probe/" + identity)) entity.discard();
        if (collisionProbe != null && collisionProbe.getTags().contains("r45_city_create_probe/" + identity)) collisionProbe.discard();
        collisionProbe = null;
        entity = null; ticket(false);
    }

    private static void atomic(Path target, CompoundTag tag) throws IOException
    {
        Path pending = Files.createTempFile(target.getParent(), target.getFileName().toString(), ".pending");
        try
        {
            NbtIo.writeCompressed(tag, pending.toFile());
            try (FileChannel file = FileChannel.open(pending, StandardOpenOption.WRITE)) { file.force(true); }
            Files.move(pending, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        }
        finally { Files.deleteIfExists(pending); }
    }

    private static String hash(Path file) throws Exception
    {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (var stream = Files.newInputStream(file))
        {
            byte[] buffer = new byte[65536]; int read;
            while ((read = stream.read(buffer)) >= 0) if (read > 0) digest.update(buffer, 0, read);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
}

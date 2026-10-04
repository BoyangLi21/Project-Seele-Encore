package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.PublicStationGatesR44;
import net.minecraft.client.Minecraft;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.ListTag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Property;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/** Actual integrated-client keys and native entityInside/scheduled tick; no gate switch calls. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PublicStationGateReviewR44
{
    private static final boolean ENABLED = Boolean.getBoolean("projectseele.r44PublicGateReview");
    private record Case(String id, BlockPos gate, Vec3 start, Vec3 finish) { }
    private enum Phase { STAGING, CLOSED, ENTERING, OCCUPIED, EXITING, RECLOSED, RESTORING }
    private static List<Case> cases;
    private static final JsonArray results = new JsonArray();
    private static int age, index = Integer.getInteger("projectseele.r44PublicGateStart", 0), end;
    private static int timer, heldTicks, steadyTicks;
    private static volatile Phase phase = Phase.STAGING;
    private static volatile Vec3 walkingTarget;
    private static volatile boolean finished;
    private static boolean initialized, optionsSaved, savedPause;
    private static int savedDistance;
    private static String failure = "";
    private static Vec3 originalPosition;
    private static ResourceKey<Level> originalDimension;
    private static GameType originalMode;
    private static boolean originalFlying;
    private static float originalYaw, originalPitch, originalHealth;
    private static ListTag originalInventory;
    private static UUID originalVehicle;
    private static JsonObject overallScoresBefore, caseScoresBefore, row;
    private static PublicStationGatesR44.ReviewCounters baseline;
    private static List<AABB> leafOnly = List.of();
    private static Vec3 holdingTarget;
    private static Vec3 previousHoldPosition;
    private static boolean stopping;
    private static final JsonArray movementTrace = new JsonArray();

    @SubscribeEvent
    public static void client(TickEvent.ClientTickEvent event)
    {
        if (!ENABLED || event.phase != TickEvent.Phase.END) return;
        var mc = Minecraft.getInstance();
        if (!optionsSaved)
        {
            optionsSaved = true;
            savedPause = mc.options.pauseOnLostFocus;
            savedDistance = mc.options.renderDistance().get();
            mc.options.pauseOnLostFocus = false;
            mc.options.renderDistance().set(8);
        }
        if (mc.screen instanceof net.minecraft.client.gui.screens.PauseScreen) mc.setScreen(null);
        keys(false);
        if (finished)
        {
            mc.options.pauseOnLostFocus = savedPause;
            mc.options.renderDistance().set(savedDistance);
            if (!stopping) { stopping = true; mc.stop(); }
            return;
        }
        if (mc.player == null || mc.level == null || mc.screen != null) return;
        mc.player.getAbilities().flying = false;
        mc.player.noPhysics = false;
        Vec3 target = walkingTarget;
        if (target != null)
        {
            var delta = target.subtract(mc.player.position());
            mc.player.setYRot((float) Math.toDegrees(Math.atan2(-delta.x, delta.z)));
            mc.player.setXRot(0);
            // Only key input during a case. The setup teleport is outside
            // the threshold, never inside/through the leaf under test.
            keys(delta.horizontalDistanceSqr() > .0100);
        }
    }

    private static void keys(boolean forward)
    {
        var options = Minecraft.getInstance().options;
        options.keyUp.setDown(forward);
        options.keyDown.setDown(false);
        options.keyLeft.setDown(false);
        options.keyRight.setDown(false);
        options.keyJump.setDown(false);
        options.keyShift.setDown(false);
        options.keySprint.setDown(false);
        options.keyAttack.setDown(false);
        options.keyUse.setDown(false);
    }

    @SubscribeEvent
    public static void server(TickEvent.ServerTickEvent event)
    {
        if (!ENABLED || finished || event.phase != TickEvent.Phase.END) return;
        var server = event.getServer();
        var mc = Minecraft.getInstance();
        if (mc.player == null || mc.level == null || mc.getSingleplayerServer() != server) return;
        var player = server.getPlayerList().getPlayer(mc.player.getUUID());
        if (player == null) return;
        Path world = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!world.getFileName().toString().equals(com.projectseele.visual.NativeReviewWorldsR45.expectedName()))
            throw new IllegalStateException("Public-gate client lifecycle refuses another world");
        try
        {
            require(++age < 120000, "Whole public-gate client run timed out");
            var level = server.getLevel(FacilitySchemaV2.DIMENSION);
            require(level != null, "Actual GeoFront level missing");
            if (!initialized)
            {
                cases = loadCases();
                end = Integer.getInteger("projectseele.r44PublicGateEnd", cases.size());
                require(index >= 0 && index < end && end <= cases.size(), "Invalid start/end range");
                originalPosition = player.position();
                originalDimension = player.level().dimension();
                originalMode = player.gameMode.getGameModeForPlayer();
                originalFlying = player.getAbilities().flying;
                originalYaw = player.getYRot(); originalPitch = player.getXRot();
                originalHealth = player.getHealth();
                originalInventory = player.getInventory().save(new ListTag()).copy();
                originalVehicle = player.getVehicle() == null ? null : player.getVehicle().getUUID();
                overallScoresBefore = scores(player);
                player.stopRiding();
                player.setGameMode(GameType.CREATIVE);
                player.getAbilities().flying = false;
                player.onUpdateAbilities();
                initialized = true;
                setup(level, player);
                return;
            }
            require(player.isAlive(), "Real client player died");
            require(Math.abs(player.getHealth() - originalHealth) < .001, "Health changed while operating a public gate");
            require(player.getInventory().save(new ListTag()).equals(originalInventory), "Inventory changed during gate lifecycle");
            if (phase == Phase.RESTORING)
            {
                if (++timer >= 8) complete(world, player);
                return;
            }
            var current = cases.get(index);
            if (timer % 10 == 0) trace(player, mc, current);
            require(++timer < 900, "Gate case timed out: " + current.id + " phase=" + phase
                    + " player=" + player.position() + " target=" + walkingTarget);
            BlockState state = level.getBlockState(current.gate);
            switch (phase)
            {
                case STAGING ->
                {
                    if (timer < 80 || !level.hasChunkAt(current.gate) || !mc.level.getChunkSource().hasChunk(current.gate.getX()>>4,current.gate.getZ()>>4)
                            || !mc.level.dimension().equals(level.dimension())) return;
                    require(player.position().distanceToSqr(current.start) < .10,
                            "Server staging position differs from outside threshold");
                    require(mc.player.position().distanceToSqr(current.start) < .15,
                            "Client did not acknowledge outside staging teleport");
                    require(PublicStationGatesR44.owned(level, current.gate, state), "Actual gate not in installed finite free-service manifest");
                    require(state.getBlock() == mc.level.getBlockState(current.gate).getBlock(), "Client/server gate type differs");
                    var closed = openState(state, "closed");
                    var opened = openState(state, "open");
                    var difference = Shapes.joinUnoptimized(closed.getCollisionShape(level, current.gate),
                            opened.getCollisionShape(level, current.gate), BooleanOp.ONLY_FIRST);
                    require(!difference.isEmpty(), "Native gate has no real closed-minus-open leaf volume");
                    leafOnly = difference.toAabbs().stream().map(b -> b.move(current.gate)).toList();
                    var largest = leafOnly.stream().max(Comparator.comparingDouble(b -> b.getXsize() * b.getYsize() * b.getZsize())).orElseThrow();
                    holdingTarget = new Vec3((largest.minX + largest.maxX) / 2,
                            current.start.y, (largest.minZ + largest.maxZ) / 2);
                    var standingBody = new AABB(holdingTarget.x - .3, holdingTarget.y, holdingTarget.z - .3,
                            holdingTarget.x + .3, holdingTarget.y + 1.8, holdingTarget.z + .3);
                    require(leafOnly.stream().anyMatch(b -> b.intersects(standingBody)), "Selected hold point misses actual native leaf");
                    require(opened.getCollisionShape(level, current.gate).toAabbs().stream()
                            .map(b -> b.move(current.gate)).noneMatch(b -> b.intersects(standingBody)),
                            "Selected hold point is inside a fixed native open body");
                    row.add("actual_native_leaf_only_world_boxes", new Gson().toJsonTree(leafOnly.stream().map(PublicStationGateReviewR44::box).toList()));
                    row.add("actual_hold_target", new Gson().toJsonTree(point(holdingTarget)));
                    phase = Phase.CLOSED; timer = 0;
                }
                case CLOSED ->
                {
                    if (!openValue(state).equals("closed") || !openValue(mc.level.getBlockState(current.gate)).equals("closed")) return;
                    baseline = PublicStationGatesR44.reviewCounters(level, current.gate);
                    row.addProperty("initial_native_closed_observed", true);
                    walkingTarget = holdingTarget;
                    phase = Phase.ENTERING; timer = 0;
                }
                case ENTERING ->
                {
                    var counters = PublicStationGatesR44.reviewCounters(level, current.gate);
                    if (counters.opened() <= baseline.opened() || !player.getUUID().equals(counters.lastOpener())) return;
                    if (player.position().subtract(holdingTarget).horizontalDistanceSqr() > .0225) return;
                    if (!openValue(state).equals("open") || !openValue(mc.level.getBlockState(current.gate)).equals("open")) return;
                    require(leafOnly.stream().anyMatch(b -> b.intersects(player.getBoundingBox())), "Real player missed leaf sweep zone on entry");
                    row.addProperty("actual_client_keys_auto_open", true);
                    row.add("actual_server_entry_position", new Gson().toJsonTree(point(player.position())));
                    walkingTarget = null;
                    previousHoldPosition = player.position();
                    heldTicks = steadyTicks = 0;
                    phase = Phase.OCCUPIED; timer = 0;
                }
                case OCCUPIED ->
                {
                    require(openValue(state).equals("open"), "Native gate closed through an occupied real player");
                    require(leafOnly.stream().anyMatch(b -> b.intersects(player.getBoundingBox())), "Standing real player left native leaf sweep");
                    if (player.position().subtract(previousHoldPosition).horizontalDistanceSqr() < .00001) steadyTicks++;
                    else steadyTicks = 0;
                    previousHoldPosition = player.position();
                    heldTicks++;
                    var counters = PublicStationGatesR44.reviewCounters(level, current.gate);
                    if (heldTicks < 65 || steadyTicks < 50 || counters.held() <= baseline.held()
                            || !counters.heldActors().contains(player.getUUID())) return;
                    row.addProperty("actual_leaf_occupied_ticks", heldTicks);
                    row.addProperty("actual_stationary_leaf_ticks", steadyTicks);
                    row.addProperty("actual_native_scheduled_refused_close", true);
                    row.addProperty("actual_scheduled_held_counter_delta", counters.held() - baseline.held());
                    walkingTarget = current.finish;
                    phase = Phase.EXITING; timer = 0;
                }
                case EXITING ->
                {
                    if (player.position().subtract(current.finish).horizontalDistanceSqr() > .04
                            || mc.player.position().subtract(current.finish).horizontalDistanceSqr() > .09) return;
                    require(!leafOnly.stream().anyMatch(b -> b.inflate(.08).intersects(player.getBoundingBox())), "Actual exit remains in the native closing sweep");
                    require(player.onGround(), "Actual player exit has no grounded support");
                    row.addProperty("actual_client_keys_walked_out", true);
                    row.add("actual_server_exit_position", new Gson().toJsonTree(point(player.position())));
                    walkingTarget = null;
                    phase = Phase.RECLOSED; timer = 0;
                }
                case RECLOSED ->
                {
                    var counters = PublicStationGatesR44.reviewCounters(level, current.gate);
                    if (!openValue(state).equals("closed") || !openValue(mc.level.getBlockState(current.gate)).equals("closed")
                            || counters.closed() <= baseline.closed()) return;
                    var after = scores(player);
                    require(after.equals(caseScoresBefore), "MTR objective existence/player scores changed; free gate mutated balance/entry zone");
                    row.addProperty("actual_unoccupied_native_closed", true);
                    row.addProperty("actual_native_closed_counter_delta", counters.closed() - baseline.closed());
                    row.add("mtr_objectives_and_existing_scores_after", after);
                    row.addProperty("all_mtr_objectives_and_player_scores_unchanged", true);
                    row.addProperty("health_and_inventory_unchanged", true);
                    results.add(row.deepCopy());
                    ProjectSeele.LOGGER.info("R44 REAL CLIENT GATE PASS {}", current.id);
                    persist(world, false);
                    if (++index >= end) { restore(player); phase = Phase.RESTORING; timer = 0; }
                    else setup(level, player);
                }
                default -> { }
            }
        }
        catch (Exception error)
        {
            failure = error.toString();
            ProjectSeele.LOGGER.error("R44 real client public gate FAILED case=" + index + " phase=" + phase, error);
            if (row != null)
            {
                if (cases != null && index < cases.size()) trace(player, mc, cases.get(index));
                row.addProperty("failure", failure);
                row.add("actual_movement_first_error_trace", movementTrace.deepCopy());
                results.add(row.deepCopy());
            }
            if (initialized) restore(player);
            persist(world, true);
            finished = true;
        }
    }

    private static void setup(ServerLevel level, ServerPlayer player)
    {
        var current = cases.get(index);
        walkingTarget = null;
        while (movementTrace.size() > 0) movementTrace.remove(0);
        row = new JsonObject(); row.addProperty("case_index", index); row.addProperty("id", current.id);
        row.add("gate", new Gson().toJsonTree(new int[] {current.gate.getX(), current.gate.getY(), current.gate.getZ()}));
        row.add("outside_staging", new Gson().toJsonTree(point(current.start)));
        row.add("outside_finish", new Gson().toJsonTree(point(current.finish)));
        caseScoresBefore = scores(player);
        row.add("mtr_objectives_and_existing_scores_before", caseScoresBefore.deepCopy());
        trace(player, Minecraft.getInstance(), current);
        player.teleportTo(level, current.start.x, current.start.y, current.start.z, 0, 0);
        player.fallDistance = 0; player.setDeltaMovement(Vec3.ZERO);
        player.getAbilities().flying = false; player.onUpdateAbilities();
        phase = Phase.STAGING; timer = 0;
    }

    private static void trace(ServerPlayer player, Minecraft mc, Case current)
    {
        var sample = new JsonObject();sample.addProperty("age", age);sample.addProperty("phase", phase.toString());sample.addProperty("timer", timer);
        sample.add("server_position", new Gson().toJsonTree(point(player.position())));
        sample.add("server_velocity", new Gson().toJsonTree(point(player.getDeltaMovement())));
        sample.addProperty("server_grounded", player.onGround());sample.addProperty("server_horizontal_collision", player.horizontalCollision);
        sample.addProperty("server_vertical_collision", player.verticalCollision);
        sample.addProperty("server_flying", player.getAbilities().flying);sample.addProperty("server_no_physics", player.noPhysics);
        sample.addProperty("server_vehicle", player.getVehicle() == null ? "NONE" : player.getVehicle().getType().toString() + "/" + player.getVehicle().getUUID());
        sample.add("expected_staging", new Gson().toJsonTree(point(current.start)));
        if (walkingTarget != null) sample.add("walking_target", new Gson().toJsonTree(point(walkingTarget)));
        sample.add("server_feet_and_support", feet(player.level(), player.position()));
        sample.addProperty("server_gate_state", player.level().getBlockState(current.gate).toString());
        var ack = new JsonObject();
        for (String field : List.of("awaitingPositionFromClient", "awaitingTeleport", "awaitingTeleportTime", "lastGoodX", "lastGoodY", "lastGoodZ"))
        {
            try
            {
                var member = player.connection.getClass().getDeclaredField(field);member.setAccessible(true);
                var value = member.get(player.connection);ack.addProperty(field, value == null ? "NONE" : value.toString());
            }
            catch (ReflectiveOperationException error) { ack.addProperty(field, "UNAVAILABLE:" + error.getClass().getSimpleName()); }
        }
        sample.add("readonly_server_teleport_ack_fields", ack);
        if (mc.player != null)
        {
            sample.add("client_position", new Gson().toJsonTree(point(mc.player.position())));
            sample.add("client_velocity", new Gson().toJsonTree(point(mc.player.getDeltaMovement())));
            sample.addProperty("client_grounded", mc.player.onGround());sample.addProperty("client_horizontal_collision", mc.player.horizontalCollision);
            sample.addProperty("client_vertical_collision", mc.player.verticalCollision);
            sample.addProperty("client_vehicle", mc.player.getVehicle() == null ? "NONE" : mc.player.getVehicle().getType().toString() + "/" + mc.player.getVehicle().getUUID());
            sample.addProperty("client_key_up", mc.options.keyUp.isDown());sample.addProperty("client_forward_input", mc.player.input.forwardImpulse);
            sample.addProperty("client_left_input", mc.player.input.leftImpulse);
            if (mc.level != null)
            {
                sample.add("client_feet_and_support", feet(mc.level, mc.player.position()));
                sample.addProperty("client_gate_state", mc.level.getBlockState(current.gate).toString());
            }
        }
        movementTrace.add(sample);
        if (movementTrace.size() > 100) movementTrace.remove(0);
    }

    private static JsonArray feet(Level level, Vec3 position)
    {
        var result = new JsonArray();
        for (double dx : new double[] {-.29, 0, .29})
            for (double dz : new double[] {-.29, 0, .29})
            {
                BlockPos at = BlockPos.containing(position.add(dx, -.04, dz));var state = level.getBlockState(at);
                var row = new JsonObject();row.addProperty("position", at.toShortString());row.addProperty("state", state.toString());
                row.add("actual_collision", new Gson().toJsonTree(state.getCollisionShape(level, at).toAabbs().stream().map(PublicStationGateReviewR44::box).toList()));
                result.add(row);
            }
        return result;
    }

    private static List<Case> loadCases() throws Exception
    {
        String path = System.getProperty("projectseele.r44PublicGateCases", "");
        if (path.isBlank()) throw new IllegalArgumentException("Explicit current native gate case file required");
        var result = new ArrayList<Case>();
        for (var item : JsonParser.parseString(Files.readString(Path.of(path))).getAsJsonArray())
        {
            var r = item.getAsJsonObject();var q = r.getAsJsonArray("actualAutomaticGate");var points = r.getAsJsonArray("path");
            require(points.size() == 2 && q.size() == 3, "Two real cardinal outside gate endpoints required");
            var start = vector(points.get(0).getAsJsonArray());var finish = vector(points.get(1).getAsJsonArray());
            require(Math.abs(start.y - finish.y) < .001 && start.distanceToSqr(finish) >= 25, "Real outside buffers missing");
            result.add(new Case(r.get("id").getAsString(), new BlockPos(q.get(0).getAsInt(), q.get(1).getAsInt(), q.get(2).getAsInt()), start, finish));
        }
        require(result.size() == 160, "All80 gate cells in both directions required as denominator");
        return List.copyOf(result);
    }

    private static JsonObject scores(ServerPlayer player)
    {
        var scoreboard = player.server.getScoreboard();
        var names = new TreeSet<>(List.of("mtr_balance", "mtr_entry_zone_1", "mtr_entry_zone_2", "mtr_entry_zone_3"));
        for (var objective : scoreboard.getObjectives()) if (objective.getName().startsWith("mtr_")) names.add(objective.getName());
        var existing = scoreboard.getPlayerScores(player.getGameProfile().getName());
        var result = new JsonObject();
        for (var name : names)
        {
            var objective = scoreboard.getObjective(name);var row = new JsonObject();
            row.addProperty("objective_existed", objective != null);
            var score = objective == null ? null : existing.get(objective);
            row.addProperty("player_score_existed", score != null);
            if (score != null) row.addProperty("existing_player_score", score.getScore());
            result.add(name, row);
        }
        // Never use TicketSystem.getBalance or a creating scoreboard getter:
        // an initially absent objective/entry is itself part of the contract.
        return result;
    }

    private static void restore(ServerPlayer player)
    {
        walkingTarget = null;
        player.getInventory().load(originalInventory.copy());
        player.setHealth(originalHealth);
        player.setGameMode(originalMode);
        var level = player.server.getLevel(originalDimension);
        player.teleportTo(level, originalPosition.x, originalPosition.y, originalPosition.z, originalYaw, originalPitch);
        player.fallDistance = 0; player.setDeltaMovement(Vec3.ZERO);
        player.getAbilities().flying = originalFlying; player.onUpdateAbilities();
        if (originalVehicle != null)
        {
            var vehicle = level.getEntity(originalVehicle);
            if (vehicle != null) player.startRiding(vehicle, true);
        }
        player.inventoryMenu.broadcastChanges();
    }

    private static void complete(Path world, ServerPlayer player)
    {
        require(player.getInventory().save(new ListTag()).equals(originalInventory), "Final inventory not restored");
        require(Math.abs(player.getHealth() - originalHealth) < .001 && player.position().distanceToSqr(originalPosition) < .05,
                "Final health/position not restored");
        require(scores(player).equals(overallScoresBefore), "Overall MTR objectives/player scores changed");
        persist(world, true); finished = true;
    }

    private static void persist(Path world, boolean finalReceipt)
    {
        var report = new JsonObject();report.addProperty("real_client_keys", true);
        report.addProperty("gate_switch_helpers_called_by_test", false);
        report.addProperty("case_denominator", 160);
        report.addProperty("start", Integer.getInteger("projectseele.r44PublicGateStart", 0));report.addProperty("end", end);
        report.addProperty("case_index", index);report.addProperty("phase", phase.toString());report.addProperty("error", failure);
        report.addProperty("completed_cases", results.size());report.add("cases", results.deepCopy());
        report.addProperty("final", finalReceipt);report.addProperty("full160_current_process_pass", finalReceipt && failure.isBlank() && results.size() == 160);
        report.addProperty("cold_reload", "UNVERIFIED separate fresh-process rerun");
        report.addProperty("remaining", "All actual station entrances/train/APG/38 boarding interfaces/whole501 routes, artistic inspection, multiplayer and final delivered copy remain separate");
        try { Files.writeString(world.resolve("r44_public_gate_client_review.json"), new GsonBuilder().setPrettyPrinting().create().toJson(report)); }
        catch (Exception error) { throw new IllegalStateException("Gate client receipt could not be saved", error); }
    }

    private static BlockState openState(BlockState state, String value)
    {
        for (var property : state.getProperties()) if (property.getName().equals("open")) return withProperty(state, property, value);
        throw new IllegalStateException("Actual native gate lacks its open property");
    }
    private static <T extends Comparable<T>> BlockState withProperty(BlockState state, Property<T> property, String value)
    { return state.setValue(property, property.getValue(value).orElseThrow()); }
    private static String openValue(BlockState state)
    {
        for (var property : state.getProperties()) if (property.getName().equals("open")) return state.getValue(property).toString().toLowerCase(Locale.ROOT);
        return "NO_NATIVE_OPEN_PROPERTY";
    }
    private static Vec3 vector(JsonArray a) { return new Vec3(a.get(0).getAsDouble(), a.get(1).getAsDouble(), a.get(2).getAsDouble()); }
    private static double[] point(Vec3 p) { return new double[] {p.x, p.y, p.z}; }
    private static double[] box(AABB b) { return new double[] {b.minX, b.minY, b.minZ, b.maxX, b.maxY, b.maxZ}; }
    private static void require(boolean value, String reason) { if (!value) throw new IllegalStateException(reason); }
    private PublicStationGateReviewR44() { }
}

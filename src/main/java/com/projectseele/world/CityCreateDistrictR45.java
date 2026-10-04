package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.registry.ModBlocks;
import java.io.DataOutputStream;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.zip.Deflater;
import java.util.zip.GZIPOutputStream;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.NbtUtils;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.BlockEntity;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.dimension.DimensionType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * Opt-in whole-district transport candidate. Durable per-object inverse plus
 * compact ownership ledger; all motion is stock Create entity translation.
 * Installed topology, full96 membership and original actor identities are
 * prerequisites, never substituted with a shadow-probe success.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityCreateDistrictR45
{
    private static final String JOB = System.getProperty("projectseele.r45CityCreateDistrict", "");
    private static final int WORK_LIMIT = 4096;
    private static final long WORK_NANOS = 8_000_000L;
    private static final double SPEED = .25;
    private static final int RAMP_TICKS = 16;
    private static final TicketType<ChunkPos> TICKET = TicketType.create(
            "projectseele_city_rigid_r45", Comparator.comparingLong(ChunkPos::toLong), 0);
    private static Context active;
    private static boolean loaded;
    private CityCreateDistrictR45() {}

    public static boolean nativeReady(ServerLevel level, BlockPos origin)
    {
        return active != null && active.level == level && active.origin.equals(origin) && !active.loadingPlans;
    }

    /** Reuses the production complete-plan validator; native QA never substitutes collision bodies. */
    static void verifyNativeGroundContract2Plan(ServerLevel level, BlockPos origin, CompoundTag tag, int from, int to)
    {
        if (active == null || active.level != level || !active.origin.equals(origin) || from + to != 312
                || (from != 0 && from != 312) || tag.getInt("GroundContract") != 2
                || !tag.contains("GroundContract", Tag.TAG_INT) || !tag.contains("InitialWorldImageCount", Tag.TAG_INT)
                || !tag.contains("InitialWorldImageSHA256", Tag.TAG_STRING) || tag.getInt("Index") < 0 || tag.getInt("Index") >= 96
                || tag.getLong("Origin") != origin.asLong() || !active.world.equals(tag.getString("WorldUUID"))
                || !active.state.journey.equals(tag.getUUID("Journey")))
            throw new IllegalStateException("Native new-plan witness requires the actual complete GroundContract2 producer");
        var expected = active.towers.get(tag.getInt("Index"));
        Plan plan = Plan.load(tag);
        plan.validate(expected, from, to, UUID.nameUUIDFromBytes((active.world + "/" + origin + "/rigid-owner/" + expected.centre())
                .getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        plan.validateOperationSequence();
    }

    /** Bounded opt-in QA snapshot; the controller, ownership and stock collider readiness stay authoritative. */
    public static JsonObject nativeDiagnostics(ServerLevel level, BlockPos origin) throws Exception
    {
        if (active == null || active.level != level || !active.origin.equals(origin)) return null;
        Context c = active; c.observePhaseTiming(); long now = System.nanoTime();
        JsonObject report = new JsonObject(); report.addProperty("phase", c.state.phase);
        report.addProperty("journey_uuid", c.state.journey.toString()); report.addProperty("world_touched", c.state.worldTouched);
        report.addProperty("saved_plans", c.state.savedPlans); report.addProperty("created", c.state.created);
        report.addProperty("index", c.state.index); report.addProperty("cursor", c.state.cursor);
        report.addProperty("motion_tick", c.state.motionTick); report.addProperty("progress", c.state.progress);
        report.addProperty("loading_plans", c.loadingPlans); report.addProperty("occupied", c.occupied);
        report.add("exact_union", CityExactShapeUnionR45.diagnostics());
        report.addProperty("quality_hold", c.qualityHold); report.addProperty("current_phase_elapsed_ms", (now - c.phaseStartedNanos) / 1e6);
        JsonObject phases = new JsonObject(); c.phaseTotalsNanos.forEach((phase, nanos) -> phases.addProperty(phase, nanos / 1e6));
        report.add("completed_phase_ms", phases); report.addProperty("peak_controller_work_ms", c.peakWorkNanos / 1e6);
        report.addProperty("peak_motion_ms", c.peakMotionNanos / 1e6); report.addProperty("wal_preflight_ms", c.walPreflightNanos / 1e6);
        report.addProperty("wal_serialization_ms", c.walSerializationNanos / 1e6); report.addProperty("wal_io_ms", c.walIoNanos / 1e6);
        report.addProperty("journal_load_ms", c.journalLoadNanos / 1e6); report.addProperty("ledger_io_ms", c.ledgerIoNanos / 1e6);
        var runtime = Runtime.getRuntime(); report.addProperty("used_heap_bytes", runtime.totalMemory() - runtime.freeMemory());
        report.addProperty("committed_heap_bytes", runtime.totalMemory()); report.addProperty("max_heap_bytes", runtime.maxMemory());
        var pool = java.util.concurrent.ForkJoinPool.commonPool(); JsonObject threads = new JsonObject();
        threads.addProperty("parallelism", pool.getParallelism()); threads.addProperty("pool_size", pool.getPoolSize());
        threads.addProperty("active_threads", pool.getActiveThreadCount()); threads.addProperty("running_threads", pool.getRunningThreadCount());
        threads.addProperty("queued_tasks", pool.getQueuedTaskCount()); threads.addProperty("queued_submissions", pool.getQueuedSubmissionCount());
        threads.addProperty("steals", pool.getStealCount()); report.add("common_pool", threads);
        com.google.gson.JsonArray collectors = new com.google.gson.JsonArray();
        for (var gc : java.lang.management.ManagementFactory.getGarbageCollectorMXBeans())
        {
            JsonObject row = new JsonObject(); row.addProperty("name", gc.getName()); row.addProperty("collection_count", gc.getCollectionCount());
            row.addProperty("collection_time_ms", gc.getCollectionTime()); collectors.add(row);
        }
        report.add("garbage_collectors", collectors); com.google.gson.JsonArray owners = new com.google.gson.JsonArray();
        JsonObject reader = new JsonObject(); reader.addProperty("thread", c.journalReader.threadName());
        reader.addProperty("queued", c.journalReader.queuedTasks()); reader.addProperty("active", c.journalReader.activeTasks());
        reader.addProperty("pending", c.journalReader.pendingTasks()); reader.addProperty("closed", c.journalReader.isClosed());
        reader.addProperty("load_cursor", c.loadCursor); report.add("journal_reader", reader);
        report.addProperty("reconcile_fold_index", c.reconcileFoldIndex);
        report.addProperty("reconcile_fold_pending", c.pendingFold != null && !c.pendingFold.isDone());
        report.addProperty("reconcile_fold_retained_rows", c.currentReconcileFold == null ? 0 : c.currentReconcileFold.size());
        for (var spec : c.towers)
        {
            UUID owner = UUID.nameUUIDFromBytes((c.world + "/" + c.origin + "/rigid-owner/" + spec.centre())
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8));
            Entity entity = level.getEntity(owner); JsonObject row;
            if (entity == null) { row = new JsonObject(); row.addProperty("owner_uuid", owner.toString()); }
            else row = CityCreateBridgeR45.collisionDiagnostics(entity);
            row.addProperty("actual_loaded", entity != null); row.addProperty("index", spec.index()); owners.add(row);
        }
        report.add("actual_owner_colliders", owners); report.addProperty("read_only_diagnostics", true);
        report.addProperty("original_colliders_not_replaced", true); return report;
    }

    /** Legacy register/generator/maintenance hooks must gate on topology owns, not this JVM flag. */
    public static boolean owns(ServerLevel level, BlockPos origin)
    {
        return CityRigidTopologyR45.owns(level, origin);
    }

    /** Root-only native checkpoint; keeps the original owners and active transaction. */
    public static boolean holdNativeCheckpoint(ServerLevel level, BlockPos origin)
    {
        if (active == null || active.level != level || !active.origin.equals(origin) || !active.state.phase.equals("MOVE")) return false;
        try { active.qualityHold = true; active.stopEntities(); active.persist(); return true; }
        catch (Exception failure) { fault(failure); return false; }
    }

    public static Tokyo3RetractionDirector.RequestResult request(ServerLevel level, BlockPos origin, boolean retract)
    {
        if (!owns(level, origin)) return null;
        if (JOB.isEmpty() && !CityRigidTopologyR45.runtimeEnabled(level, origin))
            return new Tokyo3RetractionDirector.RequestResult(false, "R45 rigid-city candidate is disabled; installed topology inhibits legacy movement.");
        String activationFailure = CityExactShapeUnionR45.requiredActivationFailure();
        if (activationFailure != null)
        {
            ProjectSeele.LOGGER.error("R45 required release city union not ready; no context/WAL/new journey: {}", activationFailure);
            return new Tokyo3RetractionDirector.RequestResult(false, "整城升降校验尚未就绪，请完成当前安装版本的碰撞验证。");
        }
        try
        {
            Context context = context(level, origin);
            if (context.loadingPlans)
                return new Tokyo3RetractionDirector.RequestResult(false, "Complete original city journals are still being verified; retry after loading.");
            int target = retract ? 312 : 0;
            if (!context.state.phase.equals("IDLE"))
            {
                if (context.state.phase.equals("FAULT")) return new Tokyo3RetractionDirector.RequestResult(false, context.state.fault);
                context.state.queued = target;
                context.persist();
                return new Tokyo3RetractionDirector.RequestResult(true, "Rigid city reversal queued at the complete endpoint transaction boundary.");
            }
            if (context.state.depth == target)
            {
                if (context.state.queued >= 0 && context.state.queued != target)
                {
                    context.state.queued = -1; context.state.queueFault = ""; context.persist(); context.claim(false);
                    return new Tokyo3RetractionDirector.RequestResult(true, "Pending city trip cancelled; the successful complete endpoint remains unchanged.");
                }
                return new Tokyo3RetractionDirector.RequestResult(false, "Rigid city is already at this endpoint.");
            }
            if (!retract && CityBattlefieldR29.combatActive(level)) return new Tokyo3RetractionDirector.RequestResult(false, "City combat must finish before restoration.");
            context.state.queued = target; context.state.queueFault = ""; context.persist(); context.claim(true);
            return new Tokyo3RetractionDirector.RequestResult(true, "Whole city trip queued: wait for all original buildings/shafts to be resident and unoccupied before preparation.");
        }
        catch (Exception failure)
        {
            fault(failure);
            return new Tokyo3RetractionDirector.RequestResult(false, failure.toString());
        }
    }

    public static Tokyo3RetractionDirector.RequestResult requestCore(ServerLevel level, BlockPos core)
    {
        if (active == null)
        {
            BlockPos origin = IntegratedNervMapBuilder.tokyo3Origin(level);
            if (!owns(level, origin)) return null;
            try
            {
                for (var tower : CityRigidTopologyR45.towers(level, origin)) if (core.equals(tower.core()))
                    return request(level, origin, Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow().depth() == 0);
                return null;
            }
            catch (Exception failure) { return new Tokyo3RetractionDirector.RequestResult(false, failure.toString()); }
        }
        if (active.level != level) return null;
        for (var tower : active.towers) if (core.equals(tower.core()))
            return request(level, active.origin, (active.state.queued >= 0 ? active.state.queued : active.state.target) == 0);
        return null;
    }

    public static Tokyo3RetractionDirector.Status status(ServerLevel level, BlockPos origin)
    {
        if (!owns(level, origin)) return null;
        if (active == null) return new Tokyo3RetractionDirector.Status("RIGID_DISABLED", Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow().depth(),
                Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow().depth(), 312);
        if (active.loadingPlans) return new Tokyo3RetractionDirector.Status("RIGID_LOADING", active.state.depth, active.state.target, 312);
        if (active.state.phase.equals("IDLE") && active.state.queued >= 0 && active.state.queued != active.state.depth)
            return new Tokyo3RetractionDirector.Status("RIGID_QUEUED" + (!active.state.queueFault.isBlank() ? "_BLOCKED" : active.occupied ? "_OCCUPIED" : ""), active.state.depth, active.state.queued, 312);
        return new Tokyo3RetractionDirector.Status("RIGID_" + active.state.phase + (active.occupied ? "_OCCUPIED" : ""), active.state.depth, active.state.target, 312);
    }

    /** Explicit retry/rollback only; foreign source/destination NBT never gets overwritten. */
    public static Tokyo3RetractionDirector.RequestResult recover(ServerLevel level, BlockPos origin, boolean rollback)
    {
        if (!owns(level, origin) || JOB.isEmpty() && !CityRigidTopologyR45.runtimeEnabled(level, origin))
            return new Tokyo3RetractionDirector.RequestResult(false, "No enabled rigid-city owner.");
        try
        {
            Context context = context(level, origin);
            if (context.loadingPlans || context.state.worldTouched && context.plans.size() != context.towers.size())
                return new Tokyo3RetractionDirector.RequestResult(false, "Full96 durable inverse verification is incomplete; preserve journals and reload after explicit repair.");
            if (!context.state.phase.equals("FAULT")) return new Tokyo3RetractionDirector.RequestResult(false, "No held transaction fault.");
            if (!context.state.worldTouched)
            {
                context.state.phase = "IDLE"; context.state.target = context.state.depth;
                context.state.fault = ""; context.state.queued = -1; context.plans.clear(); context.preparing = null;
                context.persist(); context.claim(false);
                return new Tokyo3RetractionDirector.RequestResult(true, "Unplaced preparation cancelled; original city was untouched.");
            }
            context.state.rollback = rollback;
            context.clearReconcileFold();
            context.state.allowMissingRecovery = true;
            context.state.phase = !rollback && java.util.Set.of("OPEN", "DETACH", "SPAWN", "READY", "MOVE").contains(context.state.faultPhase)
                    ? "REPLAY_OPEN" : "RECONCILE";
            context.state.index = context.state.cursor = 0;
            context.state.fault = ""; context.persist(); context.claim(true);
            return new Tokyo3RetractionDirector.RequestResult(true, "Exact persisted inverse/final images retry armed; unexpected state/NBT remains fail-closed.");
        }
        catch (Exception failure) { fault(failure); return new Tokyo3RetractionDirector.RequestResult(false, failure.toString()); }
    }

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        try
        {
            if (!SeeleConfig.dynamicTokyo3RetractionEnabled())
            {
                if (active != null) active.stopEntities();
                return;
            }
            if (JOB.isEmpty())
            {
                ServerLevel level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
                if (level == null) return;
                BlockPos origin = IntegratedNervMapBuilder.tokyo3Origin(level);
                if (!CityRigidTopologyR45.runtimeEnabled(level, origin))
                {
                    if (active != null && active.level == level) active.stopEntities();
                    return;
                }
                Context service = context(level, origin); service.step(); return;
            }
            if (!loaded)
            {
                JsonObject input = JsonParser.parseString(Files.readString(Path.of(JOB))).getAsJsonObject();
                if (!input.get("enable_native_district").getAsBoolean()) throw new IllegalStateException("Explicit district test enable required");
                ServerLevel level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
                Path world = event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
                if (input.has("candidate_binding")) world = world.toRealPath();
                if (level != null && !CityAtomicCandidateBindingR45.admit(world, input)) return;
                if (level == null
                        || !world.equals(Path.of(input.get("world").getAsString()).toAbsolutePath().normalize())
                        || level.getSeed() != input.get("world_seed").getAsLong()
                        || !Tokyo3BuildingWorldIdentityR44.get(level).equals(input.get("world_id").getAsString()))
                    throw new IllegalStateException("Wrong complete city test world identity");
                active = context(level, IntegratedNervMapBuilder.tokyo3Origin(level));
                if (input.has("terrain_block_witness_output"))
                {
                    Path witness = Path.of(input.get("terrain_block_witness_output").getAsString()).toAbsolutePath().normalize();
                    if (witness.startsWith(world) || !witness.startsWith(Path.of("D:/eva/artifacts/rebuild_r45").toAbsolutePath().normalize()) || Files.exists(witness))
                        throw new IllegalStateException("First stock blocker requires a fresh non-world artifact path");
                    active.firstTerrainBlockedOutput = witness;
                }
                if (input.has("inflight_ready_resume"))
                {
                    JsonObject binding = JsonParser.parseString(Files.readString(Path.of(input.get("candidate_binding").getAsString()))).getAsJsonObject();
                    if (input.has("unplaced_fault_recovery") || input.get("request_on_start").getAsBoolean()
                            || !binding.has("qa_inflight_checkpoint") || !binding.getAsJsonObject("qa_inflight_checkpoint").equals(input.getAsJsonObject("inflight_ready_resume"))
                            || !active.state.journey.toString().equals(input.get("expected_original_journey").getAsString())
                            || !active.state.worldTouched || active.state.savedPlans != 96 || active.state.created != 96)
                        throw new IllegalStateException("In-flight READY resume must retain the original complete journey; no new request or unplaced recovery");
                }
                if (input.has("ground_compensated_move1_resume"))
                {
                    JsonObject binding = JsonParser.parseString(Files.readString(Path.of(input.get("candidate_binding").getAsString()))).getAsJsonObject();
                    if (input.has("unplaced_fault_recovery") || input.has("inflight_ready_resume") || input.has("inflight_move1_resume") || input.has("settled_endpoint_trip") || input.get("request_on_start").getAsBoolean()
                            || !binding.has("qa_ground_compensated_checkpoint") || !binding.getAsJsonObject("qa_ground_compensated_checkpoint").equals(input.getAsJsonObject("ground_compensated_move1_resume"))
                            || !active.state.journey.toString().equals(input.get("expected_original_journey").getAsString()) || active.state.motionTick != 1
                            || active.state.journeySourceDepth != 0 || active.state.journeyTargetDepth != 312 || !active.state.worldTouched || active.state.savedPlans != 96 || active.state.created != 96)
                        throw new IllegalStateException("Ground-compensated MOVE1 requires its own complete adjunct-WAL proof; no new request/recovery");
                }
                if (input.has("inflight_move1_resume"))
                {
                    JsonObject binding = JsonParser.parseString(Files.readString(Path.of(input.get("candidate_binding").getAsString()))).getAsJsonObject();
                    JsonObject moveProof=JsonParser.parseString(Files.readString(Path.of(input.getAsJsonObject("inflight_move1_resume").get("path").getAsString()))).getAsJsonObject();
                    int from=moveProof.get("source_depth").getAsInt(),to=moveProof.get("target_depth").getAsInt(),motion=moveProof.get("MotionTick").getAsInt();
                    if ((from!=0 && from!=312) || to!=312-from || motion<1 || motion>=724
                            || input.has("unplaced_fault_recovery") || input.has("inflight_ready_resume") || input.has("settled_endpoint_trip") || input.get("request_on_start").getAsBoolean()
                            || !binding.has("qa_inflight_move1_checkpoint") || !binding.getAsJsonObject("qa_inflight_move1_checkpoint").equals(input.getAsJsonObject("inflight_move1_resume"))
                            || !active.state.journey.toString().equals(input.get("expected_original_journey").getAsString())
                            || active.state.motionTick != motion || active.state.journeySourceDepth != from || active.state.journeyTargetDepth != to
                            || !active.state.worldTouched || active.state.savedPlans != 96 || active.state.created != 96)
                        throw new IllegalStateException("Exact original downward MOVE1 resume requires its own proof; no READY/new request/recovery substitution");
                }
                if (input.has("settled_endpoint_trip"))
                {
                    JsonObject binding = JsonParser.parseString(Files.readString(Path.of(input.get("candidate_binding").getAsString()))).getAsJsonObject();
                    JsonObject settledProof = JsonParser.parseString(Files.readString(Path.of(input.getAsJsonObject("settled_endpoint_trip").get("path").getAsString()))).getAsJsonObject();
                    int endpoint = settledProof.get("depth").getAsInt();
                    boolean relogin = input.has("settled_relogin") && input.get("settled_relogin").getAsBoolean();
                    boolean deferred = input.has("await_collider_oracle") && input.get("await_collider_oracle").getAsBoolean();
                    if ((endpoint != 0 && endpoint != 312) || input.has("unplaced_fault_recovery") || input.has("inflight_ready_resume")
                            || input.has("inflight_move1_resume") || input.has("ground_compensated_move1_resume")
                            || !binding.has("qa_settled_checkpoint") || !binding.getAsJsonObject("qa_settled_checkpoint").equals(input.getAsJsonObject("settled_endpoint_trip"))
                            || relogin && deferred || input.get("request_on_start").getAsBoolean() == (relogin || deferred)
                            || deferred && endpoint != 312
                            || !relogin && input.get("retract").getAsBoolean() != (endpoint == 0)
                            || !active.state.phase.equals("IDLE") || active.state.depth != endpoint || active.state.target != endpoint
                            || !active.state.journey.toString().equals(input.get("expected_previous_journey").getAsString()))
                        throw new IllegalStateException("Settled job requires its exact finite endpoint proof and either a fresh directional request or read-only relogin");
                }
                if (input.has("expected_source_endpoint") && !input.get("expected_source_endpoint").isJsonNull()
                        && active.state.depth != input.get("expected_source_endpoint").getAsInt())
                    throw new IllegalStateException("Actual complete city source endpoint differs from the explicit native job");
                if (input.has("unplaced_fault_recovery"))
                {
                    CityAtomicCandidateBindingR45.verifyUnplacedFault(world, input.getAsJsonObject("unplaced_fault_recovery"), active.world);
                    var recovery = recover(level, active.origin, false);
                    if (!recovery.accepted()) throw new IllegalStateException("Explicit unplaced city recovery rejected: " + recovery.message());
                    ProjectSeele.LOGGER.info("R45 explicit unplaced city preparation recovery: {}", recovery.message());
                }
                loaded = true;
                if (input.get("request_on_start").getAsBoolean() && active.state.phase.equals("IDLE"))
                    request(level, active.origin, input.get("retract").getAsBoolean());
            }
            if (active != null) active.step();
        }
        catch (Exception failure) { loaded = true; fault(failure); }
    }

    @SubscribeEvent(priority = EventPriority.HIGHEST)
    public static void levelEnd(TickEvent.LevelTickEvent event)
    {
        if (active == null || event.level != active.level || event.phase != TickEvent.Phase.END || !active.state.phase.equals("MOVE")) return;
        if (active.qualityHold) return;
        if (!SeeleConfig.dynamicTokyo3RetractionEnabled()) return;
        if (JOB.isEmpty() && !CityRigidTopologyR45.runtimeEnabled(active.level, active.origin)) return;
        try
        {
            long began = System.nanoTime(); active.move();
            active.peakMotionNanos = Math.max(active.peakMotionNanos, System.nanoTime() - began);
        }
        catch (Exception failure) { fault(failure); }
    }

    @SubscribeEvent
    public static void stopping(ServerStoppingEvent event)
    {
        if (active == null) return;
        try { active.stopEntities(); active.persist(); }
        catch (Exception failure) { ProjectSeele.LOGGER.error("Rigid city stop checkpoint failed; retain durable inverse", failure); }
        finally { active.clearReconcileFold(); active.journalReader.close(); }
        active.claim(false);
        active = null; loaded = false; CityRigidTopologyR45.clearRuntimeCache();
    }

    private static Context context(ServerLevel level, BlockPos origin) throws Exception
    {
        if (active == null) active = new Context(level, origin);
        if (active.level != level || !active.origin.equals(origin)) throw new IllegalStateException("A second city world cannot acquire this test controller");
        return active;
    }

    private static void fault(Exception failure)
    {
        ProjectSeele.LOGGER.error("R45 whole-city cargo fault; original UUIDs/inverse retained", failure);
        if (active == null) return;
        active.clearReconcileFold();
        active.state.faultPhase = active.state.phase; active.state.phase = "FAULT"; active.state.fault = failure.toString();
        try { active.stopEntities(); active.persist(); }
        catch (Exception secondary) { failure.addSuppressed(secondary); }
        active.claim(false);
    }

    private static final class Context
    {
        final ServerLevel level;
        final BlockPos origin;
        final String world;
        final Path file, directory;
        final List<CityRigidTopologyR45.Tower> towers;
        final List<Plan> plans = new ArrayList<>();
        final Map<Integer, Entity> entities = new HashMap<>();
        final java.util.Set<UUID> ownerIds = new java.util.HashSet<>();
        final List<ChunkPos> chunks = new ArrayList<>();
        State state;
        Plan preparing;
        CompletableFuture<String> pending;
        CompletableFuture<Plan> pendingRead;
        final CityJournalReadExecutorR45 journalReader = new CityJournalReadExecutorR45();
        CompletableFuture<List<Fold>> pendingFold;
        List<Fold> currentReconcileFold;
        int reconcileFoldIndex = -1;
        Path firstTerrainBlockedOutput;
        boolean firstTerrainBlockedRecorded;
        int prepCursor, prepStage;
        java.security.MessageDigest initialImageDigest;
        int loadCursor, assemblyLimit, spawnLimit;
        int claimed;
        boolean occupied, qualityHold, loadingPlans, recoveredOwnersStopped;
        long lastPersistTick = Long.MIN_VALUE;
        String lastPersistPhase = "";
        long actualWrites, peakWorkNanos, peakMotionNanos, endpointFlushNanos;
        long walPreflightNanos, walSerializationNanos, walIoNanos, journalLoadNanos, ledgerIoNanos;
        final Map<String, Long> phaseTotalsNanos = new LinkedHashMap<>();
        String observedPhase = "";
        long phaseStartedNanos = System.nanoTime();

        Context(ServerLevel level, BlockPos origin) throws Exception
        {
            this.level = level; this.origin = origin; world = Tokyo3BuildingWorldIdentityR44.get(level);
            towers = CityRigidTopologyR45.towers(level, origin);
            java.util.Set<Long> unique = new java.util.LinkedHashSet<>();
            for (var spec : towers)
            {
                ownerIds.add(UUID.nameUUIDFromBytes((world + "/" + origin + "/rigid-owner/" + spec.centre())
                        .getBytes(java.nio.charset.StandardCharsets.UTF_8)));
                AABB bounds = route(spec);
                for (int x = Math.floorDiv((int) bounds.minX, 16); x <= Math.floorDiv((int) bounds.maxX, 16); x++)
                    for (int z = Math.floorDiv((int) bounds.minZ, 16); z <= Math.floorDiv((int) bounds.maxZ, 16); z++) unique.add(ChunkPos.asLong(x, z));
            }
            for (long key : unique) chunks.add(new ChunkPos(key));
            directory = DimensionType.getStorageFolder(level.dimension(), level.getServer().getWorldPath(LevelResource.ROOT)).resolve("data");
            file = directory.resolve("projectseele_city_rigid_control_r45_" + Long.toUnsignedString(origin.asLong()) + ".dat");
            if (Files.exists(file))
            {
                CompoundTag tag = NbtIo.readCompressed(file.toFile()).getCompound("data");
                if (tag.getInt("Version") != 1 || !world.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != origin.asLong())
                    throw new IllegalStateException("Foreign/unknown city WAL authority");
                state = State.load(tag);
                state.validate(towers.size());
                if (!state.phase.equals("IDLE"))
                {
                    // Incomplete preparation had no world placements. Restart
                    // its exact observation instead of trusting a lost scratch.
                    if (state.phase.equals("PREPARE") || state.phase.equals("WAL_WAIT"))
                    { plans.clear(); state.savedPlans = 0; state.planHashes.clear(); state.index = 0; state.phase = "PREPARE"; }
                    else if (state.phase.equals("FAULT") && !state.worldTouched)
                    {
                        // An explicit reviewed recovery may cancel an unplaced
                        // journey. Ordinary loading must retain its original
                        // durable journal ledger until that authorization.
                    }
                    else
                    {
                        loadingPlans = state.savedPlans > 0;
                        if (state.worldTouched && !state.phase.equals("COMMIT") && !state.phase.equals("FAULT"))
                        {
                            state.phase = java.util.Set.of("OPEN", "DETACH", "REPLAY_OPEN", "REPLAY_DETACH", "SPAWN", "READY", "MOVE").contains(state.phase) ? "REPLAY_OPEN" : "RECONCILE";
                            state.index = state.cursor = 0;
                        }
                    }
                }
            }
            else
            {
                var legacy = Tokyo3RetractionSavedData.get(level).get(origin).orElseThrow();
                if (legacy.depth() != legacy.targetDepth() || legacy.cursor() != 0 || legacy.voxelCursor() != 0
                        || legacy.depth() != 0 && legacy.depth() != 312) throw new IllegalStateException("Finish legacy transaction before rigid topology handoff");
                state = new State(); state.depth = state.target = legacy.depth();
                state.journeySourceDepth = state.journeyTargetDepth = legacy.depth(); persist();
            }
            if (!state.phase.equals("IDLE") && !state.phase.equals("FAULT")) claim(true);
        }

        Path planPath(int index)
        {
            return directory.resolve("city_rigid_journal_r45").resolve(state.journey.toString()).resolve(index + ".dat");
        }

        void begin(int target) throws Exception
        {
            String activationFailure = CityExactShapeUnionR45.requiredActivationFailure();
            if (activationFailure != null) throw new IllegalStateException("Required release union not ready before next journey: " + activationFailure);
            clearReconcileFold();
            if (pending != null && !pending.isDone()) throw new IllegalStateException("The cancelled unplaced journal is still draining; original city remains untouched");
            pending = null;
            assemblyLimit = CityCreateBridgeR45.backendBlockLimit();
            spawnLimit = CityCreateBridgeR45.backendSpawnLimit();
            if (occupied()) throw new IllegalStateException("Clear full buildings/roofs/shaft envelopes before detachment");
            UUID nextJourney;
            do { nextJourney = UUID.randomUUID(); }
            while (Files.exists(directory.resolve("city_rigid_journal_r45").resolve(nextJourney.toString())));
            state.journey = nextJourney; state.target = target; state.queued = -1;
            state.queueFault = "";
            state.journeySourceDepth = state.depth; state.journeyTargetDepth = target;
            state.phase = "PREPARE"; state.index = state.cursor = state.savedPlans = 0;
            state.planHashes.clear();
            state.progress = 0; state.rollback = false; plans.clear(); preparing = null;
            state.motionTick = 0;
            state.worldTouched = false; state.created = 0; state.allowMissingRecovery = false;
            prepCursor = prepStage = 0; actualWrites = 0; persist(); claim(true);
        }

        void step() throws Exception
        {
            observePhaseTiming();
            if (loadingPlans)
            {
                level.resetEmptyTime(); claim(true);
                if (resident())
                {
                    if (!recoveredOwnersStopped)
                    {
                        for (var spec : towers) for (Entity actor : level.getEntities((Entity) null, route(spec), e -> e.getTags().contains(ownerTag())))
                        {
                            if (!ownsActor(actor))
                                throw new IllegalStateException("Foreign actor owns a recovered city tag");
                            CityCreateBridgeR45.stop(actor);
                        }
                        recoveredOwnersStopped = true;
                    }
                    loadPlan();
                }
                return;
            }
            if (state.phase.equals("IDLE"))
            {
                if (state.queued < 0 || state.queued == state.depth || !state.queueFault.isBlank()) return;
                level.resetEmptyTime(); claim(true); if (!resident()) return;
                occupied = occupied(); if (occupied) return;
                try { begin(state.queued); }
                catch (Exception failure)
                {
                    // A preflight failure before begin changes the journey is
                    // a blocked next trip, not failure of the committed city.
                    // Once PREPARE begins, preserve the ordinary FAULT/WAL path.
                    if (!state.phase.equals("IDLE")) throw failure;
                    state.queueFault = failure.toString(); persist(); claim(false);
                    ProjectSeele.LOGGER.error("R45 next city trip blocked before preparation; committed endpoint and pending target preserved", failure);
                }
                return;
            }
            if (state.phase.equals("FAULT")) return;
            if (qualityHold) return;
            level.resetEmptyTime();
            claim(true);
            if (!resident()) return;
            // MOVE owns its occupancy check immediately before translation.
            occupied = !state.phase.equals("MOVE") && !state.phase.equals("FLUSH") && !state.phase.equals("COMMIT") && occupied();
            if (occupied) { stopEntities(); return; }
            long start = System.nanoTime();
            switch (state.phase)
            {
                case "PREPARE" -> prepare(start);
                case "WAL_WAIT" ->
                {
                    if (!pending.isDone()) return;
                    String digest = pending.join(); pending = null; state.planHashes.add(digest);
                    state.savedPlans = plans.size(); state.index++;
                    state.phase = state.index == towers.size() ? "OPEN" : "PREPARE";
                    if (state.phase.equals("OPEN")) state.index = state.cursor = 0;
                    persist();
                }
                case "OPEN" -> applyStage(0, "DETACH", start);
                case "DETACH" -> applyStage(1, "SPAWN", start);
                case "REPLAY_OPEN" -> applyStage(0, "REPLAY_DETACH", start);
                case "REPLAY_DETACH" -> applyStage(1, "SPAWN", start);
                case "SPAWN" -> spawn();
                case "READY" ->
                {
                    for (Entity entity : entities.values()) if (!CityCreateBridgeR45.collisionReady(entity)) return;
                    state.phase = "MOVE"; persist();
                }
                case "MOVE" -> { if (level.getGameTime() % 20 == 0) persist(); }
                case "PLACE" -> applyStage(2, "COVER", start);
                case "COVER" -> applyStage(3, "FLUSH", start);
                case "RECONCILE" -> reconcile(start);
                case "FLUSH" ->
                {
                    // One explicit native persistence barrier per journey,
                    // never once per tower/layer. Its measured cost is separate
                    // from the 8ms placement/capture budget, not hidden as zero.
                    syncEndpointMetadata();
                    long before = System.nanoTime(); level.save(null, true, false);
                    endpointFlushNanos += System.nanoTime() - before;
                    state.phase = "COMMIT"; persist();
                }
                case "COMMIT" -> commit();
                default -> throw new IllegalStateException("Unknown persistent city phase " + state.phase);
            }
            peakWorkNanos = Math.max(peakWorkNanos, System.nanoTime() - start);
        }

        void loadPlan() throws Exception
        {
            if (pendingRead == null)
            {
                int index = loadCursor; Path source = planPath(index);
                UUID journey = state.journey; int from = state.journeySourceDepth, to = state.journeyTargetDepth;
                String expectedDigest = state.planHashes.get(index);
                CityRigidTopologyR45.Tower spec = towers.get(index);
                pendingRead = journalReader.submit(() ->
                {
                    long began = System.nanoTime();
                    try
                    {
                        if (!expectedDigest.equals(digest(source))) throw new IllegalStateException("Complete original journal bytes changed at object " + index);
                        CompoundTag tag = NbtIo.readCompressed(source.toFile());
                        if (!expectedDigest.equals(digest(source))) throw new IllegalStateException("Original journal changed while loading at object " + index);
                        if (!world.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != origin.asLong()
                                || !journey.equals(tag.getUUID("Journey")) || tag.getInt("Index") != index)
                            throw new IllegalStateException("Foreign per-object inverse journal");
                        Plan plan = Plan.load(tag);
                        plan.validate(spec, from, to, UUID.nameUUIDFromBytes((world + "/" + origin + "/rigid-owner/" + spec.centre())
                                .getBytes(java.nio.charset.StandardCharsets.UTF_8)));
                        plan.cargo(); plan.validateOperationSequence(); // Pure immutable checks, no whole-city Fold retention.
                        return plan;
                    }
                    catch (Exception failure) { throw new java.util.concurrent.CompletionException(failure); }
                    finally { journalLoadNanos += System.nanoTime() - began; }
                });
                return;
            }
            if (!pendingRead.isDone()) return;
            plans.add(pendingRead.join()); pendingRead = null;
            if (++loadCursor == state.savedPlans)
            {
                // Publish the replay phase only after every complete inverse
                // has been decoded and checked. Native observers must wait too.
                persist(); loadingPlans = false;
            }
        }

        void prepare(long began) throws Exception
        {
            if (assemblyLimit <= 0)
            {
                assemblyLimit = CityCreateBridgeR45.backendBlockLimit(); spawnLimit = CityCreateBridgeR45.backendSpawnLimit();
            }
            if (preparing == null)
            {
                var spec = towers.get(state.index);
                for (long anchor : spec.fixedAnchors())
                {
                    BlockPos pos = BlockPos.of(anchor);
                    if (!level.getBlockState(pos).equals(Blocks.IRON_BLOCK.defaultBlockState()) || level.getBlockEntity(pos) != null)
                        throw new IllegalStateException("Complete relocated anchor state/NBT changed at " + pos);
                }
                if (spec.core() != null && !level.getBlockState(spec.core()).is(ModBlocks.RETRACTABLE_BUILDING_CORE.get()))
                    throw new IllegalStateException("Fixed controller ownership changed");
                preparing = new Plan(spec, state.depth, state.target,
                        UUID.nameUUIDFromBytes((world + "/" + origin + "/rigid-owner/" + spec.centre()).getBytes(java.nio.charset.StandardCharsets.UTF_8)));
                prepCursor = prepStage = 0;
            }
            var spec = preparing.spec;
            int width = spec.maxX() - spec.minX() + 1, depth = spec.maxZ() - spec.minZ() + 1;
            int body = width * depth * (spec.height() + 4), ground = width * depth;
            int scanned = 0;
            while (scanned++ < WORK_LIMIT && System.nanoTime() - began < WORK_NANOS)
            {
                if (prepStage == 3)
                {
                    List<Fold> initialImages = preparing.fold();
                    if (prepCursor < initialImages.size())
                    {
                        Fold row = initialImages.get(prepCursor++); Image actual = Image.read(level, row.pos);
                        if (!actual.equals(row.initial)) throw new IllegalStateException("Complete initial source/destination/Ground image changed before immutable WAL at " + row.pos);
                        CompoundTag image = actual.save(); image.putLong("Pos", row.pos.asLong());
                        try (var sink = new DataOutputStream(new java.security.DigestOutputStream(java.io.OutputStream.nullOutputStream(), initialImageDigest)))
                        { NbtIo.write(image, sink); }
                        continue;
                    }
                    preparing.initialWorldImageCount = initialImages.size();
                    preparing.initialWorldImageSHA256 = java.util.HexFormat.of().formatHex(initialImageDigest.digest());
                    preparing.folded = null; initialImageDigest = null; prepStage = 4;
                }
                if (prepStage < 2)
                {
                    if (prepCursor >= body) { prepStage++; prepCursor = 0; continue; }
                    int y = prepCursor / (width * depth), plane = prepCursor++ % (width * depth);
                    BlockPos local = new BlockPos(spec.minX() + plane / depth, y, spec.minZ() + plane % depth);
                    BlockPos source = local.offset(spec.centre().getX(), preparing.sourceY, spec.centre().getZ());
                    BlockPos target = local.offset(spec.centre().getX(), preparing.targetY, spec.centre().getZ());
                    if (prepStage == 0)
                    {
                        Image image = Image.read(level, source);
                        if (!image.state.isAir() || image.nbt != null)
                        {
                            preparing.cells.put(local.asLong(), image);
                            preparing.detach.add(new Write(source, image, Image.AIR));
                        }
                    }
                    else
                    {
                        Image actual = Image.read(level, target);
                        boolean ownCover = target.getY() == 80 && state.target == 0
                                && actual.equals(new Image(hatch(spec, local.getX(), local.getZ()), null));
                        if (!actual.state.isAir() && !ownCover || actual.nbt != null)
                            throw new IllegalStateException("Unowned destination/shaft obstruction at " + target + " " + actual.state);
                        Image cargo = preparing.cells.get(local.asLong());
                        if (cargo != null) preparing.place.add(new Write(target, ownCover ? Image.AIR : actual, cargo.at(target)));
                    }
                }
                else
                {
                    if (prepCursor >= ground)
                    {
                        if (prepStage == 2)
                        {
                            initialImageDigest = java.security.MessageDigest.getInstance("SHA-256");
                            prepStage = 3; prepCursor = 0; continue;
                        }
                        if (preparing.cells.isEmpty()) throw new IllegalStateException("Empty damaged building requires explicit retirement, never synthetic cargo");
                        plans.add(preparing);
                        Plan immutablePlan = preparing;
                        UUID journey = state.journey;
                        Path destination = planPath(state.index);
                        int capturedAssemblyLimit = assemblyLimit, capturedSpawnLimit = spawnLimit;
                        pending = CompletableFuture.supplyAsync(() ->
                        {
                            try
                            {
                                // The observed plan and its copied BE tags are
                                // immutable until this future completes. Build
                                // and compress its WAL off the server thread;
                                // no placement starts before all96 futures pass.
                                long before = System.nanoTime();
                                immutablePlan.validate(spec, immutablePlan.sourceY == spec.centre().getY() ? 0 : 312,
                                        immutablePlan.targetY == spec.centre().getY() ? 0 : 312, immutablePlan.owner);
                                CityCreateBridgeR45.preflight(immutablePlan.cargo(),
                                        new BlockPos(spec.centre().getX(), immutablePlan.sourceY, spec.centre().getZ()),
                                        capturedAssemblyLimit, capturedSpawnLimit);
                                walPreflightNanos += System.nanoTime() - before;
                                immutablePlan.validateOperationSequence();
                                before = System.nanoTime(); CompoundTag immutable = immutablePlan.save();
                                immutable.putString("WorldUUID", world); immutable.putLong("Origin", origin.asLong());
                                immutable.putUUID("Journey", journey); walSerializationNanos += System.nanoTime() - before;
                                before = System.nanoTime(); atomic(destination, immutable); walIoNanos += System.nanoTime() - before;
                                return digest(destination);
                            }
                            catch (IOException failure) { throw new java.util.concurrent.CompletionException(failure); }
                        });
                        preparing = null; state.phase = "WAL_WAIT"; persist(); return;
                    }
                    int plane = prepCursor++;
                    BlockPos pos = new BlockPos(spec.centre().getX() + spec.minX() + plane / depth, 80,
                            spec.centre().getZ() + spec.minZ() + plane % depth);
                    Image actual = Image.read(level, pos);
                    Image cover = new Image(hatch(spec, pos.getX() - spec.centre().getX(), pos.getZ() - spec.centre().getZ()), null);
                    if (state.target == 0 || preparing.sourceY > 80 && preparing.targetY < 80)
                    {
                        if (!actual.equals(cover)) throw new IllegalStateException("Street hatch state/NBT changed without ownership migration at " + pos);
                        preparing.open.add(new Write(pos, actual, Image.AIR));
                        // Imported bodies park with their real floor at81.
                        // Restore the80 support/hatch after ascent as well;
                        // generated bodies park their complete floor at80.
                        if (state.target == 312 || spec.index() >= 93) preparing.cover.add(new Write(pos, Image.AIR, cover));
                    }
                    else preparing.cover.add(new Write(pos, Image.AIR, cover));
                }
            }
        }

        void applyStage(int stage, String next, long began) throws Exception
        {
            if (!state.worldTouched) { state.worldTouched = true; persist(); }
            int writes = 0, scanned = 0;
            while (state.index < plans.size() && writes < WORK_LIMIT && scanned < WORK_LIMIT && System.nanoTime() - began < WORK_NANOS)
            {
                Plan plan = plans.get(state.index); List<Write> operations = plan.operations(stage);
                if (state.cursor >= operations.size()) { state.index++; state.cursor = 0; continue; }
                Write operation = operations.get(state.cursor++); scanned++;
                Image actual = Image.read(level, operation.pos);
                if (actual.equals(operation.after)) continue;
                if (!actual.equals(operation.before)) throw new IllegalStateException("Exact state/fullNBT precondition changed at " + operation.pos);
                operation.after.write(level, operation.pos); writes++; actualWrites++;
            }
            if (state.index == plans.size())
            {
                state.phase = next; state.index = state.cursor = 0;
                if (next.equals("FLUSH"))
                {
                    for (var entry : entities.entrySet()) CityCreateBridgeR45.verify(entry.getValue(), plans.get(entry.getKey()).cargo());
                    for (Entity entity : entities.values()) entity.discard();
                    entities.clear();
                }
            }
            checkpoint();
        }

        void spawn() throws Exception
        {
            if (state.index >= plans.size()) { state.phase = "READY"; state.index = 0; persist(); return; }
            Plan plan = plans.get(state.index);
            Entity entity = level.getEntity(plan.owner);
            if (entity != null)
            {
                if (!entity.getTags().contains(ownerTag()) || !entity.getPersistentData().getUUID("R45CityJourney").equals(state.journey))
                    throw new IllegalStateException("Moving building UUID resolves to a foreign owner");
                CityCreateBridgeR45.verify(entity, plan.cargo());
            }
            else
            {
                if (state.index < state.created && !state.allowMissingRecovery)
                    throw new IllegalStateException("Previously spawned owner UUID missing after entities-loaded barrier; explicit inverse/owner recovery required");
                entity = CityCreateBridgeR45.create(level, plan.cargo(), new BlockPos(plan.spec.centre().getX(), plan.sourceY, plan.spec.centre().getZ()), plan.owner);
                entity.addTag(ownerTag()); entity.getPersistentData().putUUID("R45CityJourney", state.journey);
                if (!level.addFreshEntity(entity)) throw new IllegalStateException("Persistent cargo owner insertion rejected");
            }
            double offset = Math.abs(plan.targetY - plan.sourceY) * fraction(state.motionTick, duration(plan));
            Vec3 checkpointPose = new Vec3(plan.spec.centre().getX() + .5,
                    plan.sourceY + Math.signum(plan.targetY - plan.sourceY) * offset, plan.spec.centre().getZ() + .5);
            if (entity.position().distanceTo(checkpointPose) > 1e-5)
            {
                if (state.index < state.created && !state.allowMissingRecovery)
                    throw new IllegalStateException("Persisted entity/control pose epochs disagree; no occupant teleport, explicit recovery required");
                // Full route occupancy and source inverse have already been
                // checked. Rehydrate only the exact persisted moving owner.
                entity.setPos(checkpointPose.x, checkpointPose.y, checkpointPose.z);
                entity.xo = entity.getX(); entity.yo = entity.getY(); entity.zo = entity.getZ();
            }
            entities.put(state.index, entity); state.index++; state.created = Math.max(state.created, state.index); persist();
        }

        void move() throws Exception
        {
            occupied = occupied();
            if (occupied) { stopEntities(); return; }
            int maximum = 0;
            for (Plan plan : plans) maximum = Math.max(maximum, duration(plan));
            int nextTick = Math.min(maximum, state.motionTick + 1);
            Map<Integer, Vec3> targets = new HashMap<>();
            for (var entry : entities.entrySet())
            {
                Plan plan = plans.get(entry.getKey()); Entity entity = entry.getValue();
                if (!entity.isAlive() || entity.getVehicle() != null) throw new IllegalStateException("Original rigid cargo owner disappeared/mounted");
                double delta = Math.abs(plan.targetY - plan.sourceY) * fraction(nextTick, duration(plan));
                double y = plan.sourceY + Math.signum(plan.targetY - plan.sourceY) * delta;
                Vec3 target = new Vec3(plan.spec.centre().getX() + .5, y, plan.spec.centre().getZ() + .5);
                if (entity.position().distanceTo(target) > .500001) throw new IllegalStateException("Cargo/control pose epochs disagree; explicit recovery required");
                if (CityCreateBridgeR45.blockedByTerrain(entity, target, Math.abs(y - plan.targetY) < 1e-6))
                { recordFirstTerrainBlock(plan, entity, target, nextTick); occupied = true; stopEntities(); return; }
                targets.put(entry.getKey(), target);
            }
            state.motionTick = nextTick;
            state.progress = fraction(nextTick, maximum);
            for (var entry : targets.entrySet()) CityCreateBridgeR45.move(entities.get(entry.getKey()), entry.getValue());
            if (nextTick >= maximum) { state.phase = "PLACE"; state.index = state.cursor = 0; stopEntities(); persist(); }
        }

        void recordFirstTerrainBlock(Plan plan, Entity entity, Vec3 target, int requestedTick) throws Exception
        {
            if (firstTerrainBlockedOutput == null || firstTerrainBlockedRecorded) return;
            JsonObject fact = CityCreateBridgeR45.stockBlockedFact(entity, target);
            fact.addProperty("schema", "projectseele.city-first-actual-stock-blocked-fact-r45.v1");
            fact.addProperty("journey_uuid", state.journey.toString()); fact.addProperty("index", plan.spec.index());
            fact.addProperty("saved_motion_tick", state.motionTick); fact.addProperty("requested_motion_tick", requestedTick);
            fact.addProperty("source_y", plan.sourceY); fact.addProperty("target_y", plan.targetY);
            Files.createDirectories(firstTerrainBlockedOutput.getParent());
            Files.writeString(firstTerrainBlockedOutput, fact.toString(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            firstTerrainBlockedRecorded = true; // The original boolean/pose/motion fact survives any later localization failure.
            try
            {
                JsonObject localization = CityCreateBridgeR45.locateStockWorldBlocker(entity, target);
                localization.addProperty("journey_uuid", state.journey.toString()); localization.addProperty("index", plan.spec.index());
                Path path = firstTerrainBlockedOutput.resolveSibling(firstTerrainBlockedOutput.getFileName() + ".faces.json");
                Files.writeString(path, localization.toString(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            }
            catch (Exception failure)
            {
                JsonObject error = new JsonObject(); error.addProperty("error", failure.toString()); error.addProperty("blocker_localization_complete", false);
                Path path = firstTerrainBlockedOutput.resolveSibling(firstTerrainBlockedOutput.getFileName() + ".localization_error.json");
                Files.writeString(path, error.toString(), StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            }
        }

        void reconcile(long began) throws Exception
        {
            if (plans.size() != towers.size()) throw new IllegalStateException("Incomplete durable inverse set; no world placements allowed");
            // Recovery collapses the ordered open/detach/place/cover journal
            // to per-coordinate initial/final states. Repeated ground cells
            // may already have a later committed cover, not just AIR.
            int changed = 0, scanned = 0;
            while (state.index < plans.size() && changed < WORK_LIMIT && scanned < WORK_LIMIT && System.nanoTime() - began < WORK_NANOS)
            {
                Plan plan = plans.get(state.index);
                if (currentReconcileFold == null)
                {
                    if (pendingFold == null)
                    {
                        int index = state.index; Path original = planPath(index); String expectedDigest = state.planHashes.get(index);
                        UUID journey = state.journey; int from = state.journeySourceDepth, to = state.journeyTargetDepth;
                        reconcileFoldIndex = index;
                        pendingFold = journalReader.submit(() ->
                        {
                            try
                            {
                                if (!expectedDigest.equals(digest(original))) throw new IllegalStateException("Original recovery journal bytes changed before Fold");
                                CompoundTag data = NbtIo.readCompressed(original.toFile());
                                if (!expectedDigest.equals(digest(original))) throw new IllegalStateException("Original recovery journal bytes changed during Fold read");
                                if (!world.equals(data.getString("WorldUUID")) || data.getLong("Origin") != origin.asLong()
                                        || !journey.equals(data.getUUID("Journey")) || data.getInt("Index") != index)
                                    throw new IllegalStateException("Foreign recovery journal Fold authority");
                                Plan originalPlan = Plan.load(data); originalPlan.validate(plan.spec, from, to, plan.owner);
                                originalPlan.validateOperationSequence(); return originalPlan.fold();
                            }
                            catch (Exception failure) { throw new java.util.concurrent.CompletionException(failure); }
                        });
                        return;
                    }
                    if (!pendingFold.isDone()) return;
                    if (reconcileFoldIndex != state.index) throw new IllegalStateException("Recovery Fold index changed while waiting; preserve inverse");
                    currentReconcileFold = pendingFold.join(); pendingFold = null;
                }
                List<Fold> folded = currentReconcileFold;
                if (state.cursor >= folded.size()) { state.index++; state.cursor = 0; clearReconcileFold(); continue; }
                Fold operation = folded.get(state.cursor++); scanned++;
                Image actual = Image.read(level, operation.pos);
                Image desired = state.rollback ? operation.initial : operation.finalImage;
                if (actual.equals(desired)) continue;
                if (!operation.known.contains(actual)) throw new IllegalStateException("Unknown fullNBT during recovery at " + operation.pos);
                desired.write(level, operation.pos); changed++; actualWrites++;
            }
            if (state.index == plans.size())
            {
                // Recovery resumes at a static authoritative endpoint. It
                // never teleports an occupant or duplicates moving inventory.
                for (Plan plan : plans)
                {
                    Entity entity = level.getEntity(plan.owner);
                    if (entity != null)
                    {
                        if (!entity.getTags().contains(ownerTag())) throw new IllegalStateException("Foreign entity at recovered UUID");
                        CityCreateBridgeR45.verify(entity, plan.cargo()); entity.discard();
                    }
                }
                entities.clear(); state.phase = "FLUSH"; state.index = state.cursor = 0;
            }
            checkpoint();
        }

        void clearReconcileFold()
        {
            if (pendingFold != null) pendingFold.cancel(false);
            pendingFold = null; currentReconcileFold = null; reconcileFoldIndex = -1;
        }

        void commit() throws Exception
        {
            clearReconcileFold();
            int endpoint = state.rollback ? state.journeySourceDepth : state.journeyTargetDepth;
            int queued = state.queued;
            state.depth = state.target = endpoint; state.phase = "IDLE";
            state.queued = queued >= 0 && queued != endpoint ? queued : -1; state.queueFault = "";
            state.index = state.cursor = 0; persist(); claim(false);
            ProjectSeele.LOGGER.info("R45 rigid city endpoint={} objects={} writes={} peakWork={}ms peakMotion={}ms nativeFlush={}ms fullNBT=true",
                    endpoint, towers.size(), actualWrites, peakWorkNanos / 1e6, peakMotionNanos / 1e6, endpointFlushNanos / 1e6);
            ProjectSeele.LOGGER.info("R45 rigid city WAL preflight={}ms encode={}ms durableIO={}ms reload={}ms ledgerIO={}ms",
                    walPreflightNanos / 1e6, walSerializationNanos / 1e6, walIoNanos / 1e6, journalLoadNanos / 1e6, ledgerIoNanos / 1e6);
            plans.clear();
            // The next trip is durable IDLE intent. Its occupancy/backend
            // preflight happens on later ticks and cannot fault this commit.
        }

        void syncEndpointMetadata()
        {
            int endpoint = state.rollback ? state.journeySourceDepth : state.journeyTargetDepth;
            for (var tower : towers) if (tower.core() != null)
            {
                BlockState core = level.getBlockState(tower.core());
                if (!core.is(ModBlocks.RETRACTABLE_BUILDING_CORE.get())) throw new IllegalStateException("Fixed core migration identity changed");
                level.setBlock(tower.core(), core.setValue(RetractableBuildingCoreBlock.ARMED, endpoint > 0), Block.UPDATE_CLIENTS);
            }
            Tokyo3RetractionSavedData.get(level).put(new Tokyo3RetractionSavedData.StoredDistrict(origin, endpoint, endpoint, level.getGameTime()));
        }

        String ownerTag() { return "r45_city_rigid/" + world + "/" + origin.asLong(); }

        boolean occupied()
        {
            for (var spec : towers)
            {
                AABB volume = route(spec).inflate(.01);
                if (!level.getEntities((Entity) null, volume, actor -> !ownsActor(actor)).isEmpty()) return true;
            }
            return false;
        }

        boolean ownsActor(Entity actor)
        {
            return ownerIds.contains(actor.getUUID()) && actor.getTags().contains(ownerTag())
                    && actor.getPersistentData().hasUUID("R45CityJourney")
                    && state.journey.equals(actor.getPersistentData().getUUID("R45CityJourney"));
        }

        AABB route(CityRigidTopologyR45.Tower spec)
        {
            return new AABB(spec.centre().getX() + spec.minX(), spec.retractedY(), spec.centre().getZ() + spec.minZ(),
                    spec.centre().getX() + spec.maxX() + 1, spec.centre().getY() + spec.height() + 4, spec.centre().getZ() + spec.maxZ() + 1);
        }

        boolean resident()
        {
            if (claimed != chunks.size()) return false;
            for (ChunkPos chunk : chunks)
                if (!level.hasChunk(chunk.x, chunk.z) || !level.areEntitiesLoaded(chunk.toLong())) return false;
            return true;
        }

        void claim(boolean acquire)
        {
            if (acquire)
            {
                int end = Math.min(chunks.size(), claimed + 12);
                for (; claimed < end; claimed++)
                {
                    ChunkPos pos = chunks.get(claimed); level.getChunkSource().addRegionTicket(TICKET, pos, 2, pos);
                }
            }
            else { for (int i = 0; i < claimed; i++) { ChunkPos pos = chunks.get(i); level.getChunkSource().removeRegionTicket(TICKET, pos, 2, pos); } claimed = 0; }
        }

        void stopEntities() throws Exception { for (Entity entity : entities.values()) if (entity.isAlive()) CityCreateBridgeR45.stop(entity); }

        void persist() throws Exception
        {
            observePhaseTiming();
            long began = System.nanoTime();
            CompoundTag tag = state.save(); tag.putInt("Version", 1); tag.putString("WorldUUID", world); tag.putLong("Origin", origin.asLong());
            CompoundTag root = new CompoundTag(); root.put("data", tag); NbtUtils.addCurrentDataVersion(root); atomic(file, root);
            ledgerIoNanos += System.nanoTime() - began; lastPersistTick = level.getGameTime(); lastPersistPhase = state.phase;
        }

        void observePhaseTiming()
        {
            if (observedPhase.equals(state.phase)) return;
            long now = System.nanoTime();
            if (!observedPhase.isEmpty()) phaseTotalsNanos.merge(observedPhase, now - phaseStartedNanos, Long::sum);
            observedPhase = state.phase; phaseStartedNanos = now;
        }

        void checkpoint() throws Exception
        {
            // All images are already durable. An older partial cursor is safe:
            // restart replays known before/after images from index zero. Every
            // phase transition and first WorldTouched barrier remains forced.
            if (!state.phase.equals(lastPersistPhase) || lastPersistTick == Long.MIN_VALUE
                    || level.getGameTime() - lastPersistTick >= 20) persist();
        }
    }

    private static int duration(Plan plan)
    {
        int ticks = Math.max(20, (int) Math.ceil(Math.abs(plan.targetY - plan.sourceY) / SPEED));
        return ticks + (ticks & 1);
    }

    private static double fraction(int tick, int duration)
    {
        double t = Math.max(0, Math.min(duration, tick));
        int ramp = Math.min(RAMP_TICKS, duration / 4);
        double normalisation = duration - ramp;
        if (t <= ramp) return t * t / (2D * ramp * normalisation);
        if (t >= duration - ramp)
        {
            double remaining = duration - t;
            return 1D - remaining * remaining / (2D * ramp * normalisation);
        }
        return (t - ramp / 2D) / normalisation;
    }

    private static BlockState hatch(CityRigidTopologyR45.Tower spec, int x, int z)
    {
        if (spec.index() < 93)
        {
            var legacy = ThirdTokyoSurfaceBuilder.movableBuildings().get(spec.index());
            return ThirdTokyoSurfaceBuilder.retractedHatchStateR44(x, z,
                    new ThirdTokyoSurfaceBuilder.TowerSpec(legacy.x(), legacy.z(), spec.height(), spec.half(), legacy.outerWard(), true));
        }
        boolean rim = x == spec.minX() || x == spec.maxX() || z == spec.minZ() || z == spec.maxZ();
        boolean seam = Math.floorMod(x - spec.minX(), 5) == 0 || Math.floorMod(z - spec.minZ(), 5) == 0;
        return (rim ? Blocks.POLISHED_DEEPSLATE : seam ? Blocks.IRON_BLOCK : Blocks.GRAY_CONCRETE).defaultBlockState();
    }

    private static final class State
    {
        String phase = "IDLE", fault = "", faultPhase = "", queueFault = "";
        int depth, target, queued = -1, index, cursor, savedPlans, created, motionTick;
        int journeySourceDepth, journeyTargetDepth;
        final List<String> planHashes = new ArrayList<>();
        double progress;
        UUID journey = UUID.randomUUID();
        boolean rollback, worldTouched, allowMissingRecovery;
        CompoundTag save()
        {
            CompoundTag tag = new CompoundTag(); tag.putString("Phase", phase); tag.putString("Fault", fault);
            tag.putInt("Depth", depth); tag.putInt("Target", target); tag.putInt("Queued", queued);
            tag.putString("QueueFault", queueFault);
            tag.putInt("Index", index); tag.putInt("Cursor", cursor); tag.putInt("SavedPlans", savedPlans);
            tag.putDouble("Progress", progress); tag.putUUID("Journey", journey); tag.putBoolean("Rollback", rollback);
            tag.putBoolean("WorldTouched", worldTouched); tag.putString("FaultPhase", faultPhase);
            tag.putInt("Created", created); tag.putBoolean("AllowMissingRecovery", allowMissingRecovery);
            tag.putInt("JourneySourceDepth", journeySourceDepth); tag.putInt("JourneyTargetDepth", journeyTargetDepth);
            ListTag hashes = new ListTag(); for (String hash : planHashes) hashes.add(net.minecraft.nbt.StringTag.valueOf(hash));
            tag.put("JournalSHA256s", hashes);
            tag.putInt("MotionTick", motionTick); tag.putString("MotionProfile", "c1_trapezoid_v1"); return tag;
        }
        static State load(CompoundTag tag)
        {
            State s = new State(); s.phase = tag.getString("Phase"); s.fault = tag.getString("Fault");
            s.depth = tag.getInt("Depth"); s.target = tag.getInt("Target"); s.queued = tag.getInt("Queued");
            s.queueFault = tag.getString("QueueFault");
            s.index = tag.getInt("Index"); s.cursor = tag.getInt("Cursor"); s.savedPlans = tag.getInt("SavedPlans");
            s.progress = tag.getDouble("Progress"); s.journey = tag.getUUID("Journey"); s.rollback = tag.getBoolean("Rollback"); s.worldTouched = tag.getBoolean("WorldTouched");
            s.faultPhase = tag.getString("FaultPhase"); s.created = tag.getInt("Created"); s.allowMissingRecovery = tag.getBoolean("AllowMissingRecovery");
            s.motionTick = tag.getInt("MotionTick");
            s.journeySourceDepth = tag.contains("JourneySourceDepth") ? tag.getInt("JourneySourceDepth") : s.depth;
            s.journeyTargetDepth = tag.contains("JourneyTargetDepth") ? tag.getInt("JourneyTargetDepth") : s.target;
            ListTag hashes = tag.getList("JournalSHA256s", Tag.TAG_STRING);
            for (int i = 0; i < hashes.size(); i++) s.planHashes.add(hashes.getString(i));
            if (s.worldTouched && !s.phase.equals("IDLE") && !tag.contains("JournalSHA256s"))
                throw new IllegalStateException("Previous active city WAL needs an explicit byte-hash migration; original journals remain untouched");
            if (s.worldTouched && !s.phase.equals("IDLE") && !tag.getString("MotionProfile").equals("c1_trapezoid_v1"))
                throw new IllegalStateException("Previous rigid trajectory requires explicit saved-control migration");
            return s;
        }
        void validate(int objects)
        {
            if (!java.util.Set.of("IDLE", "PREPARE", "WAL_WAIT", "OPEN", "DETACH", "REPLAY_OPEN", "REPLAY_DETACH", "SPAWN", "READY", "MOVE", "PLACE", "COVER", "RECONCILE", "FLUSH", "COMMIT", "FAULT").contains(phase)
                    || (depth != 0 && depth != 312) || (target != 0 && target != 312)
                    || (journeySourceDepth != 0 && journeySourceDepth != 312) || (journeyTargetDepth != 0 && journeyTargetDepth != 312)
                    || (queued != -1 && queued != 0 && queued != 312) || index < 0 || index > objects || cursor < 0
                    || savedPlans < 0 || savedPlans > objects || created < 0 || created > objects || motionTick < 0
                    || !Double.isFinite(progress) || progress < 0 || progress > 1)
                throw new IllegalStateException("Invalid persistent city transaction coordinates or phase");
            if (!phase.equals("IDLE") && (worldTouched || !java.util.Set.of("PREPARE", "WAL_WAIT", "FAULT").contains(phase))
                    && planHashes.size() != savedPlans)
                throw new IllegalStateException("Incomplete durable original journal digest list");
            if (worldTouched && !phase.equals("IDLE") && (savedPlans != objects || journeySourceDepth == journeyTargetDepth
                    || phase.equals("PREPARE") || phase.equals("WAL_WAIT")))
                throw new IllegalStateException("World mutation requires the full96 immutable original inverse set");
            if (planHashes.stream().anyMatch(hash -> !hash.matches("[0-9a-f]{64}")))
                throw new IllegalStateException("Invalid original journal SHA256");
        }
    }

    private static final class Plan
    {
        final CityRigidTopologyR45.Tower spec;
        final UUID owner;
        final int sourceY, targetY;
        final Map<Long, Image> cells = new LinkedHashMap<>();
        final List<Write> open = new ArrayList<>(), detach = new ArrayList<>(), place = new ArrayList<>(), cover = new ArrayList<>();
        List<Fold> folded;
        CityCreateCargoR45.Cargo cachedCargo;
        int groundContract = 2, initialWorldImageCount;
        String initialWorldImageSHA256 = "";
        Plan(CityRigidTopologyR45.Tower spec, int sourceDepth, int targetDepth, UUID owner)
        {
            this.spec = spec; this.owner = owner;
            sourceY = sourceDepth == 0 ? spec.centre().getY() : spec.retractedY();
            targetY = targetDepth == 0 ? spec.centre().getY() : spec.retractedY();
        }
        List<Write> operations(int stage) { return switch (stage) { case 0 -> open; case 1 -> detach; case 2 -> place; case 3 -> cover; default -> throw new IllegalStateException(); }; }
        CityCreateCargoR45.Cargo cargo()
        {
            if (cachedCargo != null) return cachedCargo;
            Map<BlockState, CompoundTag> states = new HashMap<>();
            CompoundTag building = new CompoundTag(); building.putLong("Centre", spec.centre().asLong());
            building.putInt("Half", spec.half()); building.putInt("Height", spec.height()); building.putBoolean("FixedStreetCore", false);
            CompoundTag footprint = new CompoundTag(); footprint.putInt("MinX", spec.minX()); footprint.putInt("MaxX", spec.maxX());
            footprint.putInt("MinZ", spec.minZ()); footprint.putInt("MaxZ", spec.maxZ()); building.put("R45Footprint", footprint);
            ListTag list = new ListTag(); int count = 0;
            for (var entry : cells.entrySet())
            {
                CompoundTag cell = entry.getValue().save(states); cell.remove("Data"); cell.putLong("Pos", entry.getKey());
                if (entry.getValue().nbt != null) { cell.put("NBT", entry.getValue().nbt.copy()); count++; }
                list.add(cell);
            }
            building.put("Cargo", list); return cachedCargo = new CityCreateCargoR45.Cargo(building, cells.size(), count);
        }
        List<Fold> fold()
        {
            if (folded != null) return folded;
            Map<Long, Fold> rows = new LinkedHashMap<>();
            for (int i = 0; i < 4; i++) for (Write op : operations(i))
            {
                Fold row = rows.computeIfAbsent(op.pos.asLong(), ignored -> new Fold(op.pos, op.before));
                row.known.add(op.before); row.known.add(op.after); row.finalImage = op.after;
            }
            return folded = new ArrayList<>(rows.values());
        }
        void validateOperationSequence()
        {
            Map<Long, Image> previous = new HashMap<>();
            Map<Long, Image> initial = groundContract == 2 ? new LinkedHashMap<>() : null;
            for (int stage = 0; stage < 4; stage++) for (Write operation : operations(stage))
            {
                if (initial != null) initial.putIfAbsent(operation.pos.asLong(), operation.before);
                Image before = previous.put(operation.pos.asLong(), operation.after);
                if (before != null && !before.equals(operation.before))
                    throw new IllegalStateException("Original operation images are discontinuous at " + operation.pos);
            }
            if (initial != null)
            {
                if (initialWorldImageCount != initial.size() || !initialWorldImageSHA256.matches("[0-9a-f]{64}"))
                    throw new IllegalStateException("New complete Ground plan lacks its actual full initial world image verification");
                try
                {
                    var digest = java.security.MessageDigest.getInstance("SHA-256");
                    for (var row : initial.entrySet())
                    {
                        CompoundTag image = row.getValue().save(); image.putLong("Pos", row.getKey());
                        try (var sink = new DataOutputStream(new java.security.DigestOutputStream(java.io.OutputStream.nullOutputStream(), digest)))
                        { NbtIo.write(image, sink); }
                    }
                    if (!initialWorldImageSHA256.equals(java.util.HexFormat.of().formatHex(digest.digest())))
                        throw new IllegalStateException("Complete source/destination/Ground first images differ from their actual native world snapshot");
                }
                catch (IOException | java.security.NoSuchAlgorithmException failure) { throw new IllegalStateException("Cannot verify complete initial world images", failure); }
            }
        }
        CompoundTag save()
        {
            Map<BlockState, CompoundTag> states = new HashMap<>();
            CompoundTag tag = new CompoundTag(); tag.putUUID("Owner", owner); tag.putInt("SourceY", sourceY); tag.putInt("TargetY", targetY);
            tag.putLong("Centre", spec.centre().asLong()); tag.putInt("Index", spec.index()); tag.putString("Kind", spec.kind());
            tag.putInt("Height", spec.height()); tag.putInt("Half", spec.half()); tag.putInt("RetractedY", spec.retractedY());
            tag.putInt("MinX", spec.minX()); tag.putInt("MaxX", spec.maxX()); tag.putInt("MinZ", spec.minZ()); tag.putInt("MaxZ", spec.maxZ());
            tag.putInt("GroundContract", groundContract); tag.putInt("InitialWorldImageCount", initialWorldImageCount);
            tag.putString("InitialWorldImageSHA256", initialWorldImageSHA256);
            if (spec.core() != null) tag.putLong("Core", spec.core().asLong()); tag.putLongArray("Anchors", spec.fixedAnchors());
            ListTag list = new ListTag(); cells.forEach((key, value) -> { CompoundTag cell = value.save(states); cell.putLong("Pos", key); list.add(cell); }); tag.put("Cells", list);
            for (int stage = 0; stage < 4; stage++) { ListTag ops = new ListTag(); for (Write op : operations(stage)) ops.add(op.save(states)); tag.put("Ops" + stage, ops); }
            return tag;
        }
        static Plan load(CompoundTag tag)
        {
            var spec = new CityRigidTopologyR45.Tower(tag.getInt("Index"), tag.getString("Kind"), BlockPos.of(tag.getLong("Centre")), tag.getInt("Height"), tag.getInt("Half"),
                    tag.contains("Core") ? BlockPos.of(tag.getLong("Core")) : null, tag.getLongArray("Anchors"), tag.getInt("MinX"), tag.getInt("MaxX"), tag.getInt("MinZ"), tag.getInt("MaxZ"), tag.getInt("RetractedY"));
            Plan p = new Plan(spec, tag.getInt("SourceY") == spec.centre().getY() ? 0 : 312, tag.getInt("TargetY") == spec.centre().getY() ? 0 : 312, tag.getUUID("Owner"));
            p.groundContract = tag.contains("GroundContract") ? tag.getInt("GroundContract") : 1;
            p.initialWorldImageCount = tag.getInt("InitialWorldImageCount"); p.initialWorldImageSHA256 = tag.getString("InitialWorldImageSHA256");
            if (p.groundContract != 1 && p.groundContract != 2) throw new IllegalStateException("Unknown complete Ground plan contract");
            if (tag.getInt("SourceY") != p.sourceY || tag.getInt("TargetY") != p.targetY)
                throw new IllegalStateException("Journal source/target Y is not an explicit original endpoint");
            for (Tag raw : tag.getList("Cells", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = (CompoundTag) raw;
                if (p.cells.put(cell.getLong("Pos"), Image.load(cell)) != null) throw new IllegalStateException("Duplicate journal cargo position");
            }
            for (int stage = 0; stage < 4; stage++) for (Tag raw : tag.getList("Ops" + stage, Tag.TAG_COMPOUND)) p.operations(stage).add(Write.load((CompoundTag) raw));
            return p;
        }
        void validate(CityRigidTopologyR45.Tower expected, int from, int to, UUID expectedOwner)
        {
            if (spec.index() != expected.index() || !spec.kind().equals(expected.kind()) || !spec.centre().equals(expected.centre())
                    || spec.height() != expected.height() || spec.half() != expected.half() || !java.util.Objects.equals(spec.core(), expected.core())
                    || !java.util.Arrays.equals(spec.fixedAnchors(), expected.fixedAnchors()) || spec.minX() != expected.minX()
                    || spec.maxX() != expected.maxX() || spec.minZ() != expected.minZ() || spec.maxZ() != expected.maxZ()
                    || spec.retractedY() != expected.retractedY() || !owner.equals(expectedOwner)
                    || sourceY != (from == 0 ? spec.centre().getY() : spec.retractedY())
                    || targetY != (to == 0 ? spec.centre().getY() : spec.retractedY()) || cells.isEmpty())
                throw new IllegalStateException("Full journal footprint/controller/anchor/UUID authority changed");
            for (var cell : cells.entrySet())
            {
                BlockPos p = BlockPos.of(cell.getKey()); Image image = cell.getValue();
                if (p.getX() < spec.minX() || p.getX() > spec.maxX() || p.getZ() < spec.minZ() || p.getZ() > spec.maxZ()
                        || p.getY() < 0 || p.getY() > spec.height() + 3 || image.state.hasBlockEntity() != (image.nbt != null))
                    throw new IllegalStateException("Journal cargo leaves its full owned frame or loses BE metadata");
                if (image.nbt != null && !image.equals(image.at(p.offset(spec.centre().getX(), sourceY, spec.centre().getZ()))))
                    throw new IllegalStateException("Original complete BE coordinates changed in cargo journal");
            }
            int ground = (spec.maxX() - spec.minX() + 1) * (spec.maxZ() - spec.minZ() + 1);
            boolean mustOpenGround = to == 0 || groundContract == 2 && sourceY > 80 && targetY < 80;
            if (detach.size() != cells.size() || place.size() != cells.size() || open.size() != (mustOpenGround ? ground : 0)
                    || cover.size() != (to == 312 || spec.index() >= 93 ? ground : 0))
                throw new IllegalStateException("Journal does not contain complete source/target/ground operations");
            for (int stage = 0; stage < 4; stage++)
            {
                java.util.Set<Long> seen = new java.util.HashSet<>();
                for (Write op : operations(stage))
                {
                    if (!seen.add(op.pos.asLong())) throw new IllegalStateException("Duplicate journal operation");
                    int x = op.pos.getX() - spec.centre().getX(), z = op.pos.getZ() - spec.centre().getZ();
                    if (x < spec.minX() || x > spec.maxX() || z < spec.minZ() || z > spec.maxZ())
                        throw new IllegalStateException("Journal operation crosses facility ownership");
                    if (stage == 1 || stage == 2)
                    {
                        int base = stage == 1 ? sourceY : targetY;
                        Image image = cells.get(new BlockPos(x, op.pos.getY() - base, z).asLong());
                        if (image == null || stage == 1 && (!op.before.equals(image) || !op.after.equals(Image.AIR))
                                || stage == 2 && (!op.before.state.isAir() || op.before.nbt != null || !op.after.equals(image.at(op.pos))))
                            throw new IllegalStateException("Journal cargo/image operation is not the exact captured inverse");
                    }
                    else
                    {
                        Image groundImage = new Image(hatch(spec, x, z), null);
                        if (op.pos.getY() != 80 || stage == 0 && (!op.before.equals(groundImage) || !op.after.equals(Image.AIR))
                                || stage == 3 && (!op.before.equals(Image.AIR) || !op.after.equals(groundImage)))
                            throw new IllegalStateException("Journal hatch operation is not its full owned ground image");
                    }
                }
            }
        }
    }

    private record Image(BlockState state, CompoundTag nbt)
    {
        static final Image AIR = new Image(Blocks.AIR.defaultBlockState(), null);
        static Image read(ServerLevel level, BlockPos pos)
        {
            BlockState state = level.getBlockState(pos); BlockEntity entity = level.getBlockEntity(pos);
            if (state.hasBlockEntity() && entity == null) throw new IllegalStateException("Complete source BE unavailable at " + pos);
            return state.equals(Blocks.AIR.defaultBlockState()) && entity == null ? AIR : new Image(state, entity == null ? null : entity.saveWithFullMetadata().copy());
        }
        Image at(BlockPos pos)
        {
            if (nbt == null) return this;
            CompoundTag data = nbt.copy(); data.putInt("x", pos.getX()); data.putInt("y", pos.getY()); data.putInt("z", pos.getZ()); return new Image(state, data);
        }
        void write(ServerLevel level, BlockPos pos)
        {
            level.removeBlockEntity(pos);
            level.setBlock(pos, state, Block.UPDATE_CLIENTS | Block.UPDATE_KNOWN_SHAPE | Block.UPDATE_SUPPRESS_DROPS);
            if (nbt != null)
            {
                BlockEntity entity = BlockEntity.loadStatic(pos, state, at(pos).nbt.copy());
                if (entity == null) throw new IllegalStateException("Cannot restore full cargo BE at " + pos);
                level.setBlockEntity(entity); entity.setChanged(); level.sendBlockUpdated(pos, state, state, Block.UPDATE_CLIENTS);
            }
            PerformanceCounters.recordWorldBlockWrites(1);
        }
        CompoundTag save() { CompoundTag tag = new CompoundTag(); tag.put("State", NbtUtils.writeBlockState(state)); if (nbt != null) tag.put("Data", nbt.copy()); return tag; }
        CompoundTag save(Map<BlockState, CompoundTag> states)
        {
            CompoundTag tag = new CompoundTag(); tag.put("State", states.computeIfAbsent(state, NbtUtils::writeBlockState));
            if (nbt != null) tag.put("Data", nbt.copy()); return tag;
        }
        static Image load(CompoundTag tag) { return new Image(NbtUtils.readBlockState(BuiltInRegistries.BLOCK.asLookup(), tag.getCompound("State")), tag.contains("Data") ? tag.getCompound("Data").copy() : null); }
    }

    private record Write(BlockPos pos, Image before, Image after)
    {
        CompoundTag save() { CompoundTag tag = new CompoundTag(); tag.putLong("Pos", pos.asLong()); tag.put("Before", before.save()); tag.put("After", after.save()); return tag; }
        CompoundTag save(Map<BlockState, CompoundTag> states)
        {
            CompoundTag tag = new CompoundTag(); tag.putLong("Pos", pos.asLong());
            tag.put("Before", before.save(states)); tag.put("After", after.save(states)); return tag;
        }
        static Write load(CompoundTag tag) { return new Write(BlockPos.of(tag.getLong("Pos")), Image.load(tag.getCompound("Before")), Image.load(tag.getCompound("After"))); }
    }

    private static final class Fold
    {
        final BlockPos pos; final Image initial; Image finalImage; final java.util.Set<Image> known = new java.util.HashSet<>();
        Fold(BlockPos pos, Image initial) { this.pos = pos; this.initial = initial; finalImage = initial; }
    }

    private static String digest(Path source) throws IOException
    {
        try
        {
            var digest = java.security.MessageDigest.getInstance("SHA-256");
            try (var stream = Files.newInputStream(source))
            {
                byte[] buffer = new byte[65536]; int amount;
                while ((amount = stream.read(buffer)) != -1) digest.update(buffer, 0, amount);
            }
            return java.util.HexFormat.of().formatHex(digest.digest());
        }
        catch (java.security.NoSuchAlgorithmException failure) { throw new IOException(failure); }
    }

    private static void atomic(Path target, CompoundTag tag) throws IOException
    {
        Files.createDirectories(target.getParent()); Path pending = Files.createTempFile(target.getParent(), target.getFileName().toString(), ".pending");
        try
        {
            try (DataOutputStream output = new DataOutputStream(new GZIPOutputStream(Files.newOutputStream(pending), 65536)
            { { def.setLevel(Deflater.BEST_SPEED); } })) { NbtIo.write(tag, output); }
            try (FileChannel file = FileChannel.open(pending, StandardOpenOption.WRITE)) { file.force(true); }
            Files.move(pending, target, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        }
        finally { Files.deleteIfExists(pending); }
    }
}

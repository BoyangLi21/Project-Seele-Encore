package com.projectseele.world;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Read-only native witnesses of real city ownership/cargo; no helper body replacement. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityRigidQualityR45
{
    private static final String JOB = System.getProperty("projectseele.r45CityRigidQuality", "");
    private static JsonObject input;
    private static boolean done, observedMove;
    private static int age, leg;
    private static String observedJourney;
    private static boolean oracleAscentRequested;
    private static final JsonArray completedLegs = new JsonArray(), planProofs = new JsonArray();
    private static final java.util.Map<Path, String> retainedJournals = new java.util.LinkedHashMap<>();
    private static java.util.Iterator<java.util.Map.Entry<Long, CompoundTag>> endpointImages;
    private static int endpointCargoCount, endpointBECount, endpointFinalImageCount;
    private static int endpointIndex, endpointCursor;
    private static CompoundTag endpointLedger, endpointPlan;
    private static ListTag endpointCells;
    private static final java.util.Map<Integer, CompoundTag> planCache = new java.util.HashMap<>();
    private static final JsonArray witnesses = new JsonArray();
    private CityRigidQualityR45() {}

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (JOB.isEmpty() || done || event.phase != TickEvent.Phase.END || ++age < 40) return;
        try
        {
            if (input == null)
            {
                input = JsonParser.parseString(Files.readString(Path.of(JOB))).getAsJsonObject();
                if (isRoundtrip() || input.get("mode").getAsString().equals("relogin"))
                {
                    JsonObject binding = JsonParser.parseString(Files.readString(Path.of(input.get("candidate_binding").getAsString()))).getAsJsonObject();
                    boolean resumed=input.get("mode").getAsString().equals("resume_roundtrip");
                    JsonObject proof = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject(resumed ? "qa_inflight_move1_checkpoint" : "qa_settled_checkpoint").get("path").getAsString()))).getAsJsonObject();
                    if (!(resumed ? "projectseele.city-qa-cold-inflight-motion-checkpoint-r45.v2".equals(proof.get("schema").getAsString())
                            && proof.get("source_depth").getAsInt()==input.get("expected_source_endpoint").getAsInt()
                            && proof.get("journey_uuid").getAsString().equals(input.get("expected_original_journey").getAsString())
                            && proof.get("previous_settled_journey").getAsString().equals(input.get("expected_previous_journey").getAsString())
                            : "projectseele.city-qa-cold-settled-endpoint-checkpoint-r45.v2".equals(proof.get("schema").getAsString())
                            && proof.get("depth").getAsInt()==input.get("expected_source_endpoint").getAsInt()
                            && proof.get("journey_uuid").getAsString().equals(input.get("expected_previous_journey").getAsString()))
                            || isRoundtrip() && input.get("expected_source_endpoint").getAsInt() != 312)
                        throw new IllegalStateException("Finite settled quality must match the single cold admitted endpoint");
                    for (String key : resumed ? new String[]{"retained_original_journals"} : new String[]{"current_original96_journals", "retained_original_journals"})
                        for (var raw : proof.getAsJsonArray(key))
                        {
                            JsonObject row = raw.getAsJsonObject().getAsJsonObject("current"); Path path = Path.of(row.get("path").getAsString()).toRealPath();
                            if (retainedJournals.put(path, row.get("sha256").getAsString()) != null) throw new IllegalStateException("Duplicate retained quality journal");
                        }
                    if (retainedJournals.size() != proof.get("original_journal_count").getAsInt() - (resumed ? 96 : 0)) throw new IllegalStateException("Incomplete retained quality authority");
                }
            }
            ServerLevel level = event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
            Path world = event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
            if (input.has("candidate_binding")) world = world.toRealPath();
            if (level != null && !CityAtomicCandidateBindingR45.admit(world, input)) return;
            if (level == null
                    || !world.equals(Path.of(input.get("world").getAsString()).toAbsolutePath().normalize())
                    || !Tokyo3BuildingWorldIdentityR44.get(level).equals(input.get("world_id").getAsString())
                    || level.getSeed() != input.get("world_seed").getAsLong()) throw new IllegalStateException("Wrong native real-city test identity");
            if (age > input.get("timeout_ticks").getAsInt()) throw new IllegalStateException("Native real-city test timeout");
            BlockPos origin = IntegratedNervMapBuilder.tokyo3Origin(level);
            if (input.has("write_progress_diagnostics") && input.get("write_progress_diagnostics").getAsBoolean() && age % 20 == 0)
            {
                JsonObject progress = CityCreateDistrictR45.nativeDiagnostics(level, origin);
                if (progress != null)
                {
                    progress.addProperty("age", age); progress.addProperty("wall_epoch_ms", System.currentTimeMillis());
                    progress.addProperty("game_tick", level.getGameTime()); write("progress_latest", progress);
                    Path directory = Path.of(input.get("output").getAsString());
                    Files.writeString(directory.resolve("progress_samples.jsonl"), new com.google.gson.Gson().toJson(progress) + "\n",
                            java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
                }
            }
            if (!CityCreateDistrictR45.nativeReady(level, origin)) return;
            Path data = CityRigidTopologyR45.file(level, origin).getParent();
            if (endpointLedger != null)
            {
                if (verifyActualEndpoint(level, data, endpointLedger))
                {
                    if (isRoundtrip()) finishRoundtripLeg(level, origin, data, endpointLedger);
                    else finish("complete", endpointLedger, true);
                }
                return;
            }
            Path control = data.resolve("projectseele_city_rigid_control_r45_" + Long.toUnsignedString(origin.asLong()) + ".dat");
            if (!Files.isRegularFile(control) || age % 20 != 0) return;
            CompoundTag ledger = NbtIo.readCompressed(control.toFile()).getCompound("data");
            if (!input.get("world_id").getAsString().equals(ledger.getString("WorldUUID"))) throw new IllegalStateException("Foreign native ledger");
            if (ledger.getString("Phase").equals("FAULT")) throw new IllegalStateException(ledger.getString("Fault"));
            String mode = input.get("mode").getAsString();
            if (mode.equals("relogin"))
            {
                if (!ledger.getString("Phase").equals("IDLE") || ledger.getInt("Depth") != input.get("expected_source_endpoint").getAsInt()
                        || !ledger.getUUID("Journey").toString().equals(input.get("expected_previous_journey").getAsString()))
                    throw new IllegalStateException("Read-only relogin cannot change settled control or start another journey");
                endpointLedger = ledger.copy(); return;
            }
            if (isRoundtrip() && input.has("collider_oracle_receipt") && !oracleAscentRequested)
            {
                Path oracle = Path.of(input.get("collider_oracle_receipt").getAsString());
                if (Files.exists(Path.of(oracle.toString() + ".failed.json"))) throw new IllegalStateException("Actual native stock/balanced oracle failed");
                if (!Files.isRegularFile(oracle)) return;
                JsonObject receipt = JsonParser.parseString(Files.readString(oracle)).getAsJsonObject();
                if (!"projectseele.city-native-collider-oracle-receipt-r45.v1".equals(receipt.get("schema").getAsString())
                        || !receipt.get("passed").getAsBoolean() || !receipt.get("full96_passed").getAsBoolean()
                        || receipt.get("cells").getAsInt() != 749242 || receipt.get("complete_BE").getAsInt() != 1471
                        || receipt.get("world_written").getAsBoolean() || receipt.get("entity_created").getAsBoolean()
                        || receipt.get("stock_provider_modified").getAsBoolean() || !receipt.get("actual_stock_supplier_invoked").getAsBoolean()
                        || !receipt.get("per_original_shape_repeat_XOR_empty").getAsBoolean()
                        || receipt.getAsJsonArray("complete_plan_results").size() != 96)
                    throw new IllegalStateException("Full96 actual stock and per-shape XOR/collision oracle did not pass");
                if (!ledger.getString("Phase").equals("IDLE") || ledger.getInt("Depth") != 312
                        || !ledger.getUUID("Journey").toString().equals(input.get("expected_previous_journey").getAsString()))
                    throw new IllegalStateException("World moved before the read-only oracle finished");
                var request = CityCreateDistrictR45.request(level, origin, false);
                if (request == null || !request.accepted()) throw new IllegalStateException("Original guarded ascent request rejected: " + request);
                oracleAscentRequested = true; return;
            }
            if (ledger.getString("Phase").equals("MOVE"))
            {
                if (isRoundtrip())
                {
                    String previous = leg == 0 ? input.get("expected_previous_journey").getAsString() : completedLegs.get(0).getAsJsonObject().get("journey_uuid").getAsString();
                    if (ledger.getUUID("Journey").toString().equals(previous) || ledger.getInt("JourneySourceDepth") != (leg == 0 ? 312 : 0)
                            || ledger.getInt("JourneyTargetDepth") != (leg == 0 ? 0 : 312) || ledger.getBoolean("Rollback"))
                        throw new IllegalStateException("Continuous native travel requires two fresh directional journeys");
                    if (observedJourney != null && !observedJourney.equals(ledger.getUUID("Journey").toString())) throw new IllegalStateException("Journey changed within the observed leg");
                    observedJourney = ledger.getUUID("Journey").toString();
                }
                observedMove = true;
                if (!mode.equals("interrupt") || ledger.getInt("MotionTick") >= input.get("checkpoint_motion_tick").getAsInt())
                {
                    if (mode.equals("interrupt") && !CityCreateDistrictR45.holdNativeCheckpoint(level, origin))
                        throw new IllegalStateException("Failed to hold real moving owners");
                    JsonObject witness = inspectOwners(level, data, ledger);
                    witnesses.add(witness);
                    if (mode.equals("interrupt")) { finish("checkpoint", ledger, true); return; }
                }
            }
            if (observedMove && ledger.getString("Phase").equals("IDLE")
                    && ledger.getInt("Depth") == (isRoundtrip() ? (leg == 0 ? 0 : 312) : input.get("endpoint_depth").getAsInt()))
            {
                endpointLedger = ledger.copy();
            }
        }
        catch (Exception failure)
        {
            try { JsonObject report = base(false); report.addProperty("error", failure.toString()); write("failed", report); }
            catch (Exception ignored) {}
            done = true; ProjectSeele.LOGGER.error("R45 real-city native witness failed; no surrogate repair", failure);
        }
    }

    private static JsonObject inspectOwners(ServerLevel level, Path data, CompoundTag ledger) throws Exception
    {
        JsonObject sample = new JsonObject(); sample.addProperty("motion_tick", ledger.getInt("MotionTick"));
        sample.addProperty("journey_uuid", ledger.getUUID("Journey").toString());
        JsonArray objects = new JsonArray();
        for (int index = 0; index < 96; index++)
        {
            CompoundTag plan = planCache.get(index);
            if (plan == null)
            {
                plan = NbtIo.readCompressed(data.resolve("city_rigid_journal_r45").resolve(ledger.getUUID("Journey").toString()).resolve(index + ".dat").toFile());
                if (isRoundtrip())
                {
                    for (int stage = 0; stage < 4; stage++) plan.remove("Ops" + stage);
                    if (!input.getAsJsonArray("witness_indices").contains(new com.google.gson.JsonPrimitive(index))) plan.remove("Cells");
                }
                planCache.put(index, plan);
            }
            Entity entity = level.getEntity(plan.getUUID("Owner"));
            if (entity == null || !entity.getPersistentData().getUUID("R45CityJourney").equals(ledger.getUUID("Journey")))
                throw new IllegalStateException("Actual original owner UUID missing at object " + index);
            if (input.getAsJsonArray("witness_indices").contains(new com.google.gson.JsonPrimitive(index)))
            {
                CompoundTag saved = new CompoundTag(); if (!entity.save(saved)) throw new IllegalStateException("Original owner cannot persist");
                verifyCells(plan, saved.getCompound("Contraption"));
                JsonObject row = new JsonObject(); row.addProperty("index", index); row.addProperty("owner_uuid", entity.getUUID().toString());
                row.addProperty("actual_position", entity.position().toString()); row.addProperty("cells", plan.getList("Cells", Tag.TAG_COMPOUND).size());
                row.addProperty("full_nbt_equal", true); objects.add(row);
            }
        }
        sample.add("selected_actual_objects", objects); sample.addProperty("all96_original_owner_uuid_checked", true);
        sample.addProperty("selected_original_owner_full_nbt_equal", true);
        if (input.get("mode").getAsString().equals("resume") && input.has("checkpoint_report"))
        {
            JsonObject prior = JsonParser.parseString(Files.readString(Path.of(input.get("checkpoint_report").getAsString()))).getAsJsonObject();
            if (!prior.get("journey_uuid").getAsString().equals(ledger.getUUID("Journey").toString())) throw new IllegalStateException("Cold resume changed original journey UUID");
            sample.addProperty("cold_original_journey_equal", true);
        }
        return sample;
    }

    private static void verifyCells(CompoundTag plan, CompoundTag contraption)
    {
        CompoundTag building = new CompoundTag(); building.putInt("Half", plan.getInt("Half")); building.putInt("Height", plan.getInt("Height"));
        ListTag cells = new ListTag(); int entities = 0;
        for (Tag raw : plan.getList("Cells", Tag.TAG_COMPOUND))
        {
            CompoundTag value = ((CompoundTag) raw).copy();
            if (value.contains("Data")) { value.put("NBT", value.getCompound("Data").copy()); entities++; }
            cells.add(value);
        }
        building.put("Cargo", cells);
        CityCreateCargoR45.verify(new CityCreateCargoR45.Cargo(building, cells.size(), entities), contraption);
    }

    private static boolean verifyActualEndpoint(ServerLevel level, Path data, CompoundTag ledger) throws Exception
    {
        long started = System.nanoTime(); int scanned = 0;
        while (endpointIndex < 96 && scanned < 4096 && System.nanoTime() - started < 8_000_000L)
        {
            if (endpointPlan == null)
            {
                endpointPlan = NbtIo.readCompressed(data.resolve("city_rigid_journal_r45").resolve(ledger.getUUID("Journey").toString()).resolve(endpointIndex + ".dat").toFile());
                if (level.getEntity(endpointPlan.getUUID("Owner")) != null) throw new IllegalStateException("Duplicate live cargo owner after static endpoint");
                if (isRoundtrip())
                {
                    Path journal = data.resolve("city_rigid_journal_r45").resolve(ledger.getUUID("Journey").toString()).resolve(endpointIndex + ".dat").toRealPath();
                    String hash = fileSHA(journal);
                    if (!hash.equals(ledger.getList("JournalSHA256s", Tag.TAG_STRING).getString(endpointIndex))) throw new IllegalStateException("New durable journal differs from control");
                    CityCreateDistrictR45.verifyNativeGroundContract2Plan(level, IntegratedNervMapBuilder.tokyo3Origin(level), endpointPlan, leg == 0 ? 312 : 0, leg == 0 ? 0 : 312);
                    if (!ledger.getUUID("Journey").equals(endpointPlan.getUUID("Journey")) || endpointPlan.getInt("Index") != endpointIndex
                            || !input.get("world_id").getAsString().equals(endpointPlan.getString("WorldUUID"))) throw new IllegalStateException("New native journal identity changed");
                    java.util.Map<Long, CompoundTag> images = new java.util.LinkedHashMap<>();
                    for (int stage = 0; stage < 4; stage++) for (Tag raw : endpointPlan.getList("Ops" + stage, Tag.TAG_COMPOUND))
                    { CompoundTag op = (CompoundTag)raw; images.put(op.getLong("Pos"), op.getCompound("After")); }
                    endpointImages = images.entrySet().iterator();
                    JsonObject proof = new JsonObject(); proof.addProperty("index", endpointIndex); proof.addProperty("journal_path", journal.toString()); proof.addProperty("journal_sha256", hash);
                    proof.addProperty("ground_contract", 2); proof.addProperty("actual_initial_image_count", endpointPlan.getInt("InitialWorldImageCount"));
                    proof.addProperty("actual_initial_image_sha256", endpointPlan.getString("InitialWorldImageSHA256")); proof.addProperty("full_final_image_count", images.size()); planProofs.add(proof);
                    if (retainedJournals.put(journal, hash) != null) throw new IllegalStateException("A fresh journey overwrote retained native history");
                }
                endpointCells = endpointPlan.getList("Cells", Tag.TAG_COMPOUND); endpointCursor = 0;
            }
            BlockPos centre = BlockPos.of(endpointPlan.getLong("Centre"));
            int base = endpointPlan.getInt(ledger.getBoolean("Rollback") ? "SourceY" : "TargetY");
            if (endpointCursor >= endpointCells.size())
            {
                if (endpointImages != null && endpointImages.hasNext())
                {
                    var image = endpointImages.next(); scanned++; endpointFinalImageCount++;
                    verifyActualImage(level, BlockPos.of(image.getKey()), image.getValue()); continue;
                }
                endpointIndex++; endpointPlan = null; endpointImages = null; continue;
            }
                CompoundTag cell = endpointCells.getCompound(endpointCursor++); scanned++; endpointCargoCount++; if (cell.contains("Data")) endpointBECount++;
                BlockPos local = BlockPos.of(cell.getLong("Pos"));
                BlockPos actual = new BlockPos(centre.getX() + local.getX(), base + local.getY(), centre.getZ() + local.getZ());
                CompoundTag state = net.minecraft.nbt.NbtUtils.writeBlockState(level.getBlockState(actual));
                if (!state.equals(cell.getCompound("State"))) throw new IllegalStateException("Actual endpoint cargo state differs at " + actual);
                var be = level.getBlockEntity(actual); CompoundTag nbt = cell.contains("Data") ? cell.getCompound("Data").copy() : null;
                if (nbt != null) { nbt.putInt("x", actual.getX()); nbt.putInt("y", actual.getY()); nbt.putInt("z", actual.getZ()); }
                if ((be == null) != (nbt == null) || be != null && !be.saveWithFullMetadata().equals(nbt))
                    throw new IllegalStateException("Actual endpoint full BE NBT differs at " + actual);
        }
        return endpointIndex == 96;
    }

    private static boolean isRoundtrip()
    { String mode=input.get("mode").getAsString();return mode.equals("roundtrip") || mode.equals("resume_roundtrip"); }

    private static String fileSHA(Path path) throws Exception
    {
        var digest = java.security.MessageDigest.getInstance("SHA-256");
        try (var stream = Files.newInputStream(path))
        { byte[] buffer = new byte[65536]; int size; while ((size = stream.read(buffer)) != -1) digest.update(buffer, 0, size); }
        return java.util.HexFormat.of().formatHex(digest.digest());
    }

    private static void verifyActualImage(ServerLevel level, BlockPos position, CompoundTag image)
    {
        if (!net.minecraft.nbt.NbtUtils.writeBlockState(level.getBlockState(position)).equals(image.getCompound("State")))
            throw new IllegalStateException("Complete final operation image state differs at " + position);
        var be = level.getBlockEntity(position);
        CompoundTag expected = image.contains("Data", Tag.TAG_COMPOUND) ? image.getCompound("Data").copy() : null;
        if (expected != null) { expected.putInt("x", position.getX()); expected.putInt("y", position.getY()); expected.putInt("z", position.getZ()); }
        if ((be == null) != (expected == null) || be != null && !be.saveWithFullMetadata().equals(expected))
            throw new IllegalStateException("Complete final operation image full BE differs at " + position);
    }

    private static void verifyRetainedJournals() throws Exception
    {
        for (var row : retainedJournals.entrySet())
            if (!fileSHA(row.getKey()).equals(row.getValue())) throw new IllegalStateException("Original native journal bytes changed: " + row.getKey());
    }

    private static void finishRoundtripLeg(ServerLevel level, BlockPos origin, Path data, CompoundTag ledger) throws Exception
    {
        if (endpointCargoCount != 749242 || endpointBECount != 1471 || planProofs.size() != 96 || !observedMove
                || ledger.getInt("MotionTick") != 724 || ledger.getDouble("Progress") != 1 || ledger.getBoolean("Rollback")
                || !ledger.getUUID("Journey").toString().equals(observedJourney))
            throw new IllegalStateException("The complete new-plan native leg has not passed");
        verifyRetainedJournals();
        java.util.Set<Path> files = new java.util.HashSet<>();
        try (var stream = Files.walk(data.resolve("city_rigid_journal_r45")))
        { for (Path file : stream.filter(Files::isRegularFile).toList()) files.add(file.toRealPath()); }
        if (!files.equals(retainedJournals.keySet())) throw new IllegalStateException("Missing/extra original or new native journal");
        JsonObject report = base(true); report.addProperty("phase", "IDLE"); report.addProperty("depth", ledger.getInt("Depth"));
        report.addProperty("motion_tick", ledger.getInt("MotionTick")); report.addProperty("journey_uuid", observedJourney);
        report.addProperty("source_depth", leg == 0 ? 312 : 0); report.addProperty("target_depth", leg == 0 ? 0 : 312);
        report.add("new_ground_contract2_plan_proofs", planProofs.deepCopy()); report.addProperty("original_journal_bytes_retained", true);
        report.addProperty("current_journal_count", retainedJournals.size()); report.add("phase_diagnostics", CityCreateDistrictR45.nativeDiagnostics(level, origin));
        Path file = Path.of(input.get("output").getAsString()).resolve(leg == 0 ? "ascent_complete.json" : "descent_complete.json");
        Files.createDirectories(file.getParent());
        Files.writeString(file, new GsonBuilder().setPrettyPrinting().create().toJson(report), java.nio.file.StandardOpenOption.CREATE_NEW);
        completedLegs.add(report);
        if (leg == 1) { finish("complete", ledger, true); return; }
        // Only a complete verified static endpoint may request the original guarded return transaction.
        var result = CityCreateDistrictR45.request(level, origin, true);
        if (result == null || !result.accepted()) throw new IllegalStateException("Guarded new-plan return request rejected: " + result);
        leg = 1; observedMove = false; observedJourney = null; endpointLedger = null; endpointPlan = null; endpointCells = null;
        endpointImages = null; endpointIndex = endpointCursor = endpointCargoCount = endpointBECount = endpointFinalImageCount = 0;
        planCache.clear(); witnesses.asList().clear(); planProofs.asList().clear();
    }

    private static JsonObject base(boolean passed)
    {
        JsonObject report = new JsonObject(); report.addProperty("schema", "projectseele.real96-city-native-quality-r45.v1");
        report.addProperty("passed", passed); report.addProperty("age", age); report.addProperty("helper_replacement", false);
        report.addProperty("actual_existing_city_objects", 96); report.addProperty("client_visual_passed", false); report.addProperty("performance_passed", false);
        report.addProperty("full_cargo_cells", endpointCargoCount); report.addProperty("full_BE", endpointBECount);
        report.addProperty("complete_final_image_coordinates", endpointFinalImageCount); report.add("witnesses", witnesses.deepCopy()); return report;
    }
    private static void finish(String marker, CompoundTag ledger, boolean passed) throws Exception
    {
        JsonObject report = base(passed); report.addProperty("phase", ledger.getString("Phase"));
        report.addProperty("depth", ledger.getInt("Depth")); report.addProperty("motion_tick", ledger.getInt("MotionTick"));
        report.addProperty("journey_uuid", ledger.getUUID("Journey").toString());
        if (isRoundtrip())
        {
            report.add("completed_new_plan_legs", completedLegs); report.addProperty("new_ground_contract2_roundtrip_passed", completedLegs.size() == 2);
            report.addProperty("original_journal_bytes_retained", true); report.addProperty("current_journal_count", retainedJournals.size());
        }
        if (input.get("mode").getAsString().equals("relogin"))
        {
            verifyRetainedJournals(); report.addProperty("settled_relogin_passed", true); report.addProperty("request_issued", false);
            report.addProperty("original_journal_bytes_retained", true);
        }
        write(marker, report); done = true;
        if (input.has("stop_server_when_done") && input.get("stop_server_when_done").getAsBoolean())
        {
            // Normal integrated/dedicated save/close, never process kill. Only
            // explicitly scheduled native jobs can request this checkpoint.
            var server = net.minecraftforge.server.ServerLifecycleHooks.getCurrentServer();
            if (server != null) server.halt(false);
        }
    }
    private static void write(String marker, JsonObject report) throws Exception
    {
        if (input == null) return;
        Path path = Path.of(input.get("output").getAsString()); Files.createDirectories(path);
        Files.writeString(path.resolve(marker + ".json"), new GsonBuilder().setPrettyPrinting().create().toJson(report));
    }
}

package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.google.gson.GsonBuilder;
import com.projectseele.ProjectSeele;
import java.io.InputStream;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;

/** Full cold admission is a blocking MOD setup barrier before any world opens. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD)
public final class CityAtomicCandidateBindingR45
{
    private static volatile boolean preworldAdmitted;
    private static String admittedHash;
    private static Path admittedWorld;
    private static Path admittedFile;
    private static String admittedUUID;
    private static long admittedSeed;
    private CityAtomicCandidateBindingR45() {}

    public static boolean candidateLeaseReady(Path world)
    {
        try { return preworldAdmitted && world.toRealPath().equals(admittedWorld); }
        catch (Exception failure) { throw new IllegalStateException("Exact cold candidate lease is not ready", failure); }
    }

    public static boolean admit(Path world, JsonObject job)
    {
        if (!job.has("candidate_binding"))
        {
            if (!world.getFileName().toString().equals("SEELE_FIELD_R45_REVIEW"))
                throw new IllegalStateException("Legacy native job requires its original review directory");
            return true;
        }
        try
        {
            Path file = Path.of(job.get("candidate_binding").getAsString()).toRealPath();
            String expected = job.get("candidate_binding_sha256").getAsString();
            Path actualWorld = world.toRealPath();
            if (!preworldAdmitted) throw new IllegalStateException("No pre-world MOD admission; opened worlds cannot acquire a late cold lease");
            if (!expected.equals(admittedHash) || !actualWorld.equals(admittedWorld) || !file.equals(admittedFile)
                    || !admittedUUID.equals(job.get("world_id").getAsString()) || admittedSeed != job.get("world_seed").getAsLong())
                throw new IllegalStateException("Another candidate cannot reuse the original city binding");
            return true;
        }
        catch (Exception failure) { throw new IllegalStateException("Cold City96 candidate binding refused before city preparation", failure); }
    }

    @SubscribeEvent
    public static void setup(FMLCommonSetupEvent event)
    {
        String declared = System.getProperty("projectseele.nativeCandidateBindingR45", "");
        String expected = System.getProperty("projectseele.nativeCandidateBindingR45SHA256", "");
        String output = System.getProperty("projectseele.nativeCandidateAdmissionR45", "");
        if (declared.isEmpty() && expected.isEmpty() && output.isEmpty()) return;
        JsonObject receipt = new JsonObject();
        receipt.addProperty("schema", "projectseele.native-preworld-admission-r45.v1");
        receipt.addProperty("phase", "FML_COMMON_SETUP_BEFORE_WORLD_OPEN");
        receipt.addProperty("passed", false); receipt.addProperty("world_written", false);
        long started = System.nanoTime(); Path destination = null;
        try
        {
            if (declared.isEmpty() || !expected.matches("[0-9a-f]{64}") || output.isEmpty())
                throw new IllegalStateException("All three exact pre-world admission properties are required");
            Path file = Path.of(declared).toRealPath();
            JsonObject binding = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            Path world = Path.of(binding.get("world").getAsString()).toRealPath();
            destination = Path.of(output).toAbsolutePath().normalize();
            if (!destination.equals(Path.of(binding.get("preworld_receipt_output").getAsString()).toAbsolutePath().normalize())
                    || destination.startsWith(world) || Files.exists(destination))
                throw new IllegalStateException("Use the exact new artifact receipt path outside the world");
            // Synchronous handler return is the initialization barrier. No server tick may re-hash a running save.
            validate(world, file, expected);
            admittedFile = file; admittedWorld = world; admittedHash = expected;
            admittedUUID = binding.get("world_id").getAsString(); admittedSeed = binding.get("world_seed").getAsLong();
            receipt.addProperty("binding", file.toString()); receipt.addProperty("binding_sha256", expected);
            receipt.addProperty("world", world.toString()); receipt.addProperty("world_id", admittedUUID); receipt.addProperty("world_seed", admittedSeed);
            receipt.addProperty("world_files_checked", binding.getAsJsonArray("world_files").size());
            receipt.addProperty("source_epoch_files_checked", binding.getAsJsonArray("source_epoch").size());
            receipt.addProperty("runtime_code_source", CityAtomicCandidateBindingR45.class.getProtectionDomain().getCodeSource().getLocation().toString());
            receipt.addProperty("elapsed_ms", (System.nanoTime() - started) / 1_000_000.0);
            receipt.addProperty("passed", true); writeReceipt(destination, receipt); preworldAdmitted = true;
        }
        catch (Exception failure)
        {
            receipt.addProperty("error", failure.toString()); receipt.addProperty("elapsed_ms", (System.nanoTime() - started) / 1_000_000.0);
            try { if (destination != null && !Files.exists(destination)) writeReceipt(destination, receipt); }
            catch (Exception receiptFailure) { failure.addSuppressed(receiptFailure); }
            throw new IllegalStateException("Pre-world candidate admission failed; world opening is not authorized", failure);
        }
    }

    private static void writeReceipt(Path destination, JsonObject receipt) throws Exception
    {
        Files.createDirectories(destination.getParent());
        Path temporary = Files.createTempFile(destination.getParent(), destination.getFileName().toString(), ".pending");
        byte[] bytes = new GsonBuilder().setPrettyPrinting().create().toJson(receipt).getBytes(StandardCharsets.UTF_8);
        try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.WRITE))
        {
            java.nio.ByteBuffer buffer = java.nio.ByteBuffer.wrap(bytes);
            while (buffer.hasRemaining()) channel.write(buffer);
            channel.force(true);
        }
        Files.move(temporary, destination, StandardCopyOption.ATOMIC_MOVE);
    }

    /** Shared devices use the same explicit cold lease, UUID and seed guard. */
    public static boolean admit(ServerLevel level, JsonObject job)
    {
        if (!job.has("candidate_binding")) throw new IllegalStateException("An explicit shared QA binding is required");
        try
        {
            Path world = level.getServer().getWorldPath(LevelResource.ROOT).toRealPath();
            if (!world.equals(Path.of(job.get("world").getAsString()).toRealPath())
                    || level.getSeed() != job.get("world_seed").getAsLong()
                    || !Tokyo3BuildingWorldIdentityR44.get(level).equals(job.get("world_id").getAsString()))
                throw new IllegalStateException("Shared QA world path/UUID/seed differs");
            return admit(world, job);
        }
        catch (Exception failure) { throw new IllegalStateException("Shared QA native lease refused", failure); }
    }

    private static void validate(Path world, Path file, String expected) throws Exception
    {
        if (!hash(file).equals(expected)) throw new IllegalStateException("Candidate binding bytes changed");
        JsonObject binding = JsonParser.parseString(Files.readString(file)).getAsJsonObject();
        String schema = binding.get("schema").getAsString();
        boolean copied = ("projectseele.city-atomic-native-binding-r45.v2".equals(schema)
                || "projectseele.city-atomic-native-binding-r45.v3".equals(schema)) && binding.get("qa_copy").getAsBoolean();
        if (!("projectseele.city-atomic-native-binding-r45.v1".equals(schema) || copied)
                || !binding.get("composition_complete").getAsBoolean()
                || !binding.get("installed_disabled").getAsBoolean()
                || binding.get("runtime_enabled").getAsBoolean()
                || !world.equals(Path.of(binding.get("world").getAsString()).toRealPath())
                || !copied && (!world.getFileName().toString().equals("world")
                || !world.getParent().getParent().getFileName().toString().equals("composition_candidates")))
            throw new IllegalStateException("Only the exact complete, installed-disabled candidate is admitted");
        if (copied) validateCopy(world, binding);
        check(binding.getAsJsonObject("composition_receipt"));
        check(binding.getAsJsonObject("binding_plan"));
        check(binding.getAsJsonObject("metadata_wal"));
        check(binding.getAsJsonObject("root_static_proof"));
        for (var raw : binding.getAsJsonArray("source_epoch")) check(raw.getAsJsonObject());
        java.util.Set<String> targets = new java.util.HashSet<>();
        for (var raw : binding.getAsJsonArray("world_files"))
        {
            JsonObject row = raw.getAsJsonObject();
            String relative = row.get("relative").getAsString();
            Path target = world.resolve(relative).normalize();
            if (!target.startsWith(world) || !targets.add(relative) || !Files.isRegularFile(target)
                    || !hash(target).equals(row.get("sha256").getAsString()))
                throw new IllegalStateException("Candidate full file/progress epoch changed: " + relative);
        }
        try (var files = Files.walk(world))
        {
            for (Path target : files.filter(Files::isRegularFile).toList())
            {
                String relative = world.relativize(target).toString().replace('\\', '/');
                if (!relative.equals("session.lock") && !targets.contains(relative))
                    throw new IllegalStateException("Unexpected candidate file: " + relative);
            }
        }
    }

    private static void validateCopy(Path world, JsonObject binding) throws Exception
    {
        check(binding.getAsJsonObject("copy_receipt"));
        check(binding.getAsJsonObject("runtime_revision"));
        check(binding.getAsJsonObject("runtime_compiled_proof"));
        JsonObject receipt = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("copy_receipt").get("path").getAsString()))).getAsJsonObject();
        check(receipt.getAsJsonObject("copy_plan"));
        check(receipt.getAsJsonObject("source_binding"));
        if (!"projectseele.city-r45-qa-copy-receipt.v1".equals(receipt.get("schema").getAsString())
                || !receipt.get("copy_complete").getAsBoolean() || receipt.get("source_written").getAsBoolean()
                || !"QA_ONLY".equals(receipt.get("role").getAsString())
                || !world.equals(Path.of(receipt.get("target_world").getAsString()).toAbsolutePath().normalize())
                || !world.equals(Path.of(binding.get("world").getAsString()).toAbsolutePath().normalize())
                || !Files.isDirectory(world, java.nio.file.LinkOption.NOFOLLOW_LINKS)
                || !world.getFileName().toString().equals("SEELE_FIELD_R45_REVIEW")
                || !world.getParent().getFileName().toString().equals("saves")
                || !world.getParent().getParent().getFileName().toString().equals("gameDir")
                || !world.getParent().getParent().getParent().getFileName().toString().equals("native_candidate_session_v2")
                || !receipt.get("world_id").getAsString().equals(binding.get("world_id").getAsString())
                || receipt.get("world_seed").getAsLong() != binding.get("world_seed").getAsLong())
            throw new IllegalStateException("Only the exact normal physical v2 QA copy is admitted");
        java.util.Map<String, String> copiedFiles = new java.util.TreeMap<>();
        for (var raw : receipt.getAsJsonArray("files"))
        {
            JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString();
            String source = row.get("source_sha256").getAsString(), target = row.get("target_sha256").getAsString();
            if (!source.equals(target) || copiedFiles.put(relative, target) != null)
                throw new IllegalStateException("Whole QA copy source/target bytes differ or duplicate");
        }
        if (!copiedFiles.containsKey("session.lock")) throw new IllegalStateException("The whole-copy receipt lacks its original lock bytes");
        copiedFiles.remove("session.lock");
        java.util.Map<String, String> leaseFiles = new java.util.TreeMap<>();
        for (var raw : binding.getAsJsonArray("world_files"))
        {
            JsonObject row = raw.getAsJsonObject();
            if (leaseFiles.put(row.get("relative").getAsString(), row.get("sha256").getAsString()) != null)
                throw new IllegalStateException("Duplicate QA lease file");
        }
        if (binding.has("qa_ground_compensated_checkpoint"))
        {
            if (binding.has("qa_checkpoint") || binding.has("qa_inflight_checkpoint") || binding.has("qa_settled_checkpoint") || binding.has("qa_inflight_move1_checkpoint"))
                throw new IllegalStateException("Ground compensation must use its own unique authority");
            verifyGroundCompensatedMove1(world, binding.getAsJsonObject("qa_ground_compensated_checkpoint"), binding.get("world_id").getAsString());
            JsonObject checkpoint = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("qa_ground_compensated_checkpoint").get("path").getAsString()))).getAsJsonObject();
            java.util.Map<String, String> current = new java.util.TreeMap<>();
            for (var raw : checkpoint.getAsJsonArray("current_files"))
            { JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString(); if (!relative.equals("session.lock") && current.put(relative,row.get("sha256").getAsString()) != null) throw new IllegalStateException("Duplicate compensated file"); }
            if (!current.equals(leaseFiles)) throw new IllegalStateException("Compensated lease differs from its exact current checkpoint");
        }
        else if (binding.has("qa_inflight_move1_checkpoint"))
        {
            if (binding.has("qa_checkpoint") || binding.has("qa_inflight_checkpoint") || binding.has("qa_settled_checkpoint"))
                throw new IllegalStateException("MOVE1 cannot combine another City checkpoint authority");
            verifyInFlightMove1(world, binding.getAsJsonObject("qa_inflight_move1_checkpoint"), binding.get("world_id").getAsString());
            JsonObject checkpoint = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("qa_inflight_move1_checkpoint").get("path").getAsString()))).getAsJsonObject();
            java.util.Map<String, String> current = new java.util.TreeMap<>();
            for (var raw : checkpoint.getAsJsonArray("current_files"))
            {
                JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString();
                if (!relative.equals("session.lock") && current.put(relative, row.get("sha256").getAsString()) != null)
                    throw new IllegalStateException("Duplicate MOVE1 checkpoint file");
            }
            if (!current.equals(leaseFiles)) throw new IllegalStateException("Lease differs from the exact original MOVE1 checkpoint");
        }
        else if (binding.has("qa_settled_checkpoint"))
        {
            if (binding.has("qa_checkpoint") || binding.has("qa_inflight_checkpoint"))
                throw new IllegalStateException("Settled endpoint, READY and unplaced authorities cannot be combined");
            verifySettledEndpoint0(world, binding.getAsJsonObject("qa_settled_checkpoint"), binding.get("world_id").getAsString());
            JsonObject checkpoint = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("qa_settled_checkpoint").get("path").getAsString()))).getAsJsonObject();
            java.util.Map<String, String> current = new java.util.TreeMap<>();
            for (var raw : checkpoint.getAsJsonArray("current_files"))
            {
                JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString();
                if (!relative.equals("session.lock") && current.put(relative, row.get("sha256").getAsString()) != null)
                    throw new IllegalStateException("Duplicate settled endpoint checkpoint file");
            }
            if (!current.equals(leaseFiles)) throw new IllegalStateException("Lease differs from the exact finite settled endpoint checkpoint");
        }
        else if (binding.has("qa_inflight_checkpoint"))
        {
            if (binding.has("qa_checkpoint")) throw new IllegalStateException("READY and unplaced checkpoint authorities cannot be combined");
            verifyInFlightReady(world, binding.getAsJsonObject("qa_inflight_checkpoint"), binding.get("world_id").getAsString());
            JsonObject checkpoint = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("qa_inflight_checkpoint").get("path").getAsString()))).getAsJsonObject();
            java.util.Map<String, String> current = new java.util.TreeMap<>();
            for (var raw : checkpoint.getAsJsonArray("current_files"))
            {
                JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString();
                if (!relative.equals("session.lock") && current.put(relative, row.get("sha256").getAsString()) != null)
                    throw new IllegalStateException("Duplicate in-flight checkpoint file");
            }
            if (!current.equals(leaseFiles)) throw new IllegalStateException("Lease differs from exact READY/full96 checkpoint");
        }
        else if (binding.has("qa_checkpoint"))
        {
            check(binding.getAsJsonObject("qa_checkpoint"));
            JsonObject checkpoint = JsonParser.parseString(Files.readString(Path.of(binding.getAsJsonObject("qa_checkpoint").get("path").getAsString()))).getAsJsonObject();
            check(checkpoint.getAsJsonObject("original_copy_receipt"));
            if (!"projectseele.city-qa-cold-checkpoint-r45.v1".equals(checkpoint.get("schema").getAsString())
                    || !checkpoint.get("source1736_exact").getAsBoolean() || !checkpoint.get("complete_city_cargo_pass").getAsBoolean()
                    || !checkpoint.get("complete_static2859160_pass").getAsBoolean() || !checkpoint.get("complete_metadata807_pass").getAsBoolean()
                    || !(checkpoint.get("no_city_control_or_moving_owner").getAsBoolean() || checkpoint.has("unplaced_fault_proof"))
                    || !checkpoint.get("candidate_disabled").getAsBoolean() || checkpoint.get("depth").getAsInt() != 312
                    || !world.equals(Path.of(checkpoint.get("world").getAsString()).toAbsolutePath().normalize()))
                throw new IllegalStateException("QA changed without the complete named City96 cold checkpoint");
            if (checkpoint.has("unplaced_fault_proof"))
            {
                if (checkpoint.get("no_city_control_or_moving_owner").getAsBoolean()
                        || !(checkpoint.has("no_moving_city_owner") ? checkpoint.get("no_moving_city_owner").getAsBoolean()
                            : checkpoint.get("no_moving_owner_or_durable_city_journal").getAsBoolean())
                        || checkpoint.has("no_moving_city_owner") && !checkpoint.get("complete_ground34881_pass").getAsBoolean())
                    throw new IllegalStateException("Unplaced fault cannot be described as absent city control");
                verifyUnplacedFault(world, checkpoint.getAsJsonObject("unplaced_fault_proof"), binding.get("world_id").getAsString());
            }
            java.util.Map<String, String> current = new java.util.TreeMap<>();
            for (var raw : checkpoint.getAsJsonArray("current_files"))
            {
                JsonObject row = raw.getAsJsonObject(); String relative = row.get("relative").getAsString();
                if (!relative.equals("session.lock") && current.put(relative, row.get("sha256").getAsString()) != null)
                    throw new IllegalStateException("Duplicate cold checkpoint file");
            }
            if (!current.equals(leaseFiles)) throw new IllegalStateException("The lease differs from its exact new QA checkpoint");
        }
        else if (!copiedFiles.equals(leaseFiles)) throw new IllegalStateException("The QA lease omits full source-copy files");
    }

    /** Exact failed native downward MOVE1; all original owners/journals survive, never a READY0/new request. */
    public static void verifyInFlightMove1(Path world, JsonObject evidence, String worldUUID) throws Exception
    {
        check(evidence);
        JsonObject proof = JsonParser.parseString(Files.readString(Path.of(evidence.get("path").getAsString()))).getAsJsonObject();
        boolean finite="projectseele.city-qa-cold-inflight-motion-checkpoint-r45.v2".equals(proof.get("schema").getAsString());
        int motion=finite ? proof.get("MotionTick").getAsInt() : 1;
        int from=finite ? proof.get("source_depth").getAsInt() : 0, to=312-from;
        int total=finite ? proof.get("original_journal_count").getAsInt() : 254;
        if ((from!=0 && from!=312) || motion<1 || motion>=724 || total<254 || (total-62)%96!=0) throw new IllegalStateException("Invalid complete finite MOVE checkpoint");
        if (!(finite || "projectseele.city-qa-cold-inflight-move1-checkpoint-r45.v1".equals(proof.get("schema").getAsString()))
                || !"QA_ONLY".equals(proof.get("role").getAsString()) || !world.equals(Path.of(proof.get("world").getAsString()).toRealPath())
                || !worldUUID.equals(proof.get("world_id").getAsString()) || !"MOVE".equals(proof.get("phase").getAsString())
                || proof.get("MotionTick").getAsInt() != motion || proof.get("source_depth").getAsInt() != from || proof.get("target_depth").getAsInt() != to
                || proof.get("Created").getAsInt() != 96 || proof.get("SavedPlans").getAsInt() != 96
                || proof.get("full_cargo_cells").getAsInt() != 749242 || proof.get("full_BE").getAsInt() != 1471
                || proof.get("original_actor_ids").getAsInt() != 897 || proof.get("current_actor_ids").getAsInt() != 993)
            throw new IllegalStateException("Not the exact native downward MOVE1 transaction");
        for (String key : new String[]{"source1736_exact", finite ? "all_original_journal_bytes_retained" : "all254_original_journal_bytes_retained", "all96_actual_owner_full_cargo_NBT_equal",
                "complete_static2859160_and_owned_prefix_passed", "complete_metadata807_passed", "original_actor_ids_preserved", "no_unplaced_fault_recovery", "no_QA_progress_for_delivery"})
            if (!proof.get(key).getAsBoolean()) throw new IllegalStateException("Missing strict MOVE1 audit: " + key);
        for (String key : new String[]{"frozen_move1_authority", "frozen_control", "complete_static_and_prefix_readback", "original_copy_receipt", finite ? "native_process_receipt" : "native_failed", "actor_identity_readback"})
            check(proof.getAsJsonObject(key));
        JsonObject frozen = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("frozen_move1_authority").get("path").getAsString()))).getAsJsonObject();
        if (!(finite ? "projectseele.city-Ground2-MOVE591-frozen-authority-r45.v2".equals(frozen.get("schema").getAsString())
                    && frozen.get("phase").getAsString().equals("MOVE") && frozen.get("MotionTick").getAsInt()==motion
                    && frozen.get("source_depth").getAsInt()==from && frozen.get("target_depth").getAsInt()==to
                    : "projectseele.city-failed-retraction-MOVE1-cold-authority-r45.v1".equals(frozen.get("schema").getAsString()))
                || !frozen.get("journey_uuid").equals(proof.get("journey_uuid")) || !frozen.get("Progress").equals(proof.get("Progress")))
            throw new IllegalStateException("MOVE1 is not the preserved native failure authority");
        if (finite)
        {
            JsonObject process=JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("native_process_receipt").get("path").getAsString()))).getAsJsonObject();
            if (process.get("process_exit").getAsInt()!=0 || process.get("forced_termination").getAsBoolean()
                    || process.get("complete_present").getAsBoolean() || process.get("failure_present").getAsBoolean())
                throw new IllegalStateException("Finite MOVE authority must preserve the actual normally saved incomplete process");
        }
        if (!proof.get("original96_owner_snapshots").equals(frozen.get("owners96")))
            throw new IllegalStateException("MOVE1 owner snapshots/partial poses differ from their original frozen failure");
        java.util.Map<String, JsonObject> frozenJournals = new java.util.HashMap<>();
        for (var raw : frozen.getAsJsonArray(finite ? "journals350" : "journals254"))
        { JsonObject row = raw.getAsJsonObject(); frozenJournals.put(row.getAsJsonObject("current").get("path").getAsString(), row); }
        if (frozenJournals.size() != total) throw new IllegalStateException("Frozen MOVE1 must retain all254 original journal references");
        JsonObject staticReadback = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("complete_static_and_prefix_readback").get("path").getAsString()))).getAsJsonObject();
        if (staticReadback.get("base_static_rows").getAsInt() != 2859160 || staticReadback.getAsJsonArray("errors").size() != 0)
            throw new IllegalStateException("MOVE1 full physical static/prefix readback failed");
        Path data = world.resolve("dimensions/projectseele/geofront/data"); JsonObject control = proof.getAsJsonObject("current_control"); check(control);
        Path file = data.resolve("projectseele_city_rigid_control_r45_8246338109520.dat").toRealPath();
        if (!file.equals(Path.of(control.get("path").getAsString()).toRealPath())
                || !control.get("sha256").equals(proof.getAsJsonObject("frozen_control").get("sha256"))
                || !control.get("sha256").equals(frozen.getAsJsonObject("control_frozen").get("sha256")))
            throw new IllegalStateException("Original MOVE1 control bytes/path changed");
        var root = net.minecraft.nbt.NbtIo.readCompressed(file.toFile());
        if (!root.equals(net.minecraft.nbt.TagParser.parseTag(control.get("complete_typed_snbt").getAsString()))
                || !control.get("complete_typed_snbt").equals(frozen.get("complete_typed_snbt")))
            throw new IllegalStateException("Complete typed original MOVE1 NBT changed");
        var tag = root.getCompound("data");
        for (String key : new String[]{"Version", "SavedPlans", "Created", "Index", "Cursor", "MotionTick", "Depth", "JourneySourceDepth", "Target", "JourneyTargetDepth", "Queued"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_INT)) throw new IllegalStateException("Missing typed MOVE1 integer: " + key);
        for (String key : new String[]{"WorldUUID", "MotionProfile", "Phase", "Fault", "QueueFault"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_STRING)) throw new IllegalStateException("Missing typed MOVE1 string: " + key);
        for (String key : new String[]{"WorldTouched", "Rollback", "AllowMissingRecovery"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_BYTE)) throw new IllegalStateException("Missing typed MOVE1 flag: " + key);
        if (!root.contains("DataVersion", net.minecraft.nbt.Tag.TAG_INT) || !tag.contains("Origin", net.minecraft.nbt.Tag.TAG_LONG)
                || !tag.contains("Progress", net.minecraft.nbt.Tag.TAG_DOUBLE) || !tag.contains("Journey", net.minecraft.nbt.Tag.TAG_INT_ARRAY)
                || tag.getIntArray("Journey").length != 4 || tag.getInt("Version") != 1 || !"c1_trapezoid_v1".equals(tag.getString("MotionProfile")))
            throw new IllegalStateException("Incomplete native MOVE1 typed authority");
        if (!worldUUID.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != 8246338109520L
                || !"MOVE".equals(tag.getString("Phase")) || tag.getInt("Depth") != from || tag.getInt("Target") != to
                || tag.getInt("JourneySourceDepth") != from || tag.getInt("JourneyTargetDepth") != to || tag.getInt("MotionTick") != motion
                || tag.getInt("SavedPlans") != 96 || tag.getInt("Created") != 96 || tag.getInt("Index") != 0 || tag.getInt("Cursor") != 0
                || tag.getInt("Queued") != -1 || tag.getByte("WorldTouched") != 1 || tag.getBoolean("Rollback") || tag.getBoolean("AllowMissingRecovery")
                || !tag.getString("Fault").isEmpty() || !tag.getUUID("Journey").toString().equals(proof.get("journey_uuid").getAsString())
                || tag.getDouble("Progress") != proof.get("Progress").getAsDouble() || tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).size() != 96)
            throw new IllegalStateException("MOVE1 cannot be replaced by a READY or settled ledger");
        var plans = proof.getAsJsonArray("current_original96_journals"); var owners = proof.getAsJsonArray("original96_owner_snapshots");
        var old = proof.getAsJsonArray(finite ? "retained_original_journals" : "retained_original158_journals");
        if (plans.size() != 96 || owners.size() != 96 || old.size() != total-96) throw new IllegalStateException("All254 journals/full96 original owners required");
        java.util.Set<Path> expected = new java.util.HashSet<>(); java.util.Set<java.util.UUID> ownerIDs = new java.util.HashSet<>(); int cells = 0, bes = 0;
        for (int index = 0; index < 96; index++)
        {
            JsonObject row = plans.get(index).getAsJsonObject(); check(row.getAsJsonObject("current")); check(row.getAsJsonObject("frozen_original"));
            JsonObject frozenRow = frozenJournals.get(row.getAsJsonObject("current").get("path").getAsString());
            if (frozenRow == null || !row.get("current").equals(frozenRow.get("current")) || !row.get("frozen_original").equals(frozenRow.get("frozen_original")))
                throw new IllegalStateException("MOVE1 new96 journal differs from its frozen original authority");
            Path path = data.resolve("city_rigid_journal_r45").resolve(tag.getUUID("Journey").toString()).resolve(index+".dat").toRealPath();
            String digest = tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).getString(index);
            if (row.get("index").getAsInt() != index || !path.equals(Path.of(row.getAsJsonObject("current").get("path").getAsString()).toRealPath())
                    || !digest.equals(row.getAsJsonObject("current").get("sha256").getAsString())
                    || !digest.equals(row.getAsJsonObject("frozen_original").get("sha256").getAsString()))
                throw new IllegalStateException("MOVE1 original plan order/bytes changed");
            var plan = net.minecraft.nbt.NbtIo.readCompressed(path.toFile());
            if (plan.getInt("Index") != index || !worldUUID.equals(plan.getString("WorldUUID")) || plan.getLong("Origin") != 8246338109520L
                    || !plan.getUUID("Journey").equals(tag.getUUID("Journey"))) throw new IllegalStateException("Foreign MOVE1 journal");
            if (finite && (!plan.contains("GroundContract", net.minecraft.nbt.Tag.TAG_INT) || plan.getInt("GroundContract")!=2
                    || plan.getInt("InitialWorldImageCount")<=0 || !plan.getString("InitialWorldImageSHA256").matches("[0-9a-f]{64}")))
                throw new IllegalStateException("The new actual MOVE generation must retain full GroundContract2 source-image authority");
            JsonObject actor = owners.get(index).getAsJsonObject(); check(actor.getAsJsonObject("full_entity_snapshot"));
            var entity = net.minecraft.nbt.NbtIo.readCompressed(Path.of(actor.getAsJsonObject("full_entity_snapshot").get("path").getAsString()).toFile());
            var owner = plan.getUUID("Owner");
            if (actor.get("index").getAsInt() != index || !actor.get("owner_uuid").getAsString().equals(owner.toString()) || !entity.getUUID("UUID").equals(owner)
                    || !ownerIDs.add(owner) || !"create:contraption".equals(entity.getString("id"))
                    || !entity.getCompound("ForgeData").getUUID("R45CityJourney").equals(tag.getUUID("Journey")) || !entity.getList("Passengers", net.minecraft.nbt.Tag.TAG_COMPOUND).isEmpty())
                throw new IllegalStateException("MOVE1 original owner identity/occupancy changed");
            var position = entity.getList("Pos", net.minecraft.nbt.Tag.TAG_DOUBLE);
            for (int axis = 0; axis < 3; axis++) if (position.getDouble(axis) != actor.getAsJsonArray("position").get(axis).getAsDouble())
                throw new IllegalStateException("MOVE1 original partial pose changed");
            var originalCells = plan.getList("Cells", net.minecraft.nbt.Tag.TAG_COMPOUND); var cargo = new net.minecraft.nbt.ListTag(); int be = 0;
            for (var raw : originalCells)
            { var cell = ((net.minecraft.nbt.CompoundTag)raw).copy(); if (cell.contains("Data", net.minecraft.nbt.Tag.TAG_COMPOUND)) { cell.put("NBT", cell.getCompound("Data").copy()); be++; } cargo.add(cell); }
            var building = new net.minecraft.nbt.CompoundTag(); building.put("Cargo", cargo);
            CityCreateCargoR45.verify(new CityCreateCargoR45.Cargo(building, cargo.size(), be), entity.getCompound("Contraption"));
            cells += cargo.size(); bes += be; expected.add(path);
        }
        for (var raw : old)
        {
            JsonObject row = raw.getAsJsonObject(); check(row.getAsJsonObject("current")); check(row.getAsJsonObject("frozen_original"));
            JsonObject frozenRow = frozenJournals.get(row.getAsJsonObject("current").get("path").getAsString());
            if (frozenRow == null || !row.get("current").equals(frozenRow.get("current")) || !row.get("frozen_original").equals(frozenRow.get("frozen_original")))
                throw new IllegalStateException("MOVE1 old158 journal differs from its frozen original authority");
            Path path = Path.of(row.getAsJsonObject("current").get("path").getAsString()).toRealPath();
            if (!row.getAsJsonObject("current").get("sha256").equals(row.getAsJsonObject("frozen_original").get("sha256"))
                    || !path.startsWith(data.resolve("city_rigid_journal_r45").toRealPath()) || !expected.add(path))
                throw new IllegalStateException("Original158 history was lost/changed/duplicated");
        }
        java.util.Set<Path> actual = new java.util.HashSet<>();
        try (var files = Files.walk(data.resolve("city_rigid_journal_r45"))) { for (Path path : files.filter(Files::isRegularFile).toList()) actual.add(path.toRealPath()); }
        if (cells != 749242 || bes != 1471 || !actual.equals(expected)) throw new IllegalStateException("MOVE1 complete254/full cargo membership changed");
        JsonObject actors = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("actor_identity_readback").get("path").getAsString()))).getAsJsonObject();
        var originals = actors.getAsJsonObject("original_uuid_to_type"); var current = actors.getAsJsonObject("current_uuid_to_type");
        if (originals.size() != 897 || current.size() != 993) throw new IllegalStateException("MOVE1 all-dimension actor counts changed");
        for (var entry : originals.entrySet()) if (!entry.getValue().equals(current.get(entry.getKey())))
            throw new IllegalStateException("MOVE1 lost/replaced an original actor identity");
        java.util.Set<String> added = new java.util.HashSet<>(current.keySet()); added.removeAll(originals.keySet());
        if (!added.equals(ownerIDs.stream().map(java.util.UUID::toString).collect(java.util.stream.Collectors.toSet())))
            throw new IllegalStateException("MOVE1 contains actors beyond its original897 and original96 owners");
    }

    /** Explicit Ground-compensated original MOVE1. */
    public static void verifyGroundCompensatedMove1(Path world, JsonObject evidence, String worldUUID) throws Exception
    {
        check(evidence);
        JsonObject proof = JsonParser.parseString(Files.readString(Path.of(evidence.get("path").getAsString()))).getAsJsonObject();
        if (!"projectseele.city-qa-cold-ground-compensated-move1-checkpoint-r45.v1".equals(proof.get("schema").getAsString())
                || !"QA_ONLY".equals(proof.get("role").getAsString()) || !world.equals(Path.of(proof.get("world").getAsString()).toRealPath())
                || !worldUUID.equals(proof.get("world_id").getAsString()) || !"MOVE".equals(proof.get("phase").getAsString())
                || proof.get("MotionTick").getAsInt() != 1 || proof.get("source_depth").getAsInt() != 0 || proof.get("target_depth").getAsInt() != 312
                || proof.get("Created").getAsInt() != 96 || proof.get("SavedPlans").getAsInt() != 96
                || proof.get("full_cargo_cells").getAsInt() != 749242 || proof.get("full_BE").getAsInt() != 1471
                || proof.get("original_actor_ids").getAsInt() != 897 || proof.get("current_actor_ids").getAsInt() != 993)
            throw new IllegalStateException("Not the exact native downward MOVE1 transaction");
        for (String key : new String[]{"source1736_exact", "all254_original_journal_bytes_retained", "all96_actual_owner_full_cargo_NBT_equal",
                "complete_static2859160_and_owned_prefix_passed", "complete_metadata807_passed", "original_actor_ids_preserved", "no_unplaced_fault_recovery", "no_QA_progress_for_delivery"})
            if (!proof.get(key).getAsBoolean()) throw new IllegalStateException("Missing strict MOVE1 audit: " + key);
        for (String key : new String[]{"frozen_move1_authority", "frozen_control", "complete_static_and_prefix_readback", "original_copy_receipt", "native_failed", "actor_identity_readback"})
            check(proof.getAsJsonObject(key));
        verifyExactGroundCompensation(world, proof);
        JsonObject frozen = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("frozen_move1_authority").get("path").getAsString()))).getAsJsonObject();
        if (!"projectseele.city-ground-compensated-MOVE1-cold-authority-r45.v1".equals(frozen.get("schema").getAsString())
                || !frozen.get("journey_uuid").equals(proof.get("journey_uuid")) || !frozen.get("Progress").equals(proof.get("Progress")))
            throw new IllegalStateException("MOVE1 is not the preserved native failure authority");
        if (!proof.get("original96_owner_snapshots").equals(frozen.get("owners96")))
            throw new IllegalStateException("MOVE1 owner snapshots/partial poses differ from their original frozen failure");
        java.util.Map<String, JsonObject> frozenJournals = new java.util.HashMap<>();
        for (var raw : frozen.getAsJsonArray("journals254"))
        { JsonObject row = raw.getAsJsonObject(); frozenJournals.put(row.getAsJsonObject("current").get("path").getAsString(), row); }
        if (frozenJournals.size() != 254) throw new IllegalStateException("Frozen MOVE1 must retain all254 original journal references");
        JsonObject staticReadback = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("complete_static_and_prefix_readback").get("path").getAsString()))).getAsJsonObject();
        if (staticReadback.get("base_static_rows").getAsInt() != 2859160 || staticReadback.getAsJsonArray("errors").size() != 0)
            throw new IllegalStateException("MOVE1 full physical static/prefix readback failed");
        Path data = world.resolve("dimensions/projectseele/geofront/data"); JsonObject control = proof.getAsJsonObject("current_control"); check(control);
        Path file = data.resolve("projectseele_city_rigid_control_r45_8246338109520.dat").toRealPath();
        if (!file.equals(Path.of(control.get("path").getAsString()).toRealPath())
                || !control.get("sha256").equals(proof.getAsJsonObject("frozen_control").get("sha256"))
                || !control.get("sha256").equals(frozen.getAsJsonObject("control_frozen").get("sha256")))
            throw new IllegalStateException("Original MOVE1 control bytes/path changed");
        var root = net.minecraft.nbt.NbtIo.readCompressed(file.toFile());
        if (!root.equals(net.minecraft.nbt.TagParser.parseTag(control.get("complete_typed_snbt").getAsString()))
                || !control.get("complete_typed_snbt").equals(frozen.get("complete_typed_snbt")))
            throw new IllegalStateException("Complete typed original MOVE1 NBT changed");
        var tag = root.getCompound("data");
        for (String key : new String[]{"Version", "SavedPlans", "Created", "Index", "Cursor", "MotionTick", "Depth", "JourneySourceDepth", "Target", "JourneyTargetDepth", "Queued"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_INT)) throw new IllegalStateException("Missing typed MOVE1 integer: " + key);
        for (String key : new String[]{"WorldUUID", "MotionProfile", "Phase", "Fault", "QueueFault"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_STRING)) throw new IllegalStateException("Missing typed MOVE1 string: " + key);
        for (String key : new String[]{"WorldTouched", "Rollback", "AllowMissingRecovery"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_BYTE)) throw new IllegalStateException("Missing typed MOVE1 flag: " + key);
        if (!root.contains("DataVersion", net.minecraft.nbt.Tag.TAG_INT) || !tag.contains("Origin", net.minecraft.nbt.Tag.TAG_LONG)
                || !tag.contains("Progress", net.minecraft.nbt.Tag.TAG_DOUBLE) || !tag.contains("Journey", net.minecraft.nbt.Tag.TAG_INT_ARRAY)
                || tag.getIntArray("Journey").length != 4 || tag.getInt("Version") != 1 || !"c1_trapezoid_v1".equals(tag.getString("MotionProfile")))
            throw new IllegalStateException("Incomplete native MOVE1 typed authority");
        if (!worldUUID.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != 8246338109520L
                || !"MOVE".equals(tag.getString("Phase")) || tag.getInt("Depth") != 0 || tag.getInt("Target") != 312
                || tag.getInt("JourneySourceDepth") != 0 || tag.getInt("JourneyTargetDepth") != 312 || tag.getInt("MotionTick") != 1
                || tag.getInt("SavedPlans") != 96 || tag.getInt("Created") != 96 || tag.getInt("Index") != 0 || tag.getInt("Cursor") != 0
                || tag.getInt("Queued") != -1 || tag.getByte("WorldTouched") != 1 || tag.getBoolean("Rollback") || tag.getBoolean("AllowMissingRecovery")
                || !tag.getString("Fault").isEmpty() || !tag.getUUID("Journey").toString().equals(proof.get("journey_uuid").getAsString())
                || tag.getDouble("Progress") != proof.get("Progress").getAsDouble() || tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).size() != 96)
            throw new IllegalStateException("MOVE1 cannot be replaced by a READY or settled ledger");
        var plans = proof.getAsJsonArray("current_original96_journals"); var owners = proof.getAsJsonArray("original96_owner_snapshots");
        var old = proof.getAsJsonArray("retained_original158_journals");
        if (plans.size() != 96 || owners.size() != 96 || old.size() != 158) throw new IllegalStateException("All254 journals/full96 original owners required");
        java.util.Set<Path> expected = new java.util.HashSet<>(); java.util.Set<java.util.UUID> ownerIDs = new java.util.HashSet<>(); int cells = 0, bes = 0;
        for (int index = 0; index < 96; index++)
        {
            JsonObject row = plans.get(index).getAsJsonObject(); check(row.getAsJsonObject("current")); check(row.getAsJsonObject("frozen_original"));
            JsonObject frozenRow = frozenJournals.get(row.getAsJsonObject("current").get("path").getAsString());
            if (frozenRow == null || !row.get("current").equals(frozenRow.get("current")) || !row.get("frozen_original").equals(frozenRow.get("frozen_original")))
                throw new IllegalStateException("MOVE1 new96 journal differs from its frozen original authority");
            Path path = data.resolve("city_rigid_journal_r45").resolve(tag.getUUID("Journey").toString()).resolve(index+".dat").toRealPath();
            String digest = tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).getString(index);
            if (row.get("index").getAsInt() != index || !path.equals(Path.of(row.getAsJsonObject("current").get("path").getAsString()).toRealPath())
                    || !digest.equals(row.getAsJsonObject("current").get("sha256").getAsString())
                    || !digest.equals(row.getAsJsonObject("frozen_original").get("sha256").getAsString()))
                throw new IllegalStateException("MOVE1 original plan order/bytes changed");
            var plan = net.minecraft.nbt.NbtIo.readCompressed(path.toFile());
            if (plan.getInt("Index") != index || !worldUUID.equals(plan.getString("WorldUUID")) || plan.getLong("Origin") != 8246338109520L
                    || !plan.getUUID("Journey").equals(tag.getUUID("Journey"))) throw new IllegalStateException("Foreign MOVE1 journal");
            JsonObject actor = owners.get(index).getAsJsonObject(); check(actor.getAsJsonObject("full_entity_snapshot"));
            var entity = net.minecraft.nbt.NbtIo.readCompressed(Path.of(actor.getAsJsonObject("full_entity_snapshot").get("path").getAsString()).toFile());
            var owner = plan.getUUID("Owner");
            if (actor.get("index").getAsInt() != index || !actor.get("owner_uuid").getAsString().equals(owner.toString()) || !entity.getUUID("UUID").equals(owner)
                    || !ownerIDs.add(owner) || !"create:contraption".equals(entity.getString("id"))
                    || !entity.getCompound("ForgeData").getUUID("R45CityJourney").equals(tag.getUUID("Journey")) || !entity.getList("Passengers", net.minecraft.nbt.Tag.TAG_COMPOUND).isEmpty())
                throw new IllegalStateException("MOVE1 original owner identity/occupancy changed");
            var position = entity.getList("Pos", net.minecraft.nbt.Tag.TAG_DOUBLE);
            for (int axis = 0; axis < 3; axis++) if (position.getDouble(axis) != actor.getAsJsonArray("position").get(axis).getAsDouble())
                throw new IllegalStateException("MOVE1 original partial pose changed");
            var originalCells = plan.getList("Cells", net.minecraft.nbt.Tag.TAG_COMPOUND); var cargo = new net.minecraft.nbt.ListTag(); int be = 0;
            for (var raw : originalCells)
            { var cell = ((net.minecraft.nbt.CompoundTag)raw).copy(); if (cell.contains("Data", net.minecraft.nbt.Tag.TAG_COMPOUND)) { cell.put("NBT", cell.getCompound("Data").copy()); be++; } cargo.add(cell); }
            var building = new net.minecraft.nbt.CompoundTag(); building.put("Cargo", cargo);
            CityCreateCargoR45.verify(new CityCreateCargoR45.Cargo(building, cargo.size(), be), entity.getCompound("Contraption"));
            cells += cargo.size(); bes += be; expected.add(path);
        }
        for (var raw : old)
        {
            JsonObject row = raw.getAsJsonObject(); check(row.getAsJsonObject("current")); check(row.getAsJsonObject("frozen_original"));
            JsonObject frozenRow = frozenJournals.get(row.getAsJsonObject("current").get("path").getAsString());
            if (frozenRow == null || !row.get("current").equals(frozenRow.get("current")) || !row.get("frozen_original").equals(frozenRow.get("frozen_original")))
                throw new IllegalStateException("MOVE1 old158 journal differs from its frozen original authority");
            Path path = Path.of(row.getAsJsonObject("current").get("path").getAsString()).toRealPath();
            if (!row.getAsJsonObject("current").get("sha256").equals(row.getAsJsonObject("frozen_original").get("sha256"))
                    || !path.startsWith(data.resolve("city_rigid_journal_r45").toRealPath()) || !expected.add(path))
                throw new IllegalStateException("Original158 history was lost/changed/duplicated");
        }
        java.util.Set<Path> actual = new java.util.HashSet<>();
        try (var files = Files.walk(data.resolve("city_rigid_journal_r45"))) { for (Path path : files.filter(Files::isRegularFile).toList()) actual.add(path.toRealPath()); }
        if (cells != 749242 || bes != 1471 || !actual.equals(expected)) throw new IllegalStateException("MOVE1 complete254/full cargo membership changed");
        JsonObject actors = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("actor_identity_readback").get("path").getAsString()))).getAsJsonObject();
        var originals = actors.getAsJsonObject("original_uuid_to_type"); var current = actors.getAsJsonObject("current_uuid_to_type");
        if (originals.size() != 897 || current.size() != 993) throw new IllegalStateException("MOVE1 all-dimension actor counts changed");
        for (var entry : originals.entrySet()) if (!entry.getValue().equals(current.get(entry.getKey())))
            throw new IllegalStateException("MOVE1 lost/replaced an original actor identity");
        java.util.Set<String> added = new java.util.HashSet<>(current.keySet()); added.removeAll(originals.keySet());
        if (!added.equals(ownerIDs.stream().map(java.util.UUID::toString).collect(java.util.stream.Collectors.toSet())))
            throw new IllegalStateException("MOVE1 contains actors beyond its original897 and original96 owners");
    }

    /** Actual Root codec WAL is a distinct adjunct, not a rewritten original City journal. */
    private static void verifyExactGroundCompensation(Path world, JsonObject proof) throws Exception
    {
        JsonObject c = proof.getAsJsonObject("ground_compensation");
        for (String key : new String[]{"manifest", "codec_run", "root_actual_receipt", "before_files", "after_files", "complete_after_readback"}) check(c.getAsJsonObject(key));
        JsonObject run = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("codec_run").get("path").getAsString()))).getAsJsonObject();
        JsonObject receipt = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("root_actual_receipt").get("path").getAsString()))).getAsJsonObject();
        JsonObject afterRead = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("complete_after_readback").get("path").getAsString()))).getAsJsonObject();
        if (!"COMPLETE".equals(run.get("phase").getAsString()) || run.get("final_exact_cells").getAsInt() != 828
                || !run.get("all_exact_final_actual_voxels_and_nbt_readback").getAsBoolean() || run.getAsJsonArray("regions").size() != 2
                || !run.get("manifest_sha256").equals(c.getAsJsonObject("manifest").get("sha256"))
                || !receipt.get("codec_run_sha256").equals(c.getAsJsonObject("codec_run").get("sha256"))
                || !receipt.get("all_other_full_file_bytes_preserved").getAsBoolean() || !receipt.get("original_city_control_unchanged").getAsBoolean()
                || !receipt.get("old_city_journals_unchanged").getAsBoolean() || !receipt.get("city_journey").equals(proof.get("journey_uuid"))
                || !afterRead.get("passed").getAsBoolean() || !afterRead.get("unrelated_all_region_timestamps_chunks_and_full_NBT_unchanged").getAsBoolean())
            throw new IllegalStateException("No complete actual Root Ground828 compensation/inverse preservation");
        JsonObject manifest = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("manifest").get("path").getAsString()))).getAsJsonObject();
        if (manifest.getAsJsonArray("positiveEditMask").size() != 828 || !world.equals(Path.of(manifest.get("world").getAsString()).toRealPath()))
            throw new IllegalStateException("Wrong exact Ground compensation world/mask");
        for (var raw : manifest.getAsJsonArray("inputs"))
        { JsonObject input=raw.getAsJsonObject(); check(input); JsonObject inverse=new JsonObject(); inverse.add("path",input.get("inverse")); inverse.add("sha256",input.get("inverse_sha256")); check(inverse); }
        JsonObject before = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("before_files").get("path").getAsString()))).getAsJsonObject();
        JsonObject after = JsonParser.parseString(Files.readString(Path.of(c.getAsJsonObject("after_files").get("path").getAsString()))).getAsJsonObject();
        if (!before.keySet().equals(after.keySet())) throw new IllegalStateException("Ground compensation changed world file set");
        java.util.Set<String> allowed = new java.util.HashSet<>();
        for (var raw : run.getAsJsonArray("regions"))
        {
            JsonObject r=raw.getAsJsonObject(); Path current=Path.of(r.get("current_region").getAsString()).toRealPath();
            if (!current.startsWith(world)) throw new IllegalStateException("Foreign compensation region");
            String relative=world.relativize(current).toString().replace('\\','/'); allowed.add(relative);
            if (!r.get("before_sha256").equals(before.get(relative)) || !r.get("after_sha256").equals(after.get(relative)) || !hash(current).equals(r.get("after_sha256").getAsString()))
                throw new IllegalStateException("Ground before/after region epoch differs");
            JsonObject inverse=new JsonObject(); inverse.add("path",r.get("before_backup")); inverse.add("sha256",r.get("before_sha256")); check(inverse);
        }
        for (var entry : before.entrySet()) if (!entry.getKey().equals("session.lock") && !allowed.contains(entry.getKey()) && !entry.getValue().equals(after.get(entry.getKey())))
            throw new IllegalStateException("Ground compensation changed a non-target full file");
        java.util.Map<String,String> currentFiles=new java.util.TreeMap<>(), appliedFiles=new java.util.TreeMap<>();
        for (var raw : proof.getAsJsonArray("current_files")) { JsonObject row=raw.getAsJsonObject(); if (!row.get("relative").getAsString().equals("session.lock")) currentFiles.put(row.get("relative").getAsString(),row.get("sha256").getAsString()); }
        for (var entry : after.entrySet()) if (!entry.getKey().equals("session.lock")) appliedFiles.put(entry.getKey(),entry.getValue().getAsString());
        if (!currentFiles.equals(appliedFiles)) throw new IllegalStateException("Current world changed after Root Ground compensation");
    }

    /** A successful native settled endpoint is a distinct authority, checked once before world open. */
    public static void verifySettledEndpoint0(Path world, JsonObject evidence, String worldUUID) throws Exception
    {
        check(evidence);
        JsonObject proof = JsonParser.parseString(Files.readString(Path.of(evidence.get("path").getAsString()))).getAsJsonObject();
        boolean finite = "projectseele.city-qa-cold-settled-endpoint-checkpoint-r45.v2".equals(proof.get("schema").getAsString());
        int endpoint = finite ? proof.get("depth").getAsInt() : 0;
        int totalJournals = finite ? proof.get("original_journal_count").getAsInt() : 158;
        if ((endpoint != 0 && endpoint != 312) || totalJournals < 158 || (totalJournals - 62) % 96 != 0)
            throw new IllegalStateException("Settled admission only accepts complete finite 0/312 endpoints and full journal generations");
        if (!(finite || "projectseele.city-qa-cold-settled-endpoint0-checkpoint-r45.v1".equals(proof.get("schema").getAsString()))
                || !"QA_ONLY".equals(proof.get("role").getAsString()) || !world.equals(Path.of(proof.get("world").getAsString()).toRealPath())
                || !worldUUID.equals(proof.get("world_id").getAsString()) || !"IDLE".equals(proof.get("phase").getAsString())
                || proof.get("depth").getAsInt() != endpoint || proof.get("target_depth").getAsInt() != endpoint
                || proof.get("MotionTick").getAsInt() != 724 || proof.get("Progress").getAsDouble() != 1
                || proof.get("SavedPlans").getAsInt() != 96 || proof.get("Created").getAsInt() != 96
                || proof.get("full_cargo_cells").getAsInt() != 749242 || proof.get("full_BE").getAsInt() != 1471
                || proof.get("original_actor_ids").getAsInt() != 897 || proof.get("current_actor_ids").getAsInt() != 897)
            throw new IllegalStateException("Not the independently audited successful native endpoint0");
        for (String key : new String[]{"source1736_exact", "complete_city_cargo_passed", "complete_static2859160_passed", "complete_metadata807_passed",
                finite ? "all_original_journal_bytes_retained" : "all158_original_journal_bytes_retained", "original_actor_ids_preserved", "no_moving_city_owner", "no_unplaced_fault_recovery", "no_QA_progress_for_delivery"})
            if (!proof.get(key).getAsBoolean()) throw new IllegalStateException("Missing strict settled endpoint audit: " + key);
        for (String key : new String[]{"original_copy_receipt", "complete_settled_readback", "frozen_control", "frozen_inflight_authority", "native_complete", "native_process_receipt", "actor_identity_readback"})
            check(proof.getAsJsonObject(key));
        JsonObject readback = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("complete_settled_readback").get("path").getAsString()))).getAsJsonObject();
        boolean legacyZeroReadback = endpoint == 0 && "projectseele.city-settled-endpoint0-cold-readback-r45.v1".equals(readback.get("schema").getAsString());
        boolean legacyDeepReadback = finite && endpoint == 312 && "projectseele.city-settled-endpoint312-cold-readback-r45.v1".equals(readback.get("schema").getAsString());
        boolean finiteReadback = finite && "projectseele.city-settled-endpoint-cold-readback-r45.v2".equals(readback.get("schema").getAsString())
                && readback.get("depth").getAsInt() == endpoint && readback.get("original_journal_count").getAsInt() == totalJournals;
        if (!(legacyZeroReadback || legacyDeepReadback || finiteReadback)
                || !readback.get("cold_static_endpoint_passed").getAsBoolean()
                || !(legacyZeroReadback ? readback.get("single_native_ascent_passed").getAsBoolean()
                    : legacyDeepReadback ? readback.get("native_retraction_passed").getAsBoolean() : readback.get("native_travel_passed").getAsBoolean())
                || readback.getAsJsonArray("errors").size() != 0 || readback.get("full_cargo_cells").getAsInt() != 749242
                || readback.get("complete_BE").getAsInt() != 1471 || readback.get("full_original_static_rows").getAsInt() != 2859160
                || readback.get("metadata807_scope").getAsInt() != 807 || !readback.get("all807_metadata_original_bytes_unchanged").getAsBoolean()
                || !(legacyZeroReadback ? readback.get("original158_journal_SHA_unchanged").getAsBoolean()
                    : legacyDeepReadback ? totalJournals == 254 && readback.get("complete254_original_journals_unchanged").getAsBoolean()
                    : readback.get("all_original_journal_bytes_retained").getAsBoolean()))
            throw new IllegalStateException("Full physical settled endpoint readback is missing");
        JsonObject complete = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("native_complete").get("path").getAsString()))).getAsJsonObject();
        if (!complete.get("passed").getAsBoolean() || complete.get("helper_replacement").getAsBoolean()
                || complete.get("actual_existing_city_objects").getAsInt() != 96 || !"IDLE".equals(complete.get("phase").getAsString())
                || complete.get("depth").getAsInt() != endpoint || complete.get("motion_tick").getAsInt() != 724
                || !complete.get("journey_uuid").getAsString().equals(proof.get("journey_uuid").getAsString()))
            throw new IllegalStateException("Actual native successful journey does not match settled control");
        JsonObject process = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("native_process_receipt").get("path").getAsString()))).getAsJsonObject();
        if (process.get("process_exit").getAsInt() != 0 || !"native_complete".equals(process.get("stop_reason").getAsString())
                || process.get("forced_termination").getAsBoolean() || !process.get("complete_present").getAsBoolean()
                || process.get("failure_present").getAsBoolean() || !process.get("process_and_output_gate").getAsBoolean())
            throw new IllegalStateException("Native process did not normally finish the complete successful ascent");
        java.util.Map<String, String> physicallyAudited = new java.util.TreeMap<>(), freshFiles = new java.util.TreeMap<>();
        for (var entry : readback.getAsJsonObject("world_file_epoch").entrySet())
            if (!entry.getKey().equals("session.lock")) physicallyAudited.put(entry.getKey(), entry.getValue().getAsString());
        for (var raw : proof.getAsJsonArray("current_files"))
        {
            JsonObject entry = raw.getAsJsonObject(); String relative = entry.get("relative").getAsString();
            if (!relative.equals("session.lock") && freshFiles.put(relative, entry.get("sha256").getAsString()) != null)
                throw new IllegalStateException("Duplicate settled file proof");
        }
        if (!freshFiles.equals(physicallyAudited)) throw new IllegalStateException("World bytes changed since complete physical endpoint readback");
        Path data = world.resolve("dimensions/projectseele/geofront/data");
        JsonObject row = proof.getAsJsonObject("current_control"); check(row);
        Path current = data.resolve("projectseele_city_rigid_control_r45_8246338109520.dat").toRealPath();
        if (!current.equals(Path.of(row.get("path").getAsString()).toRealPath())
                || !row.get("sha256").getAsString().equals(proof.getAsJsonObject("frozen_control").get("sha256").getAsString())
                || !row.get("sha256").getAsString().equals(readback.getAsJsonObject("control").get("sha256").getAsString()))
            throw new IllegalStateException("Settled endpoint control bytes/path changed");
        var root = net.minecraft.nbt.NbtIo.readCompressed(current.toFile());
        if (!root.equals(net.minecraft.nbt.TagParser.parseTag(row.get("complete_typed_snbt").getAsString()))
                || !row.get("complete_typed_snbt").equals(readback.get("complete_typed_snbt")))
            throw new IllegalStateException("Full typed settled endpoint control changed");
        var tag = root.getCompound("data");
        for (String key : new String[]{"Version", "Depth", "Target", "Index", "Cursor", "SavedPlans", "Created", "MotionTick", "JourneySourceDepth", "JourneyTargetDepth", "Queued"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_INT)) throw new IllegalStateException("Missing typed settled control integer: " + key);
        for (String key : new String[]{"WorldUUID", "Phase", "Fault", "QueueFault", "MotionProfile"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_STRING)) throw new IllegalStateException("Missing typed settled control string: " + key);
        for (String key : new String[]{"WorldTouched", "Rollback", "AllowMissingRecovery"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_BYTE)) throw new IllegalStateException("Missing typed settled control flag: " + key);
        if (!root.contains("DataVersion", net.minecraft.nbt.Tag.TAG_INT) || !tag.contains("Origin", net.minecraft.nbt.Tag.TAG_LONG)
                || !tag.contains("Progress", net.minecraft.nbt.Tag.TAG_DOUBLE) || !tag.contains("Journey", net.minecraft.nbt.Tag.TAG_INT_ARRAY)
                || tag.getIntArray("Journey").length != 4 || !tag.contains("JournalSHA256s", net.minecraft.nbt.Tag.TAG_LIST)
                || ((net.minecraft.nbt.ListTag)tag.get("JournalSHA256s")).size() != 96
                || !worldUUID.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != 8246338109520L
                || tag.getInt("Version") != 1 || !"c1_trapezoid_v1".equals(tag.getString("MotionProfile"))
                || !"IDLE".equals(tag.getString("Phase")) || tag.getInt("Depth") != endpoint || tag.getInt("Target") != endpoint
                || tag.getInt("Index") != 0 || tag.getInt("Cursor") != 0 || tag.getInt("SavedPlans") != 96 || tag.getInt("Created") != 96
                || tag.getInt("MotionTick") != 724 || tag.getDouble("Progress") != 1 || tag.getInt("JourneySourceDepth") != 312 - endpoint || tag.getInt("JourneyTargetDepth") != endpoint
                || tag.getInt("Queued") != -1 || tag.getByte("WorldTouched") != 1 || tag.getBoolean("Rollback") || tag.getBoolean("AllowMissingRecovery")
                || !tag.getString("Fault").isEmpty() || !tag.getString("QueueFault").isEmpty()
                || !tag.getUUID("Journey").toString().equals(proof.get("journey_uuid").getAsString()))
            throw new IllegalStateException("Settled native control is not the exact complete IDLE endpoint0");
        var plans = proof.getAsJsonArray("current_original96_journals"); var old = proof.getAsJsonArray(finite ? "retained_original_journals" : "retained_old62_journals");
        if (plans.size() != 96 || old.size() != totalJournals - 96) throw new IllegalStateException("Every retained generation and current96 journal file is required");
        java.util.Set<Path> expectedFiles = new java.util.HashSet<>(); int cells = 0, blockEntities = 0;
        for (int index = 0; index < 96; index++)
        {
            JsonObject planRow = plans.get(index).getAsJsonObject(); JsonObject original = planRow.getAsJsonObject("current");
            check(original); check(planRow.getAsJsonObject("frozen_original"));
            Path path = data.resolve("city_rigid_journal_r45").resolve(tag.getUUID("Journey").toString()).resolve(index+".dat").toRealPath();
            if (!path.equals(Path.of(original.get("path").getAsString()).toRealPath()) || planRow.get("index").getAsInt() != index
                    || !original.get("sha256").equals(planRow.getAsJsonObject("frozen_original").get("sha256"))
                    || !original.get("sha256").getAsString().equals(tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).getString(index)))
                throw new IllegalStateException("Settled original journal order/bytes changed");
            var plan = net.minecraft.nbt.NbtIo.readCompressed(path.toFile());
            if (plan.getInt("Index") != index || !plan.getUUID("Journey").equals(tag.getUUID("Journey"))
                    || !worldUUID.equals(plan.getString("WorldUUID")) || plan.getLong("Origin") != 8246338109520L)
                throw new IllegalStateException("Foreign settled original complete journal");
            var cargo = plan.getList("Cells", net.minecraft.nbt.Tag.TAG_COMPOUND); cells += cargo.size();
            for (var raw : cargo) if (((net.minecraft.nbt.CompoundTag)raw).contains("Data", net.minecraft.nbt.Tag.TAG_COMPOUND)) blockEntities++;
            expectedFiles.add(path);
        }
        for (var raw : old)
        {
            JsonObject journal = raw.getAsJsonObject(); check(journal.getAsJsonObject("current")); check(journal.getAsJsonObject("existing_frozen_original"));
            if (!journal.getAsJsonObject("current").get("sha256").equals(journal.getAsJsonObject("existing_frozen_original").get("sha256")))
                throw new IllegalStateException("Old unplaced62 logs were changed by a settled trip");
            Path path = Path.of(journal.getAsJsonObject("current").get("path").getAsString()).toRealPath();
            if (!path.startsWith(data.resolve("city_rigid_journal_r45").toRealPath()) || !expectedFiles.add(path))
                throw new IllegalStateException("Foreign/duplicate retained original journal");
        }
        java.util.Set<Path> actualFiles = new java.util.HashSet<>();
        try (var files = Files.walk(data.resolve("city_rigid_journal_r45")))
        { for (Path path : files.filter(Files::isRegularFile).toList()) actualFiles.add(path.toRealPath()); }
        if (!actualFiles.equals(expectedFiles) || cells != 749242 || blockEntities != 1471)
            throw new IllegalStateException("Settled full journal/cargo/BE membership changed");
        JsonObject actors = JsonParser.parseString(Files.readString(Path.of(proof.getAsJsonObject("actor_identity_readback").get("path").getAsString()))).getAsJsonObject();
        if (actors.getAsJsonObject("original_uuid_to_type").size() != 897 || !actors.get("original_uuid_to_type").equals(actors.get("current_uuid_to_type"))
                || actors.getAsJsonArray("moving_owner_uuids").size() != 0)
            throw new IllegalStateException("Original all-dimension897 identities were not preserved");
    }

    /** Only the independently audited READY/full96 transaction; never an unplaced cancellation. */
    public static void verifyInFlightReady(Path world, JsonObject evidence, String worldUUID) throws Exception
    {
        check(evidence);
        JsonObject proof = JsonParser.parseString(Files.readString(Path.of(evidence.get("path").getAsString()))).getAsJsonObject();
        if (!"projectseele.city-qa-cold-inflight-ready-checkpoint-r45.v1".equals(proof.get("schema").getAsString())
                || !"QA_ONLY".equals(proof.get("role").getAsString()) || !world.equals(Path.of(proof.get("world").getAsString()).toRealPath())
                || !worldUUID.equals(proof.get("world_id").getAsString()) || !"READY".equals(proof.get("phase").getAsString())
                || !proof.get("WorldTouched").getAsBoolean() || proof.get("Created").getAsInt() != 96 || proof.get("SavedPlans").getAsInt() != 96
                || proof.get("MotionTick").getAsInt() != 0 || proof.get("Progress").getAsDouble() != 0
                || proof.get("source_depth").getAsInt() != 312 || proof.get("target_depth").getAsInt() != 0
                || proof.get("full_cargo_cells").getAsInt() != 749242 || proof.get("full_BE").getAsInt() != 1471)
            throw new IllegalStateException("Not the exact audited READY/full96 native transaction");
        for (String key : new String[]{"source1736_exact", "complete96_original_journals_passed", "all158_original_journal_bytes_retained",
                "complete96_original_owner_full_cargo_passed", "complete_static2859160_and_owned_prefix_passed", "complete_metadata807_passed",
                "original_actor_ids_preserved", "no_unplaced_fault_recovery", "no_QA_progress_for_delivery"})
            if (!proof.get(key).getAsBoolean()) throw new IllegalStateException("Missing strict READY audit: " + key);
        check(proof.getAsJsonObject("frozen_inflight_authority")); check(proof.getAsJsonObject("frozen_control"));
        check(proof.getAsJsonObject("complete_static_and_prefix_readback")); check(proof.getAsJsonObject("original_copy_receipt"));
        Path data = world.resolve("dimensions/projectseele/geofront/data");
        JsonObject control = proof.getAsJsonObject("current_control"); check(control);
        Path current = data.resolve("projectseele_city_rigid_control_r45_8246338109520.dat").toRealPath();
        if (!current.equals(Path.of(control.get("path").getAsString()).toRealPath())
                || !control.get("sha256").getAsString().equals(proof.getAsJsonObject("frozen_control").get("sha256").getAsString()))
            throw new IllegalStateException("READY control path or original bytes changed");
        var root = net.minecraft.nbt.NbtIo.readCompressed(current.toFile());
        if (!root.equals(net.minecraft.nbt.TagParser.parseTag(control.get("complete_typed_snbt").getAsString())))
            throw new IllegalStateException("Complete typed READY control NBT changed");
        var tag = root.getCompound("data");
        if (!worldUUID.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != 8246338109520L
                || !"READY".equals(tag.getString("Phase")) || tag.getByte("WorldTouched") != 1
                || tag.getInt("SavedPlans") != 96 || tag.getInt("Created") != 96 || tag.getInt("Index") != 0 || tag.getInt("Cursor") != 0
                || tag.getInt("MotionTick") != 0 || tag.getDouble("Progress") != 0 || tag.getInt("Depth") != 312 || tag.getInt("Target") != 0
                || !tag.getString("Fault").isEmpty() || tag.getBoolean("Rollback") || tag.getBoolean("AllowMissingRecovery")
                || !tag.getUUID("Journey").toString().equals(proof.get("journey_uuid").getAsString())
                || tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).size() != 96)
            throw new IllegalStateException("Current READY control is not the complete original motion-zero transaction");
        var plans = proof.getAsJsonArray("current_original96_journals"); var owners = proof.getAsJsonArray("original96_owner_snapshots");
        var old = proof.getAsJsonArray("retained_old62_journals");
        if (plans.size() != 96 || owners.size() != 96 || old.size() != 62) throw new IllegalStateException("Missing full96 owners/journals or retained62");
        java.util.Set<Path> expectedFiles = new java.util.HashSet<>(); java.util.Set<java.util.UUID> ownerIDs = new java.util.HashSet<>();
        int cells = 0, blockEntities = 0;
        for (int index = 0; index < 96; index++)
        {
            JsonObject row = plans.get(index).getAsJsonObject(); JsonObject original = row.getAsJsonObject("current");
            check(original); check(row.getAsJsonObject("frozen_original"));
            Path path = data.resolve("city_rigid_journal_r45").resolve(tag.getUUID("Journey").toString()).resolve(index + ".dat").toRealPath();
            String digest = tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).getString(index);
            if (row.get("index").getAsInt() != index || !path.equals(Path.of(original.get("path").getAsString()).toRealPath())
                    || !digest.equals(original.get("sha256").getAsString()) || !digest.equals(row.getAsJsonObject("frozen_original").get("sha256").getAsString()))
                throw new IllegalStateException("Full96 original journal identity/order/bytes changed");
            var plan = net.minecraft.nbt.NbtIo.readCompressed(path.toFile());
            if (plan.getInt("Index") != index || !worldUUID.equals(plan.getString("WorldUUID")) || plan.getLong("Origin") != 8246338109520L
                    || !plan.getUUID("Journey").equals(tag.getUUID("Journey"))) throw new IllegalStateException("Foreign full96 journal");
            JsonObject actor = owners.get(index).getAsJsonObject(); check(actor.getAsJsonObject("full_entity_snapshot"));
            var entity = net.minecraft.nbt.NbtIo.readCompressed(Path.of(actor.getAsJsonObject("full_entity_snapshot").get("path").getAsString()).toFile());
            java.util.UUID owner = plan.getUUID("Owner");
            if (actor.get("index").getAsInt() != index || !actor.get("owner_uuid").getAsString().equals(owner.toString())
                    || !entity.getUUID("UUID").equals(owner) || !ownerIDs.add(owner) || !"create:contraption".equals(entity.getString("id"))
                    || !entity.getCompound("ForgeData").getUUID("R45CityJourney").equals(tag.getUUID("Journey")))
                throw new IllegalStateException("READY original actor identity/ownership differs");
            var originalCells = plan.getList("Cells", net.minecraft.nbt.Tag.TAG_COMPOUND); var cargoCells = new net.minecraft.nbt.ListTag(); int be = 0;
            for (var raw : originalCells)
            {
                var cell = ((net.minecraft.nbt.CompoundTag) raw).copy();
                if (cell.contains("Data", net.minecraft.nbt.Tag.TAG_COMPOUND)) { cell.put("NBT", cell.getCompound("Data").copy()); be++; }
                cargoCells.add(cell);
            }
            var building = new net.minecraft.nbt.CompoundTag(); building.put("Cargo", cargoCells);
            CityCreateCargoR45.verify(new CityCreateCargoR45.Cargo(building, cargoCells.size(), be), entity.getCompound("Contraption"));
            cells += cargoCells.size(); blockEntities += be; expectedFiles.add(path);
        }
        if (cells != 749242 || blockEntities != 1471) throw new IllegalStateException("READY full cargo/BE membership changed");
        for (var raw : old)
        {
            JsonObject row = raw.getAsJsonObject(); check(row.getAsJsonObject("current")); check(row.getAsJsonObject("existing_frozen_original"));
            if (!row.getAsJsonObject("current").get("sha256").getAsString().equals(row.getAsJsonObject("existing_frozen_original").get("sha256").getAsString()))
                throw new IllegalStateException("Old retained62 original bytes changed");
            expectedFiles.add(Path.of(row.getAsJsonObject("current").get("path").getAsString()).toRealPath());
        }
        java.util.Set<Path> actualFiles = new java.util.HashSet<>();
        try (var files = Files.walk(data.resolve("city_rigid_journal_r45")))
        {
            for (Path path : files.filter(Files::isRegularFile).toList()) actualFiles.add(path.toRealPath());
        }
        if (!actualFiles.equals(expectedFiles)) throw new IllegalStateException("Unexpected or missing original158 journal files");
    }

    /** Exact failed preparation; retained journals belong to their original unplaced journey. */
    public static void verifyUnplacedFault(Path world, JsonObject evidence, String worldUUID) throws Exception
    {
        check(evidence);
        JsonObject proof = JsonParser.parseString(Files.readString(Path.of(evidence.get("path").getAsString()))).getAsJsonObject();
        boolean retained = "SAFE_UNPLACED_PREPARATION_WITH_RETAINED62_JOURNALS".equals(proof.get("classification").getAsString());
        if (!"projectseele.city-unplaced-fault-proof-r45.v1".equals(proof.get("schema").getAsString())
                || !retained && !"SAFE_UNPLACED_PREPARATION_FAULT".equals(proof.get("classification").getAsString())
                || !world.equals(Path.of(proof.get("world").getAsString()).toRealPath())
                || !worldUUID.equals(proof.get("world_id").getAsString())
                || !proof.get("no_moving_city_owner").getAsBoolean())
            throw new IllegalStateException("Unplaced city fault evidence is foreign or incomplete");
        Path data = world.resolve("dimensions/projectseele/geofront/data");
        JsonObject row = proof.getAsJsonObject("control");
        check(proof.getAsJsonObject("original_control_bytes"));
        if (!row.get("sha256").getAsString().equals(proof.getAsJsonObject("original_control_bytes").get("sha256").getAsString()))
            throw new IllegalStateException("Frozen original control bytes differ");
        Path file = data.resolve("projectseele_city_rigid_control_r45_8246338109520.dat");
        if (!file.toRealPath().equals(Path.of(row.get("path").getAsString()).toRealPath()))
            throw new IllegalStateException("Unplaced fault must retain the exact existing controller file");
        check(row);
        try (var files = Files.list(data))
        {
            if (files.filter(p -> p.getFileName().toString().startsWith("projectseele_city_rigid_control_r45_")
                    && p.getFileName().toString().endsWith(".dat")).count() != 1)
                throw new IllegalStateException("Unexpected additional city control authority");
        }
        var root = net.minecraft.nbt.NbtIo.readCompressed(file.toFile());
        if (!root.equals(net.minecraft.nbt.TagParser.parseTag(row.get("complete_typed_snbt").getAsString())))
            throw new IllegalStateException("Full unplaced city control NBT changed");
        var tag = root.getCompound("data");
        for (String key : new String[]{"Version", "SavedPlans", "Created", "Index", "Cursor", "MotionTick", "Depth", "JourneySourceDepth", "Target", "JourneyTargetDepth", "Queued"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_INT)) throw new IllegalStateException("Missing typed unplaced fault integer: " + key);
        for (String key : new String[]{"WorldUUID", "MotionProfile", "Phase", "FaultPhase", "QueueFault", "Fault"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_STRING)) throw new IllegalStateException("Missing typed unplaced fault string: " + key);
        for (String key : new String[]{"WorldTouched", "Rollback", "AllowMissingRecovery"})
            if (!tag.contains(key, net.minecraft.nbt.Tag.TAG_BYTE)) throw new IllegalStateException("Missing typed unplaced fault flag: " + key);
        if (!tag.contains("Origin", net.minecraft.nbt.Tag.TAG_LONG) || !tag.contains("Progress", net.minecraft.nbt.Tag.TAG_DOUBLE)
                || !tag.contains("Journey", net.minecraft.nbt.Tag.TAG_INT_ARRAY) || tag.getIntArray("Journey").length != 4
                || !root.contains("DataVersion", net.minecraft.nbt.Tag.TAG_INT))
            throw new IllegalStateException("Incomplete native unplaced fault metadata");
        if (!worldUUID.equals(tag.getString("WorldUUID")) || tag.getLong("Origin") != 8246338109520L
                || tag.getInt("Version") != 1 || !"c1_trapezoid_v1".equals(tag.getString("MotionProfile"))
                || !"FAULT".equals(tag.getString("Phase")) || !(retained ? "PREPARE" : "WAL_WAIT").equals(tag.getString("FaultPhase"))
                || tag.getString("Fault").isBlank() || !tag.getString("QueueFault").isEmpty()
                || !tag.contains("WorldTouched", net.minecraft.nbt.Tag.TAG_BYTE) || tag.getByte("WorldTouched") != 0
                || tag.getInt("SavedPlans") != (retained ? 62 : 0) || tag.getInt("Created") != 0 || tag.getInt("Index") != (retained ? 62 : 0)
                || tag.getInt("Cursor") != 0 || tag.getInt("MotionTick") != 0 || tag.getDouble("Progress") != 0
                || tag.getInt("Depth") != 312 || tag.getInt("JourneySourceDepth") != 312
                || tag.getInt("Target") != 0 || tag.getInt("JourneyTargetDepth") != 0 || tag.getInt("Queued") != -1
                || tag.getBoolean("Rollback") || tag.getBoolean("AllowMissingRecovery")
                || !tag.contains("JournalSHA256s", net.minecraft.nbt.Tag.TAG_LIST)
                || ((net.minecraft.nbt.ListTag) tag.get("JournalSHA256s")).size() != (retained ? 62 : 0))
            throw new IllegalStateException("City fault is not the exact zero-image unplaced restore preparation");
        Path journals = data.resolve("city_rigid_journal_r45");
        java.util.Set<Path> expectedJournals = new java.util.HashSet<>();
        if (retained)
        {
            if (!tag.getString("Fault").equals("java.lang.IllegalStateException: Street hatch state/NBT changed without ownership migration at BlockPos{x=183, y=80, z=342}")
                    || proof.get("no_durable_city_journal").getAsBoolean()
                    || !row.get("sha256").getAsString().equals("34e5db818410667436087ba26eb1070cc3dc99eb90e8151003a989682b2b9e8e")
                    || !proof.get("original_current_journal_bytes_retained").getAsBoolean())
                throw new IllegalStateException("Retained partial journals cannot be described as no journal");
            check(proof.getAsJsonObject("retained_original_authority"));
            var rows = proof.getAsJsonArray("retained_journals");
            if (rows.size() != 62) throw new IllegalStateException("All62 original journal references are required");
            for (int index = 0; index < 62; index++)
            {
                JsonObject journal = rows.get(index).getAsJsonObject();
                Path original = journals.resolve(tag.getUUID("Journey").toString()).resolve(index + ".dat").toRealPath();
                String digest = tag.getList("JournalSHA256s", net.minecraft.nbt.Tag.TAG_STRING).getString(index);
                if (journal.get("index").getAsInt() != index || !original.equals(Path.of(journal.get("path").getAsString()).toRealPath())
                        || !digest.matches("[0-9a-f]{64}") || !digest.equals(journal.get("sha256").getAsString()))
                    throw new IllegalStateException("Retained partial journal identity/order/hash differs");
                check(journal); check(journal.getAsJsonObject("original_snapshot"));
                if (!digest.equals(journal.getAsJsonObject("original_snapshot").get("sha256").getAsString()))
                    throw new IllegalStateException("Frozen full original journal bytes differ");
                var saved = net.minecraft.nbt.NbtIo.readCompressed(original.toFile());
                if (!saved.contains("WorldUUID", net.minecraft.nbt.Tag.TAG_STRING)
                        || !saved.contains("Origin", net.minecraft.nbt.Tag.TAG_LONG) || !saved.contains("Index", net.minecraft.nbt.Tag.TAG_INT)
                        || !saved.contains("Cells", net.minecraft.nbt.Tag.TAG_LIST)
                        || !worldUUID.equals(saved.getString("WorldUUID")) || saved.getLong("Origin") != 8246338109520L
                        || saved.getInt("Index") != index || !saved.hasUUID("Journey") || !saved.getUUID("Journey").equals(tag.getUUID("Journey"))
                        || saved.getList("Cells", net.minecraft.nbt.Tag.TAG_COMPOUND).isEmpty())
                    throw new IllegalStateException("Retained full journal is foreign or incomplete");
                expectedJournals.add(original);
            }
        }
        java.util.Set<Path> actualJournals = new java.util.HashSet<>();
        if (Files.exists(journals)) try (var files = Files.walk(journals))
        {
            for (Path path : files.filter(Files::isRegularFile).toList()) actualJournals.add(path.toRealPath());
        }
        if (!actualJournals.equals(expectedJournals)) throw new IllegalStateException("Unexpected/missing original partial journal bytes");
    }

    private static void check(JsonObject row) throws Exception
    {
        Path path = Path.of(row.get("path").getAsString()).toRealPath();
        if (!hash(path).equals(row.get("sha256").getAsString()))
            throw new IllegalStateException("Frozen City96 dependency changed: " + path);
    }

    private static String hash(Path file) throws Exception
    {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        try (InputStream stream = Files.newInputStream(file))
        {
            byte[] buffer = new byte[1024 * 1024];
            int count;
            while ((count = stream.read(buffer)) > 0) digest.update(buffer, 0, count);
        }
        return HexFormat.of().formatHex(digest.digest());
    }
}

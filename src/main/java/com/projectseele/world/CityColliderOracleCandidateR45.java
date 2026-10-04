package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.compat.CityUnionActivationR45;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.NbtIo;
import net.minecraft.nbt.Tag;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.BlockGetter;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.levelgen.structure.templatesystem.StructureTemplate.StructureBlockInfo;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.shapes.BooleanOp;
import net.minecraft.world.phys.shapes.CollisionContext;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Root opt-in Forge oracle candidate. Artifact source only, not installed/enabled in production. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class CityColliderOracleCandidateR45
{
    private static final String JOB = System.getProperty("projectseele.r45CityColliderOracle", "");
    private static final Path ARTIFACTS = Path.of(System.getProperty("projectseele.r45CityColliderOracleArtifacts", "artifacts/rebuild_r45")).toAbsolutePath().normalize();
    private static final String BASE = "com.simibubi.create.content.contraptions.Contraption";
    private static final String PINNED_CREATE_CLASS = CityUnionActivationR45.expectedCreateSHA256();
    private static ExecutorService worker, shapeWorkers;
    private static CompletableFuture<JsonObject> result;
    private static JsonObject job;
    private static boolean started, finished;
    private CityColliderOracleCandidateR45() {}

    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if (JOB.isEmpty() || finished || event.phase != TickEvent.Phase.END) return;
        try
        {
            if (!started)
            {
                Path input = artifact(Path.of(JOB));
                job = JsonParser.parseString(Files.readString(input)).getAsJsonObject();
                require("projectseele.city-native-collider-oracle-r45.v1".equals(job.get("schema").getAsString()), "Wrong oracle schema");
                require(job.get("root_reviewed_bound_job").getAsBoolean(), "UNBOUND oracle is not executable");
                require(job.getAsJsonArray("journals").size() >= 1 && (job.getAsJsonArray("journals").size() <= 4 || job.getAsJsonArray("journals").size() == 96), "Run one to four plans or the exact full96 in bounded batches");
                Path actualWorld = event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
                require(actualWorld.equals(Path.of(job.get("world_path").getAsString()).toAbsolutePath().normalize()), "Foreign root world path");
                require(CityAtomicCandidateBindingR45.candidateLeaseReady(actualWorld), "Fresh full world/runtime binding required");
                ResourceKey<Level> key = ResourceKey.create(Registries.DIMENSION, new ResourceLocation(job.get("dimension").getAsString()));
                ServerLevel level = event.getServer().getLevel(key);
                require(level != null && level.getSeed() == job.get("seed").getAsLong(), "Foreign native dimension/seed");
                require(Tokyo3BuildingWorldIdentityR44.get(level).equals(job.get("world_uuid").getAsString()), "Foreign native world UUID");
                Path output = artifact(Path.of(job.get("output").getAsString()));
                require(!Files.exists(output), "Never replace an oracle receipt");
                started = true;
                worker = Executors.newSingleThreadExecutor(task -> { Thread t = new Thread(task, "seele-city-collider-oracle"); t.setDaemon(true); return t; });
                shapeWorkers = Executors.newFixedThreadPool(2, task -> { Thread t = new Thread(task, "seele-city-shape-oracle"); t.setDaemon(true); return t; });
                result = CompletableFuture.supplyAsync(() ->
                {
                    try { return run(level); }
                    catch (Exception failure) { throw new java.util.concurrent.CompletionException(failure); }
                }, worker);
                return;
            }
            if (!result.isDone()) return;
            JsonObject receipt = result.join();
            Path output = artifact(Path.of(job.get("output").getAsString()));
            Files.createDirectories(output.getParent()); Files.writeString(output, receipt.toString(), java.nio.file.StandardOpenOption.CREATE_NEW);
            finished = true; worker.shutdown(); shapeWorkers.shutdown();
            ProjectSeele.LOGGER.info("R45 collider native oracle batch complete passed={} path={}", receipt.get("passed"), output);
        }
        catch (Exception failure)
        {
            finished = true; if (worker != null) worker.shutdownNow(); if (shapeWorkers != null) shapeWorkers.shutdownNow();
            try
            {
                JsonObject failed = new JsonObject(); failed.addProperty("passed", false); failed.addProperty("error", failure.toString());
                failed.addProperty("world_written", false); failed.addProperty("stock_provider_modified", false);
                Path path = artifact(Path.of(job.get("output").getAsString()+".failed.json"));
                require(!Files.exists(path), "Never replace failure evidence"); Files.createDirectories(path.getParent()); Files.writeString(path, failed.toString(), java.nio.file.StandardOpenOption.CREATE_NEW);
            }
            catch (Exception suppressed) { failure.addSuppressed(suppressed); }
            ProjectSeele.LOGGER.error("R45 collider native oracle failed; no collider/world substitution", failure);
        }
    }

    @SubscribeEvent
    public static void stopping(ServerStoppingEvent event)
    {
        if (result != null) result.cancel(false);
        if (worker != null) worker.shutdownNow(); if (shapeWorkers != null) shapeWorkers.shutdownNow(); // No server join/await: cancellation is not a passing receipt.
        finished = true;
    }

    private static JsonObject run(ServerLevel level) throws Exception
    {
        JsonArray authorities = job.getAsJsonArray("journals"), rows = new JsonArray(); Set<Integer> seen = new HashSet<>();
        for (var item : authorities)
        { int index=item.getAsJsonObject().get("index").getAsInt(); require(index >= 0 && index < 96 && seen.add(index), "Unknown/duplicate original plan"); }
        int totalCells=0,totalBE=0;
        // Only two complete plans are held/computed at a time; no stock/common-pool tasks are scheduled.
        for (int first=0;first<authorities.size();first+=2)
        {
            require(!Thread.currentThread().isInterrupted(),"Cancelled oracle cannot produce a passing result");
            List<CompletableFuture<JsonObject>> pending = new ArrayList<>();
            for (int next=first;next<Math.min(first+2,authorities.size());next++)
            {
                JsonObject authority=authorities.get(next).getAsJsonObject();
                pending.add(CompletableFuture.supplyAsync(() ->
                { try { return runPlan(level,authority); } catch (Exception failure) { throw new java.util.concurrent.CompletionException(failure); } },shapeWorkers));
            }
            for (var future : pending)
            { JsonObject row=future.join();rows.add(row);totalCells+=row.get("complete_cells").getAsInt();totalBE+=row.get("complete_BE").getAsInt(); }
        }
        if (authorities.size()==96) require(seen.size()==96 && totalCells==749242 && totalBE==1471,"Full96 original cargo changed");
        JsonObject report=new JsonObject(); report.addProperty("schema","projectseele.city-native-collider-oracle-receipt-r45.v1");report.addProperty("passed",true);
        report.add("complete_plan_results",rows); report.addProperty("cells",totalCells);report.addProperty("complete_BE",totalBE);
        report.addProperty("source_job_sha256",fileSha(Path.of(JOB)));report.addProperty("source_job",Path.of(JOB).toAbsolutePath().toString());
        report.addProperty("world_written",false);report.addProperty("entity_created",false);report.addProperty("stock_provider_modified",false);
        report.addProperty("actual_stock_supplier_invoked",true);report.addProperty("per_original_shape_repeat_XOR_empty",true);report.addProperty("full96_passed",rows.size()==96);
        report.addProperty("maximum_concurrent_complete_plans",2); report.addProperty("cache_validity_or_runtime_integration_proved",false);return report;
    }

    private static JsonObject runPlan(ServerLevel level, JsonObject authority) throws Exception
    {
        int index=authority.get("index").getAsInt(); JsonObject producers=new JsonObject();
        Class<?> base = Class.forName(BASE), pulley = Class.forName(BASE.replace("Contraption", "pulley.PulleyContraption"));
        Class<?> worldClass = Class.forName("com.simibubi.create.content.contraptions.ContraptionWorld");
        require(PINNED_CREATE_CLASS != null && PINNED_CREATE_CLASS.equals(classSha(base)), "Pinned Create6.0.8 class resource changed");
        for (Class<?> type : new Class<?>[] {base, pulley, worldClass, Shapes.class, VoxelShape.class, CollisionContext.class})
            producers.addProperty(type.getName(), classSha(type));
        // This invokes the actual pinned stock supplier body, not a reimplementation/helper box baseline.
        Method nativeSupplier = base.getDeclaredMethod("lambda$gatherBBsOffThread$24"); nativeSupplier.setAccessible(true);
        Field collision = base.getDeclaredField("collisionLevel"); collision.setAccessible(true);
        Field provider = base.getDeclaredField("simplifiedEntityColliderProvider"); provider.setAccessible(true);
            Path path = artifact(Path.of(authority.get("path").getAsString())); String expected = authority.get("sha256").getAsString();
            require(expected.equals(fileSha(path)), "Original complete journal bytes changed before oracle");
            CompoundTag plan = NbtIo.readCompressed(path.toFile());
            require(expected.equals(fileSha(path)), "Original complete journal bytes changed during oracle read");
            require(plan.getInt("Index") == index && plan.getString("WorldUUID").equals(job.get("world_uuid").getAsString())
                    && plan.getLong("Origin") == job.get("origin").getAsLong()
                    && plan.getUUID("Journey").toString().equals(job.get("journey_uuid").getAsString()), "Foreign full plan identity");
            CompoundTag building = new CompoundTag(); building.putLong("Centre", plan.getLong("Centre"));
            building.putInt("Half", plan.getInt("Half")); building.putInt("Height", plan.getInt("Height")); building.putBoolean("FixedStreetCore", false);
            CompoundTag footprint = new CompoundTag();
            for (String key : new String[] {"MinX", "MaxX", "MinZ", "MaxZ"}) footprint.putInt(key, plan.getInt(key));
            building.put("R45Footprint", footprint); ListTag cells = new ListTag(); int bes = 0;
            for (Tag raw : plan.getList("Cells", Tag.TAG_COMPOUND))
            {
                CompoundTag cell = ((CompoundTag)raw).copy();
                if (cell.contains("Data")) { cell.put("NBT", cell.getCompound("Data").copy()); cell.remove("Data"); bes++; }
                cells.add(cell);
            }
            require(cells.size() == authority.get("complete_cells").getAsInt() && bes == authority.get("complete_BE").getAsInt(), "Do not reduce the full cargo/BE context");
            building.put("Cargo", cells); CityCreateCargoR45.Cargo cargo = new CityCreateCargoR45.Cargo(building, cells.size(), bes);
            BlockPos centre = BlockPos.of(plan.getLong("Centre")); BlockPos anchor = new BlockPos(centre.getX(), plan.getInt("SourceY"), centre.getZ());
            Object contraption = pulley.getConstructor().newInstance(); CompoundTag payload = CityCreateCargoR45.pulley(cargo, anchor);
            pulley.getMethod("readNBT", Level.class, CompoundTag.class, boolean.class).invoke(contraption, level, payload, false);
            CityCreateCargoR45.verify(cargo, (CompoundTag)base.getMethod("writeNBT", boolean.class).invoke(contraption, false));
            Object nativeWorld = worldClass.getConstructor(Level.class, base).newInstance(level, contraption); collision.set(contraption, nativeWorld);
            require(provider.get(contraption) == null, "Oracle must not schedule stock/common-pool providers");
            @SuppressWarnings("unchecked") Map<BlockPos, StructureBlockInfo> blocks = (Map<BlockPos, StructureBlockInfo>)base.getMethod("getBlocks").invoke(contraption);
            require(blocks.size() == cells.size(), "Native registered decode changed cargo count");
            List<VoxelShape> original = new ArrayList<>(); Map<BlockPos,VoxelShape> everyOriginalShape = new java.util.HashMap<>(); int empty = 0, nativeBE = 0;
            for (var entry : blocks.entrySet())
            {
                BlockPos p = entry.getKey(); StructureBlockInfo info = entry.getValue();
                require(p.equals(info.pos()), "Native block iteration key/position diverged");
                if (info.nbt() != null) nativeBE++;
                Class<?> producer = info.state().getBlock().getClass();
                if (!producers.has(producer.getName())) producers.addProperty(producer.getName(), classSha(producer));
                VoxelShape shape = info.state().getCollisionShape((BlockGetter)nativeWorld, p, CollisionContext.empty());
                everyOriginalShape.put(p,shape);
                if (shape.isEmpty()) empty++; else original.add(shape.move(p.getX(), p.getY(), p.getZ()));
            }
            require(nativeBE == bes, "Original full native block-entity context lost");
            long before = System.nanoTime();
            @SuppressWarnings("unchecked") List<AABB> actualStockBoxes = (List<AABB>)nativeSupplier.invoke(contraption);
            double stockMs = (System.nanoTime()-before)/1e6;
            // Reconstruct the exact native stock AABB region solely for the XOR/collision oracle.
            List<VoxelShape> stockRegions = new ArrayList<>(); for (AABB box : actualStockBoxes) stockRegions.add(Shapes.create(box));
            VoxelShape stock = ExactBalancedUnionCandidateR45.balanced(stockRegions);
            int repeatedShapes = 0;
            for (var entry : blocks.entrySet())
            {
                BlockPos position = entry.getKey();
                VoxelShape repeated = entry.getValue().state().getCollisionShape((BlockGetter)nativeWorld, position, CollisionContext.empty());
                require(ExactBalancedUnionCandidateR45.exactNativeRegionEqual(everyOriginalShape.get(position), repeated), "Actual individual shape producer changed its region at " + position);
                repeatedShapes++;
            }
            require(repeatedShapes == cells.size(), "Every original block including empty and BE states must pass native repeat XOR");
            before = System.nanoTime(); VoxelShape candidate = ExactBalancedUnionCandidateR45.balanced(original);
            double balancedMs = (System.nanoTime()-before)/1e6;
            require(ExactBalancedUnionCandidateR45.exactNativeRegionEqual(stock, candidate), "Native full-region XOR is not empty");
            long queries = axisOracle(stock, candidate, plan);
            require(provider.get(contraption) == null, "Unexpected stock provider lifecycle mutation");
            JsonObject row = new JsonObject(); row.addProperty("index", index); row.addProperty("journal_sha256", expected);
            row.addProperty("complete_cells", cells.size()); row.addProperty("complete_BE", bes); row.addProperty("native_empty_shapes", empty);
            row.addProperty("native_nonempty_shapes", original.size()); row.addProperty("actual_stock_supplier_ms", stockMs);
            row.addProperty("balanced_union_ms", balancedMs); row.addProperty("actual_stock_AABBs", actualStockBoxes.size());
            row.addProperty("candidate_AABBs", candidate.toAabbs().size()); row.addProperty("axis_queries", queries);
            row.addProperty("per_original_shape_repeat_XOR_empty", true); row.addProperty("individual_native_shapes_checked", repeatedShapes); row.addProperty("actual_stock_vs_balanced_XOR_empty", true);
            row.addProperty("axis_answers_exact_equal", true);
            row.add("actual_class_resource_SHA256s", producers);
            Path output = artifact(Path.of(job.get("output").getAsString() + ".index_" + index + ".json"));
            Files.createDirectories(output.getParent()); Files.writeString(output,row.toString(),java.nio.file.StandardOpenOption.CREATE_NEW);
            ProjectSeele.LOGGER.info("R45 actual collider oracle index={} stockMs={} balancedMs={} cells={} individualXor={} axisQueries={}", index,stockMs,balancedMs,cells.size(),repeatedShapes,queries);
            return row;
    }

    private static long axisOracle(VoxelShape stock, VoxelShape candidate, CompoundTag plan)
    {
        long queries = 0; double[] widths = {.6, 1.4}, heights = {1.8, 1.0}, epsilon = {-1e-7, 0, 1e-7};
        // Query actual native stock boundaries and complete source/middle/target translations.
        double source = plan.getInt("SourceY"), target = plan.getInt("TargetY");
        BlockPos centre = BlockPos.of(plan.getLong("Centre")); double tx=centre.getX()+.5, tz=centre.getZ()+.5;
        for (double offset : new double[] {source, (source+target)/2, target})
        {
            VoxelShape actual = stock.move(tx, offset, tz), proposed = candidate.move(tx, offset, tz);
            for (AABB boundary : stock.toAabbs()) for (int body = 0; body < widths.length; body++)
                for (double e : epsilon) for (Direction.Axis axis : Direction.Axis.values())
                {
                    double x=(boundary.minX+boundary.maxX)/2+tx, y=(boundary.minY+boundary.maxY)/2+offset, z=(boundary.minZ+boundary.maxZ)/2+tz;
                    double w=widths[body], h=heights[body];
                    for (double sign : new double[] {-1,1})
                    {
                        double bx=x-w/2, by=y-h/2, bz=z-w/2;
                        if (axis == Direction.Axis.X) bx = sign < 0 ? boundary.maxX+tx+e : boundary.minX+tx-w+e;
                        if (axis == Direction.Axis.Y) by = sign < 0 ? boundary.maxY+offset+e : boundary.minY+offset-h+e;
                        if (axis == Direction.Axis.Z) bz = sign < 0 ? boundary.maxZ+tz+e : boundary.minZ+tz-w+e;
                        AABB box = new AABB(bx,by,bz,bx+w,by+h,bz+w);
                        for (double distance : new double[] {.01, .25, 1})
                        {
                            double a=actual.collide(axis,box,sign*distance), b=proposed.collide(axis,box,sign*distance);
                            require(Double.doubleToLongBits(a)==Double.doubleToLongBits(b), "Native axis collision answer changed"); queries++;
                        }
                    }
                }
        }
        return queries;
    }

    private static String classSha(Class<?> type) throws Exception
    {
        try (var stream = type.getResourceAsStream('/'+type.getName().replace('.','/')+".class"))
        { require(stream != null, "Shape producer class resource unavailable"); return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(stream.readAllBytes())); }
    }
    private static String fileSha(Path path) throws Exception
    { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))); }
    private static Path artifact(Path path)
    { Path resolved=path.toAbsolutePath().normalize(); require(resolved.startsWith(ARTIFACTS), "Oracle inputs/results must be frozen artifacts"); return resolved; }
    private static void require(boolean condition, String message)
    { if (!condition) throw new IllegalStateException(message); }
}

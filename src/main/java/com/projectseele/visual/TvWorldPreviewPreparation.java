package com.projectseele.visual;

import com.mojang.datafixers.util.Either;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.GeoFrontBoundedChunkGenerator;
import com.projectseele.world.TvWorldPreviewTerrain;
import com.projectseele.world.ThirdTokyoSurfaceBuilder;
import com.projectseele.world.IntegratedNervMapBuilder;
import com.projectseele.world.TvWorldSurfaceLandscape;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.chunk.ChunkStatus;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

/** Explicit preparation stages, restricted to one disposable reconstruction save. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID)
public final class TvWorldPreviewPreparation
{
    private static final String MODE = System.getProperty("projectseele.tvWorldPreviewReview", "");
    private static String phase = MODE.equals("finish") ? "city" : MODE;
    private static int age, queued, completed;
    private static boolean started;
    private static volatile boolean finished;
    private static final List<ChunkPos> CHUNKS = new ArrayList<>();
    private static final Map<ChunkPos, CompletableFuture<?>> PENDING = new LinkedHashMap<>();

    private TvWorldPreviewPreparation() {}

    public static boolean isFinished() { return finished; }

    public static void completeExternalStage(net.minecraft.server.MinecraftServer server)
    {
        finish(server);
    }

    private static void finish(net.minecraft.server.MinecraftServer server)
    {
        if (MODE.equals("coast") && phase.equals("coast"))
        {
            phase = "coast-landscape";
            started = false;
            completed = 0;
            return;
        }
        if (MODE.equals("finish") && phase.equals("city"))
        {
            phase = "landscape";
            started = false;
            completed = 0;
            CHUNKS.clear();
            return;
        }
        stop(server);
    }

    private static void stop(net.minecraft.server.MinecraftServer server)
    {
        finished = true;
        if (server.isDedicatedServer()) server.halt(false);
    }

    @SubscribeEvent
    public static void serverTick(TickEvent.ServerTickEvent event)
    {
        if (MODE.isEmpty() || MODE.equals("review") || MODE.equals("systemtest") || MODE.equals("evatest") || MODE.equals("lifts") || MODE.equals("lifts-surface") || MODE.equals("lifts-cages") || MODE.equals("lifts-commander") || MODE.equals("lifts-command")
                || finished || event.phase != TickEvent.Phase.END) return;
        var server = event.getServer();
        if (!server.isDedicatedServer() && server.getPlayerList().getPlayers().isEmpty()) return;
        Path world = server.getWorldPath(LevelResource.ROOT).normalize();
        if (!world.getFileName().toString().equals("SEELE_TV_WORLD_PREVIEW_20260906")
                || !Files.isRegularFile(world.resolve(".projectseele_tv_world_preview.json")))
        {
            ProjectSeele.LOGGER.error("TV WORLD PREVIEW REFUSED unrelated world {}", world);
            stop(server);
            return;
        }
        try
        {
            if (++age < 100) return;
            if (age > 48000) throw new IllegalStateException("preparation timeout");
            ServerLevel generatedLevel = server.getLevel(FacilitySchemaV2.DIMENSION);
            if (!(generatedLevel.getChunkSource().getGenerator() instanceof GeoFrontBoundedChunkGenerator generator)
                    || !generator.isTvPreview())
            {
                throw new IllegalStateException("Save-local TV dimension profile is not active; refusing preparation");
            }
            if (MODE.equals("probe"))
            {
                int x = -210, z = 320, floor = TvWorldPreviewTerrain.ground(x, z);
                generatedLevel.getChunk(x >> 4, z >> 4);
                if (!generatedLevel.getBlockState(new BlockPos(x, floor + 20, z)).isAir()
                        || generatedLevel.getBlockState(new BlockPos(x, floor, z)).isAir()
                        || generatedLevel.getBlockState(new BlockPos(x, TvWorldPreviewTerrain.roof(x, z) + 1, z)).isAir())
                {
                    throw new IllegalStateException("TV terrain probe does not match its floor, air and solid roof");
                }
                ProjectSeele.LOGGER.info("TV WORLD PREVIEW PROFILE PROBE PASS floor={} ceiling={} profile=true", floor, TvWorldPreviewTerrain.roof(x, z));
                finish(server);
                return;
            }
            if (phase.equals("city"))
            {
                Path receipt = world.resolve("tv_preview_city_authored.json");
                if (Files.isRegularFile(receipt))
                    throw new IllegalStateException("City already authored; do not overwrite a played preview");
                if (!started)
                {
                    started = true;
                    ProjectSeele.LOGGER.info("TV WORLD PREVIEW city authoring started");
                    ThirdTokyoSurfaceBuilder.refineTvFoundation(generatedLevel, IntegratedNervMapBuilder.TOKYO3_ORIGIN);
                }
                int count = ThirdTokyoSurfaceBuilder.movableBuildings(generatedLevel).size();
                if (completed < count)
                {
                    ThirdTokyoSurfaceBuilder.refineTvLot(generatedLevel,
                            IntegratedNervMapBuilder.TOKYO3_ORIGIN, completed++);
                    if (completed % 16 == 0)
                        ProjectSeele.LOGGER.info("TV WORLD PREVIEW authored {}/{} city lots", completed, count);
                    return;
                }
                Files.writeString(receipt, "{\"revision\":1,\"lots\":" + count + "}\n");
                ProjectSeele.LOGGER.info("TV WORLD PREVIEW CITY COMPLETE lots={}", count);
                finish(server);
                return;
            }
            if (MODE.equals("survey"))
            {
                long seed = server.overworld().getSeed();
                Path report = world.resolve("coastal_seed_fine_" + seed + ".json");
                if (!started)
                {
                    started = true;
                    server.getCommands().performPrefixedCommand(server.createCommandSourceStack(),
                            "seele_coastal_seed_scout fine " + seed);
                    ProjectSeele.LOGGER.info("TV WORLD PREVIEW natural-coast survey started seed={}", seed);
                }
                else if (Files.isRegularFile(report))
                {
                    ProjectSeele.LOGGER.info("TV WORLD PREVIEW SURVEY COMPLETE report={}", report);
                    finish(server);
                }
                return;
            }
            if (phase.equals("landscape") || phase.equals("coast-landscape"))
            {
                Path receipt = world.resolve(MODE.equals("coast")
                        ? "tv_preview_coast_finished.json" : "tv_preview_surface_finished.json");
                if (Files.isRegularFile(receipt)) throw new IllegalStateException("Surface already finished");
                if (!started)
                {
                    started = true;
                    if (!MODE.equals("coast"))
                        for (int z = -12; z <= 43; z++)
                            for (int x = -24; x <= 23; x++) CHUNKS.add(new ChunkPos(x, z));
                }
                if (completed < CHUNKS.size())
                {
                    TvWorldSurfaceLandscape.finishChunk(generatedLevel, CHUNKS.get(completed++));
                    if (completed % 128 == 0)
                        ProjectSeele.LOGGER.info("TV WORLD PREVIEW landscaped {}/{} surface chunks", completed, CHUNKS.size());
                    return;
                }
                Files.writeString(receipt, "{\"revision\":1,\"chunks\":" + completed + "}\n");
                ProjectSeele.LOGGER.info("TV WORLD PREVIEW LANDSCAPE COMPLETE chunks={}", completed);
                finish(server);
                return;
            }
            if (!MODE.equals("generate") && !MODE.equals("coast")) throw new IllegalArgumentException("Unknown stage " + MODE);
            ServerLevel level = server.getLevel(FacilitySchemaV2.DIMENSION);
            if (!started)
            {
                started = true;
                if (MODE.equals("coast"))
                    for (int z = -4; z <= 39; z++)
                        for (int x = 24; x <= 47; x++) CHUNKS.add(new ChunkPos(x, z));
                else
                    for (int z = -12; z <= 43; z++)
                        for (int x = -24; x <= 23; x++) CHUNKS.add(new ChunkPos(x, z));
                ProjectSeele.LOGGER.info("TV WORLD PREVIEW generation started: {} fresh chunks", CHUNKS.size());
            }
            var iterator = PENDING.entrySet().iterator();
            while (iterator.hasNext())
            {
                var item = iterator.next();
                if (!item.getValue().isDone()) continue;
                Object result = item.getValue().join();
                if (result instanceof Either<?, ?> either && either.right().isPresent())
                    throw new IllegalStateException("chunk failed " + item.getKey() + " " + result);
                iterator.remove();
                if (++completed % 128 == 0)
                    ProjectSeele.LOGGER.info("TV WORLD PREVIEW generated {}/{} chunks", completed, CHUNKS.size());
            }
            for (int n = 0; n < 4 && PENDING.size() < 16 && queued < CHUNKS.size(); n++)
            {
                ChunkPos pos = CHUNKS.get(queued++);
                PENDING.put(pos, level.getChunkSource().getChunkFuture(pos.x, pos.z, ChunkStatus.FULL, true));
            }
            if (completed == CHUNKS.size())
            {
                Files.writeString(world.resolve(MODE.equals("coast")
                                ? "tv_preview_coast_generated.json" : "tv_preview_terrain_generated.json"),
                        "{\"chunks\":" + completed + ",\"bounds\":"
                                + (MODE.equals("coast") ? "[24,-4,47,39]" : "[-24,-12,23,43]")
                                + ",\"seed\":" + level.getSeed() + "}\n");
                ProjectSeele.LOGGER.info("TV WORLD PREVIEW GENERATION COMPLETE chunks={}", completed);
                finish(server);
            }
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error("TV WORLD PREVIEW FAILED mode=" + MODE, exception);
            stop(server);
        }
    }
}

package com.projectseele.visual;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.SplittableRandom;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.mojang.brigadier.CommandDispatcher;
import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.LongArgumentType;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import com.projectseele.world.GeoFrontBoundedChunkGenerator;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.Holder;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.FixedBiomeSource;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Read-only seed survey for the fixed Tokyo-3/GeoFront coordinate contract. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class CoastalSeedScoutCommands
{
    private static final ResourceKey<NoiseGeneratorSettings> SETTINGS =
            ResourceKey.create(Registries.NOISE_SETTINGS,
                    new ResourceLocation(ProjectSeele.MODID,
                            "geofront_surface"));
    private static final ResourceKey<Biome> BIOME = ResourceKey.create(
            Registries.BIOME,
            new ResourceLocation(ProjectSeele.MODID, "geofront_surface"));
    /** Surface scoring never needs to evaluate the solid deep-geology band. */
    private static final LevelHeightAccessor HEIGHT =
            LevelHeightAccessor.create(-64, 384);
    private static final int CENTRE_X = 30;
    private static final int CENTRE_Z = 296;
    private static final int DATUM = FacilitySchemaV2.WORLDGEN_SURFACE_DATUM;
    private static final int SEA_LEVEL = 63;
    /** Coarse scouting grid; finalists are verified by generated chunks later. */
    private static final int STEP = 128;
    /** Measured 449x449 Tokyo-3 deck, relative to centre (30,296). */
    private static final int X0 = -224;
    private static final int X1 = 224;
    private static final int Z0 = -300;
    private static final int Z1 = 148;
    private static final long[] KNOWN_CANDIDATES = {
            443877927L,
            1887782L,
            4701005640819454707L,
            -1352468750985324505L,
            888882571486312935L,
    };
    private static final Gson GSON = new GsonBuilder()
            .setPrettyPrinting().create();
    private static final AtomicBoolean RUNNING = new AtomicBoolean();

    private CoastalSeedScoutCommands() {}

    @SubscribeEvent
    public static void register(RegisterCommandsEvent event)
    {
        if(!DevelopmentCommandsR43.enabled())return;
        CommandDispatcher<CommandSourceStack> dispatcher =
                event.getDispatcher();
        dispatcher.register(Commands.literal("seele_coastal_seed_scout")
                .requires(source -> source.hasPermission(2))
                .then(Commands.argument("count", IntegerArgumentType.integer(
                                8, 512))
                        .executes(context -> survey(context.getSource(),
                                IntegerArgumentType.getInteger(context,
                                        "count"))))
                .then(Commands.literal("seed")
                        .then(Commands.argument("value", LongArgumentType.longArg())
                                .executes(context -> surveySeed(
                                        context.getSource(),
                                        LongArgumentType.getLong(context,
                                                "value")))))
                .then(Commands.literal("fine")
                        .then(Commands.argument("value", LongArgumentType.longArg())
                                .executes(context -> surveyFineSeed(
                                        context.getSource(),
                                        LongArgumentType.getLong(context,
                                                "value")))))
                .then(Commands.literal("anchor")
                        .then(Commands.argument("value", LongArgumentType.longArg())
                                .executes(context -> surveyAnchors(
                                        context.getSource(),
                                        LongArgumentType.getLong(context,
                                                "value"))))));
    }

    private static int survey(CommandSourceStack source, int count)
    {
        return startSurvey(source, candidateSeeds(count),
                "coastal_seed_scout.json", STEP);
    }

    private static int surveySeed(CommandSourceStack source, long seed)
    {
        return startSurvey(source, List.of(seed),
                "coastal_seed_check_" + seed + ".json", STEP);
    }

    private static int surveyFineSeed(CommandSourceStack source, long seed)
    {
        return startSurvey(source, List.of(seed),
                "coastal_seed_fine_" + seed + ".json", 16);
    }

    private static int surveyAnchors(CommandSourceStack source, long seed)
    {
        if (!RUNNING.compareAndSet(false, true))
        {
            source.sendFailure(Component.literal(
                    "A coastal seed survey is already running."));
            return 0;
        }
        MinecraftServer server = source.getServer();
        Path output = server.getWorldPath(LevelResource.ROOT)
                .resolve("coastal_anchor_search_" + seed + ".json");
        source.sendSuccess(() -> Component.literal(
                "Coastal anchor search started for seed " + seed + "."),
                false);
        CompletableFuture.runAsync(() -> runAnchorSearch(
                server, source, seed, output));
        return 1;
    }

    private static void runAnchorSearch(MinecraftServer server,
                                        CommandSourceStack source, long seed,
                                        Path output)
    {
        long started = System.nanoTime();
        try
        {
            Holder<NoiseGeneratorSettings> settings = server.registryAccess()
                    .registryOrThrow(Registries.NOISE_SETTINGS)
                    .getHolderOrThrow(SETTINGS);
            Holder<Biome> biome = server.registryAccess()
                    .registryOrThrow(Registries.BIOME)
                    .getHolderOrThrow(BIOME);
            GeoFrontBoundedChunkGenerator generator =
                    new GeoFrontBoundedChunkGenerator(
                            new FixedBiomeSource(biome), settings,
                            FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX, DATUM);
            RandomState randomState = RandomState.create(
                    server.registryAccess().asGetterLookup(), SETTINGS, seed);
            int gridStep = 64;
            int gridMin = -2688;
            int gridMax = 2688;
            int size = (gridMax - gridMin) / gridStep + 1;
            int[][] heights = new int[size][size];
            for (int iz = 0; iz < size; iz++)
            {
                int z = gridMin + iz * gridStep;
                for (int ix = 0; ix < size; ix++)
                {
                    int x = gridMin + ix * gridStep;
                    heights[iz][ix] = oceanFloor(
                            generator, randomState, x, z);
                }
            }
            List<AnchorResult> anchors = new ArrayList<>();
            for (int anchorZ = -2048; anchorZ <= 2048; anchorZ += gridStep)
            {
                for (int anchorX = -2048; anchorX <= 2048;
                     anchorX += gridStep)
                {
                    anchors.add(measureAnchor(heights, gridMin, gridStep,
                            anchorX, anchorZ));
                }
            }
            anchors.sort(Comparator.comparingDouble(AnchorResult::score)
                    .reversed());
            List<AnchorResult> shortlist = anchors.subList(
                    0, Math.min(20, anchors.size()));
            AnchorReport report = new AnchorReport(1, seed, gridStep,
                    new int[]{-2048, 2048, -2048, 2048},
                    List.copyOf(shortlist),
                    (System.nanoTime() - started) / 1_000_000L);
            Files.writeString(output, GSON.toJson(report) + "\n",
                    StandardCharsets.UTF_8);
            AnchorResult best = shortlist.get(0);
            server.execute(() -> source.sendSuccess(() -> Component.literal(
                    String.format(Locale.ROOT,
                            "Anchor search complete: seed=%d anchor=(%d,%d) "
                                    + "land=%.1f%% spread=%d coast=%s %.1f%% "
                                    + "report=%s",
                            seed, best.x(), best.z(),
                            best.landFraction() * 100.0D,
                            best.p90Spread(), best.coastSide(),
                            best.coastFraction() * 100.0D, output)), false));
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error("Coastal anchor search failed", exception);
            server.execute(() -> source.sendFailure(Component.literal(
                    "Coastal anchor search failed; inspect the server log.")));
        }
        finally
        {
            RUNNING.set(false);
        }
    }

    private static AnchorResult measureAnchor(int[][] heights, int gridMin,
                                              int step, int anchorX,
                                              int anchorZ)
    {
        List<Integer> land = new ArrayList<>();
        int samples = 0;
        for (int z = anchorZ - 320; z <= anchorZ + 192; z += step)
        {
            for (int x = anchorX - 256; x <= anchorX + 256; x += step)
            {
                samples++;
                int height = gridHeight(heights, gridMin, step, x, z);
                if (height > SEA_LEVEL)
                {
                    land.add(height);
                }
            }
        }
        land.sort(Integer::compareTo);
        int median = percentile(land, 0.50D);
        int p10 = percentile(land, 0.10D);
        int p90 = percentile(land, 0.90D);
        AnchorCoast best = new AnchorCoast("none", 0.0D);
        best = better(best, anchorCoast(heights, gridMin, step, "north",
                anchorX - 256, anchorX + 256,
                anchorZ - 576, anchorZ - 384));
        best = better(best, anchorCoast(heights, gridMin, step, "south",
                anchorX - 256, anchorX + 256,
                anchorZ + 256, anchorZ + 448));
        best = better(best, anchorCoast(heights, gridMin, step, "west",
                anchorX - 512, anchorX - 320,
                anchorZ - 320, anchorZ + 192));
        best = better(best, anchorCoast(heights, gridMin, step, "east",
                anchorX + 320, anchorX + 512,
                anchorZ - 320, anchorZ + 192));
        double landFraction = land.size() / (double) samples;
        int spread = p90 - p10;
        double score = 320.0D * landFraction
                + 140.0D * best.fraction()
                - 7.0D * spread
                - 4.0D * Math.abs(median - DATUM);
        if (landFraction < 0.95D)
        {
            score -= (0.95D - landFraction) * 1200.0D;
        }
        if (best.fraction() < 0.20D)
        {
            score -= (0.20D - best.fraction()) * 700.0D;
        }
        return new AnchorResult(anchorX, anchorZ, score, landFraction,
                median, p10, p90, spread, best.side(), best.fraction());
    }

    private static AnchorCoast anchorCoast(int[][] heights, int gridMin,
                                           int step, String side,
                                           int x0, int x1, int z0, int z1)
    {
        int samples = 0;
        int ocean = 0;
        for (int z = z0; z <= z1; z += step)
        {
            for (int x = x0; x <= x1; x += step)
            {
                samples++;
                ocean += gridHeight(heights, gridMin, step, x, z)
                        <= SEA_LEVEL ? 1 : 0;
            }
        }
        return new AnchorCoast(side, ocean / (double) samples);
    }

    private static AnchorCoast better(AnchorCoast first, AnchorCoast second)
    {
        return second.fraction() > first.fraction() ? second : first;
    }

    private static int gridHeight(int[][] heights, int gridMin, int step,
                                  int x, int z)
    {
        return heights[(z - gridMin) / step][(x - gridMin) / step];
    }

    private static int startSurvey(CommandSourceStack source,
                                   List<Long> seeds, String fileName,
                                   int sampleStep)
    {
        if (!RUNNING.compareAndSet(false, true))
        {
            source.sendFailure(Component.literal(
                    "A coastal seed survey is already running."));
            return 0;
        }
        MinecraftServer server = source.getServer();
        Path output = server.getWorldPath(LevelResource.ROOT)
                .resolve(fileName);
        source.sendSuccess(() -> Component.literal(
                "Coastal seed survey started in the background: " + seeds.size()
                        + " seeds."), false);
        CompletableFuture.runAsync(() -> runSurvey(
                server, source, seeds, output, sampleStep));
        return 1;
    }

    private static void runSurvey(MinecraftServer server,
                                  CommandSourceStack source, List<Long> seeds,
                                  Path output, int sampleStep)
    {
        long started = System.nanoTime();
        try
        {
        Holder<NoiseGeneratorSettings> settings = server.registryAccess()
                .registryOrThrow(Registries.NOISE_SETTINGS)
                .getHolderOrThrow(SETTINGS);
        Holder<Biome> biome = server.registryAccess()
                .registryOrThrow(Registries.BIOME)
                .getHolderOrThrow(BIOME);
        GeoFrontBoundedChunkGenerator generator =
                new GeoFrontBoundedChunkGenerator(
                        new FixedBiomeSource(biome), settings,
                        FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX, DATUM);
        List<Result> results = new ArrayList<>(seeds.size());
        for (long seed : seeds)
        {
            RandomState randomState = RandomState.create(
                    server.registryAccess().asGetterLookup(), SETTINGS, seed);
            results.add(measure(generator, randomState, seed, false,
                                sampleStep));
        }
        results.sort(Comparator.comparingDouble(Result::score).reversed());
        List<Result> shortlist = new ArrayList<>();
        for (int index = 0; index < Math.min(12, results.size()); index++)
        {
            Result measured = results.get(index);
            RandomState randomState = RandomState.create(
                    server.registryAccess().asGetterLookup(), SETTINGS,
                    measured.seed());
            shortlist.add(measure(generator, randomState,
                    measured.seed(), index < 5 && sampleStep >= 64,
                    sampleStep));
        }
        SurveyReport report = new SurveyReport(2, seeds.size(), CENTRE_X, CENTRE_Z,
                DATUM, sampleStep, new int[]{X0, X1, Z0, Z1}, shortlist,
                (System.nanoTime() - started) / 1_000_000L);
        Files.writeString(output, GSON.toJson(report) + "\n",
                StandardCharsets.UTF_8);
        Result best = shortlist.get(0);
        server.execute(() -> source.sendSuccess(() -> Component.literal(
                String.format(Locale.ROOT,
                        "Coastal scout complete: best seed=%d score=%.2f "
                                + "land=%.1f%% flat90=%d coast=%s %.1f%% "
                                + "report=%s",
                        best.seed(), best.score(),
                        best.landFraction() * 100.0D,
                        best.p90Spread(), best.coastSide(),
                        best.coastFraction() * 100.0D, output)), false));
        }
        catch (IOException | RuntimeException exception)
        {
            ProjectSeele.LOGGER.error("Coastal seed survey failed", exception);
            server.execute(() -> source.sendFailure(Component.literal(
                    "Coastal seed survey failed; inspect the server log.")));
        }
        finally
        {
            RUNNING.set(false);
        }
    }

    private static List<Long> candidateSeeds(int count)
    {
        List<Long> seeds = new ArrayList<>(count);
        for (long seed : KNOWN_CANDIDATES)
        {
            if (seeds.size() < count)
            {
                seeds.add(seed);
            }
        }
        SplittableRandom random = new SplittableRandom(
                0x5345454C455F5332L);
        while (seeds.size() < count)
        {
            seeds.add(random.nextLong());
        }
        return seeds;
    }

    private static Result measure(GeoFrontBoundedChunkGenerator generator,
                                  RandomState randomState, long seed,
                                  boolean includeGrid, int step)
    {
        List<Integer> landHeights = new ArrayList<>();
        int citySamples = 0;
        int landSamples = 0;
        for (int z = Z0; z <= Z1; z += step)
        {
            for (int x = X0; x <= X1; x += step)
            {
                citySamples++;
                int height = oceanFloor(generator, randomState,
                        CENTRE_X + x, CENTRE_Z + z);
                if (height > SEA_LEVEL)
                {
                    landSamples++;
                    landHeights.add(height);
                }
            }
        }
        landHeights.sort(Integer::compareTo);
        int median = percentile(landHeights, 0.50D);
        int p10 = percentile(landHeights, 0.10D);
        int p90 = percentile(landHeights, 0.90D);
        Coast bestCoast = bestCoast(generator, randomState, step);
        double landFraction = landSamples / (double) citySamples;
        int spread = p90 - p10;
        double score = 260.0D * landFraction
                + 120.0D * bestCoast.fraction()
                - 6.0D * spread
                - 5.0D * Math.abs(median - DATUM);
        if (landFraction < 0.90D)
        {
            score -= (0.90D - landFraction) * 900.0D;
        }
        if (bestCoast.fraction() < 0.20D)
        {
            score -= (0.20D - bestCoast.fraction()) * 500.0D;
        }
        List<List<Integer>> grid = includeGrid
                ? grid(generator, randomState, step) : List.of();
        return new Result(seed, score, landFraction, median, p10, p90,
                spread, bestCoast.side(), bestCoast.fraction(), grid);
    }

    private static Coast bestCoast(GeoFrontBoundedChunkGenerator generator,
                                   RandomState randomState, int step)
    {
        Coast best = new Coast("none", 0.0D);
        best = better(best, coastStrip(generator, randomState,
                "north", X0, X1, Z0 - 256, Z0 - 16, step));
        best = better(best, coastStrip(generator, randomState,
                "south", X0, X1, Z1 + 16, Z1 + 256, step));
        best = better(best, coastStrip(generator, randomState,
                "west", X0 - 256, X0 - 16, Z0, Z1, step));
        return better(best, coastStrip(generator, randomState,
                "east", X1 + 16, X1 + 256, Z0, Z1, step));
    }

    private static Coast coastStrip(GeoFrontBoundedChunkGenerator generator,
                                    RandomState randomState, String side,
                                    int x0, int x1, int z0, int z1,
                                    int step)
    {
        int samples = 0;
        int ocean = 0;
        for (int z = z0; z <= z1; z += step)
        {
            for (int x = x0; x <= x1; x += step)
            {
                samples++;
                if (oceanFloor(generator, randomState,
                        CENTRE_X + x, CENTRE_Z + z) <= SEA_LEVEL)
                {
                    ocean++;
                }
            }
        }
        return new Coast(side, ocean / (double) samples);
    }

    private static Coast better(Coast first, Coast second)
    {
        return second.fraction() > first.fraction() ? second : first;
    }

    private static List<List<Integer>> grid(
            GeoFrontBoundedChunkGenerator generator, RandomState randomState,
            int step)
    {
        List<List<Integer>> rows = new ArrayList<>();
        for (int z = Z0 - 256; z <= Z1 + 256; z += step)
        {
            List<Integer> row = new ArrayList<>();
            for (int x = X0 - 256; x <= X1 + 256; x += step)
            {
                row.add(oceanFloor(generator, randomState,
                        CENTRE_X + x, CENTRE_Z + z));
            }
            rows.add(row);
        }
        return rows;
    }

    private static int oceanFloor(GeoFrontBoundedChunkGenerator generator,
                                  RandomState randomState, int x, int z)
    {
        return generator.getBaseHeight(x, z,
                Heightmap.Types.OCEAN_FLOOR_WG, HEIGHT, randomState);
    }

    private static int percentile(List<Integer> sorted, double percentile)
    {
        if (sorted.isEmpty())
        {
            return -672;
        }
        int index = (int) Math.round((sorted.size() - 1) * percentile);
        return sorted.get(Math.max(0, Math.min(sorted.size() - 1, index)));
    }

    private record Coast(String side, double fraction) {}

    private record Result(long seed, double score, double landFraction,
                          int medianHeight, int p10Height, int p90Height,
                          int p90Spread, String coastSide,
                          double coastFraction,
                          List<List<Integer>> grid) {}

    private record SurveyReport(int schema, int sampledSeeds, int centreX,
                                int centreZ, int targetDatum, int sampleStep,
                                int[] cityRelativeBounds,
                                List<Result> candidates,
                                long elapsedMillis) {}

    private record AnchorCoast(String side, double fraction) {}

    private record AnchorResult(int x, int z, double score,
                                double landFraction, int medianHeight,
                                int p10Height, int p90Height, int p90Spread,
                                String coastSide, double coastFraction) {}

    private record AnchorReport(int schema, long seed, int sampleStep,
                                int[] anchorSearchBounds,
                                List<AnchorResult> candidates,
                                long elapsedMillis) {}
}

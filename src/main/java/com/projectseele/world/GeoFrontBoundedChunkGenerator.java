package com.projectseele.world;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import com.projectseele.registry.ModBlocks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.level.WorldGenRegion;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.StructureManager;
import net.minecraft.world.level.biome.BiomeManager;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.GenerationStep;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import net.minecraft.world.level.levelgen.NoiseGeneratorSettings;
import net.minecraft.world.level.levelgen.RandomState;
import net.minecraft.world.level.levelgen.blending.Blender;

/**
 * Natural-surface generator with bounded, load-bearing GeoFront caverns.
 *
 * <p>The delegated noise settings produce real geology everywhere. This
 * generator then removes only the air portion of one of the frozen candidate
 * ellipsoids, leaving a thick terrain mass below it and solid geology outside
 * it. Facility owners plus their one-block guard remain solid until their own
 * receipt-controlled builders carve them.</p>
 */
public final class GeoFrontBoundedChunkGenerator
        extends NoiseBasedChunkGenerator
{
    public static final String GENERATOR_VERSION =
            "geofront-canonical-dome-r6";
    /** TV setting-book playable GeoFront: broad, shallow upper dome. */
    private static final int CANONICAL_RADIUS_XZ = 1800;
    private static final int CANONICAL_DOME_BASE_Y = -524;
    private static final int CANONICAL_ROOF_COVER = 16;
    /** TV setting plan: the central 2 km of the 6 km dome is flat. */
    private static final int CANONICAL_FLAT_CEILING_RADIUS = 600;
    /**
     * Keep the 1.2 km ceiling-city disk, launch shafts and HQ sightlines open.
     * Static skyweave begins only beyond this radius on the far dome roof.
     */
    private static final int CANONICAL_OPEN_CEILING_RADIUS = 650;
    private static final int CANONICAL_FLOOR_Y = -478;
    private static final int CANONICAL_LAKE_LEVEL_Y = -474;
    public static final Codec<GeoFrontBoundedChunkGenerator> CODEC =
            RecordCodecBuilder.create(instance -> instance.group(
                    BiomeSource.CODEC.fieldOf("biome_source")
                            .forGetter(GeoFrontBoundedChunkGenerator
                                    ::getBiomeSource),
                    NoiseGeneratorSettings.CODEC.fieldOf("settings")
                            .forGetter(GeoFrontBoundedChunkGenerator
                                    ::generatorSettings),
                    Codec.INT.fieldOf("candidate_index")
                            .forGetter(generator -> generator.candidateIndex),
                    Codec.INT.fieldOf("surface_datum")
                            .forGetter(generator -> generator.surfaceDatum),
                    Codec.BOOL.optionalFieldOf("tv_preview", false)
                            .forGetter(generator -> generator.tvPreview)
            ).apply(instance, instance.stable(
                    GeoFrontBoundedChunkGenerator::new)));

    private final int candidateIndex;
    private final int surfaceDatum;
    private final boolean baselineEnabled;
    private final boolean tvPreview;
    private final FacilitySchemaV2.ResolvedManifest activeManifest;

    public boolean isTvPreview()
    {
        return this.tvPreview;
    }

    public GeoFrontBoundedChunkGenerator(
            BiomeSource biomeSource,
            Holder<NoiseGeneratorSettings> settings,
            int candidateIndex, int surfaceDatum)
    {
        this(biomeSource, settings, candidateIndex, surfaceDatum, false);
    }

    public GeoFrontBoundedChunkGenerator(
            BiomeSource biomeSource, Holder<NoiseGeneratorSettings> settings,
            int candidateIndex, int surfaceDatum, boolean tvPreview)
    {
        super(biomeSource, settings);
        this.tvPreview = tvPreview;
        this.candidateIndex = candidateIndex;
        this.surfaceDatum = surfaceDatum;
        this.baselineEnabled =
                candidateIndex == FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX
                && (surfaceDatum
                == FacilitySchemaV2.WORLDGEN_SURFACE_DATUM
                || surfaceDatum
                == FacilitySchemaV2.R28_LEGACY_SURFACE_DATUM);
        this.activeManifest = FacilitySchemaV2.resolve(
                FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX,
                surfaceDatum);
    }

    @Override
    protected Codec<? extends net.minecraft.world.level.chunk.ChunkGenerator>
    codec()
    {
        return CODEC;
    }

    /**
     * Bootstrap authority is the frozen generator contract, not the natural
     * surface relief above it. Surface owners establish their own reviewed
     * datum, while this identity proves that the committed cavern and roof
     * baseline will be generated at the schema coordinates.
     */
    boolean matchesFacilityBaselineContract()
    {
        return this.baselineEnabled
                && this.candidateIndex
                == FacilitySchemaV2.ACTIVE_CANDIDATE_INDEX
                && (this.surfaceDatum
                == FacilitySchemaV2.WORLDGEN_SURFACE_DATUM
                || this.surfaceDatum
                == FacilitySchemaV2.R28_LEGACY_SURFACE_DATUM);
    }

    boolean usesCanonicalDomeContract()
    {
        return this.baselineEnabled
                && this.surfaceDatum
                == FacilitySchemaV2.WORLDGEN_SURFACE_DATUM;
    }

    @Override
    public CompletableFuture<ChunkAccess> fillFromNoise(
            Executor executor, Blender blender, RandomState randomState,
            StructureManager structureManager, ChunkAccess chunk)
    {
        return super.fillFromNoise(executor, blender, randomState,
                        structureManager, chunk)
                .thenApply(generated ->
                {
                    this.carveBoundedBaseline(generated);
                    return generated;
                });
    }

    /**
     * Vanilla caves remain available in the surrounding natural continent,
     * but are disabled across the one committed GeoFront footprint so a
     * random cave cannot puncture its roof or a reserved facility shaft.
     */
    @Override
    public void applyCarvers(
            WorldGenRegion region, long seed, RandomState randomState,
            BiomeManager biomeManager, StructureManager structureManager,
            ChunkAccess chunk, GenerationStep.Carving step)
    {
        if (this.tvPreview && TvWorldPreviewTerrain.insideDome(chunk.getPos()))
        {
            return;
        }
        if (this.candidateFor(chunk.getPos()) == null)
        {
            super.applyCarvers(region, seed, randomState, biomeManager,
                    structureManager, chunk, step);
        }
    }

    private void carveBoundedBaseline(ChunkAccess chunk)
    {
        if (this.tvPreview)
        {
            TvWorldPreviewTerrain.shape(chunk);
            return;
        }
        FacilitySchemaV2.ResolvedManifest candidate =
                this.candidateFor(chunk.getPos());
        if (candidate == null)
        {
            return;
        }

        BlockPos centre = candidate.centre();
        ChunkPos chunkPos = chunk.getPos();
        int minX = chunkPos.getMinBlockX();
        int minZ = chunkPos.getMinBlockZ();
        boolean canonical = this.usesCanonicalDomeContract();
        int minY = Math.max(chunk.getMinBuildHeight(), canonical
                ? CANONICAL_DOME_BASE_Y
                : GeoFrontFabricPlan.CAVERN_BOTTOM_Y);
        int maxY = Math.min(chunk.getMaxBuildHeight(), canonical
                ? this.surfaceDatum - CANONICAL_ROOF_COVER + 1
                : GeoFrontFabricPlan.CAVERN_TOP_Y + 1);
        int radiusXZ = canonical
                ? CANONICAL_RADIUS_XZ
                : GeoFrontFabricPlan.CAVERN_RADIUS_XZ;
        BlockPos.MutableBlockPos position = new BlockPos.MutableBlockPos();

        for (int localZ = 0; localZ < 16; localZ++)
        {
            int worldZ = minZ + localZ;
            double dz = (worldZ + 0.5D - centre.getZ())
                    / radiusXZ;
            for (int localX = 0; localX < 16; localX++)
            {
                int worldX = minX + localX;
                double dx = (worldX + 0.5D - centre.getX())
                        / radiusXZ;
                double radial = 1.0D - dx * dx - dz * dz;
                if (radial <= 0.0D)
                {
                    continue;
                }

                int relativeX = worldX - centre.getX();
                int relativeZ = worldZ - centre.getZ();
                int terrainTop;
                int carveMin;
                int carveMax;
                if (canonical)
                {
                    int roof = canonicalRoofHeight(
                            relativeX, relativeZ, this.surfaceDatum);
                    terrainTop = canonicalTerrainHeight(
                            relativeX, relativeZ);
                    carveMin = Math.max(minY, terrainTop + 1);
                    carveMax = Math.min(maxY, roof + 1);
                }
                else
                {
                    double verticalRadius =
                            GeoFrontFabricPlan.CAVERN_RADIUS_Y
                                    * Math.sqrt(radial);
                    int rawBottom = (int) Math.ceil(
                            GeoFrontFabricPlan.CAVERN_CENTRE_Y
                                    - verticalRadius);
                    int rawTopExclusive = (int) Math.floor(
                            GeoFrontFabricPlan.CAVERN_CENTRE_Y
                                    + verticalRadius) + 1;
                    terrainTop = GeoFrontFabricPlan.terrainHeight(
                            relativeX, relativeZ);
                    carveMin = Math.max(minY,
                            Math.max(rawBottom, terrainTop + 1));
                    carveMax = Math.min(maxY, rawTopExclusive);
                }

                for (int y = carveMin; y < carveMax; y++)
                {
                    position.set(worldX, y, worldZ);
                    if (!canonical && GeoFrontFabricPlan.ownerGuarded(
                            candidate, position))
                    {
                        continue;
                    }
                    chunk.setBlockState(position,
                            Blocks.AIR.defaultBlockState(), false);
                }

                if (canonical && carveMax > carveMin)
                {
                    if ((long) relativeX * relativeX
                            + (long) relativeZ * relativeZ
                            >= (long) CANONICAL_OPEN_CEILING_RADIUS
                            * CANONICAL_OPEN_CEILING_RADIUS)
                    {
                        position.set(worldX, carveMax - 1, worldZ);
                        chunk.setBlockState(position,
                                ModBlocks.GEOFRONT_SKYWEAVE.get()
                                        .defaultBlockState(), false);
                    }
                    position.set(worldX, terrainTop, worldZ);
                    boolean lake = canonicalLake(relativeX, relativeZ)
                            && terrainTop < CANONICAL_LAKE_LEVEL_Y;
                    chunk.setBlockState(position, lake
                            ? Blocks.SAND.defaultBlockState()
                            : Blocks.GRASS_BLOCK.defaultBlockState(), false);
                    for (int depth = 1; depth <= 3; depth++)
                    {
                        position.set(worldX, terrainTop - depth, worldZ);
                        chunk.setBlockState(position, lake
                                ? Blocks.SAND.defaultBlockState()
                                : Blocks.DIRT.defaultBlockState(), false);
                    }
                    if (lake)
                    {
                        int waterTop = Math.min(CANONICAL_LAKE_LEVEL_Y,
                                carveMax - 1);
                        for (int y = terrainTop + 1; y <= waterTop; y++)
                        {
                            position.set(worldX, y, worldZ);
                            chunk.setBlockState(position,
                                    Blocks.WATER.defaultBlockState(), false);
                        }
                    }
                }
            }
        }

        chunk.setUnsaved(true);
    }

    /**
     * Sparse broad-leaf forest masses from the TV GeoFront setting plan.
     * Trees are planted only after every cavern column has been carved, or a
     * later column would erase neighbouring leaves.  The two-block chunk
     * margin keeps every tree self-contained and deterministic under lazy
     * generation; the central NERV campus remains an open artificial sector.
     */
    private void plantCanonicalForest(ChunkAccess chunk, BlockPos centre)
    {
        ChunkPos chunkPos = chunk.getPos();
        BlockPos.MutableBlockPos position = new BlockPos.MutableBlockPos();
        for (int localZ = 2; localZ < 14; localZ++)
        {
            int worldZ = chunkPos.getMinBlockZ() + localZ;
            int relativeZ = worldZ - centre.getZ();
            for (int localX = 2; localX < 14; localX++)
            {
                int worldX = chunkPos.getMinBlockX() + localX;
                int relativeX = worldX - centre.getX();
                if (canonicalLake(relativeX, relativeZ))
                {
                    continue;
                }
                double density = canonicalForestDensity(
                        relativeX, relativeZ);
                if (density <= 0.0D)
                {
                    continue;
                }
                long hash = mixCoordinates(worldX, worldZ);
                if (Math.floorMod(hash, 1000L)
                        >= Math.round(density * 11.0D))
                {
                    continue;
                }

                int terrainTop = canonicalTerrainHeight(
                        relativeX, relativeZ);
                double dx = (worldX + 0.5D - centre.getX())
                        / CANONICAL_RADIUS_XZ;
                double dz = (worldZ + 0.5D - centre.getZ())
                        / CANONICAL_RADIUS_XZ;
                double radial = 1.0D - dx * dx - dz * dz;
                if (radial <= 0.0D)
                {
                    continue;
                }
                int roof = canonicalRoofHeight(
                        relativeX, relativeZ, this.surfaceDatum);
                int trunkHeight = 6 + (int) Math.floorMod(hash >> 10, 4L);
                if (terrainTop + trunkHeight + 3 >= roof)
                {
                    continue;
                }

                for (int y = terrainTop + 1;
                     y <= terrainTop + trunkHeight; y++)
                {
                    position.set(worldX, y, worldZ);
                    chunk.setBlockState(position,
                            Blocks.OAK_LOG.defaultBlockState(), false);
                }
                int crownY = terrainTop + trunkHeight;
                for (int dy = -2; dy <= 1; dy++)
                {
                    int radius = dy == 1 ? 1 : 2;
                    for (int ox = -radius; ox <= radius; ox++)
                    {
                        for (int oz = -radius; oz <= radius; oz++)
                        {
                            if (Math.abs(ox) == radius
                                    && Math.abs(oz) == radius
                                    && dy != -1)
                            {
                                continue;
                            }
                            position.set(worldX + ox, crownY + dy,
                                    worldZ + oz);
                            if (chunk.getBlockState(position).isAir())
                            {
                                chunk.setBlockState(position,
                                        Blocks.OAK_LEAVES
                                                .defaultBlockState(), false);
                            }
                        }
                    }
                }
            }
        }
    }

    @Override
    public void applyBiomeDecoration(net.minecraft.world.level.WorldGenLevel world,
                                     ChunkAccess chunk,StructureManager structures)
    {
        super.applyBiomeDecoration(world,chunk,structures);
        if(getBiomeSource() instanceof RegionalEcologyBiomeSourceR44 ecology)
            NativeGeofrontVegetationR44.decorate(world,this,chunk.getPos(),ecology);
        CityRigidGenerationR45.apply(this,chunk);
    }

    boolean hasEcologicalCavernR44(ChunkPos chunk)
    {
        return tvPreview?TvWorldPreviewTerrain.insideDome(chunk):usesCanonicalDomeContract()&&candidateFor(chunk)!=null;
    }
    int ecologicalFloorR44(int x,int z)
    {
        return tvPreview?TvWorldPreviewTerrain.ground(x,z)
                :canonicalTerrainHeight(x-activeManifest.centre().getX(),z-activeManifest.centre().getZ());
    }
    int ecologicalRoofR44(int x,int z)
    {
        return tvPreview?TvWorldPreviewTerrain.roof(x,z)
                :canonicalRoofHeight(x-activeManifest.centre().getX(),z-activeManifest.centre().getZ(),surfaceDatum);
    }
    boolean ecologicalLakeR44(int x,int z)
    {
        return tvPreview?TvWorldPreviewTerrain.lakeDistance(x,z)<1.28
                :canonicalLake(x-activeManifest.centre().getX(),z-activeManifest.centre().getZ());
    }

    private FacilitySchemaV2.ResolvedManifest candidateFor(
            ChunkPos chunk)
    {
        if (!this.baselineEnabled)
        {
            // Codec/config mismatch fails closed: keep complete geology.
            return null;
        }
        int minX = chunk.getMinBlockX();
        int maxX = chunk.getMaxBlockX();
        int minZ = chunk.getMinBlockZ();
        int maxZ = chunk.getMaxBlockZ();
        int radius = this.usesCanonicalDomeContract()
                ? CANONICAL_RADIUS_XZ
                : GeoFrontFabricPlan.CAVERN_RADIUS_XZ;
        BlockPos centre = this.activeManifest.centre();
        if (maxX >= centre.getX() - radius
                && minX <= centre.getX() + radius
                && maxZ >= centre.getZ() - radius
                && minZ <= centre.getZ() + radius)
        {
            return this.activeManifest;
        }
        return null;
    }

    /**
     * Broad parkland rather than the retired spherical bowl.  Low-frequency
     * deterministic relief keeps the central approved facility datum intact
     * while giving the expanded dome forests, hills and lake shelves.
     */
    private static int canonicalTerrainHeight(int x, int z)
    {
        double rolling = 5.0D * Math.sin(x / 173.0D)
                + 4.0D * Math.cos(z / 211.0D)
                + 3.0D * Math.sin((x + z) / 97.0D);
        double southHills = 22.0D * gaussian(
                x, z, 420.0D, 680.0D, 430.0D);
        double eastHills = 14.0D * gaussian(
                x, z, 780.0D, -260.0D, 360.0D);
        double lakeShelf = 9.0D * gaussian(
                x, z, -520.0D, -320.0D, 330.0D);
        double distance = Math.hypot(x, z);
        double campusBlend = Math.max(0.0D, Math.min(1.0D,
                (distance - 280.0D) / 160.0D));
        return CANONICAL_FLOOR_Y + (int) Math.round(
                (rolling + southHills + eastHills - lakeShelf)
                        * campusBlend);
    }

    /**
     * Canonical upper Black-Moon section: a level ceiling-city disk followed
     * by one broad, shallow outer dome.  Applying a sphere equation from the
     * centre made the roof sag immediately and contradicted the production
     * dimensional drawing's explicit 2 km flat top.
     */
    static int canonicalRoofHeight(int x, int z, int surfaceDatum)
    {
        double distance = Math.hypot(x, z);
        int flatTop = surfaceDatum - CANONICAL_ROOF_COVER;
        if (distance <= CANONICAL_FLAT_CEILING_RADIUS)
        {
            return flatTop;
        }
        double transition = Math.min(1.0D,
                (distance - CANONICAL_FLAT_CEILING_RADIUS)
                / (CANONICAL_RADIUS_XZ - CANONICAL_FLAT_CEILING_RADIUS));
        double dome = Math.sqrt(Math.max(0.0D,
                1.0D - transition * transition));
        return CANONICAL_DOME_BASE_Y + (int) Math.floor(
                (flatTop - CANONICAL_DOME_BASE_Y) * dome);
    }

    private static double gaussian(int x, int z, double centreX,
                                   double centreZ, double radius)
    {
        double dx = x - centreX;
        double dz = z - centreZ;
        return Math.exp(-(dx * dx + dz * dz) / (radius * radius));
    }

    private static boolean canonicalLake(int x, int z)
    {
        double dx = (x + 310.0D) / 320.0D;
        double dz = (z + 200.0D) / 210.0D;
        double shore = dx * dx + dz * dz
                + 0.10D * Math.sin((x + z) / 41.0D)
                + 0.07D * Math.cos((x - z) / 53.0D);
        return shore < 1.0D;
    }

    private static double canonicalForestDensity(int x, int z)
    {
        // Three asymmetric masses leave the NERV/HQ centre and lake arrival
        // axis readable, matching the setting diagram's forest/hill sectors.
        double northWest = gaussian(x, z, -650.0D, 330.0D, 560.0D);
        double south = gaussian(x, z, -160.0D, 760.0D, 520.0D);
        double east = gaussian(x, z, 720.0D, 180.0D, 520.0D);
        double campusClearance = gaussian(x, z, 0.0D, 0.0D, 300.0D);
        return Math.max(0.0D,
                Math.min(1.0D, Math.max(northWest,
                        Math.max(south, east)) - campusClearance * 0.92D));
    }

    private static long mixCoordinates(int x, int z)
    {
        long value = x * 341873128712L ^ z * 132897987541L;
        value ^= value >>> 33;
        value *= 0xff51afd7ed558ccdL;
        value ^= value >>> 33;
        value *= 0xc4ceb9fe1a85ec53L;
        return value ^ value >>> 33;
    }
}

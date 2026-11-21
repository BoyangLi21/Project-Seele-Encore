package com.projectseele.world;

import java.util.EnumSet;
import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;
import net.minecraft.core.Holder;
import net.minecraft.resources.RegistryOps;
import com.mojang.serialization.Lifecycle;
import net.minecraft.SharedConstants;
import net.minecraft.core.BlockPos;
import net.minecraft.core.MappedRegistry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ProtoChunk;
import net.minecraft.world.level.chunk.UpgradeData;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.*;
import net.minecraft.world.level.levelgen.blending.Blender;

/** Regression for the photographed 125-block water wall; no client or save. */
public final class HakoneSurfaceFieldTest
{
    public static void main(String[] args) throws Exception
    {
        var field = HakoneSurfaceField.sample(2432, 1087, 50);
        if (field == null || field.ground() < -67 || field.ground() > -61
                || field.water() != HakoneSurfaceField.NO_WATER)
            throw new AssertionError("Photographed east boundary is surveyed land, not the legacy ocean");
        var coastGap = HakoneSurfaceField.sample(3148, 1088, 50);
        if (coastGap == null || coastGap.ground() > -60)
            throw new AssertionError("Missing coastal DEM sample became an elevated artificial island");
        // Outer boundary (F1/F2): land beyond the survey is mountain on the one sea datum,
        // seaward of the Sagami Bay coast it is open sea. Inland water is local to measured lakes.
        for (int[] at : new int[][]{{-4096,-1000},{0,-3072},{6500,-6500}})
        {
            var land = HakoneSurfaceField.sample(at[0],at[1],45);
            if (!OuterBoundaryTerrain.unknown(at[0],at[1]) || land.ground() <= HakoneSurfaceField.SEA_Y + 20 || land.water() != HakoneSurfaceField.SEA_Y)
                throw new AssertionError("Outer land is not mountain on the sea datum at "+at[0]+","+at[1]);
        }
        for (int[] at : new int[][]{{6500,1000},{3000,5200},{6500,5200}})
        {
            var sea = HakoneSurfaceField.sample(at[0],at[1],45);
            if (sea.ground() >= HakoneSurfaceField.SEA_Y - 10 || sea.water() != HakoneSurfaceField.SEA_Y)
                throw new AssertionError("Sagami Bay did not continue into the unsaved exterior at "+at[0]+","+at[1]);
        }
        // The exterior scan intersects these shallow-water columns in the R64 saved world.
        // Each triple gives block X, Z and the first solid bed below the water at Y62.
        int[][] measured = {
                {-3228, -1317, 59}, {-3228, -1153, 59}, {-3228, -1112, 59}, {-3228, -1071, 61},
                {-3228, -948, 61}, {-2747, -1563, 59}, {-2562, -1563, 61}, {-2303, -989, 61},
                {-2303, -907, 60}, {-2192, -1645, 59}, {-2192, -1604, 60}, {-2192, -1276, 60},
                {-2192, -1153, 60}, {-2155, -1030, 61}, {-2155, -907, 59}, {-2044, -1686, 61},
                {-2007, -1727, 61}, {-1674, -2014, 61}, {-1637, -2014, 61}, {-1304, -2178, 60},
                {-1267, -2178, 60}, {-1230, -2178, 59}, {-1230, -2137, 59}, {-1193, -2178, 59},
                {-1193, -2137, 59}, {-1156, -2137, 60}, {-1119, -2137, 61}, {-1045, -2014, 60},
                {-934, -1973, 59}, {-268, -1809, 61}, {953, -1809, 61}, {990, -1809, 59},
                {1101, -1809, 60}, {1212, -1809, 60}, {1249, -1809, 61}, {1360, -1809, 61},
                {1397, -1727, 60}, {1471, -1727, 60}, {1508, -1809, 60}
        };
        var lakeBeds = new java.util.HashMap<Long, Integer>();
        if (PlaytestLandscapeR64.hasSurvey())
            for (int[] lake : measured) lakeBeds.put(BlockPos.asLong(lake[0], 0, lake[1]), lake[2]);
        if (PlaytestLandscapeR64.class.getResource("/data/projectseele/worldgen/playtest_shores_r64/-7_-3.bin.gz") != null)
        {
            lakeBeds.put(BlockPos.asLong(-1304, 0, -2178), 61);
            lakeBeds.put(BlockPos.asLong(-1230, 0, -2178), 57);
            lakeBeds.put(BlockPos.asLong(-1230, 0, -2137), 53);
            lakeBeds.put(BlockPos.asLong(-1193, 0, -2178), 57);
            lakeBeds.put(BlockPos.asLong(-2747, 0, -1563), 56);
            lakeBeds.put(BlockPos.asLong(-2710, 0, -1563), 60);
            lakeBeds.put(BlockPos.asLong(-2673, 0, -1563), 61);
            lakeBeds.put(BlockPos.asLong(-3228, 0, -1317), 58);
            lakeBeds.put(BlockPos.asLong(-3228, 0, -1276), 61);
            lakeBeds.put(BlockPos.asLong(2914, 0, -1850), 59);
        }
        for (int x = -9000; x < 12000; x += 37)
            for (int z = -8000; z < 10000; z += 41)
            {
                if (!OuterBoundaryTerrain.unknown(x, z)) continue;
                var outer = HakoneSurfaceField.sample(x, z, 45);
                if (outer.ground() > 300 || outer.ground() < -120)
                    throw new AssertionError("Outer height out of range at " + x + "," + z);
                if (outer.water() != HakoneSurfaceField.SEA_Y && outer.water() != HakoneSurfaceField.NO_WATER)
                {
                    Integer bed = lakeBeds.remove(BlockPos.asLong(x, 0, z));
                    if (outer.water() != 62 || bed == null || bed != outer.ground())
                        throw new AssertionError("Unexpected inland water at " + x + "," + z + " = " + outer);
                }
            }
        if (!lakeBeds.isEmpty()) throw new AssertionError("Missing measured lake columns: " + lakeBeds.size());
        var lake = HakoneSurfaceField.sample(-1230, -1802, 45);
        var bank = HakoneSurfaceField.sample(PlaytestLandscapeR64.hasSurvey() ? -1188 : -1228, -1802, 45);
        if (lake.water() != 62 || bank.ground() < 62)
            throw new AssertionError("The inland lake lost its water level or its bank");
        for(int x=4400;x<12000;x+=31)
        {
            HakoneSurfaceField.Surface previous=null;
            for(int z=-9000;z<-1600;z++)
            {
                var next=HakoneSurfaceField.exterior(x,z,45);
                if(previous!=null && (previous.ground()<previous.water() && previous.water()>Math.max(next.ground(),next.water())
                        || next.ground()<next.water() && next.water()>Math.max(previous.ground(),previous.water())))
                    throw new AssertionError("Different exterior seas meet across an exposed water wall");
                previous=next;
            }
        }
        SharedConstants.tryDetectVersion();
        var ready = Bootstrap.class.getDeclaredField("isBootstrapped");
        ready.setAccessible(true); ready.setBoolean(null, true);
        BuiltInRegistries.bootStrap();
        for (var block : BuiltInRegistries.BLOCK)
            for (var state : block.getStateDefinition().getPossibleStates()) state.initCache();
        var biome = VanillaRegistries.createLookup().lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS);
        var registry = new MappedRegistry<Biome>(Registries.BIOME, Lifecycle.stable());
        registry.register(Biomes.PLAINS, biome.value(), Lifecycle.stable()); registry.freeze();
        var chunk = new ProtoChunk(new ChunkPos(152, 67), UpgradeData.EMPTY,
                LevelHeightAccessor.create(-672, 992), registry, null);
        var p = new BlockPos.MutableBlockPos();
        for (int x = 2432; x < 2448; x++) for (int z = 1072; z < 1088; z++)
            for (int y = -128; y <= 62; y++)
                chunk.setBlockState(p.set(x,y,z), (y <= 50 ? Blocks.STONE : Blocks.WATER).defaultBlockState(), false);
        chunk.setBlockState(new BlockPos(2432,-129,1087), Blocks.GOLD_BLOCK.defaultBlockState(), false);
        Heightmap.primeHeightmaps(chunk, EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG, Heightmap.Types.OCEAN_FLOOR_WG));
        TvWorldPreviewTerrain.shape(chunk);
        for (int x = 2432; x < 2448; x++) for (int z = 1072; z < 1088; z++)
        {
            var target = HakoneSurfaceField.sample(x,z,50);
            if (!chunk.getBlockState(p.set(x,target.ground(),z)).is(Blocks.GRASS_BLOCK))
                throw new AssertionError("Surveyed ground was not installed");
            for (int y = target.ground()+1; y <= 63; y++)
                if (!chunk.getBlockState(p.set(x,y,z)).isAir())
                    throw new AssertionError("Old ocean survived above the surveyed ground");
        }
        if (!chunk.getBlockState(new BlockPos(2432,-129,1087)).is(Blocks.GOLD_BLOCK))
            throw new AssertionError("Surface repair touched the underground");
        verifyConsumers(registry,biome);
        verifyOuterFastPath(registry);
        System.out.println("Hakone boundary PASS: surveyed land and coast retained, outer mountains and Sagami Bay on one sea datum, matching chunk/column/height consumers including the outer fast path, underground retained");
    }

    /** A whole outer chunk skips the native noise; its surface must match the column consumers. */
    private static void verifyOuterFastPath(MappedRegistry<Biome> registry)throws Exception
    {
        var lookup=VanillaRegistries.createLookup();
        var stream=HakoneSurfaceFieldTest.class.getResourceAsStream("/data/projectseele/worldgen/noise_settings/geofront_surface.json");
        var json=JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8));
        stream.close();
        var settings=NoiseGeneratorSettings.DIRECT_CODEC.parse(RegistryOps.create(JsonOps.INSTANCE,lookup),json)
                .getOrThrow(false,message->{throw new AssertionError(message);});
        var random=RandomState.create(settings,lookup.lookupOrThrow(Registries.NOISE),-3816295015381828007L);
        var biome=lookup.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS);
        var shaped=new GeoFrontBoundedChunkGenerator(new net.minecraft.world.level.biome.FixedBiomeSource(biome),Holder.direct(settings),0,80,true);
        var bounds=LevelHeightAccessor.create(-672,992);
        for(int[] at:new int[][]{{9000,-6000},{6400,5120},{-6000,-1000}})
        {
            var pos=new ChunkPos(at[0]>>4,at[1]>>4);
            if(!OuterBoundaryTerrain.wholeChunkUnknown(pos))throw new AssertionError("Expected a whole outer chunk at "+at[0]+","+at[1]);
            var c=new ProtoChunk(pos,UpgradeData.EMPTY,bounds,registry,null);
            shaped.fillFromNoise(Runnable::run,Blender.empty(),random,null,c).join();
            var p=new BlockPos.MutableBlockPos();
            for(int dz:new int[]{0,7,15})for(int dx:new int[]{0,7,15})
            {
                int x=pos.getMinBlockX()+dx,z=pos.getMinBlockZ()+dz;
                var col=shaped.getBaseColumn(x,z,bounds,random);
                int ground=HakoneSurfaceField.sample(x,z,-128).ground();
                for(int y=Math.max(-128,ground-3);y<320;y++)if(c.getBlockState(p.set(x,y,z))!=col.getBlock(y))
                    throw new AssertionError("Outer fast path and base column differ at "+x+","+y+","+z);
                if(!c.getBlockState(p.set(x,-200,z)).is(Blocks.STONE))throw new AssertionError("Outer fast path left no stone below at "+x+","+z);
            }
        }
    }

    private static void verifyConsumers(MappedRegistry<Biome> registry,Holder<Biome> biome)throws Exception
    {
        var lookup=VanillaRegistries.createLookup();
        var stream=HakoneSurfaceFieldTest.class.getResourceAsStream("/data/projectseele/worldgen/noise_settings/geofront_surface.json");
        var json=JsonParser.parseReader(new java.io.InputStreamReader(stream,java.nio.charset.StandardCharsets.UTF_8));
        stream.close();
        var settings=NoiseGeneratorSettings.DIRECT_CODEC.parse(RegistryOps.create(JsonOps.INSTANCE,lookup),json)
                .getOrThrow(false,message->{throw new AssertionError(message);});
        var random=RandomState.create(settings,lookup.lookupOrThrow(Registries.NOISE),-3816295015381828007L);
        var source=new net.minecraft.world.level.biome.FixedBiomeSource(biome);
        var original=new NoiseBasedChunkGenerator(source,Holder.direct(settings));
        var shaped=new GeoFrontBoundedChunkGenerator(source,Holder.direct(settings),0,80,true);
        var pickerMethod=NoiseBasedChunkGenerator.class.getDeclaredMethod("createFluidPicker",NoiseGeneratorSettings.class);
        pickerMethod.setAccessible(true);var picker=(Aquifer.FluidPicker)pickerMethod.invoke(null,settings);
        var markerField=Class.forName("net.minecraft.world.level.levelgen.DensityFunctions$BeardifierMarker").getDeclaredField("INSTANCE");
        markerField.setAccessible(true);var marker=markerField.get(null);
        var factory=java.util.Arrays.stream(NoiseChunk.class.getMethods()).filter(m->m.getName().equals("forChunk")).findFirst().orElseThrow();
        var bounds=LevelHeightAccessor.create(-672,992);
        for(int[] at:new int[][]{{-2048,-1728},{4608,1024},{6400,5120},{-1200,-2176}})
        {
            var c=new ProtoChunk(new ChunkPos(at[0]/16,at[1]/16),UpgradeData.EMPTY,LevelHeightAccessor.create(-128,448),registry,null);
            c.getOrCreateNoiseChunk(q->{try{return (NoiseChunk)factory.invoke(null,q,random,marker,settings,picker,Blender.empty());}
                catch(ReflectiveOperationException failure){throw new IllegalStateException(failure);}});
            original.fillFromNoise(Runnable::run,Blender.empty(),random,null,c).join();
            TvWorldPreviewTerrain.shape(c);
            var p=new BlockPos.MutableBlockPos();
            for(int dz:new int[]{0,15})for(int dx:new int[]{0,15})
            {
                int x=at[0]+dx,z=at[1]+dz;
                var col=shaped.getBaseColumn(x,z,bounds,random);
                for(int y=-128;y<320;y++)if(c.getBlockState(p.set(x,y,z))!=col.getBlock(y))
                    throw new AssertionError("Fresh chunk/base column differ at "+x+","+y+","+z);
                for(var type:new Heightmap.Types[]{Heightmap.Types.OCEAN_FLOOR_WG,Heightmap.Types.WORLD_SURFACE_WG})
                {
                    int top=-128;
                    for(int y=319;y>=-128;y--)if(type.isOpaque().test(col.getBlock(y))){top=y+1;break;}
                    if(top!=shaped.getBaseHeight(x,z,type,bounds,random))
                        throw new AssertionError("Native base height disagrees with final generated column");
                }
            }
            if (at[0] == -1200 && at[1] == -2176 && PlaytestLandscapeR64.hasSurvey())
            {
                PlaytestLandscapeR64.decorate(c);
                int x = -1191, z = -2163;
                if (!c.getBlockState(p.set(x, 59, z)).is(Blocks.STONE)
                        || !c.getBlockState(p.set(x, 63, z)).isAir())
                    throw new AssertionError("Regenerated northwest bay bed or headroom differs from the save");
                for (int y = 60; y <= 62; y++)
                {
                    var water = c.getBlockState(p.set(x, y, z));
                    if (!water.is(Blocks.WATER) || !water.getFluidState().isSource())
                        throw new AssertionError("Missing source water in regenerated northwest bay at Y" + y);
                }
            }
        }
    }
}

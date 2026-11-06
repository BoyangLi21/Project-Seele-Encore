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
        for (int[] at : new int[][]{{-4096,-1000},{0,-3072},{6500,-6500}})
        {
            var retained = HakoneSurfaceField.sample(at[0],at[1],45);
            if (retained.ground()!=45 || retained.water()!=62)
                throw new AssertionError("Legacy continent/UN exterior lost its original water datum");
        }
        for (int[] at : new int[][]{{6500,1000},{3000,5200},{6500,5200}})
        {
            var sea = HakoneSurfaceField.sample(at[0],at[1],45);
            if (sea.ground()!=-99 || sea.water()!=-82)
                throw new AssertionError("Surveyed coast did not continue into the unsaved exterior");
        }
        var lake=HakoneSurfaceField.sample(-1230,-1802,45);
        var bank=HakoneSurfaceField.sample(-1228,-1802,45);
        if(lake.water()!=62 || bank.ground()<62)
            throw new AssertionError("Truncated old water/bank boundary was not retained in generation");
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
        System.out.println("Hakone boundary PASS: retained native waters, continuous coast/watershed, matching chunk/column/height consumers, underground retained");
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
        for(int[] at:new int[][]{{-2048,-1728},{4608,1024},{6400,5120}})
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
        }
    }
}

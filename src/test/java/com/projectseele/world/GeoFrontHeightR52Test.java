package com.projectseele.world;

import com.google.gson.*;
import com.mojang.serialization.JsonOps;
import com.mojang.serialization.Lifecycle;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.SharedConstants;
import net.minecraft.core.*;
import net.minecraft.core.registries.Registries;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.*;
import net.minecraft.world.level.biome.*;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.*;
import net.minecraft.world.level.levelgen.*;

/** Detached native columns/chunks only; no Level, save, actors or game. */
public final class GeoFrontHeightR52Test
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static JsonObject resource(String name)throws Exception
    {
        try(var stream=GeoFrontHeightR52Test.class.getResourceAsStream(name))
        {if(stream==null)throw new AssertionError("Height resource missing: "+name);return JsonParser.parseReader(new InputStreamReader(stream,StandardCharsets.UTF_8)).getAsJsonObject();}
    }
    private static long oldBlocks(ChunkAccess chunk)
    {
        long hash=17;var pos=new BlockPos.MutableBlockPos();int x0=chunk.getPos().getMinBlockX(),z0=chunk.getPos().getMinBlockZ();
        for(int y=GeoFrontHeightR52.LEGACY_MIN_Y;y<GeoFrontHeightR52.MAX_Y_EXCLUSIVE;y++)for(int z=z0;z<z0+16;z++)for(int x=x0;x<x0+16;x++)hash=hash*31+Block.getId(chunk.getBlockState(pos.set(x,y,z)));
        return hash;
    }
    public static void main(String[] args)throws Exception
    {
        SharedConstants.tryDetectVersion();
        // A bare JavaExec has no ModLauncher network event transformation.
        // Initialize native registries only; no Forge network/game bootstrap.
        var ready=Bootstrap.class.getDeclaredField("isBootstrapped");ready.setAccessible(true);ready.setBoolean(null,true);
        BuiltInRegistries.bootStrap();
        // Forge's normal registry snapshot initializes collision/solid caches;
        // do only that native state work without its network initialization.
        for(var block:BuiltInRegistries.BLOCK)for(var state:block.getStateDefinition().getPossibleStates())state.initCache();
        check(Blocks.DEEPSLATE.defaultBlockState().blocksMotion(),"Detached native solid-state cache was not initialized");
        var definition=resource("/data/projectseele/dimension_type/geofront.json");
        if(!NervRouteRuntimeR52.mapRebuildEnabledR52())
        {
            check(definition.get("min_y").getAsInt()==-672,"Rollback moved the original minimum");
            check(definition.get("height").getAsInt()==992,"Rollback changed original section count");
            check(definition.get("logical_height").getAsInt()==992,"Rollback changed logical height");
            var legacyNoise=resource("/data/projectseele/worldgen/noise_settings/geofront_surface.json").getAsJsonObject("noise");
            check(legacyNoise.get("min_y").getAsInt()==-672&&legacyNoise.get("height").getAsInt()==992,"Rollback changed original noise interval");
            System.out.println("R52 rollback height contract PASS: original -672..320; migrated-map checks remain deferred");
            return;
        }
        check(definition.get("min_y").getAsInt()==GeoFrontHeightR52.MIN_Y,"Build minimum differs");
        check(definition.get("height").getAsInt()==GeoFrontHeightR52.HEIGHT,"Build height differs");
        check(definition.get("logical_height").getAsInt()==GeoFrontHeightR52.HEIGHT,"Logical height differs");
        check(GeoFrontHeightR52.MIN_Y+GeoFrontHeightR52.HEIGHT==320,"Existing upper limit moved");
        var oldHeight=LevelHeightAccessor.create(-672,992);var extended=LevelHeightAccessor.create(-960,1280);
        check(oldHeight.getSectionsCount()==62&&extended.getSectionsCount()==80,"Wrong section expansion");
        check(extended.getMinSection()==-60&&extended.getMaxSection()==20,"Section absolute coordinates shifted");
        var lookup=VanillaRegistries.createLookup();var noise=resource("/data/projectseele/worldgen/noise_settings/geofront_surface.json");
        var settings=NoiseGeneratorSettings.DIRECT_CODEC.parse(RegistryOps.create(JsonOps.INSTANCE,lookup),noise).getOrThrow(false,message->{throw new AssertionError(message);});
        check(settings.noiseSettings().minY()==-672&&settings.noiseSettings().height()==992,"Legacy noise interval changed");
        var biome=lookup.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS);
        var source=new FixedBiomeSource(biome);var original=new NoiseBasedChunkGenerator(source,Holder.direct(settings));
        var generator=new GeoFrontBoundedChunkGenerator(source,Holder.direct(settings),0,68);
        var context=new WorldGenerationContext(generator,extended);
        check(context.getMinGenY()==-672&&context.getGenDepth()==992,"Old above_bottom/surface context moved");
        for(long seed:new long[]{0,14052})
        {
            var state=RandomState.create(settings,lookup.lookupOrThrow(Registries.NOISE),seed);
            check(generator.getBaseHeight(0,0,Heightmap.Types.OCEAN_FLOOR_WG,LevelHeightAccessor.create(-960,288),state)==-672,"Deep-only height query omitted solid foundation");
            check(generator.getBaseHeight(0,0,Heightmap.Types.OCEAN_FLOOR_WG,LevelHeightAccessor.create(-1024,64),state)==-1024,"Outside build bounds became a solid column");
            for(var at:new int[][]{{0,0},{15,-17},{-33,48}})
            {
                var before=original.getBaseColumn(at[0],at[1],oldHeight,state);var after=generator.getBaseColumn(at[0],at[1],extended,state);
                for(int y=-672;y<320;y++)check(before.getBlock(y)==after.getBlock(y),"Original noise column changed at Y="+y);
                for(int y=-960;y<-672;y++)check(after.getBlock(y).is(y==-960?Blocks.BEDROCK:Blocks.DEEPSLATE),"New deep column is missing solid geology");
                check(after.getBlock(-961).isAir()&&after.getBlock(320).isAir(),"Column exceeded declared build bounds");
                check(original.getBaseHeight(at[0],at[1],Heightmap.Types.OCEAN_FLOOR_WG,oldHeight,state)==generator.getBaseHeight(at[0],at[1],Heightmap.Types.OCEAN_FLOOR_WG,extended,state),"Original top/base height moved");
            }
        }
        var registry=new MappedRegistry<Biome>(Registries.BIOME,Lifecycle.stable());registry.register(Biomes.PLAINS,biome.value(),Lifecycle.stable());registry.freeze();
        var chunk=new ProtoChunk(new ChunkPos(-2,3),UpgradeData.EMPTY,extended,registry,null);
        var pos=new BlockPos.MutableBlockPos();int x0=chunk.getPos().getMinBlockX(),z0=chunk.getPos().getMinBlockZ();
        for(int y=-672;y<320;y++)for(int z=z0;z<z0+16;z++)for(int x=x0;x<x0+16;x++)
        {
            var block=y<68?(y==-672?Blocks.BEDROCK:(x+z+y)%11==0?Blocks.WATER:Blocks.STONE):y==68?Blocks.GRASS_BLOCK:Blocks.AIR;
            chunk.setBlockState(pos.set(x,y,z),block.defaultBlockState(),false);
        }
        Heightmap.primeHeightmaps(chunk,EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG,Heightmap.Types.OCEAN_FLOOR_WG));
        long before=oldBlocks(chunk);int surface=chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG,0,0);
        var originalSections=chunk.getSections().clone();var originalMaps=new EnumMap<Heightmap.Types,long[]>(Heightmap.Types.class);
        for(var entry:chunk.getHeightmaps())originalMaps.put(entry.getKey(),entry.getValue().getRawData().clone());
        GeoFrontHeightR52.fillFoundation(chunk);
        check(oldBlocks(chunk)==before,"Foundation rewrote an original section/city block");
        for(int i=18;i<originalSections.length;i++)check(chunk.getSection(i)==originalSections[i],"Original upper section replaced");
        for(var entry:chunk.getHeightmaps())check(Arrays.equals(originalMaps.get(entry.getKey()),entry.getValue().getRawData()),"An existing high heightmap column changed");
        for(int i=0;i<18;i++)
        {
            var section=chunk.getSection(i);check(section.getBiomes()==originalSections[i].getBiomes(),"Original sampled biome palette replaced");
            check(!section.hasOnlyAir()&&!section.isRandomlyTicking()&&!section.isRandomlyTickingFluids(),"Native section counts were not reconstructed");
            int[] counted={0,0};section.getStates().count((state,count)->{if(state.is(Blocks.BEDROCK))counted[0]+=count;else if(state.is(Blocks.DEEPSLATE))counted[1]+=count;else throw new AssertionError("Unexpected deep palette state");});
            check(counted[0]==(i==0?256:0)&&counted[1]==(i==0?3840:4096),"Native palette block counts differ");
        }
        for(int y=-960;y<-672;y++)for(int z=z0;z<z0+16;z++)for(int x=x0;x<x0+16;x++)check(chunk.getBlockState(pos.set(x,y,z)).is(y==-960?Blocks.BEDROCK:Blocks.DEEPSLATE),"Detached deep section contains void");
        Heightmap.primeHeightmaps(chunk,EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG,Heightmap.Types.OCEAN_FLOOR_WG));
        check(chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG,0,0)==surface,"Deep foundation moved the existing surface");
        check(chunk.getOrCreateHeightmapUnprimed(Heightmap.Types.WORLD_SURFACE_WG).getRawData().length==52,"Extended heightmap was not 11-bit/native packed");
        var empty=new ProtoChunk(new ChunkPos(0,0),UpgradeData.EMPTY,extended,registry,null);
        Heightmap.primeHeightmaps(empty,EnumSet.of(Heightmap.Types.WORLD_SURFACE_WG,Heightmap.Types.OCEAN_FLOOR_WG));GeoFrontHeightR52.fillFoundation(empty);
        check(empty.getHeight(Heightmap.Types.WORLD_SURFACE_WG,0,0)==-673&&empty.getHeight(Heightmap.Types.OCEAN_FLOOR_WG,0,0)==-673,"Previously empty column omitted new solid top in heightmap: "+empty.getHeight(Heightmap.Types.WORLD_SURFACE_WG,0,0)+"/"+empty.getHeight(Heightmap.Types.OCEAN_FLOOR_WG,0,0));
        var legacy=new ProtoChunk(new ChunkPos(0,0),UpgradeData.EMPTY,oldHeight,registry,null);legacy.setBlockState(new BlockPos(1,-672,1),Blocks.GOLD_BLOCK.defaultBlockState(),false);long legacyBefore=oldBlocks(legacy);GeoFrontHeightR52.fillFoundation(legacy);check(oldBlocks(legacy)==legacyBefore,"Legacy dimension was altered");
        System.out.println("GeoFront height PASS checks="+checks+": build -960..320, 18 added solid sections, exact unchanged old noise columns/context/top, detached old blocks unchanged, new native 11-bit heightmaps; no world save/game");
    }
}

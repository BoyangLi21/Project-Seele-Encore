import com.google.gson.JsonParser;
import com.mojang.serialization.JsonOps;
import com.mojang.serialization.Lifecycle;
import java.nio.file.*;
import java.io.*;
import net.minecraft.SharedConstants;
import net.minecraft.core.Holder;
import net.minecraft.core.MappedRegistry;
import net.minecraft.core.registries.*;
import net.minecraft.data.registries.VanillaRegistries;
import net.minecraft.resources.RegistryOps;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.level.LevelHeightAccessor;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.biome.*;
import net.minecraft.world.level.chunk.*;
import net.minecraft.world.level.levelgen.*;
import net.minecraft.world.level.levelgen.blending.Blender;

/** Detached native density samples; never opens a Level or a save for writing. */
public final class HakoneNativeSurfaceSampler
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 4 || args.length > 5) throw new IllegalArgumentException("settings.json seed points.csv output.csv [chunks]");
        SharedConstants.tryDetectVersion();
        var ready = Bootstrap.class.getDeclaredField("isBootstrapped");
        ready.setAccessible(true);
        ready.setBoolean(null, true);
        BuiltInRegistries.bootStrap();
        for (var block : BuiltInRegistries.BLOCK)
            for (var state : block.getStateDefinition().getPossibleStates()) state.initCache();
        var lookup = VanillaRegistries.createLookup();
        var json = JsonParser.parseString(Files.readString(Path.of(args[0])));
        var settings = NoiseGeneratorSettings.DIRECT_CODEC.parse(RegistryOps.create(JsonOps.INSTANCE, lookup), json)
                .getOrThrow(false, message -> { throw new IllegalArgumentException(message); });
        var biome = lookup.lookupOrThrow(Registries.BIOME).getOrThrow(Biomes.PLAINS);
        var generator = new NoiseBasedChunkGenerator(new FixedBiomeSource(biome), Holder.direct(settings));
        var random = RandomState.create(settings, lookup.lookupOrThrow(Registries.NOISE), Long.parseLong(args[1]));
        var bounds = LevelHeightAccessor.create(settings.noiseSettings().minY(), settings.noiseSettings().height());
        if (args.length == 5)
        {
            if (!args[4].equals("chunks")) throw new IllegalArgumentException("Unknown sampling mode");
            var registry = new MappedRegistry<Biome>(Registries.BIOME, Lifecycle.stable());
            registry.register(Biomes.PLAINS, biome.value(), Lifecycle.stable()); registry.freeze();
            var pickerMethod = NoiseBasedChunkGenerator.class.getDeclaredMethod("createFluidPicker", NoiseGeneratorSettings.class);
            pickerMethod.setAccessible(true);
            var picker = (Aquifer.FluidPicker) pickerMethod.invoke(null, settings);
            var markerType = Class.forName("net.minecraft.world.level.levelgen.DensityFunctions$BeardifierMarker");
            var markerField = markerType.getDeclaredField("INSTANCE"); markerField.setAccessible(true);
            var marker = markerField.get(null);
            var noiseFactory = java.util.Arrays.stream(NoiseChunk.class.getMethods())
                    .filter(m -> m.getName().equals("forChunk")).findFirst().orElseThrow();
            int chunks = 0;
            try (var input = Files.newBufferedReader(Path.of(args[2]));
                 var output = Files.newBufferedWriter(Path.of(args[3])))
            {
                output.write("x,z,ground,water\n");
                while (true)
                {
                    var batch = new java.util.ArrayList<ProtoChunk>();
                    var pending = new java.util.ArrayList<java.util.concurrent.CompletableFuture<ChunkAccess>>();
                    while (batch.size()<8)
                    {
                        String row = input.readLine();
                        if (row==null) break;
                        if (row.isBlank() || row.startsWith("x,")) continue;
                        String[] parts = row.split(",");
                        int cx = Integer.parseInt(parts[0]), cz = Integer.parseInt(parts[1]);
                        var chunk = new ProtoChunk(new ChunkPos(cx,cz), UpgradeData.EMPTY,
                                LevelHeightAccessor.create(-128,448), registry, null);
                        chunk.getOrCreateNoiseChunk(c -> {
                            try { return (NoiseChunk) noiseFactory.invoke(null,c,random,marker,settings,picker,Blender.empty()); }
                            catch (ReflectiveOperationException failure) { throw new IllegalStateException(failure); }
                        });
                        // No Level/StructureManager is needed: the native
                        // noise chunk was explicitly built without structures.
                        pending.add(generator.fillFromNoise(Runnable::run,Blender.empty(),random,null,chunk));
                        batch.add(chunk);
                    }
                    if (batch.isEmpty()) break;
                    for (var future : pending) future.join();
                    for (var chunk : batch)
                    {
                        int cx=chunk.getPos().x,cz=chunk.getPos().z;
                        for (int z=cz*16;z<cz*16+16;z++) for (int x=cx*16;x<cx*16+16;x++)
                        {
                            int ground=chunk.getHeight(Heightmap.Types.OCEAN_FLOOR_WG,x&15,z&15);
                            if (chunks<3 && (x&7)==0 && (z&7)==0
                                    && ground!=generator.getBaseHeight(x,z,Heightmap.Types.OCEAN_FLOOR_WG,bounds,random)-1)
                                throw new AssertionError("Detached chunk/column disagreement at "+x+","+z);
                            output.write(x+","+z+","+ground+","+(ground<settings.seaLevel()-1?settings.seaLevel()-1:-32768)+"\n");
                        }
                        if (++chunks%100==0) { output.flush(); System.out.println("Native chunks "+chunks); }
                    }
                }
            }
            System.out.println("Complete: "+chunks+" detached chunks; no world writes");
            return;
        }
        int count = 0;
        try (var input = Files.newBufferedReader(Path.of(args[2]));
             var output = Files.newBufferedWriter(Path.of(args[3])))
        {
            output.write("x,z,ground,water\n");
            for (String row; (row = input.readLine()) != null;)
            {
                if (row.isBlank() || row.startsWith("x,")) continue;
                String[] parts = row.split(",");
                int x = Integer.parseInt(parts[0]), z = Integer.parseInt(parts[1]);
                int ground = generator.getBaseHeight(x, z, Heightmap.Types.OCEAN_FLOOR_WG, bounds, random) - 1;
                int water = ground < settings.seaLevel() - 1 ? settings.seaLevel() - 1 : -32768;
                output.write(x + "," + z + "," + ground + "," + water + "\n");
                if (++count % 5000 == 0) { output.flush(); System.out.println("Native columns " + count); }
            }
        }
        System.out.println("Complete: " + count + " detached columns; no world writes");
    }
}

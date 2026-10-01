package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Parent-scheduled real incomplete-chunk generation, separate from dry-run overlays. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class EcologyFutureGenerationR44
{
    private static final String JOB=System.getProperty("projectseele.r44EcologyFutureJob","");
    private static boolean done;private static int age,cursor;private static JsonObject input;
    private static final JsonArray cases=new JsonArray();
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(JOB.isEmpty()||done||event.phase!=TickEvent.Phase.END)return;
        try
        {
            if(++age<40)return;Path world=event.getServer().getWorldPath(LevelResource.ROOT).toAbsolutePath().normalize();
            if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalStateException("Fresh ecology fixture refuses a different world");
            if(input==null)input=JsonParser.parseString(Files.readString(Path.of(JOB),StandardCharsets.UTF_8)).getAsJsonObject();
            ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);
            if(!(level.getChunkSource().getGenerator() instanceof GeoFrontBoundedChunkGenerator)
                    ||!(level.getChunkSource().getGenerator().getBiomeSource() instanceof RegionalEcologyBiomeSourceR44))
                throw new IllegalStateException("Future source fixture requires the actual installed bounded ecology generator");
            JsonArray chunks=input.getAsJsonArray("chunks");
            if(cursor<chunks.size())
            {
                JsonObject q=chunks.get(cursor++).getAsJsonObject();String before=q.get("measured_status").getAsString();
                if(before.equals("full")||before.equals("missing"))throw new IllegalStateException("Expected an existing incomplete chunk source case");
                int x=q.get("x").getAsInt(),z=q.get("z").getAsInt();var chunk=level.getChunk(x,z);
                JsonObject counts=new JsonObject();int logs=0,leaves=0,flowers=0,grass=0;
                for(int y=-512;y<310;y++)for(int dz=0;dz<16;dz++)for(int dx=0;dx<16;dx++)
                {
                    var state=chunk.getBlockState(new BlockPos(x*16+dx,y,z*16+dz));String name=BuiltInRegistries.BLOCK.getKey(state.getBlock()).getPath();
                    if(name.endsWith("_log"))logs++;else if(name.endsWith("_leaves"))leaves++;
                    else if(name.equals("grass")||name.equals("tall_grass")||name.equals("fern"))grass++;
                    else if(name.equals("dandelion")||name.equals("cornflower")||name.equals("poppy")||name.equals("oxeye_daisy")||name.equals("allium"))flowers++;
                }
                counts.addProperty("logs",logs);counts.addProperty("leaves",leaves);counts.addProperty("grass",grass);counts.addProperty("flowers",flowers);
                JsonObject result=q.deepCopy();result.addProperty("after_status",chunk.getStatus().toString());result.add("native_generation_counts",counts);cases.add(result);return;
            }
            JsonObject result=new JsonObject();result.addProperty("actual_world_generation",true);result.addProperty("overlay_preview",false);
            result.addProperty("passed",true);result.addProperty("world_seed",level.getSeed());result.add("cases",cases);
            Files.writeString(Path.of(JOB+".complete.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result),StandardCharsets.UTF_8);done=true;
        }
        catch(Throwable error)
        {
            JsonObject result=new JsonObject();result.addProperty("passed",false);result.addProperty("error",error.toString());result.add("cases",cases);
            try{Files.writeString(Path.of(JOB+".failed.json"),result.toString(),StandardCharsets.UTF_8);}catch(Exception ignored){}
            done=true;ProjectSeele.LOGGER.error("Real future ecology source fixture failed",error);
        }
    }
    private EcologyFutureGenerationR44(){}
}

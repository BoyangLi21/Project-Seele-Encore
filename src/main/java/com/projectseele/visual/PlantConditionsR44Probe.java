package com.projectseele.visual;

import com.google.gson.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.TicketType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.LightLayer;
import net.minecraft.world.level.block.state.BlockState;
import java.nio.file.*;
import java.util.*;
import java.util.function.Function;

/** Explicit, bounded server-side observations; never places a candidate plant. */
final class PlantConditionsR44Probe
{
    private static final String INPUT=System.getProperty("projectseele.r44PlantConditionsInput","");
    private static final String OUTPUT=System.getProperty("projectseele.r44PlantConditionsOutput","");
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_plant_condition_probe",
            Comparator.comparingLong(ChunkPos::toLong),100);
    private static JsonArray requests;
    private static final JsonArray before=new JsonArray();
    private static final Set<ChunkPos> leases=new LinkedHashSet<>();
    private static int elapsed;
    private static boolean complete;

    private static BlockPos position(JsonObject row)
    {
        JsonArray p=row.getAsJsonArray("position");
        if(p.size()!=3)throw new IllegalArgumentException("Plant probe requires three coordinates");
        return new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt());
    }

    static boolean advance(ServerLevel level,Function<String,BlockState> parser)throws Exception
    {
        if(INPUT.isEmpty()||complete)return true;
        if(!Path.of(INPUT).isAbsolute()||!Path.of(OUTPUT).isAbsolute())throw new IllegalArgumentException("Explicit absolute probe input/output required");
        if(requests==null)
        {
            requests=JsonParser.parseString(Files.readString(Path.of(INPUT))).getAsJsonArray();
            if(requests.isEmpty()||requests.size()>64)throw new IllegalArgumentException("Plant probe must contain1–64 samples");
            for(var element:requests)
            {
                var row=element.getAsJsonObject();var p=position(row);var chunk=new ChunkPos(p);
                if(level.isOutsideBuildHeight(p)||row.getAsJsonArray("states").size()>16)throw new IllegalArgumentException("Invalid bounded plant probe");
                var prior=new JsonObject();prior.addProperty("chunk_loaded",level.getChunkSource().getChunkNow(chunk.x,chunk.z)!=null);
                prior.addProperty("entity_ticking",level.isPositionEntityTicking(p));before.add(prior);
                leases.add(chunk);level.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);level.getChunk(chunk.x,chunk.z);
            }
            return false;
        }
        elapsed++;
        if(elapsed%40==0)for(var chunk:leases)level.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);
        if(elapsed<40)return false;
        boolean lightingReady=true;
        for(var element:requests)lightingReady&=level.getChunkAt(position(element.getAsJsonObject())).isLightCorrect();
        if(!lightingReady&&elapsed<200)return false;
        var samples=new JsonArray();int index=0;
        for(var element:requests)
        {
            var request=element.getAsJsonObject();var p=position(request);var chunk=level.getChunkAt(p);
            var row=new JsonObject();row.addProperty("name",request.get("name").getAsString());row.add("position",request.get("position").deepCopy());
            row.add("before_probe_ticket",before.get(index++));row.addProperty("loaded_with_probe_ticket",true);
            row.addProperty("chunk_light_correct",chunk.isLightCorrect());row.addProperty("entity_ticking_during_probe",level.isPositionEntityTicking(p));
            row.addProperty("block_ticking_during_probe",level.getChunkSource().isPositionTicking(chunk.getPos().toLong()));
            row.addProperty("actual_state",level.getBlockState(p).toString());row.addProperty("actual_ground",level.getBlockState(p.below()).toString());
            row.addProperty("block_light",level.getBrightness(LightLayer.BLOCK,p));row.addProperty("sky_light",level.getBrightness(LightLayer.SKY,p));
            row.addProperty("raw_brightness_at_plant",level.getMaxLocalRawBrightness(p));
            int above=level.getMaxLocalRawBrightness(p.above());row.addProperty("raw_brightness_above_plant",above);
            row.addProperty("sapling_light_threshold_at_least_9",above>=9);
            row.addProperty("grass_spread_light_threshold_at_least_9",level.getMaxLocalRawBrightness(p)>=9);
            var states=new JsonArray();
            for(var s:request.getAsJsonArray("states"))
            {
                BlockState state=parser.apply(s.getAsString());var candidate=new JsonObject();candidate.addProperty("state",s.getAsString());
                candidate.addProperty("can_survive_here",state.canSurvive(level,p));states.add(candidate);
            }
            row.add("candidate_states_not_placed",states);samples.add(row);
        }
        var result=new JsonObject();result.add("samples",samples);result.addProperty("all_lighting_complete",lightingReady);
        result.addProperty("settle_server_ticks",elapsed);result.addProperty("random_tick_speed",level.getGameRules().getInt(GameRules.RULE_RANDOMTICKING));
        result.addProperty("day_time",level.getDayTime());result.addProperty("dimension_has_skylight",level.dimensionType().hasSkyLight());
        result.addProperty("dimension_ambient_light",level.dimensionType().ambientLight());
        result.addProperty("explicit_block_writes",false);result.addProperty("natural_growth_executed",false);
        result.addProperty("scope","Probe-owned tickets temporarily load/tick these known source chunks. Ticking during sampling is not proof of ordinary distant ticking; canSurvive is not proof of random-tick growth. Incomplete lighting leaves light conclusions unverified.");
        Files.writeString(Path.of(OUTPUT),new GsonBuilder().setPrettyPrinting().create().toJson(result));
        for(var chunk:leases)level.getChunkSource().removeRegionTicket(TICKET,chunk,3,chunk);
        leases.clear();complete=true;return true;
    }
}

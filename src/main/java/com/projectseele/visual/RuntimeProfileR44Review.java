package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.*;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.server.level.DistanceManager;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.Ticket;
import net.minecraft.world.level.ChunkPos;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;

/** Same room, no active dossier or command; raw tick times and actual loaded vehicles. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RuntimeProfileR44Review
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r44RuntimeProfileReview");
    public static volatile boolean done;
    private static int age;
    private static long began;
    private static final JsonArray SAMPLES=new JsonArray();
    private static final String TICKET_TRACE=System.getProperty("projectseele.r44ChunkTicketTrace", "");
    private static long ticketAge;
    private static final JsonArray TICKET_SAMPLES=new JsonArray();
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!TICKET_TRACE.isBlank() && event.phase==TickEvent.Phase.END)
        {
            ticketAge++;
            if(ticketAge==1 || ticketAge==20 || ticketAge%100==0)
                traceTickets(event.getServer().getLevel(FacilitySchemaV2.DIMENSION));
        }
        if(!ENABLED||done)return;var server=event.getServer();var world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))throw new IllegalStateException("Runtime profile refuses owner world");
        if(server.getPlayerList().getPlayers().isEmpty())return;
        if(event.phase==TickEvent.Phase.START){began=System.nanoTime();return;}
        try
        {
            var level=server.getLevel(FacilitySchemaV2.DIMENSION);var player=server.getPlayerList().getPlayers().get(0);
            if(++age==40){player.stopRiding();player.setGameMode(GameType.SPECTATOR);player.teleportTo(level,37.5,-406,390.5,0,0);}
            if(age<200)return;
            if(age==200)Files.writeString(world.resolve("r44_runtime_profile_ready.json"),"{}");
            if(age%5==0)
            {
                var row=new JsonObject();row.addProperty("age",age);row.addProperty("server_tick_ms",(System.nanoTime()-began)/1e6);
                int vehicles=0;for(var entity:level.getAllEntities())if(BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType()).getNamespace().equals("superbwarfare"))vehicles++;
                row.addProperty("loaded_sbw_entities",vehicles);row.addProperty("loaded_chunks",level.getChunkSource().getLoadedChunksCount());
                row.add("parking_tickets",new Gson().toJsonTree(SbwParkingTicketsR44.diagnostics()));SAMPLES.add(row);
            }
            if(age>=1400)
            {
                var result=new JsonObject();result.addProperty("original_idle_ticket_behavior",Boolean.getBoolean("projectseele.keepIdleVehicleTickets"));result.add("samples",SAMPLES);
                Files.writeString(world.resolve("r44_runtime_profile.json"),new Gson().toJson(result));done=true;
            }
        }
        catch(Exception error){done=true;throw new IllegalStateException(error);}
    }

    /** Read-only diagnostics: never remove a ticket or force a chunk for measurement. */
    private static void traceTickets(ServerLevel level)
    {
        if(level==null)return;
        try
        {
            var world=level.getServer().getWorldPath(LevelResource.ROOT).normalize();
            if(!world.getFileName().toString().equals("SEELE_FIELD_R44_REVIEW"))
                throw new IllegalStateException("Chunk ticket trace refuses another world");
            var row=new JsonObject();row.addProperty("tick",level.getGameTime());row.addProperty("trace_age",ticketAge);
            row.addProperty("loaded_chunks",level.getChunkSource().getLoadedChunksCount());
            var runtime=Runtime.getRuntime();row.addProperty("used_heap_bytes",runtime.totalMemory()-runtime.freeMemory());
            row.addProperty("committed_heap_bytes",runtime.totalMemory());row.addProperty("max_heap_bytes",runtime.maxMemory());
            var manager=level.getChunkSource().chunkMap.getDistanceManager();
            row.addProperty("distance_manager_status",manager.getDebugStatus());
            var maps=new JsonObject();
            // The pinned mapped development runtime exposes these actual fields.
            // Discover both ticket maps by their declared type and record field identity,
            // avoiding an assumption that the first map is the ordinary ticket map.
            for(var field:DistanceManager.class.getDeclaredFields())
            {
                if(!it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap.class.isAssignableFrom(field.getType()))continue;
                field.setAccessible(true);
                var map=(it.unimi.dsi.fastutil.longs.Long2ObjectOpenHashMap<?>)field.get(manager);
                var summary=new JsonObject();summary.addProperty("ticket_origin_chunks",map.size());
                var counts=new java.util.TreeMap<String,Integer>();var examples=new JsonArray();
                int tickets=0;
                for(var entry:map.long2ObjectEntrySet())
                {
                    if(!(entry.getValue() instanceof Iterable<?> values))continue;
                    for(var value:values)
                    {
                        if(!(value instanceof Ticket<?> ticket))continue;
                        tickets++;String key=ticket.getType()+"/level="+ticket.getTicketLevel();
                        int count=counts.merge(key,1,Integer::sum);
                        if(count<=12)
                        {
                            var at=new ChunkPos(entry.getLongKey());var example=new JsonObject();
                            example.addProperty("type_level",key);example.addProperty("x",at.x);example.addProperty("z",at.z);
                            example.addProperty("actual_ticket",ticket.toString());examples.add(example);
                        }
                    }
                }
                summary.addProperty("tickets",tickets);summary.add("type_level_histogram",new Gson().toJsonTree(counts));
                summary.add("bounded_examples",examples);maps.add(field.getName(),summary);
            }
            row.add("actual_ticket_maps",maps);TICKET_SAMPLES.add(row);
            // Keep the first startup snapshots plus the recent tail on lengthy authors.
            if(TICKET_SAMPLES.size()>100)TICKET_SAMPLES.remove(2);
            var report=new JsonObject();report.add("samples",TICKET_SAMPLES);
            report.addProperty("scope","Read-only live ticket origins/types/levels. Loaded dependent chunks exceed origin counts; no attribution from saved NBT alone. Reflection does not mutate ticket maps.");
            Files.writeString(Path.of(TICKET_TRACE),new Gson().toJson(report));
        }
        catch(Exception error){throw new IllegalStateException("Native chunk-ticket measurement failed",error);}
    }
    private RuntimeProfileR44Review() {}
}

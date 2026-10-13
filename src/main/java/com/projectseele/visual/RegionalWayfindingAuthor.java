package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.nbt.*;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.server.level.TicketType;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Explicit, idempotent installation of persistent, non-colliding architectural labels. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class RegionalWayfindingAuthor
{
    private static final boolean ENABLED="wayfinding".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_wayfinding",Comparator.comparingLong(ChunkPos::toLong),200);
    private static int age;
    private static JsonArray labels;
    private static boolean done;
    private static ListTag floats(float... values)
    {
        ListTag list=new ListTag();for(float value:values)list.add(FloatTag.valueOf(value));return list;
    }
    @SubscribeEvent
    public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();
        if(com.projectseele.world.NervLegacyGenerationGuardR52.retired(server))return;
        var world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals("SEELE_TV_WORLD_PREVIEW_20260906"))throw new IllegalStateException("Wrong wayfinding world");
        try
        {
            var level=server.getLevel(FacilitySchemaV2.DIMENSION);
            if(++age<80)return;
            if (com.projectseele.world.TvDetailR04Layout.active(level))
                com.projectseele.world.TerminalDogmaBuilder.repairRuntimeSpecimen(level,
                        com.projectseele.world.IntegratedNervMapBuilder.GEOFRONT_ORIGIN);
            if(labels==null)
            {
                labels=JsonParser.parseString(Files.readString(world.resolve("regional_wayfinding.json"))).getAsJsonArray();
                for(var item:labels)
                {
                    var pos=item.getAsJsonObject().getAsJsonArray("position");ChunkPos chunk=new ChunkPos((int)Math.floor(pos.get(0).getAsDouble())>>4,(int)Math.floor(pos.get(2).getAsDouble())>>4);
                    level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);level.getChunk(chunk.x,chunk.z);
                }
                age=80;return;
            }
            if(age<120)return;
            for(String retired:List.of("r04/airport/bay/departures","r04/airport/hakone/departures"))
            {
                UUID id=UUID.nameUUIDFromBytes(("SEELE_R03_SIGN/"+retired).getBytes(StandardCharsets.UTF_8));
                var entity=level.getEntity(id);
                if(entity!=null&&entity.getType()==EntityType.TEXT_DISPLAY)entity.discard();
            }
            int count=0;
            for(var item:labels)
            {
                var d=item.getAsJsonObject();var pos=d.getAsJsonArray("position");
                UUID id=UUID.nameUUIDFromBytes(("SEELE_R03_SIGN/"+d.get("id").getAsString()).getBytes(StandardCharsets.UTF_8));
                var existing=level.getEntity(id);
                if(existing!=null&&existing.getType()!=EntityType.TEXT_DISPLAY)throw new IllegalStateException("Label UUID belongs to another entity");
                var display=existing!=null?existing:EntityType.TEXT_DISPLAY.create(level);
                CompoundTag tag=new CompoundTag();tag.putString("text",d.get("text").toString());
                tag.putInt("line_width",d.has("lineWidth")?d.get("lineWidth").getAsInt():240);
                tag.putInt("background",0);tag.putByte("text_opacity",(byte)-1);tag.putString("billboard","fixed");tag.putString("alignment","center");
                tag.putBoolean("shadow",false);tag.putBoolean("see_through",false);tag.putFloat("view_range",1.5F);
                tag.putBoolean("NoGravity",true);
                CompoundTag brightness=new CompoundTag();brightness.putInt("block",15);brightness.putInt("sky",0);tag.put("brightness",brightness);
                float scale=d.get("scale").getAsFloat();CompoundTag transform=new CompoundTag();
                transform.put("translation",floats(0,0,0));transform.put("scale",floats(scale,scale,scale));transform.put("left_rotation",floats(0,0,0,1));transform.put("right_rotation",floats(0,0,0,1));tag.put("transformation",transform);
                display.load(tag);display.setUUID(id);display.moveTo(pos.get(0).getAsDouble(),pos.get(1).getAsDouble(),pos.get(2).getAsDouble(),d.get("yaw").getAsFloat(),0);
                display.addTag("projectseele_r03_wayfinding");
                if(existing==null&&!level.addFreshEntity(display))throw new IllegalStateException("Cannot create label "+id);
                count++;
            }
            Files.writeString(world.resolve("regional_wayfinding_receipt.json"),"{\"labels\":"+count+",\"nativeTextDisplays\":true}");
            if (com.projectseele.world.TvDetailR04Layout.active(level))
            {
                JsonObject proof=new JsonObject();JsonArray specimens=new JsonArray();
                for(var entity:level.getEntitiesOfClass(com.projectseele.entity.LilithEntity.class,
                        com.projectseele.world.TvDetailR04Layout.specimenBounds()))
                {
                    JsonObject d=new JsonObject();d.addProperty("uuid",entity.getStringUUID());
                    d.addProperty("scale",entity.getContainmentScale());d.addProperty("position",entity.position().toString());specimens.add(d);
                }
                proof.add("specimens",specimens);
                var audit=com.projectseele.world.TerminalDogmaBuilder.inspect(level,
                        com.projectseele.world.IntegratedNervMapBuilder.GEOFRONT_ORIGIN);
                proof.addProperty("valid",audit.valid());proof.addProperty("audit",audit.toString());
                Files.writeString(world.resolve("regional_r04_specimen_receipt.json"),proof.toString());
                if(specimens.size()!=1||!audit.valid())throw new IllegalStateException("R04 specimen acceptance failed: "+proof);
            }
            ProjectSeele.LOGGER.info("REGIONAL WAYFINDING COMPLETE labels={}",count);done=true;server.halt(false);
        }
        catch(Exception failure)
        {
            ProjectSeele.LOGGER.error("REGIONAL WAYFINDING FAILED",failure);
            try{Files.writeString(world.resolve("regional_wayfinding_failure.txt"),failure.toString());}catch(Exception ignored){}
            done=true;server.halt(false);
        }
    }
}

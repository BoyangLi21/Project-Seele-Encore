package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import net.minecraft.server.level.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** A real, full-duration repair in an existing disposable copy; no timer shortcuts. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class BayRepairR33Review
{
    public static final boolean ENABLED="r33-repair".equals(System.getProperty("projectseele.regionalBuild",""));
    public static volatile boolean ready,done;
    public static volatile int actorId,elapsed;
    public static volatile String error="",shot="";
    public static final int SERIAL=Integer.getInteger("projectseele.bayRepairSerial",-1);
    public static final boolean VISUAL_ONLY=Boolean.getBoolean("projectseele.bayRepairVisual");
    public static final boolean WET_REVIEW=Boolean.getBoolean("projectseele.facilityWetReview");
    private static EvaUnit01Entity unit;private static long started;private static UUID original;
    private static final JsonArray samples=new JsonArray();private static int ticks,variant=1;
    private static final TicketType<ChunkPos> TICKET=TicketType.create("seele_repair_review",Comparator.comparingLong(ChunkPos::toLong));
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||!ready||done||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals(CombatR31Review.WORLD))throw new IllegalStateException("Repair fixture world boundary");
        try
        {
            var level=server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)throw new IllegalStateException("Missing facility");
            var pilot=server.getPlayerList().getPlayers().get(0);ticks++;
            if(ticks>3000)throw new IllegalStateException("Repair review deadline");
            if(unit==null)
            {
                if(SERIAL<0)for(int v=0;v<3;v++){var row=EvaFleetSavedData.get(server).entry(v).orElse(null);if(row!=null&&row.phase()==EvaFleetSavedData.Phase.PARKED){variant=v;break;}}
                var bed=SERIAL<0?EvaLogisticsDirector.assignedHangarBedR33(level,variant):net.minecraft.core.BlockPos.containing(UNRecoveryR22.home(level,SERIAL));var chunk=new ChunkPos(bed);level.getChunkSource().addRegionTicket(TICKET,chunk,4,chunk);level.getChunk(bed);
                original=SERIAL<0?EvaFleetSavedData.get(server).canonicalId(variant).orElseThrow():UNRecoveryR22.identity(level,SERIAL);
                if(!(level.getEntity(original) instanceof EvaUnit01Entity found))return;unit=found;
                if(!EvaBayRepairR33.docked(unit))throw new IllegalStateException("Original Unit01 is not parked");
                pilot.stopRiding();pilot.setGameMode(net.minecraft.world.level.GameType.SPECTATOR);
                var f=unit.getForward().multiply(1,0,1).normalize();var right=new net.minecraft.world.phys.Vec3(f.z,0,-f.x);
                var eye=unit.position().add(f.scale(WET_REVIEW?16:21)).add(right.scale(WET_REVIEW?9:12)).add(0,WET_REVIEW?59:51,0);
                pilot.teleportTo(level,eye.x,eye.y,eye.z,151,10);
                if(!WET_REVIEW){unit.getPersistentData().remove("R33Repair");EvaShutdownR30.fail(unit);unit.setHealth(0);}started=level.getGameTime();actorId=unit.getId();
            }
            elapsed=(int)(level.getGameTime()-started);
            if(WET_REVIEW)
            {
                if(!unit.getUUID().equals(original))throw new IllegalStateException("Wet view changed original identity");
                if(elapsed==90)shot="lcl_top";
                if(elapsed>=150){done=true;shot="lcl_top_settled";}
            }
            else
            {
            if(elapsed%120==0)
            {
                var row=new JsonObject();row.addProperty("tick",elapsed);row.addProperty("health",unit.getHealth());row.addProperty("repairing",EvaBayRepairR33.active(unit));row.addProperty("shutdown",EvaShutdownR30.mode(unit));samples.add(row);
                if(!unit.getUUID().equals(original))throw new IllegalStateException("Original EVA replaced");
                if(elapsed<2280&&unit.getHealth()>=unit.getMaxHealth())throw new IllegalStateException("Repair completed early");
                if(elapsed>0&&elapsed<2400&&!EvaShutdownR30.wreck(unit))throw new IllegalStateException("Wreck enabled before repair complete");
            }
            if(elapsed==320)shot="repair_arms";
            if(VISUAL_ONLY&&elapsed>=420){done=true;shot="repair_visual";}
            if(elapsed==1200)
            {
                var tag=new net.minecraft.nbt.CompoundTag();unit.saveWithoutId(tag);
                if(!tag.getCompound("ForgeData").contains("R33Repair"))throw new IllegalStateException("Repair not persisted");
                shot="repair_halfway";
            }
            if(elapsed>=2403)
            {
                if(EvaBayRepairR33.active(unit)||unit.getHealth()!=unit.getMaxHealth()||EvaShutdownR30.wreck(unit))throw new IllegalStateException("Repair did not finish in 2400 ticks");
                shot="repair_complete";done=true;
            }
            }
        }
        catch(Exception failure){error=failure.toString();done=true;}
        if(done)try
        {
            var report=new JsonObject();report.addProperty("passed",error.isEmpty());report.addProperty("error",error);report.addProperty("original_uuid",String.valueOf(original));report.addProperty("duration_ticks",elapsed);report.addProperty("variant",variant);report.addProperty("un_serial",SERIAL);report.addProperty("visual_only",VISUAL_ONLY);report.add("samples",samples);
            Path out=world.resolve("Review/r33_repair_"+(SERIAL<0?"nerv":"un"+SERIAL)+(VISUAL_ONLY?"_visual":"")+".json");Files.createDirectories(out.getParent());Files.writeString(out,new GsonBuilder().setPrettyPrinting().create().toJson(report));
        }
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private BayRepairR33Review(){}
}

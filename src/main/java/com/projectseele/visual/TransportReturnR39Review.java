package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.world.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Functional review only, fenced to the fresh cold-copy world. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class TransportReturnR39Review
{
    public static final boolean ENABLED="r39-transport".equals(System.getProperty("projectseele.regionalBuild"));
    private static int age,stage,stageAge;public static volatile boolean done;
    private static final JsonObject report=new JsonObject();private static final JsonArray trace=new JsonArray();
    private static UUID nearId,farId;private static float nearLastRise=-1,farLastRise=-1;
    private static boolean nearRose,farRose,nearWalked,airRequested;private static long lastUnReport;
    private static void check(String name,boolean ok){report.addProperty(name,ok);if(!ok)throw new IllegalStateException(name);}
    private static void next(int value){stage=value;stageAge=0;com.projectseele.ProjectSeele.LOGGER.info("R39 REVIEW stage={}",stage);}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;
        var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty())return;
        Path world=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!world.getFileName().toString().equals("SEELE_FIELD_R39_REVIEW"))throw new IllegalStateException("R39 isolated world only");
        var l=server.getLevel(FacilitySchemaV2.DIMENSION);if(l==null||++age<80)return;stageAge++;
        var player=server.getPlayerList().getPlayers().get(0);
        try
        {
            if(age>18000||Files.exists(world.resolve("regional_stop_requested")))throw new IllegalStateException("Review deadline / stop, stage="+stage);
            if(age%20==0)
            {
                var row=new JsonObject();row.addProperty("tick",age);row.addProperty("stage",stage);row.addProperty("nerv",NervAirLiftR30.phaseName(l));row.addProperty("un",UNAirLiftR29.phaseName(l,0));
                row.addProperty("near",EvaLogisticsDirector.status(l,0).phase());row.addProperty("far",EvaLogisticsDirector.status(l,2).phase());trace.add(row);
            }
            if(age%200==0)com.projectseele.ProjectSeele.LOGGER.info("R39 REVIEW stage={} age={} near={} far={} nerv={} UN={}",stage,age,EvaLogisticsDirector.status(l,0).phase(),EvaLogisticsDirector.status(l,2).phase(),NervAirLiftR30.status(l),UNAirLiftR29.status(l,0));
            if(stage==0)
            {
                for(int i:new int[]{0,2})EvaLogisticsDirector.loadControlTarget(l,i);
                var a=EvaLogisticsDirector.canonicalUnit(l,0);var b=EvaLogisticsDirector.canonicalUnit(l,2);if(a==null||b==null)return;
                nearId=a.getUUID();farId=b.getUUID();
                if(Boolean.getBoolean("projectseele.r39ResumeReturn"))
                {
                    var proof=JsonParser.parseString(Files.readString(Path.of("../artifacts/transport_return_r39/near_return_evidence.json"))).getAsJsonObject();
                    for(var entry:proof.getAsJsonObject("classes").entrySet())
                    {
                        try(var in=TransportReturnR39Review.class.getClassLoader().getResourceAsStream("com/projectseele/world/"+entry.getKey()+".class"))
                        {check("unchanged_near_component_"+entry.getKey(),java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(in.readAllBytes())).equals(entry.getValue().getAsString()));}
                    }
                    check("prior_near_completed",proof.get("near_return_completed").getAsBoolean()&&EvaLogisticsDirector.status(l,0).phase().equals("PARKED"));
                    nearRose=nearWalked=true;report.addProperty("near_evidence","near_return_evidence.json + original log; matching unchanged component class hashes");
                    check("resume_original_far_job",NervAirLiftR30.phaseName(l).equals("HOLD"));
                    NervAirLiftR30.cancel(player);next(2);return;
                }
                player.stopRiding();player.setGameMode(GameType.SPECTATOR);player.teleportTo(l,30,-405,280,0,0);
                player.getInventory().add(new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.NERV_EMPLOYEE_CARD.get()));
                for(var e:List.of(a,b)){e.setHealth(e.getMaxHealth());EvaShutdownR30.clear(e);e.enterHangarStandby();}
                TvCampaignDirector.select(player,"shamshel");check("mission_started",TvCampaignDirector.beginAssigned(player,0,true,false)==1);
                check("support_started",TvSortiesR32.reinforce(player,2,true,false)==1);next(1);return;
            }
            var campaign=TvCampaignSavedData.get(l);
            if(campaign.angel!=null&&l.getEntity(campaign.angel) instanceof net.minecraft.world.entity.Mob boss){boss.setNoAi(true);boss.setInvulnerable(true);}
            if(stage==1)
            {
                var a=EvaLogisticsDirector.canonicalUnit(l,0);var b=EvaLogisticsDirector.canonicalUnit(l,2);
                if(a==null||b==null||!TvSortiesR32.ready(a)||!TvSortiesR32.ready(b))return;
                check("two_original_npc_pilots",a.getPilotEntity() instanceof TrainingPilotEntity&&b.getPilotEntity() instanceof TrainingPilotEntity);
                Vec3 near=NervAirLiftR30.head(l,0).add(0,0,9);a.teleportTo(near.x,near.y,near.z);a.stopAutonomousR30();
                var c=new net.minecraft.world.level.ChunkPos(400,-364);l.getChunkSource().addRegionTicket(TicketType.PORTAL,c,5,net.minecraft.core.BlockPos.containing(6400,64,-5819));l.getChunk(c.x,c.z);
                b.teleportTo(6400.5,64,-5819.5);b.stopAutonomousR30();
                if(campaign.angel==null||!(l.getEntity(campaign.angel) instanceof ShamshelEntity enemy))return;
                enemy.setInvulnerable(false);enemy.setHealth(0);enemy.die(l.damageSources().fellOutOfWorld());
                check("native_campaign_completion",campaign.active.isEmpty());
                check("return_orders_persist",PilotReturnR39.state(l).save(new CompoundTag()).getList("Orders",10).size()==2);
                next(2);return;
            }
            if(stage>=2&&stage<=3)
            {
                for(int variant:new int[]{0,2})
                {
                    var e=EvaLogisticsDirector.canonicalUnit(l,variant);if(e==null)continue;
                    check("original_unit_"+variant,e.getUUID().equals(variant==0?nearId:farId));
                    var entry=EvaFleetSavedData.get(server).entry(variant).orElseThrow();
                    if(variant==0&&entry.phase()==EvaFleetSavedData.Phase.DEPLOYED&&e.position().distanceTo(NervAirLiftR30.head(l,0))<7)nearWalked=true;
                    if(entry.phase()==EvaFleetSavedData.Phase.DESCENDING&&e.getPersistentData().getBoolean("RecoveryRiseR39"))
                    {
                        float rise=e.carrierRiseProgress(1),last=variant==0?nearLastRise:farLastRise;
                        if(last>=0)check("continuous_rack_"+variant,rise-last<.025F&&rise>=last-.001F);
                        if(rise>0&&rise<.99F)
                        {
                            check("hatch_closed_during_rise_"+variant,Math.abs(e.getY()-NervAirLiftR30.head(l,variant).y)<.05);
                            if(variant==0)nearRose=true;else farRose=true;
                        }
                        if(variant==0)nearLastRise=rise;else farLastRise=rise;
                    }
                }
                if(!NervAirLiftR30.phaseName(l).equals("IDLE"))airRequested=true;
                if(NervAirLiftR30.phaseName(l).equals("HOLD"))throw new IllegalStateException("NERV transport held: "+NervAirLiftR30.status(l));
                if(EvaLogisticsDirector.status(l,0).phase().equals("PARKED")&&EvaLogisticsDirector.status(l,2).phase().equals("PARKED"))
                {
                    check("near_walked",nearWalked);check("far_requested_aircraft",airRequested);check("both_racks_rose",nearRose&&farRose);
                    check("return_queue_completed",PilotReturnR39.state(l).save(new CompoundTag()).getList("Orders",10).isEmpty());
                    next(4);
                }
                return;
            }
            if(stage==4)
            {
                if(!NervAirLiftR30.phaseName(l).equals("IDLE"))return;
                if(!UNAirLiftR29.stageCruiseReviewR39(l,player))return;next(5);return;
            }
            if(stage==5)
            {
                var tag=UNAirLiftR29.state(l).save(new CompoundTag());var jobs=tag.getList("Jobs",10);
                if(!jobs.isEmpty())
                {
                    var job=jobs.getCompound(0);long next=job.getLong("NextReportR39");
                    if(lastUnReport>0&&next!=lastUnReport)check("coordinate_report_interval",next-lastUnReport>=10000);
                    if(next>0)lastUnReport=next;
                    check("un_not_held",!job.getString("Phase").equals("HOLD"));
                }
                if(!UNAirLiftR29.active(l,0))
                {
                    var e=TvSortiesR32.unit(l,3);check("un_delivered_original",e!=null&&e.position().subtract(UNAirLiftR29.apron(l,0)).horizontalDistance()<.1&&e.getY()>=UNAirLiftR29.apron(l,0).y&&e.getY()<UNAirLiftR29.apron(l,0).y+4);
                    report.addProperty("un_long_flight_ticks",stageAge);check("un_long_flight_bounded",stageAge<4000);finish(true,null);
                }
            }
        }
        catch(Throwable error){finish(false,error);}
    }
    private static void finish(boolean passed,Throwable error)
    {
        done=true;report.addProperty("passed",passed);report.addProperty("stage",stage);report.addProperty("ticks",age);report.add("trace",trace);
        if(error!=null){report.addProperty("error",error.toString());com.projectseele.ProjectSeele.LOGGER.error("R39 review failed",error);}
        try{Path p=Path.of("../artifacts/transport_return_r39/native.json");Files.createDirectories(p.getParent());Files.writeString(p,new GsonBuilder().setPrettyPrinting().create().toJson(report));}catch(Exception e){throw new IllegalStateException(e);}
    }
    private TransportReturnR39Review(){}
}

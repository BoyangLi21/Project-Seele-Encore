package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import com.projectseele.registry.ModItems;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Actual JVM interruption during an occupied long-distance flight. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class UNR29ResumeReview
{
    private static final String MODE=System.getProperty("projectseele.regionalBuild","");
    public static final boolean CANCEL_RESUME=MODE.equals("r29-un-cancel-resume"),SAVE=MODE.equals("r29-un-save"),RESUME=MODE.equals("r29-un-resume")||CANCEL_RESUME,ENABLED=SAVE||RESUME;
    public static volatile boolean ready,finished;
    public static volatile String input="",keys="",photo="";
    public static final Set<String> inputs=java.util.concurrent.ConcurrentHashMap.newKeySet(),photos=java.util.concurrent.ConcurrentHashMap.newKeySet();
    private static ServerLevel level;private static ServerPlayer player;private static Path world;private static UUID unit,plugId;
    private static int stage,age,timer,powerSamples;private static boolean canceled;
    private static Vec3 flightStart;private static double heightGain,horizontal;
    private static final JsonObject checks=new JsonObject();
    private static void check(String key,boolean value){checks.addProperty(key,value);if(!value)throw new IllegalStateException(key);}
    private static void next(int s){stage=s;timer=0;input="";keys="";photo="";ProjectSeele.LOGGER.info("R29 UN RESILIENCE stage={} resume={}",s,RESUME);}
    private static void finish(String error)
    {
        finished=true;keys="";var result=new JsonObject();result.addProperty("passed",error.isEmpty());result.addProperty("error",error);result.addProperty("stage",stage);result.addProperty("ticks",age);result.add("checks",checks);
        try{Files.writeString(world.resolve(SAVE?"r29_un_save_pass.json":"r29_un_resume_pass.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));}catch(Exception e){throw new IllegalStateException(e);}
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||!ready||finished||event.phase!=TickEvent.Phase.END)return;
        try
        {
            var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty())return;
            if(world==null)
            {
                world=server.getWorldPath(LevelResource.ROOT).normalize();check("review_world",world.getFileName().toString().equals("SEELE_FIELD_R29_REVIEW"));level=server.getLevel(FacilitySchemaV2.DIMENSION);player=server.getPlayerList().getPlayers().get(0);unit=UNRecoveryR22.identity(level,1);
                if(SAVE)
                {
                    player.stopRiding();player.setGameMode(GameType.CREATIVE);player.setInvulnerable(true);player.getInventory().add(new net.minecraft.world.item.ItemStack(ModItems.UN_SATELLITE_PHONE.get()));player.teleportTo(level,6286.5,127,-6217.5,0,0);
                    check("idle_original_unit",!UNAirLiftR29.active(level,1));UNRecoveryR22.request(player.createCommandSourceStack(),1,true);
                }
                else
                {
                    var receipt=JsonParser.parseString(Files.readString(world.resolve("r29_un_reload_checkpoint.json"))).getAsJsonObject();check("same_saved_pilot",player.getUUID().toString().equals(receipt.get("pilot").getAsString()));check("same_registered_eva",unit.toString().equals(receipt.get("eva").getAsString()));plugId=UUID.fromString(receipt.get("plug").getAsString());check("saved_airlift_active",UNAirLiftR29.active(level,1));stage=CANCEL_RESUME?16:10;
                }
            }
            age++;timer++;check("bounded_review",age<26000);level.resetEmptyTime();if(timer%20==0)UNCommandR29.receive(player,"status",1,0,0);
            if(!(level.getEntity(unit) instanceof EvaPrototypeEntity eva))return;var plug=UNPlugDirector.capsule(eva);if(plug==null)return;
            if(plugId==null)plugId=plug.getUUID();check("original_plug_identity",plugId.equals(plug.getUUID()));
            if(eva.getPilotEntity()==player){check("nuclear_power",eva.getPowerTicks()==eva.getPowerCapacityTicks()&&!eva.isUmbilicalConnected()&&eva.getUmbilicalAnchor()==null);powerSamples++;}
            String phase=UNAirLiftR29.phaseName(level,1);check("no_transport_fault",!phase.equals("HOLD"));
            if(SAVE)
            {
                if(stage==0&&timer>100){UNCommandR29.receive(player,"board",1,0,0);next(1);}
                else if(stage==1&&eva.getPilotEntity()==player&&eva.getActivationTicks()==0&&eva.getPersistentData().getInt("UNSequenceTicks")>=60)
                {UNCommandR29.receive(player,"deliver",1,32,195);next(2);}
                else if(stage==2&&phase.equals("CRUISE")&&eva.position().distanceTo(UNRecoveryR22.home(level,1))>1500)
                {
                    check("occupied_original_ride",player.getVehicle()==plug&&eva.getPilotEntity()==player);check("away_from_base_before_save",true);
                    var receipt=new JsonObject();receipt.addProperty("pilot",player.getUUID().toString());receipt.addProperty("eva",eva.getUUID().toString());receipt.addProperty("plug",plug.getUUID().toString());receipt.addProperty("phase",phase);receipt.addProperty("x",eva.getX());receipt.addProperty("y",eva.getY());receipt.addProperty("z",eva.getZ());Files.writeString(world.resolve("r29_un_reload_checkpoint.json"),receipt.toString());finish("");
                }
                return;
            }
            if(stage==10)
            {
                if(eva.getPilotEntity()!=player){if(timer>400)throw new IllegalStateException("Saved UN ride was not restored");return;}
                check("original_ride_after_jvm_restart",player.getVehicle()==plug);check("still_away_from_base",eva.position().distanceTo(UNRecoveryR22.home(level,1))>1000);next(11);
            }
            else if(stage==11&&!UNAirLiftR29.active(level,1))
            {
                check("long_distance_city_delivery",eva.position().distanceTo(new Vec3(32.5,81,195.5))<80);
                var fake=net.minecraftforge.common.util.FakePlayerFactory.get(level,new com.mojang.authlib.GameProfile(UUID.fromString("c312d8bb-0c53-4251-a9a5-9a7082c93bb2"),"UNAccessProbe"));fake.getInventory().clearContent();check("untrusted_handset_request_denied",!UNCommandR29.authorized(fake));
                check("outside_world_rejected",UNAirLiftR29.request(player,0,false,29999999,0).contains("边界")&&!UNAirLiftR29.active(level,0));
                player.setYRot(0);player.setXRot(0);flightStart=eva.position();next(12);input="fly";
            }
            else if(stage==12)
            {
                if(eva.isUNFlying()){keys="up";heightGain=eva.getY()-flightStart.y;if(timer>80){check("new_flight_ascent",heightGain>20);next(13);keys="forward";}}
                if(timer>180)throw new IllegalStateException("Flight did not start after deployment");
            }
            else if(stage==13)
            {
                keys="forward";horizontal=eva.position().subtract(flightStart).horizontalDistance();photo="un01_horizontal_flight";
                if(timer>55){check("actual_horizontal_flight",horizontal>60);checks.addProperty("horizontal_metres",horizontal);next(14);input="land";}
            }
            else if(stage==14)
            {
                if(!eva.isUNFlying()&&timer>60){check("flight_returned_to_ground",eva.onGround());next(15);}
                if(timer>700)throw new IllegalStateException("Flight landing did not finish");
            }
            else if(stage==15&&timer==20)
            {UNCommandR29.receive(player,"deliver",1,-800,600);next(16);}
            else if(stage==16)
            {
                if(phase.equals("CRUISE")&&!canceled){UNCommandR29.receive(player,"cancel",1,0,0);canceled=true;check("airborne_cancel_requested",true);}
                if(canceled&&!UNAirLiftR29.active(level,1))
                {
                    check("cancel_returned_original_home",eva.position().distanceTo(UNRecoveryR22.home(level,1))<.2);check("safe_automatic_extraction",!player.isPassenger()&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED);check("continuous_nuclear_samples",powerSamples>600);checks.addProperty("power_samples",powerSamples);finish("");
                }
            }
        }
        catch(Exception error){ProjectSeele.LOGGER.error("R29 UN RESILIENCE FAILED",error);finish(error.toString());}
    }
    private UNR29ResumeReview() {}
}

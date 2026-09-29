package com.projectseele.visual;

import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.projectseele.entity.*;
import com.projectseele.registry.ModItems;
import com.projectseele.world.*;
import net.minecraft.server.level.*;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.common.util.*;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Original-identity UN outbound/wreck recovery/intake and NERV surface recovery. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class AirLiftR30Review
{
    private static final boolean R40="r40-airlift".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final boolean R32=R40||"r32-airlift".equals(System.getProperty("projectseele.regionalBuild",""));
    private static final int UN_SERIAL=Integer.getInteger("projectseele.airReviewUnSerial",0);
    private static final boolean UN_ONLY=R40&&Boolean.getBoolean("projectseele.airReviewUnOnly");
    private static final boolean RESUME_RETURN=R40&&Boolean.getBoolean("projectseele.airReviewResumeReturn");
    private static final boolean ENABLED=R32||"r30-airlift".equals(System.getProperty("projectseele.regionalBuild",""));
    public static String reviewWorld()
    {
        String world=System.getProperty("projectseele.airReviewWorld",R32?"SEELE_R32_AIR_REVIEW":"SEELE_FIELD_R30_REVIEW");
        if(!world.equals("SEELE_R32_AIR_REVIEW")&&!world.equals("SEELE_FIELD_R30_REVIEW")&&!world.matches("SEELE_R43_AIR_REVIEW(?:_V[0-9]+)?"))throw new IllegalStateException("Unapproved isolated airlift review world");
        return world;
    }
    private static final TicketType<ChunkPos> TICKET=TicketType.create("r30_airlift_review",Comparator.comparingLong(ChunkPos::toLong),100);
    private static boolean done;private static int age,stage=R32&&Boolean.getBoolean("projectseele.airReviewNervOnly")?4:0,timer;private static FakePlayer operator;private static UUID unId,plugId,nervId;
    private static final JsonObject report=new JsonObject();private static final Set<String> phases=new TreeSet<>();
    private static final Map<UUID,Integer> landings=new HashMap<>();
    private static boolean sawNervHead;
    public static volatile Vec3 observer;
    public static volatile int observedEntity=-1;
    public static volatile String reviewPhase="";
    public static volatile int reviewStage;
    public static boolean finished(){return R40&&done;}
    public static void touchdown(EvaUnit01Entity eva)
    {if(R40&&!done)landings.merge(eva.getUUID(),1,Integer::sum);}
    private static void check(String label,boolean value){report.addProperty(label,value);if(!value)throw new IllegalStateException(label);}
    private static void next(int s){stage=s;timer=0;com.projectseele.ProjectSeele.LOGGER.info("R30 AIRLIFT REVIEW stage={}",stage);}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();var path=server.getWorldPath(LevelResource.ROOT).normalize();
        if(!path.getFileName().toString().equals(reviewWorld()))throw new IllegalStateException("Wrong airlift review world");
        var l=server.getLevel(FacilitySchemaV2.DIMENSION);if(l==null)return;l.resetEmptyTime();
        try
        {
            if(Files.deleteIfExists(path.resolve("regional_stop_requested"))){report.addProperty("passed",false);report.addProperty("error","Review stopped for diagnosis");finish(l,path);return;}
            if(++age<60)return;check("bounded_run",age<18000);timer++;
            if(operator==null)
            {
                operator=FakePlayerFactory.get(l,new GameProfile(UUID.fromString("ca19e174-a03b-47a7-adf7-41508fda0e30"),"R30AirController"));operator.getInventory().add(new ItemStack(ModItems.NERV_EMPLOYEE_CARD.get()));operator.getInventory().add(new ItemStack(ModItems.SATELLITE_PHONE.get()));
                unId=UNRecoveryR22.identity(l,UN_SERIAL);nervId=EvaFleetSavedData.get(server).canonicalId(1).orElseThrow();check("registered_original_un",unId!=null);
            }
            String up=UNAirLiftR29.phaseName(l,UN_SERIAL),np=NervAirLiftR30.phaseName(l);phases.add(stage+":"+up+":"+np);
            if(R40){reviewPhase=stage<4?up:np;reviewStage=stage;}
            if(R40)
            {
                var id=stage<4?unId:nervId;
                if(id!=null&&l.getEntity(id) instanceof EvaUnit01Entity watched)
                {
                    observer=watched.position();observedEntity=watched.getId();
                    if(stage==5&&NervAirLiftR30.waitingAtHead(watched))sawNervHead=true;
                }
            }
            if(R32)for(UUID id:new UUID[]{unId,nervId})if(id!=null&&l.getEntity(id) instanceof EvaUnit01Entity carried&&EvaAirTransportR31.active(carried))
            {
                check("no_power_during_pickup",!carried.isUmbilicalConnected());
                if(EvaAirTransportR31.restraint(carried,1)>.99F&&!up.equals("RELEASE")&&!np.equals("RELEASE"))
                {
                    var origin=EvaAirTransportR31.origin(carried);var pose=EvaBodyPose.sample(carried,1);double error=0;
                    for(String bone:origin.rig.keySet())if(!bone.equals("root"))
                    {error=Math.max(error,1-Math.abs(origin.rotations.get(bone).dot(pose.rotations.get(bone))));error=Math.max(error,origin.positions.get(bone).distance(pose.positions.get(bone)));}
                    check("pickup_joints_unchanged_stage_"+stage,error<.0001);
                    if(EvaShutdownR30.wreck(carried))
                    {
                        var before=origin.matrix("torso_lower").transformDirection(new org.joml.Vector3f(0,1,0)).normalize();
                        var now=pose.matrix("torso_lower").transformDirection(new org.joml.Vector3f(0,1,0)).normalize();
                        if(Math.abs(before.y)<.2F)check("fallen_body_stays_horizontal_stage_"+stage,Math.abs(now.y)<.22F);
                    }
                }
            }
            if(stage>0){check("no_un_transport_hold",!up.equals("HOLD"));check("no_nerv_transport_hold",!np.equals("HOLD"));}
            if(timer%100==0)com.projectseele.ProjectSeele.LOGGER.info("R30 AIRLIFT REVIEW stage={} ticks={} un={} nerv={} status={}",stage,timer,up,np,stage<4?UNAirLiftR29.status(l,UN_SERIAL):NervAirLiftR30.status(l));
            if(stage==0)
            {
                if(R40&&Boolean.getBoolean("projectseele.airReviewResumeGround"))
                {
                    if(!(l.getEntity(unId) instanceof EvaPrototypeEntity e)||UNPlugDirector.capsule(e)==null)return;
                    plugId=UNPlugDirector.capsule(e).getUUID();
                    if(!UNAirLiftR29.resumeGroundReviewR40(l,UN_SERIAL))return;
                    report.addProperty("resumed_ground_only",true);next(3);return;
                }
                if(RESUME_RETURN)
                {
                    if(!(l.getEntity(unId) instanceof EvaPrototypeEntity e)||UNPlugDirector.capsule(e)==null)return;
                    plugId=UNPlugDirector.capsule(e).getUUID();check("resumed_original_wreck",EvaShutdownR30.wreck(e)&&e.getHealth()==0);
                    check("return_job_preserved",UNAirLiftR29.active(l,UN_SERIAL));report.addProperty("resumed_return_only",true);next(2);return;
                }
                if(timer==1)UNRecoveryR22.request(operator.createCommandSourceStack(),UN_SERIAL,true);
                if(timer<80||!(l.getEntity(unId) instanceof EvaPrototypeEntity e)||UNPlugDirector.capsule(e)==null)return;
                plugId=UNPlugDirector.capsule(e).getUUID();check("original_un_at_home",e.position().distanceTo(UNRecoveryR22.home(UN_SERIAL))<.1);
                report.addProperty("un_deliver_reply",UNAirLiftR29.request(operator,UN_SERIAL,false,(int)UNRecoveryR22.home(UN_SERIAL).x,-5980));check("delivery_started",UNAirLiftR29.active(l,UN_SERIAL));next(1);return;
            }
            if(stage<4)
            {
                if(!(l.getEntity(unId) instanceof EvaPrototypeEntity e))return;check("original_un_identity",e.getUUID().equals(unId));
                var capsule=UNPlugDirector.capsule(e);check("original_un_capsule_identity",capsule!=null&&capsule.getUUID().equals(plugId));
                if(stage==1&&!UNAirLiftR29.active(l,UN_SERIAL))
                {
                    if(R40)check("un_outbound_touchdown_once",landings.getOrDefault(unId,0)==1);
                    check("un_delivered",e.getZ()>-6050);check("un_control_released",!e.isNervLogisticsLocked()&&!e.hasActiveCarrierMotion());
                    e.hurt(l.damageSources().fellOutOfWorld(),100000);check("un_wreck_ready",EvaShutdownR30.wreck(e));report.addProperty("un_recover_reply",UNAirLiftR29.request(operator,UN_SERIAL,true,0,0));check("wreck_airlift_started",UNAirLiftR29.active(l,UN_SERIAL));next(2);return;
                }
                if(stage==2&&!UNAirLiftR29.active(l,UN_SERIAL))
                {
                    if(R40)check("un_wreck_return_touchdown_once",landings.getOrDefault(unId,0)==(RESUME_RETURN?1:2));
                    var pad=UNAirLiftR29.reception(l,UN_SERIAL);
                    var cartTag=UNAirLiftR29.state(l).save(new net.minecraft.nbt.CompoundTag());
                    var receiver=cartTag.hasUUID("Cart"+UN_SERIAL)?l.getEntity(cartTag.getUUID("Cart"+UN_SERIAL)):null;
                    var bearing=receiver instanceof UNTransportEntity cart?UNReceivingCradleR40.contact(e,cart):null;
                    var support=new JsonObject();support.addProperty("entity_root_y",e.getY());support.addProperty("pad_y",pad.y);
                    support.addProperty("root_lift",e.getY()-pad.y);support.addProperty("horizontal_error",e.position().subtract(pad).horizontalDistance());
                    support.addProperty("owned_receiver_bearing",bearing!=null);if(bearing!=null)support.addProperty("bearing_y",bearing.y);report.add("receiving_geometry",support);
                    // A fallen body's measured clearance can lift its root off
                    // the deck. Require its real owned receiver contact, not a
                    // nominal entity coordinate that would push it into metal.
                    check("un_delivered_to_intake",bearing!=null&&e.position().subtract(pad).horizontalDistance()<.2&&receiver.position().distanceTo(pad)<.1);
                    check("un_wreck_not_healed",e.getHealth()==0);check("un_waits_before_docking",e.isNervLogisticsLocked()&&e.position().distanceTo(UNRecoveryR22.home(UN_SERIAL))>50);
                    report.addProperty("dock_reply",UNAirLiftR29.requestDock(operator,UN_SERIAL));check("ground_dock_started",UNAirLiftR29.active(l,UN_SERIAL));next(3);return;
                }
                if(stage==3&&!UNAirLiftR29.active(l,UN_SERIAL))
                {check("un_original_home_reached",e.position().distanceTo(UNRecoveryR22.home(UN_SERIAL))<.1);check("wreck_remains_for_repair",e.getHealth()==0&&EvaShutdownR30.wreck(e)||R40&&EvaBayRepairR33.active(e));if(UN_ONLY){report.addProperty("un_serial",UN_SERIAL);report.addProperty("passed",true);finish(l,path);}else next(4);return;}
            }
            if(stage==4)
            {
                EvaLogisticsDirector.loadControlTarget(l,1);if(!(l.getEntity(nervId) instanceof EvaUnit01Entity e))return;
                if(!np.equals("IDLE"))
                {check("resumed_original_wreck",EvaShutdownR30.wreck(e)&&e.getHealth()==0);report.addProperty("resumed_nerv_phase",np);next(5);return;}
                var chunk=R32?new ChunkPos(400,-364):new ChunkPos(24,13);l.getChunkSource().addRegionTicket(TICKET,chunk,3,chunk);l.getChunk(chunk.x,chunk.z);
                // R32 uses a scanned open apron; the older city point has a station canopy across the fallen body.
                EvaLogisticsDirector.markDeployedForVisual(l,e);e.normalizeAfterTransportR30(false);e.teleportTo(R32?6400.5:392.5,R32?64:81,R32?-5819.5:217.5);e.setHealth(e.getMaxHealth());EvaShutdownR30.clear(e);e.hurt(l.damageSources().fellOutOfWorld(),100000);check("nerv_wreck_ready",EvaShutdownR30.wreck(e)&&e.getHealth()==0);
                report.addProperty("nerv_recover_reply",NervAirLiftR30.request(operator,1,true,0,0));check("nerv_request_started",!NervAirLiftR30.phaseName(l).equals("IDLE"));next(5);return;
            }
            if(stage==5&&NervAirLiftR30.phaseName(l).equals("IDLE"))
            {
                if(R40)
                {
                    var original=EvaLogisticsDirector.canonicalUnit(l,1);
                    check("nerv_original_identity",original!=null&&original.getUUID().equals(nervId));
                    check("nerv_real_silo_handoff_seen",sawNervHead);
                    check("nerv_touchdown_once",landings.getOrDefault(nervId,0)==1);
                    if(NervAirLiftR30.waitingAtHead(original))check("surface_recovery_accepted",EvaLogisticsDirector.requestRecovery(l,1).accepted());
                    next(6);return;
                }
                var e=EvaLogisticsDirector.canonicalUnit(l,1);check("nerv_original_identity",e!=null&&e.getUUID().equals(nervId));check("nerv_waits_on_own_head",NervAirLiftR30.waitingAtHead(e));check("nerv_wreck_retained",EvaShutdownR30.wreck(e));
                var result=EvaLogisticsDirector.requestRecovery(l,1);report.addProperty("nerv_ground_recovery",result.message());check("surface_recovery_accepted",result.accepted());next(6);return;
            }
            if(stage==6&&EvaLogisticsDirector.status(l,1).phase().equals("PARKED"))
            {var e=EvaLogisticsDirector.canonicalUnit(l,1);check("nerv_wreck_recovered_to_cage",e!=null&&e.getUUID().equals(nervId)&&(EvaShutdownR30.wreck(e)||R40&&EvaBayRepairR33.active(e)));report.addProperty("passed",true);finish(l,path);}
        }
        catch(Exception error){report.addProperty("passed",false);report.addProperty("stage",stage);report.addProperty("error",error.toString());com.projectseele.ProjectSeele.LOGGER.error("R30 airlift regression failed",error);finish(l,path);}
    }
    private static void finish(ServerLevel l,Path path)
    {
        done=true;report.add("phases",new Gson().toJsonTree(phases));
        try{Files.writeString(path.resolve(R32?"r32_airlift_review.json":"r30_airlift_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));}catch(Exception e){throw new IllegalStateException(e);}
        l.getServer().halt(false);
    }
    private AirLiftR30Review(){}
}

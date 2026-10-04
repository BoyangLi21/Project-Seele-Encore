package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import net.minecraft.server.level.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** One human-piloted cycle through the relocated physical plant. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FactoryR20Review
{
    private static final boolean R21="r21-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R44_PASSENGER=Boolean.getBoolean("projectseele.r44PassengerFactoryReview");
    public static final boolean R35=R44_PASSENGER||"r35-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final String R35_WORLD=R44_PASSENGER?com.projectseele.visual.NativeReviewWorldsR45.expectedName():"SEELE_FACTORY_R35_REVIEW";
    public static final boolean R27="r27-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R29="r29-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R28_VISUAL=R29||"r28-visual-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R28=R28_VISUAL||"r28-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R35||R28||R27||R21||"r20-factory".equals(System.getProperty("projectseele.regionalBuild",""));
    public static volatile boolean ready,finished;public static volatile String phase="setup";
    public static volatile Vec3 launchRoot;
    private static int age,state,timer,variant=1;private static Path world;private static ServerLevel level;private static ServerPlayer player;
    private static UUID evaId,plugId;private static final JsonArray samples=new JsonArray();private static Vec3 last;
    private static UUID expectedEva,expectedPlug;private static boolean reboarded;
    private static void require(boolean ok,String why){if(!ok)throw new IllegalStateException(why);}
    private static void next(String s){phase=s;state++;timer=0;ProjectSeele.LOGGER.info("R20 FACTORY {}",s);}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||!ready||event.phase!=TickEvent.Phase.END)return;
        if(R27&&!FuyutsukiR27Review.finished)return;
        if(R28&&!FieldR28Review.seatsFinished)return;
        try
        {
            if(world==null)
            {
                world=event.getServer().getWorldPath(LevelResource.ROOT).normalize();require(world.getFileName().toString().equals(R35?R35_WORLD:R29?"SEELE_FIELD_R29_REVIEW":R28?"SEELE_FIELD_R28_REVIEW":R27?"SEELE_R27_REVIEW":R21?"SEELE_R21_REVIEW":"SEELE_R20_REVIEW"),"Review world boundary");
                level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);player=event.getServer().getPlayerList().getPlayers().get(0);player.stopRiding();player.setGameMode(GameType.CREATIVE);player.teleportTo(level,30.5,-394,-267.5,0,0);
                if(R44_PASSENGER)
                {
                    variant=Integer.getInteger("projectseele.r44PassengerFactoryVariant",1);require(variant>=0&&variant<3,"Original cage variant required");
                    expectedEva=UUID.fromString(System.getProperty("projectseele.r44PassengerFactoryEvaUuid",""));
                    var saved=EvaFleetSavedData.get(event.getServer()).entry(variant).orElseThrow();
                    require(saved.canonicalId().equals(expectedEva),"Current original EVA UUID differs from supplied witness");expectedPlug=saved.entryPlugId();require(expectedPlug!=null,"Current saved original plug identity missing");
                }
            }
            require(++age<14000,"Cycle timeout: "+phase);timer++;
            if(state==0)
            {
                for(int v=0;v<3;v++)EvaLogisticsDirector.loadControlTarget(level,v);
                if(timer<180)return;
                for(int v=0;v<3;v++)
                {
                    var b=IntegratedNervMapBuilder.lowerLiftBed(level,v);var h=EvaHangarBuilder.hangarBed(RegionalFacilityLayout.evaOrigin(level),v);var s=IntegratedNervMapBuilder.surfaceLiftBed(level,v);
                    ProjectSeele.LOGGER.info("R20 anchors {} cage={} lower={} {} surface={} {}",v,h,b,level.getBlockState(b),s,level.getBlockState(s));
                    if(!R35){require(b.equals(new BlockPos(new int[]{-12,30,72}[v],-411,-36)),"Wrong launch frame "+b);require(h.getZ()==-240,"Wrong cage frame "+h);}
                }
                require(EvaHangarBuilder.runtimeInfrastructurePresent(level,RegionalFacilityLayout.evaOrigin(level)),"Mechanical marker check");
                if(R35)
                {
                    boolean parked=R44_PASSENGER&&EvaLogisticsDirector.status(level,variant).phase().equals("PARKED");
                    if(!R44_PASSENGER)for(int v=0;v<3;v++)if(EvaLogisticsDirector.status(level,v).phase().equals("PARKED")){variant=v;parked=true;break;}
                    if(!parked){require(timer<2400,"No parked airframe after ordinary interrupted-cycle recovery");return;}
                }
                TrainingPilotDirector.stop(level,variant);require(EvaLogisticsDirector.status(level,variant).phase().equals("PARKED"),"Cold saved fleet must be parked; do not replace its identities");next("board");return;
            }
            var eva=EvaLogisticsDirector.canonicalUnit(level,variant);var plug=EntryPlugDirector.canonical(level,variant);
            if(eva==null||plug==null){require(timer<500,"Missing canonical actor");return;}
            if(R44_PASSENGER)require(eva.getUUID().equals(expectedEva)&&plug.getUUID().equals(expectedPlug),"Current fleet/capsule identity changed");
            String current=EvaLogisticsDirector.status(level,variant).phase();
            if(R35&&timer%100==0)ProjectSeele.LOGGER.info("R35 FACTORY status={} variant={} clock={} plug={} locked={} pilot={}",current,variant,timer,plug.getInsertionProgress(),plug.isLockedToEva(),plug.getFirstPassenger());
            if(timer%10==0)
            {
                JsonObject q=new JsonObject();q.addProperty("tick",age);q.addProperty("phase",current);q.addProperty("x",eva.getX());q.addProperty("y",eva.getY());q.addProperty("z",eva.getZ());q.addProperty("yaw",eva.getYRot());q.addProperty("body",eva.yBodyRot);q.addProperty("pilot",eva.getPilotEntity()==player);samples.add(q);
            }
            switch(state)
            {
                case 1 ->
                {
                    if(timer<140)return;evaId=eva.getUUID();plugId=plug.getUUID();Vec3 hatch=plug.transformPlugMarker(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P),outward=plug.getCanonicalTransform().transformVector(EntryPlugKinematics.PILOT_VIEW_FORWARD_P).normalize();Vec3 eye=hatch.add(outward.scale(2.4)),look=hatch.subtract(eye);
                    player.teleportTo(level,eye.x,eye.y-player.getEyeHeight(),eye.z,(float)Math.toDegrees(Math.atan2(-look.x,look.z)),(float)-Math.toDegrees(Math.atan2(look.y,look.horizontalDistance())));plug.tryBoardFromHatch(player);require(plug.getFirstPassenger()==player,"Real hatch boarding");
                    var r=EvaLogisticsDirector.requestPrepare(level,variant);require(r.accepted(),"Prepare rejected: "+r);next("prepare_transfer");
                }
                case 2 ->
                {
                    require(!current.equals("PLUG_FAULT"),"Plug fault");
                    if(R35)require(timer<2400,"Prepare stalled: "+EvaLogisticsDirector.status(level,variant));
                    if(current.equals("SILO_READY"))
                    {
                        if(R35)launchRoot=eva.position();
                        if((R27||R28)&&++siloFrames<140)return;
                        if(!R35)require(Math.abs(eva.getY()+410)<.3&&Math.abs(eva.getZ()+35.5)<.3,"High launch arrival");require(EvaLogisticsDirector.requestLaunch(level,variant).accepted(),"Launch rejected");next("launch");
                    }
                }
                case 3 ->{if(current.equals("DEPLOYED")){require(NervSiloDoorEntity.hasClosedSurfaceSupport(level,IntegratedNervMapBuilder.surfaceLiftBed(level,variant)),"Surface support absent");next("free_surface_hold");}}
                case 4 ->
                {
                    require(eva.getY()>80.7,"Fell through arrival hatch");
                    if(R28_VISUAL&&timer==25)
                    {
                        eva.installExternalArmament(EvaUnit01Entity.WEAPON_RIFLE);
                        for(int i=0;i<6&&eva.getWeapon()!=EvaUnit01Entity.WEAPON_RIFLE;i++)eva.cycleWeapon(player);
                        require(eva.getWeapon()==EvaUnit01Entity.WEAPON_RIFLE,"Visual firing loadout");
                    }
                    if(R29&&timer>=100&&timer<140||!R29&&R28_VISUAL&&(timer==100||timer==140))eva.fireRifle(player);
                    if(timer>180){eva.setYRot(90);eva.yBodyRot=90;eva.yHeadRot=90;require(EvaLogisticsDirector.requestRecovery(level,variant).accepted(),"Recover rejected");next("recover_from_sideways");}
                }
                case 5 ->
                {
                    if(current.equals("TO_HANGAR"))require(Math.abs(net.minecraft.util.Mth.wrapDegrees(eva.getYRot()-180))<.05,"Return EVA faces wrong way");
                    if(current.equals("PARKED"))
                    {
                        require(eva.getUUID().equals(evaId)&&plug.getUUID().equals(plugId),"Fleet identity changed");
                        if(R44_PASSENGER){var home=EvaHangarBuilder.hangarBed(RegionalFacilityLayout.evaOrigin(level),variant);require(Math.abs(eva.getZ()-(home.getZ()+.5))<.2,"Returned to wrong current cage");}
                        else require(Math.abs(eva.getZ()+239.5)<.2,"Returned to wrong cage");
                        if(R44_PASSENGER)
                        {
                            player.stopRiding();require(!player.isPassenger()&&plug.getFirstPassenger()!=player,"Actual exit failed");
                            require(!eva.isPoweredOn(),"Real exit retained a powered pilot circuit");next("real_hatch_reboard");return;
                        }
                        player.stopRiding();player.teleportTo(level,103.5,-369,-70.5,180,0);
                        Files.writeString(world.resolve(R35?"Review/r35_factory_pass.json":"r20_factory_pass.json"),samples.toString());phase="complete";finished=true;
                    }
                }
                case 6 ->
                {
                    if(timer<40)return;
                    Vec3 hatch=plug.transformPlugMarker(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P),outward=plug.getCanonicalTransform().transformVector(EntryPlugKinematics.PILOT_VIEW_FORWARD_P).normalize();
                    Vec3 eye=hatch.add(outward.scale(2.4)),look=hatch.subtract(eye);player.teleportTo(level,eye.x,eye.y-player.getEyeHeight(),eye.z,(float)Math.toDegrees(Math.atan2(-look.x,look.z)),(float)-Math.toDegrees(Math.atan2(look.y,look.horizontalDistance())));
                    plug.tryBoardFromHatch(player);require(plug.getFirstPassenger()==player,"Real hatch reboarding failed");
                    require(EvaLogisticsDirector.requestPrepare(level,variant).accepted(),"Second real prepare rejected");reboarded=true;next("second_real_prepare");
                }
                case 7 ->
                {
                    if(current.equals("SILO_READY")){require(reboarded&&eva.isEntryPlugInserted()&&eva.isPoweredOn()&&eva.getPilotEntity()==player&&player.getVehicle()==plug&&plug.getVehicle()==eva,"Reboard/physical insertion circuit failed");
                        require(EvaLogisticsDirector.requestCancel(level,variant).accepted(),"Second prepare cancel rejected");next("second_real_return");}
                }
                case 8 ->
                {
                    if(current.equals("PARKED")){player.stopRiding();require(!player.isPassenger(),"Final real exit failed");Files.createDirectories(world.resolve("Review"));
                        Files.writeString(world.resolve("Review/r44_passenger_factory_"+variant+".json"),samples.toString());phase="complete";finished=true;}
                }
            }
        }
        catch(Exception e)
        {
            ProjectSeele.LOGGER.error("R20 factory review failed "+phase,e);try{Files.writeString(world.resolve(R35?"Review/r35_factory_failure.txt":"r20_factory_failure.txt"),phase+"\n"+e+"\n"+samples);}catch(Exception ignored){}finished=true;
        }
    }
    private static int siloFrames;
    private FactoryR20Review(){}
}

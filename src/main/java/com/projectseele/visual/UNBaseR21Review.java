package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Real saved airframes, wall-panel controllers, hatch boarding and driver input. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class UNBaseR21Review
{
    public static final boolean R22="r22-un-base".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R22||Set.of("r21-un-base","r21-un-base00","r21-un-base01").contains(System.getProperty("projectseele.regionalBuild",""));
    public static volatile int actor,forward,attackCycle;public static volatile boolean finished;public static volatile String shot="";
    public static final Set<String> captured=java.util.concurrent.ConcurrentHashMap.newKeySet();
    private static int age,stage,ticks,serial="r21-un-base01".equals(System.getProperty("projectseele.regionalBuild",""))?1:0;private static ServerPlayer pilot;private static EvaPrototypeEntity eva;private static UUID unitId,plugId;private static Path world;private static float health,pilotHealth,boardingYaw,boardingPitch;private static boolean recalledInitialState;
    private static final JsonArray checks=new JsonArray();
    private static MilitaryR07Director.Phase phase(ServerLevel l){return serial==0?MilitaryR07Director.state(l).phase:UNAnnexR20.state(l).phase;}
    private static String request(ServerLevel l,String action){return serial==0?MilitaryR07Director.request(l,action,pilot):UNAnnexR20.request(l,action,pilot);}
    private static void next(int value){stage=value;ticks=0;}
    private static void require(boolean value,String label){if(!value)throw new IllegalStateException(label);}
    private static void control(ServerLevel l,Vec3 home){pilot.stopRiding();pilot.teleportTo(l,home.x-40,77,-6132.5,0,0);pilot.setDeltaMovement(Vec3.ZERO);pilot.fallDistance=0;}
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty()||++age<100)return;
        world=server.getWorldPath(LevelResource.ROOT).normalize();if(!world.getFileName().toString().equals(R22?"SEELE_R22_REVIEW":"SEELE_R21_REVIEW"))throw new IllegalStateException("UN base review is copy-only");
        var level=server.getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        try
        {
            if(pilot==null){pilot=server.getPlayerList().getPlayers().get(0);pilot.setGameMode(GameType.CREATIVE);pilot.getCapability(com.projectseele.capability.EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));if(pilot.getRootVehicle() instanceof EvaPrototypeEntity saved)serial=saved.getUNSerial();}
            Vec3 home=UNRecoveryR22.home(level,serial);
            if(age%20==0)for(int x=(int)home.x-48;x<home.x+49;x+=16)for(int z=-6230;z<-6120;z+=16)
            {var p=new net.minecraft.world.level.ChunkPos(x>>4,z>>4);level.getChunkSource().addRegionTicket(net.minecraft.server.level.TicketType.PORTAL,p,2,new BlockPos(x,77,z));level.getChunk(p.x,p.z);}
            if(++ticks>1800)throw new IllegalStateException("UN-0"+serial+" base stage "+stage+" timeout; "+phase(level));
            if(stage==0)
            {
                level.getChunkAt(BlockPos.containing(home));
                UUID id=serial==0?MilitaryR07Director.state(level).entities.get("prototype"):UNAnnexR20.state(level).unitId;
                if(id==null||!(level.getEntity(id) instanceof EvaPrototypeEntity found))return;
                eva=found;unitId=id;actor=eva.getId();require(eva.getUNSerial()==serial,"Airframe serial mismatch");
                if(R22&&!recalledInitialState&&eva.position().distanceTo(home)>3)
                {
                    recalledInitialState=true;
                    server.getCommands().performPrefixedCommand(pilot.createCommandSourceStack().withPermission(2),"seele military recover 0"+serial);
                    next(-3);return;
                }
                // A timed-out drive may be saved as Player.RootVehicle. Recover
                // that same airframe and capsule through normal driver input.
                if(pilot.getRootVehicle()==eva)
                {
                    var original=UNPlugDirector.capsule(eva);require(original!=null&&original.isLockedToEva(),"Saved drive lost capsule");
                    if(pilot.getVehicle()!=original){pilot.stopRiding();require(pilot.startRiding(original,true),"Saved ride graph recovery failed");}
                    require(eva.bindEntryPlug(original,100),"Saved capsule could not resume pilot control");forward=-1;next(-1);return;
                }
                if(eva.position().distanceTo(home)>3)
                {
                    var savedPlug=UNPlugDirector.capsule(eva);
                    if(phase(level)==MilitaryR07Director.Phase.DRY){request(level,"door");return;}
                    if(phase(level)==MilitaryR07Director.Phase.OPENING||phase(level)==MilitaryR07Director.Phase.CLOSING)return;
                    require(phase(level)==MilitaryR07Director.Phase.OPEN&&savedPlug!=null&&savedPlug.isLockedToEva()&&eva.getPilotEntity()==null,"Unexpected out-of-bay fixture state");
                    // Recovery setup only: the earlier interrupted review left
                    // its sealed capsule outside. The measured cycle below
                    // still boards normally from the restored physical gantry.
                    pilot.stopRiding();require(pilot.startRiding(savedPlug,true)&&eva.bindEntryPlug(savedPlug,100),"Review recovery could not resume saved drive");forward=-1;next(-1);return;
                }
                control(level,home);
                if(phase(level)!=MilitaryR07Director.Phase.WET)
                {if(phase(level)==MilitaryR07Director.Phase.OPEN)request(level,"door");else if(phase(level)==MilitaryR07Director.Phase.DRY)request(level,"fill");return;}
                health=eva.getHealth();pilotHealth=pilot.getHealth();request(level,"drain");next(1);return;
            }
            var plug=UNPlugDirector.capsule(eva);
            if(stage==-3&&eva.position().distanceTo(home)<1&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!pilot.isPassenger())
            {control(level,home);next(0);return;}
            if(stage==-1&&eva.getZ()<home.z+1.5)
            {forward=0;require(eva.position().distanceTo(home)<3,"Saved drive recovery missed original bed");require(EntryPlugDirector.ejectPilotToPlug(level,1,eva,pilot),"Saved drive capsule recovery rejected");next(-2);}
            else if(stage==-2&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!pilot.isPassenger())
            {control(level,home);next(0);}
            else if(stage==1&&phase(level)==MilitaryR07Director.Phase.DRY){request(level,"door");next(2);}
            else if(stage==2&&phase(level)==MilitaryR07Director.Phase.OPEN&&plug!=null)
            {
                shot="un0"+serial+"_open_bay";if(!captured.contains(shot)||ticks<50)return;
                plugId=plug.getUUID();Vec3 hatch=plug.getCanonicalTransform().transformPoint(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P);Vec3 standing=null;
                for(double dx:new double[]{4,-4,3,-3})
                {
                    Vec3 p=new Vec3(hatch.x+dx,home.y+50,hatch.z);var floor=BlockPos.containing(p.add(0,-.05,0));
                    if(!level.getBlockState(floor).getCollisionShape(level,floor).isEmpty()&&level.noCollision(pilot,new net.minecraft.world.phys.AABB(p.x-.3,p.y,p.z-.3,p.x+.3,p.y+1.8,p.z+.3))){standing=p;break;}
                }
                require(standing!=null,"The saved boarding bridge needs a real floor beside the hatch");
                Vec3 delta=hatch.subtract(standing.add(0,pilot.getEyeHeight(),0));float yaw=(float)Math.toDegrees(Math.atan2(-delta.x,delta.z)),pitch=(float)-Math.toDegrees(Math.atan2(delta.y,delta.horizontalDistance()));
                boardingYaw=yaw;boardingPitch=pitch;pilot.teleportTo(level,standing.x,standing.y,standing.z,yaw,pitch);pilot.setYHeadRot(yaw);pilot.fallDistance=0;next(21);
            }
            else if(stage==21&&ticks>=5)
            {
                pilot.setYRot(boardingYaw);pilot.setYHeadRot(boardingYaw);pilot.setXRot(boardingPitch);
                Vec3 hatch=plug.getCanonicalTransform().transformPoint(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P),delta=hatch.subtract(pilot.getEyePosition());
                var diagnostic=new JsonObject();diagnostic.addProperty("unit",serial);diagnostic.addProperty("hatch_open",plug.isHatchOpen());diagnostic.addProperty("stage",plug.getInsertionStage());diagnostic.addProperty("host_locked",eva.isNervLogisticsLocked());diagnostic.addProperty("distance",delta.length());diagnostic.addProperty("aim_dot",delta.normalize().dot(pilot.getViewVector(1)));diagnostic.addProperty("eye",pilot.getEyePosition().toString());diagnostic.addProperty("hatch",hatch.toString());Files.writeString(world.resolve("un_base_boarding_diagnostic.json"),diagnostic.toString());
                plug.tryBoardFromHatch(pilot);require(pilot.getVehicle()==plug,"Ordinary hatch reach/aim/obstruction gate refused boarding: "+diagnostic);next(3);
            }
            else if(stage==3&&plug!=null&&plug.isLockedToEva()&&EvaDorsalMechanism.bow(eva)<.001&&eva.isPoweredOn())
            {shot="un0"+serial+"_pilot_view";if(captured.contains(shot)){forward=1;next(4);}}
            else if(stage==3&&ticks>60&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!pilot.isPassenger())
            {throw new IllegalStateException("Physical crane preflight rejected; see un_preflight_obstruction.json");}
            else if(stage==4)
            {
                require(pilot.getRootVehicle()==eva,"Pilot ride graph lost while exiting");
                if(eva.getZ()>-6108){forward=0;shot="un0"+serial+"_outside";next(5);}
            }
            else if(stage==5&&ticks>40&&captured.contains(shot))
            {
                if(R22){shot="un0"+serial+"_head_detail";next(48);}
                else {forward=-1;next(6);}
            }
            else if(stage==48&&captured.contains(shot)){shot="un0"+serial+"_hand_detail";next(49);}
            else if(stage==49&&captured.contains(shot)){attackCycle=1;eva.meleeAttack(pilot);shot="un0"+serial+"_attack_a";next(50);}
            else if(stage==50)
            {
                if(ticks==8)shot="un0"+serial+"_attack_b";
                if(ticks==16)shot="un0"+serial+"_attack_c";
                if(ticks>60)
                {
                    boolean complete=captured.contains("un0"+serial+"_attack_a")&&captured.contains("un0"+serial+"_attack_b")&&captured.contains("un0"+serial+"_attack_c");
                    if(!complete)
                    {
                        require(++attackCycle<=3,"Three native attacks produced no complete capture coverage");
                        eva.meleeAttack(pilot);shot="un0"+serial+"_attack_a";ticks=0;
                        ProjectSeele.LOGGER.info("UN capture repeats a genuine native attack after a missed render window: serial={} cycle={}",serial,attackCycle);return;
                    }
                    server.getCommands().performPrefixedCommand(pilot.createCommandSourceStack().withPermission(2),"seele military recover 0"+serial);next(7);
                }
            }
            else if(stage==6&&eva.getZ()<home.z+1.5)
            {
                forward=0;require(eva.position().distanceTo(home)<3,"Return to the original bed under driver input");
                require(EntryPlugDirector.ejectPilotToPlug(level,1,eva,pilot),"Original capsule extraction rejected");next(7);
            }
            else if(stage==7&&plug!=null&&plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!pilot.isPassenger())
            {
                require(plug.getUUID().equals(plugId)&&eva.getUUID().equals(unitId),"Capsule or airframe was replaced");require(eva.getHealth()>=health&&pilot.getHealth()>=pilotHealth,"Drive cycle caused damage");
                control(level,home);
                if(R22)
                {
                    eva.teleportTo(home.x+12,home.y,home.z+35);eva.setYRot(90);eva.setYBodyRot(90);
                    server.getCommands().performPrefixedCommand(pilot.createCommandSourceStack().withPermission(2),"seele military reset 0"+serial);next(71);
                }
                else {request(level,"door");next(8);}
            }
            else if(stage==71&&ticks>10)
            {
                require(eva.getUUID().equals(unitId)&&plug.getUUID().equals(plugId),"Reset replaced identities");
                require(eva.position().distanceTo(home)<1&&Math.abs(eva.getYRot())<.01,"Reset home/yaw mismatch");
                require(plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&!pilot.isPassenger(),"Reset capsule not docked");request(level,"door");next(8);
            }
            else if(stage==8&&phase(level)==MilitaryR07Director.Phase.DRY){request(level,"fill");next(9);}
            else if(stage==9&&phase(level)==MilitaryR07Director.Phase.WET)
            {
                shot="un0"+serial+"_stored";if(!captured.contains(shot))return;
                var row=new JsonObject();row.addProperty("unit","EVA-UN-0"+serial);row.addProperty("airframe",unitId.toString());row.addProperty("plug",plugId.toString());row.addProperty("passed",true);row.addProperty("ordinary_hatch_boarding",true);row.addProperty("driven_out_and_back",!R22);row.addProperty("attack_recover_reset_commands",R22);row.addProperty("native_attacks_for_capture",attackCycle);row.addProperty("wet_closed_restored",true);checks.add(row);
                if(++serial<2&&!"r21-un-base00".equals(System.getProperty("projectseele.regionalBuild",""))){shot="";next(0);}else finish("");
            }
        }
        catch(Exception failure){ProjectSeele.LOGGER.error("UN R21 BASE REVIEW FAILED",failure);finish(failure.toString());}
    }
    private static void finish(String error)
    {
        forward=0;finished=true;try{var data=new JsonObject();data.addProperty("error",error);data.add("checks",checks);Files.writeString(world.resolve(R22?"un_base_r22_review.json":"un_base_r21_review.json"),data.toString());}catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private UNBaseR21Review(){}
}

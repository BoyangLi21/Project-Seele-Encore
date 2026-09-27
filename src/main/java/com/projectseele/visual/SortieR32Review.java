package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.event.TvCampaignDirector;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.*;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.*;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Vector3f;
import java.nio.file.*;
import java.util.*;

/** Original three-cage launch, two NPCs and a real seated player, in the disposable world only. */
@Mod.EventBusSubscriber(modid="projectseele")
public final class SortieR32Review
{
    private static final boolean R41="r41-sortie".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R41||"r32-sortie".equals(System.getProperty("projectseele.regionalBuild",""));
    public static volatile boolean ready,finished;
    private static int ticks,stage,ritsukoStart,misatoStart;
    private static ServerLevel level;private static ServerPlayer player;private static Path world;
    private static final UUID[] fleet=new UUID[3],plugs=new UUID[3];
    private static final JsonObject report=new JsonObject();private static final JsonArray trace=new JsonArray();
    private static NervStaffEntity ritsuko,misato;
    private static void check(String key,boolean value){report.addProperty(key,value);if(!value)throw new IllegalStateException(key);}
    private static NervStaffEntity officer(String skin)
    {
        var post=NervStaffDirector.roster(level).stream().filter(p->p.skin().equals(skin)).findFirst().orElseThrow();level.getChunk(post.feet());
        var id=NervStaffSavedData.get(level).identity(post.id());return id!=null&&level.getEntity(id) instanceof NervStaffEntity n?n:null;
    }
    private static void poseChecks()
    {
        for(int variant=0;variant<5;variant++)
        {
            EvaUnit01Entity eva=variant==0?ModEntities.EVA_UNIT00.get().create(level):variant==1?ModEntities.EVA_UNIT01.get().create(level):variant==2?ModEntities.EVA_UNIT02.get().create(level):ModEntities.EVA_PROTOTYPE.get().create(level);
            if(eva instanceof EvaPrototypeEntity un)un.setUNSerial(variant-3);
            eva.prepareForMotionLab();eva.setPos(12000,281,12000);
            for(int mode:new int[]{EvaShutdownR30.EMPTY,EvaShutdownR30.WRECK})
            {
                EvaShutdownR30.clear(eva);if(mode==EvaShutdownR30.WRECK)EvaShutdownR30.fail(eva);else EvaShutdownR30.ensureUnpilotedR31(eva);
                // The settled disabled pose is the exact visible input to pickup, not a standing substitute.
                var nbt=eva.saveWithoutId(new CompoundTag());nbt.putLong("R30ShutdownSince",level.getGameTime()-40);eva.load(nbt);
                var before=EvaBodyPose.sample(eva,1);EvaAirTransportR31.begin(eva);
                // R35 added articulated shutdown. Production hands that body
                // to an active cradle at the next physics tick; this isolated
                // synchronous fixture must perform the same handoff first.
                com.projectseele.physics.CombatBodyDynamics.cancel(eva);
                com.projectseele.physics.CombatBodyDynamics.acknowledgeHandoff(eva);
                EvaAirTransportR31.transition(eva,0,1,1);
                var clamped=EvaBodyPose.sample(eva,2);double worst=0;
                for(var bone:before.rig.keySet())
                {
                    worst=Math.max(worst,1-Math.abs(before.rotations.get(bone).dot(clamped.rotations.get(bone))));
                    worst=Math.max(worst,before.positions.get(bone).distance(clamped.positions.get(bone)));
                }
                check("clamp_keeps_pose_"+variant+"_"+mode,worst<.0001);
                check("no_cable_"+variant+"_"+mode,!eva.isUmbilicalConnected());
                EvaAirTransportR31.transition(eva,90,1,1);var folded=EvaBodyPose.sample(eva,2);
                var face=folded.matrix("torso_lower").transformDirection(new Vector3f(0,0,-1)).normalize();
                check("face_down_cruise_"+variant+"_"+mode,face.y<-.98F);
                var restored=variant==0?ModEntities.EVA_UNIT00.get().create(level):variant==1?ModEntities.EVA_UNIT01.get().create(level):variant==2?ModEntities.EVA_UNIT02.get().create(level):ModEntities.EVA_PROTOTYPE.get().create(level);
                restored.load(eva.saveWithoutId(new CompoundTag()));check("transport_reload_"+variant+"_"+mode,EvaAirTransportR31.active(restored)&&EvaAirTransportR31.origin(restored).rotations.keySet().equals(EvaAirTransportR31.origin(eva).rotations.keySet()));
                EvaAirTransportR31.clear(eva);
            }
        }
        var legacy=new CompoundTag();legacy.putString("Active","sachiel");legacy.putUUID("Owner",player.getUUID());legacy.putInt("AssignedVariant",2);legacy.putBoolean("NpcPilot",true);
        var migrated=TvCampaignSavedData.load(legacy);check("legacy_roster_migration",migrated.sorties.size()==1&&migrated.sorties.get(2).npc);
        migrated.assign(1,player.getUUID(),false,false);var loaded=TvCampaignSavedData.load(migrated.save(new CompoundTag()));check("two_rosters_persist",loaded.sorties.size()==2&&loaded.sorties.get(2).npc&&!loaded.sorties.get(1).npc);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||!ready||finished||event.phase!=TickEvent.Phase.END||event.getServer().getPlayerList().getPlayers().isEmpty())return;
        try
        {
            if(world==null)
            {
                world=event.getServer().getWorldPath(LevelResource.ROOT).normalize();if(!world.getFileName().toString().equals(R41?"SEELE_R41_MECHANICS_REVIEW":"SEELE_R32_SORTIE_REVIEW"))throw new IllegalStateException("Wrong review world");
                level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);player=event.getServer().getPlayerList().getPlayers().get(0);
                player.stopRiding();player.setGameMode(GameType.CREATIVE);player.teleportTo(level,27.5,-407,282.5,0,0);
                player.getInventory().add(new net.minecraft.world.item.ItemStack(com.projectseele.registry.ModItems.NERV_EMPLOYEE_CARD.get()));
                event.getServer().setFlightAllowed(true);player.getAbilities().flying=true;player.onUpdateAbilities();poseChecks();
            }
            ticks++;level.resetEmptyTime();if(ticks>11000)throw new IllegalStateException("Sortie deadline stage "+stage);
            if(Files.deleteIfExists(world.resolve("regional_stop_requested")))throw new IllegalStateException("Review stopped for diagnosis");
            if(ticks%20==0)
            {
                for(int unit=0;unit<3;unit++)EvaLogisticsDirector.loadControlTarget(level,unit);
                var row=new JsonObject();row.addProperty("tick",ticks);row.addProperty("stage",stage);
                for(int i=0;i<3;i++)row.addProperty("unit"+i,EvaLogisticsDirector.status(level,i).phase());trace.add(row);
            }
            if(stage==0)
            {
                for(int i=0;i<3;i++)EvaLogisticsDirector.loadControlTarget(level,i);
                ritsuko=officer("ritsuko");misato=officer("misato");if(ritsuko==null||misato==null)return;
                for(int i=0;i<3;i++)
                {
                    var e=EvaLogisticsDirector.canonicalUnit(level,i);var p=EntryPlugDirector.canonical(level,i);if(e==null||p==null)return;
                    if(!EvaLogisticsDirector.status(level,i).phase().equals("PARKED"))throw new IllegalStateException("Review needs parked original "+i);
                    fleet[i]=e.getUUID();plugs[i]=p.getUUID();
                    // Test setup only: the owner's formal R31 contains a damaged Unit-01.
                    e.setHealth(e.getMaxHealth());EvaShutdownR30.clear(e);e.enterHangarStandby();
                }
                var d=TvCampaignSavedData.get(level);check("no_existing_encounter",d.active.isEmpty());ritsukoStart=ritsuko.pressCount();misatoStart=misato.pressCount();
                TvCampaignDirector.select(player,"shamshel");check("mission_start",TvCampaignDirector.beginAssigned(player,0,true,true)==1);
                check("second_unit_enrolled",TvSortiesR32.reinforce(player,1,false,false)==1);stage=1;return;
            }
            if(stage==1)
            {
                var plug=EntryPlugDirector.canonical(level,1);Vec3 hatch=plug.transformPlugMarker(EntryPlugKinematics.HATCH_PORTAL_CENTRE_P);
                Vec3 outward=plug.getCanonicalTransform().transformVector(EntryPlugKinematics.PILOT_VIEW_FORWARD_P).normalize();Vec3 eye=hatch.add(outward.scale(2.4)),look=hatch.subtract(eye);
                if(R41)
                {
                    var deck=EvaHangarBuilder.boardingPosition(RegionalFacilityLayout.evaOrigin(level),1);
                    eye=new Vec3(deck.getX()+.5,deck.getY()+player.getEyeHeight(),deck.getZ()+.5);look=hatch.subtract(eye);
                    check("actual_boarding_deck_has_floor",level.getBlockState(deck.below()).isFaceSturdy(level,deck.below(),net.minecraft.core.Direction.UP));
                }
                player.teleportTo(level,eye.x,eye.y-player.getEyeHeight(),eye.z,(float)Math.toDegrees(Math.atan2(-look.x,look.z)),(float)-Math.toDegrees(Math.atan2(look.y,look.horizontalDistance())));
                if(R41)
                {
                    // LivingEntity's view direction uses head yaw. A server
                    // teleport alone can retain the previous room's head
                    // direction until the next player tick.
                    player.setYHeadRot(player.getYRot());player.yHeadRotO=player.getYRot();
                }
                if(R41)
                {
                    JsonObject diagnostic=new JsonObject();diagnostic.addProperty("player",player.position().toString());diagnostic.addProperty("eye",player.getEyePosition().toString());diagnostic.addProperty("hatch",hatch.toString());
                    diagnostic.addProperty("distance",player.getEyePosition().distanceTo(hatch));diagnostic.addProperty("viewDot",hatch.subtract(player.getEyePosition()).normalize().dot(player.getViewVector(1)));
                    diagnostic.addProperty("hatchOpen",plug.isHatchOpen());diagnostic.addProperty("stage",plug.getInsertionStage());diagnostic.addProperty("canonicalPose",plug.hasCanonicalPose());diagnostic.addProperty("playerPassenger",player.isPassenger());diagnostic.addProperty("occupant",String.valueOf(plug.getFirstPassenger()));
                    var hit=level.clip(new net.minecraft.world.level.ClipContext(player.getEyePosition(),hatch,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,player));
                    diagnostic.addProperty("rayHit",hit.getType().toString());diagnostic.addProperty("hitPos",hit.getBlockPos().toShortString());diagnostic.addProperty("hitToHatch",hit.getLocation().distanceTo(hatch));
                    report.add("boardingContext",diagnostic);com.projectseele.ProjectSeele.LOGGER.info("R41 boarding diagnostic {}",diagnostic);
                }
                plug.tryBoardFromHatch(player);check("real_player_boarded",plug.getFirstPassenger()==player);stage=2;return;
            }
            for(int i=0;i<3;i++)
            {
                var e=EvaLogisticsDirector.canonicalUnit(level,i);var p=EntryPlugDirector.canonical(level,i);
                if(e==null||p==null){EvaLogisticsDirector.loadControlTarget(level,i);return;}
                check("original_identity_"+i,fleet[i].equals(e.getUUID())&&plugs[i].equals(p.getUUID()));
                check("no_plug_fault_"+i,!EvaLogisticsDirector.status(level,i).phase().equals("PLUG_FAULT"));
            }
            var d=TvCampaignSavedData.get(level);
            if(d.angel!=null&&level.getEntity(d.angel) instanceof net.minecraft.world.entity.LivingEntity boss)boss.setInvulnerable(true);
            if(stage==2&&d.angel!=null)
            {
                check("first_pair_deployed",EvaLogisticsDirector.status(level,0).phase().equals("DEPLOYED")&&EvaLogisticsDirector.status(level,1).phase().equals("DEPLOYED"));
                report.addProperty("original_angel",d.angel.toString());check("midbattle_support_accepted",TvSortiesR32.reinforce(player,2,true,false)==1);stage=3;
            }
            if(stage==3&&EvaLogisticsDirector.status(level,2).phase().equals("DEPLOYED"))
            {
                check("same_encounter",d.sorties.size()==3&&d.angel!=null&&d.angel.toString().equals(report.get("original_angel").getAsString()));
                ritsuko=officer("ritsuko");misato=officer("misato");if(ritsuko==null||misato==null)return;
                report.addProperty("ritsuko_presses",ritsuko.pressCount()-ritsukoStart);report.addProperty("misato_presses",misato.pressCount()-misatoStart);
                check("ritsuko_prepared_all",ritsuko.pressCount()-ritsukoStart==3);check("misato_launched_all_once",misato.pressCount()-misatoStart==3);
                check("two_independent_npc_controllers",NervPilotCombatR30.controls(EvaLogisticsDirector.canonicalUnit(level,0))&&NervPilotCombatR30.controls(EvaLogisticsDirector.canonicalUnit(level,2)));
                if(R41)
                {
                    var recovering=EvaLogisticsDirector.canonicalUnit(level,1);
                    if(!EvaLogisticsDirector.recoveryMotionSettled(recovering))return;
                    check("original_player_unit_recovery_accepted",EvaLogisticsDirector.requestRecovery(level,1).accepted());stage=4;
                }
                else finish(true,null);
            }
            if(R41&&stage==4&&EvaLogisticsDirector.status(level,1).phase().equals("PARKED"))
            {
                var deck=EvaHangarBuilder.boardingPosition(RegionalFacilityLayout.evaOrigin(level),1);
                check("return_bridge_floor_rebuilt",level.getBlockState(deck.below()).isFaceSturdy(level,deck.below(),net.minecraft.core.Direction.UP));
                check("original_eva_and_plug_recovered",EvaLogisticsDirector.canonicalUnit(level,1).getUUID().equals(fleet[1])&&EntryPlugDirector.canonical(level,1).getUUID().equals(plugs[1]));
                finish(true,null);
            }
        }
        catch(Throwable error){finish(false,error);}
    }
    private static void finish(boolean passed,Throwable error)
    {
        finished=true;report.addProperty("pass",passed);report.add("trace",trace);if(error!=null){report.addProperty("failure",error.toString());com.projectseele.ProjectSeele.LOGGER.error("R32 sortie review failed",error);}
        try{Path dir=world.resolve("Review");Files.createDirectories(dir);Files.writeString(dir.resolve("r32_sortie_"+(passed?"pass":"failure")+".json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));}catch(Exception e){throw new IllegalStateException(e);}
    }
    private SortieR32Review(){}
}

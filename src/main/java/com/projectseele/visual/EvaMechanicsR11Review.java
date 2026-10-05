package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.world.*;
import com.projectseele.registry.ModEntities;
import net.minecraft.server.level.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;

/** Disposable native capsule, articulation, hit and eye-ray acceptance fixture. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class EvaMechanicsR11Review
{
    public static final boolean R21=java.util.Set.of("r21-un00","r21-un01").contains(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean R19=R21||"r19-un".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final boolean ENABLED=R19||"r11-mechanics".equals(System.getProperty("projectseele.regionalBuild",""));
    public static final java.util.Set<String> captured=java.util.concurrent.ConcurrentHashMap.newKeySet();
    public static volatile int actor,age;public static volatile boolean tracked,finished;public static volatile String shot="",view="body";
    private static final net.minecraft.server.level.TicketType<net.minecraft.world.level.ChunkPos> TARGET_TICKET=net.minecraft.server.level.TicketType.create("r11_mechanics_target",java.util.Comparator.comparingLong(net.minecraft.world.level.ChunkPos::toLong),80);
    private static int phase,tick;private static EvaPrototypeEntity eva;private static ServerPlayer pilot;private static SachielEntity target;
    private static final JsonArray trace=new JsonArray();private static final JsonObject checks=new JsonObject();private static java.util.UUID plugId;
    private static float targetHealth;private static Path world;
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||finished||event.phase!=TickEvent.Phase.END)return;var server=event.getServer();if(server.getPlayerList().getPlayers().isEmpty()||++age<70)return;
        world=server.getWorldPath(LevelResource.ROOT).normalize();if(!world.getFileName().toString().equals(R21?"SEELE_UN_R21_REVIEW":R19?"SEELE_UN_R19_REVIEW":"SEELE_MECHANICS_REVIEW_R11"))throw new IllegalStateException("UN mechanics requires disposable lab");
        ServerLevel l=server.overworld();try
        {
            if(age>1800)throw new IllegalStateException("UN mechanics deadline in phase "+phase);
            if(phase==0)
            {
                pilot=server.getPlayerList().getPlayers().get(0);pilot.stopRiding();pilot.setGameMode(net.minecraft.world.level.GameType.SURVIVAL);pilot.getCapability(com.projectseele.capability.EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));server.setFlightAllowed(true);server.setDifficulty(net.minecraft.world.Difficulty.NORMAL,true);
                var old=new java.util.ArrayList<net.minecraft.world.entity.Entity>();for(var e:l.getAllEntities())if(e instanceof EvaUnit01Entity||e instanceof EntryPlugCarrierEntity p&&p.laboratorySlotR47()<0&&!p.isIndependentUNPlug()||e instanceof SachielEntity)old.add(e);old.forEach(net.minecraft.world.entity.Entity::discard);
                l.getGameRules().getRule(GameRules.RULE_DOMOBSPAWNING).set(false,server);l.getGameRules().getRule(GameRules.RULE_DAYLIGHT).set(false,server);l.setDayTime(6000);
                for(BlockPos p:BlockPos.betweenClosed(-45,-60,-55,45,22,200))if(!l.getBlockState(p).isAir())l.setBlock(p,Blocks.AIR.defaultBlockState(),2);
                for(BlockPos p:BlockPos.betweenClosed(-45,-61,-55,45,-61,200))l.setBlock(p,Blocks.GRAY_CONCRETE.defaultBlockState(),2);
                l.setBlock(new BlockPos(-20,-60,0),com.projectseele.registry.ModBlocks.UMBILICAL_PYLON.get().defaultBlockState(),2);
                for(BlockPos b:BlockPos.betweenClosed(-5,-12,-16,5,-11,-10))if(Math.abs(b.getX())>=2)l.setBlock(b,Blocks.IRON_BLOCK.defaultBlockState(),2);
                eva=ModEntities.EVA_PROTOTYPE.get().create(l);if("r21-un01".equals(System.getProperty("projectseele.regionalBuild","")))eva.setUNSerial(1);eva.moveTo(.5,-60,.5,0,0);eva.setNoAi(true);eva.setNoGravity(true);eva.getPersistentData().putBoolean("UNMechanicsLab",true);l.addFreshEntity(eva);actor=eva.getId();pilot.teleportTo(l,.5,-10,-18,0,0);phase=1;tick=0;return;
            }
            tick++;EntryPlugCarrierEntity p=UNPlugDirector.capsule(eva);
            if(target!=null&&tick%20==0){var c=new net.minecraft.world.level.ChunkPos(target.blockPosition());l.getChunkSource().addRegionTicket(TARGET_TICKET,c,2,c);l.getChunk(c.x,c.z);}
            if(p!=null)
            {
                JsonObject row=new JsonObject();row.addProperty("age",age);row.addProperty("phase",phase);row.addProperty("tick",tick);row.addProperty("stage",p.getInsertionStage());row.addProperty("progress",p.getInsertionProgress());row.addProperty("open",EvaDorsalMechanism.open(eva));row.addProperty("bow",EvaDorsalMechanism.bow(eva));row.addProperty("eyes",EvaDorsalMechanism.eyesEnabled(eva));row.addProperty("plug_x",p.getX());row.addProperty("plug_y",p.getY());row.addProperty("plug_z",p.getZ());row.addProperty("head_laser",eva.isEyeLaserActive());row.addProperty("power",eva.getPowerTicks());row.addProperty("eye_end",eva.eyeLaserEnd().toString());if(target!=null){row.addProperty("target_tick",target.tickCount);row.addProperty("target_health",target.getHealth());row.addProperty("target_removed",target.isRemoved());row.addProperty("strike_age",target.strikeAge(1));}trace.add(row);
                if(age%20==0){JsonObject checkpoint=new JsonObject();checkpoint.add("checks",checks);checkpoint.add("trace",trace);Files.writeString(world.resolve("r11_mechanics_partial.json"),checkpoint.toString());}
            }
            if(phase==1&&tick>50&&tracked&&p!=null)
            {
                // Asset warming can consume the old fixed screenshot windows.
                // Request each view until the actual client confirms capture.
                shot=!captured.contains("un_body")?"un_body":!captured.contains("crane_full")?"crane_full":"crane_detail";
                view=shot.equals("un_body")?"body":shot.equals("crane_full")?"crane":"crane_detail";
                if(tick>140&&captured.contains("un_body")&&captured.contains("crane_full")&&captured.contains("crane_detail")){plugId=p.getUUID();if(!p.boardPassenger(pilot))throw new IllegalStateException("UN boarding refused");phase=2;tick=0;}return;
            }
            if(phase==2)
            {
                if(p==null)throw new IllegalStateException("dedicated capsule lost");
                view="dorsal";
                if(p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_INSERTING)
                {if(p.getInsertionProgress()<1&&EvaDorsalMechanism.open(eva)>.6)shot="dorsal_opening";else if(p.getInsertionProgress()<35)shot="crane_approach";else if(p.getInsertionProgress()<70)shot="socket_alignment";else if(p.getInsertionProgress()<98)shot="spinal_insertion";}
                if(p.isLockedToEva()&&EvaDorsalMechanism.bow(eva)<.001F)
                {
                    checks.addProperty("same_capsule_locked",plugId.equals(p.getUUID())&&pilot.getVehicle()==p&&p.getVehicle()==eva);checks.addProperty("seals_then_eyes",EvaDorsalMechanism.open(eva)<.001&&EvaDorsalMechanism.eyesEnabled(eva));shot="sealed_and_raised";
                    var targetChunk=new net.minecraft.world.level.ChunkPos(0,10);l.getChunkSource().addRegionTicket(TARGET_TICKET,targetChunk,2,targetChunk);l.getChunk(0,10);
                    target=ModEntities.SACHIEL.get().create(l);target.setPersistenceRequired();target.moveTo(.5,-60,160,180,0);target.setNoAi(true);target.setNoGravity(true);target.setFirstBattleField(0);l.addFreshEntity(target);targetHealth=target.getHealth();phase=3;tick=0;
                }
                if(tick>420)throw new IllegalStateException("UN insertion deadline stage="+p.getInsertionStage()+" progress="+p.getInsertionProgress());return;
            }
            if(phase==3)
            {
                view="laser";pilot.setYRot(0);pilot.setXRot(0);
                if(tick==35){if(l.getEntity(target.getId())!=target)throw new IllegalStateException("Eye target not alive in world");eva.requestEyeLaser(pilot);checks.addProperty("eye_charge_armed",eva.isEyeLaserActive()&&eva.eyeLaserCooldown()>0);}if(tick==40){int old=eva.eyeLaserCooldown();eva.requestEyeLaser(pilot);checks.addProperty("cooldown_cannot_restart",old>0&&eva.eyeLaserCooldown()==old);}if(tick>=44&&tick<=48)shot="eye_laser_contact";
                if(tick==65){checks.addProperty("eye_ray_hit",target.getHealth()<targetHealth);targetHealth=target.getHealth();target.setFirstBattleField(900);}
                if(tick==90)eva.requestEyeLaser(pilot);if(tick>=99&&tick<=103)shot="at_field_deflection";
                if(tick==120){checks.addProperty("shield_blocks_eye_damage",target.getHealth()==targetHealth);target.setFirstBattleField(0);for(BlockPos b:BlockPos.betweenClosed(-4,-12,70,4,4,72))l.setBlock(b,Blocks.IRON_BLOCK.defaultBlockState(),2);}
                if(tick==140)eva.requestEyeLaser(pilot);
                if(tick==170){checks.addProperty("wall_blocks_eye_damage",target.getHealth()==targetHealth&&eva.eyeLaserEnd().z<73);for(BlockPos b:BlockPos.betweenClosed(-4,-12,70,4,4,72))l.setBlock(b,Blocks.AIR.defaultBlockState(),2);}
                if(tick==185){com.projectseele.event.EvaHitFeedback.hurt(eva,target.damageSources().mobAttack(target),15,eva.position().add(6,46,0),new Vec3(-1,.1,.3));com.projectseele.event.EvaHitFeedback.hurt(target,eva.damageSources().mobAttack(eva),24,target.position().add(-5,48,0),new Vec3(1,.1,-.3));view="body";}
                if(tick==188){checks.addProperty("eva_directional_response",EvaImpactResponse.sample(eva,1).energy()>0);checks.addProperty("angel_directional_response",EvaImpactResponse.sample(target,1).energy()>0);shot="directional_impact";}
                if(tick==218)
                {
                    var tag=new net.minecraft.nbt.CompoundTag();p.saveWithoutId(tag);EntryPlugCarrierEntity restored=ModEntities.ENTRY_PLUG_CARRIER.get().create(l);restored.load(tag);checks.addProperty("un_identity_persisted",restored.isIndependentUNPlug()&&restored.getHostEvaUuid().equals(eva.getUUID()));
                    if(!EntryPlugDirector.ejectPilotToPlug(l,1,eva,pilot))throw new IllegalStateException("UN extraction rejected");phase=4;tick=0;
                }
            }
            if(phase==4)
            {
                view="dorsal";if(tick>50&&tick<90)shot="crane_extraction";
                if(tick>220){checks.addProperty("same_capsule_returned",p.getUUID().equals(plugId)&&p.getInsertionProgress()==0&&!p.isLockedToEva()&&EvaDorsalMechanism.open(eva)<.001);target.moveTo(.5,-60,48,180,0);target.yBodyRot=target.yHeadRot=180;targetHealth=eva.getHealth();target.beginStrike(eva,2);phase=5;tick=0;}
            }
            if(phase==5)
            {
                view="combat";
                if(tick==11)checks.addProperty("sachiel_no_damage_during_windup",eva.getHealth()==targetHealth);
                if(tick>=21&&tick<=24)shot="sachiel_bone_lance";
                if(tick==60){checks.addProperty("sachiel_lance_contact_damage",eva.getHealth()<targetHealth);if(!p.boardPassenger(pilot))throw new IllegalStateException("Reboarding for abort check");phase=6;tick=0;}
            }
            if(phase==6)
            {
                view="dorsal";
                if(p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_INSERTING&&p.getInsertionProgress()>=45)p.requestInsertionAbort();
                if(tick>70&&p.getInsertionStage()==EntryPlugCarrierEntity.STAGE_SUSPENDED&&p.getInsertionProgress()==0){checks.addProperty("abort_returns_same_capsule",p.getUUID().equals(plugId)&&EvaDorsalMechanism.open(eva)<.001&&EvaDorsalMechanism.bow(eva)<.001);finish("");}
                if(tick>460)throw new IllegalStateException("UN abort return deadline");
            }
            if(age>1800)throw new IllegalStateException("R11 mechanics deadline");
        }
        catch(Exception e){ProjectSeele.LOGGER.error("R11 MECHANICS FAILED",e);finish(e.toString());}
    }
    private static void finish(String error)
    {
        finished=true;JsonObject data=new JsonObject();data.addProperty("error",error);data.add("checks",checks);data.add("trace",trace);try{Files.writeString(world.resolve("r11_mechanics.json"),data.toString());}catch(Exception ignored){}ProjectSeele.LOGGER.info("R11 MECHANICS RESULT {} {}",error,checks);
    }
}

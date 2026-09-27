package com.projectseele.event;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.fx.CrossExplosionFX;
import com.projectseele.registry.ModSounds;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.FirstBattleSavedData;
import net.minecraft.core.particles.BlockParticleOption;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.level.TicketType;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.sounds.SoundSource;
import net.minecraft.tags.DamageTypeTags;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.living.LivingAttackEvent;
import net.minecraftforge.event.level.LevelEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.util.*;

/** Bounded server authority for the Unit-01/Sachiel finale. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class FirstBattleDirector
{
    private static final TicketType<ChunkPos> TICKET=TicketType.create("first_battle_r10",Comparator.comparingLong(ChunkPos::toLong),80);
    private static final Map<ServerLevel,Set<ChunkPos>> TICKETS=new WeakHashMap<>();
    public static boolean tryStart(SachielEntity angel,EvaUnit01Entity eva,boolean review)
    {
        if(!review&&(EvaBerserkMotionR34.introduction(eva)||EvaBerserkMotionR34.striking(eva)&&EvaBerserkMotionR34.phase(eva,0)<.72F))return false;
        if(!review&&(com.projectseele.entity.EvaCombatR31.active(eva)||com.projectseele.entity.EvaCombatR31.holds(angel)
                ||com.projectseele.entity.CombatFeelR31.restrained(eva)||com.projectseele.entity.CombatFeelR31.restrained(angel)))return false;
        if("r10-firstbattle".equals(System.getProperty("projectseele.regionalBuild","")))
            ProjectSeele.LOGGER.info("R10 START CHECK health={} ready={} pilot={} variant={} experimental={} locked={} launch={} crucified={} powered={} prone={} crouch={} weapon={} used={} ground={} position={}",angel.getHealth(),FirstBattleClip.ready(),eva.getPilotEntity(),eva.getUnitVariant(),eva.isExperimentalUnit(),eva.isNervLogisticsLocked(),eva.isLaunchSequenceActive(),eva.isCrucified(),eva.isPoweredOn(),eva.isPilotProne(),eva.isPilotCrouching(),eva.getWeapon(),angel.hasUsedFirstBattle(),eva.onGround(),eva.position());
        if(!(angel.level() instanceof ServerLevel level)||eva.level()!=level||!angel.isAlive()||!eva.isAlive()||!FirstBattleClip.ready())return false;
        if(level.getEntity(eva.getUUID())!=eva||level.getEntity(angel.getUUID())!=angel)return false;
        if(com.projectseele.physics.CombatBodyDynamics.active(eva)||com.projectseele.physics.CombatBodyDynamics.active(angel))return false;
        var occupant=eva.getPilotEntity();ServerPlayer pilot=occupant instanceof ServerPlayer p?p:null;
        if(occupant instanceof com.projectseele.entity.TrainingPilotEntity)
        {
            var campaign=com.projectseele.world.TvCampaignSavedData.get(level);
            var sortie=campaign.sorties.get(1);
            if(sortie!=null&&sortie.npc&&campaign.active.equals("sachiel"))pilot=level.getServer().getPlayerList().getPlayer(sortie.commander);
        }
        if(pilot==null||eva.getUnitVariant()!=EvaUnit01Entity.UNIT_01||eva.isExperimentalUnit()||eva.isNervLogisticsLocked()||eva.isLaunchSequenceActive()||eva.isCrucified()||!eva.isPoweredOn())return false;
        if(eva.isPilotProne()||eva.isPilotCrouching()||eva.getWeapon()==EvaUnit01Entity.WEAPON_N2||angel.hasUsedFirstBattle())return false;
        FirstBattleSavedData data=FirstBattleSavedData.get(level);if(data.active!=null)return false;
        boolean selectedReplay=pilot.getUUID().equals(data.missionOwner)&&com.projectseele.world.TvCampaignSavedData.get(level).active.equals("sachiel");
        if(!review&&!selectedReplay&&!eva.isBerserk()&&data.completedPilots.contains(pilot.getUUID())&&!angel.getTags().contains("seele_first_battle_replay"))return false;
        Vec3 delta=angel.position().subtract(eva.position());double distance=delta.horizontalDistance();
        if(!review&&(angel.getHealth()>angel.getMaxHealth()*.32F||!stableSupport(eva)||distance<14||distance>46||Math.abs(delta.y)>4))
        {
            if("r30-npc-combat".equals(System.getProperty("projectseele.regionalBuild",""))&&angel.getHealth()<=angel.getMaxHealth()*.32F&&level.getGameTime()%40==0)
                ProjectSeele.LOGGER.info("R30 FINALE WAIT health={} distance={} height={} stable={} eva={} angel={}",angel.getHealth(),distance,delta.y,stableSupport(eva),eva.position(),angel.position());
            return false;
        }
        float yaw=(float)Math.toDegrees(Math.atan2(-delta.x,delta.z));
        var spec=new FirstBattleSignals.Spec(eva.position(),yaw,eva.getYRot(),angel.getYRot(),(float)distance,(float)delta.y);
        if(!review&&!spaceReady(level,eva,spec))
        {
            if("r30-npc-combat".equals(System.getProperty("projectseele.regionalBuild",""))&&level.getGameTime()%40==0)ProjectSeele.LOGGER.info("R30 FINALE WAIT scene clearance eva={} angel={} yaw={}",eva.position(),angel.position(),yaw);
            return false;
        }
        var record=new FirstBattleSavedData.Encounter();record.eva=eva.getUUID();record.angel=angel.getUUID();record.pilot=pilot.getUUID();record.npcPilot=occupant instanceof com.projectseele.entity.TrainingPilotEntity?occupant.getUUID():null;record.spec=spec;record.originalField=angel.getAtField();record.originalHealth=angel.getHealth();data.active=record;data.setDirty();
        eva.beginFirstBattle(spec,angel.getId());angel.beginFirstBattle(spec,eva.getId());
        tickets(level,record);pilot.displayClientMessage(Component.literal("制御不能 — 初号机进入自主行动"),true);
        com.projectseele.world.NervStaffDialogue.say(pilot,"赤木律子 · 指挥通信","初号机没有接收指令……它在自行行动。驾驶员的生命信号还在。");
        sound(level,FirstBattleClip.point(spec,true,"eye_blocks",0),ModSounds.EVA_BERSERK_ROAR.get(),2.3F);
        ProjectSeele.LOGGER.info("R10 FIRST BATTLE START hero={} angel={} pilot={} health={}",record.eva,record.angel,record.pilot,record.originalHealth);return true;
    }
    public static boolean stableSupport(EvaUnit01Entity eva)
    {
        double velocity=eva.getDeltaMovement().y,gravity=eva.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get());
        if(velocity>.2||velocity<-(gravity+.07))return false;
        // Ridden actors are movement-authoritative on the pilot's client; a
        // stationary vehicle can have a stale server onGround bit. Require
        // actual nearby floor in three of five small sole-area probes.
        int supported=0;double x=eva.getX(),y=eva.getY(),z=eva.getZ();
        for(double[] offset:new double[][]{{0,0},{-3,0},{3,0},{0,-2},{0,2}})
        {
            AABB sole=new AABB(x+offset[0]-.6,y-.16,z+offset[1]-.6,x+offset[0]+.6,y+.005,z+offset[1]+.6);
            if(eva.level().getBlockCollisions(eva,sole).iterator().hasNext())supported++;
        }
        return supported>=3;
    }
    public static Vec3 stagingPosition(EvaUnit01Entity eva,SachielEntity angel,int alternate)
    {
        if(!(eva.level() instanceof ServerLevel level))return null;
        Vec3 away=eva.position().subtract(angel.position()).multiply(1,0,1).normalize();
        if(away.lengthSqr()<.1)away=eva.getForward().scale(-1);
        Vec3 best=null;double cost=Double.MAX_VALUE;
        for(double radius:new double[]{24,30})for(int angle:new int[]{0,30,-30,60,-60,90,-90,180})
        {
            if(alternate>0&&angle==0)continue;
            Vec3 offset=away.yRot((float)Math.toRadians(angle)).scale(radius),candidate=angel.position().add(offset);
            var at=net.minecraft.core.BlockPos.containing(candidate);if(!level.hasChunkAt(at))continue;
            Double floor=null;
            for(int y=at.getY()+4;y>=at.getY()-6;y--)
            {
                var pos=new net.minecraft.core.BlockPos(at.getX(),y,at.getZ());var shape=level.getBlockState(pos).getCollisionShape(level,pos);
                if(!shape.isEmpty()){floor=y+shape.max(net.minecraft.core.Direction.Axis.Y);break;}
            }
            if(floor==null||Math.abs(floor-angel.getY())>4)continue;
            candidate=new Vec3(candidate.x,floor,candidate.z);
            if(!level.noCollision(eva,eva.getBoundingBox().move(candidate.subtract(eva.position())).deflate(.05)))continue;
            Vec3 delta=angel.position().subtract(candidate);float yaw=(float)Math.toDegrees(Math.atan2(-delta.x,delta.z));
            var spec=new FirstBattleSignals.Spec(candidate,yaw,eva.getYRot(),angel.getYRot(),(float)radius,(float)delta.y);
            if(!spaceReady(level,eva,spec))continue;
            if(angle==0&&radius==24&&alternate==0)return candidate;
            double distance=candidate.distanceToSqr(eva.position());if(distance<cost){cost=distance;best=candidate;}
        }
        return best;
    }
    private static boolean participantPresent(FirstBattleSavedData.Encounter record,EvaUnit01Entity eva,ServerPlayer commander)
    {
        if(record.npcPilot==null)return EvaPilotResolver.controlTarget(commander)==eva;
        return eva.getPilotEntity() instanceof com.projectseele.entity.TrainingPilotEntity pilot&&pilot.getUUID().equals(record.npcPilot);
    }
    private static boolean spaceReady(ServerLevel level,EvaUnit01Entity eva,FirstBattleSignals.Spec spec)
    {
        for(float t:new float[]{0,5,9.2F,10.7F,11.7F,15,19.4F,23})for(boolean hero:new boolean[]{true,false})
        {
            Vec3 p=FirstBattleClip.point(spec,hero,"root_blocks",t);double half=hero?8.5:10;
            // During the ground grapple the root pivot lies below the floor;
            // the folded skeleton has a compensating authored root offset.
            // Only the body above the reviewed contact plane needs free air.
            double bottom=Math.max(spec.origin().y+.15,p.y+.15);
            AABB box=new AABB(p.x-half,bottom,p.z-half,p.x+half,Math.max(bottom+1,spec.origin().y+80),p.z+half);
            if(level.getBlockCollisions(eva,box).iterator().hasNext())return false;
        }
        return true;
    }
    private static void tickets(ServerLevel level,FirstBattleSavedData.Encounter record)
    {
        Set<ChunkPos> held=TICKETS.computeIfAbsent(level,k->new HashSet<>());
        for(float t:new float[]{0,10,16,23})for(boolean hero:new boolean[]{true,false})
        {
            Vec3 p=FirstBattleClip.point(record.spec,hero,"root_blocks",t);ChunkPos centre=new ChunkPos(net.minecraft.core.BlockPos.containing(p));
            for(int dx=-2;dx<=2;dx++)for(int dz=-2;dz<=2;dz++)
            {
                ChunkPos chunk=new ChunkPos(centre.x+dx,centre.z+dz);held.add(chunk);level.getChunkSource().addRegionTicket(TICKET,chunk,2,chunk);
            }
        }
    }
    private static void release(ServerLevel level)
    {
        Set<ChunkPos> held=TICKETS.remove(level);if(held!=null)for(ChunkPos p:held)level.getChunkSource().removeRegionTicket(TICKET,p,2,p);
    }
    private static void sound(ServerLevel level,Vec3 p,SoundEvent sound,float volume)
    {
        level.playSound(null,p.x,p.y,p.z,sound,SoundSource.HOSTILE,volume,1);
    }
    private static void chips(ServerLevel level,Vec3 p,boolean bone)
    {
        level.sendParticles(new BlockParticleOption(ParticleTypes.BLOCK,(bone?Blocks.QUARTZ_BLOCK:Blocks.REDSTONE_BLOCK).defaultBlockState()),p.x,p.y,p.z,30,1.4,.6,1.4,.25);
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START)return;
        String mode=System.getProperty("projectseele.regionalBuild","");if(mode.equals("r10-models")||mode.equals("r10-choreography"))return;
        for(ServerLevel level:event.getServer().getAllLevels())
        {
            FirstBattleSavedData data=FirstBattleSavedData.get(level);var record=data.active;if(record==null)continue;
            try
            {
                if(!TICKETS.containsKey(level)||event.getServer().getTickCount()%20==0)tickets(level,record);
                Entity h=level.getEntity(record.eva),a=level.getEntity(record.angel);ServerPlayer pilot=event.getServer().getPlayerList().getPlayer(record.pilot);
                // Player data can be saved after vanilla has detached the ride
                // chain at shutdown. Rejoin only this recorded pilot and actor,
                // only during startup reconciliation, without replacing either.
                if(record.npcPilot==null&&!record.observedActors&&h instanceof EvaUnit01Entity restored&&restored.isFirstBattleActive()
                        &&pilot!=null&&pilot.level()==level&&!pilot.isPassenger()&&restored.getPilotEntity()==null
                        &&pilot.distanceToSqr(restored)<128*128)
                    restored.boardFromExternalPlug(pilot,100);
                if(!(h instanceof EvaUnit01Entity eva)||!eva.isAlive()||pilot==null||!participantPresent(record,eva,pilot)||(!(a instanceof SachielEntity)&&!record.deathResolved))
                {
                    boolean actorLost=record.observedActors&&(!(h instanceof EvaUnit01Entity)||(!(a instanceof SachielEntity)&&!record.deathResolved));
                    if(actorLost||++record.missingTicks>(record.observedActors?40:200))abort(level,"participant unavailable");continue;
                }
                record.missingTicks=0;record.observedActors=true;SachielEntity angel=a instanceof SachielEntity s?s:null;
                if(angel!=null&&!angel.isAlive()&&!record.deathResolved){abort(level,"Angel removed before finale");continue;}
                record.age++;float seconds=record.age/20F;
                eva.firstBattleSignals().resume(eva,record.spec,record.age,angel==null?-1:angel.getId());
                if(angel!=null)angel.firstBattleSignals().resume(angel,record.spec,record.age,eva.getId());
                FirstBattleClip.applyKinematics(eva);if(angel!=null)FirstBattleClip.applyKinematics(angel);
                // The director moves a nested EVA -> plug -> pilot assembly
                // without ordinary player movement packets. Keep the pilot's
                // chunk subscription centred on that authoritative motion.
                if(record.npcPilot==null&&record.age%20==0)level.getChunkSource().move(pilot);
                if(angel!=null)angel.setFirstBattleField(900*(1-FirstBattleClip.smooth((seconds-3)/2)));
                Vec3 field=FirstBattleClip.world(record.spec,new Vec3(0,40,21));
                if(record.age==19||record.age==122||record.age==410||record.age==428)
                    sound(level,FirstBattleClip.point(record.spec,true,record.age==19||record.age==410?"foot_l_blocks":"foot_r_blocks",seconds),ModSounds.EVA_FOOT_CONCRETE.get(),1.5F);
                if(record.age==28||record.age==53||record.age==75)sound(level,field,ModSounds.EVA_AT_PRESSURE.get(),1.3F);
                if(record.age==99)sound(level,field,ModSounds.EVA_AT_TEAR.get(),1.8F);
                if(record.age==107)CrossExplosionFX.spawn(level,FirstBattleClip.point(record.spec,false,"eye_blocks",seconds),.30F);
                if(record.age==160){Vec3 p=FirstBattleClip.point(record.spec,false,"hand_r_blocks",seconds);sound(level,p,ModSounds.EVA_ARMOR_IMPACT.get(),1.5F);chips(level,p,true);}
                if(record.age==184){Vec3 p=FirstBattleClip.point(record.spec,true,"foot_l_blocks",seconds);sound(level,p,ModSounds.EVA_IMPACT.get(),1.8F);chips(level,p,false);}
                if(record.age==FirstBattleClip.landingTick())sound(level,eva.position(),ModSounds.EVA_LAND.get(),2.1F);
                if(record.age==307){Vec3 p=FirstBattleClip.point(record.spec,true,"hand_r_blocks",seconds);sound(level,p,ModSounds.EVA_ARMOR_IMPACT.get(),1.4F);chips(level,p,true);}
                if(record.age==255||record.age==283||record.age==321)
                {
                    Vec3 p=FirstBattleClip.point(record.spec,true,"hand_r_blocks",seconds);sound(level,p,record.age==321?ModSounds.EVA_CORE_BREAK.get():ModSounds.EVA_IMPACT.get(),1.8F);chips(level,p,record.age==321);
                    if(angel!=null)angel.setHealth(Math.max(1,record.originalHealth*(record.age==255?.6F:record.age==283?.25F:.05F)));
                }
                if(record.age==354)sound(level,FirstBattleClip.point(record.spec,false,"core_blocks",seconds),ModSounds.EVA_AT_PRESSURE.get(),1.6F);
                if(record.age>=FirstBattleClip.DEATH_TICK&&!record.deathResolved)finishAngel(level,data,eva,angel,pilot);
                if(record.age>=FirstBattleClip.DURATION_TICKS)
                {
                    TvCampaignDirector.firstBattleComplete(level,data.missionOwner==null?record.pilot:data.missionOwner,record.angel);
                    eva.completeFirstBattle();if(angel!=null)angel.endFirstBattle();
                    publishControlReturn(level,eva,pilot);if(angel!=null)publishState(level,angel,pilot);
                    data.completedPilots.add(pilot.getUUID());data.active=null;data.missionOwner=null;data.missionAngel=null;release(level);
                    pilot.displayClientMessage(Component.literal("目標沈黙 — 初号机操纵已恢复"),true);ProjectSeele.LOGGER.info("R10 FIRST BATTLE COMPLETE hero={} pilot={}",eva.getUUID(),pilot.getUUID());
                }
                data.setDirty();
            }
            catch(Exception e){ProjectSeele.LOGGER.error("First battle aborted after director failure",e);abort(level,"director exception");}
        }
    }
    private static void finishAngel(ServerLevel level,FirstBattleSavedData data,EvaUnit01Entity eva,SachielEntity angel,ServerPlayer pilot)
    {
        var record=data.active;if(record==null||record.deathResolved)return;record.deathResolved=true;data.setDirty();
        Vec3 p=angel==null?eva.position().add(0,40,0):FirstBattleClip.point(record.spec,false,"core_blocks",Math.min(18.6F,record.age/20F));
        var finale=new com.projectseele.network.ClientboundBattleFinalePacket(p.x,record.spec.origin().y,p.z);
        for(var observer:level.players())
            if(observer==pilot||observer.position().distanceToSqr(p)<1024*1024)
                com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.PLAYER.with(()->observer),finale);
        if(angel!=null)angel.finishFirstBattle(eva,pilot);
        ProjectSeele.LOGGER.info("R10 FIRST BATTLE DEATH ONCE angel={} pilot={} age={}",record.angel,record.pilot,record.age);
    }
    private static void publishState(ServerLevel level,Entity actor,ServerPlayer pilot)
    {
        // Flush BEFORE releasing the director's chunk tickets. Otherwise the
        // last dirty `active=false` can be stranded when the actor stops
        // ticking, leaving a client's cinematic clock at age 459 forever.
        var values=actor.getEntityData().packDirty();
        if(values==null||values.isEmpty())return;
        var packet=new net.minecraft.network.protocol.game.ClientboundSetEntityDataPacket(actor.getId(),values);
        level.getChunkSource().broadcastAndSend(actor,packet);
        if(pilot!=null&&pilot.level()==level)pilot.connection.send(packet);
    }
    private static void publishControlReturn(ServerLevel level,EvaUnit01Entity eva,ServerPlayer pilot)
    {
        publishState(level,eva,pilot);
        level.getChunkSource().broadcastAndSend(eva,new net.minecraft.network.protocol.game.ClientboundTeleportEntityPacket(eva));
        if(pilot!=null&&pilot.level()==level&&EvaPilotResolver.controlTarget(pilot)==eva)
        {
            level.getChunkSource().move(pilot);
            // Vanilla intentionally ignores vehicle teleports on its locally
            // authoritative driver. Use the existing bounded arrival bridge.
            com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.PLAYER.with(()->pilot),
                    new com.projectseele.network.ClientboundEvaArrivalSyncPacket(eva.getId(),eva.getX(),eva.getY(),eva.getZ(),eva.getYRot(),eva.getXRot()));
        }
    }
    public static boolean skip(ServerPlayer pilot)
    {
        ServerLevel level=pilot.serverLevel();FirstBattleSavedData data=FirstBattleSavedData.get(level);var r=data.active;if(r==null||!r.pilot.equals(pilot.getUUID()))return false;
        Entity entity=level.getEntity(r.eva);if(!(entity instanceof EvaUnit01Entity eva))return false;
        Entity enemy=level.getEntity(r.angel);finishAngel(level,data,eva,enemy instanceof SachielEntity s?s:null,pilot);
        Vec3 end=FirstBattleClip.localPoint(r.spec,true,"root_blocks",FirstBattleClip.RETURN_TICK/20F);Vec3 offset=FirstBattleClip.world(r.spec,end).subtract(r.spec.origin());
        Vec3 origin=new Vec3(eva.getX()-offset.x,r.spec.origin().y,eva.getZ()-offset.z);
        r.spec=new FirstBattleSignals.Spec(origin,r.spec.yaw(),r.spec.yaw(),r.spec.yaw()+180,34,0);r.age=FirstBattleClip.RETURN_TICK;r.skipped=true;data.setDirty();return true;
    }
    public static void abort(ServerLevel level,String reason)
    {
        FirstBattleSavedData data=FirstBattleSavedData.get(level);var r=data.active;if(r==null)return;
        Entity h=level.getEntity(r.eva),a=level.getEntity(r.angel);
        ServerPlayer pilot=level.getServer().getPlayerList().getPlayer(r.pilot);
        if(h instanceof EvaUnit01Entity eva){eva.setPos(eva.getX(),r.spec.origin().y,eva.getZ());eva.endFirstBattle();publishControlReturn(level,eva,pilot);}
        if(a instanceof SachielEntity angel){angel.setPos(angel.getX(),r.spec.origin().y,angel.getZ());angel.endFirstBattle();angel.setFirstBattleField(r.originalField);publishState(level,angel,pilot);}
        data.active=null;data.setDirty();release(level);ProjectSeele.LOGGER.info("R10 FIRST BATTLE ABORT {}",reason);
    }
    @SubscribeEvent public static void protectPilot(LivingAttackEvent event)
    {
        if(event.getEntity().level() instanceof ServerLevel level&&!event.getSource().is(DamageTypeTags.BYPASSES_INVULNERABILITY))
        {
            var active=FirstBattleSavedData.get(level).active;
            if(active!=null&&event.getEntity().getUUID().equals(active.npcPilot==null?active.pilot:active.npcPilot))event.setCanceled(true);
        }
    }
    @SubscribeEvent public static void unload(LevelEvent.Unload event){if(event.getLevel() instanceof ServerLevel level)release(level);}
    @SubscribeEvent public static void reconcile(net.minecraftforge.event.entity.EntityJoinLevelEvent event)
    {
        if(!(event.getLevel() instanceof ServerLevel level)||!(event.getEntity() instanceof FirstBattleSignals.Actor actor)||!actor.firstBattleSignals().active(event.getEntity()))return;
        String mode=System.getProperty("projectseele.regionalBuild","");if(mode.equals("r10-choreography")||mode.equals("r10-models"))return;
        Entity entity=event.getEntity();
        level.getServer().execute(()->
        {
            var record=FirstBattleSavedData.get(level).active;
            if(record!=null&&(entity.getUUID().equals(record.eva)||entity.getUUID().equals(record.angel)))return;
            double ground=actor.firstBattleSignals().spec(entity).origin().y;entity.setPos(entity.getX(),ground,entity.getZ());
            if(entity instanceof EvaUnit01Entity eva)eva.endFirstBattle();else if(entity instanceof SachielEntity angel)angel.recoverFirstBattle();
            ProjectSeele.LOGGER.info("R10 FIRST BATTLE recovered orphan actor {}",entity.getUUID());
        });
    }
    private FirstBattleDirector() {}
}

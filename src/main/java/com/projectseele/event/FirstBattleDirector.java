package com.projectseele.event;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
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
        if(!review&&(com.projectseele.entity.EvaCombatR31.active(eva)
                ||com.projectseele.entity.CombatFeelR31.restrained(eva)||com.projectseele.entity.CombatFeelR31.restrained(angel)))return false;
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
        // Every Sachiel fight that meets the conditions below ends this way, not only a pilot's first: Enter skips
        // the scene for a pilot who has seen it. (completedPilots still records who has finished it.)
        Vec3 delta=angel.position().subtract(eva.position());double distance=delta.horizontalDistance();
        if(!review&&angel.getHealth()>angel.getMaxHealth()*.32F)return false;
        var spec=sceneAt(eva,angel,eva.position());
        if(!review&&(!stableSupport(eva)||distance<14||distance>46||Math.abs(delta.y)>4||!spaceReady(level,eva,spec,FLOOR_STEP)))
        {
            // R65 (playtest 2, item 16): in the raised city a fight goes on between buildings, beside kerbs and
            // kiosks, and a Unit steps onto their roofs; the scene seldom fits where the Unit stands. It is then laid
            // where it fits on a line through Sachiel (sceneOrigin). The Unit is put there on the scene's first
            // frame, as the scene's own camera cuts in; Sachiel is carried from where it stands, as before. A Unit
            // far off, high up or falling is not taken, and the search is made at most once a second for an Angel.
            if(distance>STAGE_REACH||Math.abs(delta.y)>STAGE_RISE||Math.abs(eva.getY()-eva.yo)>.5)return false;
            long now=level.getGameTime();Long tried=STAGED.get(angel);
            if(tried!=null&&now-tried<20)return false;
            STAGED.put(angel,now);
            Vec3 staged=sceneOrigin(eva,angel,FLOOR_STEP);
            // The raised city's streets are seldom clear even so: then the scene may overlap the street's furniture
            // under the knees (STREET_CLUTTER), where the Unit stands or on a line through Sachiel.
            if(staged==null&&stableSupport(eva)&&distance>=14&&distance<=46&&Math.abs(delta.y)<=4&&spaceReady(level,eva,spec,STREET_CLUTTER))staged=eva.position();
            if(staged==null)staged=sceneOrigin(eva,angel,STREET_CLUTTER);
            if(staged==null)return false;
            spec=sceneAt(eva,angel,staged);
        }
        var record=new FirstBattleSavedData.Encounter();record.eva=eva.getUUID();record.angel=angel.getUUID();record.pilot=pilot.getUUID();record.npcPilot=occupant instanceof com.projectseele.entity.TrainingPilotEntity?occupant.getUUID():null;record.spec=spec;record.originalField=angel.getAtField();record.originalHealth=angel.getHealth();data.active=record;data.setDirty();
        eva.beginFirstBattle(spec,angel.getId());angel.beginFirstBattle(spec,eva.getId());
        tickets(level,record);pilot.displayClientMessage(Component.translatable("message.projectseele.first_battle.autonomous"),true);
        com.projectseele.world.NervStaffDialogue.say(pilot,"赤木律子 · 指挥通信","ops.projectseele.first.autonomous_radio");
        sound(level,FirstBattleClip.point(spec,true,"eye_blocks",0),ModSounds.EVA_BERSERK_ROAR.get(),2.3F);
        ProjectSeele.LOGGER.info("R10 FIRST BATTLE START hero={} angel={} pilot={} health={}",record.eva,record.angel,record.pilot,record.originalHealth);return true;
    }
    /** The scene laid with Unit-01 at this place, facing Sachiel. */
    private static FirstBattleSignals.Spec sceneAt(EvaUnit01Entity eva,SachielEntity angel,Vec3 origin)
    {
        Vec3 delta=angel.position().subtract(origin);
        return new FirstBattleSignals.Spec(origin,(float)Math.toDegrees(Math.atan2(-delta.x,delta.z)),eva.getYRot(),angel.getYRot(),
                (float)delta.horizontalDistance(),(float)delta.y);
    }
    /**
     * R65 (playtest 2, item 16): where the scene fits when it does not where the Unit stands. It needs a clear lane
     * 20 blocks wide and 80 high from Unit-01's place to some 77 ahead (Unit-01 lunges about 70 forward, and Sachiel
     * is held 50 to 67 ahead). The raised city's streets are about 22 wide between its blocks, so such a lane runs
     * along a street and seldom across one. The scene is laid on a line through Sachiel: 24 headings, every 15
     * degrees, with Unit-01 52, 40 or 30 blocks from Sachiel on it (52 is where the clip holds Sachiel, which then
     * is not carried). The places are taken nearest to where the Unit stands first. A lane with a building standing
     * in it (by the height map, furniture a Unit walks through aside) is passed over at once; the first that passes
     * spaceReady from step over the floor and whose camera is clear (cameraClear) is the scene's, else the first
     * that passes spaceReady. At most SCENE_TRIES are measured in full in one search. Null when none fits.
     */
    public static Vec3 sceneOrigin(EvaUnit01Entity eva,SachielEntity angel,double step)
    {
        if(!(eva.level() instanceof ServerLevel level))return null;
        Vec3 home=angel.position();
        var places=new ArrayList<Vec3>();
        for(double reach:SCENE_REACH)for(int k=0;k<24;k++)
        {
            double a=Math.toRadians(k*15);places.add(home.add(Math.cos(a)*reach,0,Math.sin(a)*reach));
        }
        places.sort(Comparator.comparingDouble(c->c.distanceToSqr(eva.getX(),home.y,eva.getZ())));
        int measured=0;Vec3 framed=null;
        for(Vec3 place:places)
        {
            var at=net.minecraft.core.BlockPos.containing(place);if(!level.hasChunkAt(at))continue;
            Double floor=null;
            for(int y=at.getY()+4;y>=at.getY()-6;y--)
            {
                var pos=new net.minecraft.core.BlockPos(at.getX(),y,at.getZ());var shape=level.getBlockState(pos).getCollisionShape(level,pos);
                if(!shape.isEmpty()){floor=y+shape.max(net.minecraft.core.Direction.Axis.Y);break;}
            }
            if(floor==null||Math.abs(floor-home.y)>4)continue;
            Vec3 origin=new Vec3(place.x,floor,place.z);
            var spec=sceneAt(eva,angel,origin);
            if(laneBlocked(level,eva,spec,step))continue;
            if(!level.noCollision(eva,eva.getBoundingBox().move(origin.subtract(eva.position())).deflate(.05)))continue;
            if(spaceReady(level,eva,spec,step))
            {
                if(cameraClear(level,eva,spec))return origin;
                if(framed==null)framed=origin;
            }
            if(++measured>=SCENE_TRIES)return framed;
        }
        return framed;
    }
    /**
     * Whether the scene's own camera sees its target in every second of the scene, from where the clip puts it.
     * In the raised city a lane between buildings may have room for the bodies while the camera, authored for open
     * ground, stands behind a building; it is then pulled in to the wall and the bodies are behind a corner.
     */
    private static boolean cameraClear(ServerLevel level,EvaUnit01Entity eva,FirstBattleSignals.Spec spec)
    {
        for(float t=1.2F;t<FirstBattleClip.RETURN_TICK/20F;t+=1)
        {
            var shot=FirstBattleClip.camera(spec,t);
            var hit=level.clip(new net.minecraft.world.level.ClipContext(shot.target(),shot.position(),net.minecraft.world.level.ClipContext.Block.COLLIDER,
                    net.minecraft.world.level.ClipContext.Fluid.NONE,eva));
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)return false;
        }
        return true;
    }
    /** Unit-01's distances from Sachiel tried by sceneOrigin, and how many places it measures in full. */
    private static final double[] SCENE_REACH={52,40,30};
    private static final int SCENE_TRIES=8;
    /**
     * Whether the height map shows something standing in the boxes spaceReady measures (a five by five grid of
     * columns in each): a column topped more than step and less than 80 over the scene's floor, by a block a Unit
     * does not walk through. A cheap first look: what it passes, spaceReady measures.
     */
    private static boolean laneBlocked(ServerLevel level,EvaUnit01Entity eva,FirstBattleSignals.Spec spec,double step)
    {
        double floor=spec.origin().y;
        for(float t:SPACE_TIMES)for(boolean hero:new boolean[]{true,false})for(int i=-2;i<=2;i++)for(int j=-2;j<=2;j++)
        {
            Vec3 c=FirstBattleClip.point(spec,hero,"root_blocks",t);double half=(hero?8.5:10)*.5;
            int x=net.minecraft.util.Mth.floor(c.x+i*half),z=net.minecraft.util.Mth.floor(c.z+j*half);
            int top=level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING,x,z)-1;
            if(top<floor+step||top>floor+80)continue;
            var pos=new net.minecraft.core.BlockPos(x,top,z);var state=level.getBlockState(pos);
            var shape=state.getCollisionShape(level,pos);
            if(!shape.isEmpty()&&!EvaObstacleCollision.ignores(eva,state,pos,shape))return true;
        }
        return false;
    }
    /** How far off (blocks, flat) and how far over or under Sachiel a Unit may be for the scene to be laid elsewhere. */
    private static final double STAGE_REACH=60,STAGE_RISE=24;
    /** When the scene was last searched for an Angel (game time). */
    private static final Map<SachielEntity,Long> STAGED=new WeakHashMap<>();
    /**
     * R65 (playtest 2, item 16): measured in the raised city, every finale was refused here. The vertical speed is
     * what the Unit moved in the tick: a Unit its pilot drives is moved by the pilot's client, and the server's own
     * velocity is not its motion (one standing still on the road read -0.41 for as long as it stood). And the floor
     * may be a block under the probes: a Unit standing on a kerb with its middle over the road is standing.
     */
    public static boolean stableSupport(EvaUnit01Entity eva)
    {
        double velocity=eva.getY()-eva.yo,gravity=eva.getAttributeValue(net.minecraftforge.common.ForgeMod.ENTITY_GRAVITY.get());
        if(velocity>.2||velocity<-(gravity+.07))return false;
        // Ridden actors are movement-authoritative on the pilot's client; a
        // stationary vehicle can have a stale server onGround bit. Require
        // actual nearby floor in three of five small sole-area probes.
        int supported=0;double x=eva.getX(),y=eva.getY(),z=eva.getZ();
        for(double[] offset:new double[][]{{0,0},{-3,0},{3,0},{0,-2},{0,2}})
        {
            AABB sole=new AABB(x+offset[0]-.6,y-SOLE_REACH,z+offset[1]-.6,x+offset[0]+.6,y+.005,z+offset[1]+.6);
            if(eva.level().getBlockCollisions(eva,sole).iterator().hasNext())supported++;
        }
        return supported>=3;
    }
    /** How far under the feet a sole probe finds floor (blocks). */
    private static final double SOLE_REACH=1.1;
    /**
     * R65: the finale's bodies stand in what is lower than this over the scene's floor (kerbs, planters, steps):
     * under the ankles of a 48-block Unit. The raised city's kerbs line every pavement, and as the lowest block of
     * the space they refused every finale beside one.
     */
    private static final double FLOOR_STEP=2.05;
    /**
     * R65: what the scene may overlap when no place near Sachiel is clear but for kerbs: the street's furniture lower
     * than this over the floor (awnings and canopies about 7 up, kiosks, lamps, young trees), under the knees of a
     * 60-block Unit. Measured on the R65 world around the Sachiel operation's street: within 120 blocks, three
     * places are clear but for kerbs (the nearest 80 off); with this, 474 are (the nearest 16 off).
     */
    private static final double STREET_CLUTTER=12;
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
            if(!spaceReady(level,eva,spec,FLOOR_STEP))continue;
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
    /** The scene's moments (seconds) whose bodies spaceReady measures. */
    private static final float[] SPACE_TIMES={0,5,9.2F,10.7F,11.7F,15,19.4F,23};
    /** Whether the scene's bodies have free air, from step over the scene's floor (FLOOR_STEP or STREET_CLUTTER) up. */
    private static boolean spaceReady(ServerLevel level,EvaUnit01Entity eva,FirstBattleSignals.Spec spec,double step)
    {
        for(float t:SPACE_TIMES)for(boolean hero:new boolean[]{true,false})
        {
            Vec3 p=FirstBattleClip.point(spec,hero,"root_blocks",t);double half=hero?8.5:10;
            // During the ground grapple the root pivot lies below the floor;
            // the folded skeleton has a compensating authored root offset.
            // Only the body above the reviewed contact plane needs free air.
            double bottom=Math.max(spec.origin().y+step,p.y+.15);
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
        // A blow between sixty-metre bodies: a burst at the contact and the
        // ground thrown up under it. Sent forced: the pilot's camera sits in
        // the head, beyond the 32-block reach of an ordinary particle packet.
        var ground=level.getBlockState(net.minecraft.core.BlockPos.containing(p.x,p.y-1,p.z));
        for(ServerPlayer viewer:level.players())
        {
            if(viewer.distanceToSqr(p)>200*200)continue;
            level.sendParticles(viewer,new BlockParticleOption(ParticleTypes.BLOCK,(bone?Blocks.QUARTZ_BLOCK:Blocks.REDSTONE_BLOCK).defaultBlockState()),true,p.x,p.y,p.z,30,1.4,.6,1.4,.25);
            level.sendParticles(viewer,ParticleTypes.EXPLOSION,true,p.x,p.y,p.z,3,1.6,1.2,1.6,0);
            level.sendParticles(viewer,ParticleTypes.CLOUD,true,p.x,p.y,p.z,36,2.2,1.4,2.2,.32);
            level.sendParticles(viewer,new BlockParticleOption(ParticleTypes.BLOCK,(bone?Blocks.BONE_BLOCK:Blocks.REDSTONE_BLOCK).defaultBlockState()),true,p.x,p.y,p.z,60,2.6,1.6,2.6,.6);
            if(!ground.isAir())level.sendParticles(viewer,new BlockParticleOption(ParticleTypes.BLOCK,ground),true,p.x,p.y,p.z,80,4.5,.5,4.5,.45);
            level.sendParticles(viewer,ParticleTypes.CAMPFIRE_COSY_SMOKE,true,p.x,p.y+1,p.z,8,3,1,3,.02);
        }
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.START)return;
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
                if(record.age==FirstBattleClip.eventTick(19)||record.age==FirstBattleClip.eventTick(122)||record.age==FirstBattleClip.eventTick(410)||record.age==FirstBattleClip.eventTick(428))
                    sound(level,FirstBattleClip.point(record.spec,true,record.age==FirstBattleClip.eventTick(19)||record.age==FirstBattleClip.eventTick(410)?"foot_l_blocks":"foot_r_blocks",seconds),ModSounds.EVA_FOOT_CONCRETE.get(),1.5F);
                if(record.age==FirstBattleClip.eventTick(28)||record.age==FirstBattleClip.eventTick(53)||record.age==FirstBattleClip.eventTick(75))sound(level,field,ModSounds.EVA_AT_PRESSURE.get(),1.3F);
                if(record.age==FirstBattleClip.eventTick(99))sound(level,field,ModSounds.EVA_AT_TEAR.get(),1.8F);
                // Field rupture is a tear/contact cue. The cross belongs only
                // to Sachiel's final self-destruction, not this earlier hit.
                if(record.age==FirstBattleClip.eventTick(160)){Vec3 p=FirstBattleClip.point(record.spec,false,"hand_r_blocks",seconds);sound(level,p,ModSounds.EVA_ARMOR_IMPACT.get(),1.5F);chips(level,p,true);}
                if(record.age==FirstBattleClip.eventTick(184)){Vec3 p=FirstBattleClip.point(record.spec,true,"foot_l_blocks",seconds);sound(level,p,ModSounds.EVA_IMPACT.get(),1.8F);chips(level,p,false);}
                if(record.age==FirstBattleClip.landingTick())sound(level,eva.position(),ModSounds.EVA_LAND.get(),2.1F);
                if(record.age==FirstBattleClip.eventTick(208)&&FirstBattleClip.hasCurve(false,"waist_blocks")){Vec3 p=FirstBattleClip.point(record.spec,false,"waist_blocks",seconds);sound(level,p,ModSounds.EVA_IMPACT.get(),2.0F);chips(level,p,false);}
                if(record.age==FirstBattleClip.eventTick(307)||record.age==FirstBattleClip.eventTick(267)||record.age==FirstBattleClip.eventTick(295)){Vec3 p=FirstBattleClip.poundCore(record.spec,seconds);sound(level,p,record.age==FirstBattleClip.eventTick(307)?ModSounds.EVA_ARMOR_IMPACT.get():ModSounds.EVA_IMPACT.get(),1.6F);chips(level,p,true);}
                if(record.age==FirstBattleClip.eventTick(255)||record.age==FirstBattleClip.eventTick(283)||record.age==FirstBattleClip.eventTick(321))
                {
                    Vec3 p=FirstBattleClip.poundCore(record.spec,seconds);sound(level,p,record.age==FirstBattleClip.eventTick(321)?ModSounds.EVA_CORE_BREAK.get():ModSounds.EVA_IMPACT.get(),1.8F);chips(level,p,record.age==FirstBattleClip.eventTick(321));
                    if(angel!=null)angel.setHealth(Math.max(1,record.originalHealth*(record.age==FirstBattleClip.eventTick(255)?.6F:record.age==FirstBattleClip.eventTick(283)?.25F:.05F)));
                }
                if(record.age==FirstBattleClip.eventTick(354))sound(level,FirstBattleClip.point(record.spec,false,"core_blocks",seconds),ModSounds.EVA_AT_PRESSURE.get(),1.6F);
                if(record.age>=FirstBattleClip.DEATH_TICK&&!record.deathResolved)finishAngel(level,data,eva,angel,pilot);
                if(record.age>=FirstBattleClip.DURATION_TICKS)
                {
                    TvCampaignDirector.firstBattleComplete(level,data.missionOwner==null?record.pilot:data.missionOwner,record.angel);
                    eva.completeFirstBattle();if(angel!=null)angel.endFirstBattle();
                    publishControlReturn(level,eva,pilot);if(angel!=null)publishState(level,angel,pilot);
                    data.completedPilots.add(pilot.getUUID());data.active=null;data.missionOwner=null;data.missionAngel=null;release(level);
                    pilot.displayClientMessage(Component.translatable(eva.isPowerDepleted() ? "ops.projectseele.first.return_control.yes" : "ops.projectseele.first.return_control.no"),true);ProjectSeele.LOGGER.info("R10 FIRST BATTLE COMPLETE hero={} pilot={}",eva.getUUID(),pilot.getUUID());
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
        // Every player in the dimension sees the finale, not only those near the battle.
        com.projectseele.network.SeeleNetwork.CHANNEL.send(net.minecraftforge.network.PacketDistributor.DIMENSION.with(level::dimension),finale);
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

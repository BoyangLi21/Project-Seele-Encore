package com.projectseele.visual;

import com.google.gson.*;
import com.mojang.authlib.GameProfile;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.physics.*;
import com.projectseele.network.CombatBundleGateR44;
import com.projectseele.registry.ModEntities;
import com.projectseele.registry.ModItems;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.Connection;
import net.minecraft.network.ConnectionProtocol;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.entity.*;
import net.minecraft.world.entity.ai.attributes.Attributes;
import net.minecraft.world.level.GameRules;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraft.core.BlockPos;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.entity.player.PlayerEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import io.netty.channel.embedded.EmbeddedChannel;
import org.joml.Vector3f;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;

/** Production native query/damage APIs in a dedicated, disposable fixture world. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class CombatQueryNativeR44
{
    public static final String WORLD="SEELE_R44_COMBAT_QUERY_QA",TAG="seele_r44_query_fixture";
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44CombatQueryReview");
    private static final JsonArray CASES=new JsonArray();
    private static final int PLANNED_CASES=66;
    private static final Map<BlockPos,BlockState> WALL_BLOCKS=new LinkedHashMap<>();
    private static final List<Entity> OWNED_ACTORS=new ArrayList<>();
    private static final Set<net.minecraft.world.level.ChunkPos> OWNED_CHUNKS=new LinkedHashSet<>();
    private static final JsonObject INDEX_CALIBRATION=new JsonObject();
    private static final Vec3 ORIGIN=new Vec3(18000.5,160,18000.5);
    private static boolean done;
    private static int readyTick=-1;
    private static EvaUnit01Entity coldActor;
    private static ServerLevel level;
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()<60)return;
        MinecraftServer server=event.getServer();safe(server);level=server.overworld();
        if(readyTick<0)
        {
            coldActor=eva(0,ORIGIN);INDEX_CALIBRATION.add("cold",indexWitness(coldActor,bone(coldActor,"head")));
            var center=new net.minecraft.world.level.ChunkPos(BlockPos.containing(ORIGIN));
            for(int x=-8;x<=8;x++)for(int z=-8;z<=8;z++)
            {
                var chunk=new net.minecraft.world.level.ChunkPos(center.x+x,center.z+z);
                if(!level.getForcedChunks().contains(chunk.toLong())){level.setChunkForced(chunk.x,chunk.z,true);OWNED_CHUNKS.add(chunk);}
                level.getChunk(chunk.x,chunk.z);
            }
            // Loaded blocks and query-visible entity sections are different
            // lifecycles. Let the real server promote these tickets first.
            readyTick=server.getTickCount()+40;return;
        }
        if(server.getTickCount()<readyTick)return;
        INDEX_CALIBRATION.add("hot",indexWitness(coldActor,bone(coldActor,"head")));done=true;
        level.getGameRules().getRule(GameRules.RULE_MOBGRIEFING).set(false,server);
        try
        {
            for(int rig=0;rig<5;rig++)spatial(rig);
            for(String path:new String[]{"jab","cross","heavy","knife_forward","knife_reverse","kick","eva_rifle","eva_cannon","un_eye","player_rifle",
                    "shamshel_whip","ramiel_beam","ramiel_drill","zeruel_paper","zeruel_eye","strategic_blast","native_explosion"})damage(path);
            handshake(server);
        }
        catch(Exception failure){record("suite_setup","native_API",false,failure.toString());}
        finally{cleanup();for(var chunk:OWNED_CHUNKS)level.setChunkForced(chunk.x,chunk.z,false);OWNED_CHUNKS.clear();write(server);}
    }
    private static void safe(MinecraftServer server)
    {
        if(!server.getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals(WORLD)||!"127.0.0.1".equals(server.getLocalIp()))
            throw new IllegalStateException("Combat native QA refuses an owner, integrated, or non-local world");
    }
    private static EvaUnit01Entity eva(int rig,Vec3 position)
    {
        EvaUnit01Entity e=(rig==0?ModEntities.EVA_UNIT00.get():rig==2?ModEntities.EVA_UNIT02.get():rig>=3?ModEntities.EVA_PROTOTYPE.get():ModEntities.EVA_UNIT01.get()).create(level);
        if(e==null)throw new IllegalStateException("Fixture actor factory");if(e instanceof EvaPrototypeEntity un)un.setUNSerial(rig-3);
        CompoundTag tag=new CompoundTag();e.saveWithoutId(tag);tag.putBoolean("SeeleEntryPlugInserted",true);tag.putInt("SeelePowerTicks",6000);
        tag.putInt("SeeleActivationTicks",0);tag.putBoolean("SeeleNervLogisticsLocked",false);tag.putInt("R30Shutdown",0);e.load(tag);
        e.addTag(TAG);e.setNoAi(true);e.setNoGravity(true);e.moveTo(position.x,position.y,position.z,0,0);e.setOnGround(true);
        e.getAttribute(Attributes.MAX_HEALTH).setBaseValue(10000);e.getAttribute(Attributes.ARMOR).setBaseValue(0);e.setHealth(10000);
        signal(e,EvaUnit01Entity.class,"DATA_AT_ON",false);signal(e,EvaUnit01Entity.class,"DATA_ACTIVATION_TICKS",0);
        if(!level.addFreshEntity(e))throw new IllegalStateException("Fixture actor spawn rejected");OWNED_ACTORS.add(e);EvaShutdownR30.clear(e);return e;
    }
    private static <T extends LivingEntity> T add(T e,Vec3 point)
    {
        if(e==null)throw new IllegalStateException("Fixture Angel factory");e.addTag(TAG);e.setNoGravity(true);if(e instanceof Mob mob)mob.setNoAi(true);
        e.moveTo(point.x,point.y,point.z,0,0);if(!level.addFreshEntity(e))throw new IllegalStateException("Fixture Angel spawn rejected");OWNED_ACTORS.add(e);return e;
    }
    private static Vec3 bone(EvaUnit01Entity e,String name)
    {
        var p=EvaBodyPose.sample(e,0);var v=p.matrix(name).transformPosition(new Vector3f(p.rig.get(name).pivot())).mul(EvaScale.RENDER_SCALE)
                .rotateY((float)Math.toRadians(180-e.getYRot()));return e.position().add(v.x,v.y,v.z);
    }
    private static void spatial(int rig)
    {
        for(String name:new String[]{"head","chest","feet","gap","crouch_chest","prone_head","wall","nearest_giant"})
        {
            cleanup();try
            {
                var target=eva(rig,ORIGIN);String part=name.equals("feet")?"foot_l":name.contains("head")?"head":"torso_upper";
                if(name.equals("crouch_chest")||name.equals("prone_head"))
                {float stance=name.startsWith("prone")?3:1;signal(target,EvaUnit01Entity.class,"DATA_RIFLE_STANCE",stance);signal(target,EvaUnit01Entity.class,"DATA_PRONE",stance==3);signal(target,EvaUnit01Entity.class,"DATA_CROUCHING",stance==1);target.refreshDimensions();}
                Vec3 point=name.equals("gap")?ORIGIN.add(0,8,0):bone(target,part),from=point.add(0,0,-80),to=point.add(0,0,80);
                if(name.equals("wall"))
                {
                    BlockPos start=BlockPos.containing(point.add(0,0,-35));
                    for(int x=-18;x<=18;x++)for(int y=-4;y<=4;y++)
                    {BlockPos p=start.offset(x,y,0);if(!level.getBlockState(p).isAir()||level.getBlockEntity(p)!=null)throw new IllegalStateException("QA wall mask is not empty: "+p);WALL_BLOCKS.put(p,level.getBlockState(p));level.setBlock(p,Blocks.STONE.defaultBlockState(),2);}
                    var wall=level.clip(new net.minecraft.world.level.ClipContext(from,to,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,target));
                    to=wall.getLocation();var hit=CombatEntityQueryR44.ray(level,from,to,.3,e->e.getTags().contains(TAG));
                    record("rig_"+rig+"_wall","native_block_then_ray",hit==null,"wall="+wall.getType());
                    restoreWall();continue;
                }
                if(name.equals("nearest_giant"))
                {
                    var blocker=eva((rig+1)%5,ORIGIN.add(0,0,-40));var hit=CombatEntityQueryR44.ray(level,from,to,.3,e->e.getTags().contains(TAG));
                    record("rig_"+rig+"_nearest_giant","native_ray",hit!=null&&hit.getEntity()==blocker,"actual="+(hit==null?"none":hit.getEntity().getUUID()));continue;
                }
                var hit=CombatEntityQueryR44.ray(level,from,to,.3,e->e==target);
                boolean oldBox=target.getBoundingBox().inflate(.3).clip(from,to).isPresent();boolean pass=name.equals("gap")?oldBox&&hit==null:hit!=null&&hit.getEntity()==target;
                record("rig_"+rig+"_"+name,"native_pose_ray",pass,"oldBBox="+oldBox+" actual="+(hit==null?"none":hit.getLocation())+"; index="+indexWitness(target,point));
            }
            catch(Exception failure){record("rig_"+rig+"_"+name,"native_pose_ray",false,cause(failure));}
            finally{restoreWall();}
        }
    }
    private static void damage(String path)
    {
        cleanup();try
        {
            var actor=eva(path.equals("un_eye")?3:1,ORIGIN);var target=eva(0,ORIGIN.add(0,0,40));
            ServerPlayer pilot=FakePlayerFactory.get(level,new GameProfile(UUID.nameUUIDFromBytes((TAG+path).getBytes(java.nio.charset.StandardCharsets.UTF_8)),"R44QueryPilot"));
            pilot.moveTo(ORIGIN.x,ORIGIN.y+3,ORIGIN.z-10,0,0);float before=target.getHealth();Object[] extra={};
            if(path.equals("jab")||path.equals("cross")||path.equals("heavy"))
            {
                signal(actor,EvaUnit01Entity.class,"DATA_WEAPON",EvaUnit01Entity.WEAPON_FISTS);signal(actor,EvaUnit01Entity.class,"DATA_ORDINARY_ATTACK_STAGE",path.equals("heavy")?-1:path.equals("cross")?1:0);
                signal(actor,EvaUnit01Entity.class,"DATA_HEAVY_ACTIVE",path.equals("heavy"));String name=path.equals("heavy")?"heavy":path;
                signal(actor,EvaUnit01Entity.class,"DATA_LIVE_ACTION_PHASE",EvaGameplayMotionR32.contactPhase(actor,name));
                Vec3 contact=EvaGameplayMotionR32.hand(actor,EvaGameplayMotionR32.side(actor,name),0);placeAtHead(target,contact);
                invoke(actor,"gameplayContactR32",new Class<?>[]{LivingEntity.class,String.class,boolean.class},pilot,name,path.equals("heavy"));
            }
            else if(path.startsWith("knife"))
            {
                boolean reverse=path.endsWith("reverse");signal(actor,EvaUnit01Entity.class,"DATA_WEAPON",EvaUnit01Entity.WEAPON_KNIFE);
                signal(actor,EvaUnit01Entity.class,"DATA_KNIFE_TYPE",reverse?1:0);set(actor,"knifeReverseMotion",reverse);
                signal(actor,EvaUnit01Entity.class,"DATA_LIVE_ACTION_PHASE",EvaGameplayMotionR32.contactPhase(actor,path));
                placeAtHead(target,EvaGameplayMotionR32.contact(actor,path,0));invoke(actor,"resolveKnifeContact",new Class<?>[]{LivingEntity.class},pilot);
            }
            else if(path.equals("kick"))
            {
                signal(actor,EvaUnit01Entity.class,"DATA_WEAPON",EvaUnit01Entity.WEAPON_FISTS);signal(actor,EvaUnit01Entity.class,"DATA_KICK_ACTIVE",true);
                signal(actor,EvaUnit01Entity.class,"DATA_LIVE_ACTION_PHASE",EvaGameplayMotionR32.contactPhase(actor,"kick"));placeAtHead(target,EvaGameplayMotionR32.contact(actor,"kick",0));
                invoke(actor,"resolveSideKickContact",new Class<?>[]{LivingEntity.class},pilot);
            }
            else if(path.equals("eva_rifle"))
            {
                if(!actor.boardFromExternalPlug(pilot,100))throw new IllegalStateException("Normal fake-pilot boarding refused");
                signal(actor,EvaUnit01Entity.class,"DATA_ACTIVATION_TICKS",0);signal(actor,EvaUnit01Entity.class,"DATA_WEAPON",EvaUnit01Entity.WEAPON_RIFLE);signal(actor,EvaUnit01Entity.class,"DATA_RIFLE_READY",1F);
                var gun=EvaRifleKinematics.sample(actor,0,new Vec3(0,0,1));placeAtHead(target,gun.muzzle().add(gun.forward().scale(75)));actor.fireRifle(pilot);
            }
            else if(path.equals("eva_cannon"))
            {
                signal(actor,EvaUnit01Entity.class,"DATA_WEAPON",EvaUnit01Entity.WEAPON_CANNON);Vec3 from=(Vec3)invoke(actor,"cannonMuzzlePosition",new Class<?>[]{Vec3.class},new Vec3(0,0,1));placeAtHead(target,from.add(0,0,75));
                var active=activeCraters();var prior=new ArrayList<>(active);
                try{invoke(actor,"fireCannon",new Class<?>[]{ServerLevel.class,ServerPlayer.class},level,pilot);}
                finally{active.removeIf(task->!prior.contains(task));}
            }
            else if(path.equals("un_eye"))
            {var un=(EvaPrototypeEntity)actor;placeAtHead(target,EvaUNOptics.eye(un,0).add(0,0,75));invoke(un,"fireEyeLaser",new Class<?>[]{ServerPlayer.class},pilot);}
            else if(path.equals("player_rifle"))
            {
                // This path uses a pedestrian's rifle. The unused EVA would
                // correctly occlude the target; dedicated occlusion cases
                // above already require the nearer giant to absorb the ray.
                actor.discard();Vec3 point=bone(target,"head");pilot.moveTo(point.x,point.y-pilot.getEyeHeight(),point.z-80,0,0);
                invoke(ModItems.POSITRON_RIFLE.get(),"fire",new Class<?>[]{ServerLevel.class,net.minecraft.world.entity.player.Player.class},level,pilot);
            }
            else if(path.equals("shamshel_whip"))
            {
                var angel=add(ModEntities.SHAMSHEL.get().create(level),ORIGIN);int age=ShamshelWhipMotion.contactStart(0);
                signal(angel,ShamshelEntity.class,"SWEEP",age-1);signal(angel,ShamshelEntity.class,"SIDE",1);signal(angel,ShamshelEntity.class,"YAW",0F);signal(angel,ShamshelEntity.class,"SWEEP_MODE",0);
                var points=ShamshelWhipMotion.points(angel,age,0);placeAtHead(target,points.get(points.size()-2));invoke(angel,"tickSweep",new Class<?>[]{});
            }
            else if(path.equals("ramiel_beam"))
            {var angel=add(ModEntities.RAMIEL.get().create(level),ORIGIN);invoke(angel,"fireBeam",new Class<?>[]{LivingEntity.class},target);}
            else if(path.equals("ramiel_drill"))
            {
                var angel=add(ModEntities.RAMIEL.get().create(level),ORIGIN.add(0,40,0));angel.setTarget(target);
                Class<?> type=Class.forName("com.projectseele.entity.RamielEntity$DrillAttackGoal");Constructor<?> ctor=type.getDeclaredConstructor(RamielEntity.class);ctor.setAccessible(true);Object goal=ctor.newInstance(angel);
                set(goal,"drilling",true);set(goal,"anchor",angel.position());set(goal,"drillTicks",49);
                Vec3 foot=bone(target,"foot_l");target.teleportTo(target.getX()+ORIGIN.x-foot.x,target.getY(),target.getZ()+ORIGIN.z-foot.z);invoke(goal,"tick",new Class<?>[]{});
            }
            else if(path.startsWith("zeruel"))
            {var angel=add(ModEntities.ZERUEL.get().create(level),ORIGIN);target.teleportTo(ORIGIN.x,ORIGIN.y,ORIGIN.z+25);invoke(angel,path.equals("zeruel_eye")?"eyeBeam":"paperArmSweep",path.equals("zeruel_eye")?new Class<?>[]{LivingEntity.class}:new Class<?>[]{LivingEntity.class,Vec3.class},path.equals("zeruel_eye")?new Object[]{target}:new Object[]{target,new Vec3(0,0,1)});}
            else if(path.equals("strategic_blast"))
            {Vec3 point=bone(target,"head").add(0,0,-1);invokeStatic(com.projectseele.fx.StrategicExplosionDirector.class,"applyBlast",new Class<?>[]{ServerLevel.class,Vec3.class,Entity.class,double.class,float.class},level,point,actor,5D,30F);}
            else if(path.equals("native_explosion"))
            {Vec3 point=bone(target,"head").add(0,0,-1);level.explode(actor,point.x,point.y,point.z,3F,Level.ExplosionInteraction.NONE);}
            float damage=before-target.getHealth();record(path,"production_contact_or_weapon_API",damage>0,"health_delta="+damage+"; target_index="+indexWitness(target,bone(target,"head"))+"; phase seeded; real input/timing not inferred");
        }
        catch(Exception failure){record(path,"production_contact_or_weapon_API",false,cause(failure));}
    }
    private static void placeAtHead(EvaUnit01Entity target,Vec3 point)
    {Vec3 head=bone(target,"head"),delta=point.subtract(head);target.teleportTo(target.getX()+delta.x,target.getY()+delta.y,target.getZ()+delta.z);target.setOnGround(true);}
    @SuppressWarnings("unchecked") private static List<Object> activeCraters()throws Exception
    {return (List<Object>)field(com.projectseele.fx.StrategicExplosionDirector.class,"ACTIVE").get(null);}
    private static void handshake(MinecraftServer server)throws Exception
    {
        var expected=com.projectseele.entity.CombatMotionResourcesR44.fingerprints();
        for(String key:new TreeMap<>(expected).keySet())
        {
            ServerPlayer player=null;EmbeddedChannel channel=null;
            try
            {
                player=new ServerPlayer(server,level,new GameProfile(UUID.randomUUID(),"R44Gate"));
                Connection connection=new Connection(PacketFlow.SERVERBOUND);channel=new EmbeddedChannel(connection);connection.setProtocol(ConnectionProtocol.PLAY);
                player.connection=new ServerGamePacketListenerImpl(server,connection,player);connection.setListener(player.connection);
                CombatBundleGateR44.login(new PlayerEvent.PlayerLoggedInEvent(player));var bad=new HashMap<>(expected);bad.put(key,"0".repeat(64));
                CombatBundleGateR44.accept(player,bad);channel.runPendingTasks();
                record("mismatch_"+key,"native_server_handler_embedded_connection",!connection.isConnected(),
                        String.valueOf(connection.getDisconnectedReason())+"; actual separate client is a different denominator");
            }
            catch(Exception failure){record("mismatch_"+key,"native_server_handler_embedded_connection",false,cause(failure));}
            finally{if(player!=null)CombatBundleGateR44.logout(new PlayerEvent.PlayerLoggedOutEvent(player));if(channel!=null)channel.finishAndReleaseAll();}
        }
    }
    private static void restoreWall()
    {if(level!=null)for(var entry:WALL_BLOCKS.entrySet())level.setBlock(entry.getKey(),entry.getValue(),2);WALL_BLOCKS.clear();}
    private static JsonObject indexWitness(EvaUnit01Entity target,Vec3 point)
    {
        Vec3 from=point.add(0,0,-80),to=point.add(0,0,80);JsonObject row=new JsonObject();
        row.addProperty("variant",target.getUnitVariant());row.addProperty("profile",CombatBodyProfiles.key(target));
        row.addProperty("known_entity",level.getEntity(target.getId())==target);row.addProperty("feet_chunk_loaded",level.hasChunkAt(target.blockPosition()));
        row.addProperty("direct_body_hit",CombatBodyContacts.clip(target,from,to,.3).isPresent());
        row.addProperty("coarse_candidate",CombatEntityQueryR44.candidates(level,new AABB(from,to).inflate(.3),e->e==target).contains(target));
        row.addProperty("position",target.position().toString());return row;
    }
    private static void cleanup()
    {
        if(level==null)return;restoreWall();Set<Entity> owned=new LinkedHashSet<>(OWNED_ACTORS);for(var e:level.getAllEntities())if(e.getTags().contains(TAG))owned.add(e);
        for(var e:owned){for(var passenger:new ArrayList<>(e.getPassengers())){passenger.addTag(TAG);passenger.ejectPassengers();passenger.discard();}e.ejectPassengers();e.discard();}
        OWNED_ACTORS.clear();
    }
    private static Field field(Class<?> type,String name)throws Exception
    {for(Class<?> at=type;at!=null;at=at.getSuperclass())try{Field f=at.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(type+" / "+name);}
    private static void set(Object object,String name,Object value)throws Exception{field(object.getClass(),name).set(object,value);}
    @SuppressWarnings({"rawtypes","unchecked"}) private static void signal(Entity entity,Class<?> type,String name,Object value)
    {try{entity.getEntityData().set((net.minecraft.network.syncher.EntityDataAccessor)field(type,name).get(null),value);}catch(Exception failure){throw new IllegalStateException(name,failure);}}
    private static Object invoke(Object object,String name,Class<?>[] types,Object...args)throws Exception
    {for(Class<?> at=object.getClass();at!=null;at=at.getSuperclass())try{Method m=at.getDeclaredMethod(name,types);m.setAccessible(true);return m.invoke(object,args);}catch(NoSuchMethodException ignored){}throw new NoSuchMethodException(name);}
    private static Object invokeStatic(Class<?> type,String name,Class<?>[] types,Object...args)throws Exception
    {Method method=type.getDeclaredMethod(name,types);method.setAccessible(true);return method.invoke(null,args);}
    private static void record(String name,String mode,boolean pass,String detail)
    {JsonObject row=new JsonObject();row.addProperty("case",name);row.addProperty("mode",mode);row.addProperty("passed",pass);row.addProperty("detail",detail);CASES.add(row);}
    private static String cause(Throwable failure)
    {while(failure.getCause()!=null&&failure.getCause()!=failure)failure=failure.getCause();return failure.toString();}
    private static void write(MinecraftServer server)
    {
        try
        {
            int passed=0;for(var entry:CASES)if(entry.getAsJsonObject().get("passed").getAsBoolean())passed++;
            JsonObject result=new JsonObject();result.addProperty("passed",CASES.size()==PLANNED_CASES&&passed==PLANNED_CASES);result.addProperty("planned_total",PLANNED_CASES);result.addProperty("total",CASES.size());result.addProperty("passed_cases",passed);result.add("cases",CASES);
            result.add("fixture_index_calibration",INDEX_CALIBRATION);
            result.addProperty("scope","Native Forge query/contact/weapon APIs and server disconnect handler; phase injection does not verify input, cooldown, animation timing, final GPU pixels or artistic quality");
            result.addProperty("unverified","source=null/TNT explosion scope; real client nine rejection screens; low-stance damage timing; all combat performance");
            Files.writeString(server.getWorldPath(LevelResource.ROOT).resolve("r44_combat_query.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
            ProjectSeele.LOGGER.info("R44 combat native API review: {}/{}",passed,CASES.size());
        }
        catch(Exception failure){throw new IllegalStateException(failure);}
    }
    private CombatQueryNativeR44(){}
}

package com.projectseele.visual;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.physics.CombatDamageTargetsR44;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.*;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.entity.PartEntity;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Disabled normally; real health assertions in a disposable dedicated-server copy. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class VehicleDamageNativeR44
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44VehicleDamageReview");
    private static final Vec3 ORIGIN=new Vec3(32000.5,280,32000.5);
    private static final List<Entity> ACTORS=new ArrayList<>();
    private static final Set<ChunkPos> TICKETS=new LinkedHashSet<>();
    private static final JsonArray RESULTS=new JsonArray();
    private static EvaUnit01Entity attacker;
    private static int ready=-1;
    private static boolean done;
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(!ENABLED||done||event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()<60)return;
        var server=event.getServer();var level=server.overworld();
        if(ready<0)
        {
            try
            {
            var centre=new ChunkPos(BlockPos.containing(ORIGIN));
            for(int x=-3;x<=3;x++)for(int z=-3;z<=3;z++)
            {
                var p=new ChunkPos(centre.x+x,centre.z+z);
                if(!level.getForcedChunks().contains(p.toLong())){level.setChunkForced(p.x,p.z,true);TICKETS.add(p);}
                level.getChunk(p.x,p.z);
            }
            // Let entity sections become query-visible before asserting hits.
            // A production copy already owns its canonical EVA UUID. The
            // attacker only supplies the real strike implementation/source;
            // never join it to the world or alter that ownership contract.
            attacker=ModEntities.EVA_UNIT01.get().create(level);
            if(attacker==null)throw new IllegalStateException("Missing EVA strike fixture");
            Vec3 at=ORIGIN.add(-25,0,0);attacker.moveTo(at.x,at.y,at.z,0,0);
            attacker.setNoAi(true);attacker.setNoGravity(true);
                // Keep the independent rifle target beyond the earlier pig's
                // firing lane; the obstruction case is exercised separately.
                spawn(EntityType.PIG,level,ORIGIN);spawn(EntityType.COW,level,ORIGIN.add(0,0,48));
            var type=BuiltInRegistries.ENTITY_TYPE.get(new ResourceLocation("superbwarfare","t_90a"));
            spawn(type,level,ORIGIN.add(20,0,0));spawn(type,level,ORIGIN.add(40,0,12));
            ready=server.getTickCount()+40;return;
            }
            catch(Exception error)
            {
                done=true;check("fixture_setup_exception",false,error.toString());
                finish(event.getServer(),level);return;
            }
        }
        if(server.getTickCount()<ready)return;
        done=true;
        try
        {
            EvaUnit01Entity eva=attacker;
            var pilot=FakePlayerFactory.getMinecraft(level);var source=level.damageSources().playerAttack(pilot);
            var method=EvaUnit01Entity.class.getDeclaredMethod("strikeZone",LivingEntity.class,AABB.class,float.class,double.class,Vec3.class);
            method.setAccessible(true);
            var field=EvaUnit01Entity.class.getDeclaredField("SMASH_FIST_DAMAGE");field.setAccessible(true);float melee=field.getFloat(null);
            for(int index:new int[]{0,2})
            {
                Entity target=ACTORS.get(index);double before=health(target);Vec3 point=target.getBoundingBox().getCenter();
                method.invoke(eva,pilot,target.getBoundingBox().inflate(.3),melee,0D,point);
                check(index==0?"pig_real_melee":"t90a_real_melee",health(target)<before,"before="+before+" after="+health(target));
            }
            for(int index:new int[]{1,3})
            {
                Entity target=ACTORS.get(index);double before=health(target);Vec3 centre=target.getBoundingBox().getCenter();
                Vec3 from=centre.add(0,0,-30),to=centre.add(0,0,30);
                var hit=CombatDamageTargetsR44.ray(level,from,to,.3,eva,pilot);
                check(index==1?"cow_rifle_ray":"t90a_rifle_ray",hit!=null&&hit.getEntity()==target,"first="+(hit==null?"none":hit.getEntity().getType()));
                if(hit!=null&&hit.getEntity()==target)CombatDamageTargetsR44.hurt(target,source,SeeleConfig.EVA_RIFLE_DAMAGE.get().floatValue(),hit.getLocation(),to.subtract(from).normalize(),CombatDamageTargetsR44.Weapon.PROJECTILE);
                check(index==1?"cow_rifle_health":"t90a_rifle_health",health(target)<before,"before="+before+" after="+health(target));
            }
            Entity tank=ACTORS.get(3);Vec3 centre=tank.getBoundingBox().getCenter();
            // The living animal is farther along the same ray than the hull.
            ACTORS.get(1).moveTo(centre.x,centre.y,centre.z+20,0,0);
            var first=CombatDamageTargetsR44.ray(level,centre.add(0,0,-30),centre.add(0,0,40),.3,eva,pilot);
            check("vehicle_blocks_living_behind",first!=null&&first.getEntity()==tank,"first="+(first==null?"none":first.getEntity().getType()));
            check("self_and_pilot_filtered",!CombatDamageTargetsR44.allowed(eva,eva,pilot)&&!CombatDamageTargetsR44.allowed(pilot,eva,pilot),"self/pilot predicate");
            // Use an actual mounted occupant, not a synthetic root reference.
            Entity occupant=ACTORS.get(1);boolean mounted=occupant.startRiding(tank,true);
            check("mounted_occupant_filtered",mounted&&!CombatDamageTargetsR44.allowed(occupant,eva,pilot),"mounted="+mounted);
            occupant.stopRiding();
            check("multipart_parent_once",CombatDamageTargetsR44.unique(List.of(tank,new FixturePart(tank),new FixturePart(tank)),e->CombatDamageTargetsR44.allowed(e,eva,pilot)).equals(List.of(tank)),"one parent for hull and two parts");
        }
        catch(Exception error){check("fixture_exception",false,error.toString());}
        finally
        {
            finish(server,level);
        }
    }
    private static void finish(net.minecraft.server.MinecraftServer server,ServerLevel level)
    {
            for(Entity actor:ACTORS)
            {
                try{actor.discard();}
                catch(Exception error){check("fixture_cleanup_exception",false,error.toString());}
            }
            for(ChunkPos p:TICKETS)
            {
                try{level.setChunkForced(p.x,p.z,false);}
                catch(Exception error){check("fixture_ticket_cleanup_exception",false,error.toString());}
            }
            JsonObject report=new JsonObject();report.add("cases",RESULTS);
            boolean passed=RESULTS.size()==10;for(var row:RESULTS)passed&=row.getAsJsonObject().get("passed").getAsBoolean();
            report.addProperty("passed",passed);report.addProperty("default_disabled",true);report.addProperty("animation_or_damage_numbers_changed",false);
            try{Files.writeString(server.getWorldPath(LevelResource.ROOT).resolve("r44_vehicle_damage_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));}
            catch(Exception error){ProjectSeele.LOGGER.error("Vehicle damage report write failed",error);}
            ProjectSeele.LOGGER.info("R44 vehicle damage native review: {}",report);
    }
    private static <T extends Entity> T spawn(EntityType<T> type,ServerLevel level,Vec3 position)
    {
        T entity=type.create(level);if(entity==null)throw new IllegalStateException("Missing real fixture "+type);
        entity.moveTo(position.x,position.y,position.z,0,0);entity.setNoGravity(true);
        if(entity instanceof Mob mob)
        {
            mob.setNoAi(true);
            if(!(mob instanceof EvaUnit01Entity))
            {
                mob.getAttribute(net.minecraft.world.entity.ai.attributes.Attributes.MAX_HEALTH).setBaseValue(100);
                mob.setHealth(100);
            }
        }
        if(!level.addFreshEntity(entity))throw new IllegalStateException("Fixture spawn rejected");ACTORS.add(entity);return entity;
    }
    private static double health(Entity target) throws ReflectiveOperationException
    {
        return target instanceof LivingEntity living?living.getHealth():((Number)target.getClass().getMethod("getHealth").invoke(target)).doubleValue();
    }
    private static void check(String id,boolean passed,String detail)
    {
        JsonObject row=new JsonObject();row.addProperty("id",id);row.addProperty("passed",passed);row.addProperty("detail",detail);RESULTS.add(row);
    }
    private static final class FixturePart extends PartEntity<Entity>
    {
        FixturePart(Entity parent){super(parent);}
        @Override protected void defineSynchedData() {}
        @Override protected void readAdditionalSaveData(CompoundTag tag) {}
        @Override protected void addAdditionalSaveData(CompoundTag tag) {}
    }
    private VehicleDamageNativeR44() {}
}

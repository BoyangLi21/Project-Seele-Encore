import com.projectseele.entity.*;
import com.projectseele.registry.ModEntities;
import com.projectseele.world.TvCampaignCatalog;
import com.projectseele.world.FixedCannonCradleR52;
import com.google.common.collect.ImmutableList;
import com.google.gson.JsonParser;
import java.lang.reflect.*;
import java.util.*;
import java.util.function.Supplier;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.syncher.*;
import net.minecraft.world.entity.*;
import net.minecraft.world.level.entity.EntityInLevelCallback;
import net.minecraft.world.phys.*;
import net.minecraftforge.registries.*;
import sun.misc.Unsafe;

/** Isolated JVM memory fixture: production factories and Entity.save/load, no server or world. */
public final class R52ControllerSaveLoadCheck {
    private static Unsafe unsafe; private static int checks;
    private static Field field(Class<?> type,String name)throws Exception {
        for(Class<?> c=type;c!=null;c=c.getSuperclass())try{var f=c.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException absent){}
        throw new NoSuchFieldException(name);
    }
    private static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    private static void eventLists()throws Exception {
        Object cache=field(net.minecraftforge.eventbus.api.EventListenerHelper.class,"listeners").get(null);
        @SuppressWarnings("unchecked") var map=(Map<Class<?>,net.minecraftforge.eventbus.ListenerList>)field(cache.getClass(),"map").get(cache);
        var base=(net.minecraftforge.eventbus.ListenerList)field(net.minecraftforge.eventbus.api.EventListenerHelper.class,"EVENTS_LIST").get(null);
        map.put(net.minecraftforge.eventbus.api.Event.class,base);
        for(String name:new String[]{"net.minecraftforge.network.NetworkEvent","net.minecraftforge.event.level.LevelEvent","net.minecraftforge.event.level.LevelEvent$Unload","net.minecraftforge.event.entity.EntityEvent","net.minecraftforge.event.entity.EntityLeaveLevelEvent"}) {
            Class<?> c=Class.forName(name,false,R52ControllerSaveLoadCheck.class.getClassLoader());map.putIfAbsent(c,new net.minecraftforge.eventbus.ListenerList(map.getOrDefault(c.getSuperclass(),base)));
        }
    }
    @SuppressWarnings("unchecked") private static EntityType<?> actualFactory(RegistryObject<?> id)throws Exception {
        var entries=(Map<RegistryObject<?>,Supplier<?>>)field(DeferredRegister.class,"entries").get(ModEntities.ENTITY_TYPES);
        var registry=BuiltInRegistries.ENTITY_TYPE;var frozen=field(registry.getClass(),"frozen");boolean before=frozen.getBoolean(registry);
        frozen.setBoolean(registry,false);try{return (EntityType<?>)entries.get(id).get();}finally{frozen.setBoolean(registry,before);}
    }
    @SuppressWarnings({"unchecked","rawtypes"}) private static void register(EntityType<?> type,RegistryObject<?> id)throws Exception {
        // Only this isolated JVM's vanilla key map is changed. Production Forge registration remains untouched.
        var registry=BuiltInRegistries.ENTITY_TYPE;Field f=field(registry.getClass(),"frozen"),locked=field(registry.getClass(),"locked");boolean before=f.getBoolean(registry),lockBefore=locked.getBoolean(registry);
        f.setBoolean(registry,false);locked.setBoolean(registry,false);try{Registry.register((Registry)registry,id.getId(),type);}finally{f.setBoolean(registry,before);locked.setBoolean(registry,lockBefore);}
    }
    private static Entity blank(Class<? extends Entity> kind,EntityType<?> type)throws Exception {
        Entity e=(Entity)unsafe.allocateInstance(kind);
        field(Entity.class,"level").set(e,unsafe.allocateInstance(net.minecraft.server.level.ServerLevel.class));
        field(Entity.class,"type").set(e,type);field(Entity.class,"position").set(e,new Vec3(14.5,-442,25.5));
        field(Entity.class,"blockPosition").set(e,net.minecraft.core.BlockPos.containing(e.position()));field(Entity.class,"chunkPosition").set(e,new net.minecraft.world.level.ChunkPos(e.blockPosition()));
        field(Entity.class,"deltaMovement").set(e,Vec3.ZERO);field(Entity.class,"dimensions").set(e,EntityDimensions.fixed(1,1));
        field(Entity.class,"bb").set(e,new AABB(14,-442,25,15,-441,26));field(Entity.class,"passengers").set(e,ImmutableList.of());
        field(Entity.class,"tags").set(e,new HashSet<String>());field(Entity.class,"levelCallback").set(e,EntityInLevelCallback.NULL);
        e.setUUID(UUID.randomUUID());var data=new SynchedEntityData(e);field(Entity.class,"entityData").set(e,data);
        Map<String,Object> defaults=new LinkedHashMap<>();defaults.put("DATA_SHARED_FLAGS_ID",(byte)0);defaults.put("DATA_AIR_SUPPLY_ID",300);
        defaults.put("DATA_CUSTOM_NAME",Optional.empty());defaults.put("DATA_CUSTOM_NAME_VISIBLE",false);defaults.put("DATA_SILENT",false);
        defaults.put("DATA_NO_GRAVITY",true);defaults.put("DATA_POSE",Pose.STANDING);defaults.put("DATA_TICKS_FROZEN",0);
        for(var item:defaults.entrySet())define(data,(EntityDataAccessor<?>)field(Entity.class,item.getKey()).get(null),item.getValue());
        var method=kind.getDeclaredMethod("defineSynchedData");method.setAccessible(true);method.invoke(e);
        if(kind!=YashimaCannonEntityR52.class)field(kind,kind==NervSiloDoorEntity.class?"savedDeclaredR52":"savedStackR52").set(e,new CompoundTag());
        return e;
    }
    @SuppressWarnings({"unchecked","rawtypes"}) private static void define(SynchedEntityData data,EntityDataAccessor key,Object value){data.define(key,value);}
    private static CompoundTag state(boolean silo,float raw) {
        var spec=new CompoundTag();if(silo){spec.putFloat("OpeningX",33);spec.putFloat("OpeningZ",33);spec.putInt("SeparationSign",-1);spec.putDouble("BeamBottom",-2.02);spec.putBoolean("ServiceColumnPorts",true);}
        else{spec.putFloat("Width",33);spec.putFloat("Height",65);}
        spec.putInt("OpenTicks",100);spec.putInt("CloseTicks",100);spec.putFloat("PreviousRaw",raw-.01F);spec.putFloat("CurrentRaw",raw);spec.putLong("At",71234);
        var row=new CompoundTag();row.putInt("Version",52);row.put("Spec",spec);row.putFloat("Raw",raw);row.putFloat("Target",1);
        row.putInt("Variant",1);row.putInt("Stage",2);row.putFloat("ClockStart",0);row.putFloat("ClockGoal",1);row.putInt("ClockStep",37);row.putInt("ClockDuration",100);
        var tag=new CompoundTag();tag.put(silo?"R52DeclaredHatch":"R52SideStack",row);return tag;
    }
    private static void roundTrip(Class<? extends Entity> kind,EntityType<?> type,boolean silo)throws Exception {
        var original=blank(kind,type);check(!original.shouldBeSaved(),"Legacy transient gate entered entity-section persistence");
        String key=silo?"R52DeclaredHatch":"R52SideStack";var seed=state(silo,.37F);var read=kind.getDeclaredMethod("readAdditionalSaveData",CompoundTag.class);read.setAccessible(true);read.invoke(original,seed);
        check(original.shouldBeSaved(),"Root declared gate excluded from native entity sections");
        var saved=new CompoundTag();check(original.save(saved),"Production Entity.save rejected registered Root controller");
        check(saved.getString("id").equals(silo?"projectseele:nerv_silo_door":"projectseele:nerv_hangar_door"),"Saved exact production registry identity differs");
        check(saved.contains(key)&&saved.getCompound(key).getFloat("Raw")==.37F,"Current source raw sample was not serialized");
        check(saved.getCompound(key).getInt("ClockStep")==37&&saved.getCompound(key).getInt("ClockDuration")==100,"Actual in-flight door clock was lost");
        var decoded=blank(kind,type);decoded.load(saved);check(decoded.getUUID().equals(original.getUUID()),"Native load changed stable declared UUID");
        check(decoded.position().equals(original.position())&&decoded.shouldBeSaved(),"Native load changed physical frame or declaration");
        var again=new CompoundTag();check(decoded.save(again),"Reloaded declared controller cannot be saved again");
        check(again.getCompound(key).equals(saved.getCompound(key)),"Full source/spec/progress/clock NBT changed across native save/load");
        original.remove(Entity.RemovalReason.KILLED);check(!original.shouldBeSaved(),"Removed door resurrected through declared persistence");
    }
    private static void cannonRoundTrip(EntityType<?> type)throws Exception {
        var plan=JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of("D:/eva/artifacts/r52_fresh_from_r51_20261009/encounter_installation/STATION_DESIGN.json"))).getAsJsonObject();
        var original=(YashimaCannonEntityR52)blank(YashimaCannonEntityR52.class,type);
        original.setPos(YashimaCannonGeometryR52.vector(plan.getAsJsonArray("closed_position")));
        original.setUUID(UUID.fromString(plan.get("cannon_uuid").getAsString()));original.configureR52(YashimaCannonGeometryR52.parse(plan));
        original.configureCradleR52(FixedCannonCradleR52.Spec.parse(plan.getAsJsonObject("cradle")));original.loadedR52(true);original.readyR52(true);
        check(original.shouldBeSaved(),"Declared fixed cannon excluded from native entity-section persistence");var saved=new CompoundTag();check(original.save(saved),"64th production controller rejected by Entity.save");
        check(saved.getString("id").equals("projectseele:yashima_cannon_r52"),"Fixed cannon saved registry identity differs");
        var decoded=(YashimaCannonEntityR52)blank(YashimaCannonEntityR52.class,type);decoded.load(saved);
        check(decoded.getUUID().equals(original.getUUID())&&decoded.position().equals(original.position()),"Native fixed cannon reload changed original UUID/frame");
        check(decoded.shouldBeSaved()&&decoded.loadedR52()&&decoded.readyR52(),"Native fixed cannon reload lost loaded/ready state");
        var again=new CompoundTag();check(decoded.save(again),"Reloaded fixed cannon cannot persist");
        for(String key:new String[]{"GunGeometryR52","GunCradleR52","GunAimR52"})check(saved.get(key).equals(again.get(key)),"Native fixed cannon save/load changed "+key);
    }
    public static void main(String[] args)throws Exception {
        net.minecraft.SharedConstants.tryDetectVersion();net.minecraftforge.fml.loading.FMLPaths.loadAbsolutePaths(java.nio.file.Path.of(".Codex/r52_runtime_close/runtime_context").toAbsolutePath());eventLists();
        try{net.minecraft.server.Bootstrap.bootStrap();}catch(ExceptionInInitializerError failure){if(Arrays.stream(failure.getStackTrace()).noneMatch(frame->frame.getClassName().equals("net.minecraftforge.network.NetworkHooks"))||BuiltInRegistries.BLOCK.size()<1000)throw failure;System.out.println("Fixture-only unused untransformed Forge network bootstrap skipped");}
        unsafe=(Unsafe)field(Unsafe.class,"theUnsafe").get(null);
        EntityType<?> silo=actualFactory(ModEntities.NERV_SILO_DOOR),hangar=actualFactory(ModEntities.NERV_HANGAR_DOOR),carrier=actualFactory(ModEntities.NERV_CARRIER_PLATFORM),cannon=actualFactory(ModEntities.YASHIMA_CANNON_R52);
        check(silo.canSerialize()&&hangar.canSerialize()&&carrier.canSerialize()&&cannon.canSerialize(),"Actual production factory still uses type.noSave");register(silo,ModEntities.NERV_SILO_DOOR);register(hangar,ModEntities.NERV_HANGAR_DOOR);register(cannon,ModEntities.YASHIMA_CANNON_R52);
        roundTrip(NervSiloDoorEntity.class,silo,true);roundTrip(NervHangarDoorEntity.class,hangar,false);
        cannonRoundTrip(cannon);
        for(String id:new String[]{"ramiel","gaghiel"}){var c=TvCampaignCatalog.find(id).orElseThrow();check(!c.playable()&&c.briefing().contains("筹备中")&&!TvCampaignCatalog.preparationBlockerR52(id).isEmpty(),"Deferred encounter advertises a playable entry");}
        check(TvCampaignCatalog.find("sachiel").orElseThrow().playable()&&TvCampaignCatalog.find("shamshel").orElseThrow().playable(),"Unrelated playable encounter closed");
        System.out.println("R52 production factory + native Entity.save/load gate regression PASS checks="+checks+"; isolated memory fixture, no game, world, geometry, native cycle or art acceptance");
    }
}

package com.projectseele.entity;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.EnumMap;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.storage.WritableLevelData;
import sun.misc.Unsafe;

/** Executes the production melee/smash queue and expiry methods in a scripted
 * memory context. No game, server thread, world, chunks or animation starts.
 * Native candidate6 must still verify the eventual attack and rendered pose. */
public final class EvaKnifeRecoveryR52Test
{
    private static int checks;
    private static long time=51801;
    private static final UUID PILOT=new UUID(1,52);
    private static Unsafe unsafe;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static final class InputContext extends EvaUnit01Entity
    {
        Level clock; LivingEntity pilot; SynchedEntityData data;
        int weapon=WEAPON_KNIFE; boolean powered=true,alive=true,locked,crouch,prone;
        RecoveryInputStampR51 stamp=new RecoveryInputStampR51(2,1,0);
        private InputContext(){super(null,null);}
        @Override public Level level(){return clock;}
        @Override public SynchedEntityData getEntityData(){return data;}
        @Override public int getWeapon(){return weapon;}
        @Override public LivingEntity getPilotEntity(){return pilot;}
        @Override public boolean isMeleeWeapon(){return weapon==WEAPON_KNIFE||weapon==WEAPON_FISTS;}
        @Override public boolean isPoweredOn(){return powered;}
        @Override public boolean isAlive(){return alive;}
        @Override protected boolean isPilotControlLocked(){return locked;}
        @Override public boolean isPilotCrouching(){return crouch;}
        @Override public boolean isPilotProne(){return prone;}
        @Override public boolean isHeavyMotionActive(){return false;}
        @Override public boolean isVisuallyAirborneForRender(){return false;}
        @Override public java.util.Set<String> getTags(){return java.util.Set.of();}
        @Override RecoveryInputStampR51 recoveryInputStampR51(){return stamp;}
    }
    private static Field field(Class<?> type,String name)throws Exception
    {var f=type.getDeclaredField(name);f.setAccessible(true);return f;}
    private static int integer(InputContext actor,String name)throws Exception
    {return field(EvaUnit01Entity.class,name).getInt(actor);}
    private static void integer(InputContext actor,String name,int value)throws Exception
    {field(EvaUnit01Entity.class,name).setInt(actor,value);}
    private static Method method(String name,Class<?>... parameters)throws Exception
    {var m=EvaUnit01Entity.class.getDeclaredMethod(name,parameters);m.setAccessible(true);return m;}
    @SuppressWarnings({"unchecked","rawtypes"})
    private static InputContext context(int melee,int smash,int active)throws Exception
    {
        InputContext actor=(InputContext)unsafe.allocateInstance(InputContext.class);
        actor.weapon=EvaUnit01Entity.WEAPON_KNIFE;actor.powered=true;actor.alive=true;actor.stamp=new EvaUnit01Entity.RecoveryInputStampR51(2,1,0);
        actor.clock=(ServerLevel)unsafe.allocateInstance(ServerLevel.class);
        var data=Proxy.newProxyInstance(WritableLevelData.class.getClassLoader(),new Class<?>[]{WritableLevelData.class},
                (proxy,m,args)->m.getName().equals("getGameTime")?time: m.getReturnType()==boolean.class?false:m.getReturnType()==int.class?0:null);
        field(Level.class,"levelData").set(actor.clock,data);
        actor.pilot=(ServerPlayer)unsafe.allocateInstance(ServerPlayer.class);
        field(Entity.class,"uuid").set(actor.pilot,PILOT);
        actor.data=new SynchedEntityData(actor);actor.firstBattleSignals().define(actor.data);EvaCombatR31.define(actor.data);
        Class<? extends Enum> queue=(Class<? extends Enum>)Class.forName("com.projectseele.entity.EvaUnit01Entity$LegacyRecoveryQueueR51");
        field(EvaUnit01Entity.class,"legacyRecoveryInputsR51").set(actor,new EnumMap(queue));
        integer(actor,"meleeCooldown",melee);integer(actor,"smashCooldown",smash);integer(actor,"knifeVisualTicks",active);
        integer(actor,"queuedKnifeInput",-1);
        return actor;
    }
    private static EnumMap<?,?> requests(InputContext actor)throws Exception
    {return (EnumMap<?,?>)field(EvaUnit01Entity.class,"legacyRecoveryInputsR51").get(actor);}
    private static long deadline(InputContext actor)throws Exception
    {var row=requests(actor).values().iterator().next();var m=row.getClass().getDeclaredMethod("until");m.setAccessible(true);return (long)m.invoke(row);}
    @SuppressWarnings("unchecked")
    private static void dataOnlyEventLists()throws Exception
    {
        // ModLauncher normally supplies event listener lists through its API
        // transform. Supply only the unused API lists needed to initialize
        // the actual entity classes in this standalone memory replay.
        Object cache=field(net.minecraftforge.eventbus.api.EventListenerHelper.class,"listeners").get(null);
        var map=(java.util.Map<Class<?>,net.minecraftforge.eventbus.ListenerList>)field(cache.getClass(),"map").get(cache);
        var base=(net.minecraftforge.eventbus.ListenerList)field(net.minecraftforge.eventbus.api.EventListenerHelper.class,"EVENTS_LIST").get(null);
        map.put(net.minecraftforge.eventbus.api.Event.class,base);
        for(String name:new String[]{"net.minecraftforge.network.NetworkEvent","net.minecraftforge.event.level.LevelEvent",
                "net.minecraftforge.event.level.LevelEvent$Unload","net.minecraftforge.event.entity.EntityEvent",
                "net.minecraftforge.event.entity.EntityLeaveLevelEvent"})
        {
            Class<?> type=Class.forName(name,false,EvaKnifeRecoveryR52Test.class.getClassLoader());
            map.putIfAbsent(type,new net.minecraftforge.eventbus.ListenerList(map.getOrDefault(type.getSuperclass(),base)));
        }
    }
    public static void main(String[] args)throws Exception
    {
        net.minecraft.SharedConstants.tryDetectVersion();
        net.minecraftforge.fml.loading.FMLPaths.loadAbsolutePaths(java.nio.file.Path.of(".Codex/r52_knife_reinput_fix/runtime_context").toAbsolutePath());
        dataOnlyEventLists();
        try { net.minecraft.server.Bootstrap.bootStrap(); }
        catch(ExceptionInInitializerError failure)
        {
            // The plain mapped Forge API jar lacks ModLauncher's Event class
            // transformer. Its late networking init is unused by this data-
            // only replay; accept only that known failure after vanilla data
            // bootstrap, never a production queue/input failure.
            if(java.util.Arrays.stream(failure.getStackTrace()).noneMatch(frame->frame.getClassName().equals("net.minecraftforge.network.NetworkHooks"))
                    ||net.minecraft.core.registries.BuiltInRegistries.BLOCK.size()<1000)throw failure;
            System.out.println("Data-only test: unused untransformed Forge networking bootstrap skipped");
        }
        var f=field(Unsafe.class,"theUnsafe");unsafe=(Unsafe)f.get(null);
        var light=context(29,0,0);light.meleeAttack((ServerPlayer)light.pilot);
        check(integer(light,"meleeCooldown")==29,"Cancellation replay changed original damage cadence");
        check(integer(light,"meleeInputBufferTicks")==37&&deadline(light)==51838,"Actual melee entry lost the native 29-tick remaining recovery");
        for(int tick=1;tick<=29;tick++)
        {
            time=51801+tick;integer(light,"meleeCooldown",29-tick);
            integer(light,"meleeInputBufferTicks",integer(light,"meleeInputBufferTicks")-1);
            method("expireLegacyRecoveryR51").invoke(light);
            check(requests(light).size()==1&&integer(light,"meleeInputBufferTicks")>0,"Actual expiry discarded the packet before normal cooldown completion");
        }
        check(integer(light,"meleeCooldown")==0&&integer(light,"meleeInputBufferTicks")==8,"Queued actual input is unavailable at normal consumption boundary");
        method("clearLegacyRecoveryR51").invoke(light);
        check(requests(light).isEmpty()&&integer(light,"meleeInputBufferTicks")==0,"Committed action would retain duplicate buffered input");
        time=51900;var reverse=context(0,24,0);reverse.smashAttack((ServerPlayer)reverse.pilot);
        check(integer(reverse,"smashCooldown")==24&&integer(reverse,"queuedKnifeInput")==1&&deadline(reverse)==51932,"RMB recovery input did not use the real smash entry/queue");
        reverse.weapon=EvaUnit01Entity.WEAPON_RIFLE;method("expireLegacyRecoveryR51").invoke(reverse);
        check(requests(reverse).isEmpty()&&integer(reverse,"queuedKnifeInput")==-1,"Weapon change retained unauthorized delayed strike");
        var another=context(29,0,0);another.meleeAttack((ServerPlayer)another.pilot);another.pilot=null;
        method("expireLegacyRecoveryR51").invoke(another);check(requests(another).isEmpty(),"Pilot dismount retained delayed strike");
        var stance=context(29,0,0);stance.meleeAttack((ServerPlayer)stance.pilot);stance.crouch=true;
        method("expireLegacyRecoveryR51").invoke(stance);check(requests(stance).isEmpty(),"Subsequent stance change retained stale input");
        var sequence=context(29,0,0);sequence.meleeAttack((ServerPlayer)sequence.pilot);sequence.stamp=new EvaUnit01Entity.RecoveryInputStampR51(3,1,0);
        method("expireLegacyRecoveryR51").invoke(sequence);check(requests(sequence).isEmpty(),"Another committed attack retained the old sequence input");
        var power=context(29,0,0);power.meleeAttack((ServerPlayer)power.pilot);power.powered=false;
        method("expireLegacyRecoveryR51").invoke(power);check(requests(power).isEmpty(),"Unpowered frame retained attack authority");
        var expired=context(29,0,0);expired.meleeAttack((ServerPlayer)expired.pilot);time=deadline(expired)+1;
        method("expireLegacyRecoveryR51").invoke(expired);check(requests(expired).isEmpty(),"Bounded request never expired");
        time=52000;var ordinary=context(12,0,0);ordinary.weapon=EvaUnit01Entity.WEAPON_FISTS;
        Class<?> queue=Class.forName("com.projectseele.entity.EvaUnit01Entity$LegacyRecoveryQueueR51");
        @SuppressWarnings({"unchecked","rawtypes"}) Object melee=Enum.valueOf((Class)queue,"MELEE");
        method("queueLegacyRecoveryR51",queue,LivingEntity.class).invoke(ordinary,melee,ordinary.pilot);
        check(deadline(ordinary)==52008,"Fist/ordinary tail buffering was changed");
        System.out.println("R52 actual production melee/smash queue/expiry replay PASS checks="+checks+"; scripted clock/admission only, no game/world/attack or art acceptance");
    }
    private EvaKnifeRecoveryR52Test(){}
}

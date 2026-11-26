package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.*;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.common.capabilities.ForgeCapabilities;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Explicit install receipt authorizes initial aircraft creation only once. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervAirportR21
{
    public static final class State extends SavedData
    {
        final Map<String,UUID> aircraft=new LinkedHashMap<>();
        static State load(CompoundTag tag){var s=new State();for(String k:tag.getAllKeys())if(tag.hasUUID(k))s.aircraft.put(k,tag.getUUID(k));return s;}
        @Override public CompoundTag save(CompoundTag tag){aircraft.forEach(tag::putUUID);return tag;}
    }
    private static final String FIGHTER_TAG = "projectseele_nerv16";
    private static final Set<Entity> pendingFighters = Collections.newSetFromMap(new WeakHashMap<>());

    public static CompoundTag commissioningData(Entity aircraft) throws ReflectiveOperationException {
        var tag = aircraft.saveWithoutId(new CompoundTag());
        tag.putBoolean("GearUp", false);
        tag.putInt("Energy", ((Number)aircraft.getClass().getMethod("getMaxEnergy").invoke(aircraft)).intValue());
        // Missing health fields tell Superb Warfare to take each component's initial health from its definition.
        for (String part : new String[]{"Health", "TurretHealth", "LeftWheelHealth", "RightWheelHealth", "MainEngineHealth", "SubEngineHealth"})
            tag.remove(part);
        return tag;
    }

    public static void identifyFighter(Entity aircraft) {
        if (!com.projectseele.item.Nerv16BoxItem.AIRFRAME.equals(BuiltInRegistries.ENTITY_TYPE.getKey(aircraft.getType()))) return;
        if (!aircraft.getTags().contains(FIGHTER_TAG)) {
            if (!aircraft.hasCustomName()) aircraft.setCustomName(net.minecraft.network.chat.Component.translatable("entity.projectseele.nerv_16"));
            aircraft.addTag(FIGHTER_TAG);
        }
    }

    @SubscribeEvent public static void onAircraftLoaded(net.minecraftforge.event.entity.EntityJoinLevelEvent event) {
        var entity = event.getEntity();
        if (!event.getLevel().isClientSide() && entity.getTags().contains(FIGHTER_TAG)
                && com.projectseele.item.Nerv16BoxItem.AIRFRAME.equals(BuiltInRegistries.ENTITY_TYPE.getKey(entity.getType())))
            pendingFighters.add(entity);
    }

    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END || !net.minecraftforge.fml.ModList.get().isLoaded("superbwarfare"))return;
        pendingFighters.removeIf(aircraft -> {
            if (aircraft.isRemoved()) return true;
            if (aircraft.tickCount < 5) return false;
            tuneEngine(aircraft);
            if (!aircraft.getTags().contains(AMMUNITION_TAG)) stockAmmunition(aircraft);
            return true;
        });
        if(event.getServer().getTickCount()%40!=0)return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var file=event.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_airport_r21.json");if(!Files.isRegularFile(file))return;
        State state=level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_nerv_airport_r21");
        // R65 (owner's feedback 2, items 46 and 45): aircraft already standing in the world get their ammunition once,
        // when loaded; the J-16s get their engine every time they are loaded.
        for(var placed:state.aircraft.entrySet())
        {
            Entity existing=level.getEntity(placed.getValue());
            if(existing==null)continue;
            identifyFighter(existing);
            if(!existing.getTags().contains(AMMUNITION_TAG)&&stockAmmunition(existing))
                ProjectSeele.LOGGER.info("R65 NERV aircraft {} ammunition stocked",placed.getKey());
            tuneEngine(existing);
        }
        try
        {
            var plan=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
            for(var element:plan.getAsJsonArray("vehicles"))
            {
                var spec=element.getAsJsonObject();String key=spec.get("key").getAsString();var pos=spec.getAsJsonArray("position");
                BlockPos pad=BlockPos.containing(pos.get(0).getAsDouble(),pos.get(1).getAsDouble(),pos.get(2).getAsDouble());
                if(state.aircraft.containsKey(key))continue;
                level.getChunk(pad);if(level.getBlockState(pad.below()).isAir())throw new IllegalStateException("Missing airport apron "+pad);
                var type=BuiltInRegistries.ENTITY_TYPE.get(new ResourceLocation(spec.get("id").getAsString()));Entity aircraft=type.create(level);
                if(aircraft==null)throw new IllegalStateException("Unavailable installed aircraft "+spec);
                CompoundTag tag=commissioningData(aircraft);
                tag.putFloat("ServerYaw",spec.get("yaw").getAsFloat());
                aircraft.load(tag);aircraft.moveTo(pos.get(0).getAsDouble(),pos.get(1).getAsDouble(),pos.get(2).getAsDouble(),spec.get("yaw").getAsFloat(),0);aircraft.addTag("seele_r21_nerv_aircraft");
                identifyFighter(aircraft);
                stockAmmunition(aircraft);
                if(!level.addFreshEntity(aircraft))throw new IllegalStateException("Aircraft creation rejected "+key);
                state.aircraft.put(key,aircraft.getUUID());state.setDirty();ProjectSeele.LOGGER.info("R21 NERV AIRPORT aircraft {} {} {}",key,aircraft.getUUID(),aircraft.position());
            }
        }
        catch(Exception e){throw new IllegalStateException("R21 aircraft commissioning",e);}
    }
    /**
     * R65 (owner's feedback 2, item 45): the NERV J-16s' own engine, through superbwarfare's per-vehicle override, so
     * one takes off within the GeoFront apron (27 blocks of roll instead of 108) and climbs the transport shaft even
     * without boost (thrust 0.047 x 1.5 against gravity 0.06). Against the mod's J-16: Increment 1 -> 2.5,
     * SpeedRate 1 -> 1.5, LiftSpeed 1 -> 1.5. The override replaces the whole block, so the rest is the mod's own.
     * J-16s elsewhere keep the mod's data.
     */
    static final String J16_ENGINE="{\"EngineInfo\":{\"EnergyCostRate\":256,\"Increment\":2.5,\"Decrement\":1,\"PitchSpeed\":1,\"YawSpeed\":1,"
        +"\"RollSpeed\":1,\"LiftSpeed\":1.5,\"SpeedRate\":1.5,\"GearRotateAngle\":85,\"EngineStartSound\":\"superbwarfare:a_10a_engine_start\",\"EngineSoundVolume\":0.8}}";
    private static final java.util.Set<Entity> TUNED=java.util.Collections.newSetFromMap(new java.util.WeakHashMap<>());

    /**
     * superbwarfare reads a vehicle's engine block on its first move and keeps it, and applies the override only once
     * the vehicle is initialised; so the block is cleared, to be read again, once the J-16 has ticked, once a session.
     */
    static void tuneEngine(Entity aircraft)
    {
        if(aircraft.tickCount<5||TUNED.contains(aircraft)||!"superbwarfare:j_16".equals(String.valueOf(BuiltInRegistries.ENTITY_TYPE.getKey(aircraft.getType()))))return;
        try
        {
            if(!J16_ENGINE.equals(aircraft.getClass().getMethod("getOverride").invoke(aircraft)))
                aircraft.getClass().getMethod("setOverride",String.class).invoke(aircraft,J16_ENGINE);
            for(var method:aircraft.getClass().getMethods())
                if(method.getName().equals("setEngineInfo")&&method.getParameterCount()==1){method.invoke(aircraft,(Object)null);TUNED.add(aircraft);break;}
        }
        catch(ReflectiveOperationException|RuntimeException failed)
        {
            ProjectSeele.LOGGER.warn("R65 NERV J-16 {}: engine left as the mod has it ({})",aircraft.getUUID(),failed.toString());
        }
    }

    /** Marks an aircraft whose ammunition was stocked, so a box taken out of it is not put back again. */
    static final String AMMUNITION_TAG="seele_r65_ammunition";

    /**
     * One creative ammunition box in the aircraft's own hold: superbwarfare then counts every weapon's reserve as
     * endless (shells, rockets, missiles, flares), and magazines reload from it. The box was written into the save as
     * "Items", but a vehicle that already carries an "Inventory" (every saved one does) reads only that, so it was
     * never there. The hold is the vehicle's item handler; a full hold is left alone. The magazines are then loaded
     * from it, so the first sortie does not open with a reload (the J-16's missiles take 10 s).
     */
    static boolean stockAmmunition(Entity aircraft)
    {
        var box=BuiltInRegistries.ITEM.get(new ResourceLocation("superbwarfare:creative_ammo_box"));
        var handler=aircraft.getCapability(ForgeCapabilities.ITEM_HANDLER).orElse(null);
        if(handler==null||box==net.minecraft.world.item.Items.AIR)return false;
        boolean held=false;
        for(int slot=0;!held&&slot<handler.getSlots();slot++)held=handler.getStackInSlot(slot).is(box);
        for(int slot=0;!held&&slot<handler.getSlots();slot++)
            held=handler.getStackInSlot(slot).isEmpty()&&handler.insertItem(slot,new ItemStack(box),false).isEmpty();
        if(!held){ProjectSeele.LOGGER.warn("R65 NERV aircraft {} hold is full; no ammunition box added",aircraft.getUUID());return false;}
        loadMagazines(aircraft);
        aircraft.addTag(AMMUNITION_TAG);
        return true;
    }

    /** superbwarfare is not on the compile path: its own (unobfuscated) methods are reached by name. */
    static void loadMagazines(Entity aircraft)
    {
        try
        {
            var guns=(java.util.Map<?,?>)aircraft.getClass().getMethod("getGunDataMap").invoke(aircraft);
            var modify=aircraft.getClass().getMethod("modifyGunData",String.class,java.util.function.Consumer.class);
            for(Object name:guns.keySet())
                modify.invoke(aircraft,name,(java.util.function.Consumer<Object>)gun->
                {
                    try{gun.getClass().getMethod("reloadAmmo",Entity.class,boolean.class).invoke(gun,aircraft,false);}
                    catch(ReflectiveOperationException failed){throw new IllegalStateException(failed);}
                });
        }
        catch(ReflectiveOperationException|RuntimeException failed)
        {
            ProjectSeele.LOGGER.warn("R65 NERV aircraft {}: magazines left as they were ({})",aircraft.getUUID(),failed.toString());
        }
    }

    private NervAirportR21(){}
}

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
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||event.getServer().getTickCount()%40!=0)return;
        ServerLevel level=event.getServer().getLevel(FacilitySchemaV2.DIMENSION);if(level==null)return;
        var file=event.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_airport_r21.json");if(!Files.isRegularFile(file))return;
        State state=level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_nerv_airport_r21");
        // R65 (owner's feedback 2, item 46): aircraft already standing in the world get their ammunition once, when loaded.
        for(var placed:state.aircraft.entrySet())
        {
            Entity existing=level.getEntity(placed.getValue());
            if(existing!=null&&!existing.getTags().contains(AMMUNITION_TAG)&&stockAmmunition(existing))
                ProjectSeele.LOGGER.info("R65 NERV aircraft {} ammunition stocked",placed.getKey());
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
                CompoundTag tag=aircraft.saveWithoutId(new CompoundTag());tag.putBoolean("GearUp",false);tag.putFloat("ServerYaw",spec.get("yaw").getAsFloat());
                for(String field:new String[]{"Health","TurretHealth","LeftWheelHealth","RightWheelHealth","MainEngineHealth","SubEngineHealth"})tag.remove(field);
                tag.putInt("Energy",((Number)aircraft.getClass().getMethod("getMaxEnergy").invoke(aircraft)).intValue());
                aircraft.load(tag);aircraft.moveTo(pos.get(0).getAsDouble(),pos.get(1).getAsDouble(),pos.get(2).getAsDouble(),spec.get("yaw").getAsFloat(),0);aircraft.addTag("seele_r21_nerv_aircraft");
                stockAmmunition(aircraft);
                if(!level.addFreshEntity(aircraft))throw new IllegalStateException("Aircraft creation rejected "+key);
                state.aircraft.put(key,aircraft.getUUID());state.setDirty();ProjectSeele.LOGGER.info("R21 NERV AIRPORT aircraft {} {} {}",key,aircraft.getUUID(),aircraft.position());
            }
        }
        catch(Exception e){throw new IllegalStateException("R21 aircraft commissioning",e);}
    }
    /** Marks an aircraft whose ammunition was stocked, so a box taken out of it is not put back again. */
    static final String AMMUNITION_TAG="seele_r65_ammunition";

    /**
     * One creative ammunition box in the aircraft's own hold: superbwarfare then counts every weapon's reserve as
     * endless (shells, rockets, missiles, flares), and magazines reload from it. The box was written into the save as
     * "Items", but a vehicle that already carries an "Inventory" (every saved one does) reads only that, so it was
     * never there. The hold is the vehicle's item handler; a full hold is left alone.
     */
    static boolean stockAmmunition(Entity aircraft)
    {
        var box=BuiltInRegistries.ITEM.get(new ResourceLocation("superbwarfare:creative_ammo_box"));
        var handler=aircraft.getCapability(ForgeCapabilities.ITEM_HANDLER).orElse(null);
        if(handler==null||box==net.minecraft.world.item.Items.AIR)return false;
        for(int slot=0;slot<handler.getSlots();slot++)if(handler.getStackInSlot(slot).is(box)){aircraft.addTag(AMMUNITION_TAG);return true;}
        for(int slot=0;slot<handler.getSlots();slot++)
            if(handler.getStackInSlot(slot).isEmpty()&&handler.insertItem(slot,new ItemStack(box),false).isEmpty()){aircraft.addTag(AMMUNITION_TAG);return true;}
        ProjectSeele.LOGGER.warn("R65 NERV aircraft {} hold is full; no ammunition box added",aircraft.getUUID());
        return false;
    }

    private NervAirportR21(){}
}

package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

/** Sound events; individual asset provenance is recorded in docs/ASSETS.md. */
public class ModSounds
{
    public static final DeferredRegister<SoundEvent> SOUNDS =
            DeferredRegister.create(ForgeRegistries.SOUND_EVENTS, ProjectSeele.MODID);

    public static final RegistryObject<SoundEvent> ALARM = register("alarm");
    public static final RegistryObject<SoundEvent> BEAM_CHARGE = register("beam_charge");
    public static final RegistryObject<SoundEvent> BEAM_FIRE = register("beam_fire");
    public static final RegistryObject<SoundEvent> CROSS_EXPLOSION = register("cross_explosion");
    public static final RegistryObject<SoundEvent> CRYSTAL_HIT = register("crystal_hit");
    public static final RegistryObject<SoundEvent> CRYSTAL_BREAK = register("crystal_break");
    public static final RegistryObject<SoundEvent> DRILL = register("drill");
    public static final RegistryObject<SoundEvent> RAMIEL_HUM = register("ramiel_hum");
    public static final RegistryObject<SoundEvent> RIFLE_FIRE = register("rifle_fire");
    public static final RegistryObject<SoundEvent> EVA_FOOT_CONCRETE=register("eva_foot_concrete");
    public static final RegistryObject<SoundEvent> EVA_FOOT_SOIL=register("eva_foot_soil");
    public static final RegistryObject<SoundEvent> EVA_LAND=register("eva_land");
    public static final RegistryObject<SoundEvent> EVA_SERVO=register("eva_servo");
    public static final RegistryObject<SoundEvent> EVA_SWING=register("eva_swing");
    public static final RegistryObject<SoundEvent> EVA_IMPACT=register("eva_impact");
    public static final RegistryObject<SoundEvent> EVA_IMPACT_HEAVY=register("eva_impact_heavy");
    public static final RegistryObject<SoundEvent> EVA_JOINT_LOAD=register("eva_joint_load");
    public static final RegistryObject<SoundEvent> SACHIEL_FOOT=register("sachiel_foot");
    public static final RegistryObject<SoundEvent> SACHIEL_SWING=register("sachiel_swing");
    public static final RegistryObject<SoundEvent> EVA_ARMOR_IMPACT=register("eva_armor_impact");
    public static final RegistryObject<SoundEvent> EVA_KNIFE_CUT=register("eva_knife_cut");
    public static final RegistryObject<SoundEvent> EVA_CORE_BREAK=register("eva_core_break");
    public static final RegistryObject<SoundEvent> EVA_AT_PRESSURE=register("eva_at_pressure");
    public static final RegistryObject<SoundEvent> EVA_AT_TEAR=register("eva_at_tear");
    public static final RegistryObject<SoundEvent> EVA_BERSERK_ROAR=register("eva_berserk_roar");
    public static final RegistryObject<SoundEvent> EVA_ATTACK_ROAR=register("eva_attack_roar");
    public static final RegistryObject<SoundEvent> TRANSPORT_ENGINE=register("transport_engine");
    public static final RegistryObject<SoundEvent> PERSONNEL_DOOR_OPEN=register("personnel_door_open");
    public static final RegistryObject<SoundEvent> PERSONNEL_DOOR_CLOSE=register("personnel_door_close");
    public static final RegistryObject<SoundEvent> PRESSURE_DOOR_MOTION=register("pressure_door_motion");
    public static final RegistryObject<SoundEvent> EVA_COCKPIT_CONFIRM=register("eva_cockpit_confirm");
    public static final RegistryObject<SoundEvent> EVA_COCKPIT_WARNING=register("eva_cockpit_warning");
    public static final RegistryObject<SoundEvent> EVA_DRIVE_LOOP=register("eva_drive_loop");
    public static final RegistryObject<SoundEvent> EVA_RIFLE_FIRE=register("eva_rifle_fire");
    public static final RegistryObject<SoundEvent> SHAMSHEL_WHIP_CHARGE=register("shamshel_whip_charge");
    public static final RegistryObject<SoundEvent> SHAMSHEL_WHIP_CRACK=register("shamshel_whip_crack");
    public static final RegistryObject<SoundEvent> PERIOD_PHONE_BUSY=register("period_phone_busy");
    public static final RegistryObject<SoundEvent> STAFF_RADIO_CONNECT=register("staff_radio_connect");
    public static final RegistryObject<SoundEvent> STAFF_RADIO_ACK=register("staff_radio_ack");

    public static final java.util.Map<String,RegistryObject<SoundEvent>> FACILITY=facilitySounds();
    private static java.util.Map<String,RegistryObject<SoundEvent>> facilitySounds()
    {
        var result=new java.util.LinkedHashMap<String,RegistryObject<SoundEvent>>();
        for(String name:new String[]{"facility_rail_motion","facility_hydraulic","facility_hydraulic_launch","facility_lock","facility_catapult","facility_siren",
                "pa_prepare","pa_insert","pa_lock","pa_drain","pa_transfer","pa_ready","pa_recover","pa_return","pa_fill","pa_standby","pa_fault","pa_3","pa_2","pa_1","pa_launch","pa_door_open","pa_door_close",
                "pa_signal_r30","pa_blue_r30","pa_alert_r30","pa_combat_r31"})
            result.put(name,SOUNDS.register(name,()->SoundEvent.createFixedRangeEvent(new ResourceLocation(ProjectSeele.MODID,name),220)));
        return java.util.Collections.unmodifiableMap(result);
    }

    /** Dedicated positional room recordings; ordinary facility and phone events stay dry. */
    public static final java.util.Map<String,RegistryObject<SoundEvent>> HANGAR_PA=hangarPa();
    private static java.util.Map<String,RegistryObject<SoundEvent>> hangarPa()
    {
        var result=new java.util.LinkedHashMap<String,RegistryObject<SoundEvent>>();
        for(String original:new String[]{"pa_prepare", "pa_insert", "pa_lock", "pa_drain", "pa_transfer", "pa_ready", "pa_recover", "pa_return", "pa_fill", "pa_standby", "pa_fault", "pa_door_open", "pa_door_close", "pa_3", "pa_2", "pa_1", "pa_launch", "pa_combat_r31"})
        {
            String name="hangar_"+original+"_r46";
            result.put(original,SOUNDS.register(name,()->SoundEvent.createFixedRangeEvent(
                    new ResourceLocation(ProjectSeele.MODID,name),220)));
        }
        return java.util.Collections.unmodifiableMap(result);
    }

    private static RegistryObject<SoundEvent> register(String name)
    {
        return SOUNDS.register(name,
                () -> (name.startsWith("eva_")&&!name.startsWith("eva_cockpit")&&!name.equals("eva_drive_loop"))||name.startsWith("shamshel_")
                        ? SoundEvent.createFixedRangeEvent(new ResourceLocation(ProjectSeele.MODID,name),192)
                        : SoundEvent.createVariableRangeEvent(new ResourceLocation(ProjectSeele.MODID, name)));
    }
}

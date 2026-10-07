package com.projectseele;

import com.projectseele.capability.EvaPilotData;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.registry.ModEntities;
import net.minecraftforge.common.capabilities.RegisterCapabilitiesEvent;
import net.minecraftforge.event.entity.EntityAttributeCreationEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, bus = Mod.EventBusSubscriber.Bus.MOD)
public class CommonEvents
{
    @SubscribeEvent
    public static void onRegisterCapabilities(RegisterCapabilitiesEvent event)
    {
        event.register(EvaPilotData.class);
    }

    @SubscribeEvent
    public static void onEntityAttributeCreation(EntityAttributeCreationEvent event)
    {
        event.put(ModEntities.RAMIEL.get(), RamielEntity.createAttributes().build());
        event.put(ModEntities.GAGHIEL.get(), com.projectseele.entity.GaghielEntity.createAttributes().build());
        event.put(ModEntities.EVA_UNIT01.get(), EvaUnit01Entity.createAttributes().build());
        event.put(ModEntities.EVA_UNIT00.get(), EvaUnit01Entity.createAttributes().build());
        event.put(ModEntities.EVA_UNIT02.get(), EvaUnit01Entity.createAttributes().build());
        event.put(ModEntities.EVA_PROTOTYPE.get(), EvaUnit01Entity.createAttributes().build());
        event.put(ModEntities.ENTRY_PLUG_CARRIER.get(),
                EntryPlugCarrierEntity.createAttributes().build());
        event.put(ModEntities.TRAINING_PILOT.get(),
                TrainingPilotEntity.createAttributes().build());
        event.put(ModEntities.NERV_STAFF.get(),com.projectseele.entity.NervStaffEntity.createAttributes().build());
        event.put(ModEntities.SACHIEL.get(), com.projectseele.entity.SachielEntity.createAttributes().build());
        event.put(ModEntities.SHAMSHEL.get(), com.projectseele.entity.ShamshelEntity.createAttributes().build());
        event.put(ModEntities.ZERUEL.get(), com.projectseele.entity.ZeruelEntity.createAttributes().build());
        event.put(ModEntities.ISRAFEL.get(), com.projectseele.entity.IsrafelEntity.createAttributes().build());
        event.put(ModEntities.MASS_PRODUCTION_EVA.get(),
                com.projectseele.entity.MassProductionEvaEntity.createAttributes().build());
        event.put(ModEntities.LILITH.get(),
                com.projectseele.entity.LilithEntity.createAttributes().build());
    }
}

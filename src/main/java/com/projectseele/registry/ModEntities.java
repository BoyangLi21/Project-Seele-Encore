package com.projectseele.registry;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaScale;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.LilithEntity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.entity.NervCommandSeatEntity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.NervSiloDoorEntity;
import com.projectseele.entity.NervHangarDoorEntity;
import com.projectseele.entity.NervSlidingDoorEntity;
import com.projectseele.entity.NervLiftDoorEntity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.SachielEntity;
import com.projectseele.entity.MassProductionEvaEntity;
import com.projectseele.entity.ShamshelEntity;
import com.projectseele.entity.ZeruelEntity;
import com.projectseele.entity.TrainingPilotEntity;
import com.projectseele.entity.UltramanAvatarEntity;
import com.projectseele.entity.IsrafelEntity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public class ModEntities
{
    public static final DeferredRegister<EntityType<?>> ENTITY_TYPES =
            DeferredRegister.create(ForgeRegistries.ENTITY_TYPES, ProjectSeele.MODID);
    public static final RegistryObject<EntityType<com.projectseele.entity.UNTransportEntity>> UN_TRANSPORT=ENTITY_TYPES.register("un_transport",
            ()->EntityType.Builder.<com.projectseele.entity.UNTransportEntity>of(com.projectseele.entity.UNTransportEntity::new,MobCategory.MISC)
                    .sized(8,8).clientTrackingRange(48).updateInterval(1).fireImmune().build("un_transport"));

    public static final RegistryObject<EntityType<RamielEntity>> RAMIEL = ENTITY_TYPES.register("ramiel",
            () -> EntityType.Builder.of(RamielEntity::new, MobCategory.MONSTER)
                    .sized(15.0F, 15.0F)
                    .fireImmune()
                    .clientTrackingRange(12)
                    .build("ramiel"));

    // Tracking ranges below are wide because scenario staging can park these
    // entities hundreds of blocks up the Tree of Life.
    public static final RegistryObject<EntityType<EvaUnit01Entity>> EVA_UNIT01 = ENTITY_TYPES.register("eva_unit01",
            () -> EntityType.Builder.of(EvaUnit01Entity::new, MobCategory.MISC)
                    .sized(EvaScale.NORMAL_WIDTH, EvaScale.NORMAL_HEIGHT)
                    .fireImmune()
                    .clientTrackingRange(64)
                    .updateInterval(1)
                    .build("eva_unit01"));

    public static final RegistryObject<EntityType<EvaPrototypeEntity>> EVA_PROTOTYPE = ENTITY_TYPES.register("eva_prototype",
            () -> EntityType.Builder.of(EvaPrototypeEntity::new, MobCategory.MISC)
                    .sized(EvaScale.NORMAL_WIDTH, EvaScale.NORMAL_HEIGHT)
                    .fireImmune()
                    .clientTrackingRange(32)
                    .updateInterval(1)
                    .build("eva_prototype"));

    public static final RegistryObject<EntityType<com.projectseele.entity.IndustrialMemberEntity>> INDUSTRIAL_MEMBER = ENTITY_TYPES.register("industrial_member",
            () -> EntityType.Builder.<com.projectseele.entity.IndustrialMemberEntity>of(com.projectseele.entity.IndustrialMemberEntity::new, MobCategory.MISC)
                    .sized(0,0).clientTrackingRange(32).updateInterval(20).noSummon().build("industrial_member"));

    public static final RegistryObject<EntityType<EvaUnit01Entity>> EVA_UNIT00 = ENTITY_TYPES.register("eva_unit00",
            () -> EntityType.Builder.of(EvaUnit01Entity::new, MobCategory.MISC)
                    .sized(EvaScale.NORMAL_WIDTH, EvaScale.NORMAL_HEIGHT)
                    .fireImmune()
                    .clientTrackingRange(12)
                    .updateInterval(1)
                    .build("eva_unit00"));

    public static final RegistryObject<EntityType<EvaUnit01Entity>> EVA_UNIT02 = ENTITY_TYPES.register("eva_unit02",
            () -> EntityType.Builder.of(EvaUnit01Entity::new, MobCategory.MISC)
                    .sized(EvaScale.NORMAL_WIDTH, EvaScale.NORMAL_HEIGHT)
                    .fireImmune()
                    .clientTrackingRange(12)
                    .updateInterval(1)
                    .build("eva_unit02"));

    public static final RegistryObject<EntityType<EntryPlugCarrierEntity>> ENTRY_PLUG_CARRIER =
            ENTITY_TYPES.register("entry_plug_carrier",
                    () -> EntityType.Builder.of(EntryPlugCarrierEntity::new,
                                    MobCategory.MISC)
                            .sized(EvaScale.ENTRY_PLUG_WIDTH,
                                    EvaScale.ENTRY_PLUG_LENGTH)
                            .fireImmune()
                            .clientTrackingRange(24)
                            .updateInterval(1)
                            .build("entry_plug_carrier"));

    public static final RegistryObject<EntityType<NervCarrierPlatformEntity>>
            NERV_CARRIER_PLATFORM = ENTITY_TYPES.register(
                    "nerv_carrier_platform",
                    () -> EntityType.Builder.of(NervCarrierPlatformEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(EvaScale.CARRIER_WIDTH, 0.6F)
                            .clientTrackingRange(32)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_carrier_platform"));

    public static final RegistryObject<EntityType<NervCarrierPlatformEntity>>
            NERV_LIFT_CABIN = ENTITY_TYPES.register(
                    "nerv_lift_cabin",
                    () -> EntityType.Builder.of(NervCarrierPlatformEntity::new,
                                    MobCategory.MISC)
                            .sized(5.0F, 4.0F)
                            .fireImmune()
                            .clientTrackingRange(64)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_lift_cabin"));

    public static final RegistryObject<EntityType<NervCommandSeatEntity>>
            NERV_COMMAND_SEAT = ENTITY_TYPES.register(
                    "nerv_command_seat",
                    () -> EntityType.Builder.of(NervCommandSeatEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(0.55F, 0.35F)
                            .clientTrackingRange(12)
                            .updateInterval(20)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_command_seat"));

    public static final RegistryObject<EntityType<NervCommandSeatEntity>> PILOT_REST_SEAT_R47=ENTITY_TYPES.register(
            "pilot_rest_seat_r47",()->EntityType.Builder.of(NervCommandSeatEntity::new,MobCategory.MISC)
                    .sized(.55F,.35F).clientTrackingRange(12).updateInterval(20).setShouldReceiveVelocityUpdates(false)
                    .build("pilot_rest_seat_r47"));

    public static final RegistryObject<EntityType<NervArmamentStationEntity>>
            NERV_ARMAMENT_STATION = ENTITY_TYPES.register(
                    "nerv_armament_station",
                    () -> EntityType.Builder.of(
                                    NervArmamentStationEntity::new,
                                    MobCategory.MISC)
                            .sized(9.0F, 42.0F)
                            .fireImmune()
                            .clientTrackingRange(48)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_armament_station"));

    public static final RegistryObject<EntityType<NervSiloDoorEntity>>
            NERV_SILO_DOOR = ENTITY_TYPES.register(
                    "nerv_silo_door",
                    () -> EntityType.Builder.of(NervSiloDoorEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            // Visual leaves are non-pickable and no-cull; a
                            // 64-block server AABB only bloats entity-section
                            // bookkeeping without affecting their renderer.
                            .sized(1.0F, 1.0F)
                            .fireImmune()
                            .clientTrackingRange(96)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_silo_door"));

    public static final RegistryObject<EntityType<NervHangarDoorEntity>>
            NERV_HANGAR_DOOR = ENTITY_TYPES.register(
                    "nerv_hangar_door",
                    () -> EntityType.Builder.of(NervHangarDoorEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(1.0F, 1.0F)
                            .fireImmune()
                            .clientTrackingRange(64)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_hangar_door"));

    public static final RegistryObject<EntityType<NervSlidingDoorEntity>>
            NERV_SLIDING_DOOR = ENTITY_TYPES.register(
                    "nerv_sliding_door",
                    () -> EntityType.Builder.of(NervSlidingDoorEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(1.0F, 1.0F)
                            .fireImmune()
                            .clientTrackingRange(16)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_sliding_door"));

    public static final RegistryObject<EntityType<NervLiftDoorEntity>>
            NERV_LIFT_DOOR = ENTITY_TYPES.register(
                    "nerv_lift_door",
                    () -> EntityType.Builder.of(NervLiftDoorEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(1.0F, 1.0F)
                            .fireImmune()
                            .clientTrackingRange(24)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("nerv_lift_door"));

    public static final RegistryObject<EntityType<UltramanAvatarEntity>>
            ULTRAMAN_AVATAR = ENTITY_TYPES.register(
                    "ultraman_avatar",
                    () -> EntityType.Builder.of(UltramanAvatarEntity::new,
                                    MobCategory.MISC)
                            .noSave()
                            .sized(1.0F, 1.0F)
                            .fireImmune()
                            .clientTrackingRange(128)
                            .updateInterval(1)
                            .setShouldReceiveVelocityUpdates(false)
                            .build("ultraman_avatar"));

    public static final RegistryObject<EntityType<TrainingPilotEntity>> TRAINING_PILOT =
            ENTITY_TYPES.register("training_pilot",
                    () -> EntityType.Builder.of(TrainingPilotEntity::new,
                                    MobCategory.MISC)
                            .sized(0.6F, 1.8F)
                            .clientTrackingRange(12)
                            .build("training_pilot"));

    public static final RegistryObject<EntityType<com.projectseele.entity.NervStaffEntity>> NERV_STAFF=ENTITY_TYPES.register("nerv_staff",
            ()->EntityType.Builder.of(com.projectseele.entity.NervStaffEntity::new,MobCategory.MISC).sized(.6F,1.8F).clientTrackingRange(6).updateInterval(3).build("nerv_staff"));

    public static final RegistryObject<EntityType<SachielEntity>> SACHIEL = ENTITY_TYPES.register("sachiel",
            () -> EntityType.Builder.of(SachielEntity::new, MobCategory.MONSTER)
                    .sized(18.0F, 60.0F).fireImmune().clientTrackingRange(24).build("sachiel"));

    public static final RegistryObject<EntityType<MassProductionEvaEntity>> MASS_PRODUCTION_EVA =
            ENTITY_TYPES.register("mass_production_eva",
                    () -> EntityType.Builder.of(MassProductionEvaEntity::new, MobCategory.MONSTER)
                            // The fixed Tree camera is 120 blocks off-plane;
                            // crown/nadir vessels add 67 vertical blocks. A
                            // range of 16 dropped those four client-side while
                            // the server still held a 9/9 formation.
                            .sized(10.0F, 26.0F).fireImmune().clientTrackingRange(32)
                            .build("mass_production_eva"));

    public static final RegistryObject<EntityType<ShamshelEntity>> SHAMSHEL = ENTITY_TYPES.register("shamshel",
            () -> EntityType.Builder.of(ShamshelEntity::new, MobCategory.MONSTER)
                    .sized(20.0F, 60.0F).fireImmune().clientTrackingRange(24).build("shamshel"));

    public static final RegistryObject<EntityType<ZeruelEntity>> ZERUEL = ENTITY_TYPES.register("zeruel",
            () -> EntityType.Builder.of(ZeruelEntity::new, MobCategory.MONSTER)
                    .sized(24.0F, 60.0F).fireImmune().clientTrackingRange(24).build("zeruel"));

    public static final RegistryObject<EntityType<IsrafelEntity>> ISRAFEL = ENTITY_TYPES.register("israfel",
            () -> EntityType.Builder.of(IsrafelEntity::new, MobCategory.MONSTER)
                    .sized(18.0F, 60.0F).fireImmune().clientTrackingRange(24).build("israfel"));
    public static final RegistryObject<EntityType<LilithEntity>> LILITH =
            ENTITY_TYPES.register("lilith",
                    () -> EntityType.Builder.of(LilithEntity::new, MobCategory.MISC)
                            .sized(1.0F, 1.0F).fireImmune()
                            .clientTrackingRange(24).updateInterval(20)
                            .build("lilith"));
}

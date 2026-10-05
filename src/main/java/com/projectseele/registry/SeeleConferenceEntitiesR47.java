package com.projectseele.registry;

import com.projectseele.entity.SeeleMonolithEntityR47;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraftforge.registries.RegistryObject;

public final class SeeleConferenceEntitiesR47
{
    public static final RegistryObject<EntityType<SeeleMonolithEntityR47>> MONOLITH=ModEntities.ENTITY_TYPES.register(
            "seele_monolith_r47",()->EntityType.Builder.of(SeeleMonolithEntityR47::new,MobCategory.MISC)
                    .sized(2.2F,4.5F).clientTrackingRange(48).updateInterval(20).setShouldReceiveVelocityUpdates(false)
                    .build("seele_monolith_r47"));
    public static final RegistryObject<EntityType<SeeleMonolithEntityR47>> DESK=ModEntities.ENTITY_TYPES.register(
            "seele_meeting_desk_r47",()->EntityType.Builder.of(SeeleMonolithEntityR47::new,MobCategory.MISC)
                    .sized(3.3F,1.04F).clientTrackingRange(48).updateInterval(20).setShouldReceiveVelocityUpdates(false)
                    .build("seele_meeting_desk_r47"));
    public static void bootstrap(){}
    private SeeleConferenceEntitiesR47(){}
}

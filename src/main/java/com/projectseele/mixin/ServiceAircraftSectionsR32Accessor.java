package com.projectseele.mixin;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.entity.EntitySectionStorage;
import net.minecraft.world.level.entity.PersistentEntitySectionManager;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

@Mixin(PersistentEntitySectionManager.class)
public interface ServiceAircraftSectionsR32Accessor
{
    @Accessor("permanentStorage")
    net.minecraft.world.level.entity.EntityPersistentStorage<Entity> seele$storageR65();

    @Accessor("sectionStorage")
    EntitySectionStorage<Entity> seele$sectionsR32();
}

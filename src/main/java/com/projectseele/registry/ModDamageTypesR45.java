package com.projectseele.registry;

import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.damagesource.DamageType;
import net.minecraft.world.entity.LivingEntity;

/** Dynamic data registry entry; source attribution matches vanilla mobAttack(attacker). */
public final class ModDamageTypesR45
{
    public static final ResourceKey<DamageType> EVA_ORDINARY_CONTACT=ResourceKey.create(
            Registries.DAMAGE_TYPE,new ResourceLocation("projectseele","eva_ordinary_contact"));

    public static DamageSource ordinaryContact(LivingEntity actualAttacker)
    {
        var holder=actualAttacker.level().registryAccess().registryOrThrow(Registries.DAMAGE_TYPE)
                .getHolderOrThrow(EVA_ORDINARY_CONTACT);
        return new DamageSource(holder,actualAttacker);
    }
    private ModDamageTypesR45(){}
}

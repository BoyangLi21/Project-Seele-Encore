package com.projectseele.combat;

import com.projectseele.registry.ModItems;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;

/** Shared checks for damage sources that ignore an A.T. Field entirely. */
public final class AtFieldRules
{
    private AtFieldRules() {}

    public static boolean bypassesAtField(DamageSource source)
    {
        // /kill and the void bypass invulnerability in vanilla; a field must not keep an Angel alive
        // against them either (Ramiel and the EVA already let them through).
        if (source.is(net.minecraft.tags.DamageTypeTags.BYPASSES_INVULNERABILITY))
        {
            return true;
        }
        if (!(source.getEntity() instanceof LivingEntity attacker))
        {
            return false;
        }
        return attacker.getMainHandItem().is(ModItems.LANCE_OF_LONGINUS.get())
                || attacker instanceof EvaUnit01Entity eva
                && eva.getWeapon() == EvaUnit01Entity.WEAPON_LANCE;
    }
}

package com.projectseele.mixin;

import com.projectseele.world.CityEntitySaveFence;
import net.minecraft.server.level.ServerLevel;
import net.minecraftforge.eventbus.api.Event;
import net.minecraftforge.eventbus.api.IEventBus;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Mixin(ServerLevel.class)
abstract class CitySaveEventMixin
{
    @Redirect(method = "save", at = @At(value = "INVOKE", remap = false,
            target = "Lnet/minecraftforge/eventbus/api/IEventBus;post(Lnet/minecraftforge/eventbus/api/Event;)Z"))
    private boolean seele$postAfterCityFlush(IEventBus bus, Event event)
    {
        return CityEntitySaveFence.postWhenDurable(bus, event);
    }
}

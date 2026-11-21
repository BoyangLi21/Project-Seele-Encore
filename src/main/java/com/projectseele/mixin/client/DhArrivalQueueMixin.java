package com.projectseele.mixin.client;

import com.projectseele.client.DhArrivalPriorityR65;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

import java.util.ArrayList;
import java.util.Comparator;

@Pseudo
@Mixin(targets = "com.seibel.distanthorizons.core.render.LodQuadTree", remap = false)
public abstract class DhArrivalQueueMixin
{
    @Redirect(method = "loadQueuedSections", require = 0, at = @At(value = "INVOKE",
            target = "Ljava/util/ArrayList;sort(Ljava/util/Comparator;)V"))
    private void seele$prioritizeVisibleTerrain(ArrayList<Object> sections, Comparator<Object> original)
    {
        DhArrivalPriorityR65.sort(sections, original);
    }
}

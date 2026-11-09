package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.world.FacilityVisibilityR54;
import net.minecraft.client.Minecraft;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/** Vanilla's far plane is four times the chunk radius; a giant past it would be clipped and frustum-culled. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class GiantFarViewR61
{
    private static final float MARGIN = 128F;
    private static volatile float farthest;

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END) return;
        var minecraft = Minecraft.getInstance();
        float distance = 0F;
        if (minecraft.level != null && minecraft.player != null)
        {
            var camera = minecraft.gameRenderer.getMainCamera().getPosition();
            for (var entity : minecraft.level.entitiesForRendering())
            {
                if (!FacilityVisibilityR54.giant(entity)) continue;
                distance = (float) Math.max(distance, Math.sqrt(entity.distanceToSqr(camera)));
            }
        }
        farthest = Math.min(distance, FacilityVisibilityR54.GIANT_DISTANCE + MARGIN);
    }

    public static Matrix4f projection(Matrix4f original)
    {
        float wanted = farthest + MARGIN;
        float near = original.m32() / (original.m22() - 1F);
        float far = original.m32() / (original.m22() + 1F);
        if (farthest <= 0F || wanted <= far || !Float.isFinite(near) || near <= 0F) return original;
        return new Matrix4f(original).m22(-(wanted + near) / (wanted - near)).m32(-2F * wanted * near / (wanted - near));
    }

    private GiantFarViewR61() { }
}

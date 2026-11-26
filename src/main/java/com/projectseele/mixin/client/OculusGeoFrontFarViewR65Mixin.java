package com.projectseele.mixin.client;

import com.google.common.collect.ImmutableSet;
import com.projectseele.ProjectSeele;
import com.projectseele.client.GeoFrontDomeFarViewR65;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

import static org.lwjgl.opengl.GL11.glGetInteger;
import static org.lwjgl.opengl.GL30.*;

/** Oculus has finished shading the opaque scene here, before glass and water blend into its colour buffer. */
@Pseudo
@Mixin(targets = "net.irisshaders.iris.pipeline.IrisRenderingPipeline", remap = false)
public abstract class OculusGeoFrontFarViewR65Mixin
{
    @Unique private int projectseele$cavityFramebuffer = -1;

    @Inject(method = "beginTranslucents", at = @At("RETURN"), require = 0)
    private void projectseele$drawCavityBehindGlass(CallbackInfo callback)
    {
        if (!GeoFrontDomeFarViewR65.hasPendingFarView() || projectseele$cavityFramebuffer == 0) return;
        if (projectseele$cavityFramebuffer < 0)
        {
            // The framebuffer belongs to this optional pipeline. Oculus updates its depth attachment on resize
            // and deletes it with its other targets when the pack reloads.
            int read = glGetInteger(GL_READ_FRAMEBUFFER_BINDING), draw = glGetInteger(GL_DRAW_FRAMEBUFFER_BINDING);
            try
            {
                var field = getClass().getDeclaredField("renderTargets");
                field.setAccessible(true);
                Object targets = field.get(this);
                Object flipped = getClass().getMethod("getFlippedAfterTranslucent").invoke(this);
                Object buffer = targets.getClass().getMethod("createGbufferFramebuffer", ImmutableSet.class, int[].class)
                        .invoke(targets, flipped, new int[]{0});
                projectseele$cavityFramebuffer = (int) buffer.getClass().getMethod("getId").invoke(buffer);
            }
            catch (ReflectiveOperationException | RuntimeException unavailable)
            {
                projectseele$cavityFramebuffer = 0;
                ProjectSeele.LOGGER.warn("Oculus opaque colour target unavailable for the GeoFront far view", unavailable);
            }
            finally
            {
                glBindFramebuffer(GL_READ_FRAMEBUFFER, read);
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, draw);
            }
        }
        if (projectseele$cavityFramebuffer > 0) GeoFrontDomeFarViewR65.composite(projectseele$cavityFramebuffer);
    }
}

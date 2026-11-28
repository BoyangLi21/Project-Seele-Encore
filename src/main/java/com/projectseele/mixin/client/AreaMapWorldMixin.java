package com.projectseele.mixin.client;

import com.projectseele.ProjectSeele;
import com.projectseele.client.map.AreaMapAtlas;
import com.projectseele.client.map.AreaMapDisplay;
import com.projectseele.client.map.AreaMapLayer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.Coerce;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyConstant;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Pseudo
@Mixin(targets = "xaero.map.gui.GuiMap", remap = false)
abstract class AreaMapWorldMixin
{
    @Shadow private int mouseBlockPosX, mouseBlockPosY, mouseBlockPosZ;
    @Shadow private double cameraX, cameraZ, userScale, scale;
    @Shadow private static double destScale;
    @Shadow private static boolean attachedCamera;
    @Shadow private ResourceKey<Level> lastViewedDimensionId;
    @Unique private AreaMapLayer projectseele$layer;
    @Unique private double projectseele$nativeZoom, projectseele$fitZoom, projectseele$resumeZoom;
    @Unique private boolean projectseele$ownsZoom;
    @Unique private boolean projectseele$undergroundView;
    @Unique private static final String LABEL = "Lxaero/map/graphics/MapRenderHelper;drawCenteredStringWithBackground(Lnet/minecraft/client/gui/GuiGraphics;Lnet/minecraft/client/gui/Font;Ljava/lang/String;IIIFFFFLcom/mojang/blaze3d/vertex/VertexConsumer;)V";

    @Inject(method = "getScaleMultiplier", at = @At("HEAD"))
    private void projectseele$openArea(int shortSide, CallbackInfoReturnable<Double> ci)
    {
        // This native call follows the attached-camera update and current viewed dimension lookup, before hit-testing.
        var layer = AreaMapAtlas.current(lastViewedDimensionId);
        boolean same = layer != null && layer == projectseele$layer;
        projectseele$layer = layer;
        if (layer == null)
        {
            if (projectseele$ownsZoom)
            {
                userScale = destScale = projectseele$nativeZoom;
                projectseele$ownsZoom = false;
            }
            projectseele$resumeZoom = 0;
            return;
        }
        if (same && projectseele$ownsZoom) return;
        if (!projectseele$ownsZoom) projectseele$nativeZoom = destScale;
        projectseele$ownsZoom = true;
        var mc = Minecraft.getInstance();
        var view = layer.hudView(mc.player.getX(), mc.player.getZ());
        var window = mc.getWindow();
        double margin = 20 * window.getGuiScale();
        projectseele$fitZoom = view.fit(Math.max(1, window.getWidth() - margin), Math.max(1, window.getHeight() - 2 * margin))
                / Math.max(1.0, shortSide / 1080.0);
        if (same && projectseele$resumeZoom > 0) userScale = destScale = projectseele$resumeZoom;
        else
        {
            userScale = destScale = projectseele$fitZoom;
            if (!attachedCamera)
            {
                cameraX = view.centerX();
                cameraZ = view.centerZ();
            }
        }
        projectseele$resumeZoom = 0;
        // The constructor's animation targets Xaero's previous scale. Clearing it lets the next wheel movement
        // start at the fitted scale, using Xaero's normal animation.
        try
        {
            var field = Class.forName("xaero.map.gui.GuiMap", false, getClass().getClassLoader()).getDeclaredField("zoomAnim");
            field.setAccessible(true);
            field.set(this, null);
        }
        catch (ReflectiveOperationException unavailable) { ProjectSeele.LOGGER.debug("Xaero opening zoom animation", unavailable); }
        if (Boolean.getBoolean("projectseele.areaMapTrace"))
            ProjectSeele.LOGGER.info("Area map opening {} center [{}, {}] scale {}", layer.id(), cameraX, cameraZ, userScale);
    }

    @ModifyConstant(method = "applyZoomLimits", constant = @Constant(doubleValue = 0.0625))
    private double projectseele$fitSmallWindows(double nativeLimit)
    {
        return projectseele$ownsZoom ? Math.min(nativeLimit, projectseele$fitZoom) : nativeLimit;
    }

    @Unique private boolean projectseele$showNativeDetail()
    {
        return projectseele$layer != null && projectseele$layer.id().equals("surface") && scale >= 0.5;
    }

    @Inject(method = {"render", "m_88315_"}, at = @At(value = "INVOKE", target = "Lxaero/map/MapProcessor;getGlobalVersion()I"))
    private void projectseele$underNativeDetail(GuiGraphics graphics, int x, int y, float partial, CallbackInfo ci)
    {
        projectseele$undergroundView = projectseele$layer != null && !projectseele$layer.id().equals("surface");
        if (projectseele$showNativeDetail()) AreaMapDisplay.worldTerrain(graphics, projectseele$layer, cameraX, cameraZ, false);
    }

    @Inject(method = {"render", "m_88315_"}, at = @At(value = "INVOKE",
            target = "Lxaero/map/graphics/renderer/multitexture/MultiTextureRenderTypeRendererProvider;draw(Lxaero/map/graphics/renderer/multitexture/MultiTextureRenderTypeRenderer;)V",
            ordinal = 1, shift = At.Shift.AFTER))
    private void projectseele$terrainBeforeMarkers(GuiGraphics graphics, int x, int y, float partial, CallbackInfo ci)
    {
        if (projectseele$undergroundView) mouseBlockPosY = projectseele$layer.cursorHeight(mouseBlockPosX + 0.5, mouseBlockPosZ + 0.5);
        if (!projectseele$showNativeDetail()) AreaMapDisplay.worldTerrain(graphics, projectseele$layer, cameraX, cameraZ, projectseele$undergroundView);
    }

    @Redirect(method = {"render", "m_88315_"}, at = @At(value = "INVOKE", target = "Lxaero/map/region/LeveledRegion;loadingAnimation()Z"))
    private boolean projectseele$onlyUnbakedLoading(@Coerce Object value)
    {
        var region = (AreaMapRegionAccess)value;
        if (!region.projectseele$loading()) return false;
        if (projectseele$undergroundView) return false;
        if (projectseele$layer == null || !projectseele$layer.id().equals("surface") || projectseele$showNativeDetail()) return true;
        double side = 512L << region.projectseele$level();
        double x = (region.projectseele$x() + 0.5) * side, z = (region.projectseele$z() + 0.5) * side;
        var b = projectseele$layer.bounds();
        return x < b.minX() || x >= b.maxX() || z < b.minZ() || z >= b.maxZ();
    }

    @ModifyArg(method = {"render", "m_88315_"}, at = @At(value = "INVOKE", target = LABEL, ordinal = 0), index = 2)
    private String projectseele$floorCoordinates(String nativeCoords)
    {
        if (!projectseele$undergroundView) return nativeCoords;
        String y = mouseBlockPosY == Short.MAX_VALUE ? "" : " Y: " + mouseBlockPosY;
        return "X: " + mouseBlockPosX + y + " Z: " + mouseBlockPosZ;
    }

    @ModifyArg(method = {"render", "m_88315_"}, at = @At(value = "INVOKE", target = LABEL, ordinal = 1), index = 2)
    private String projectseele$floorName(String nativeBiome)
    {
        return projectseele$undergroundView ? projectseele$layer.label() : nativeBiome;
    }

    @Inject(method = {"removed", "m_7861_"}, at = @At("HEAD"))
    private void projectseele$restoreNativeZoom(CallbackInfo ci)
    {
        if (!projectseele$ownsZoom) return;
        projectseele$resumeZoom = destScale;
        destScale = projectseele$nativeZoom;
        projectseele$ownsZoom = false;
    }
}

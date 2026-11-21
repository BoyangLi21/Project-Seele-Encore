package com.projectseele.client.map;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferUploader;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.math.Axis;
import com.projectseele.ProjectSeele;
import java.util.LinkedHashSet;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.resources.ResourceKey;
import net.minecraft.util.Mth;
import net.minecraft.world.level.Level;

public final class AreaMapDisplay
{
    private record Marker(double x, double z, int color) {}
    private static final LinkedHashSet<Marker> markers = new LinkedHashSet<>();
    private static boolean collecting;
    private static final boolean TRACE = Boolean.getBoolean("projectseele.areaMapTrace");
    private static String lastMini, lastFull;

    private AreaMapDisplay() {}

    public static void startMinimap()
    {
        markers.clear();
        var mc = Minecraft.getInstance();
        collecting = mc.level != null && AreaMapAtlas.current(mc.level.dimension()) != null;
    }

    public static boolean collectingMarkers() { return collecting; }

    public static void waypoint(double x, double z, int color)
    {
        if (collecting) markers.add(new Marker(x, z, color | 0xff000000));
    }

    public static void finishMinimap(GuiGraphics graphics, int x, int y, int boxSize, float partial, ResourceKey<Level> dimension)
    {
        collecting = false;
        var layer = AreaMapAtlas.current(dimension);
        if (TRACE) lastMini = trace("minimap", layer, lastMini);
        if (layer == null || boxSize < 12) return;
        var player = Minecraft.getInstance().player;
        var bounds = layer.bounds();
        double px = Mth.lerp(partial, player.xo, player.getX());
        double pz = Mth.lerp(partial, player.zo, player.getZ());
        int padding = Math.max(1, boxSize / 40);
        int caption = Math.max(7, Math.min(11, boxSize / 8));
        double scale = layer.fit(boxSize - 2.0 * padding, boxSize - 2.0 * padding - caption);
        double mapW = bounds.width() * scale, mapH = bounds.depth() * scale;
        double left = x + (boxSize - mapW) * 0.5, top = y + (boxSize - caption - mapH) * 0.5;

        graphics.pose().pushPose();
        // The native map and its radar have finished. Cover its entire reserved box; its information lines are outside.
        graphics.pose().translate(0, 0, 300);
        graphics.fill(x, y, x + boxSize, y + boxSize, 0xff293036);
        graphics.fill(x + 1, y + 1, x + boxSize - 1, y + boxSize - 1, 0xff151b20);
        graphics.pose().pushPose();
        graphics.pose().translate(left, top, 1);
        graphics.pose().scale((float)mapW, (float)mapH, 1);
        graphics.blit(layer.preview(), 0, 0, 0, 0, 1, 1, 1, 1);
        graphics.pose().popPose();

        for (Marker marker : markers)
        {
            if (marker.x < bounds.minX() || marker.x >= bounds.maxX() || marker.z < bounds.minZ() || marker.z >= bounds.maxZ()) continue;
            int mx = (int)Math.round(left + (marker.x - bounds.minX()) * scale);
            int mz = (int)Math.round(top + (marker.z - bounds.minZ()) * scale);
            graphics.fill(mx - 1, mz - 1, mx + 2, mz + 2, 0xff141414);
            graphics.fill(mx, mz, mx + 1, mz + 1, marker.color);
        }
        graphics.flush();
        graphics.pose().pushPose();
        graphics.pose().translate(left + (px - bounds.minX()) * scale, top + (pz - bounds.minZ()) * scale, 3);
        graphics.pose().mulPose(Axis.ZP.rotationDegrees(180 + player.getViewYRot(partial)));
        arrow(graphics, Math.max(2.3f, Math.min(4.0f, boxSize / 24f)));
        graphics.pose().popPose();
        var font = Minecraft.getInstance().font;
        float textScale = Math.min(1f, (caption - 1f) / font.lineHeight);
        graphics.pose().translate(x + padding + 1, y + boxSize - caption, 3);
        graphics.pose().scale(textScale, textScale, 1);
        int textWidth = (int)((boxSize - 2 * padding - 2) / textScale);
        graphics.drawString(font, font.plainSubstrByWidth(layer.label(), Math.max(0, textWidth - 9)),
                0, 0, 0xffeff3f5, false);
        graphics.drawString(font, "N", textWidth - font.width("N"), 0, 0xffa7bdc3, false);
        graphics.pose().popPose();
        graphics.flush();
    }

    private static void arrow(GuiGraphics graphics, float radius)
    {
        RenderSystem.setShader(GameRenderer::getPositionColorShader);
        var buffer = Tesselator.getInstance().getBuilder();
        var matrix = graphics.pose().last().pose();
        buffer.begin(VertexFormat.Mode.TRIANGLES, DefaultVertexFormat.POSITION_COLOR);
        for (int i = 0; i < 2; i++)
        {
            float r = radius * (i == 0 ? 1.15f : 0.78f);
            int color = i == 0 ? 0xff12191d : 0xfff7ffff;
            buffer.vertex(matrix, 0, -r, i).color(color).endVertex();
            buffer.vertex(matrix, -0.72f * r, 0.78f * r, i).color(color).endVertex();
            buffer.vertex(matrix, 0.72f * r, 0.78f * r, i).color(color).endVertex();
        }
        BufferUploader.drawWithShader(buffer.end());
    }

    /** At both insertion points Xaero has bound its terrain FBO and its pose is in whole world blocks. */
    public static void worldTerrain(GuiGraphics graphics, AreaMapLayer layer, double cameraX, double cameraZ, boolean underground)
    {
        if (TRACE) lastFull = trace("world map", layer, lastFull);
        if (layer == null) return;
        var bounds = layer.bounds();
        if (underground)
        {
            // This is Xaero's terrain-only framebuffer. Its controls, player arrow, waypoint and selection overlays
            // are drawn afterwards. Below the city, the unused part of this floor has no surveyed surface imagery.
            RenderSystem.clearColor(21 / 255f, 30 / 255f, 35 / 255f, 1);
            RenderSystem.clear(org.lwjgl.opengl.GL11.GL_COLOR_BUFFER_BIT, Minecraft.ON_OSX);
            RenderSystem.clearColor(0, 0, 0, 1);
        }
        var pose = graphics.pose();
        pose.pushPose();
        pose.translate(bounds.minX() - Math.floor(cameraX), bounds.minZ() - Math.floor(cameraZ), 0);
        pose.scale(bounds.width(), bounds.depth(), 1);
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.disableCull();
        RenderSystem.depthMask(false);
        RenderSystem.setShaderColor(1, 1, 1, 1);
        graphics.blit(layer.texture(), 0, 0, 0, 0, 1, 1, 1, 1);
        RenderSystem.depthMask(true);
        RenderSystem.enableCull();
        pose.popPose();
    }

    static String trace(String display, AreaMapLayer layer, String previous)
    {
        String name = layer == null ? "native" : layer.id();
        if (!name.equals(previous)) ProjectSeele.LOGGER.info("Area map {} = {}", display, name);
        return name;
    }
}

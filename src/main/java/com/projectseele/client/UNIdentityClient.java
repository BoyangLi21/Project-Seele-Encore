package com.projectseele.client;
import com.projectseele.ProjectSeele;
import com.google.gson.JsonParser;
import com.mojang.blaze3d.platform.NativeImage;
import com.mojang.math.Axis;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.DynamicTexture;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.core.BlockPos;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Insignia sit just outside measured wall/hull faces and never add collision. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class UNIdentityClient
{
    private record Plate(Vec3 p,float width,float height,float yaw,BlockPos support) {}
    private static final ResourceLocation TEXTURE=new ResourceLocation("projectseele","local/un_emblem_r11");
    private static List<Plate> plates;private static DynamicTexture texture;private static float imageAspect=1;
    public static ResourceLocation logoTexture()
    {
        if(plates==null)load();
        return texture==null?new ResourceLocation("projectseele","textures/entity/un_door_mark.png"):TEXTURE;
    }
    private static void load()
    {
        plates=new ArrayList<>();Path base=Path.of("projectseele-local-maps");
        try(var in=Files.newInputStream(base.resolve("un_emblem.png")))
        {
            var pixels=NativeImage.read(in);imageAspect=pixels.getWidth()/(float)pixels.getHeight();texture=new DynamicTexture(pixels);Minecraft.getInstance().getTextureManager().register(TEXTURE,texture);var data=JsonParser.parseString(Files.readString(base.resolve("un_markings_r11.json"))).getAsJsonObject();
            for(var value:data.getAsJsonArray("plates")){var d=value.getAsJsonObject();var p=d.getAsJsonArray("position");var s=d.getAsJsonArray("support");plates.add(new Plate(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),d.get("width").getAsFloat(),d.get("height").getAsFloat(),d.get("yaw").getAsFloat(),new BlockPos(s.get(0).getAsInt(),s.get(1).getAsInt(),s.get(2).getAsInt())));}
        }
        catch(Exception e){ProjectSeele.LOGGER.warn("Local UN insignia not installed",e);}
    }
    @SubscribeEvent public static void draw(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_ENTITIES)return;var mc=Minecraft.getInstance();if(mc.level==null||mc.getSingleplayerServer()==null||!mc.level.dimension().location().toString().equals("projectseele:geofront")||!mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals("SEELE_TV_WORLD_PREVIEW_20260906"))return;
        if(plates==null)load();if(texture==null||plates.isEmpty())return;var buffers=mc.renderBuffers().bufferSource();var type=RenderType.entityCutoutNoCull(TEXTURE);var vertex=buffers.getBuffer(type);var stack=event.getPoseStack();var cam=event.getCamera().getPosition();boolean drew=false;
        for(var p:plates)
        {
            if(cam.distanceToSqr(p.p)>420*420||!mc.level.hasChunkAt(p.support)||mc.level.getBlockState(p.support).isAir())continue;
            stack.pushPose();stack.translate(p.p.x-cam.x,p.p.y-cam.y,p.p.z-cam.z);stack.mulPose(Axis.YP.rotationDegrees(p.yaw));float w=p.width/2,h=Math.min(p.height,p.width/imageAspect)/2;int light=net.minecraft.client.renderer.LevelRenderer.getLightColor(mc.level,p.support.relative(net.minecraft.core.Direction.fromYRot(-p.yaw)));
            float[][] corners={{w,-h,1,1},{-w,-h,0,1},{-w,h,0,0},{w,h,1,0}};
            for(var c:corners)vertex.vertex(stack.last().pose(),c[0],c[1],0).color(255,255,255,255).uv(c[2],c[3]).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(stack.last().normal(),0,0,1).endVertex();stack.popPose();drew=true;
        }
        if(drew)buffers.endBatch(type);
    }
    private UNIdentityClient() {}
}

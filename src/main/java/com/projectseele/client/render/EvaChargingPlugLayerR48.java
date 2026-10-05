package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaPowerPortsR48;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.layer.GeoRenderLayer;

/** Normal entity/shadow pass; no deferred unlit duplicate and no body-witness pollution. */
final class EvaChargingPlugLayerR48 extends GeoRenderLayer<EvaUnit01Entity>
{
    private static final ResourceLocation TEXTURE=new ResourceLocation("projectseele","textures/entity/tripo_charger_r48.png");
    private static final ResourceLocation[] MESH={
            new ResourceLocation("projectseele","mesh/eva_charger_unit00_r48.mesh.json"),
            new ResourceLocation("projectseele","mesh/eva_charger_unit01_r48.mesh.json"),
            new ResourceLocation("projectseele","mesh/eva_charger_unit02_r48.mesh.json")};
    EvaChargingPlugLayerR48(EvaUnit01Renderer renderer){super(renderer);}
    @Override public void renderForBone(PoseStack poses,EvaUnit01Entity entity,GeoBone bone,RenderType type,
                                        MultiBufferSource buffers,VertexConsumer ignored,float partial,int light,int overlay)
    {
        if(!bone.getName().equals("torso_upper")||bone.isHidden()||!entity.isUmbilicalConnected()
                ||EvaPowerPortsR48.of(entity)==null)return;
        LocalTriangleMeshLayer.renderRigidAttachment(poses,buffers,MESH[entity.getUnitVariant()],TEXTURE,
                "torso_upper",light,overlay);
    }
}

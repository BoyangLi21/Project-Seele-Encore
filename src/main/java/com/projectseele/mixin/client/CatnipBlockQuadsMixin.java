package com.projectseele.mixin.client;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.render.TerrainQuadWriter;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/**
 * Hands the vertices of a Create mesh (a moving contraption, such as a city district on its way up or down) to
 * {@link TerrainQuadWriter}. All three hooks are optional: with any of them missing every vertex still reaches the
 * buffer the usual way.
 */
@Pseudo
@Mixin(targets="net.createmod.catnip.render.ShadeSeparatingSuperByteBuffer",remap=false)
public abstract class CatnipBlockQuadsMixin
{
    @Inject(method="renderInto",at=@At("HEAD"),remap=false,require=0)
    private void seele$beginMesh(PoseStack pose,VertexConsumer buffer,CallbackInfo callback)
    {TerrainQuadWriter.begin(buffer);}

    @Redirect(method="renderInto",at=@At(value="INVOKE",target="Lcom/mojang/blaze3d/vertex/VertexConsumer;vertex(FFFFFFFFFIIFFF)V",remap=true),remap=false,require=0)
    private void seele$meshVertex(VertexConsumer buffer,float x,float y,float z,float r,float g,float b,float a,float u,float v,int overlay,int light,float nx,float ny,float nz)
    {TerrainQuadWriter.vertex(buffer,x,y,z,r,g,b,a,u,v,overlay,light,nx,ny,nz);}

    @Inject(method="renderInto",at=@At("RETURN"),remap=false,require=0)
    private void seele$endMesh(PoseStack pose,VertexConsumer buffer,CallbackInfo callback)
    {TerrainQuadWriter.end();}
}

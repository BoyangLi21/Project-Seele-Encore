package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.client.TreeOfLifeWallClient;
import com.projectseele.entity.NervHangarDoorEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.client.renderer.texture.TextureAtlas;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import org.joml.Matrix3f;
import org.joml.Matrix4f;

/** Paired sideways pressure doors at the rear of each wet cage. */
public final class NervHangarDoorRenderer
        extends EntityRenderer<NervHangarDoorEntity>
{
    private static final BlockState DOOR =
            Blocks.DEEPSLATE_TILES.defaultBlockState();

    public NervHangarDoorRenderer(EntityRendererProvider.Context context)
    {
        super(context);
        this.shadowRadius = 0.0F;
    }

    @Override
    public boolean shouldRender(NervHangarDoorEntity entity, Frustum frustum,
            double cameraX, double cameraY, double cameraZ)
    {
        /*
         * The server entity deliberately owns a one-block AABB, while its two
         * visual leaves span up to 67 x 65 blocks.  Testing only the origin
         * made a door vanish when the camera saw a leaf but not that origin.
         * At most three transient gates exist, so keeping tracked gates
         * renderable is deterministic and cheaper than a giant server AABB.
         */
        return true;
    }

    @Override
    public void render(NervHangarDoorEntity door, float yaw,
            float partialTick, PoseStack poses, MultiBufferSource buffers,
            int packedLight)
    {
        int facilityLight = packedLight;
        if(door.isSectionalUNGate())
        {
            sectionalUN(door,partialTick,poses,buffers,facilityLight);
            super.render(door,yaw,partialTick,poses,buffers,packedLight);
            return;
        }
        double slide = door.getOpenProgress(partialTick) * 17.0D;
        poses.pushPose();
        poses.scale(1,door.visualHeight()/65F,1);
        TvFacilityMeshes.withBuffers(buffers,()->TvFacilityMeshes.pressureDoors(poses,facilityLight,door.getOpenProgress(partialTick)));
        splitLogo(poses, buffers, slide,door.getVariant()==3,facilityLight);
        poses.popPose();
        super.render(door, yaw, partialTick, poses, buffers, packedLight);
    }

    private static void sectionalUN(NervHangarDoorEntity door,float partialTick,
            PoseStack poses,MultiBufferSource buffers,int light)
    {
        double width=door.visualWidth(),height=door.visualHeight(),section=height/4.0;
        double progress=door.getOpenProgress(partialTick);
        progress=progress*progress*(3-2*progress);
        // All four leaves remain inside the enclosed Y142..160 header. Unlike
        // a widened sideways gate, their sweep cannot cross the personnel door.
        NervDoorFinish.frame(poses,buffers,light,width/2,height,progress>.99);
        for(int i=0;i<4;i++)
        {
            double base=i*section,lift=(height-base)*progress,z=-.30+i*.68;
            double y=base+lift;
            NervDoorFinish.leaf(poses,buffers,light,-width/2,y,z,width,section+.04,.60,true);
            for(int column=1;column<4;column++)
                NervDoorFinish.leaf(poses,buffers,light,-width/2+column*width/4-.05,y+.15,z-.04,.10,section-.35,.045,false);
            unLogoSection(poses,buffers,base,base+section,lift,z,light);
        }
        for(int side:new int[]{-1,1})
            NervDoorFinish.leaf(poses,buffers,light,side<0?-width/2-.55:width/2+.10,0,-.4,.45,height+section,2.8,true);
    }

    private static void unLogoSection(PoseStack poses,MultiBufferSource buffers,
            double bottom,double top,double lift,double z,int light)
    {
        double low=Math.max(20,bottom),high=Math.min(44,top);
        if(high<=low)return;
        ResourceLocation texture=com.projectseele.client.UNIdentityClient.logoTexture();
        if(texture==null)return;
        var out=buffers.getBuffer(RenderType.entityCutout(texture));
        var pose=poses.last().pose();var normal=poses.last().normal();
        float vTop=(float)((44-high)/24),vBottom=(float)((44-low)/24);
        // Each slice travels with its own leaf, preserving the full mark when shut.
        vertex(out,pose,normal,-12,high+lift,z-.012,1,vTop,light,-1);
        vertex(out,pose,normal,12,high+lift,z-.012,0,vTop,light,-1);
        vertex(out,pose,normal,12,low+lift,z-.012,0,vBottom,light,-1);
        vertex(out,pose,normal,-12,low+lift,z-.012,1,vBottom,light,-1);
        vertex(out,pose,normal,12,high+lift,z+.615,1,vTop,light,1);
        vertex(out,pose,normal,-12,high+lift,z+.615,0,vTop,light,1);
        vertex(out,pose,normal,-12,low+lift,z+.615,0,vBottom,light,1);
        vertex(out,pose,normal,12,low+lift,z+.615,1,vBottom,light,1);
    }

    private static void splitLogo(PoseStack poses,
            MultiBufferSource buffers, double slide,boolean unitedNations,int light)
    {
        ResourceLocation texture = unitedNations?com.projectseele.client.UNIdentityClient.logoTexture()
                :TreeOfLifeWallClient.nervLogoTexture(Minecraft.getInstance());
        if (texture == null) return;
        VertexConsumer consumer = buffers.getBuffer(
                RenderType.entityCutout(texture));
        double bottom=unitedNations?20:18,top=unitedNations?44:46;
        logoHalf(poses, consumer, -12.0D - slide, -slide,
                bottom, top, -0.61D, 1.0F, 0.5F,light);
        logoHalf(poses, consumer, slide, 12.0D + slide,
                bottom, top, -0.61D, 0.5F, 0.0F,light);
        // Opposite face has its own winding and UVs, so the exterior approach
        // reads the same word instead of seeing the reverse of an inner decal.
        logoHalf(poses,consumer,-slide,-12.0D-slide,bottom,top,.61D,.5F,0F,light);
        logoHalf(poses,consumer,12.0D+slide,slide,bottom,top,.61D,1F,.5F,light);
    }

    private static void logoHalf(PoseStack poses, VertexConsumer consumer,
            double x0, double x1, double y0, double y1, double z,
            float u0, float u1,int light)
    {
        Matrix4f matrix = poses.last().pose();
        Matrix3f normal = poses.last().normal();
        float normalZ=z<0?-1:1;
        vertex(consumer, matrix, normal, x0, y1, z, u0, 0.0F,light,normalZ);
        vertex(consumer, matrix, normal, x1, y1, z, u1, 0.0F,light,normalZ);
        vertex(consumer, matrix, normal, x1, y0, z, u1, 1.0F,light,normalZ);
        vertex(consumer, matrix, normal, x0, y0, z, u0, 1.0F,light,normalZ);
    }

    private static void vertex(VertexConsumer consumer, Matrix4f pose,
            Matrix3f normal, double x, double y, double z, float u, float v,int light,float normalZ)
    {
        consumer.vertex(pose, (float)x, (float)y, (float)z)
                .color(255, 255, 255, 255).uv(u, v)
                .overlayCoords(OverlayTexture.NO_OVERLAY)
                .uv2(light).normal(normal, 0.0F, 0.0F, normalZ)
                .endVertex();
    }

    private static void panel(PoseStack poses, MultiBufferSource buffers,
            int light, double x, double y, double z,
            float sx, float sy, float sz)
    {
        NervDoorFinish.leaf(poses,buffers,light,x,y,z,sx,sy,sz,true);
    }

    @Override
    public ResourceLocation getTextureLocation(NervHangarDoorEntity entity)
    {
        return TextureAtlas.LOCATION_BLOCKS;
    }
}

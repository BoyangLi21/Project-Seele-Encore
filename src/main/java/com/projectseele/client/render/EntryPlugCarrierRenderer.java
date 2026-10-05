package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaScale;
import com.projectseele.world.EntryPlugKinematics;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/** Renders the reviewed local entry-plug mesh as an independent carrier. */
public final class EntryPlugCarrierRenderer
        extends GeoEntityRenderer<EntryPlugCarrierEntity>
{
    private static final ResourceLocation GEOMETRY =
            resource("geo/entry_plug_carrier.geo.json");
    private static final ResourceLocation ANIMATION =
            resource("animations/entry_plug_carrier.animation.json");
    private static final ResourceLocation[] MESHES = {
            resource("mesh/entry_plug_unit00.mesh.json"),
            resource("mesh/entry_plug_unit01.mesh.json"),
            resource("mesh/entry_plug_unit02.mesh.json"),
    };
    private static final ResourceLocation[] LOCAL_TEXTURES = {
            resource("textures/entity/entry_plug_unit00.png"),
            resource("textures/entity/entry_plug_unit01.png"),
            resource("textures/entity/entry_plug_unit02.png"),
    };
    private static final ResourceLocation FALLBACK_TEXTURE =
            minecraftResource("textures/block/white_concrete.png");
    public EntryPlugCarrierRenderer(EntityRendererProvider.Context context)
    {
        super(context, new LocalAddonGeoModel<>(GEOMETRY,
                FALLBACK_TEXTURE, ANIMATION));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EntryPlugCarrierRenderer::unitMesh,
                EntryPlugCarrierRenderer::unitTexture));
        this.withScale(EvaScale.ENTRY_PLUG_RENDER_SCALE);
        this.shadowRadius = 1.0F;
    }

    @Override
    public void render(EntryPlugCarrierEntity animatable, float entityYaw,
                       float partialTick, PoseStack poseStack,
                       MultiBufferSource bufferSource, int packedLight)
    {
        // The persistent carrier still exists and holds the pilot while seated,
        // but the external shell is physically inside the airframe.
        if (!animatable.isShellVisible())
        {
            return;
        }
        SynchCradleRendererR47.render(poseStack,bufferSource,animatable,partialTick,packedLight);
        super.render(animatable, entityYaw, partialTick, poseStack,
                bufferSource, packedLight);
    }

    @Override
    public boolean shouldRender(EntryPlugCarrierEntity entity,
                                Frustum frustum,
                                double cameraX, double cameraY,
                                double cameraZ)
    {
        /*
         * The visible shell is ten blocks long while the PathfinderMob AABB
         * is intentionally tiny.  Frustum testing that tiny origin box made
         * the capsule disappear when a player stood beside its flank, tail or
         * hatch.  There are at most three carriers, so rendering every visible
         * shell is both deterministic and negligible.
         */
        return entity.isShellVisible() || super.shouldRender(entity, frustum,
                cameraX, cameraY, cameraZ);
    }

    @Override
    public net.minecraft.world.phys.Vec3 getRenderOffset(EntryPlugCarrierEntity entity,float partial)
    {
        var base=super.getRenderOffset(entity,partial);
        if(!entity.hasCanonicalPose())return base;
        var dispatcher=new net.minecraft.world.phys.Vec3(
                net.minecraft.util.Mth.lerp((double)partial,entity.xOld,entity.getX()),
                net.minecraft.util.Mth.lerp((double)partial,entity.yOld,entity.getY()),
                net.minecraft.util.Mth.lerp((double)partial,entity.zOld,entity.getZ()));
        return base.add(entity.getInterpolatedCanonicalTransform(partial).translation().subtract(dispatcher));
    }

    @Override
    protected void applyRotations(EntryPlugCarrierEntity animatable,
                                  PoseStack poseStack, float ageInTicks,
                                  float rotationYaw, float partialTick)
    {
        if (!animatable.hasCanonicalPose())
        {
            super.applyRotations(animatable, poseStack, ageInTicks,
                    rotationYaw, partialTick);
            return;
        }
        poseStack.mulPose(animatable.getCanonicalRotation(partialTick));
    }

    public org.joml.Matrix4f renderedMeshTransform(org.joml.Matrix4f pose,EntryPlugCarrierEntity plug,float partial)
    {
        var world=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(pose,this.entityRenderTranslations);
        var origin=new net.minecraft.world.phys.Vec3(net.minecraft.util.Mth.lerp((double)partial,plug.xOld,plug.getX()),net.minecraft.util.Mth.lerp((double)partial,plug.yOld,plug.getY()),net.minecraft.util.Mth.lerp((double)partial,plug.zOld,plug.getZ())).add(getRenderOffset(plug,partial));
        world.m30(world.m30()+(float)origin.x).m31(world.m31()+(float)origin.y).m32(world.m32()+(float)origin.z);return world;
    }

    @Override
    public void preRender(PoseStack poseStack,
                          EntryPlugCarrierEntity animatable,
                          BakedGeoModel model,
                          net.minecraft.client.renderer.MultiBufferSource bufferSource,
                          VertexConsumer buffer, boolean isReRender,
                          float partialTick, int packedLight, int packedOverlay,
                          float red, float green, float blue, float alpha)
    {
        super.preRender(poseStack, animatable, model, bufferSource, buffer,
                isReRender, partialTick, packedLight, packedOverlay,
                red, green, blue, alpha);
        float hatch = animatable.getHatchOpenAmount();
        model.getBone("plug_hatch_l").ifPresent(bone ->
        {
            bone.setPosX(0.0F);
            bone.setRotZ((float) Math.toRadians(
                    EntryPlugKinematics.HATCH_OPEN_ANGLE_DEGREES * hatch));
        });
        model.getBone("plug_hatch_r").ifPresent(bone ->
        {
            bone.setPosX(0.0F);
            bone.setRotZ((float) Math.toRadians(
                    -EntryPlugKinematics.HATCH_OPEN_ANGLE_DEGREES * hatch));
        });
        // The collar belongs to the wet-cage crane. It follows the capsule
        // throughout controlled insertion/ejection, but must not be thrown
        // across the battlefield by an emergency pyrotechnic ejection.
        int stage = animatable.getInsertionStage();
        boolean fieldEjected = stage
                == EntryPlugCarrierEntity.STAGE_FIELD_EJECTING
                || stage == EntryPlugCarrierEntity.STAGE_FIELD_LANDED;
        model.getBone("plug_crane_collar").ifPresent(bone ->
                bone.setHidden(true));
    }

    @Override
    public void renderCubesOfBone(PoseStack poseStack, GeoBone bone,
                                  VertexConsumer buffer, int packedLight,
                                  int packedOverlay, float red, float green,
                                  float blue, float alpha)
    {
        if (LocalTriangleMeshLayer.hasPart(MESHES[0], bone.getName()))
        {
            return;
        }
        super.renderCubesOfBone(poseStack, bone, buffer, packedLight,
                packedOverlay, red, green, blue, alpha);
    }

    @Override
    public ResourceLocation getTextureLocation(EntryPlugCarrierEntity entity)
    {
        return FALLBACK_TEXTURE;
    }

    private static ResourceLocation unitTexture(EntryPlugCarrierEntity entity)
    {
        if(entity.isIndependentUNPlug())return resource("textures/entity/entry_plug_un.png");
        int variant = Math.max(0, Math.min(2, entity.getAssignedVariant()));
        return LOCAL_TEXTURES[variant];
    }

    private static ResourceLocation unitMesh(EntryPlugCarrierEntity entity)
    {
        if(entity.isIndependentUNPlug())return resource("mesh/entry_plug_un.mesh.json");
        int variant = Math.max(0, Math.min(2, entity.getAssignedVariant()));
        return MESHES[variant];
    }

    @SuppressWarnings("removal")
    private static ResourceLocation resource(String path)
    {
        return new ResourceLocation(ProjectSeele.MODID, path);
    }

    @SuppressWarnings("removal")
    private static ResourceLocation minecraftResource(String path)
    {
        return new ResourceLocation("minecraft", path);
    }
}

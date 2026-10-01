package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.MassProductionEvaEntity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.LivingEntity;
import software.bernie.geckolib.animatable.GeoEntity;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/** Uses a local high-detail Gecko model when installed, otherwise the original fallback renderer. */
public class HybridAddonRenderer<T extends LivingEntity & GeoEntity> extends EntityRenderer<T>
{
    private final ColossalHumanoidRenderer<T> fallback;
    private final GeoEntityRenderer<T> detailed;
    private final ResourceLocation geometry;
    private final ResourceLocation texture;
    private final ResourceLocation animation;
    private final ResourceLocation mesh;
    private final String assetName;
    private boolean strictFailureReported;

    public HybridAddonRenderer(EntityRendererProvider.Context context,
                               ColossalHumanoidRenderer.Style fallbackStyle,
                               String assetName, float scale)
    {
        super(context);
        this.assetName = assetName;
        this.geometry = new ResourceLocation(ProjectSeele.MODID, "geo/" + assetName + ".geo.json");
        this.texture = new ResourceLocation(ProjectSeele.MODID, "textures/entity/" + assetName + ".png");
        this.animation = new ResourceLocation(ProjectSeele.MODID, "animations/" + assetName + ".animation.json");
        this.mesh = new ResourceLocation(ProjectSeele.MODID, "mesh/" + assetName + ".mesh.json");
        this.fallback = new ColossalHumanoidRenderer<>(context, fallbackStyle);
        this.detailed = new MeshBackedRenderer<>(context,
                new LocalAddonGeoModel<>(this.geometry, this.texture, this.animation), this.mesh,
                !assetName.equals("mass_production_eva"));
        this.detailed.withScale(scale);
        this.shadowRadius = fallbackStyle == ColossalHumanoidRenderer.Style.SACHIEL ? 3.8F : 4.5F;
    }

    private boolean hasDetailedResources()
    {
        var resources = Minecraft.getInstance().getResourceManager();
        return resources.getResource(this.geometry).isPresent()
                && resources.getResource(this.texture).isPresent()
                && resources.getResource(this.animation).isPresent()
                && resources.getResource(this.mesh).isPresent();
    }

    @Override
    public void render(T entity, float yaw, float partialTick, PoseStack poseStack,
                       MultiBufferSource buffers, int packedLight)
    {
        if(entity instanceof com.projectseele.entity.SachielEntity angel&&angel.isFirstBattleActive()
                &&angel.firstBattleSignals().time(angel,partialTick)>=18.65F)return;
        if (LocalVisualAssetFingerprint.isStrictMode()
                && "mass_production_eva".equals(this.assetName))
        {
            LocalVisualAssetFingerprint.Fingerprint fingerprint =
                    LocalVisualAssetFingerprint.inspect(this.assetName);
            if (!fingerprint.valid())
            {
                if (!this.strictFailureReported)
                {
                    this.strictFailureReported = true;
                    ProjectSeele.LOGGER.error(
                            "Strict high-detail hybrid render refused: {}",
                            fingerprint.description());
                }
                return;
            }
        }
        int effectiveLight = entity instanceof MassProductionEvaEntity mass
                && mass.isRitualFormation() ? LightTexture.FULL_BRIGHT : packedLight;
        if (hasDetailedResources())
        {
            this.detailed.render(entity, yaw, partialTick, poseStack, buffers, effectiveLight);
        }
        else
        {
            this.fallback.render(entity, yaw, partialTick, poseStack, buffers, effectiveLight);
        }
        if(entity instanceof com.projectseele.entity.ShamshelEntity angel)
            ShamshelWhipLight.render(angel,partialTick,poseStack,buffers);
    }

    @Override
    public boolean shouldRender(T entity, Frustum frustum, double cameraX,
                                double cameraY, double cameraZ)
    {
        if(entity instanceof com.projectseele.entity.Angel&&entity.shouldRender(cameraX,cameraY,cameraZ))
            return frustum.isVisible(entity.getBoundingBox().inflate(42,8,42));
        if (entity instanceof MassProductionEvaEntity
                && entity.shouldRender(cameraX, cameraY, cameraZ))
        {
            // The reviewed winged mesh spans roughly 40 x 47 x 17 blocks,
            // substantially beyond the 10 x 26 gameplay hitbox.  Test the
            // full visual envelope so ritual wings do not vanish at the edge
            // of the Third-Impact camera frustum.
            var visualBounds = entity.getBoundingBox()
                    .expandTowards(0.0D, 22.0D, 0.0D)
                    .inflate(16.0D, 1.0D, 10.0D);
            if (frustum.isVisible(visualBounds))
            {
                return true;
            }
        }
        return super.shouldRender(entity, frustum, cameraX, cameraY, cameraZ);
    }

    @Override
    public ResourceLocation getTextureLocation(T entity)
    {
        return hasDetailedResources() ? this.texture : this.fallback.getTextureLocation(entity);
    }
    @Override public net.minecraft.world.phys.Vec3 getRenderOffset(T entity,float partial)
    {
        return super.getRenderOffset(entity,partial).add(com.projectseele.entity.FirstBattleClip.renderOffset(entity,partial));
    }

    public LocalVisualAssetFingerprint.Fingerprint visualFingerprint()
    {
        return LocalVisualAssetFingerprint.inspect(this.assetName);
    }

    static final class MeshBackedRenderer<T extends LivingEntity & GeoEntity>
            extends GeoEntityRenderer<T>
    {
        @Override public int getPackedOverlay(T entity,float partial){return entity instanceof com.projectseele.entity.Angel?net.minecraft.client.renderer.texture.OverlayTexture.NO_OVERLAY:super.getPackedOverlay(entity,partial);}
        @Override public int getPackedOverlay(T entity,float white,float partial){return entity instanceof com.projectseele.entity.Angel?net.minecraft.client.renderer.texture.OverlayTexture.NO_OVERLAY:super.getPackedOverlay(entity,white,partial);}
        private final ResourceLocation mesh;

        MeshBackedRenderer(EntityRendererProvider.Context context, LocalAddonGeoModel<T> model,
                           ResourceLocation mesh,boolean weightedCandidate)
        {
            super(context, model);
            this.mesh = mesh;
            this.addRenderLayer(new LocalTriangleMeshLayer<>(this, entity -> this.mesh,null,
                    (entity,bone)->{
                        boolean available=!weightedCandidate||RiggedAngelLayer.available(this.mesh);
                        if(weightedCandidate&&!available)RiggedAngelSkinWitnessR44.fallback(entity,this.mesh,bone.getName());
                        return !weightedCandidate||!available;
                    }));
            if(weightedCandidate)this.addRenderLayer(new RiggedAngelLayer<>(this,this.mesh));
        }

        org.joml.Matrix4f renderedMeshTransform(org.joml.Matrix4f pose,net.minecraft.world.entity.Entity entity,float partial)
        {
            var world=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(pose,this.entityRenderTranslations);
            var origin=new net.minecraft.world.phys.Vec3(
                    net.minecraft.util.Mth.lerp((double)partial,entity.xOld,entity.getX()),
                    net.minecraft.util.Mth.lerp((double)partial,entity.yOld,entity.getY()),
                    net.minecraft.util.Mth.lerp((double)partial,entity.zOld,entity.getZ()))
                    .add(com.projectseele.entity.FirstBattleClip.renderOffset(entity,partial));
            world.m30(world.m30()+(float)origin.x).m31(world.m31()+(float)origin.y).m32(world.m32()+(float)origin.z);return world;
        }

        @Override protected void applyRotations(T entity,PoseStack pose,float age,float yaw,float partial)
        {
            if(entity instanceof com.projectseele.entity.FirstBattleSignals.Actor actor&&actor.firstBattleSignals().active(entity))
                yaw=com.projectseele.entity.FirstBattleClip.yaw(actor.firstBattleSignals().spec(entity),actor.isFirstBattleEva(),actor.firstBattleSignals().time(entity,partial));
            super.applyRotations(entity,pose,age,yaw,partial);
        }

        @Override public void preRender(PoseStack pose,T entity,software.bernie.geckolib.cache.object.BakedGeoModel model,
                MultiBufferSource buffers,VertexConsumer vertex,boolean rerender,float partial,int light,int overlay,float red,float green,float blue,float alpha)
        {
            if(!rerender)AngelCombatPoseR31.restoreBeforeGecko(entity,model);
            super.preRender(pose,entity,model,buffers,vertex,rerender,partial,light,overlay,red,green,blue,alpha);
        }

        @Override
        public void renderCubesOfBone(PoseStack poseStack, GeoBone bone, VertexConsumer buffer,
                                      int packedLight, int packedOverlay, float red, float green,
                                      float blue, float alpha)
        {
            T animatable = this.getAnimatable();
            if ("replica_lance".equals(bone.getName())
                    && animatable instanceof MassProductionEvaEntity mass
                    && (mass.isReviving() || mass.isRitualFormation()
                        || mass.getVisualPose() == MassProductionEvaEntity.VISUAL_REVIVE))
            {
                return;
            }
            if (LocalTriangleMeshLayer.hasPart(this.mesh, bone.getName()))
            {
                return;
            }
            super.renderCubesOfBone(poseStack, bone, buffer, packedLight, packedOverlay,
                    red, green, blue, alpha);
        }
    }
}

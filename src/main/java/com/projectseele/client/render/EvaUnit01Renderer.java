package com.projectseele.client.render;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.function.Consumer;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.client.ClientForgeEvents;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaScale;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.culling.Frustum;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;
import org.jetbrains.annotations.Nullable;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.renderer.GeoEntityRenderer;

/**
 * GeckoLib-driven EVA renderer.
 *
 * GeckoLib is the sole authority for body and arm poses. First person observes
 * this same world-space skeleton from the pilot's head socket. Only mesh
 * shells that physically enclose the camera are suppressed. The sole special
 * case is the building-sized positron cannon: its first-person geometry is
 * stowed in favour of the entry-plug optical feed; third person remains the
 * authoritative world skeleton. There is no detached arm viewmodel.
 */
public class EvaUnit01Renderer extends GeoEntityRenderer<EvaUnit01Entity>
{
    @Override public int getPackedOverlay(EvaUnit01Entity entity,float partial){return net.minecraft.client.renderer.texture.OverlayTexture.NO_OVERLAY;}
    @Override public int getPackedOverlay(EvaUnit01Entity entity,float white,float partial){return net.minecraft.client.renderer.texture.OverlayTexture.NO_OVERLAY;}
    private static final Map<Integer, MuzzleSample> RIFLE_MUZZLES =
            new HashMap<>();
    private static final long MUZZLE_STALE_NANOS = 100_000_000L;
    private static final ResourceLocation MESH_00 =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva_unit00.mesh.json");
    private static final ResourceLocation MESH_01 =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva_unit01.mesh.json");
    private static final ResourceLocation MESH_02 =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva_unit02.mesh.json");
    private static final ResourceLocation TEXTURE_00 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit00.png");
    private static final ResourceLocation TEXTURE_01 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit01.png");
    private static final ResourceLocation TEXTURE_02 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit02.png");
    private static final ResourceLocation EYES_00 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit00_eyes.png");
    private static final ResourceLocation EYES_01 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit01_eyes.png");
    private static final ResourceLocation EYES_02 =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_unit02_eyes.png");
    private static final ResourceLocation POSITRON_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/positron_cannon.mesh.json");
    private static final ResourceLocation POSITRON_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/positron_cannon.png");
    private static final ResourceLocation RIFLE_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva_pallet_smg.mesh.json");
    private static final ResourceLocation RIFLE_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_pallet_smg.png");
    private static final ResourceLocation N2_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva_n2_device.mesh.json");
    private static final ResourceLocation N2_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva_n2_device.png");
    private static final ResourceLocation COMMON_KNIFE_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/progressive_knife.mesh.json");
    private static final ResourceLocation COMMON_KNIFE_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/progressive_knife.png");
    private static final ResourceLocation UNIT02_KNIFE_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva02_knife.mesh.json");
    private static final ResourceLocation UNIT02_SPECIAL_WEAPON_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/eva02_special_weapon.mesh.json");
    private static final ResourceLocation UNIT02_WEAPONS_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/eva02_weapons.png");
    private static final ResourceLocation ENTRY_PLUG_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/entry_plug.mesh.json");
    private static final ResourceLocation ENTRY_PLUG_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/entry_plug.png");
    private static final ResourceLocation LONGINUS_MESH =
            new ResourceLocation(ProjectSeele.MODID, "mesh/longinus_lance.mesh.json");
    private static final ResourceLocation LONGINUS_TEXTURE =
            new ResourceLocation(ProjectSeele.MODID, "textures/entity/longinus_lance.png");
    private static final Set<String> CAMERA_COVER_BONES = Set.of(
            "head", "Head", "horn", "Horn", "neck", "Neck", "r37_jaw", "r37_red_upper", "r37_red_lower", "r37_lining");
    private static final Set<String> PILOT_CAMERA_MESH_COVER = Set.of(
            "torso_lower", "torso_upper", "pylon_l", "pylon_r", "dorsal_cover", "dorsal_liner");
    private boolean pilotView;
    private BakedGeoModel pendingPoseModel;
    private EvaUnit01Entity pendingPoseEntity;
    private float pendingPosePartialTick;
    private boolean pendingPoseCommit;
    private boolean strictFailureReported;

    public static void rememberRifleMuzzle(int entityId, Vec3 position)
    {
        if (RIFLE_MUZZLES.size() > 24)
        {
            RIFLE_MUZZLES.clear();
        }
        RIFLE_MUZZLES.put(entityId,
                new MuzzleSample(position, System.nanoTime()));
    }

    public static Vec3 rifleMuzzleOrFallback(int entityId, Vec3 fallback)
    {
        MuzzleSample sample = RIFLE_MUZZLES.get(entityId);
        if (sample == null
                || System.nanoTime() - sample.capturedNanos()
                > MUZZLE_STALE_NANOS)
        {
            RIFLE_MUZZLES.remove(entityId);
            return fallback;
        }
        return sample.position();
    }

    public Vec3 renderedMeshPoint(org.joml.Matrix4f pose, org.joml.Vector3f point,
                                  EvaUnit01Entity eva, float partial)
    {
        // Gecko 4.8.4's world-matrix helper adds whole identity matrices. Undoing
        // the render origin directly preserves the actual vertex scale.
        var world = software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(
                pose, this.entityRenderTranslations).transformPosition(point);
        return renderedOrigin(eva,partial).add(world.x, world.y, world.z);
    }
    public org.joml.Matrix4f renderedMeshTransform(org.joml.Matrix4f pose,EvaUnit01Entity eva,float partial)
    {
        var world=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(pose,this.entityRenderTranslations);
        Vec3 p=renderedOrigin(eva,partial);world.m30(world.m30()+(float)p.x).m31(world.m31()+(float)p.y).m32(world.m32()+(float)p.z);return world;
    }
    private Vec3 renderedOrigin(EvaUnit01Entity eva,float partial)
    {
        // This is the exact LevelRenderer/dispatcher baseline. xo/yo/zo used
        // by getPosition can differ during authoritative vehicle corrections.
        return new Vec3(Mth.lerp((double)partial,eva.xOld,eva.getX()),
                Mth.lerp((double)partial,eva.yOld,eva.getY()),Mth.lerp((double)partial,eva.zOld,eva.getZ()))
                .add(getRenderOffset(eva,partial));
    }

    public EvaUnit01Renderer(EntityRendererProvider.Context context)
    {
        super(context, new EvaUnit01GeoModel());
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaUnit01Renderer::meshResourceForEntity,
                entity -> entity.isExperimentalUnit()?new ResourceLocation(ProjectSeele.MODID,"textures/entity/"+entity.experimentalAssetName()+".png"):textureResourceForVariant(entity.getUnitVariant()),
                this::shouldRenderBodyMesh));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaHandSurfaceR45::mesh,
                entity -> textureResourceForVariant(entity.getUnitVariant()),
                (entity,bone) -> EvaHandSurfaceR45.applies(entity)&&(bone.getName().startsWith("hand_")||bone.getName().startsWith("r45_hand_"))));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaUnit01Renderer::meshResourceForEntity,
                entity -> entity.isExperimentalUnit()?new ResourceLocation(ProjectSeele.MODID,"textures/entity/"+entity.experimentalAssetName()+"_eyes.png"):EvaEyeMaterialsR42.texture(entity,eyeTextureResourceForVariant(entity.getUnitVariant())),
                (entity, bone) -> !this.pilotView && (com.projectseele.entity.EvaDorsalMechanism.eyesEnabled(entity)
                        && "head".equals(bone.getName()) || entity instanceof com.projectseele.entity.EvaPrototypeEntity un
                        && un.getUNSerial()==1&&un.isUNFlying()&&bone.getName().startsWith("r30_thruster_")), true));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaUnit01Renderer::meshResourceForEntity,
                entity -> EvaEyeMaterialsR42.texture(entity,eyeTextureResourceForVariant(entity.getUnitVariant())),
                (entity, bone) -> !this.pilotView && !entity.isExperimentalUnit()
                        && entity.getUnitVariant()==EvaUnit01Entity.UNIT_01
                        && "head".equals(bone.getName())
                        && !com.projectseele.entity.EvaDorsalMechanism.eyesEnabled(entity)));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaUnit01Renderer::knifeMeshResource,
                EvaUnit01Renderer::knifeTextureResource,
                (entity, bone) -> com.projectseele.entity.EvaWeaponHandlingR45.knifeVisible(entity,0)
                        && "knife".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> POSITRON_MESH, entity -> POSITRON_TEXTURE,
                (entity, bone) -> entity.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                        && "cannon".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> RIFLE_MESH, entity -> RIFLE_TEXTURE,
                (entity, bone) -> entity.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                        && "cannon".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> N2_MESH, entity -> N2_TEXTURE,
                (entity, bone) -> entity.getWeapon() == EvaUnit01Entity.WEAPON_N2
                        && "n2".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                EvaUnit01Renderer::lanceMeshResource,
                EvaUnit01Renderer::lanceTextureResource,
                (entity, bone) -> entity.getWeapon() == EvaUnit01Entity.WEAPON_LANCE
                        && "lance".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> new ResourceLocation(ProjectSeele.MODID,"mesh/eva02_longsword.mesh.json"),
                entity -> new ResourceLocation(ProjectSeele.MODID,"textures/entity/eva02_longsword.png"),
                (entity,bone) -> !entity.isExperimentalUnit()&&entity.getUnitVariant()==2
                        &&entity.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45&&"lance".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> new ResourceLocation(ProjectSeele.MODID,"mesh/yashima_shield.mesh.json"),
                entity -> new ResourceLocation(ProjectSeele.MODID,"textures/entity/yashima_shield.png"),
                (entity,bone) -> com.projectseele.entity.EvaShieldRigR47.equipped(entity)&&"shield".equals(bone.getName())));
        this.addRenderLayer(new LocalTriangleMeshLayer<>(this,
                entity -> entity.isExperimentalUnit()?new ResourceLocation(ProjectSeele.MODID,"mesh/entry_plug_un.mesh.json"):ENTRY_PLUG_MESH,
                entity -> entity.isExperimentalUnit()?new ResourceLocation(ProjectSeele.MODID,"textures/entity/entry_plug_un.png"):ENTRY_PLUG_TEXTURE,
                (entity, bone) -> !this.pilotView
                        && isEntryHardwareVisible(entity, bone.getName())));
        this.shadowRadius = 5.4F;
        this.withScale(EvaScale.RENDER_SCALE);
    }

    /** Loads the three route-visible airframes before live frame sampling. */
    public static void prewarmLocalBodyMeshes(ResourceManager resourceManager)
    {
        LocalTriangleMeshLayer.prewarm(resourceManager,
                MESH_00, MESH_01, MESH_02,
                new ResourceLocation(ProjectSeele.MODID,"mesh/eva_prototype.mesh.json"),
                new ResourceLocation(ProjectSeele.MODID,"mesh/eva_un01.mesh.json"));
    }

    @Override
    public void render(EvaUnit01Entity entity, float entityYaw, float partialTick, PoseStack poseStack,
                       MultiBufferSource bufferSource, int packedLight)
    {
        com.projectseele.client.visual.FactoryR20Client.bodyDraw(entity);
        LocalVisualAssetFingerprint.Fingerprint fingerprint =
                entity.isExperimentalUnit()?LocalVisualAssetFingerprint.inspect(entity.experimentalAssetName()):visualFingerprintForVariant(entity.getUnitVariant());
        if (LocalVisualAssetFingerprint.isStrictMode() && !fingerprint.valid())
        {
            if (!this.strictFailureReported)
            {
                this.strictFailureReported = true;
                ProjectSeele.LOGGER.error(
                        "Strict high-detail EVA render refused: {}", fingerprint.description());
            }
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        // The physical feed trims enclosing armour. The sun's view must keep
        // the whole body, even though Minecraft's camera mode is first person.
        boolean localPilotView=isLocalPilotView(minecraft, entity),shadowPass=ShaderShadowPassR44.active();
        this.pilotView = localPilotView && !shadowPass;
        EvaShadowProbeR44.renderMode(entity,localPilotView,shadowPass);
        if(this.pilotView)com.projectseele.client.EvaPilotBodyRenderBridge.mark(entity);
        EvaPoseRuntimeRecorder.maybeStartSmoke(entity);
        // Wet cages and launch shafts use dedicated NERV floodlights.  Keeping
        // the airframe full-bright only while logistics-locked prevents a
        // 24-block model from sampling one dark centre voxel and becoming a
        // black silhouette despite the illuminated shaft walls.
        boolean nervFloodlit = entity.isNervLogisticsLocked()
                || entity instanceof com.projectseele.entity.EvaPrototypeEntity prototype && prototype.isInsideTestHangar()
                || entity.getLaunchPhase() == EvaUnit01Entity.LAUNCH_ASCENT;
        if (!entity.isExperimentalUnit() && !com.projectseele.entity.EvaAirTransportR31.active(entity) && (entity.hasActiveCarrierMotion()
                || entity.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR || entity.carrierRiseProgress(partialTick)>.001F))
        {
            // The deck is one rigid piece of the rendered EVA assembly.  It
            // has no independent entity, packet clock or culling lifetime.
            NervMovingCarrierRenderer.render(poseStack, bufferSource,
                    nervFloodlit ? LightTexture.FULL_BRIGHT : packedLight,
                    entity,partialTick);
        }
        TvFacilityMeshes.withBuffers(bufferSource,()->EvaBayMachineryR33.render(poseStack,entity,partialTick));
        boolean recording = EvaPoseRuntimeRecorder.wants(entity);
        if (recording)
        {
            EvaPoseRuntimeRecorder.beginFrame(entity, partialTick);
        }
        try
        {
            super.render(entity, entityYaw, partialTick, poseStack, bufferSource,
                    entity.isCrucified() || nervFloodlit
                            ? LightTexture.FULL_BRIGHT : packedLight);
        }
        finally
        {
            if (recording)
            {
                EvaPoseRuntimeRecorder.endFrame(entity);
            }
        }
    }

    private record MuzzleSample(Vec3 position, long capturedNanos) {}

    @Override protected void applyRotations(EvaUnit01Entity entity,PoseStack pose,float age,float yaw,float partial)
    {
        if(entity.isFirstBattleActive())yaw=com.projectseele.entity.FirstBattleClip.yaw(entity.firstBattleSignals().spec(entity),true,entity.firstBattleSignals().time(entity,partial));
        else if(!entity.isExperimentalUnit()&&entity.isNervLogisticsLocked()
                &&!com.projectseele.entity.EvaAirTransportR31.active(entity))yaw=EvaUnit01Entity.SILO_BAY_YAW;
        super.applyRotations(entity,pose,age,yaw,partial);
    }

    @Override
    public Vec3 getRenderOffset(EvaUnit01Entity entity, float partialTick)
    {
        Vec3 base = super.getRenderOffset(entity, partialTick);
        if (entity.isFirstBattleActive()) return base.add(com.projectseele.entity.FirstBattleClip.renderOffset(entity,partialTick));
        if (!entity.hasActiveCarrierMotion())
        {
            return base;
        }
        // Body, rack and third-person camera share one analytic mechanical
        // frame. A rider's independently corrected packet history must not
        // move the entire sixty-block assembly back and forth.
        Vec3 exact = entity.carrierRenderPosition(partialTick);
        // EntityRenderDispatcher is fed LevelRenderer's xOld/yOld/zOld
        // interpolation, not Entity.getPosition(partial)'s xo/yo/zo path.
        // Subtract the exact baseline the dispatcher will add.
        Vec3 dispatcherPosition = new Vec3(
                Mth.lerp((double) partialTick,
                        entity.xOld, entity.getX()),
                Mth.lerp((double) partialTick,
                        entity.yOld, entity.getY()),
                Mth.lerp((double) partialTick,
                        entity.zOld, entity.getZ()));
        return base.add(exact.subtract(dispatcherPosition));
    }

    @Override
    public boolean shouldRender(EvaUnit01Entity entity, Frustum frustum,
                                double cameraX, double cameraY, double cameraZ)
    {
        com.projectseele.client.visual.FactoryR20Client.bodyCandidate(entity);
        if(com.projectseele.entity.EvaAirTransportR31.active(entity))return frustum.isVisible(entity.getBoundingBox().inflate(72));
        if(entity.hasActiveCarrierMotion())
        {
            var p=entity.carrierRenderPosition(Minecraft.getInstance().getFrameTime());
            return frustum.isVisible(new net.minecraft.world.phys.AABB(p.x-24,p.y-4,p.z-24,p.x+24,p.y+70,p.z+24));
        }
        if (EvaPoseRuntimeRecorder.requestsSmokeRender())
        {
            return true;
        }
        Minecraft minecraft = Minecraft.getInstance();
        // The crouch/prone head socket can sit just beyond the entity's coarse
        // gameplay AABB while hands and weapon remain in front of the camera.
        // Do not let frustum culling make the shared body disappear only in
        // first person; every other observer keeps the normal culling path.
        if (isLocalPilotView(minecraft, entity))
        {
            return true;
        }
        var retainedBounds=EvaRetainedRenderBoundsR46.bounds(entity,minecraft.getFrameTime());
        if(retainedBounds!=null)return frustum.isVisible(retainedBounds);
        if(com.projectseele.entity.EvaShutdownR30.retainsPoseR45(entity))
            return frustum.isVisible(entity.getBoundingBox().inflate(72));
        return super.shouldRender(entity, frustum, cameraX, cameraY, cameraZ);
    }

    private static boolean isLocalPilotView(Minecraft minecraft,
                                             EvaUnit01Entity entity)
    {
        if(entity.isFirstBattleActive())return com.projectseele.client.FirstBattleClient.insideOptics(entity);
        return minecraft.options.getCameraType().isFirstPerson()
                && minecraft.getCameraEntity() != null
                && EvaPilotResolver.controlTarget(
                        minecraft.getCameraEntity()) == entity;
    }

    @Override
    public void preRender(PoseStack poseStack, EvaUnit01Entity animatable, BakedGeoModel model,
                          @Nullable MultiBufferSource bufferSource, @Nullable VertexConsumer buffer,
                          boolean isReRender, float partialTick, int packedLight, int packedOverlay,
                          float red, float green, float blue, float alpha)
    {
        if (!isReRender)
        {
            EvaPoseTransition.restoreGecko(model);
            EvaMechanicalResetR30.prepare(animatable,model);
        }
        super.preRender(poseStack, animatable, model, bufferSource, buffer, isReRender,
                partialTick, packedLight, packedOverlay, red, green, blue, alpha);
        forEachBone(model, bone ->
        {
            bone.setHidden(false);
            bone.setChildrenHidden(false);
            if (EvaPoseRuntimeRecorder.wants(animatable))
            {
                EvaPoseRuntimeRecorder.trackMatrices(bone);
            }
        });
        EvaWeightedInnerProxy.prepare(model);
        EvaManifoldInnerBody.prepare(model);
        if (this.pilotView)
        {
            forEachBone(model, bone ->
            {
                if (CAMERA_COVER_BONES.contains(bone.getName()))
                {
                    hideSubtree(bone);
                }
            });
            // The long weapons only leave the physical camera feed while an
            // optical sight is actually active. Keeping the aim subtree for
            // the clean first-person pass lets visual regression captures
            // inspect the same arms and weapon that third person renders;
            // holding RMB switches to the entry-plug fire-control picture.
            if (ClientForgeEvents.isCannonScopeActive(animatable)
                    || ClientForgeEvents.isRifleSightActive(animatable))
            {
                model.getBone("aim_pitch").ifPresent(EvaUnit01Renderer::hideSubtree);
            }
        }
        // GeoEntityRenderer evaluates Gecko controllers inside actuallyRender,
        // after this preRender hook. Defer the PoseGraph commit until the root
        // recursion begins so live motion is the final pose that reaches the
        // vertex path instead of being overwritten by handleAnimations.
        if (!isReRender)
        {
            this.pendingPoseModel = model;
            this.pendingPoseEntity = animatable;
            this.pendingPosePartialTick = partialTick;
            this.pendingPoseCommit = true;
        }
        // Weapon visibility applies on top in every view.
        setWeaponVisibility(model, "knife", com.projectseele.entity.EvaWeaponHandlingR45.knifeVisible(animatable,partialTick));
        setWeaponVisibility(model, "cannon", animatable.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                || animatable.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE);
        setWeaponVisibility(model, "lance", animatable.getWeapon() == EvaUnit01Entity.WEAPON_LANCE
                ||animatable.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45);
        setWeaponVisibility(model, "n2", animatable.getWeapon() == EvaUnit01Entity.WEAPON_N2);
        setWeaponVisibility(model, "shield", com.projectseele.entity.EvaShieldRigR47.equipped(animatable));
        // The external carrier owns the entire visible insertion. Once seated,
        // the capsule is inside the artificial spine and the dorsal armour
        // reseals; no duplicate capsule or generic hatch may protrude from the
        // body rig.
        setWeaponVisibility(model, "entry_plug", false);
        setWeaponVisibility(model, "plug_hatch_l", false);
        setWeaponVisibility(model, "plug_hatch_r", false);
    }

    @Override
    public void renderRecursively(PoseStack poseStack,
                                  EvaUnit01Entity animatable, GeoBone bone,
                                  RenderType renderType,
                                  MultiBufferSource bufferSource,
                                  VertexConsumer buffer, boolean isReRender,
                                  float partialTick, int packedLight,
                                  int packedOverlay, float red, float green,
                                  float blue, float alpha)
    {
        if (!isReRender && bone.getParent() == null
                && this.pendingPoseCommit
                && this.pendingPoseEntity == animatable
                && this.pendingPoseModel != null)
        {
            BakedGeoModel poseModel = this.pendingPoseModel;
            this.pendingPoseCommit = false;
            this.pendingPoseModel = null;
            this.pendingPoseEntity = null;
            org.joml.Matrix4f world=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(poseStack.last().pose(),this.entityRenderTranslations);
            Vec3 origin=com.projectseele.entity.EvaAirTransportR31.active(animatable)||com.projectseele.entity.EvaShutdownR30.displayed(animatable)?renderedOrigin(animatable,partialTick):animatable.getPosition(partialTick);
            world.m30(world.m30()+(float)origin.x).m31(world.m31()+(float)origin.y).m32(world.m32()+(float)origin.z);
            EvaPoseGraph.commit(animatable, poseModel,this.pendingPosePartialTick,world);
        }
        if("cannon".equals(bone.getName()))bone.setTrackingMatrices(true);
        super.renderRecursively(poseStack, animatable, bone, renderType,
                bufferSource, buffer, isReRender, partialTick, packedLight,
                packedOverlay, red, green, blue, alpha);
        EvaPoseRuntimeRecorder.captureBone(animatable, bone, isReRender);
        if (!isReRender && bone.getParent() == null)
        {
            com.projectseele.client.visual.EvaConnectedActionReview.recordPose(animatable,
                    this.getGeoModel().getBakedModel(this.getGeoModel().getModelResource(animatable)), partialTick);
            EvaWeightedInnerProxy.renderAfterRoot(
                    poseStack, animatable, bone, bufferSource,
                    packedLight, packedOverlay);
            EvaManifoldInnerBody.renderAfterRoot(
                    poseStack, animatable, bone, bufferSource,
                    packedLight, packedOverlay);
        }
    }

    private static void setWeaponVisibility(BakedGeoModel model, String name, boolean active)
    {
        model.getBone(name).ifPresent(bone ->
                bone.setHidden(bone.isHidden() || !active));
    }

    @Override
    public void renderCubesOfBone(PoseStack poseStack, GeoBone bone, VertexConsumer buffer,
                                  int packedLight, int packedOverlay, float red, float green,
                                  float blue, float alpha)
    {
        EvaUnit01Entity entity = this.getAnimatable();
        boolean bodyMesh = entity != null && LocalTriangleMeshLayer.hasPart(
                meshResourceForEntity(entity), bone.getName());
        boolean cannonMesh = entity != null
                && entity.getWeapon() == EvaUnit01Entity.WEAPON_CANNON
                && "cannon".equals(bone.getName())
                && LocalTriangleMeshLayer.hasPart(POSITRON_MESH, bone.getName());
        boolean rifleMesh = entity != null
                && entity.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                && "cannon".equals(bone.getName())
                && LocalTriangleMeshLayer.hasPart(RIFLE_MESH, bone.getName());
        boolean n2Mesh = entity != null
                && entity.getWeapon() == EvaUnit01Entity.WEAPON_N2
                && "n2".equals(bone.getName())
                && LocalTriangleMeshLayer.hasPart(N2_MESH, bone.getName());
        ResourceLocation activeKnifeMesh = entity == null ? COMMON_KNIFE_MESH
                : knifeMeshResource(entity);
        boolean knifeMesh = entity != null
                && com.projectseele.entity.EvaWeaponHandlingR45.knifeVisible(entity,0)
                && "knife".equals(bone.getName())
                && LocalTriangleMeshLayer.hasPart(activeKnifeMesh, bone.getName());
        boolean entryHardwareMesh = !this.pilotView && entity != null
                && isEntryHardwareVisible(entity, bone.getName())
                && LocalTriangleMeshLayer.hasPart(ENTRY_PLUG_MESH, bone.getName());
        ResourceLocation activeLanceMesh = entity == null ? LONGINUS_MESH
                : lanceMeshResource(entity);
        boolean lanceMesh = entity != null
                && entity.getWeapon() == EvaUnit01Entity.WEAPON_LANCE
                && "lance".equals(bone.getName())
                && LocalTriangleMeshLayer.hasPart(activeLanceMesh, bone.getName());
        boolean swordMesh=entity!=null&&entity.getWeapon()==EvaUnit01Entity.WEAPON_SWORD_R45
                &&"lance".equals(bone.getName())&&LocalTriangleMeshLayer.hasPart(
                        new ResourceLocation(ProjectSeele.MODID,"mesh/eva02_longsword.mesh.json"),"lance");
        boolean shieldMesh=entity!=null&&com.projectseele.entity.EvaShieldRigR47.equipped(entity)&&"shield".equals(bone.getName());
        if (bodyMesh || cannonMesh || rifleMesh || n2Mesh
                || knifeMesh || lanceMesh || swordMesh || shieldMesh || entryHardwareMesh)
        {
            return;
        }
        super.renderCubesOfBone(poseStack, bone, buffer, packedLight, packedOverlay,
                red, green, blue, alpha);
    }

    private static boolean isEntryHardwareVisible(EvaUnit01Entity entity, String boneName)
    {
        return false;
    }

    public static ResourceLocation meshResourceForVariant(int variant)
    {
        return switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> MESH_00;
            case EvaUnit01Entity.UNIT_02 -> MESH_02;
            default -> MESH_01;
        };
    }

    /** Keep body vertices on a variant-owned buffer, never a weapon buffer. */
    public static ResourceLocation textureResourceForVariant(int variant)
    {
        return switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> TEXTURE_00;
            case EvaUnit01Entity.UNIT_02 -> TEXTURE_02;
            default -> TEXTURE_01;
        };
    }

    private static ResourceLocation eyeTextureResourceForVariant(int variant)
    {
        return switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> EYES_00;
            case EvaUnit01Entity.UNIT_02 -> EYES_02;
            default -> EYES_01;
        };
    }

    public static ResourceLocation positronMeshResource()
    {
        return POSITRON_MESH;
    }

    public static ResourceLocation rifleMeshResource()
    {
        return RIFLE_MESH;
    }

    public static ResourceLocation n2MeshResource()
    {
        return N2_MESH;
    }

    public static ResourceLocation knifeMeshResource(EvaUnit01Entity entity)
    {
        var candidate=com.projectseele.entity.EvaAnatomicalHandsR45.knifeAttachment(entity);
        if(candidate!=null)return new ResourceLocation("projectseele","mesh/"+candidate.mesh());
        return entity.getUnitVariant() == EvaUnit01Entity.UNIT_02
                ? UNIT02_KNIFE_MESH : COMMON_KNIFE_MESH;
    }

    private static ResourceLocation knifeTextureResource(EvaUnit01Entity entity)
    {
        return entity.getUnitVariant() == EvaUnit01Entity.UNIT_02
                ? UNIT02_WEAPONS_TEXTURE : COMMON_KNIFE_TEXTURE;
    }

    public static ResourceLocation lanceMeshResource(EvaUnit01Entity entity)
    {
        // Until Unit-02's dedicated weapon has its own reviewed stance, all
        // three pilotable EVAs use the same Longinus geometry and two-hand
        // spear contract.  The old rebuild sword occupied this socket like a
        // chest-mounted blade instead of a polearm.
        return LONGINUS_MESH;
    }

    private static ResourceLocation lanceTextureResource(EvaUnit01Entity entity)
    {
        return LONGINUS_TEXTURE;
    }

    public static LocalVisualAssetFingerprint.Fingerprint visualFingerprintForVariant(int variant)
    {
        return LocalVisualAssetFingerprint.inspect(switch (variant)
        {
            case EvaUnit01Entity.UNIT_00 -> "eva_unit00";
            case EvaUnit01Entity.UNIT_02 -> "eva_unit02";
            default -> "eva_unit01";
        });
    }

    private boolean shouldRenderBodyMesh(EvaUnit01Entity entity, GeoBone bone)
    {
        if(EvaHandSurfaceR45.applies(entity)&&EvaHandSurfaceR45.oldSurface(bone.getName()))return false;
        if (!this.pilotView)
        {
            EvaShadowProbeR44.admission(entity,bone.getName(),true);
            return true;
        }
        if (CAMERA_COVER_BONES.contains(bone.getName()))
        {
            EvaShadowProbeR44.admission(entity,bone.getName(),false);
            return false;
        }
        // The rider socket is fixed to the entity while attack animations can
        // rotate the chest through that socket.  Suppress only the four rigid
        // shells enclosing the pilot in every stance; never hide their bones
        // or descendants.  Arms, hands, fingers and weapons therefore remain
        // the exact world skeleton seen by third person without the chest
        // becoming an opaque wall during a knife strike or spear lunge.
        String surface=bone.getName().startsWith("r21_join_")&&bone.getParent()!=null?bone.getParent().getName():bone.getName();
        boolean visible=!PILOT_CAMERA_MESH_COVER.contains(surface);
        EvaShadowProbeR44.admission(entity,bone.getName(),visible);
        return visible;
    }

    private static void hideSubtree(GeoBone bone)
    {
        bone.setHidden(true);
        bone.setChildrenHidden(true);
        for (GeoBone child : bone.getChildBones())
        {
            hideSubtree(child);
        }
    }

    private static void forEachBone(BakedGeoModel model, Consumer<GeoBone> action)
    {
        for (GeoBone bone : model.topLevelBones())
        {
            walkBone(bone, action);
        }
    }

    private static void walkBone(GeoBone bone, Consumer<GeoBone> action)
    {
        action.accept(bone);
        for (GeoBone child : bone.getChildBones())
        {
            walkBone(child, action);
        }
    }

    public static ResourceLocation meshResourceForEntity(EvaUnit01Entity entity)
    {
        var mechanism=com.projectseele.entity.EvaAnatomicalHandsR45.knifeMechanism(entity);
        if(mechanism!=null)return new ResourceLocation(ProjectSeele.MODID,"mesh/"+mechanism.bodyMesh());
        return entity.isExperimentalUnit()?new ResourceLocation(ProjectSeele.MODID,"mesh/"+entity.experimentalAssetName()+".mesh.json"):meshResourceForVariant(entity.getUnitVariant());
    }

}

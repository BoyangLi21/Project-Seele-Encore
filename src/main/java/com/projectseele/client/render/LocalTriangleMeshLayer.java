package com.projectseele.client.render;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.ArrayList;
import java.util.Optional;
import java.util.Set;
import java.util.function.Function;
import java.util.function.BiPredicate;
import java.util.zip.CRC32;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.LightTexture;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix3f;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.core.animatable.GeoAnimatable;
import software.bernie.geckolib.renderer.GeoRenderer;
import software.bernie.geckolib.renderer.layer.GeoRenderLayer;

/**
 * Optional local-only triangle geometry driven by a GeckoLib bone hierarchy.
 * The public jar contains the loader but no third-party mesh or texture.
 */
public final class LocalTriangleMeshLayer<T extends GeoAnimatable> extends GeoRenderLayer<T>
{
    private static final Map<ResourceLocation, MeshData> CACHE = new HashMap<>();
    private static final Set<ResourceLocation> LOAD_ATTEMPTED = new HashSet<>();
    private static final Set<Class<?>> GPU_DIAGNOSTICS = new HashSet<>();
    private final Function<T, ResourceLocation> meshSelector;
    private final Function<T, ResourceLocation> textureSelector;
    private final BiPredicate<T, GeoBone> partVisibility;
    private final boolean fullBright;

    public LocalTriangleMeshLayer(GeoRenderer<T> renderer,
                                  Function<T, ResourceLocation> meshSelector)
    {
        this(renderer, meshSelector, null, (entity, bone) -> true, false);
    }

    public LocalTriangleMeshLayer(GeoRenderer<T> renderer,
                                  Function<T, ResourceLocation> meshSelector,
                                  Function<T, ResourceLocation> textureSelector)
    {
        this(renderer, meshSelector, textureSelector,
                (entity, bone) -> true, false);
    }

    public LocalTriangleMeshLayer(GeoRenderer<T> renderer,
                                  Function<T, ResourceLocation> meshSelector,
                                  Function<T, ResourceLocation> textureSelector,
                                  BiPredicate<T, GeoBone> partVisibility)
    {
        this(renderer, meshSelector, textureSelector, partVisibility, false);
    }

    public LocalTriangleMeshLayer(GeoRenderer<T> renderer,
                                  Function<T, ResourceLocation> meshSelector,
                                  Function<T, ResourceLocation> textureSelector,
                                  BiPredicate<T, GeoBone> partVisibility,
                                  boolean fullBright)
    {
        super(renderer);
        this.meshSelector = meshSelector;
        this.textureSelector = textureSelector;
        this.partVisibility = partVisibility;
        this.fullBright = fullBright;
    }

    @Override
    public void renderForBone(PoseStack poseStack, T animatable, GeoBone bone,
                              RenderType renderType, MultiBufferSource bufferSource,
                              VertexConsumer buffer, float partialTick, int packedLight,
                              int packedOverlay)
    {
        if(!this.fullBright&&bone.getName().equals("root")&&animatable instanceof net.minecraft.world.entity.Entity entity)
            FirstBattlePoseRenderer.remember(entity,bone);
        if (bone.isHidden() || !this.partVisibility.test(animatable, bone))
        {
            return;
        }
        ResourceLocation meshLocation = this.meshSelector.apply(animatable);
        MeshData mesh = getMesh(meshLocation);
        if (mesh == null)
        {
            return;
        }
        MeshPart part = mesh.parts().get(bone.getName());
        if (part == null)
        {
            return;
        }

        Matrix4f pose = poseStack.last().pose();
        Matrix3f normal = poseStack.last().normal();
        if(com.projectseele.visual.MechanicsR31Review.ENABLED&&!this.fullBright)
        {
            if(animatable instanceof EvaUnit01Entity eva&&"torso_upper".equals(bone.getName())&&this.getRenderer() instanceof EvaUnit01Renderer renderer)
                com.projectseele.client.visual.MechanicsR31Client.captureSocket(eva,renderer.renderedMeshTransform(pose,eva,partialTick),partialTick);
            if(animatable instanceof EvaUnit01Entity eva&&"head".equals(bone.getName())&&this.getRenderer() instanceof EvaUnit01Renderer renderer)
                com.projectseele.client.visual.MechanicsR31Client.captureHeadFacing(eva,renderer.renderedMeshTransform(pose,eva,partialTick),partialTick);
            if(animatable instanceof com.projectseele.entity.EntryPlugCarrierEntity plug&&"entry_plug".equals(bone.getName())&&this.getRenderer() instanceof EntryPlugCarrierRenderer renderer)
                com.projectseele.client.visual.MechanicsR31Client.capturePlug(plug,renderer.renderedMeshTransform(pose,plug,partialTick),partialTick);
        }
        if((com.projectseele.client.visual.EvaDorsalR13Audit.ENABLED||EvaHeadArmorR25Audit.ENABLED)&&!this.fullBright&&animatable instanceof EvaUnit01Entity eva
                &&this.getRenderer() instanceof EvaUnit01Renderer renderer)
        {
            com.projectseele.client.visual.EvaDorsalR13Audit.capture(eva,bone.getName(),renderer.renderedMeshTransform(pose,eva,partialTick));
            EvaHeadArmorR25Audit.capture(eva,bone.getName(),renderer.renderedMeshTransform(pose,eva,partialTick));
        }
        if (animatable instanceof EvaUnit01Entity eva
                && eva.getWeapon() == EvaUnit01Entity.WEAPON_RIFLE
                && "cannon".equals(bone.getName())
                && meshLocation.getPath().endsWith("eva_pallet_smg.mesh.json"))
        {
            if (this.getRenderer() instanceof EvaUnit01Renderer renderer)
            {
                var muzzle=renderer.renderedMeshPoint(pose,new Vector3f(part.muzzleX(),part.muzzleY(),part.muzzleZ()),eva,partialTick);
                EvaUnit01Renderer.rememberRifleMuzzle(eva.getId(),muzzle);
                com.projectseele.client.visual.UNR29Client.captureRifle(eva,muzzle);
            }
        }
        VertexConsumer targetBuffer = this.textureSelector == null ? buffer
                : bufferSource.getBuffer(RenderType.entityCutoutNoCull(
                        this.textureSelector.apply(animatable)));
        float[] values = skinVertices(mesh,part,bone);
        int stride = mesh.stride();
        if(Boolean.getBoolean("projectseele.r38JointAudit")&&!this.fullBright&&animatable instanceof EvaUnit01Entity eva
                &&eva.getId()==com.projectseele.visual.CombatR31Review.evaId&&this.getRenderer() instanceof EvaUnit01Renderer renderer)
            witnessAttachmentsR38(mesh,part,bone,values,renderer.renderedMeshTransform(pose,eva,partialTick));
        if(!this.fullBright&&animatable instanceof EvaUnit01Entity eva&&eva.isFirstBattleActive()
                &&this.getRenderer() instanceof EvaUnit01Renderer renderer)
            EvaContactShadowsR24.capture(eva,bone.getName(),values,stride,part.pivotX(),part.pivotY(),part.pivotZ(),renderer.renderedMeshTransform(pose,eva,partialTick));
        if(com.projectseele.client.visual.TvBattleContactR24Audit.ENABLED&&!this.fullBright&&animatable instanceof EvaUnit01Entity eva
                &&this.getRenderer() instanceof EvaUnit01Renderer renderer)
            com.projectseele.client.visual.TvBattleContactR24Audit.sample(eva,bone.getName(),values,stride,part.pivotX(),part.pivotY(),part.pivotZ(),renderer.renderedMeshTransform(pose,eva,partialTick));
        if(!this.fullBright&&animatable instanceof com.projectseele.entity.EvaPrototypeEntity eva&&this.getRenderer() instanceof EvaUnit01Renderer renderer
                &&com.projectseele.visual.EvaTerrainR11Review.R21&&com.projectseele.visual.EvaTerrainR11Review.runningCase
                &&com.projectseele.visual.EvaTerrainR11Review.caseTick%20==0)
            witnessWelds(mesh,part,bone,values,renderer.renderedMeshTransform(pose,eva,partialTick),eva.getUNSerial());
        if(Boolean.getBoolean("projectseele.motionReviewR05")&&!this.fullBright&&animatable instanceof EvaUnit01Entity eva
                &&this.getRenderer() instanceof EvaUnit01Renderer renderer)
            com.projectseele.client.visual.EvaMeshAuditR05.capture(eva.getId(),meshLocation.getPath().contains("pallet_smg")?"rifle":bone.getName(),
                    values,stride,part.pivotX(),part.pivotY(),part.pivotZ(),renderer.renderedMeshTransform(pose,eva,partialTick));
        boolean dormantEye = animatable instanceof EvaUnit01Entity eva && "head".equals(bone.getName())
                && !com.projectseele.entity.EvaDorsalMechanism.eyesEnabled(eva);
        int vertexLight = this.fullBright && !dormantEye
                ? LightTexture.FULL_BRIGHT : packedLight;
        if(this.fullBright&&"head".equals(bone.getName())&&animatable instanceof EvaUnit01Entity eva&&this.textureSelector!=null)
            com.projectseele.client.visual.OpticsR43Review.draw(eva,this.textureSelector.apply(animatable),vertexLight);
        if(GPU_DIAGNOSTICS.add(animatable.getClass()))com.projectseele.ProjectSeele.LOGGER.info(
                "Rigid mesh dispatch: entity={} rigid={} buffer={} texture={}",animatable.getClass().getSimpleName(),values==part.vertices(),targetBuffer.getClass().getName(),this.textureSelector!=null);
        if(values==part.vertices()&&this.textureSelector!=null
                &&(targetBuffer instanceof com.mojang.blaze3d.vertex.BufferBuilder
                    ||targetBuffer.getClass().getName().equals("me.jellysquid.mods.sodium.client.render.vertex.buffer.SodiumBufferBuilder"))
                &&RigidCapsuleGpu.draw(part,values,stride,part.pivotX(),part.pivotY(),part.pivotZ(),
                this.textureSelector.apply(animatable),poseStack,vertexLight,packedOverlay,part.red(),part.green(),part.blue()))return;
        for (int index = 0; index + stride * 3 <= values.length; index += stride * 3)
        {
            emitVertex(targetBuffer, pose, normal, values, index, part,
                    vertexLight, packedOverlay);
            emitVertex(targetBuffer, pose, normal, values, index + stride, part,
                    vertexLight, packedOverlay);
            emitVertex(targetBuffer, pose, normal, values, index + stride * 2, part,
                    vertexLight, packedOverlay);
            // Gecko's entity cutout buffer is QUADS. A repeated third point
            // makes each OBJ triangle an independent degenerate quad.
            emitVertex(targetBuffer, pose, normal, values, index + stride * 2, part,
                    vertexLight, packedOverlay);
        }
    }

    private static void emitVertex(VertexConsumer buffer, Matrix4f pose, Matrix3f normal,
                                   float[] values, int index, MeshPart part,
                                   int packedLight, int packedOverlay)
    {
        // Match GeckoLib's Bedrock X reflection so cubes and local triangles
        // occupy the same animated coordinate space.
        float x = -(values[index] + part.pivotX()) / 16.0F;
        float y = (values[index + 1] + part.pivotY()) / 16.0F;
        float z = (values[index + 2] + part.pivotZ()) / 16.0F;
        MeshVertexWriter.emitTinted(buffer,pose,normal,x,y,z,values[index+3],values[index+4],
                packedLight,packedOverlay,-values[index+5],values[index+6],values[index+7],part.red(),part.green(),part.blue());
    }

    public static void clearCache()
    {
        EvaEyeMaterialsR42.reload();
        RigidCapsuleGpu.clear();
        CACHE.clear();
        LOAD_ATTEMPTED.clear();
        EvaHeadClearance.clear();
    }

    static float[] nativeTrianglePositions(ResourceLocation resource,String name)
    {
        MeshData mesh=getMesh(resource);if(mesh==null)return null;
        MeshPart part=mesh.parts().get(name);if(part==null)return null;
        float[] source=part.vertices(),result=new float[source.length/mesh.stride()*3];
        for(int i=0,j=0;i<source.length;i+=mesh.stride(),j+=3)
        {
            result[j]=-(source[i]+part.pivotX())/16;
            result[j+1]=(source[i+1]+part.pivotY())/16;
            result[j+2]=(source[i+2]+part.pivotZ())/16;
        }
        return result;
    }

    /**
     * Parses the large local EVA shells while the resource reload screen still
     * owns the render thread. Lazy parsing after an EVA first enters view can
     * otherwise create multi-second frame stalls in an ordinary route walk.
     */
    public static void prewarm(ResourceManager resourceManager,
                               ResourceLocation... meshResources)
    {
        long startedAt = System.nanoTime();
        int loaded = 0;
        for (ResourceLocation meshResource : meshResources)
        {
            if (getMesh(resourceManager, meshResource) != null)
            {
                loaded++;
            }
        }
        ProjectSeele.LOGGER.info(
                "Prewarmed local triangle meshes: loaded={}/{} elapsedMs={}",
                loaded, meshResources.length,
                (System.nanoTime() - startedAt) / 1_000_000L);
    }

    public static boolean hasPart(ResourceLocation meshResource, String boneName)
    {
        MeshData mesh = getMesh(meshResource);
        return mesh != null && mesh.parts().containsKey(boneName);
    }

    /**
     * Renders a local attachment mesh as one independent world object.
     * Weapon elevators use this path so the payload stays a real persistent
     * entity before it is handed to the EVA skeleton.  The mesh is centred on
     * X/Z and rests on local Y=0; caller scale/orientation remains explicit.
     */
    public static boolean renderStandalone(PoseStack poseStack,
                                           MultiBufferSource bufferSource,
                                           ResourceLocation meshResource,
                                           ResourceLocation textureResource,
                                           int packedLight,
                                           int packedOverlay)
    {
        MeshData mesh = getMesh(meshResource);
        if (mesh == null)
        {
            return false;
        }
        VertexConsumer target = bufferSource.getBuffer(
                RenderType.entityCutoutNoCull(textureResource));
        Matrix4f pose = poseStack.last().pose();
        Matrix3f normal = poseStack.last().normal();
        for (MeshPart part : mesh.parts().values())
        {
            float[] values = part.vertices();
            for (int index = 0; index + mesh.stride() * 3 <= values.length;
                 index += mesh.stride() * 3)
            {
                emitStandaloneVertex(target, pose, normal, values, index,
                        part, mesh, packedLight, packedOverlay);
                emitStandaloneVertex(target, pose, normal, values,
                        index + mesh.stride(), part, mesh,
                        packedLight, packedOverlay);
                emitStandaloneVertex(target, pose, normal, values,
                        index + mesh.stride() * 2, part, mesh,
                        packedLight, packedOverlay);
                emitStandaloneVertex(target, pose, normal, values,
                        index + mesh.stride() * 2, part, mesh,
                        packedLight, packedOverlay);
            }
        }
        return true;
    }

    private static void emitStandaloneVertex(VertexConsumer buffer,
                                             Matrix4f pose, Matrix3f normal,
                                             float[] values, int index,
                                             MeshPart part, MeshData mesh,
                                             int packedLight,
                                             int packedOverlay)
    {
        float absoluteX = values[index] + part.pivotX();
        float absoluteY = values[index + 1] + part.pivotY();
        float absoluteZ = values[index + 2] + part.pivotZ();
        float x = -(absoluteX - mesh.centreX()) / 16.0F;
        float y = (absoluteY - mesh.minimumY()) / 16.0F;
        float z = (absoluteZ - mesh.centreZ()) / 16.0F;
        MeshVertexWriter.emit(buffer,pose,normal,x,y,z,values[index+3],values[index+4],
                packedLight,packedOverlay,-values[index+5],values[index+6],values[index+7]);
    }

    public static String captureTag(ResourceLocation meshResource)
    {
        MeshData mesh = getMesh(meshResource);
        return mesh == null ? "mesh-missing" : mesh.captureTag();
    }

    private static MeshData getMesh(ResourceLocation meshLocation)
    {
        return getMesh(Minecraft.getInstance().getResourceManager(),
                meshLocation);
    }

    private static MeshData getMesh(ResourceManager resourceManager,
                                    ResourceLocation meshLocation)
    {
        if (LOAD_ATTEMPTED.contains(meshLocation))
        {
            return CACHE.get(meshLocation);
        }
        LOAD_ATTEMPTED.add(meshLocation);
        Optional<Resource> resource = resourceManager.getResource(meshLocation);
        if (resource.isEmpty())
        {
            return null;
        }
        try (var stream = resource.get().open())
        {
            byte[] bytes = stream.readAllBytes();
            JsonObject root = JsonParser.parseString(
                    new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject();
            int stride = root.get("stride").getAsInt();
            if (stride != 8)
            {
                throw new IOException("Unsupported local mesh stride " + stride);
            }
            Map<String, MeshPart> parts = new HashMap<>();
            for (Map.Entry<String, JsonElement> entry : root.getAsJsonObject("parts").entrySet())
            {
                JsonObject object = entry.getValue().getAsJsonObject();
                JsonArray pivot = object.getAsJsonArray("pivot");
                JsonArray source = object.getAsJsonArray("vertices");
                if (pivot.size() != 3 || source.size() == 0)
                {
                    throw new IOException("Invalid local mesh part " + entry.getKey());
                }
                float[] vertices = new float[source.size()];
                for (int index = 0; index < source.size(); index++)
                {
                    vertices[index] = source.get(index).getAsFloat();
                    if (!Float.isFinite(vertices[index]))
                    {
                        throw new IOException("Non-finite vertex in " + entry.getKey());
                    }
                }
                if (vertices.length % (stride * 3) != 0)
                {
                    throw new IOException("Incomplete triangles in " + entry.getKey());
                }
                float pivotX = pivot.get(0).getAsFloat();
                float pivotY = pivot.get(1).getAsFloat();
                float pivotZ = pivot.get(2).getAsFloat();
                float[] muzzle = farCap(vertices, stride,
                        pivotX, pivotY, pivotZ);
                parts.put(entry.getKey(), new MeshPart(
                        pivotX, pivotY, pivotZ, vertices,
                        muzzle[0], muzzle[1], muzzle[2],
                        object.has("tint")?object.getAsJsonArray("tint").get(0).getAsFloat():1,
                        object.has("tint")?object.getAsJsonArray("tint").get(1).getAsFloat():1,
                        object.has("tint")?object.getAsJsonArray("tint").get(2).getAsFloat():1));
            }
            int triangleCount = parts.values().stream()
                    .mapToInt(part -> part.vertices().length / (stride * 3)).sum();
            CRC32 crc = new CRC32();
            crc.update(bytes);
            String captureTag = String.format("triangle-mesh-%d-p%d-%08x",
                    triangleCount, parts.size(), crc.getValue());
            float minimumX = Float.POSITIVE_INFINITY;
            float minimumY = Float.POSITIVE_INFINITY;
            float minimumZ = Float.POSITIVE_INFINITY;
            float maximumX = Float.NEGATIVE_INFINITY;
            float maximumZ = Float.NEGATIVE_INFINITY;
            for (MeshPart part : parts.values())
            {
                float[] values = part.vertices();
                for (int index = 0; index < values.length; index += stride)
                {
                    float x = values[index] + part.pivotX();
                    float y = values[index + 1] + part.pivotY();
                    float z = values[index + 2] + part.pivotZ();
                    minimumX = Math.min(minimumX, x);
                    minimumY = Math.min(minimumY, y);
                    minimumZ = Math.min(minimumZ, z);
                    maximumX = Math.max(maximumX, x);
                    maximumZ = Math.max(maximumZ, z);
                }
            }
            MeshData mesh = new MeshData(stride, Map.copyOf(parts),
                    triangleCount, captureTag,
                    (minimumX + maximumX) * 0.5F, minimumY,
                    (minimumZ + maximumZ) * 0.5F, resolvedJointSkins(root,parts,stride));
            CACHE.put(meshLocation, mesh);
            ProjectSeele.LOGGER.info("Loaded local triangle mesh {}: {}",
                    meshLocation, captureTag);
            return mesh;
        }
        catch (Exception exception)
        {
            ProjectSeele.LOGGER.error("Failed to load local triangle mesh " + meshLocation,
                    exception);
            return null;
        }
    }

    private static float[] farCap(float[] vertices, int stride,
                                  float pivotX, float pivotY, float pivotZ)
    {
        float minimumY = Float.POSITIVE_INFINITY;
        for (int index = 0; index < vertices.length; index += stride)
        {
            minimumY = Math.min(minimumY, vertices[index + 1]);
        }
        float sumX = 0.0F;
        float sumY = 0.0F;
        float sumZ = 0.0F;
        int samples = 0;
        for (int index = 0; index < vertices.length; index += stride)
        {
            if (vertices[index + 1] > minimumY + 0.85F)
            {
                continue;
            }
            sumX += vertices[index] + pivotX;
            sumY += vertices[index + 1] + pivotY;
            sumZ += vertices[index + 2] + pivotZ;
            samples++;
        }
        if (samples == 0)
        {
            return new float[] {-pivotX / 16.0F,
                    pivotY / 16.0F, pivotZ / 16.0F};
        }
        return new float[] {-(sumX / samples) / 16.0F,
                (sumY / samples) / 16.0F,
                (sumZ / samples) / 16.0F};
    }

    private record MeshData(int stride, Map<String, MeshPart> parts,
                            int triangleCount, String captureTag,
                            float centreX, float minimumY,
                            float centreZ,Map<String,JointSkin> joints) {}

    private record JointSkin(String other,float[] weights,float[] rest,float[] scratch,Map<String,float[]> influences)
    {
        JointSkin(String other,float[] weights,float[] rest,float[] scratch){this(other,weights,rest,scratch,Map.of());}
    }

    private static final Map<String,WeldWitness> WELD_WITNESSES=new HashMap<>();
    private static final class WeldWitness
    {
        final Map<String,Map<String,Integer>> points=new HashMap<>();
        final Map<String,Vector3f> framePoints=new HashMap<>();final Map<String,String> frameOwners=new HashMap<>();long frame=-1;int samples;double maximum;String worst="";
        WeldWitness(MeshData mesh)
        {this(mesh,false);}
        WeldWitness(MeshData mesh,boolean attachments)
        {
            for(var entry:mesh.parts().entrySet())
            {
                String name=entry.getKey();if(name.startsWith("dorsal_")||name.startsWith("finger_")||!attachments&&(name.startsWith("hand_")||name.startsWith("wrist_")))continue;
                var part=entry.getValue();var v=part.vertices();
                for(int i=0;i<v.length;i+=8)
                {
                    String key=Math.round((v[i]+part.pivotX())*1000)+","+Math.round((v[i+1]+part.pivotY())*1000)+","+Math.round((v[i+2]+part.pivotZ())*1000);
                    points.computeIfAbsent(key,k->new HashMap<>()).putIfAbsent(name,i);
                }
            }
            points.entrySet().removeIf(e->e.getValue().size()<2||!(e.getValue().keySet().stream().anyMatch(n->n.startsWith("r21_join_"))
                    ||attachments&&(pairedR38(e.getValue().keySet(),"forearm_","hand_")||pairedR38(e.getValue().keySet(),"shin_","foot_"))));
        }
    }
    private static boolean pairedR38(java.util.Set<String> names,String a,String b)
    {return names.contains(a+"l")&&names.contains(b+"l")||names.contains(a+"r")&&names.contains(b+"r");}
    private static void witnessAttachmentsR38(MeshData mesh,MeshPart part,GeoBone bone,float[] values,Matrix4f world)
    {
        var witness=WELD_WITNESSES.computeIfAbsent(mesh.captureTag()+"-r38",k->new WeldWitness(mesh,true));long frame=com.projectseele.client.AircraftRenderClockR21.frame;
        if(frame!=witness.frame)
        {
            witness.frame=frame;witness.framePoints.clear();witness.frameOwners.clear();
            if(witness.samples>0&&frame%15==0)try
            {
                var report=new JsonObject();report.addProperty("passed",witness.maximum<.02);report.addProperty("maximum_world_gap",witness.maximum);report.addProperty("compared_pairs",witness.samples);report.addProperty("neutral_shared_points",witness.points.size());report.addProperty("worst",witness.worst);
                java.nio.file.Files.writeString(java.nio.file.Path.of(com.projectseele.visual.CombatR31Review.mediaFolder).resolve("surface_seams_r38.json"),report.toString());
            }
            catch(IOException error){throw new IllegalStateException(error);}
        }
        for(var entry:witness.points.entrySet())
        {
            Integer i=entry.getValue().get(bone.getName());if(i==null)continue;
            var point=world.transformPosition(new Vector3f(-(values[i]+part.pivotX())/16,(values[i+1]+part.pivotY())/16,(values[i+2]+part.pivotZ())/16));
            var previous=witness.framePoints.putIfAbsent(entry.getKey(),point);
            if(previous!=null)
            {
                double gap=point.distance(previous);if(gap>witness.maximum){witness.maximum=gap;witness.worst=entry.getKey()+" "+witness.frameOwners.get(entry.getKey())+" / "+bone.getName()+" stage="+com.projectseele.visual.CombatR31Review.stageName;}
                witness.samples++;
            }
            else witness.frameOwners.put(entry.getKey(),bone.getName());
        }
    }
    private static void witnessWelds(MeshData mesh,MeshPart part,GeoBone bone,float[] values,Matrix4f world,int serial)
    {
        var witness=WELD_WITNESSES.computeIfAbsent(mesh.captureTag(),k->new WeldWitness(mesh));long frame=com.projectseele.client.AircraftRenderClockR21.frame;
        if(frame!=witness.frame)
        {
            witness.frame=frame;witness.framePoints.clear();witness.frameOwners.clear();
            if(witness.samples>0)try
            {
                var report=new JsonObject();report.addProperty("passed",witness.maximum<.02);report.addProperty("maximum_world_gap",witness.maximum);report.addProperty("compared_pairs",witness.samples);report.addProperty("neutral_shared_points",witness.points.size());report.addProperty("worst",witness.worst);
                var path=Minecraft.getInstance().gameDirectory.toPath().resolve("../artifacts/un_models_r21/seam_witness_un0"+serial+".json").normalize();java.nio.file.Files.writeString(path,report.toString());
            }catch(IOException e){throw new IllegalStateException(e);}
        }
        for(var entry:witness.points.entrySet())
        {
            Integer i=entry.getValue().get(bone.getName());if(i==null)continue;
            var point=world.transformPosition(new Vector3f(-(values[i]+part.pivotX())/16,(values[i+1]+part.pivotY())/16,(values[i+2]+part.pivotZ())/16));
            var previous=witness.framePoints.putIfAbsent(entry.getKey(),point);
            if(previous!=null)
            {
                double gap=point.distance(previous);if(gap>witness.maximum){witness.maximum=gap;witness.worst=entry.getKey()+" "+witness.frameOwners.get(entry.getKey())+" / "+bone.getName()+" case="+com.projectseele.visual.EvaTerrainR11Review.caseIndex+" tick="+com.projectseele.visual.EvaTerrainR11Review.caseTick;}
                witness.samples++;
            }
            else witness.frameOwners.put(entry.getKey(),bone.getName());
        }
    }

    private static Map<String,JointSkin> resolvedJointSkins(JsonObject root,Map<String,MeshPart> parts,int stride) throws IOException
    {
        if(!root.has("jointSkins"))return jointSkins(parts,stride);
        var authored=authoredJointSkins(root.getAsJsonObject("jointSkins"),parts,stride);
        if(!root.has("r37_mouth"))return authored;
        // A new jaw membrane must not disable the source rig's welded knees
        // and elbows simply by adding the first authored skin to this mesh.
        var merged=new HashMap<>(jointSkins(parts,stride));merged.putAll(authored);return Map.copyOf(merged);
    }

    private static Map<String,JointSkin> authoredJointSkins(JsonObject definitions,Map<String,MeshPart> parts,int stride) throws IOException
    {
        Map<String,JointSkin> result=new HashMap<>();
        for(var entry:definitions.entrySet())
        {
            var part=parts.get(entry.getKey());var definition=entry.getValue().getAsJsonObject();
            if(part==null)throw new IOException("Authored joint part missing");
            if(definition.has("influences"))
            {
                int count=part.vertices().length/stride;Map<String,float[]> influences=new HashMap<>();float[] sums=new float[count];
                for(var row:definition.getAsJsonObject("influences").entrySet())
                {
                    var values=row.getValue().getAsJsonArray();if(values.size()!=count)throw new IOException("Joint influence length");float[] weights=new float[count];
                    for(int i=0;i<count;i++){float w=values.get(i).getAsFloat();if(!Float.isFinite(w)||w<0||w>1)throw new IOException("Invalid joint influence");weights[i]=w;sums[i]+=w;}
                    influences.put(row.getKey(),weights);
                }
                for(float sum:sums)if(Math.abs(sum-1)>.0002)throw new IOException("Joint influences must sum to one");
                float[] rest=part.vertices().clone();result.put(entry.getKey(),new JointSkin("",new float[0],rest,rest.clone(),java.util.Collections.unmodifiableMap(new java.util.TreeMap<>(influences))));continue;
            }
            var values=definition.getAsJsonArray("weights");
            if(part==null||values.size()!=part.vertices().length/stride)throw new IOException("Authored joint weight length: "+entry.getKey());
            float[] weights=new float[values.size()];
            for(int i=0;i<weights.length;i++){weights[i]=values.get(i).getAsFloat();if(!Float.isFinite(weights[i])||weights[i]<0||weights[i]>1)throw new IOException("Invalid joint weight");}
            float[] rest=part.vertices().clone();result.put(entry.getKey(),new JointSkin(definition.get("otherBone").getAsString(),weights,rest,rest.clone()));
        }
        return Map.copyOf(result);
    }

    private static Vector3f restPoint(MeshPart p,int offset)
    {
        return new Vector3f(p.vertices()[offset]+p.pivotX(),
                p.vertices()[offset+1]+p.pivotY(),p.vertices()[offset+2]+p.pivotZ());
    }

    private static Map<String,JointSkin> jointSkins(Map<String,MeshPart> parts,int stride)
    {
        Map<String,JointSkin> result=new HashMap<>();
            for(String joint:new String[]{"elbow","ankle","wrist"})for(String side:new String[]{"l","r"})
        {
                String upper=(joint.equals("elbow")?"arm_":joint.equals("ankle")?"shin_":"forearm_")+side,lower=(joint.equals("elbow")?"forearm_":joint.equals("ankle")?"foot_":"hand_")+side;
            var a=parts.get(upper);var b=parts.get(lower);if(a==null||b==null)continue;
            // Pivot + relative coordinates can round to opposite sides of a
            // quantization cell. Match spatially and give BOTH copies the same
            // rest point and exactly half weight; a near-half weight still tears.
            float epsilonSquared=.002F*.002F;
            var seam=new ArrayList<Vector3f>();
            for(int i=0;i<a.vertices().length;i+=stride)
            {
                var point=restPoint(a,i);
                for(int j=0;j<b.vertices().length;j+=stride)
                {
                    var other=restPoint(b,j);if(point.distanceSquared(other)>epsilonSquared)continue;
                    var centre=new Vector3f(point).add(other).mul(.5F);
                    if(seam.stream().noneMatch(v->v.distanceSquared(centre)<epsilonSquared))seam.add(centre);
                    break;
                }
            }
            if(seam.size()<3)continue;
            for(String name:new String[]{upper,lower})
            {
                var p=parts.get(name);float[] weights=new float[p.vertices().length/stride],rest=p.vertices().clone();
                for(int i=0;i<weights.length;i++)
                {
                    var point=restPoint(p,i*stride);float distanceSquared=Float.POSITIVE_INFINITY;Vector3f nearest=null;
                    for(var s:seam){float d=point.distanceSquared(s);if(d<distanceSquared){distanceSquared=d;nearest=s;}}
                    if(distanceSquared<epsilonSquared)
                    {
                        weights[i]=.5F;rest[i*stride]=nearest.x-p.pivotX();
                        rest[i*stride+1]=nearest.y-p.pivotY();rest[i*stride+2]=nearest.z-p.pivotZ();
                    }
                    else
                    {
                        float t=Math.max(0,1-(float)Math.sqrt(distanceSquared)/6);weights[i]=.5F*t*t*(3-2*t);
                    }
                }
                    mergeJointSkin(result,name,p,name.equals(upper)?lower:upper,weights,rest);
            }
            ProjectSeele.LOGGER.info("EVA joint skin seam: joint={} side={} sharedVertices={}",joint,side,seam.size());
        }
            if(parts.containsKey("head")&&parts.containsKey("torso_upper"))
            {
                var p=parts.get("head");float[] weights=new float[p.vertices().length/stride];
                for(int i=0;i<weights.length;i++)
                {
                    float y=p.vertices()[i*stride+1]+p.pivotY(),z=p.vertices()[i*stride+2]+p.pivotZ();
                    float blend=Math.max(0,Math.min(1,(p.pivotY()+1.5F-y)/7F));
                    if(y>p.pivotY()-3&&z<-6)blend=0; // Helmet and new jaw stay rigid; only the neck sleeve bends.
                    weights[i]=blend*blend*(3-2*blend);
                }
                mergeJointSkin(result,"head",p,"torso_upper",weights,p.vertices().clone());
            }
            return Map.copyOf(result);
    }

    private static void mergeJointSkin(Map<String,JointSkin> result,String name,MeshPart part,String other,float[] weights,float[] rest)
    {
        var previous=result.get(name);
        if(previous==null){result.put(name,new JointSkin(other,weights,rest,rest.clone()));return;}
        Map<String,float[]> all=new java.util.TreeMap<>();int count=weights.length;
        if(previous.influences().isEmpty())
        {
            all.put(previous.other(),previous.weights().clone());float[] own=new float[count];for(int i=0;i<count;i++)own[i]=1-previous.weights()[i];all.put(name,own);
        }
        else previous.influences().forEach((n,w)->all.put(n,w.clone()));
        float[] own=all.get(name),added=all.computeIfAbsent(other,n->new float[count]);
        for(int i=0;i<count;i++){float take=Math.min(own[i],weights[i]);own[i]-=take;added[i]+=take;}
        result.put(name,new JointSkin("",new float[0],rest,rest.clone(),Map.copyOf(all)));
    }

    private static GeoBone findBone(GeoBone bone,String name)
    {
        if(bone.getName().equals(name))return bone;
        for(var child:bone.getChildBones()){var found=findBone(child,name);if(found!=null)return found;}
        return null;
    }

    /** Dual-quaternion blending keeps both copies of every seam vertex coincident. */
    private static float[] skinVertices(MeshData mesh,MeshPart part,GeoBone bone)
    {
        var skin=mesh.joints().get(bone.getName());if(skin==null)return part.vertices();
        if(!skin.influences().isEmpty())return skinAuthored(mesh,part,bone,skin);
        var root=bone;while(root.getParent()!=null)root=root.getParent();var other=findBone(root,skin.other());if(other==null)return part.vertices();
        var matrix=EvaRigTransforms.model(bone).invert().mul(EvaRigTransforms.model(other));
        var q=EvaRigTransforms.rotation(matrix);if(q.w<0)q.mul(-1);
        var dual=new org.joml.Quaternionf(matrix.m30(),matrix.m31(),matrix.m32(),0).mul(q).mul(.5F);
        float[] source=skin.rest(),out=skin.scratch();int stride=mesh.stride();
        for(int vertex=0;vertex<skin.weights().length;vertex++)
        {
            float weight=skin.weights()[vertex];if(weight==0)continue;int i=vertex*stride;
            float rx=q.x*weight,ry=q.y*weight,rz=q.z*weight,rw=1-weight+q.w*weight;
            float inv=1F/(float)Math.sqrt(rx*rx+ry*ry+rz*rz+rw*rw);rx*=inv;ry*=inv;rz*=inv;rw*=inv;
            float dx=dual.x*weight*inv,dy=dual.y*weight*inv,dz=dual.z*weight*inv,dw=dual.w*weight*inv;
            float dot=rx*dx+ry*dy+rz*dz+rw*dw;dx-=rx*dot;dy-=ry*dot;dz-=rz*dot;dw-=rw*dot;
            float tx=2*(-dw*rx+dx*rw-dy*rz+dz*ry),ty=2*(-dw*ry+dx*rz+dy*rw-dz*rx),tz=2*(-dw*rz-dx*ry+dy*rx+dz*rw);
            float x=-(source[i]+part.pivotX())/16,y=(source[i+1]+part.pivotY())/16,z=(source[i+2]+part.pivotZ())/16;
            float ax=2*(ry*z-rz*y),ay=2*(rz*x-rx*z),az=2*(rx*y-ry*x);
            out[i]=-(x+rw*ax+ry*az-rz*ay+tx)*16-part.pivotX();
            out[i+1]=(y+rw*ay+rz*ax-rx*az+ty)*16-part.pivotY();out[i+2]=(z+rw*az+rx*ay-ry*ax+tz)*16-part.pivotZ();
            x=-source[i+5];y=source[i+6];z=source[i+7];ax=2*(ry*z-rz*y);ay=2*(rz*x-rx*z);az=2*(rx*y-ry*x);
            out[i+5]=-(x+rw*ax+ry*az-rz*ay);out[i+6]=y+rw*ay+rz*ax-rx*az;out[i+7]=z+rw*az+rx*ay-ry*ax;
        }
        return out;
    }

    /** Generated bodies can have three-way shoulder/hip junctions. All
     * copies share the complete authored weights, avoiding pairwise tears. */
    private static float[] skinAuthored(MeshData mesh,MeshPart part,GeoBone bone,JointSkin skin)
    {
        var root=bone;while(root.getParent()!=null)root=root.getParent();
        var inverse=EvaRigTransforms.model(bone).invert();var inverseRotation=EvaRigTransforms.rotation(inverse);int palette=skin.influences().size(),slot=0;
        float[][] transforms=new float[palette][8],weights=new float[palette][];
        for(var entry:skin.influences().entrySet())
        {
            var other=findBone(root,entry.getKey());if(other==null)throw new IllegalStateException("Authored seam bone missing: "+entry.getKey());
            var model=EvaRigTransforms.model(other);var global=EvaRigTransforms.rotation(model);if(global.w<0)global.mul(-1);
            var relative=new Matrix4f(inverse).mul(model);var q=EvaRigTransforms.rotation(relative);
            // All seam copies use the same global quaternion hemisphere.
            // Choosing a separate short arc around each owning part tears
            // three-way junctions when limbs fold past 180 degrees.
            if(q.dot(new org.joml.Quaternionf(inverseRotation).mul(global))<0)q.mul(-1);
            var dual=new org.joml.Quaternionf(relative.m30(),relative.m31(),relative.m32(),0).mul(q).mul(.5F);
            transforms[slot]=new float[]{q.x,q.y,q.z,q.w,dual.x,dual.y,dual.z,dual.w};weights[slot++]=entry.getValue();
        }
        float[] rest=skin.rest(),out=skin.scratch();int stride=mesh.stride();
        for(int vertex=0;vertex<rest.length/stride;vertex++)
        {
            float rx=0,ry=0,rz=0,rw=0,dx=0,dy=0,dz=0,dw=0;
            int dominant=0;for(int p=1;p<palette;p++)if(weights[p][vertex]>weights[dominant][vertex])dominant=p;
            var reference=transforms[dominant];
            for(int p=0;p<palette;p++)
            {
                float weight=weights[p][vertex];if(weight==0)continue;var t=transforms[p];
                if(t[0]*reference[0]+t[1]*reference[1]+t[2]*reference[2]+t[3]*reference[3]<0)weight=-weight;
                rx+=t[0]*weight;ry+=t[1]*weight;rz+=t[2]*weight;rw+=t[3]*weight;
                dx+=t[4]*weight;dy+=t[5]*weight;dz+=t[6]*weight;dw+=t[7]*weight;
            }
            float inv=1F/(float)Math.sqrt(rx*rx+ry*ry+rz*rz+rw*rw);rx*=inv;ry*=inv;rz*=inv;rw*=inv;dx*=inv;dy*=inv;dz*=inv;dw*=inv;
            float dot=rx*dx+ry*dy+rz*dz+rw*dw;dx-=rx*dot;dy-=ry*dot;dz-=rz*dot;dw-=rw*dot;
            float tx=2*(-dw*rx+dx*rw-dy*rz+dz*ry),ty=2*(-dw*ry+dx*rz+dy*rw-dz*rx),tz=2*(-dw*rz-dx*ry+dy*rx+dz*rw);
            int i=vertex*stride;float x=-(rest[i]+part.pivotX())/16,y=(rest[i+1]+part.pivotY())/16,z=(rest[i+2]+part.pivotZ())/16;
            float ax=2*(ry*z-rz*y),ay=2*(rz*x-rx*z),az=2*(rx*y-ry*x);
            out[i]=-(x+rw*ax+ry*az-rz*ay+tx)*16-part.pivotX();out[i+1]=(y+rw*ay+rz*ax-rx*az+ty)*16-part.pivotY();out[i+2]=(z+rw*az+rx*ay-ry*ax+tz)*16-part.pivotZ();
            x=-rest[i+5];y=rest[i+6];z=rest[i+7];ax=2*(ry*z-rz*y);ay=2*(rz*x-rx*z);az=2*(rx*y-ry*x);
            out[i+5]=-(x+rw*ax+ry*az-rz*ay);out[i+6]=y+rw*ay+rz*ax-rx*az;out[i+7]=z+rw*az+rx*ay-ry*ax;
        }
        return out;
    }

    private record MeshPart(float pivotX, float pivotY, float pivotZ,
                            float[] vertices, float muzzleX,
                            float muzzleY, float muzzleZ,float red,float green,float blue) {}
}

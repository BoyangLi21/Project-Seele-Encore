package com.projectseele.client.render;

import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.resources.ResourceLocation;
import org.joml.Matrix4f;
import org.joml.Quaternionf;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.GeoBone;
import software.bernie.geckolib.core.animatable.GeoAnimatable;
import software.bernie.geckolib.renderer.GeoRenderer;
import software.bernie.geckolib.renderer.layer.GeoRenderLayer;
import java.util.*;

/** Four-influence skinning for local Angel rigs; UV duplicates share the same deformation. */
public final class RiggedAngelLayer<T extends GeoAnimatable> extends GeoRenderLayer<T>
{
    private static final Map<ResourceLocation,Model> CACHE=new HashMap<>();
    private static final Set<ResourceLocation> ATTEMPTED=new HashSet<>();
    private final ResourceLocation resource;
    private record Model(String[] bones,float[] vertices,int[] indices,float[] weights,float[] groundedVertices) {}

    public RiggedAngelLayer(GeoRenderer<T> renderer,ResourceLocation resource)
    {
        super(renderer);this.resource=resource;
    }
    public static void clearCache(){CACHE.clear();ATTEMPTED.clear();SachielWrapSurface.clear();}
    public static boolean available(ResourceLocation resource){return load(resource)!=null;}
    private static Model load(ResourceLocation resource)
    {
        if(ATTEMPTED.contains(resource))return CACHE.get(resource);
        ATTEMPTED.add(resource);
        var file=Minecraft.getInstance().getResourceManager().getResource(resource);if(file.isEmpty())return null;
        try(var stream=file.get().open())
        {
            byte[] loadedBytes=stream.readAllBytes();
            var json=JsonParser.parseString(new String(loadedBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();if(!json.has("skin"))return null;
            if(json.get("stride").getAsInt()!=8)throw new IllegalArgumentException("Invalid weighted mesh stride");
            var skin=json.getAsJsonObject("skin");var names=skin.getAsJsonArray("bones");String[] bones=new String[names.size()];
            for(int i=0;i<bones.length;i++)bones[i]=names.get(i).getAsString();
            var source=json.getAsJsonObject("parts").getAsJsonObject("root").getAsJsonArray("vertices");
            float[] vertices=new float[source.size()];for(int i=0;i<vertices.length;i++)vertices[i]=source.get(i).getAsFloat();
            if(vertices.length%24!=0)throw new IllegalArgumentException("Incomplete weighted triangles");
            var ji=skin.getAsJsonArray("indices");var jw=skin.getAsJsonArray("weights");
            if(ji.size()!=vertices.length/2||jw.size()!=ji.size())throw new IllegalArgumentException("Invalid skin influence count");
            int[] indices=new int[ji.size()];float[] weights=new float[ji.size()];
            for(int i=0;i<indices.length;i++)
            {
                indices[i]=ji.get(i).getAsInt();weights[i]=jw.get(i).getAsFloat();
                if(indices[i]<0||indices[i]>=bones.length||!Float.isFinite(weights[i])||weights[i]<0)throw new IllegalArgumentException("Invalid skin influence");
            }
            for(int i=0;i<weights.length;i+=4)if(Math.abs(weights[i]+weights[i+1]+weights[i+2]+weights[i+3]-1)>1e-4)throw new IllegalArgumentException("Unnormalized skin weights");
            for(float v:vertices)if(!Float.isFinite(v))throw new IllegalArgumentException("Non-finite skin vertex");
            Model model=new Model(bones,vertices,indices,weights,new float[vertices.length/8*6]);CACHE.put(resource,model);
            if(RiggedAngelSkinWitnessR44.ENABLED)RiggedAngelSkinWitnessR44.parsed(resource,file.get().sourcePackId(),
                    java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(loadedBytes)),bones,vertices,indices,weights);
            SachielWrapSurface.prepare(resource,vertices.length/8);
            ProjectSeele.LOGGER.info("R10 weighted Angel loaded: {} triangles={} bones={}",resource,vertices.length/24,bones.length);return model;
        }
        catch(Exception e){ProjectSeele.LOGGER.error("R10 weighted Angel rejected: {}",resource,e);return null;}
    }
    private static void collect(GeoBone bone,Map<String,GeoBone> bones)
    {
        bones.put(bone.getName(),bone);for(var child:bone.getChildBones())collect(child,bones);
    }
    @Override public void renderForBone(PoseStack stack,T entity,GeoBone root,RenderType type,MultiBufferSource buffers,
                                        VertexConsumer target,float partial,int light,int overlay)
    {
        if(!root.getName().equals("root")||root.isHidden())return;
        Model model=load(resource);if(model==null)return;
        Map<String,GeoBone> bones=new HashMap<>();collect(root,bones);
        Matrix4f inverseRoot=EvaRigTransforms.model(root).invert();
        Matrix4f witnessWorld=RiggedAngelSkinWitnessR44.ENABLED&&entity instanceof net.minecraft.world.entity.Entity actor&&getRenderer() instanceof HybridAddonRenderer.MeshBackedRenderer<?> renderer?renderer.renderedMeshTransform(stack.last().pose(),actor,partial):null;
        var skinWitness=RiggedAngelSkinWitnessR44.begin(entity,resource,partial,witnessWorld);
        Matrix4f sharedContactWorld=SharedHandContactWitnessR44.ENABLED&&entity instanceof net.minecraft.world.entity.LivingEntity actor
                &&getRenderer() instanceof HybridAddonRenderer.MeshBackedRenderer<?> renderer?renderer.renderedMeshTransform(stack.last().pose(),actor,partial):null;
        if(entity instanceof net.minecraft.world.entity.Entity worldEntity
                &&entity instanceof com.projectseele.entity.FirstBattleSignals.Actor actor
                &&!actor.isFirstBattleEva()&&actor.firstBattleSignals().active(worldEntity))
        {
            float seconds=actor.firstBattleSignals().time(worldEntity,partial);
            var surface=SachielWrapSurface.frame(resource,model.vertices.length/8,seconds);
            if(surface!=null)
            {
                var origin=com.projectseele.entity.FirstBattleClip.localPoint(actor.firstBattleSignals().spec(worldEntity),false,"root_blocks",seconds);
                Vector3f p=new Vector3f(),n=new Vector3f();
                Matrix4f auditWorld=com.projectseele.client.visual.SachielWrapR14Audit.ENABLED&&getRenderer() instanceof HybridAddonRenderer.MeshBackedRenderer<?> renderer?renderer.renderedMeshTransform(stack.last().pose(),worldEntity,partial):null;
                for(int vertex=0;vertex<surface.vertexCount();vertex++)
                {
                    surface.sample(vertex,p,n);
                    Vector3f authored=com.projectseele.client.visual.SachielWrapR14Audit.ENABLED&&vertex%(Math.max(1,surface.vertexCount()/16))==0?new Vector3f(p):null;
                    p.sub((float)origin.x,(float)origin.y,(float)origin.z).div(5);
                    inverseRoot.transformPosition(p);inverseRoot.transformDirection(n).normalize();
                    if(skinWitness!=null)skinWitness.vertex(p);
                    if(entity instanceof net.minecraft.world.entity.LivingEntity living)SharedHandContactWitnessR44.targetVertex(living,p,sharedContactWorld,"actual-wrap-cache");
                    if(authored!=null&&auditWorld!=null)com.projectseele.client.visual.SachielWrapR14Audit.sample(worldEntity,actor,auditWorld,p,authored);
                    emit(target,stack,p,n,surface.u(vertex),surface.v(vertex),light,overlay);
                    if(vertex%3==2)emit(target,stack,p,n,surface.u(vertex),surface.v(vertex),light,overlay);
                }
                if(skinWitness!=null)skinWitness.finish("wrap-cache");return;
            }
        }
        Quaternionf[] real=new Quaternionf[model.bones.length],dual=new Quaternionf[model.bones.length];
        Matrix4f[] matrices=new Matrix4f[model.bones.length];boolean[] scaled=new boolean[model.bones.length];
        for(int i=0;i<real.length;i++)
        {
            GeoBone bone=bones.get(model.bones[i]);if(bone==null)return;
            Matrix4f matrix=new Matrix4f(inverseRoot).mul(EvaRigTransforms.model(bone));matrices[i]=matrix;
            Vector3f scale=matrix.getScale(new Vector3f());scaled[i]=scale.distanceSquared(1,1,1)>1e-6F;
            real[i]=matrix.getUnnormalizedRotation(new Quaternionf()).normalize();
            Vector3f translation=matrix.getTranslation(new Vector3f());
            dual[i]=new Quaternionf(translation.x,translation.y,translation.z,0).mul(real[i]).mul(.5F);
        }
        if(skinWitness!=null)skinWitness.palette(model.bones,matrices,scaled,real,dual);
        Quaternionf q=new Quaternionf(),d=new Quaternionf(),translation=new Quaternionf(),conjugate=new Quaternionf();
        Vector3f point=new Vector3f(),normal=new Vector3f(),work=new Vector3f();
        boolean grounded=entity instanceof net.minecraft.world.entity.LivingEntity living&&AngelCombatPoseR31.needsGroundSupport(living);
        Matrix4f rootModel=grounded?EvaRigTransforms.model(root):null;float floor=Float.POSITIVE_INFINITY;
        Matrix4f contactAudit=com.projectseele.visual.CombatR31Review.ENABLED&&entity instanceof net.minecraft.world.entity.Entity actor&&getRenderer() instanceof HybridAddonRenderer.MeshBackedRenderer<?> renderer?renderer.renderedMeshTransform(stack.last().pose(),actor,partial):null;
        float worldFloor=Float.POSITIVE_INFINITY;
        for(int vertex=0;vertex<model.vertices.length/8;vertex++)
        {
            int i=vertex*8,j=vertex*4;float[] v=model.vertices;
            point.set(-v[i]/16,v[i+1]/16,v[i+2]/16);normal.set(-v[i+5],v[i+6],v[i+7]);
            boolean hasScale=false;for(int k=0;k<4;k++)hasScale|=model.weights[j+k]>0&&scaled[model.indices[j+k]];
            if(hasScale)
            {
                float x=point.x,y=point.y,z=point.z;point.zero();
                for(int k=0;k<4;k++)if(model.weights[j+k]>0)
                {
                    matrices[model.indices[j+k]].transformPosition(work.set(x,y,z));point.fma(model.weights[j+k],work);
                }
                matrices[model.indices[j]].normal(new org.joml.Matrix3f()).transform(normal).normalize();
            }
            else
            {
                q.set(0,0,0,0);d.set(0,0,0,0);
                int referenceBone=DqSkinReferenceR44.REVIEW
                        ?DqSkinReferenceR44.referenceBone(model.indices,model.weights,j,4)
                        :model.indices[j];
                Quaternionf reference=real[referenceBone];
                for(int k=0;k<4;k++)
                {
                    float weight=model.weights[j+k];if(weight==0)continue;int b=model.indices[j+k];
                    // The isolated DCC candidate aligns each positive slot
                    // against the already weighted running sum. Zero padding
                    // neither owns a reference nor advances that sum.
                    if((DqSkinReferenceR44.RUNNING?q:reference).dot(real[b])<0)weight=-weight;
                    q.x+=real[b].x*weight;q.y+=real[b].y*weight;q.z+=real[b].z*weight;q.w+=real[b].w*weight;
                    d.x+=dual[b].x*weight;d.y+=dual[b].y*weight;d.z+=dual[b].z*weight;d.w+=dual[b].w*weight;
                }
                float length=(float)Math.sqrt(q.lengthSquared());q.mul(1/length);d.mul(1/length);float orthogonal=q.dot(d);
                d.x-=q.x*orthogonal;d.y-=q.y*orthogonal;d.z-=q.z*orthogonal;d.w-=q.w*orthogonal;
                translation.set(d).mul(conjugate.set(q).conjugate());q.transform(point);point.add(2*translation.x,2*translation.y,2*translation.z);q.transform(normal).normalize();
            }
            if(grounded)
            {
                int at=vertex*6;float[] output=model.groundedVertices;
                output[at]=point.x;output[at+1]=point.y;output[at+2]=point.z;output[at+3]=normal.x;output[at+4]=normal.y;output[at+5]=normal.z;
                floor=Math.min(floor,rootModel.m01()*point.x+rootModel.m11()*point.y+rootModel.m21()*point.z+rootModel.m31());
            }
            else
            {
                if(contactAudit!=null)worldFloor=Math.min(worldFloor,contactAudit.m01()*point.x+contactAudit.m11()*point.y+contactAudit.m21()*point.z+contactAudit.m31());
                if(skinWitness!=null)skinWitness.vertex(point);
                if(entity instanceof net.minecraft.world.entity.LivingEntity living)SharedHandContactWitnessR44.targetVertex(living,point,sharedContactWorld,"actual-weighted-final-emit");
                emit(target,stack,point,normal,v[i+3],v[i+4],light,overlay);
                if(vertex%3==2)emit(target,stack,point,normal,v[i+3],v[i+4],light,overlay);
            }
        }
        if(grounded&&Float.isFinite(floor))
        {
            // Reuse the exact DQS output already calculated above. A fixed
            // pelvis offset cannot support both Sachiel and Shamshel, nor all
            // four fall directions. Translate the rigid assembly, never scale
            // limbs or run an approximate second skinning pass.
            Vector3f lift=inverseRoot.transformDirection(new Vector3f(0,.016F-floor,0));
            if(skinWitness!=null)skinWitness.supportTranslation(lift);
            for(int vertex=0;vertex<model.vertices.length/8;vertex++)
            {
                int at=vertex*6,i=vertex*8;float[] output=model.groundedVertices;
                point.set(output[at],output[at+1],output[at+2]).add(lift);normal.set(output[at+3],output[at+4],output[at+5]);
                if(skinWitness!=null)skinWitness.vertex(point);
                if(entity instanceof net.minecraft.world.entity.LivingEntity living)SharedHandContactWitnessR44.targetVertex(living,point,sharedContactWorld,"actual-weighted-ground-lift-final-emit");
                if(contactAudit!=null)worldFloor=Math.min(worldFloor,contactAudit.m01()*point.x+contactAudit.m11()*point.y+contactAudit.m21()*point.z+contactAudit.m31());
                emit(target,stack,point,normal,model.vertices[i+3],model.vertices[i+4],light,overlay);
                if(vertex%3==2)emit(target,stack,point,normal,model.vertices[i+3],model.vertices[i+4],light,overlay);
            }
        }
        if(skinWitness!=null)skinWitness.finish(grounded?"grounded-final-lift":DqSkinReferenceR44.RUNNING?"running-sum-review-or-scale-lbs":DqSkinReferenceR44.REVIEW?"dominant-review-or-scale-lbs":"first-slot-or-scale-lbs");
        if(contactAudit!=null&&entity instanceof net.minecraft.world.entity.LivingEntity living)com.projectseele.client.visual.CombatR31Client.angelSupport(living,worldFloor);
    }
    private static void emit(VertexConsumer target,PoseStack stack,Vector3f p,Vector3f n,float u,float v,int light,int overlay)
    {
        MeshVertexWriter.emit(target,stack.last().pose(),stack.last().normal(),p.x,p.y,p.z,u,v,light,overlay,n.x,n.y,n.z);
    }
}

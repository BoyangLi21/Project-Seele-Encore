package com.projectseele.client.render;

import com.projectseele.entity.*;
import com.google.gson.JsonParser;
import com.mojang.blaze3d.vertex.VertexConsumer;
import net.minecraft.client.Minecraft;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import software.bernie.geckolib.cache.object.BakedGeoModel;
import java.util.*;

/** Hold the legs in a restrained hover pose; keep the upper body in the rifle's existing rig. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class UNFlightPoseR29
{
    private record Pose(long frame,float weight,float gimbal){}
    private record Jets(Vec3 left,Vec3 right,Vec3 leftAxis,Vec3 rightAxis,long frame){}
    private static final Map<EvaPrototypeEntity,Pose> POSES=new WeakHashMap<>();
    private static final Map<EvaPrototypeEntity,Jets> JETS=new WeakHashMap<>();
    private static final Map<String,Vector3f> SOLES=new HashMap<>();
    public static void resetEntityR31(EvaUnit01Entity eva)
    {if(eva instanceof EvaPrototypeEntity un){POSES.remove(un);JETS.remove(un);}}
    private static Vector3f sole(String side)
    {
        return SOLES.computeIfAbsent(side,key->
        {
            try(var reader=Minecraft.getInstance().getResourceManager().getResource(new ResourceLocation("projectseele","mesh/eva_un01.mesh.json")).orElseThrow().openAsReader())
            {
                var p=JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("parts").getAsJsonObject("foot_"+side);var pivot=p.getAsJsonArray("pivot");var a=p.getAsJsonArray("vertices");float bottom=Float.POSITIVE_INFINITY;
                for(int i=1;i<a.size();i+=8)bottom=Math.min(bottom,a.get(i).getAsFloat());
                Vector3f sum=new Vector3f();int n=0;
                for(int i=0;i<a.size();i+=8)if(a.get(i+1).getAsFloat()<=bottom+.08F)
                {sum.add(-(a.get(i).getAsFloat()+pivot.get(0).getAsFloat())/16,(a.get(i+1).getAsFloat()+pivot.get(1).getAsFloat())/16,(a.get(i+2).getAsFloat()+pivot.get(2).getAsFloat())/16);n++;}
                return sum.div(Math.max(1,n));
            }
            catch(Exception error){com.projectseele.ProjectSeele.LOGGER.warn("UN flight sole geometry unavailable",error);return new Vector3f();}
        });
    }
    public static EvaMotionEngineV2.BoneWrites apply(EvaUnit01Entity eva,BakedGeoModel model,float partial,Matrix4f root)
    {
        if(!(eva instanceof EvaPrototypeEntity un)||un.getUNSerial()!=1)return EvaMotionEngineV2.BoneWrites.empty();
        boolean measured=model.getBone("tripo_thruster_measured_r48").isPresent();
        if(eva.isNervLogisticsLocked()||eva.hasActiveCarrierMotion()||eva.isLaunchSequenceActive())
        {POSES.remove(un);JETS.remove(un);return stowNozzles(model,65);}
        long now=System.nanoTime();var old=POSES.get(un);float target=un.isUNFlying()?1:0;
        float blend=old==null?1:(float)(1-Math.exp(-Math.min(.1,(now-old.frame)/1e9)*9));
        float weight=old==null?target:old.weight+(target-old.weight)*blend;
        float gimbalTarget=un.isUNFlying()?65-50*(float)Math.min(1,un.getDeltaMovement().horizontalDistance()/2.8):65;
        float gimbal=old==null?gimbalTarget:old.gimbal+(gimbalTarget-old.gimbal)*blend;POSES.put(un,new Pose(now,weight,gimbal));
        if(weight<.001)return stowNozzles(model,gimbal);Set<String> changed=new HashSet<>(),positions=new HashSet<>();
        for(String side:List.of("l","r"))
        {
            for(var entry:Map.of("leg_",-9F,"shin_",18F,"ankle_",0F,"foot_",-9F).entrySet())
            {
                String name=entry.getKey()+side;var bone=model.getBone(name).orElse(null);if(bone==null)continue;var bind=bone.getInitialSnapshot();
                float goal=bind.getRotX()+(float)Math.toRadians(entry.getValue());bone.setRotX(bone.getRotX()+(goal-bone.getRotX())*weight);bone.setRotY(bone.getRotY()+(bind.getRotY()-bone.getRotY())*weight);bone.setRotZ(bone.getRotZ()+(bind.getRotZ()-bone.getRotZ())*weight);changed.add(name);
            }
            var shin=model.getBone("shin_"+side).orElse(null);if(shin!=null){EvaRigTransforms.hinge(shin,EvaRigTransforms.knee(shin));positions.add("shin_"+side);}
            var nozzle=model.getBone("r30_thruster_"+side).orElse(null);if(nozzle!=null){nozzle.setRotX(measured?0:(float)Math.toRadians(gimbal));nozzle.setRotY(0);nozzle.setRotZ(0);changed.add(nozzle.getName());}
        }
        if(un.isUNFlying()&&root!=null)
        {
            var left=model.getBone("r30_thruster_l").orElse(null);var right=model.getBone("r30_thruster_r").orElse(null);
            if(left!=null&&right!=null)
            {
                float tail=measured?0:6.25F/16;
                var a=EvaRigTransforms.point(left,EvaRigTransforms.pivot(left).add(0,0,tail),root);var b=EvaRigTransforms.point(right,EvaRigTransforms.pivot(right).add(0,0,tail),root);
                Vector3f direction=measured?new Vector3f(0,-(float)Math.sin(Math.toRadians(gimbal)),(float)Math.cos(Math.toRadians(gimbal))):new Vector3f(0,0,1);
                var da=new Matrix4f(root).mul(EvaRigTransforms.model(left)).transformDirection(new Vector3f(direction)).normalize();var db=new Matrix4f(root).mul(EvaRigTransforms.model(right)).transformDirection(new Vector3f(direction)).normalize();
                JETS.put(un,new Jets(new Vec3(a.x,a.y,a.z),new Vec3(b.x,b.y,b.z),new Vec3(da.x,da.y,da.z),new Vec3(db.x,db.y,db.z),now));
            }
            else
            {
                left=model.getBone("foot_l").orElse(null);right=model.getBone("foot_r").orElse(null);
                if(left!=null&&right!=null){var a=EvaRigTransforms.point(left,sole("l"),root);var b=EvaRigTransforms.point(right,sole("r"),root);JETS.put(un,new Jets(new Vec3(a.x,a.y,a.z),new Vec3(b.x,b.y,b.z),new Vec3(0,-1,0),new Vec3(0,-1,0),now));}
            }
        }
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.copyOf(positions),"MOTION_ENGINE_LIVE_ACTION");
    }
    private static EvaMotionEngineV2.BoneWrites stowNozzles(BakedGeoModel model,float degrees)
    {
        Set<String> changed=new HashSet<>();
        boolean measured=model.getBone("tripo_thruster_measured_r48").isPresent();
        for(String side:List.of("l","r"))model.getBone("r30_thruster_"+side).ifPresent(b->{b.setRotX(measured?0:(float)Math.toRadians(degrees));b.setRotY(0);b.setRotZ(0);changed.add(b.getName());});
        return new EvaMotionEngineV2.BoneWrites(Set.copyOf(changed),Set.of(),"MOTION_ENGINE_LIVE_ACTION");
    }
    @SubscribeEvent public static void render(RenderLevelStageEvent event)
    {
        if(event.getStage()!=RenderLevelStageEvent.Stage.AFTER_PARTICLES)return;var mc=Minecraft.getInstance();if(mc.level==null)return;
        var buffers=mc.renderBuffers().bufferSource();VertexConsumer out=buffers.getBuffer(EnergyGlowR24.CROSS);var poses=event.getPoseStack();var camera=event.getCamera().getPosition();
        poses.pushPose();poses.translate(-camera.x,-camera.y,-camera.z);Matrix4f m=poses.last().pose();
        for(var entry:JETS.entrySet())
        {
            var un=entry.getKey();var jet=entry.getValue();if(un.level()!=mc.level||!un.isUNFlying()||System.nanoTime()-jet.frame>250_000_000L)continue;
            float length=6+(float)Math.min(1.5,Math.abs(un.getDeltaMovement().y))*5;
            for(int side=0;side<2;side++)
            {
                Vec3 point=side==0?jet.left:jet.right,direction=side==0?jet.leftAxis:jet.rightAxis;
                Vector3f a=point.toVector3f(),b=point.add(direction.scale(length)).toVector3f();
                RibbonRenderer.drawSoftStarRibbon(m,out,a,b,.85F,.1F,.32F,.72F,1,.75F);
                RibbonRenderer.drawSoftStarRibbon(m,out,a,b,.32F,.02F,.92F,.97F,1,.90F);
            }
        }
        poses.popPose();buffers.endBatch(EnergyGlowR24.CROSS);
    }
    private UNFlightPoseR29() {}
}

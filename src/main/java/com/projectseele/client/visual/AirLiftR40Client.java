package com.projectseele.client.visual;

import com.projectseele.ProjectSeele;
import com.projectseele.visual.AirLiftR30Review;
import com.projectseele.world.FacilitySchemaV2;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Isolated real observer receives the same positional landing sound as a player. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class AirLiftR40Client
{
    private static final boolean ENABLED="r40-airlift".equals(System.getProperty("projectseele.regionalBuild",""));
    private static int ticks;
    private static final java.util.Queue<com.google.gson.JsonObject> soundEvidence=new java.util.concurrent.ConcurrentLinkedQueue<>();
    private static final java.util.Map<String,String> soundHashes=new java.util.concurrent.ConcurrentHashMap<>();
    private static boolean wroteEvidence;
    private static String photoPhase="";private static int stablePhase;
    private static final java.util.Set<String> photos=new java.util.HashSet<>();
    private static CombatR31Client.View lastView;
    private static boolean clearView;
    private static net.minecraft.world.phys.AABB framedBounds;
    private static int testedRays, clearRays;
    private static double maximumProjection;
    private static final com.google.gson.JsonArray cameraEvidence=new com.google.gson.JsonArray();
    public static CombatR31Client.View cameraView(float partial)
    {
        var mc=Minecraft.getInstance();if(!ENABLED||mc.level==null||mc.player==null)return null;
        if(!(mc.level.getEntity(AirLiftR30Review.observedEntity) instanceof com.projectseele.entity.EvaUnit01Entity eva))return null;
        var pose=com.projectseele.entity.EvaBodyPose.sample(eva,partial);
        var root=com.projectseele.entity.EvaAirTransportR31.active(eva)
                ?com.projectseele.entity.EvaAirTransportR31.framePosition(eva,partial)
                :new net.minecraft.world.phys.Vec3(net.minecraft.util.Mth.lerp(partial,eva.xOld,eva.getX()),
                        net.minecraft.util.Mth.lerp(partial,eva.yOld,eva.getY()),
                        net.minecraft.util.Mth.lerp(partial,eva.zOld,eva.getZ()));
        float yaw=com.projectseele.entity.EvaAirTransportR31.active(eva)
                ?com.projectseele.entity.EvaAirTransportR31.frameYaw(eva,partial):eva.getYRot();
        var samples=new java.util.ArrayList<net.minecraft.world.phys.Vec3>();
        framedBounds=null;
        for(var local:com.projectseele.entity.EvaBodyPose.posedCarrierHulls(eva,pose))
        {
            var box=worldBox(local,root,yaw);framedBounds=framedBounds==null?box:framedBounds.minmax(box);
            samples.add(box.getCenter());
        }
        if(framedBounds==null)framedBounds=eva.getBoundingBoxForCulling();
        if(samples.isEmpty())samples.add(framedBounds.getCenter());
        // A cargo-only torso view can omit the head, feet, trunnions and the
        // entire aircraft. Include each linked transport assembly in framing.
        for(var entity:mc.level.entitiesForRendering())
        {
            if(entity instanceof com.projectseele.entity.UNTransportEntity transport
                    &&transport.cargoEntityId()==eva.getId()
                    &&transport.position().distanceToSqr(eva.position())<256D*256D)
            {
                framedBounds=framedBounds.minmax(transport.getBoundingBoxForCulling());
                samples.add(transport.getBoundingBox().getCenter());
            }
        }
        var target=framedBounds.getCenter();
        clearView=false;lastView=null;
        testedRays=clearRays=0;maximumProjection=Double.POSITIVE_INFINITY;
        double aspect=(double)mc.getWindow().getWidth()/Math.max(1,mc.getWindow().getHeight());
        double vertical=Math.tan(Math.toRadians(mc.options.fov().get()*.5D))*.8D;
        double horizontal=vertical*aspect;
        double radius=Math.sqrt(framedBounds.getXsize()*framedBounds.getXsize()
                +framedBounds.getYsize()*framedBounds.getYsize()+framedBounds.getZsize()*framedBounds.getZsize())*.5D;
        double distance=radius/Math.sin(Math.atan(Math.min(vertical,horizontal)))*1.2D;
        for(var direction:java.util.List.of(new net.minecraft.world.phys.Vec3(40,24,62),new net.minecraft.world.phys.Vec3(-40,24,62),new net.minecraft.world.phys.Vec3(45,28,-55),new net.minecraft.world.phys.Vec3(-45,28,-55),new net.minecraft.world.phys.Vec3(0,35,75),new net.minecraft.world.phys.Vec3(0,35,-75)))
        {
            var at=target.add(direction.normalize().scale(Math.max(70,distance)));
            var hit=mc.level.clip(new net.minecraft.world.level.ClipContext(at,target,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)continue;
            int visible=0;
            for(var point:samples)
            {
                var ray=mc.level.clip(new net.minecraft.world.level.ClipContext(at,point,
                        net.minecraft.world.level.ClipContext.Block.COLLIDER,
                        net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
                if(ray.getType()==net.minecraft.world.phys.HitResult.Type.MISS)visible++;
            }
            double projection=projection(framedBounds,at,target,vertical,horizontal);
            if(visible<Math.ceil(samples.size()*.8D)||projection>1D)continue;
            testedRays=samples.size();clearRays=visible;maximumProjection=projection;
            clearView=true;lastView=new CombatR31Client.View(at,target);return lastView;
        }
        return null;
    }
    private static net.minecraft.world.phys.AABB worldBox(net.minecraft.world.phys.AABB local,
            net.minecraft.world.phys.Vec3 root,float yaw)
    {
        net.minecraft.world.phys.AABB result=null;
        for(double x:new double[]{local.minX,local.maxX})for(double y:new double[]{local.minY,local.maxY})for(double z:new double[]{local.minZ,local.maxZ})
        {
            var v=new org.joml.Vector3f((float)x,(float)y,(float)z)
                    .rotateY((180-yaw)*net.minecraft.util.Mth.DEG_TO_RAD);
            var point=root.add(v.x,v.y,v.z);var box=new net.minecraft.world.phys.AABB(point,point);
            result=result==null?box:result.minmax(box);
        }
        return result;
    }
    private static double projection(net.minecraft.world.phys.AABB bounds,
            net.minecraft.world.phys.Vec3 at,net.minecraft.world.phys.Vec3 target,
            double vertical,double horizontal)
    {
        var forward=target.subtract(at).normalize();
        var right=forward.cross(new net.minecraft.world.phys.Vec3(0,1,0)).normalize();
        var up=right.cross(forward).normalize();double largest=0;
        for(double x:new double[]{bounds.minX,bounds.maxX})for(double y:new double[]{bounds.minY,bounds.maxY})for(double z:new double[]{bounds.minZ,bounds.maxZ})
        {
            var v=new net.minecraft.world.phys.Vec3(x,y,z).subtract(at);double depth=v.dot(forward);
            if(depth<=1D)return Double.POSITIVE_INFINITY;
            largest=Math.max(largest,Math.max(Math.abs(v.dot(right))/(depth*horizontal),
                    Math.abs(v.dot(up))/(depth*vertical)));
        }
        return largest;
    }
    @SubscribeEvent public static void sound(net.minecraftforge.client.event.sound.SoundEvent.SoundSourceEvent event)
    {
        if(!ENABLED||event.getSound()==null)return;
        var sound=event.getSound();String id=sound.getLocation().toString();
        if(!id.equals("projectseele:eva_land")&&!id.equals("projectseele:eva_joint_load"))return;
        var mc=Minecraft.getInstance();var row=new com.google.gson.JsonObject();
        row.addProperty("event",id);row.addProperty("stage",AirLiftR30Review.reviewStage);row.addProperty("phase",AirLiftR30Review.reviewPhase);
        row.addProperty("volume",sound.getVolume());row.addProperty("pitch",sound.getPitch());row.addProperty("category_volume",mc.options.getSoundSourceVolume(sound.getSource()));
        row.addProperty("master_volume",mc.options.getSoundSourceVolume(net.minecraft.sounds.SoundSource.MASTER));
        var point=new net.minecraft.world.phys.Vec3(sound.getX(),sound.getY(),sound.getZ());
        row.addProperty("distance_to_camera",point.distanceTo(mc.gameRenderer.getMainCamera().getPosition()));
        if(sound.getSound()!=null)
        {
            var sample=sound.getSound();row.addProperty("sample",sample.getLocation().toString());row.addProperty("attenuation_distance",sample.getAttenuationDistance());
            mc.getResourceManager().getResource(sample.getPath()).ifPresent(resource->{
                row.addProperty("pack",resource.sourcePackId());
                try
                {
                    String key=sample.getPath().toString(),hash=soundHashes.get(key);
                    if(hash==null){try(var input=resource.open()){hash=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(input.readAllBytes()));}soundHashes.put(key,hash);}
                    row.addProperty("sha256",hash);
                }
                catch(Exception error){row.addProperty("fingerprint_error",error.toString());}
            });
        }
        soundEvidence.add(row);
    }
    private static java.nio.file.Path output()
    {
        String custom=System.getProperty("projectseele.reviewArtifactRoot","");
        return custom.isBlank()?java.nio.file.Path.of("../artifacts/world_combat_r40/airlift/native_photos_"+Integer.getInteger("projectseele.airReviewUnSerial",0)):java.nio.file.Path.of(custom);
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;
        var mc=Minecraft.getInstance();
        if(AirLiftR30Review.finished())
        {
            if(!wroteEvidence)
            {
                try{java.nio.file.Files.createDirectories(output());java.nio.file.Files.writeString(output().resolve("resolved_landing_sounds.json"),new com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(soundEvidence));java.nio.file.Files.writeString(output().resolve("camera_evidence.json"),new com.google.gson.GsonBuilder().setPrettyPrinting().create().toJson(cameraEvidence));}
                catch(Exception error){throw new IllegalStateException("Cannot save landing audio evidence",error);}
                wroteEvidence=true;
            }
            mc.stop();return;
        }
        var server=mc.getSingleplayerServer();
        if(server==null||mc.player==null||AirLiftR30Review.observer==null)return;
        ++ticks;
        if(!server.getWorldPath(LevelResource.ROOT).normalize().getFileName().toString().equals(AirLiftR30Review.reviewWorld()))throw new IllegalStateException("Airlift review boundary");
        mc.options.pauseOnLostFocus=false;
        mc.options.renderDistance().set(8);
        var at=AirLiftR30Review.observer.add(0,20,-30);
        server.execute(()->{
            var player=server.getPlayerList().getPlayers().get(0);
            player.setGameMode(GameType.SPECTATOR);
            player.teleportTo(server.getLevel(FacilitySchemaV2.DIMENSION),at.x,at.y,at.z,49,8);
        });
        String key=AirLiftR30Review.reviewStage+"_"+AirLiftR30Review.reviewPhase;
        if(!key.equals(photoPhase)){photoPhase=key;stablePhase=0;}
        if(++stablePhase>=30&&!photos.contains(key)&&lastView!=null&&clearView
                &&mc.gameRenderer.getMainCamera().getPosition().distanceTo(lastView.position())<.1
                &&java.util.Set.of("CRUISE","RELEASE","GROUND_APPROACH","ROLL_IN").contains(AirLiftR30Review.reviewPhase))
        {
            var folder=output();
            try
            {
                java.nio.file.Files.createDirectories(folder);
                try(var capture=net.minecraft.client.Screenshot.takeScreenshot(mc.getMainRenderTarget()))
                {capture.writeToFile(folder.resolve(key+".png"));}
                var proof=new com.google.gson.JsonObject();proof.addProperty("file",key+".png");proof.addProperty("tracked_entity",AirLiftR30Review.observedEntity);
                proof.addProperty("camera_error",mc.gameRenderer.getMainCamera().getPosition().distanceTo(lastView.position()));proof.addProperty("unobstructed_target_ray",clearView);
                proof.addProperty("target",lastView.target().toString());proof.addProperty("camera",lastView.position().toString());cameraEvidence.add(proof);photos.add(key);
                proof.addProperty("assembly_bounds",framedBounds.toString());
                proof.addProperty("visibility_samples",testedRays);proof.addProperty("unobstructed_samples",clearRays);
                proof.addProperty("maximum_screen_fraction",maximumProjection);
                proof.addProperty("framed_full_assembly",maximumProjection<=1D);
            }
            catch(java.io.IOException error){throw new IllegalStateException("Airlift photo could not be written",error);}
        }
    }
    private AirLiftR40Client(){}
}

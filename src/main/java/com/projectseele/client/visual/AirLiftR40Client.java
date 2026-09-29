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
    private static final com.google.gson.JsonArray cameraEvidence=new com.google.gson.JsonArray();
    public static CombatR31Client.View cameraView(float partial)
    {
        var mc=Minecraft.getInstance();if(!ENABLED||mc.level==null||mc.player==null)return null;
        if(!(mc.level.getEntity(AirLiftR30Review.observedEntity) instanceof com.projectseele.entity.EvaUnit01Entity eva))return null;
        var target=com.projectseele.physics.CombatBodyContacts.coreBounds(eva).getCenter();
        clearView=false;lastView=null;
        // Frame the posed cargo, whose centre changes during the saddle tilt.
        // The old fixed observer angle often photographed only sky or a wall.
        for(var offset:java.util.List.of(new net.minecraft.world.phys.Vec3(40,24,62),new net.minecraft.world.phys.Vec3(-40,24,62),new net.minecraft.world.phys.Vec3(45,28,-55),new net.minecraft.world.phys.Vec3(-45,28,-55),new net.minecraft.world.phys.Vec3(0,35,75)))
        {
            var at=target.add(offset);var hit=mc.level.clip(new net.minecraft.world.level.ClipContext(at,target,net.minecraft.world.level.ClipContext.Block.COLLIDER,net.minecraft.world.level.ClipContext.Fluid.NONE,mc.player));
            if(hit.getType()!=net.minecraft.world.phys.HitResult.Type.MISS)continue;
            clearView=true;lastView=new CombatR31Client.View(at,target);return lastView;
        }
        return null;
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
            }
            catch(java.io.IOException error){throw new IllegalStateException("Airlift photo could not be written",error);}
        }
    }
    private AirLiftR40Client(){}
}

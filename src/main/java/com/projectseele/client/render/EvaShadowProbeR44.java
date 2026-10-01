package com.projectseele.client.render;

import com.google.gson.*;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.*;
import com.projectseele.capability.EvaPilotCapability;
import com.projectseele.registry.ModEntities;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.Screenshot;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.GameType;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

/** Static first-person caster regression only; no movement or combat input. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class EvaShadowProbeR44
{
    private static final boolean ENABLED=Boolean.getBoolean("projectseele.r44ShadowReview");
    private static final boolean BEFORE=Boolean.getBoolean("projectseele.r44ShadowBefore");
    private static final int[] VARIANTS={1,0,2,3,4};
    private static final Set<String> CRITICAL=Set.of("head","torso_upper","torso_lower");
    private static final Map<String,Integer> admitted=new LinkedHashMap<>(),rejected=new LinkedHashMap<>();
    private static final JsonArray cases=new JsonArray();
    private static boolean started,done,spawnRequested;
    private static volatile boolean staged;
    private static volatile String failure="";
    private static volatile int actorId=-1;
    private static int variantIndex,age,floorCursor,exit;
    private static int readinessWait;
    private static EvaUnit01Entity serverActor;
    private static int mainFirstPerson,shadowFirstPerson;
    private static Path world;

    public static void renderMode(EvaUnit01Entity entity,boolean localPilot,boolean shadow)
    {
        if(!ENABLED||entity.getId()!=actorId||!localPilot)return;
        if(shadow)shadowFirstPerson++;else mainFirstPerson++;
    }

    public static void admission(EvaUnit01Entity entity,String bone,boolean visible)
    {
        if(!ENABLED||entity.getId()!=actorId||!CRITICAL.contains(bone)||!ShaderShadowPassR44.active())return;
        (visible?admitted:rejected).merge(bone,1,Integer::sum);
    }

    private static void spawn(Minecraft mc)
    {
        spawnRequested=true;staged=false;age=0;readinessWait=0;admitted.clear();rejected.clear();mainFirstPerson=shadowFirstPerson=0;
        mc.getSingleplayerServer().execute(()->
        {
            try
            {
                var level=mc.getSingleplayerServer().overworld();var player=mc.getSingleplayerServer().getPlayerList().getPlayers().get(0);
                if(variantIndex==0)
                {
                    var retired=new ArrayList<net.minecraft.world.entity.Entity>();
                    for(var old:level.getAllEntities())if(old.getTags().contains("seele_r44_shadow_fixture"))retired.add(old);
                    player.stopRiding();
                    for(var old:retired){for(var passenger:new ArrayList<>(old.getPassengers())){passenger.ejectPassengers();passenger.discard();}old.discard();}
                }
                player.stopRiding();if(serverActor!=null)
                {for(var passenger:new ArrayList<>(serverActor.getPassengers())){passenger.ejectPassengers();passenger.discard();}serverActor.discard();}
                int variant=VARIANTS[variantIndex];var type=variant==0?ModEntities.EVA_UNIT00.get():variant==2?ModEntities.EVA_UNIT02.get():variant>=3?ModEntities.EVA_PROTOTYPE.get():ModEntities.EVA_UNIT01.get();
                var actor=type.create(level);if(actor==null)throw new IllegalStateException("Shadow actor factory");
                if(actor instanceof EvaPrototypeEntity un)un.setUNSerial(variant-3);
                CompoundTag tag=new CompoundTag();actor.saveWithoutId(tag);tag.putBoolean("SeeleEntryPlugInserted",true);tag.putInt("SeelePowerTicks",6000);
                tag.putInt("SeeleActivationTicks",0);tag.putBoolean("SeeleNervLogisticsLocked",false);tag.putInt("R30Shutdown",0);actor.load(tag);
                actor.moveTo(16000.5,81,16000.5,90,0);actor.setOnGround(true);actor.setHealth(actor.getMaxHealth());actor.addTag("seele_r44_shadow_fixture");
                if(!level.addFreshEntity(actor))throw new IllegalStateException("Shadow actor rejected");
                player.setGameMode(GameType.CREATIVE);player.teleportTo(level,16000.5,83,15980.5,90,55);
                player.getCapability(EvaPilotCapability.DATA).ifPresent(c->c.setSynchronization(100));
                if(!actor.boardFromExternalPlug(player,100))throw new IllegalStateException("Normal shadow boarding failed");
                player.setYRot(90);player.setXRot(55);level.setDayTime(3000);level.setWeatherParameters(6000,0,false,false);
                serverActor=actor;actorId=actor.getId();staged=true;
            }
            catch(Exception error){failure=error.toString();}
        });
    }

    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!ENABLED||event.phase!=TickEvent.Phase.END)return;var mc=Minecraft.getInstance();
        if(done){if(++exit>40)mc.stop();return;}
        if(mc.player==null||mc.level==null||mc.getSingleplayerServer()==null)return;
        mc.options.pauseOnLostFocus=false;if(mc.screen!=null)mc.setScreen(null);
        try
        {
            if(!failure.isEmpty())throw new IllegalStateException(failure);
            if(!started)
            {
                world=mc.getSingleplayerServer().getWorldPath(LevelResource.ROOT).normalize();
                if(!world.getFileName().toString().equals("SEELE_R44_SHADOW_REVIEW"))throw new IllegalStateException("Shadow review world boundary");
                mc.options.setCameraType(CameraType.FIRST_PERSON);mc.options.renderDistance().set(12);mc.options.broadcastOptions();
                started=true;
            }
            if(floorCursor<193*257)
            {
                int first=floorCursor,last=Math.min(193*257,first+2400);floorCursor=last;
                mc.getSingleplayerServer().execute(()->
                {
                    var level=mc.getSingleplayerServer().overworld();
                    for(int n=first;n<last;n++){int x=15904+n%193,z=15920+n/193;var at=new BlockPos(x,80,z);
                        level.getChunkAt(at);level.setBlock(at,(Math.floorMod(x,16)==0||Math.floorMod(z,16)==0?Blocks.WHITE_CONCRETE:Blocks.LIGHT_GRAY_CONCRETE).defaultBlockState(),2);}
                });
                return;
            }
            if(actorId<0){if(!spawnRequested)spawn(mc);return;}
            if(!staged)return;
            mc.options.setCameraType(CameraType.FIRST_PERSON);mc.player.setYRot(90);mc.player.setXRot(55);
            mc.options.keyUp.setDown(false);mc.options.keyJump.setDown(false);mc.options.keyAttack.setDown(false);
            var camera=mc.gameRenderer.getMainCamera();
            boolean geometry=java.util.List.of(new BlockPos(16000,80,16000),new BlockPos(15952,80,16000),new BlockPos(15968,80,16016))
                    .stream().allMatch(q->mc.level.getChunkSource().hasChunk(q.getX()>>4,q.getZ()>>4)&&mc.levelRenderer.isChunkCompiled(q));
            if(!geometry||camera.getLookVector().y>-.15F)
            {if(++readinessWait>2400)throw new IllegalStateException("Actual first-person camera/compiled shadow floor not ready");return;}
            if(++age==180)
                Screenshot.grab(mc.gameDirectory,"r44_shadow_"+(BEFORE?"before_":"after_")+VARIANTS[variantIndex]+".png",mc.getMainRenderTarget(),c->{});
            if(age<210)return;
            if(!ShaderShadowPassR44.enabled())throw new IllegalStateException("Actual shader pack is not active");
            JsonObject result=new JsonObject();result.addProperty("variant",VARIANTS[variantIndex]);result.addProperty("first_person",mc.options.getCameraType().isFirstPerson());
            result.addProperty("shader_pack_in_use",true);
            result.addProperty("compiled_floor_ready",geometry);result.addProperty("actual_camera",camera.getPosition().toString());
            result.addProperty("actual_camera_yaw",camera.getYRot());result.addProperty("actual_camera_pitch",camera.getXRot());
            result.addProperty("server_serial",serverActor instanceof EvaPrototypeEntity un?un.getUNSerial():-1);
            result.addProperty("main_first_person_renders",mainFirstPerson);result.addProperty("shadow_first_person_renders",shadowFirstPerson);
            result.add("shadow_admitted_parts",new Gson().toJsonTree(admitted));result.add("shadow_rejected_parts",new Gson().toJsonTree(rejected));
            boolean pass=!BEFORE&&mainFirstPerson>0&&shadowFirstPerson>0&&rejected.isEmpty()&&CRITICAL.stream().allMatch(b->admitted.getOrDefault(b,0)>0);
            result.addProperty("caster_admission_pass",pass);result.addProperty("actual_pixel_review","UNVERIFIED until screenshot inspected");cases.add(result);
            if(!BEFORE&&!pass)throw new IllegalStateException("First-person full caster admission incomplete");
            if(++variantIndex<VARIANTS.length){spawn(mc);return;}
            write("");done=true;
        }
        catch(Exception error){ProjectSeele.LOGGER.error("First-person shadow review failed",error);write(error.toString());done=true;}
    }

    private static void write(String error)
    {
        try{var root=new JsonObject();root.addProperty("before_renderer",BEFORE);root.addProperty("error",error);root.add("cases",cases);
            root.addProperty("motion_quality","NOT_TESTED: standing caster only");root.addProperty("visual_passed",false);
            Files.writeString(world.resolve("r44_shadow_review.json"),new GsonBuilder().setPrettyPrinting().create().toJson(root));}
        catch(Exception problem){throw new IllegalStateException(problem);}
    }
    private EvaShadowProbeR44(){}
}

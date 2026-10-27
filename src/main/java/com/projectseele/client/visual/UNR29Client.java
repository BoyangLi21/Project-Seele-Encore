package com.projectseele.client.visual;

import com.projectseele.visual.UNR29Review;
import com.projectseele.client.Keybinds;
import com.projectseele.client.screen.UNPhoneScreen;
import net.minecraft.client.Minecraft;
import net.minecraft.client.KeyMapping;
import net.minecraft.client.gui.components.*;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.*;
import java.util.*;

@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class UNR29Client
{
    private static boolean started,oldPause;private static int end,oldDistance;private static Path folder;
    private static net.minecraft.world.entity.Entity camera;
    private static boolean missingWitnessLogged;
    public static void captureRifle(com.projectseele.entity.EvaUnit01Entity eva,net.minecraft.world.phys.Vec3 actual)
    {
        if(!UNR29Review.R30||!UNR29Review.modelInspection||UNR29Review.modelFlight||eva.getId()!=UNR29Review.modelActor)return;
        var witness=com.projectseele.client.render.EvaRifleContactRig.LAST.get(eva.getId());
        if(witness==null)
        {
            if(!missingWitnessLogged){missingWitnessLogged=true;com.projectseele.ProjectSeele.LOGGER.warn("R30 missing rifle pose: powered={} pilot={} plug={} activation={} visual={} shutdown={} fps={}",eva.isPoweredOn(),eva.getPilotEntity(),eva.isEntryPlugInserted(),eva.getActivationTicks(),eva.getVisualPose(),com.projectseele.entity.EvaShutdownR30.mode(eva),Minecraft.getInstance().getFps());}
            return;
        }
        UNR29Review.muzzleSamples++;UNR29Review.muzzleError=Math.max(UNR29Review.muzzleError,actual.distanceTo(witness.expectedMuzzle()));UNR29Review.rightGripError=Math.max(UNR29Review.rightGripError,witness.rightError());UNR29Review.leftGripError=Math.max(UNR29Review.leftGripError,witness.leftError());
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(!UNR29Review.ENABLED)return;var mc=Minecraft.getInstance();if(mc.player==null)return;
        if(event.phase==TickEvent.Phase.START)
        {
            mc.options.keyJump.setDown(UNR29Review.flightKeys.equals("up"));mc.options.keyUp.setDown(UNR29Review.flightKeys.equals("forward")||UNR29Review.modelWalk);mc.options.keyDown.setDown(UNR29Review.modelBack);mc.options.keySprint.setDown(UNR29Review.flightKeys.equals("forward"));return;
        }
        if(!started)
        {
            started=true;oldPause=mc.options.pauseOnLostFocus;mc.options.pauseOnLostFocus=false;oldDistance=mc.options.renderDistance().get();mc.options.renderDistance().set(UNR29Review.R30?10:16);mc.options.broadcastOptions();folder=mc.gameDirectory.toPath().resolve((UNR29Review.R30?"../artifacts/facility_r30/native_un_":"../artifacts/facility_r29/native_un_")+System.currentTimeMillis()).normalize();
            try{Files.createDirectories(folder);}catch(Exception e){throw new IllegalStateException(e);}UNR29Review.ready=true;
        }
        if(UNR29Review.finished)
        {if(++end>30){mc.options.keyJump.setDown(false);mc.options.keyUp.setDown(false);mc.options.keyDown.setDown(false);mc.options.keySprint.setDown(false);mc.options.pauseOnLostFocus=oldPause;mc.options.renderDistance().set(oldDistance);mc.options.broadcastOptions();mc.setScreen(null);mc.setCameraEntity(mc.player);mc.stop();}return;}
        if(UNR29Review.modelInspection){if(mc.screen!=null)mc.setScreen(null);mc.player.setYRot(0);mc.player.yRotO=0;mc.player.setXRot(0);mc.player.xRotO=0;}
        String command=UNR29Review.input;
        if(command.equals("close")){if(mc.screen!=null)mc.setScreen(null);return;}
        if(command.isEmpty()||UNR29Review.inputs.contains(command))return;
        if(command.startsWith("flight")||command.equals("land"))
        {KeyMapping.click(Keybinds.UN_FLIGHT.getKey());UNR29Review.inputs.add(command);return;}
        if(command.startsWith("deliver")&&mc.screen instanceof UNPhoneScreen screen)
        {
            if(!UNR29Review.photos.contains("un_phone")){UNR29Review.photo="un_phone";return;}
            int serial=command.endsWith("1")?1:0;
            for(var child:List.copyOf(screen.children()))if(child instanceof Button b&&b.getMessage().getString().equals(com.projectseele.entity.Unit03SourceRigR53.displayName(serial))){screen.mouseClicked(b.getX()+3,b.getY()+3,0);screen.mouseReleased(b.getX()+3,b.getY()+3,0);}
            var boxes=screen.children().stream().filter(x->x instanceof EditBox).map(x->(EditBox)x).toList();if(boxes.size()!=2)return;
            boxes.get(0).setValue(serial==0?"6400":"6260");boxes.get(1).setValue("-5820");
            for(var child:List.copyOf(screen.children()))if(child instanceof Button b&&b.getMessage().getString().equals("投放到指定 X / Z"))
            {screen.mouseClicked(b.getX()+3,b.getY()+3,0);screen.mouseReleased(b.getX()+3,b.getY()+3,0);UNR29Review.inputs.add(command);break;}
        }
    }
    @SubscribeEvent public static void render(TickEvent.RenderTickEvent event)
    {
        if(!UNR29Review.ENABLED||!started)return;
        var mc=Minecraft.getInstance();
        if(UNR29Review.R30&&event.phase==TickEvent.Phase.START&&mc.level!=null&&mc.player!=null)
        {
            if(UNR29Review.modelInspection&&mc.level.getEntity(UNR29Review.modelActor) instanceof com.projectseele.entity.EvaPrototypeEntity eva)
            {
                mc.options.setCameraType(net.minecraft.client.CameraType.FIRST_PERSON);
                boolean pilotView=UNR29Review.modelFlight?UNR29Review.modelTick<45||UNR29Review.modelTick>52
                        :UNR29Review.modelTick>305&&UNR29Review.modelTick<325||UNR29Review.modelTick>=475;
                if(pilotView)mc.setCameraEntity(mc.player);
                else
                {
                    if(camera==null){camera=net.minecraft.world.entity.EntityType.ARMOR_STAND.create(mc.level);camera.setInvisible(true);}
                    var centre=eva.getPosition(event.renderTickTime);var position=centre.add(UNR29Review.modelFlight?48:55,33,UNR29Review.modelFlight?-85:85);var delta=centre.add(0,30,0).subtract(position);
                    camera.setPos(position.x,position.y-camera.getEyeHeight(),position.z);camera.xo=camera.xOld=camera.getX();camera.yo=camera.yOld=camera.getY();camera.zo=camera.zOld=camera.getZ();camera.setYRot((float)Math.toDegrees(Math.atan2(-delta.x,delta.z)));camera.yRotO=camera.getYRot();camera.setYHeadRot(camera.getYRot());if(camera instanceof net.minecraft.world.entity.LivingEntity living)living.yHeadRotO=living.yHeadRot;camera.setXRot((float)-Math.toDegrees(Math.atan2(delta.y,delta.horizontalDistance())));camera.xRotO=camera.getXRot();mc.setCameraEntity(camera);
                }
            }
            else mc.setCameraEntity(mc.player);
        }
        if(event.phase==TickEvent.Phase.START&&mc.player!=null&&UNR29Review.lookTarget!=null)
        {
            var d=UNR29Review.lookTarget.subtract(mc.player.getEyePosition());float yaw=(float)Math.toDegrees(Math.atan2(-d.x,d.z)),pitch=(float)-Math.toDegrees(Math.atan2(d.y,d.horizontalDistance()));mc.player.setYRot(yaw);mc.player.yRotO=yaw;mc.player.setXRot(pitch);mc.player.xRotO=pitch;
        }
        if(event.phase!=TickEvent.Phase.END)return;
        if(UNR29Review.R30&&UNR29Review.modelInspection&&!UNR29Review.modelFlight&&mc.level!=null&&mc.level.getEntity(UNR29Review.modelActor) instanceof com.projectseele.entity.EvaPrototypeEntity eva&&eva.getWeapon()==com.projectseele.entity.EvaUnit01Entity.WEAPON_RIFLE)
        {
            var witness=com.projectseele.client.render.EvaRifleContactRig.LAST.get(eva.getId());
            if(witness!=null)
            {
                var muzzle=com.projectseele.client.render.EvaUnit01Renderer.rifleMuzzleOrFallback(eva.getId(),new net.minecraft.world.phys.Vec3(Double.NaN,Double.NaN,Double.NaN));
                if(Double.isFinite(muzzle.x)){UNR29Review.muzzleSamples++;UNR29Review.muzzleError=Math.max(UNR29Review.muzzleError,muzzle.distanceTo(witness.expectedMuzzle()));UNR29Review.rightGripError=Math.max(UNR29Review.rightGripError,witness.rightError());UNR29Review.leftGripError=Math.max(UNR29Review.leftGripError,witness.leftError());}
            }
        }
        String name=UNR29Review.photo;if(name.isEmpty()||UNR29Review.photos.contains(name))return;
        try(var frame=net.minecraft.client.Screenshot.takeScreenshot(Minecraft.getInstance().getMainRenderTarget())){frame.writeToFile(folder.resolve(name+".png"));UNR29Review.photos.add(name);}catch(Exception e){throw new IllegalStateException(e);}
    }
    private UNR29Client() {}
}

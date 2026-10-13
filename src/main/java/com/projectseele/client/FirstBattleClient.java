package com.projectseele.client;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.FirstBattleClip;
import com.projectseele.network.SeeleNetwork;
import com.projectseele.network.ServerboundEvaControlPacket;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Camera;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.lwjgl.glfw.GLFW;
import java.util.UUID;

/** The participating pilot receives directed shots; observers and the optical feed keep their own views. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,value=Dist.CLIENT)
public final class FirstBattleClient
{
    private static final boolean REVIEW_CAMERA_R52="r10-firstbattle".equals(System.getProperty("projectseele.regionalBuild",""))&&Boolean.getBoolean("projectseele.firstBattleAuthoredCameraR52");
    private static final boolean REVIEW_CLOSE_R52=REVIEW_CAMERA_R52&&Boolean.getBoolean("projectseele.firstBattleCloseViewsR52");
    private static CameraType savedCamera;
    private static UUID savedActor;
    private static Vec3 entryPosition,entryTarget,lastPosition,lastTarget,returnPosition,returnTarget;
    private static boolean returning;
    private static EvaUnit01Entity actor()
    {
        var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null)return null;
        var eva=EvaPilotResolver.controlTarget(mc.player);return eva!=null&&eva.isFirstBattleActive()&&FirstBattleClip.ready()?eva:null;
    }
    public static boolean active(){return actor()!=null;}
    public static void releaseCamera(){restore();}
    @SubscribeEvent public static void renderClock(TickEvent.RenderTickEvent event)
    {
        if(event.phase==TickEvent.Phase.START)com.projectseele.entity.FirstBattleSignals.beginClientFrame(System.nanoTime(),Minecraft.getInstance().isPaused());
    }
    private static void capture(EvaUnit01Entity eva,Camera camera)
    {
        var mc=Minecraft.getInstance();
        if(savedCamera==null||!eva.getUUID().equals(savedActor))
        {
            restore();savedCamera=mc.options.getCameraType();savedActor=eva.getUUID();entryPosition=camera.getPosition();entryTarget=entryPosition.add(new Vec3(camera.getLookVector()).scale(40));returning=false;
        }
    }
    private static void restore()
    {
        if(savedCamera!=null)Minecraft.getInstance().options.setCameraType(savedCamera);
        savedCamera=null;savedActor=null;entryPosition=entryTarget=lastPosition=lastTarget=returnPosition=returnTarget=null;returning=false;
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var eva=actor();if(eva==null){restore();return;}
        var mc=Minecraft.getInstance();capture(eva,mc.gameRenderer.getMainCamera());
        float time=eva.firstBattleSignals().time(eva,1);
        if(time<FirstBattleClip.RETURN_TICK/20F)mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        else mc.options.setCameraType(savedCamera);
    }
    public static FirstBattleClip.CameraPose camera(Camera camera,float partial)
    {
        var eva=actor();var mc=Minecraft.getInstance();
        if(eva==null&&REVIEW_CLOSE_R52&&com.projectseele.visual.FirstBattleR10Review.capturePostStopR52&&mc.level!=null
                &&mc.level.getEntity(com.projectseele.visual.FirstBattleR10Review.heroId) instanceof EvaUnit01Entity stopped)
        {mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);return reviewShotR52(stopped,23,true);}
        if(eva==null)return null;var signals=eva.firstBattleSignals();var spec=signals.spec(eva);float time=signals.time(eva,partial);
        if(EvaCommandFeedClient.isOpticalRenderPass())
            return new FirstBattleClip.CameraPose(FirstBattleClip.point(spec,true,"eye_blocks",time),FirstBattleClip.point(spec,true,"look_blocks",time),70);
        capture(eva,camera);var shot=FirstBattleClip.camera(spec,time);Vec3 p=shot.position(),target=shot.target();
        // The authored shot covers the actors and the single blast. Replacing
        // it with a fixed skyline hid the actual recovery and return pose.
        if(time<1.2F)
        {
            float mix=FirstBattleClip.smooth(time/1.2F);p=entryPosition.lerp(p,mix);target=entryTarget.lerp(target,mix);
            mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        }
        if(time>=FirstBattleClip.RETURN_TICK/20F)
        {
            if(!returning){returnPosition=lastPosition==null?p:lastPosition;returnTarget=lastTarget==null?target:lastTarget;returning=true;}
            Vec3 normal=savedCamera.isFirstPerson()?FirstBattleClip.point(spec,true,"eye_blocks",time):camera.getPosition();
            Vec3 look=normal.add(new Vec3(camera.getLookVector()).scale(40));float mix=FirstBattleClip.smooth((time-21.6F)/1.4F);
            p=returnPosition.lerp(normal,mix);target=returnTarget.lerp(look,mix);
        }
        if(REVIEW_CLOSE_R52)
        {
            var close=reviewShotR52(eva,time,false);
            if(close!=null){p=close.position();target=close.target();}
        }
        p=clearCamera(target,p);lastPosition=p;lastTarget=target;return new FirstBattleClip.CameraPose(p,target,shot.fov());
    }
    public static String reviewViewR52(float time,boolean stopped)
    {
        if(!REVIEW_CLOSE_R52)return REVIEW_CAMERA_R52?"authored-wide":"production-directed";
        if(stopped)return "actual-stop-eye-close";
        if(time>=2.25F&&time<=2.8F)return "ordinary-eye-close";
        if(time>=8.15F&&time<=8.65F)return "core-side";
        if(time>=9F&&time<=9.45F)return "berserk-eye-jaw-close";
        if(time>=13.55F&&time<=14.3F)return "rise-side";
        if(time>=16F&&time<=16.7F)return "step-side";
        if(time>=17.65F&&time<=18.3F)return "embrace-side";
        if(time>=21.9F&&time<=22.35F)return "post-angel-death-eye-close";
        return "authored-wide";
    }
    private static FirstBattleClip.CameraPose reviewShotR52(EvaUnit01Entity eva,float time,boolean stopped)
    {
        String view=reviewViewR52(time,stopped);if(view.equals("authored-wide")||view.equals("production-directed"))return null;
        var spec=eva.firstBattleSignals().spec(eva);
        if(view.contains("eye")||view.contains("jaw"))
        {
            Vec3 eye=FirstBattleClip.point(spec,true,"eye_blocks",time),look=FirstBattleClip.point(spec,true,"look_blocks",time);
            Vec3 forward=look.subtract(eye).normalize(),side=new Vec3(forward.z,0,-forward.x).normalize();
            return new FirstBattleClip.CameraPose(eye.add(forward.scale(13)).add(side.scale(18)).add(0,4,0),eye.add(0,-1.5,0),45);
        }
        Vec3 p,target;
        // Exact visible-skin bounds over each finite window keep the furthest
        // point below95 blocks even with the R10 shader's far uniform128.
        if(view.equals("core-side")){p=new Vec3(-53.844,27.017,95.945);target=new Vec3(-11.409,7.2,61.831);}
        else if(view.equals("rise-side")){p=new Vec3(7.105,33.897,110.558);target=new Vec3(-7.247,29.045,56.996);}
        else if(view.equals("step-side")){p=new Vec3(-3.347,49.557,113.858);target=new Vec3(-22.441,29.237,61.396);}
        else {p=new Vec3(37.963,29.197,71.420);target=new Vec3(-26.303,29.197,60.088);}
        return new FirstBattleClip.CameraPose(FirstBattleClip.world(spec,p),FirstBattleClip.world(spec,target),80);
    }
    private static Vec3 clearCamera(Vec3 target,Vec3 desired)
    {
        var mc=Minecraft.getInstance();if(mc.level==null||mc.player==null)return desired;
        var hit=mc.level.clip(new ClipContext(target,desired,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,mc.player));
        if(hit.getType()==HitResult.Type.MISS)return desired;
        Vec3 direction=desired.subtract(target).normalize();Vec3 result=hit.getLocation().subtract(direction.scale(1));
        if(result.distanceTo(target)<8)
        {
            Vec3 raised=desired.add(0,35,0);var alternative=mc.level.clip(new ClipContext(target,raised,ClipContext.Block.COLLIDER,ClipContext.Fluid.NONE,mc.player));
            if(alternative.getType()==HitResult.Type.MISS)return raised;
        }
        return result;
    }
    public static boolean insideOptics(EvaUnit01Entity eva)
    {
        if(actor()!=eva)return false;if(EvaCommandFeedClient.isOpticalRenderPass())return true;
        Vec3 eye=FirstBattleClip.point(eva.firstBattleSignals().spec(eva),true,"eye_blocks",eva.firstBattleSignals().time(eva,1));
        return lastPosition!=null&&lastPosition.distanceToSqr(eye)<9;
    }
    @SubscribeEvent public static void fov(ViewportEvent.ComputeFov event)
    {
        var eva=actor();if(eva==null){if(REVIEW_CLOSE_R52&&com.projectseele.visual.FirstBattleR10Review.capturePostStopR52)event.setFOV(45);return;}float time=eva.firstBattleSignals().time(eva,1);
        if(EvaCommandFeedClient.isOpticalRenderPass()){event.setFOV(70);return;}
        if(REVIEW_CLOSE_R52){var close=reviewShotR52(eva,time,false);if(close!=null){event.setFOV(close.fov());return;}}
        double mix=FirstBattleClip.smooth(time/1.2F)*(1-FirstBattleClip.smooth((time-21.6F)/1.4F));
        double directed=FirstBattleClip.camera(eva.firstBattleSignals().spec(eva),time).fov();event.setFOV(event.getFOV()*(1-mix)+directed*mix);
    }
    @SubscribeEvent public static void key(InputEvent.Key event)
    {
        if(event.getKey()==GLFW.GLFW_KEY_ENTER&&event.getAction()==GLFW.GLFW_PRESS&&Minecraft.getInstance().screen==null&&active())
            SeeleNetwork.CHANNEL.sendToServer(new ServerboundEvaControlPacket(ServerboundEvaControlPacket.ACTION_SKIP_FIRST_BATTLE));
    }
    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut event){restore();}
    @SubscribeEvent(priority=net.minecraftforge.eventbus.api.EventPriority.HIGHEST)
    public static void directedHud(net.minecraftforge.client.event.RenderGuiOverlayEvent.Pre event)
    {
        // The pilot's directed view keeps the scene, accessibility subtitles
        // and optical-feed capture. Normal HUDs return immediately afterwards;
        // no user minimap settings or chat history are changed.
        if(!active()||Minecraft.getInstance().screen!=null)return;
        String id=event.getOverlay().id().toString();
        if(!java.util.Set.of("projectseele:first_battle","projectseele:nuclear_flash",
                "projectseele:eva_command_feed_capture","minecraft:subtitles").contains(id))event.setCanceled(true);
    }
    public static final IGuiOverlay OVERLAY=(gui,g,partial,width,height)->
    {
        var eva=actor();if(eva==null)return;float t=eva.firstBattleSignals().time(eva,partial);float fade=FirstBattleClip.smooth(t/.7F)*(1-FirstBattleClip.smooth((t-21.6F)/1.4F));int bars=Math.round(height*.09F*fade),alpha=Math.round(fade*235);
        g.fill(0,0,width,bars,alpha<<24);g.fill(0,height-bars,width,height,alpha<<24);
        String title=t<5?"制御不能 / AT フィールド侵蝕":t<FirstBattleClip.landingTick()/20F?"自律作動 — THE BEAST":t<18.6?"目標コア制圧":t<21.6?"目標沈黙":eva.isPowerDepleted()?"初号機・活動停止":"操縦系復帰";
        if(bars>12){g.drawString(gui.getFont(),title,14,Math.max(4,bars-15),0xFFFF8250,false);g.drawString(gui.getFont(),"Enter · 跳过演出",14,height-bars+6,0xFFB5BABE,false);}
    };
    private FirstBattleClient() {}
}

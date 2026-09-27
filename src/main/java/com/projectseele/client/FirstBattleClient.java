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
        var eva=actor();if(eva==null)return null;var mc=Minecraft.getInstance();var signals=eva.firstBattleSignals();var spec=signals.spec(eva);float time=signals.time(eva,partial);
        if(EvaCommandFeedClient.isOpticalRenderPass())
            return new FirstBattleClip.CameraPose(FirstBattleClip.point(spec,true,"eye_blocks",time),FirstBattleClip.point(spec,true,"look_blocks",time),70);
        capture(eva,camera);var shot=FirstBattleClip.camera(spec,time);Vec3 p=shot.position(),target=shot.target();
        // Cut on the detonation flash to a wide skyline view. The return
        // below still hands control back through the original camera blend.
        if(time>=FirstBattleClip.DEATH_TICK/20F&&time<FirstBattleClip.RETURN_TICK/20F)
        {p=FirstBattleClip.world(spec,new Vec3(0,90,-205));target=FirstBattleClip.world(spec,new Vec3(0,140,25));}
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
        p=clearCamera(target,p);lastPosition=p;lastTarget=target;return new FirstBattleClip.CameraPose(p,target,shot.fov());
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
        var eva=actor();if(eva==null)return;float time=eva.firstBattleSignals().time(eva,1);
        if(EvaCommandFeedClient.isOpticalRenderPass()){event.setFOV(70);return;}
        double mix=FirstBattleClip.smooth(time/1.2F)*(1-FirstBattleClip.smooth((time-21.6F)/1.4F));double directed=70+10*FirstBattleClip.smooth((time-18.3F)/.3F);event.setFOV(event.getFOV()*(1-mix)+directed*mix);
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

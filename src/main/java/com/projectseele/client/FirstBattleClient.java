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
import net.minecraft.util.Mth;
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
    /** Review only: keep the review's fixed camera instead of the authored shots. */
    private static final boolean FIXED_REVIEW_CAMERA_R58=Boolean.getBoolean("projectseele.finaleFixedCameraR58");
    private static CameraType savedCamera;
    private static UUID savedActor;
    private static Vec3 entryPosition,entryTarget,lastPosition,lastTarget,returnPosition,returnTarget;
    private static boolean returning;
    /**
     * How far the blends at both ends keep from a body's upright axis. Sachiel's shoulders reach 22 blocks from its
     * axis and Unit-01's spread arms 20; the authored shots never come nearer than this.
     */
    private static final double ANGEL_CLEAR=24,EVA_CLEAR=20;
    /** A camera that starts this near Sachiel's axis starts inside its body. No path out of a body is clean: the first shot is cut to. */
    private static final double ANGEL_CORE=12;
    /** How far the pilot's own camera stood from each axis when the battle began, no more than the clearance. */
    private static double entryAngel=Double.NaN,entryEva=Double.NaN;
    private static boolean cutIn;
    private static EvaUnit01Entity actor()
    {
        var mc=Minecraft.getInstance();if(mc.player==null||mc.level==null)return null;
        var eva=EvaPilotResolver.controlTarget(mc.player);return eva!=null&&eva.isFirstBattleActive()&&FirstBattleClip.ready()?eva:null;
    }
    public static boolean active(){return actor()!=null;}
    @SubscribeEvent public static void renderClock(TickEvent.RenderTickEvent event)
    {
        // The frame's own start, not this event's: see AircraftRenderClockR21.stampFrame.
        if(event.phase==TickEvent.Phase.START)com.projectseele.entity.FirstBattleSignals.beginClientFrame(AircraftRenderClockR21.frameNanos(),Minecraft.getInstance().isPaused());
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
        entryAngel=entryEva=Double.NaN;cutIn=false;
    }
    /**
     * How far the camera has gone back to the pilot's own view, 0 to 1, from 21.6 s. A first-person view is cut to:
     * the way into it runs through Unit-01's head, which is only hidden from within three blocks of the eye.
     */
    private static double returned(float time)
    {
        return time<FirstBattleClip.RETURN_TICK/20F?0:savedCamera!=null&&savedCamera.isFirstPerson()?1:FirstBattleClip.smooth((time-21.6F)/1.4F);
    }
    /** The point of a body's axis nearest to a camera: the upright line from 10 to 50 blocks above its root (both bodies stand about 60 tall). */
    private static Vec3 onAxis(Vec3 root,Vec3 camera){return new Vec3(root.x,Mth.clamp(camera.y,root.y+10,root.y+50),root.z);}
    /** The camera moved straight away from a body's axis until it is the given distance from it; unchanged when it already is. */
    private static Vec3 clearOf(Vec3 root,Vec3 camera,double radius,Vec3 toward)
    {
        Vec3 axis=onAxis(root,camera),out=camera.subtract(axis);double distance=out.length();if(distance>=radius)return camera;
        if(distance<1e-3){out=toward.subtract(axis).multiply(1,0,1);distance=out.length();if(distance<1e-3){out=new Vec3(1,0,0);distance=1;}}
        return axis.add(out.scale(radius/distance));
    }
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;var eva=actor();if(eva==null){restore();return;}
        var mc=Minecraft.getInstance();capture(eva,mc.gameRenderer.getMainCamera());
        float time=eva.firstBattleSignals().time(eva,1);
        if(FIXED_REVIEW_CAMERA_R58)return;
        if(time<FirstBattleClip.RETURN_TICK/20F)mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        else mc.options.setCameraType(savedCamera);
    }
    public static FirstBattleClip.CameraPose camera(Camera camera,float partial)
    {
        if(FIXED_REVIEW_CAMERA_R58)return null;
        var eva=actor();var mc=Minecraft.getInstance();
        if(eva==null)return null;var signals=eva.firstBattleSignals();var spec=signals.spec(eva);float time=signals.time(eva,partial);
        if(EvaCommandFeedClient.isOpticalRenderPass())
            return new FirstBattleClip.CameraPose(FirstBattleClip.point(spec,true,"eye_blocks",time),FirstBattleClip.point(spec,true,"look_blocks",time),70);
        capture(eva,camera);var shot=FirstBattleClip.camera(spec,time);Vec3 p=shot.position(),target=shot.target();
        // The authored shot covers the actors and the single blast. Replacing
        // it with a fixed skyline hid the actual recovery and return pose.
        Vec3 body=FirstBattleClip.point(spec,true,"root_blocks",time);
        if(time<1.2F)
        {
            // Sachiel is carried from where it really stood to where the clip has it over this same time.
            Vec3 angel=FirstBattleClip.point(spec,false,"root_blocks",time);
            if(Double.isNaN(entryAngel))
            {
                entryAngel=Math.min(ANGEL_CLEAR,entryPosition.distanceTo(onAxis(angel,entryPosition)));
                entryEva=Math.min(EVA_CLEAR,entryPosition.distanceTo(onAxis(body,entryPosition)));
                // Out of a first-person view the camera would also leave through Unit-01's own head and shoulders.
                cutIn=savedCamera.isFirstPerson()||entryAngel<ANGEL_CORE;
            }
            if(!cutIn)
            {
                float mix=FirstBattleClip.smooth(time/1.2F);p=entryPosition.lerp(p,mix);target=entryTarget.lerp(target,mix);
                // The straight line from the pilot's camera to the first shot can run through either body. Each
                // body's clearance opens from what the camera started with (a first-person camera starts inside
                // Unit-01's head) to its full size over the first half, so the camera leaves a body outward and
                // goes round the other one. A line that touches neither stays as it is.
                double open=FirstBattleClip.smooth(mix/.5F);
                for(int pass=0;pass<3;pass++)
                {
                    p=clearOf(angel,p,Mth.lerp(open,entryAngel,ANGEL_CLEAR),entryPosition);
                    p=clearOf(body,p,Mth.lerp(open,entryEva,EVA_CLEAR),entryPosition);
                }
            }
            mc.options.setCameraType(CameraType.THIRD_PERSON_BACK);
        }
        if(time>=FirstBattleClip.RETURN_TICK/20F)
        {
            if(!returning){returnPosition=lastPosition==null?p:lastPosition;returnTarget=lastTarget==null?target:lastTarget;returning=true;}
            Vec3 normal=savedCamera.isFirstPerson()?FirstBattleClip.point(spec,true,"eye_blocks",time):camera.getPosition();
            Vec3 look=normal.add(new Vec3(camera.getLookVector()).scale(40));float mix=(float)returned(time);
            p=returnPosition.lerp(normal,mix);target=returnTarget.lerp(look,mix);
            // Back to the pilot's own view round Unit-01, not through it (Sachiel is no longer drawn). The clearance
            // closes over the second half to what the pilot's camera itself keeps: a first-person eye is inside the head.
            double end=Math.min(EVA_CLEAR,normal.distanceTo(onAxis(body,normal)));
            p=clearOf(body,p,Mth.lerp(FirstBattleClip.smooth((mix-.5F)/.5F),EVA_CLEAR,end),returnPosition);
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
        double mix=(cutIn?1:FirstBattleClip.smooth(time/1.2F))*(1-returned(time));
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

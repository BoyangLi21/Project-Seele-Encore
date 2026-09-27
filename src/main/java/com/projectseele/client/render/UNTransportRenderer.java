package com.projectseele.client.render;

import com.projectseele.entity.UNTransportEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.EvaPrototypeEntity;
import com.projectseele.entity.EvaAirTransportR31;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import net.minecraft.client.renderer.*;
import net.minecraft.client.renderer.entity.*;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import com.google.gson.JsonParser;
import java.util.*;
import org.joml.Vector3f;
import org.joml.Matrix4f;
import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;

public final class UNTransportRenderer extends EntityRenderer<UNTransportEntity>
{
    private static final ResourceLocation PAINT=new ResourceLocation("minecraft","textures/block/white_concrete.png");
    private static final Map<String,float[]> PARTS=new HashMap<>();
    private static final int[] TRIANGLE_AS_QUAD={0,1,2,2};
    private static int draw(String name,PoseStack poses,MultiBufferSource buffers,int light)
    {return draw(name,poses,buffers,light,0);}
    private static float hoistY(float y,float extension){return y-extension*net.minecraft.util.Mth.clamp((-11-y)/21,0,1);}
    private static int draw(String name,PoseStack poses,MultiBufferSource buffers,int light,float extension)
    {
        if(PARTS.isEmpty())
        {
            try(var reader=net.minecraft.client.Minecraft.getInstance().getResourceManager().getResource(new ResourceLocation("projectseele","mesh/tv_facilities_r16.json")).orElseThrow().openAsReader())
            {
                for(var row:JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("parts").entrySet())
                    if(row.getKey().startsWith("un_")){var a=row.getValue().getAsJsonArray();float[] values=new float[a.size()];for(int i=0;i<a.size();i++)values[i]=a.get(i).getAsFloat();PARTS.put(row.getKey(),values);}
            }
            catch(Exception error){throw new IllegalStateException("UN aircraft mesh could not be loaded",error);}
            try(var reader=net.minecraft.client.Minecraft.getInstance().getResourceManager().getResource(new ResourceLocation("projectseele","mesh/air_cradle_r31.json")).orElseThrow().openAsReader())
            {
                for(var row:JsonParser.parseReader(reader).getAsJsonObject().getAsJsonObject("parts").entrySet())
                {var a=row.getValue().getAsJsonArray();float[] values=new float[a.size()];for(int i=0;i<a.size();i++)values[i]=a.get(i).getAsFloat();PARTS.put(row.getKey(),values);}
            }
            catch(Exception error){throw new IllegalStateException("R31 rotating air cradle mesh could not be loaded",error);}
        }
        var a=PARTS.get(name);if(a==null)return 0;var out=buffers.getBuffer(RenderType.entityCutoutNoCull(PAINT));var m=poses.last().pose();var normal=poses.last().normal();int submitted=0;
        for(int i=0;i<a.length;i+=18)
        {
            float ux=a[i+6]-a[i],uy=hoistY(a[i+7],extension)-hoistY(a[i+1],extension),uz=a[i+8]-a[i+2],vx=a[i+12]-a[i],vy=hoistY(a[i+13],extension)-hoistY(a[i+1],extension),vz=a[i+14]-a[i+2];
            float nx=uy*vz-uz*vy,ny=uz*vx-ux*vz,nz=ux*vy-uy*vx,length=(float)Math.sqrt(nx*nx+ny*ny+nz*nz);if(length<1e-6)continue;nx/=length;ny/=length;nz/=length;
            for(int j:TRIANGLE_AS_QUAD)
            {
                int k=i+j*6;out.vertex(m,a[k],hoistY(a[k+1],extension),a[k+2]).color((int)a[k+3],(int)a[k+4],(int)a[k+5],255).uv(j==0?0:1,j<2?0:1).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normal,nx,ny,nz).endVertex();
            }
            submitted++;
        }
        return submitted;
    }
    public UNTransportRenderer(EntityRendererProvider.Context context){super(context);shadowRadius=0;}
    private static Vector3f latch(float x,float y,float pitch,float width,float offset)
    {
        var p=new Vector3f(x*width,y-EvaAirTransportR31.HIP_HEIGHT,8);
        p.rotateX((float)Math.toRadians(-pitch));
        p.add(0,EvaAirTransportR31.HIP_HEIGHT+EvaAirTransportR31.lift(pitch)-offset,0);
        return p.rotateY((float)Math.PI);
    }
    private static boolean rod(PoseStack poses,MultiBufferSource buffers,int light,Vector3f a,Vector3f b,float radius,int colour)
    {
        var axis=new Vector3f(b).sub(a);if(axis.lengthSquared()<1e-6)return false;axis.normalize();
        var x=new Vector3f(axis).cross(Math.abs(axis.y)<.95?new Vector3f(0,1,0):new Vector3f(1,0,0)).normalize();
        var y=new Vector3f(axis).cross(x).normalize();
        var out=buffers.getBuffer(RenderType.entityCutoutNoCull(PAINT));var matrix=poses.last().pose();var normal=poses.last().normal();
        for(int i=0;i<12;i++)
        {
            float u=(float)(i*Math.PI/6),v=(float)((i+1)*Math.PI/6);
            var p=new Vector3f(x).mul((float)Math.cos(u)).fma((float)Math.sin(u),y);
            var q=new Vector3f(x).mul((float)Math.cos(v)).fma((float)Math.sin(v),y);
            Vector3f[] vertices={new Vector3f(a).fma(radius,p),new Vector3f(a).fma(radius,q),new Vector3f(b).fma(radius,q),new Vector3f(b).fma(radius,p)};
            var n=new Vector3f(p).add(q).normalize();
            for(int k=0;k<4;k++){var point=vertices[k];out.vertex(matrix,point.x,point.y,point.z).color(colour,Math.min(255,colour+10),Math.min(255,colour+14),255).uv(k==0||k==3?0:1,k<2?0:1).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(normal,n.x,n.y,n.z).endVertex();}
        }
        return true;
    }
    private static void cradle(UNTransportEntity plane,float partial,PoseStack poses,MultiBufferSource buffers,int light,Matrix4f submittedEntityFrame,Vec3 dispatcher)
    {
        if(plane.rig(partial)<.001F)return;
        var cargo=plane.level().getEntity(plane.cargoEntityId());
        EvaUnit01Entity eva=cargo instanceof EvaUnit01Entity e?e:null;
        if(plane.carrying()&&eva==null)return;
        if(eva!=null&&EvaAirTransportR31.active(eva)&&EvaAirTransportR31.adaptive(eva))
        {adaptiveCradle(plane,eva,partial,poses,buffers,light,submittedEntityFrame,dispatcher);return;}
        boolean attached=plane.carrying()&&eva!=null&&EvaAirTransportR31.active(eva);
        float pitch=attached?EvaAirTransportR31.pitch(eva,partial):(1-plane.rig(partial))*90;
        float width=eva instanceof EvaPrototypeEntity un?(un.getUNSerial()==1?1.05F:.95F):.86F;
        float offset=plane.hoistDistance();
        int rods=0;
        // The two telescopic pairs carry the rotating saddle. They end at real
        // trunnions on its spine, not at imaginary points above the payload.
        for(int side:new int[]{-1,1})for(int end:new int[]{-1,1})
        {
            var a=new Vector3f(-side*14,-11,-end*10);
            var b=latch(side*14,end<0?18:50,pitch,width,offset);
            var mid=new Vector3f(a).lerp(b,.58F);
            if(rod(poses,buffers,light,a,mid,.48F,70))rods++;
            if(rod(poses,buffers,light,mid,b,.27F,170))rods++;
        }
        poses.pushPose();
        poses.mulPose(Axis.YP.rotationDegrees(180));
        poses.translate(0,-offset+EvaAirTransportR31.lift(pitch)+EvaAirTransportR31.HIP_HEIGHT,0);
        poses.mulPose(Axis.XP.rotationDegrees(-pitch));
        poses.translate(0,-EvaAirTransportR31.HIP_HEIGHT,0);
        poses.scale(width,1,1);
        int triangles=draw("air_cradle_frame_r31",poses,buffers,light);
        for(int side:new int[]{-1,1})
        {
            poses.pushPose();poses.translate(side*4*plane.jaws(partial),0,0);
            triangles+=draw("air_cradle_jaw_r31_"+side,poses,buffers,light);poses.popPose();
        }
        if(com.projectseele.visual.MechanicsR31Review.ENABLED)
        {
            var actual=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(poses.last().pose(),submittedEntityFrame);
            actual.m30(actual.m30()+(float)dispatcher.x).m31(actual.m31()+(float)dispatcher.y).m32(actual.m32()+(float)dispatcher.z);
            com.projectseele.client.visual.MechanicsR31Client.captureCradle(plane,actual,partial,triangles,rods);
        }
        poses.popPose();
    }
    private static void adaptiveCradle(UNTransportEntity plane,EvaUnit01Entity eva,float partial,PoseStack poses,MultiBufferSource buffers,int light,Matrix4f submittedEntityFrame,Vec3 dispatcher)
    {
        Vec3 aircraft=plane.carrying()?EvaAirTransportR31.framePosition(eva,partial).add(0,plane.hoistDistance(),0):plane.renderFlightPosition(partial);
        float yaw=plane.carrying()?EvaAirTransportR31.frameYaw(eva,partial):plane.renderFlightYaw(partial);
        var origin=EvaAirTransportR31.origin(eva);
        // Dorsal supports follow the frozen torso/leg frames, including a fallen or kneeling pickup.
        var anchors=new ArrayList<Vector3f>();
        for(String bone:new String[]{"arm_l","arm_r","leg_l","leg_r","shin_l","shin_r"})
        {
            var matrix=origin.matrix(bone);
            var point=matrix.transformPosition(new Vector3f(origin.rig.get(bone).pivot()).add(0,0,2.5F/com.projectseele.entity.EvaScale.RENDER_SCALE)).mul(com.projectseele.entity.EvaScale.RENDER_SCALE);
            Vec3 world=EvaAirTransportR31.point(eva,new Vec3(point.x,point.y,point.z),partial).subtract(aircraft);
            var end=new Vector3f((float)world.x,(float)world.y,(float)world.z).rotateY(yaw*Mth.DEG_TO_RAD);
            anchors.add(end);
        }
        int segments=0;
        for(int pair=0;pair<3;pair++)
        {
            Vector3f left=anchors.get(pair*2),right=anchors.get(pair*2+1);
            var spread=new Vector3f(right).sub(left).normalize().mul(4*EvaAirTransportR31.jawOpening(eva,partial));
            left.sub(spread);right.add(spread);
            float extension=plane.rig(partial);
            left.lerp(new Vector3f(14,-13,(pair-1)*11),1-extension);
            right.lerp(new Vector3f(-14,-13,(pair-1)*11),1-extension);
            if(rod(poses,buffers,light,left,right,.48F,66))segments++;
            for(int side=0;side<2;side++)
            {
                var end=anchors.get(pair*2+side);var top=new Vector3f(side==0?14:-14,-11,(pair-1)*11);
                var mid=new Vector3f(top).lerp(end,.62F);
                if(rod(poses,buffers,light,top,mid,.48F,65))segments++;
                if(rod(poses,buffers,light,mid,end,.24F,182))segments++;
                var collar=new Vector3f(mid).lerp(end,.07F);
                if(rod(poses,buffers,light,mid,collar,.60F,48))segments++;
                var tangent=new Vector3f(right).sub(left).normalize().mul(1.6F);
                if(rod(poses,buffers,light,new Vector3f(end).sub(tangent),new Vector3f(end).add(tangent),.85F,86))segments++;
            }
            if(pair>0)for(int side=0;side<2;side++)if(rod(poses,buffers,light,anchors.get((pair-1)*2+side),anchors.get(pair*2+side),.35F,58))segments++;
        }
        if(com.projectseele.visual.MechanicsR31Review.ENABLED)
        {
            var centre=new Vector3f(anchors.get(2)).add(anchors.get(3)).mul(.5F);
            var submitted=new Matrix4f(poses.last().pose()).translate(centre.x,centre.y-EvaAirTransportR31.HIP_HEIGHT,centre.z);
            var actual=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(submitted,submittedEntityFrame);
            actual.m30(actual.m30()+(float)dispatcher.x).m31(actual.m31()+(float)dispatcher.y).m32(actual.m32()+(float)dispatcher.z);
            com.projectseele.client.visual.MechanicsR31Client.captureCradle(plane,actual,partial,segments*24,segments);
        }
    }
    @Override public ResourceLocation getTextureLocation(UNTransportEntity entity){return entity.isNerv()?com.projectseele.client.TreeOfLifeWallClient.nervLogoTexture(net.minecraft.client.Minecraft.getInstance()):com.projectseele.client.UNIdentityClient.logoTexture();}
    @Override public void render(UNTransportEntity entity,float yaw,float partial,PoseStack poses,MultiBufferSource buffers,int light)
    {
        Matrix4f submittedEntityFrame=new Matrix4f(poses.last().pose());
        Vec3 dispatcher=new Vec3(Mth.lerp((double)partial,entity.xOld,entity.getX()),Mth.lerp((double)partial,entity.yOld,entity.getY()),Mth.lerp((double)partial,entity.zOld,entity.getZ()));
        poses.pushPose();
        if(entity.carrying()&&entity.level().getEntity(entity.cargoEntityId()) instanceof com.projectseele.entity.EvaUnit01Entity eva)
        {
            var wanted=EvaAirTransportR31.framePosition(eva,partial);
            poses.translate(wanted.x-dispatcher.x,wanted.y+entity.hoistDistance()-dispatcher.y,wanted.z-dispatcher.z);yaw=EvaAirTransportR31.frameYaw(eva,partial);
        }
        else
        {
            var wanted=entity.renderFlightPosition(partial);
            poses.translate(wanted.x-dispatcher.x,wanted.y-dispatcher.y,wanted.z-dispatcher.z);yaw=entity.renderFlightYaw(partial);
        }
        poses.mulPose(Axis.YP.rotationDegrees(-yaw));
        if(entity.groundCart())
        {
            draw("un_ground_carrier",poses,buffers,light);
            if(entity.level().getEntity(entity.cargoEntityId()) instanceof EvaUnit01Entity load)
            {
                float extension=entity.rig(partial);
                for(var pad:com.projectseele.entity.UNReceivingCradleR40.pads(load))
                {
                    var top=new Vector3f((float)pad.x,(float)pad.y,(float)pad.z);
                    var base=new Vector3f(Mth.clamp(top.x,-10,10),-.65F,Mth.clamp(top.z,-12,12));
                    top=new Vector3f(base).lerp(top,extension);
                    var foot=new Vector3f(top.x,-.65F,top.z);
                    rod(poses,buffers,light,base,foot,.40F,30);
                    rod(poses,buffers,light,new Vector3f(base.x,-1.2F,base.z),new Vector3f(foot).add(0,-.45F,0),.25F,42);
                    rod(poses,buffers,light,foot,new Vector3f(top).add(0,-.16F,0),.35F,58);
                    rod(poses,buffers,light,new Vector3f(top).add(-1.5F,-.18F,0),new Vector3f(top).add(1.5F,-.18F,0),.18F,24);
                }
            }
            poses.popPose();return;
        }
        draw("un_transport_body",poses,buffers,light);
        if(com.projectseele.visual.MechanicsR31Review.ENABLED)
        {
            var actual=software.bernie.geckolib.util.RenderUtils.invertAndMultiplyMatrices(poses.last().pose(),submittedEntityFrame);
            actual.m30(actual.m30()+(float)dispatcher.x).m31(actual.m31()+(float)dispatcher.y).m32(actual.m32()+(float)dispatcher.z);
            com.projectseele.client.visual.MechanicsR31Client.captureAircraft(entity,actual,partial);
        }
        cradle(entity,partial,poses,buffers,light,submittedEntityFrame,dispatcher);
        int i=0;
        for(int[] rotor:new int[][]{{-29,-11},{29,-11},{-49,9},{49,9}})
        {
            poses.pushPose();poses.translate(rotor[0],4.8,rotor[1]);poses.mulPose(Axis.YP.rotationDegrees(((entity.level().getGameTime()%3600)+partial)*47*(i%2==0?1:-1)));
            draw("un_transport_rotor_"+i++,poses,buffers,light);poses.popPose();
        }
        var texture=getTextureLocation(entity);
        if(texture!=null)
        {
            var out=buffers.getBuffer(RenderType.entityCutoutNoCull(texture));var m=poses.last().pose();var n=poses.last().normal();
            for(int side:new int[]{-1,1})
            {
                float x=side*12.04F;
                out.vertex(m,x,4,-8).color(255,255,255,255).uv(0,0).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(n,side,0,0).endVertex();
                out.vertex(m,x,4,5).color(255,255,255,255).uv(1,0).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(n,side,0,0).endVertex();
                out.vertex(m,x,-3,5).color(255,255,255,255).uv(1,1).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(n,side,0,0).endVertex();
                out.vertex(m,x,-3,-8).color(255,255,255,255).uv(0,1).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(n,side,0,0).endVertex();
            }
        }
        poses.popPose();super.render(entity,yaw,partial,poses,buffers,light);
    }
}

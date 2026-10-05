package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/** Client-only catenary lead and rigid upper-back plug for connected EVAs. */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT,
        bus = Mod.EventBusSubscriber.Bus.FORGE)
public final class EvaUmbilicalCableRenderer
{
    private static final double RENDER_RANGE = 160.0D;

    private EvaUmbilicalCableRenderer() {}

    @SubscribeEvent
    public static void onRenderLevel(RenderLevelStageEvent event)
    {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_PARTICLES)
        {
            return;
        }
        Minecraft minecraft = Minecraft.getInstance();
        ClientLevel level = minecraft.level;
        if (level == null || minecraft.player == null)
        {
            return;
        }

        AABB visible = minecraft.player.getBoundingBox().inflate(RENDER_RANGE);
        var units = level.getEntitiesOfClass(EvaUnit01Entity.class, visible,
                EvaUnit01Entity::isUmbilicalConnected);
        if (units.isEmpty())
        {
            return;
        }

        PoseStack poseStack = event.getPoseStack();
        Vec3 camera = event.getCamera().getPosition();
        MultiBufferSource.BufferSource buffers = minecraft.renderBuffers().bufferSource();
        // This is painted industrial hardware, not an energy beam.  The old
        // lightning layer was fullbright/additive and visibly flashed against
        // the armour as the camera moved. debugQuads is a stable POSITION_COLOR
        // layer with ordinary alpha blending and no emissive pulse.
        RenderType hardwareLayer = RenderType.debugQuads();
        VertexConsumer consumer = buffers.getBuffer(hardwareLayer);
        poseStack.pushPose();
        poseStack.translate(-camera.x, -camera.y, -camera.z);
        Matrix4f pose = poseStack.last().pose();
        for (EvaUnit01Entity unit : units)
        {
            BlockPos anchor = unit.getUmbilicalAnchor();
            boolean rack=unit.isCarrierPowerConnected();
            if (anchor == null && !rack)
            {
                continue;
            }
            Vec3 pylon = rack?unit.carrierRenderPosition(event.getPartialTick()).add(0,47,0)
                    .add(unit.getRearDirection().scale(9.3))
                    :Vec3.atCenterOf(anchor).add(0.0D, 0.65D, 0.0D);
            if(!rack&&unit.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR)
            {
                float handoff=net.minecraft.util.Mth.clamp((18-unit.getLaunchTicks()+event.getPartialTick())/18F,0,1);
                handoff=handoff*handoff*(3-2*handoff);
                Vec3 travelling=unit.carrierRenderPosition(event.getPartialTick()).add(0,47,0).add(unit.getRearDirection().scale(9.3));
                pylon=travelling.lerp(pylon,handoff);
            }
            var attachment=EvaPowerAttachmentR25.frame(unit,event.getPartialTick());
            Vec3 armourMount = attachment.mount();
            Vec3 plugTail = attachment.socket();
            Vec3 rear = attachment.rear();
            Vec3 right = attachment.right();
            Vec3 up = attachment.up();
            boolean suppliedConnector=com.projectseele.entity.EvaPowerPortsR48.of(unit)!=null;
            Vec3 collarOuter = suppliedConnector?plugTail:plugTail.add(rear.scale(0.35D));

            // Machined bayonet collar, tapered strain relief and separate
            // locking dogs share the final torso socket frame in every pose.
            if(!suppliedConnector)
            {
            sleeve(pose,consumer,armourMount.subtract(rear.scale(.12)),armourMount.add(rear.scale(.40)),right,up,.85F,.85F,.43F,.47F,.44F);
            sleeve(pose,consumer,armourMount.add(rear.scale(.40)),plugTail.subtract(rear.scale(.18)),right,up,.70F,.56F,.19F,.24F,.22F);
            sleeve(pose,consumer,plugTail.subtract(rear.scale(.20)),collarOuter,right,up,.60F,.32F,.58F,.37F,.09F);
            for(int ring=0;ring<6;ring++)
            {
                Vec3 at=armourMount.lerp(plugTail,.38+ring*.065);
                sleeve(pose,consumer,at,at.add(rear.scale(.10)),right,up,.70F,.70F,.09F,.11F,.11F);
            }
            for(int side:new int[]{-1,1})
            {
                Vec3 at=armourMount.add(right.scale(side*.91)).add(rear.scale(.47));
                drawOrientedBox(pose,consumer,at,right,up,rear,.18F,.34F,.5F,.48F,.52F,.48F,1);
                drawOrientedBox(pose,consumer,at.add(up.scale(.38)),right,up,rear,.12F,.065F,.24F,.12F,.75F,.40F,1);
            }
            }

            var route=new java.util.ArrayList<Vec3>();route.add(collarOuter);
            Vec3 exit=collarOuter.add((suppliedConnector?attachment.cableDirection():rear).scale(2.2));route.add(exit);
            var hull=unit.getBoundingBox().inflate(3);
            if(!rack&&hull.clip(exit,pylon).isPresent())
            {
                // When the unit turns its front towards the reel, take the
                // lead around the flank instead of drawing it through its chest.
                Vec3 back=unit.getRearDirection();
                double width=Math.max(16,unit.getBbWidth()*.5+6);
                Vec3 centre=unit.getPosition(event.getPartialTick());
                double rearDistance=exit.subtract(centre).dot(back);
                Vec3 rearCorner=exit.add(back.scale(Math.max(0,width-rearDistance)));
                route.add(rearCorner);
                Vec3 lateral=new Vec3(right.x,0,right.z).normalize();
                if(pylon.subtract(unit.position()).dot(lateral)<0)lateral=lateral.scale(-1);
                if(hull.clip(rearCorner,pylon).isPresent())
                {
                    Vec3 rearSide=rearCorner.add(lateral.scale(width));route.add(rearSide);
                    Vec3 side=centre.add(lateral.scale(width));
                    route.add(new Vec3(side.x,Math.max(unit.getY()+1.5,
                            Math.min(exit.y-2,pylon.y+2)),side.z));
                }
            }
            route.add(pylon);
            // Round the support-route corners before applying gravity. Hard
            // ninety-degree joints made a prone EVA's lead look like a rail.
            var rounded=new java.util.ArrayList<Vec3>();rounded.add(route.get(0));
            for(int corner=1;corner<route.size()-1;corner++)
            {
                Vec3 previous=route.get(corner-1),joint=route.get(corner),next=route.get(corner+1);
                double radius=Math.min(2.5,Math.min(previous.distanceTo(joint),joint.distanceTo(next))*.4);
                Vec3 entry=joint.add(previous.subtract(joint).normalize().scale(radius));
                Vec3 leave=joint.add(next.subtract(joint).normalize().scale(radius));
                rounded.add(entry);
                for(int step=1;step<=12;step++)
                {
                    double t=step/12.0;
                    rounded.add(entry.scale((1-t)*(1-t)).add(joint.scale(2*(1-t)*t)).add(leave.scale(t*t)));
                }
            }
            rounded.add(pylon);
            for(int leg=1;leg<rounded.size();leg++)
            {
                Vec3 a=rounded.get(leg-1),b=rounded.get(leg);double span=a.distanceTo(b);
                double sag=span<4?0:Math.min(16,span*.10);int segments=Math.max(2,Math.min(128,(int)Math.ceil(span/2)));
                Vec3 previous=a;
                for(int segment=1;segment<=segments;segment++)
                {
                    Vec3 current=cablePoint(a,b,sag,segment/(double)segments);
                    tube(pose,consumer,previous,current,.22F);previous=current;
                }
            }
        }
        poseStack.popPose();
        buffers.endBatch(hardwareLayer);
    }

    private static Vec3 cablePoint(Vec3 start, Vec3 end, double sag, double t)
    {
        Vec3 point = start.lerp(end, t).add(0.0D, -Math.sin(Math.PI * t) * sag, 0.0D);
        // Reel and back socket sit above the floor. Do not let increased
        // cable length turn the decorative sag into a subterranean loop.
        return new Vec3(point.x,Math.max(Math.min(start.y,end.y)-.55,point.y),point.z);
    }

    private static void sleeve(Matrix4f pose,VertexConsumer out,Vec3 a,Vec3 b,Vec3 right,Vec3 up,
                               float ra,float rb,float r,float g,float blue)
    {
        for(int i=0;i<24;i++)
        {
            double t=i*Math.PI/12,u=(i+1)*Math.PI/12;
            Vec3 n=right.scale(Math.cos(t)).add(up.scale(Math.sin(t))),m=right.scale(Math.cos(u)).add(up.scale(Math.sin(u)));
            float shade=.72F+.28F*(float)Math.max(0,Math.sin((t+u)/2));
            RibbonRenderer.quadBothSides(pose,out,vector(a.add(n.scale(ra))),vector(b.add(n.scale(rb))),vector(b.add(m.scale(rb))),vector(a.add(m.scale(ra))),r*shade,g*shade,blue*shade,1);
            RibbonRenderer.quadBothSides(pose,out,vector(a),vector(a.add(n.scale(ra))),vector(a.add(m.scale(ra))),vector(a),r,g,blue,1);
        }
    }

    private static void tube(Matrix4f pose, VertexConsumer consumer, Vec3 a, Vec3 b, float radius)
    {
        Vec3 axis=b.subtract(a).normalize();
        Vec3 u=axis.cross(Math.abs(axis.y)>.95?new Vec3(1,0,0):new Vec3(0,1,0)).normalize();
        Vec3 v=axis.cross(u).normalize();
        for(int side=0;side<10;side++)
        {
            double t0=side*Math.PI/5,t1=(side+1)*Math.PI/5;
            Vec3 r0=u.scale(Math.cos(t0)*radius).add(v.scale(Math.sin(t0)*radius));
            Vec3 r1=u.scale(Math.cos(t1)*radius).add(v.scale(Math.sin(t1)*radius));
            float shade=.10F+.08F*(float)Math.max(0,u.scale(Math.cos((t0+t1)/2)).add(v.scale(Math.sin((t0+t1)/2))).y);
            RibbonRenderer.quadBothSides(pose,consumer,vector(a.add(r0)),vector(b.add(r0)),vector(b.add(r1)),vector(a.add(r1)),shade*.9F,shade,shade*1.05F,1);
        }
    }

    private static Vector3f vector(Vec3 value)
    {
        return new Vector3f((float) value.x, (float) value.y, (float) value.z);
    }

    private static void drawOrientedBox(Matrix4f pose, VertexConsumer consumer,
                                        Vec3 centre, Vec3 right, Vec3 up,
                                        Vec3 rear, float halfRight,
                                        float halfUp, float halfRear,
                                        float red, float green, float blue,
                                        float alpha)
    {
        Vector3f c = vector(centre);
        Vector3f r = vector(right.scale(halfRight));
        Vector3f u = vector(up.scale(halfUp));
        Vector3f b = vector(rear.scale(halfRear));
        Vector3f p000 = corner(c, r, u, b, -1, -1, -1);
        Vector3f p001 = corner(c, r, u, b, -1, -1, 1);
        Vector3f p010 = corner(c, r, u, b, -1, 1, -1);
        Vector3f p011 = corner(c, r, u, b, -1, 1, 1);
        Vector3f p100 = corner(c, r, u, b, 1, -1, -1);
        Vector3f p101 = corner(c, r, u, b, 1, -1, 1);
        Vector3f p110 = corner(c, r, u, b, 1, 1, -1);
        Vector3f p111 = corner(c, r, u, b, 1, 1, 1);
        RibbonRenderer.quadBothSides(pose, consumer, p000, p100, p110, p010,
                red, green, blue, alpha);
        RibbonRenderer.quadBothSides(pose, consumer, p101, p001, p011, p111,
                red, green, blue, alpha);
        RibbonRenderer.quadBothSides(pose, consumer, p001, p000, p010, p011,
                red, green, blue, alpha);
        RibbonRenderer.quadBothSides(pose, consumer, p100, p101, p111, p110,
                red, green, blue, alpha);
        RibbonRenderer.quadBothSides(pose, consumer, p010, p110, p111, p011,
                red, green, blue, alpha);
        RibbonRenderer.quadBothSides(pose, consumer, p001, p101, p100, p000,
                red, green, blue, alpha);
    }

    private static Vector3f corner(Vector3f centre, Vector3f right,
                                   Vector3f up, Vector3f rear,
                                   int rightSign, int upSign, int rearSign)
    {
        return new Vector3f(centre)
                .add(new Vector3f(right).mul(rightSign))
                .add(new Vector3f(up).mul(upSign))
                .add(new Vector3f(rear).mul(rearSign));
    }
}

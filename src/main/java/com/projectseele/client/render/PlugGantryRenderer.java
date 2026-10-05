package com.projectseele.client.render;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.blaze3d.vertex.VertexBuffer;
import com.mojang.blaze3d.systems.RenderSystem;
import net.minecraft.client.renderer.GameRenderer;
import com.mojang.blaze3d.vertex.VertexConsumer;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.EntryPlugKinematics;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.RenderType;
import net.minecraft.client.renderer.texture.OverlayTexture;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.phys.Vec3;
import org.joml.Vector3f;
import org.joml.Quaternionf;

/** Original rail hoist: twin girders, reeved winches, four ropes and a two-axis plug chuck. */
public final class PlugGantryRenderer
{
    private static final ResourceLocation PAINT=new ResourceLocation("minecraft","textures/block/white_concrete.png");
    private static final int GREEN=0x566a51, EDGE=0x8d9a86, STEEL=0xadb7bb, DARK=0x222d32, GOLD=0xb69347;
    private final PoseStack poses; private final VertexConsumer buffer; private final int light;private final RigidMachineryPartR44.Builder baking;
    private final MultiBufferSource buffers;
    private static RigidMachineryPartR44 TOP,YOKE,CHUCK,JAW_LEFT,JAW_RIGHT,HOSES_CLOSED,HOSES_OPEN,ROPE,SHEAVE,LINKS,WHEEL;
    private PlugGantryRenderer(PoseStack poses, MultiBufferSource buffers, int light)
    {this.poses=poses;this.buffers=buffers;this.buffer=buffers.getBuffer(RenderType.entitySolid(PAINT));this.light=light;this.baking=null;}
    private PlugGantryRenderer(RigidMachineryPartR44.Builder builder){this.poses=new PoseStack();this.buffers=null;this.buffer=null;this.light=15728880;this.baking=builder;}
    public static void render(NervCarrierPlatformEntity entity,float partial,PoseStack poses,MultiBufferSource buffers,int light)
    {TvCraneMeshWitnessR44.begin(entity,partial,poses);try{new PlugGantryRenderer(poses,buffers,light).draw(entity,partial);}finally{TvCraneMeshWitnessR44.end();}}
    private void draw(NervCarrierPlatformEntity entity,float partial)
    {
        gpu(topMesh(),poses,light);
        // The two surveyed runways run along Z at X = body axis +/- 4.
        // Wheel bottoms meet their Y=-373 running surface; no floating bogies.
        for(double x:new double[]{-4,4})for(double z:new double[]{-2.8,2.8})
        {
            poses.pushPose();poses.translate(x,.38,z);
            poses.mulPose(new Quaternionf().rotationX((float)(entity.getPosition(partial).z/.38)));
            gpu(wheelMesh(),poses,light);poses.popPose();
        }
        Vec3 lower=v(0,entity.getCraneBottomOffset(partial),0);
        EntryPlugCarrierEntity plug=entity.getCranePlug();
        com.projectseele.world.RigidTransform transform=plug==null?null:plug.getInterpolatedCanonicalTransform(partial);
        Quaternionf stowedRotation=new Quaternionf().rotationX((float)-Math.PI/2),rotation=new Quaternionf(stowedRotation);
        Vec3 anchor=entity.hasCraneReference()?entity.getCraneReferenceAnchor():lower;
        boolean coupled=transform!=null&&!(plug.getInsertionStage()==EntryPlugCarrierEntity.STAGE_EJECTING&&plug.getInsertionProgress()>=99);
        if(transform!=null){anchor=transform.transformPoint(EntryPlugKinematics.CRANE_ATTACHMENT_P).subtract(entity.getPosition(partial));rotation=transform.rotation();}
        else if(entity.hasCraneReference())rotation=entity.getCraneReferenceRotation();
        float released=1;
        if(coupled){lower=anchor;released=0;}
        else if(transform!=null||entity.hasCraneReference())
        {
            double travel=Math.max(1,-2-anchor.y),linear=Math.max(0,Math.min(1,(lower.y-anchor.y)/travel));
            double rise=travel*com.projectseele.entity.EvaDorsalMechanism.smooth((float)linear);
            Vector3f forward=rotation.transform(new Vector3f(0,0,1));Vec3 axis=v(forward.x,forward.y,forward.z);
            double axial=Math.min(rise,2*Math.max(.25,axis.y));
            lower=anchor.add(axis.scale(axial/Math.max(.25,axis.y))).add(0,rise-axial,0);
            released=(float)Math.max(0,Math.min(1,rise/.65));
            rotation.slerp(stowedRotation,com.projectseele.entity.EvaDorsalMechanism.smooth((float)((rise-2)/Math.max(1,travel-2))));
        }
        Vec3 suppliedMount = TripoMachineryR48.clampMount();
        Vec3 mount = lower;
        if (suppliedMount != null)
        {
            Vector3f rotatedMount = rotation.transform(new Vector3f((float)suppliedMount.x,(float)suppliedMount.y,(float)suppliedMount.z));
            mount = lower.add(rotatedMount.x,rotatedMount.y,rotatedMount.z);
        }
        Vec3 yoke=suppliedMount==null?lower.add(0,1.6,0):mount.add(0,.45,0);
        for(double x:new double[]{-2.4,2.4})for(double z:new double[]{-.78,.78})
        {
            Vec3 end=yoke.add(x,0,z);gpuRope(v(x,-.7,z),end,.065);
            poses.pushPose();poses.translate(end.x,end.y,end.z);gpu(sheaveMesh(),poses,light);poses.popPose();
        }
        poses.pushPose();poses.translate(yoke.x,yoke.y,yoke.z);gpu(yokeMesh(),poses,light);poses.popPose();
        // The gimbal centre and its rotating collar derive from the capsule's exact render transform.
        if (suppliedMount == null)
        {poses.pushPose();poses.translate(lower.x,lower.y,lower.z);gpu(linksMesh(),poses,light);poses.popPose();}
        else
        {
            gpuRope(yoke.add(-1.8,-.2,0),mount.add(-.5,0,0),.10);
            gpuRope(yoke.add(1.8,-.2,0),mount.add(.5,0,0),.10);
        }
        poses.pushPose();poses.translate(lower.x,lower.y,lower.z);
        poses.mulPose(rotation);
        if (TripoMachineryR48.clamp(poses,buffers,light,released))
        {poses.popPose();return;}
        gpu(chuckMesh(),poses,light);
        for(double side:new double[]{-1,1})
        {
            poses.pushPose();poses.translate(side*.55*released,0,0);gpu(jawMesh(side),poses,light);poses.popPose();
        }
        // Parked and coupled hoses are rigid. Keep the exact procedural curve
        // only during the short jaw-release interval, with no quantized motion.
        if(released==0||released==1)gpu(hoseMesh(released==1),poses,light);
        else for(double side:new double[]{-1,1})hose(side,released);
        poses.popPose();
    }
    public static void clearCache()
    {TOP=YOKE=CHUCK=JAW_LEFT=JAW_RIGHT=HOSES_CLOSED=HOSES_OPEN=ROPE=SHEAVE=LINKS=WHEEL=null;}
    private static RigidMachineryPartR44 bake(java.util.function.Consumer<PlugGantryRenderer> author)
    {
        var builder=new RigidMachineryPartR44.Builder();author.accept(new PlugGantryRenderer(builder));return builder.finish();
    }
    private static RigidMachineryPartR44 topMesh(){if(TOP==null)TOP=bake(PlugGantryRenderer::top);return TOP;}
    private static RigidMachineryPartR44 yokeMesh(){if(YOKE==null)YOKE=bake(PlugGantryRenderer::yoke);return YOKE;}
    private static RigidMachineryPartR44 chuckMesh(){if(CHUCK==null)CHUCK=bake(PlugGantryRenderer::chuck);return CHUCK;}
    private static RigidMachineryPartR44 jawMesh(double side)
    {
        if(side<0){if(JAW_LEFT==null)JAW_LEFT=bake(r->r.jaw(-1));return JAW_LEFT;}
        if(JAW_RIGHT==null)JAW_RIGHT=bake(r->r.jaw(1));return JAW_RIGHT;
    }
    private static RigidMachineryPartR44 hoseMesh(boolean open)
    {
        if(open){if(HOSES_OPEN==null)HOSES_OPEN=bake(r->{r.hose(-1,1);r.hose(1,1);});return HOSES_OPEN;}
        if(HOSES_CLOSED==null)HOSES_CLOSED=bake(r->{r.hose(-1,0);r.hose(1,0);});return HOSES_CLOSED;
    }
    private static RigidMachineryPartR44 sheaveMesh(){if(SHEAVE==null)SHEAVE=bake(r->r.cylinder(v(0,-.12,-.20),v(0,-.12,.20),.25,.10,DARK,16));return SHEAVE;}
    private static RigidMachineryPartR44 linksMesh(){if(LINKS==null)LINKS=bake(r->{r.rod(v(-2.45,1.4,0),v(-1.50,0,0),.17,STEEL);r.rod(v(2.45,1.4,0),v(1.50,0,0),.17,STEEL);});return LINKS;}
    private static RigidMachineryPartR44 wheelMesh()
    {
        if(WHEEL==null)WHEEL=bake(r->
        {
            r.cylinder(v(-.36,0,0),v(.36,0,0),.38,.16,DARK,48);
            r.cylinder(v(-.41,0,0),v(.41,0,0),.19,0,STEEL,32);
            for(int i=0;i<8;i++)
            {
                double a=i*Math.PI/4;double y=Math.cos(a)*.28,z=Math.sin(a)*.28;
                r.cylinder(v(-.38,y,z),v(.38,y,z),.045,0,STEEL,8);
            }
        });
        return WHEEL;
    }
    private void gpuRope(Vec3 a,Vec3 b,double radius)
    {
        if(ROPE==null)ROPE=bake(r->r.cylinder(v(0,0,0),v(0,1,0),1,0,STEEL,12));Vec3 delta=b.subtract(a);double length=delta.length();if(length<1e-6)return;
        poses.pushPose();poses.translate(a.x,a.y,a.z);poses.mulPose(new Quaternionf().rotationTo(new Vector3f(0,1,0),new Vector3f((float)(delta.x/length),(float)(delta.y/length),(float)(delta.z/length))));poses.scale((float)radius,(float)length,(float)radius);gpu(ROPE,poses,light);poses.popPose();
    }
    private void gpu(RigidMachineryPartR44 mesh,PoseStack poses,int light)
    {
        mesh.draw(poses,buffers,light);
    }
    private void top()
    {
        for(double x:new double[]{-4,4})
        {
            box(x-.25,.05,-3.6,.50,.16,7.2,GREEN);
            box(x-.25,1.09,-3.6,.50,.16,7.2,GREEN);
            box(x-.08,.21,-3.6,.16,.88,7.2,EDGE);
            for(double z:new double[]{-2.8,2.8})
            {
                housing(x-.47,.46,z-.62,.94,.78,1.24,.16,GREEN);
                cylinder(v(x-.54,.38,z),v(x+.54,.38,z),.12,0,STEEL,32);
                for(double side:new double[]{-.5,.5})for(double dz:new double[]{-.42,.42})
                    cylinder(v(x+side,.93,z+dz),v(x+side+Math.copySign(.045,side),.93,z+dz),.045,0,DARK,8);
            }
        }
        for(double z:new double[]{-2.1,2.1})
        {
            housing(-4.28,.50,z-.24,8.56,.63,.48,.12,GREEN);
            for(double x:new double[]{-2.3,2.3})rod(v(x,-.4,z*.52),v(x,.78,z),.12,STEEL);
        }
        box(-3,-.65,-1.7,6,.28,3.4,GREEN);
        for(double x:new double[]{-2.30,2.30})
        {
            cylinder(v(x,-.06,-1.25),v(x,-.06,1.25),.48,.14,STEEL,24);
            for(int n=0;n<15;n++)cylinder(v(x,-.06,-1.20+n*.16),v(x,-.06,-1.16+n*.16),.51,.48,DARK,24);
            housing(x-.61,-.28,1.25,1.22,1.10,.72,.20,GREEN);cylinder(v(x,.15,1.97),v(x,.15,2.08),.32,0,STEEL,40);
            for(int i=0;i<8;i++){double angle=i*Math.PI/4;cylinder(v(x+Math.cos(angle)*.44,.15+Math.sin(angle)*.44,1.98),v(x+Math.cos(angle)*.44,.15+Math.sin(angle)*.44,2.035),.042,0,DARK,6);}
            for(double z:new double[]{-1.08,1.08})box(x-.7,-.64,z-.18,1.4,.18,.36,GOLD);
        }
        housing(-.62,-.45,-1.1,1.24,1.5,1.9,.16,GREEN);
        for(int i=0;i<6;i++)box(-.55,.10+i*.12,-1.14,1.1,.035,.08,DARK);
        // Rounded motor casings, cooling fins and flexible hydraulic lines are real mesh surfaces.
        for(double side:new double[]{-1,1})
        {
            Vec3 centre=v(side*3.65,.03,.15);cylinder(centre.add(-.85,0,0),centre.add(.85,0,0),.50,0,GREEN,48);
            for(int i=0;i<14;i++)cylinder(centre.add(-.72+i*.11,0,0),centre.add(-.68+i*.11,0,0),.54,.49,EDGE,48);
            for(int i=0;i<8;i++){double a=i*Math.PI/4;Vec3 ring=v(0,Math.cos(a)*.39,Math.sin(a)*.39);cylinder(centre.add(.85,0,0).add(ring),centre.add(.90,0,0).add(ring),.045,0,STEEL,10);}
            Vec3 last=centre.add(side*.9,.1,0);
            for(int i=1;i<=24;i++){double t=i/24D;Vec3 next=v(side*(4.55+Math.sin(t*Math.PI)*.6),.13-Math.sin(t*Math.PI)*.38,t*1.1+.15);rod(last,next,.055,DARK);last=next;}
        }
        // Fabricated service deck and tubular handrail give the assembly
        // an industrial silhouette independent of Minecraft block sizes.
        for(int i=0;i<18;i++)box(-2.7+i*.30,.98,2.25,.065,.065,.9,STEEL);
        for(double x:new double[]{-2.7,0,2.7})rod(v(x,1.01,3.12),v(x,2.12,3.12),.045,GOLD);
        rod(v(-2.75,2.12,3.12),v(2.75,2.12,3.12),.045,GOLD);rod(v(-2.75,1.57,3.12),v(2.75,1.57,3.12),.035,GOLD);
        for(double x:new double[]{-1.6,1.6})
        {
            rod(v(x,.05,1.65),v(x,1.01,3.10),.055,DARK);
            housing(x-.17,1.03,2.34,.34,.46,.40,.07,DARK);
        }
    }
    private void yoke()
    {
        for(double z:new double[]{-1.05,.77})
        {
            housing(-3.08,-.33,z,6.16,.55,.28,.18,GREEN);
            for(double x:new double[]{-2.4,2.4})
            {
                housing(x-.47,-.40,z-.06,.94,.87,.40,.24,EDGE);
                cylinder(v(x,-.08,z-.10),v(x,-.08,z+.40),.29,.10,DARK,40);
                cylinder(v(x,-.08,z-.15),v(x,-.08,z+.45),.105,0,STEEL,24);
            }
        }
        for(double x:new double[]{-2.5,2.5})housing(x-.2,-.28,-1.05,.4,.5,2.1,.09,EDGE);
        for(double side:new double[]{-1,1})
        {
            Vec3 a=v(side*2.25,-.28,.50),b=v(side*1.4,-1.30,.30);
            cylinder(a,a.lerp(b,.65),.21,0,GREEN,32);cylinder(a.lerp(b,.58),b,.095,0,STEEL,24);
            cylinder(a.add(-.12,0,0),a.add(.12,0,0),.18,.05,GOLD,24);
        }
    }
    private void chuck()
    {
        cylinder(v(0,0,-.42),v(0,0,.32),1.62,1.18,GREEN,64);
        cylinder(v(0,0,-.48),v(0,0,-.37),1.70,1.20,STEEL,64);
        cylinder(v(0,0,.29),v(0,0,.44),1.66,1.22,GOLD,64);
        for(int i=0;i<8;i++)
        {
            double a=i*Math.PI/4;Vec3 r=v(Math.cos(a),Math.sin(a),0);
            cylinder(r.scale(1.45).add(0,0,.44),r.scale(1.45).add(0,0,.53),.08,0,DARK,10);
            if(i%2==0){rod(r.scale(1.62).add(0,0,-.25),r.scale(1.27).add(0,0,-.8),.11,STEEL);}
        }
        for(int i=0;i<3;i++)
        {
            double angle=(i/3D+.25)*Math.PI*2;Vec3 radial=v(Math.cos(angle),Math.sin(angle),0);
            cylinder(radial.scale(1.72).add(0,0,-.08),radial.scale(1.22).add(0,0,-.08),.16,0,DARK,24);
            cylinder(radial.scale(1.34).add(0,0,-.08),radial.scale(1.16).add(0,0,-.08),.095,0,STEEL,24);
        }
        housing(-.30,1.47,-.28,.60,.40,.58,.12,DARK);
        cylinder(v(0,1.67,.30),v(0,1.67,.42),.11,0,STEEL,32);
        cylinder(v(0,1.67,.421),v(0,1.67,.435),.076,0,0x395868,32);
        // Toothed drive ring and axial actuator behind the plug tail.
        for(int i=0;i<48;i++)
        {
            double a=2*Math.PI*i/48,b=a+.065;Vec3 r=v(Math.cos(a),Math.sin(a),0),s=v(Math.cos(b),Math.sin(b),0);
            Vec3 p=r.scale(1.61).add(0,0,.12),q=s.scale(1.61).add(0,0,.12),u=s.scale(1.78).add(0,0,.12),w=r.scale(1.78).add(0,0,.12);
            quad(p,q,u,w,DARK);quad(p.add(0,0,.18),w.add(0,0,.18),u.add(0,0,.18),q.add(0,0,.18),STEEL);quad(w,u,u.add(0,0,.18),w.add(0,0,.18),DARK);
        }
        cylinder(v(0,1.85,-.62),v(0,1.85,.90),.26,0,STEEL,40);
        cylinder(v(0,1.85,-1.42),v(0,1.85,-.58),.09,0,0xd0d7d9,24);
        housing(-.19,1.71,.86,.38,.28,.26,.06,DARK);
    }
    private void jaw(double side)
    {
        housing(side>0?1.58:-2.92,-1.32,-.48,1.34,2.74,.66,.28,GREEN);
        for(double y:new double[]{-.94,.94})
        {
            cylinder(v(side*2.04,y,-.57),v(side*2.04,y,.28),.22,.085,DARK,32);
            cylinder(v(side*2.04,y,-.62),v(side*2.04,y,.34),.085,0,STEEL,20);
            rod(v(side*1.75,y,-.42),v(side*.75,y*.37,-1.10),.13,STEEL);
            cylinder(v(side*.75,y*.37,-1.20),v(side*.75,y*.37,-.97),.17,0,DARK,24);
        }
        housing(side>0?1.76:-2.64,-.38,.20,.88,.76,.25,.15,EDGE);
        for(int i=0;i<4;i++)box(side>0?1.84:-2.56,-.27+i*.15,.46,.72,.055,.04,DARK);
    }
    private void hose(double side,float released)
    {
        for(int line=0;line<2;line++)
        {
            Vec3 a=v(side*1.18,-.92+line*.23,.46),b=v(side*(2.35+.55*released),-1.78,.98),c=v(side*(3.20+.55*released),1.60,.85),d=v(side*(2.10+.55*released),1.20,.32);Vec3 previous=a;
            for(int i=1;i<=18;i++)
            {
                double t=i/18D,u=1-t;Vec3 next=a.scale(u*u*u).add(b.scale(3*u*u*t)).add(c.scale(3*u*t*t)).add(d.scale(t*t*t));rod(previous,next,line==0?.070:.055,line==0?0x8e272c:DARK);previous=next;
            }
        }
    }
    /** Extruded chamfered casting, with an inset lid and machined edge. */
    private void housing(double x,double y,double z,double w,double h,double depth,double bevel,int colour)
    {
        double r=Math.min(bevel,Math.min(w,h)*.45);
        double[][] outline={{r,0},{w-r,0},{w,r},{w,h-r},{w-r,h},{r,h},{0,h-r},{0,r}};
        Vec3 front=v(x+w*.5,y+h*.5,z),back=front.add(0,0,depth);
        for(int i=0;i<8;i++)
        {
            double[] p=outline[i],q=outline[(i+1)%8];Vec3 a=v(x+p[0],y+p[1],z),b=v(x+q[0],y+q[1],z),c=b.add(0,0,depth),d=a.add(0,0,depth);
            quad(a,d,c,b,colour);quad(front,a,b,b,colour);quad(back,c,d,d,colour);
            if(i%2!=0)rod(a.add(0,0,.02),b.add(0,0,.02),.014,EDGE);
        }
    }
    private void box(double x,double y,double z,double w,double h,double d,int colour)
    {
        Vec3 a=v(x,y,z),b=v(x+w,y,z),c=v(x+w,y+h,z),e=v(x,y+h,z),f=v(x,y,z+d),g=v(x+w,y,z+d),i=v(x+w,y+h,z+d),j=v(x,y+h,z+d);
        quad(a,e,c,b,colour);quad(f,g,i,j,colour);quad(a,f,j,e,colour);quad(b,c,i,g,colour);quad(e,j,i,c,colour);quad(a,b,g,f,colour);
    }
    private void rod(Vec3 a,Vec3 b,double radius,int colour){cylinder(a,b,radius,0,colour,12);}
    private void cylinder(Vec3 a,Vec3 b,double radius,double inside,int colour,int segments)
    {
        Vec3 axis=b.subtract(a).normalize(),x=axis.cross(Math.abs(axis.y)<.9?v(0,1,0):v(1,0,0)).normalize(),y=axis.cross(x);
        for(int n=0;n<segments;n++)
        {
            double s=2*Math.PI*n/segments,t=2*Math.PI*(n+1)/segments;
            Vec3 r=x.scale(Math.cos(s)).add(y.scale(Math.sin(s))),q=x.scale(Math.cos(t)).add(y.scale(Math.sin(t)));
            quad(a.add(r.scale(radius)),a.add(q.scale(radius)),b.add(q.scale(radius)),b.add(r.scale(radius)),colour);
            quad(a.add(r.scale(inside)),a.add(q.scale(inside)),a.add(q.scale(radius)),a.add(r.scale(radius)),colour);
            quad(b.add(r.scale(radius)),b.add(q.scale(radius)),b.add(q.scale(inside)),b.add(r.scale(inside)),colour);
            if(inside>0)quad(a.add(r.scale(inside)),b.add(r.scale(inside)),b.add(q.scale(inside)),a.add(q.scale(inside)),DARK);
        }
    }
    private void quad(Vec3 a,Vec3 b,Vec3 c,Vec3 d,int colour)
    {
        Vec3 n=b.subtract(a).cross(c.subtract(a));if(n.lengthSqr()<1e-12)return;n=n.normalize();
        float red=((colour>>16)&255)/255F,green=((colour>>8)&255)/255F,blue=(colour&255)/255F;
        if(baking!=null)
        {
            baking.quad(a,b,c,d,colour);return;
        }
        for(Vec3 p:new Vec3[]{a,b,c,d})buffer.vertex(poses.last().pose(),(float)p.x,(float)p.y,(float)p.z).color(red,green,blue,1).uv(.5F,.5F).overlayCoords(OverlayTexture.NO_OVERLAY).uv2(light).normal(poses.last().normal(),(float)n.x,(float)n.y,(float)n.z).endVertex();
    }
    private static Vec3 v(double x,double y,double z){return new Vec3(x,y,z);}
}

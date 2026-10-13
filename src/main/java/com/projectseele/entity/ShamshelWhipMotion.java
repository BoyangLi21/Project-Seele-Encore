package com.projectseele.entity;

import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import org.joml.Quaternionf;
import java.util.*;

/** Measured rig pivots; one FK curve drives both visible whips and server contacts. */
public final class ShamshelWhipMotion
{
    public static final int CYCLE = 44, CONTACT_START = 12, CONTACT_END = 23;
    public static final int GROUND=3;
    public static int contactStart(int mode){return mode==GROUND?28:mode==1?19:mode==2?17:12;}
    public static int contactEnd(int mode){return mode==GROUND?37:mode==0?23:28;}
    public static int cycle(int mode){return mode==GROUND?64:mode==0?40:44;}
    private static final float[][] PIVOTS = {{51.868429F,155.598410F,-11.655827F},
            {60.027508F,121.796513F,-29.139567F},{62.941464F,87.994615F,-52.451220F},{60.610299F,54.192717F,-67.603795F}};
    public static float smooth(float x) {return (float)CombatMotionR29.ease(x);}
    public static float envelope(float age) { return age < 0 ? 0 : smooth(age/10)*(1-smooth((age-23)/11)); }
    public static float envelope(int mode,float age){return age<0?0:smooth(age/(mode==0?10:14))*(1-smooth((age-contactEnd(mode))/(cycle(mode)-contactEnd(mode))));}
    public static Vector3f rotation(int side, int segment, int activeSide, float age, double clock)
    {return rotation(side,segment,activeSide,0,age,clock);}
    public static Vector3f rotation(int side, int segment, int activeSide,int mode,float age,double clock)
    {
        float idle = (float)Math.sin(clock*.055-segment*.55+side)*.025F;
        if (age < 0 || side != activeSide) return new Vector3f(idle, 0, idle*.4F);
        float weight = envelope(mode,age), drive = smooth((age-(contactStart(mode)-3)-segment*.8F)/(mode==1?7:9));
        if(mode==1)return new Vector3f((segment==0?.56F+.71F*drive:.14F-.19F*drive)*weight+idle*(1-weight),side*(segment==0?.42F*(1-drive):.08F*(1-drive))*weight,side*.035F*weight);
        if(mode==2)return new Vector3f((segment==0?1.03F+.15F*drive:.04F)*weight+idle*(1-weight),-side*((segment==0?.76F:.12F)*(1-2*drive))*weight,-side*(segment==0?.18F:.05F)*weight);
        return new Vector3f((segment==0?1.12F:.045F)*weight+idle*(1-weight),
                side*((segment==0?.72F:.11F)*(1-2*drive))*weight,
                side*(segment==0?.13F:.045F)*weight);
    }
    public static float bodyPitch(float age) { return (.035F-.085F*smooth((age-11)/9))*envelope(age); }
    public static float bodyYaw(int side,float age) {return side*(.07F-.14F*smooth((age-11)/9))*envelope(age);}
    public static float bodyPitch(int mode,float age){return mode==GROUND?-.60F*groundWeight(age):(mode==1?.11F-.20F*smooth((age-16)/8):.035F-.085F*smooth((age-(contactStart(mode)-1))/9))*envelope(mode,age);}
    public static float bodyYaw(int side,int mode,float age){return mode==GROUND?0:(mode==1?0:side*(mode==2?-1:1)*(.07F-.14F*smooth((age-(contactStart(mode)-1))/9)))*envelope(mode,age);}
    public static float groundWeight(float age){return age<0?0:smooth(age/20)*(1-smooth((age-40)/24));}
    private static Vector3f pivot(int side, int index)
    {
        float[] p=PIVOTS[index]; return new Vector3f(-side*p[0],p[1],p[2]).div(16);
    }
    private static void rotate(Matrix4f m, Vector3f pivot, Vector3f r)
    { m.translate(pivot).rotateZ(r.z).rotateY(r.y).rotateX(r.x).translate(-pivot.x,-pivot.y,-pivot.z); }
    public static Matrix4f bodyMatrix(ShamshelEntity actor,float age,float partial)
    {
        Vec3 origin=actor.level().isClientSide?actor.getPosition(partial):actor.position();
        float yaw=actor.isSweeping()?actor.sweepYaw():(actor.level().isClientSide?Mth.rotLerp(partial,actor.yBodyRotO,actor.yBodyRot):actor.yBodyRot);
        var matrix=new Matrix4f().translation(origin.toVector3f()).rotateY((float)Math.toRadians(180-yaw)).scale(5);
        rotate(matrix,new Vector3f(0,93.822528F/16,0),new Vector3f(bodyPitch(actor.sweepMode(),age),bodyYaw(actor.sweepSide(),actor.sweepMode(),age),0));
        return matrix;
    }
    private static Vector3f tip(int side){return new Vector3f(-side*65,20,-78).div(16);}
    private record GroundFrame(float age,float partial,int side,Vec3 origin,float yaw,Vec3 aim,Quaternionf[] rotations){}
    private static final Map<ShamshelEntity,GroundFrame> GROUND_CACHE=new WeakHashMap<>();
    /** A shallow original-length polygon bends in a horizontal plane, so the descent cannot fold below the plate. */
    private static synchronized Quaternionf[] groundRotations(ShamshelEntity actor,float age,float partial)
    {
        int side=actor.sweepSide();Vec3 origin=actor.level().isClientSide?actor.getPosition(partial):actor.position(),aim=actor.armorAimR52();float yaw=actor.sweepYaw();
        var cached=GROUND_CACHE.get(actor);if(cached!=null&&cached.age()==age&&cached.partial()==partial&&cached.side()==side&&cached.origin().equals(origin)&&cached.yaw()==yaw&&cached.aim().equals(aim))return cached.rotations();
        var joints=new Quaternionf[4];for(int i=0;i<4;i++)joints[i]=new Quaternionf();
        var inverse=bodyMatrix(actor,age,partial).invert();
        float clearance=8*(1-smooth((age-23)/5))+8*smooth((age-40)/10);
        Vector3f target=inverse.transformPosition(actor.armorAimR52().add(0,clearance,0).toVector3f());
        Vector3f direction=target.sub(pivot(side,0),new Vector3f());float distance=direction.length();direction.normalize();
        Vector3f lateral=new Vector3f(direction).cross(inverse.transformDirection(new Vector3f(0,1,0)).normalize());
        if(lateral.lengthSquared()<1e-6F)lateral.set(1,0,0);lateral.normalize();
        float[] lengths=new float[4];for(int i=0;i<4;i++)lengths[i]=pivot(side,i).distance(i==3?tip(side):pivot(side,i+1));
        float low=0,high=1.3F;for(int iteration=0;iteration<30;iteration++)
        {
            float bend=(low+high)/2;double x=0,y=0;for(int i=0;i<4;i++){x+=lengths[i]*Math.cos(bend*i);y+=lengths[i]*Math.sin(bend*i);}
            if(Math.hypot(x,y)>distance)low=bend;else high=bend;
        }
        float bend=(low+high)/2;double x=0,y=0;for(int i=0;i<4;i++){x+=lengths[i]*Math.cos(bend*i);y+=lengths[i]*Math.sin(bend*i);}
        float offset=(float)Math.atan2(y,x);var prefix=new Matrix4f();
        for(int i=0;i<4;i++)
        {
            Vector3f original=(i==3?tip(side):pivot(side,i+1)).sub(pivot(side,i));
            Vector3f wanted=new Vector3f(direction).mul((float)Math.cos(bend*i-offset)).fma((float)Math.sin(bend*i-offset),lateral);
            Vector3f current=prefix.transformDirection(original).normalize();var turn=new Quaternionf().rotationTo(current,wanted);
            var parent=prefix.getUnnormalizedRotation(new Quaternionf()).normalize();joints[i].set(new Quaternionf(parent).conjugate().mul(turn).mul(parent)).normalize();
            var p=pivot(side,i);prefix.translate(p).rotate(joints[i]).translate(new Vector3f(p).negate());
        }
        float drive=smooth((age-12)/10)*(1-smooth((age-40)/24));
        for(int i=0;i<4;i++)joints[i].set(new Quaternionf().rotationX(i==0?1.15F*groundWeight(age):0).slerp(joints[i],drive)).normalize();
        GROUND_CACHE.put(actor,new GroundFrame(age,partial,side,origin,yaw,aim,joints));return joints;
    }
    public static Vector3f rotation(ShamshelEntity actor,int side,int segment,float age,float partial)
    {
        if(actor.sweepMode()!=GROUND||age<0)return rotation(side,segment,actor.sweepSide(),actor.sweepMode(),age,actor.level().getGameTime()+(double)partial);
        // The other real chain chambers as the body dives; leaving it idle would drag its visible tip through the street.
        if(side!=actor.sweepSide())return new Vector3f(segment==0?1.15F*groundWeight(age):0,0,0);
        var m=new Matrix4f().rotation(groundRotations(actor,age,partial)[segment]);
        float y=(float)Math.asin(Mth.clamp(-m.m02(),-1,1));
        if(Math.abs(Math.cos(y))<1e-6)return new Vector3f(0,y,(float)Math.atan2(-m.m10(),m.m11()));
        return new Vector3f((float)Math.atan2(m.m12(),m.m22()),y,(float)Math.atan2(m.m01(),m.m00()));
    }
    public static List<Vec3> points(ShamshelEntity actor, float age, float partial)
    {
        int side=actor.sweepSide();
        var matrix=bodyMatrix(actor,age,partial);
        List<Vec3> points=new ArrayList<>();
        for(int i=0;i<4;i++)
        {
            Vector3f p=pivot(side,i); points.add(new Vec3(matrix.transformPosition(new Vector3f(p))));
            rotate(matrix,p,rotation(actor,side,i,age,partial));
        }
        points.add(new Vec3(matrix.transformPosition(tip(side))));
        return points;
    }
    private ShamshelWhipMotion() {}
}

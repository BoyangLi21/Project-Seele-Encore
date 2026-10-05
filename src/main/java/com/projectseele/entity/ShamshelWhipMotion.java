package com.projectseele.entity;

import net.minecraft.util.Mth;
import net.minecraft.world.phys.Vec3;
import org.joml.Matrix4f;
import org.joml.Vector3f;
import java.util.*;

/** Measured rig pivots; one FK curve drives both visible whips and server contacts. */
public final class ShamshelWhipMotion
{
    public static final int CYCLE = 44, CONTACT_START = 12, CONTACT_END = 23;
    public static int contactStart(int mode){return mode==1?19:mode==2?17:12;}
    public static int contactEnd(int mode){return mode==0?23:28;}
    public static int cycle(int mode){return mode==0?40:44;}
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
    public static float bodyPitch(int mode,float age){return (mode==1?.11F-.20F*smooth((age-16)/8):.035F-.085F*smooth((age-(contactStart(mode)-1))/9))*envelope(mode,age);}
    public static float bodyYaw(int side,int mode,float age){return (mode==1?0:side*(mode==2?-1:1)*(.07F-.14F*smooth((age-(contactStart(mode)-1))/9)))*envelope(mode,age);}
    private static Vector3f pivot(int side, int index)
    {
        float[] p=PIVOTS[index]; return new Vector3f(-side*p[0],p[1],p[2]).div(16);
    }
    private static void rotate(Matrix4f m, Vector3f pivot, Vector3f r)
    { m.translate(pivot).rotateZ(r.z).rotateY(r.y).rotateX(r.x).translate(-pivot.x,-pivot.y,-pivot.z); }
    public static List<Vec3> points(ShamshelEntity actor, float age, float partial)
    {
        int side=actor.sweepSide();
        Vec3 origin=actor.level().isClientSide?actor.getPosition(partial):actor.position();
        float yaw=actor.isSweeping()?actor.sweepYaw():(actor.level().isClientSide?Mth.rotLerp(partial,actor.yBodyRotO,actor.yBodyRot):actor.yBodyRot);
        var matrix=new Matrix4f().translation(origin.toVector3f()).rotateY((float)Math.toRadians(180-yaw)).scale(5);
        rotate(matrix,new Vector3f(0,93.822528F/16,0),new Vector3f(bodyPitch(actor.sweepMode(),age),bodyYaw(side,actor.sweepMode(),age),0));
        List<Vec3> points=new ArrayList<>();
        for(int i=0;i<4;i++)
        {
            Vector3f p=pivot(side,i); points.add(new Vec3(matrix.transformPosition(new Vector3f(p))));
            rotate(matrix,p,rotation(side,i,side,actor.sweepMode(),age,actor.level().getGameTime()+(double)partial));
        }
        points.add(new Vec3(matrix.transformPosition(new Vector3f(-side*65,20,-78).div(16))));
        return points;
    }
    private ShamshelWhipMotion() {}
}

package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Real frozen skin contacts, rather than six arbitrary bone-pivot offsets.
 * Each closed 12-sided jaw has a source vertex edge on that skin point. */
public final class NervAirCradleContactsR52
{
    public record Contact(String bone,Vec3 skin,Vec3 centre,Vec3 axis){}
    private static final List<String> BONES=List.of("arm_l","arm_r","leg_l","leg_r","shin_l","shin_r");
    public static List<Contact> evaluate(EvaOriginalMeshGeometryR52.Geometry geometry,List<Vec3> desired)
    {
        if(desired.size()!=6)throw new IllegalArgumentException("Six actual frozen body contact references required");var points=new ArrayList<Vec3>();var normals=new ArrayList<Vec3>();
        for(int i=0;i<6;i++)
        {
            double distance=Double.POSITIVE_INFINITY;Vec3 nearest=null,normal=null;String bone=BONES.get(i);
            for(var part:geometry.parts())if(part.bone().equals(bone))
            {
                double[] xyz=part.triangles();for(int n=0;n<xyz.length;n+=9){var a=point(xyz,n);var b=point(xyz,n+3);var c=point(xyz,n+6);var q=b.subtract(a).cross(c.subtract(a));if(q.lengthSqr()<1e-20)continue;var at=closest(desired.get(i),a,b,c);double d=at.distanceToSqr(desired.get(i));if(d<distance){distance=d;nearest=at;normal=q.normalize();if(normal.dot(desired.get(i).subtract(at))<0)normal=normal.scale(-1);}}
            }
            if(nearest==null)throw new IllegalStateException("Actual frozen contact surface absent: "+bone);points.add(nearest);normals.add(normal);
        }
        var result=new ArrayList<Contact>();for(int pair=0;pair<3;pair++)
        {
            var axis=points.get(pair*2+1).subtract(points.get(pair*2)).normalize();if(axis.lengthSqr()<.99)throw new IllegalStateException("Actual cradle side contacts coincide");
            var x=axis.cross(Math.abs(axis.y)<.95?new Vec3(0,1,0):new Vec3(1,0,0)).normalize();var y=axis.cross(x).normalize();
            for(int side=0;side<2;side++)
            {
                int index=pair*2+side;Vec3 radial=null;double best=Double.NEGATIVE_INFINITY;for(int n=0;n<12;n++){var r=x.scale(Math.cos(n*Math.PI/6)).add(y.scale(Math.sin(n*Math.PI/6)));double d=r.dot(normals.get(index).scale(-1));if(d>best){best=d;radial=r;}}
                result.add(new Contact(BONES.get(index),points.get(index),points.get(index).subtract(radial.scale(.85)),axis));
            }
        }
        return List.copyOf(result);
    }
    private static Vec3 point(double[] a,int n){return new Vec3(a[n],a[n+1],a[n+2]);}
    public static Vec3 closest(Vec3 p,Vec3 a,Vec3 b,Vec3 c)
    {
        var ab=b.subtract(a);var ac=c.subtract(a);var ap=p.subtract(a);double d1=ab.dot(ap),d2=ac.dot(ap);if(d1<=0&&d2<=0)return a;
        var bp=p.subtract(b);double d3=ab.dot(bp),d4=ac.dot(bp);if(d3>=0&&d4<=d3)return b;
        double vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0)return a.add(ab.scale(d1/(d1-d3)));
        var cp=p.subtract(c);double d5=ab.dot(cp),d6=ac.dot(cp);if(d6>=0&&d5<=d6)return c;
        double vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0)return a.add(ac.scale(d2/(d2-d6)));
        double va=d3*d6-d5*d4;if(va<=0&&d4-d3>=0&&d5-d6>=0)return b.add(c.subtract(b).scale((d4-d3)/((d4-d3)+(d5-d6))));
        double denominator=1/(va+vb+vc);return a.add(ab.scale(vb*denominator)).add(ac.scale(vc*denominator));
    }
    private NervAirCradleContactsR52(){}
}

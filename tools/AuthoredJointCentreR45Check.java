import com.projectseele.physics.AuthoredJointCentreR45;
import java.nio.file.*;
import java.util.*;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Replays exported real captured-pose transition channels, independent of MC. */
public final class AuthoredJointCentreR45Check
{
    static Vector3f vec(float[] v,int i){return new Vector3f(v[i],v[i+1],v[i+2]);}
    static Quaternionf quat(float[] v,int i){return new Quaternionf(v[i],v[i+1],v[i+2],v[i+3]);}
    public static void main(String[] args)throws Exception
    {
        int count=0;float worstBefore=0,worstAfter=0;
        for(String line:Files.readAllLines(Path.of(args[0])))
        {
            if(line.isBlank()||line.startsWith("#"))continue;
            String[] tokens=line.split("\\t");float[] v=new float[tokens.length];
            for(int i=0;i<v.length;i++)v[i]=Float.parseFloat(tokens[i]);
            Vector3f offset=vec(v,0);Quaternionf q=quat(v,3).slerp(quat(v,7),v[17]);
            Quaternionf preserved=new Quaternionf(q);
            Vector3f old=vec(v,11).lerp(vec(v,14),v[17]);
            Vector3f now=AuthoredJointCentreR45.translation(offset,q);
            float before=new Vector3f(old).add(q.transform(new Vector3f(offset))).distance(offset)*5;
            float after=new Vector3f(now).add(q.transform(new Vector3f(offset))).distance(offset)*5;
            if(!Float.isFinite(after)||after>1e-5F||!q.equals(preserved))
                throw new AssertionError("Joint failed or rotation mutated: "+count+" "+after);
            worstBefore=Math.max(worstBefore,before);worstAfter=Math.max(worstAfter,after);count++;
        }
        if(count<100||worstBefore<.05F)throw new AssertionError("Fixture did not reproduce the actual class of failure");
        System.out.println("PASS actual captured transition samples="+count+" old_max_gap_world_m="+worstBefore+
                " corrected_max_gap_world_m="+worstAfter+" native=false art=false");
    }
}

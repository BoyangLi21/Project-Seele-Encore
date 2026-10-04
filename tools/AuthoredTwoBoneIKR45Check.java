import com.projectseele.physics.AuthoredTwoBoneIKR45;
import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Isolated geometric contract: no world or animation approval is inferred. */
public final class AuthoredTwoBoneIKR45Check
{
    static int checks;
    static void near(float value,float expected,float tolerance,String message)
    {if(!Float.isFinite(value)||Math.abs(value-expected)>tolerance)throw new AssertionError(message+": "+value+" != "+expected);checks++;}
    public static void main(String[] args)
    {
        for(int pose=0;pose<24;pose++)
        {
            Quaternionf rotation=new Quaternionf().rotationXYZ(pose*.13F,pose*.07F,-pose*.11F);
            Vector3f origin=new Vector3f(1,2,3);
            Vector3f middle=rotation.transform(new Vector3f(0,-3,1)).add(origin);
            Vector3f end=rotation.transform(new Vector3f(0,-5,-1)).add(origin);
            Vector3f fallback=rotation.transform(new Vector3f(0,0,1));
            var unchanged=AuthoredTwoBoneIKR45.solve(origin,middle,end,new Vector3f(end),fallback);
            near(unchanged.middle().distance(middle),0,0,"Unchanged target moved authored knee");
            near(unchanged.end().distance(end),0,0,"Unchanged target moved authored ankle");
            near(unchanged.upperSwing().angle(),0,0,"Unchanged target twisted thigh");
            near(unchanged.lowerSwing().angle(),0,0,"Unchanged target twisted shin");
            Vector3f requested=new Vector3f(end).add(.15F,-.04F,.12F);
            var result=AuthoredTwoBoneIKR45.solve(origin,middle,end,requested,fallback);
            near(result.middle().distance(origin),middle.distance(origin),2e-5F,"Upper bone stretched");
            near(result.end().distance(result.middle()),end.distance(middle),2e-5F,"Lower bone stretched");
            near(result.end().distance(requested),0,2e-5F,"Reachable target missed");
            Vector3f reconstructedMiddle=result.upperSwing().transform(new Vector3f(middle).sub(origin)).add(origin);
            Vector3f reconstructedEnd=result.lowerSwing().transform(new Vector3f(end).sub(middle)).add(reconstructedMiddle);
            near(reconstructedMiddle.distance(result.middle()),0,2e-5F,"Thigh rotation did not reconstruct solved knee");
            near(reconstructedEnd.distance(result.end()),0,2e-5F,"Shin rotation did not reconstruct solved ankle");
            Vector3f pole=rotation.transform(new Vector3f(2,-2,1)).add(origin);
            var blended=AuthoredTwoBoneIKR45.solveWithPole(origin,middle,end,requested,pole,fallback);
            near(blended.middle().distance(origin),middle.distance(origin),2e-5F,"Pole blend stretched upper limb");
            near(blended.end().distance(blended.middle()),end.distance(middle),2e-5F,"Pole blend stretched lower limb");
            near(blended.end().distance(requested),0,2e-5F,"Pole blend lost reachable endpoint");
            Vector3f axis=new Vector3f(requested).sub(origin).normalize();
            Vector3f wanted=new Vector3f(pole).sub(origin);wanted.fma(-wanted.dot(axis),axis).normalize();
            Vector3f actual=new Vector3f(blended.middle()).sub(origin);actual.fma(-actual.dot(axis),axis).normalize();
            near(wanted.dot(actual),1,2e-5F,"Pole blend reversed authored knee/elbow guide");
        }
        var unreachable=AuthoredTwoBoneIKR45.solve(new Vector3f(),new Vector3f(0,2,0),new Vector3f(1,3,0),new Vector3f(100,0,0),new Vector3f(0,1,0));
        near(unreachable.end().length(),2+(float)Math.sqrt(2)-1e-5F,2e-5F,"Unreachable goal stretched whole limb");
        System.out.println("PASS authored two-bone geometric checks="+checks+" native=false art=false");
    }
}

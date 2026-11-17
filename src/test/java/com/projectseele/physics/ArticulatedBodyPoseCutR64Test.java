package com.projectseele.physics;

import com.google.gson.JsonParser;
import java.util.LinkedHashMap;
import java.util.Map;
import org.joml.Matrix4f;
import org.joml.Vector3f;

/**
 * A fallen body starts at the speed its pose changed by, but not where that change is the cut from one move to
 * the next: a side kick begun the tick before stands five blocks aside of the frame it follows, and read as speed
 * that threw a Unit 135 blocks.
 */
public final class ArticulatedBodyPoseCutR64Test
{
    private static final String BODY="""
            {"bodies":[
              {"name":"torso_upper","shape":"box","size":[0.3,0.5,0.2],"mass":10,"parent":null,
               "bind":[1,0,0,0, 0,1,0,2, 0,0,1,0, 0,0,0,1]},
              {"name":"arm_l","shape":"capsule","size":[0.1,0.5],"mass":2,"parent":"torso_upper","cone":[0.5,0.5,0.5],
               "joint":[1,0,0,0.4, 0,1,0,2.4, 0,0,1,0, 0,0,0,1],
               "bind":[1,0,0,0.5, 0,1,0,2, 0,0,1,0, 0,0,0,1]}
            ]}""";

    private static void check(boolean condition,String reason)
    {
        if(!condition)throw new AssertionError(reason);
    }

    /** The mass centre's speed along x after a start from a pose that stood {@code shift} units back, 0.05 s before. */
    private static float[] start(float shift,Vector3f actor)
    {
        Map<String,Matrix4f> now=new LinkedHashMap<>(),before=new LinkedHashMap<>();
        for(String name:new String[]{"torso_upper","arm_l"})
        {
            now.put(name,new Matrix4f());before.put(name,new Matrix4f().translation(-shift,0,0));
        }
        try(var body=new ArticulatedBody(JsonParser.parseString(BODY).getAsJsonObject(),now))
        {
            float[] carried=body.motionFromPose(before,.05F,actor);var centre=body.massCentreVelocity();
            check(Math.abs(centre.y)<1e-3F&&Math.abs(centre.z)<1e-3F,"the mass centre left the line of the shift: "+centre);
            return new float[]{centre.x,carried==null?Float.NaN:carried[0],carried==null?Float.NaN:carried[1]};
        }
    }

    private static void near(float actual,float wanted,String what)
    {
        check(Math.abs(actual-wanted)<.02F,what+": "+actual+", wanted "+wanted);
    }

    public static void main(String[] args)
    {
        Vector3f still=new Vector3f();
        // The pose went 1 unit a second and the actor stood: under the limit, believed whole.
        float[] r=start(.05F,still);near(r[0],1,"pose carry of 1 unit a second");near(r[1],1,"beyond the actor");near(r[2],1,"kept");
        // The actor itself went that fast: nothing is the pose's doing.
        r=start(.05F,new Vector3f(1,0,0));near(r[0],1,"the actor's own going");near(r[1],0,"beyond the actor");
        // Five units a second out of a standing actor: a cut, no speed at all.
        r=start(.25F,still);near(r[0],0,"a cut of 5 units a second");near(r[2],0,"kept");
        // The same pose change under an actor going 4: one unit a second is the pose's, and believed.
        r=start(.25F,new Vector3f(4,0,0));near(r[0],5,"an actor going 4 and a pose carrying 1");near(r[2],1,"kept");
        // Half way between the two limits half of what the pose adds is kept.
        float middle=(ArticulatedBody.POSE_CARRY_R64+ArticulatedBody.POSE_CUT_R64)/2;
        r=start(middle*.05F,still);near(r[2],.5F,"kept half way");near(r[0],middle/2,"speed half way");
        // No actor given: as before, every part at the speed its pose changed by, 5 at most.
        r=start(.25F,null);near(r[0],5,"without an actor");
        r=start(.5F,null);near(r[0],5,"the old limit of 5 a part");
    }
}

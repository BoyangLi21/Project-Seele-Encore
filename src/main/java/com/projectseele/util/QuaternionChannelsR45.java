package com.projectseele.util;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/** One ZYX conversion for rendering and persistent body pose handoffs. */
public final class QuaternionChannelsR45
{
    public static Vector3f euler(Quaternionf q)
    {
        double length=Math.sqrt((double)q.x*q.x+(double)q.y*q.y+(double)q.z*q.z+(double)q.w*q.w);
        if(!(length>0)||!Double.isFinite(length))throw new IllegalArgumentException("Invalid bone quaternion");
        double x=q.x/length,y=q.y/length,z=q.z/length,w=q.w/length;
        double sinY=Math.max(-1,Math.min(1,2*(w*y-z*x)));
        if(Math.abs(sinY)>1-1e-8)
            return new Vector3f(0,(float)Math.copySign(Math.PI/2,sinY),(float)Math.atan2(2*(w*z-x*y),1-2*(x*x+z*z)));
        return new Vector3f((float)Math.atan2(2*(w*x+y*z),1-2*(x*x+y*y)),
                (float)Math.asin(sinY),(float)Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)));
    }
    private QuaternionChannelsR45(){}
}

package com.projectseele.physics;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Keeps a measured hinge centre fixed under its sampled local rotation. */
public final class AuthoredJointCentreR45
{
    public static Vector3f translation(Vector3f offset,Quaternionf rotation)
    {
        return new Vector3f(offset).sub(rotation.transform(new Vector3f(offset)));
    }

    private AuthoredJointCentreR45() { }
}

package com.projectseele.client.render;

import org.joml.Quaternionf;
import org.joml.Vector3f;

/** Quaternion to Gecko's Rz * Ry * Rx channels, including a vertical Y axis. */
final class QuaternionChannels
{
    static Vector3f euler(Quaternionf q)
    {
        return com.projectseele.util.QuaternionChannelsR45.euler(q);
    }
    private QuaternionChannels(){}
}

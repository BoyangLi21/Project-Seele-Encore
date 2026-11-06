package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import net.minecraft.world.phys.Vec3;

/** Exact approved rigid migration of fixed original steel, used by server and client. */
public final class NervLegacyDeepFrameR53
{
    public static final String SOURCE="mesh/legacy_deep_frame_r53.json";
    private static Vec3 offset;
    public static synchronized Vec3 translation()throws IOException
    {
        if(offset!=null)return offset;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        var j=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
        if(!j.get("schema").getAsString().equals("projectseele.r53.original-assembly-rigid-deep-frame.v1"))throw new IllegalStateException("Explicit rigid deep frame schema required");
        var a=j.getAsJsonArray("translation");offset=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());if(!offset.equals(new Vec3(0,-384,0)))throw new IllegalStateException("Root approved rigid deep translation required");return offset;
    }
    public static RigidTransform fixedFrame(RigidTransform source)throws IOException
    {return new RigidTransform(source.translation().add(translation()),source.qx(),source.qy(),source.qz(),source.qw());}
    private NervLegacyDeepFrameR53(){}
}

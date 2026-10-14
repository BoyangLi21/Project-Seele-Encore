package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Exact approved rigid migration of fixed original steel, used by server and client. */
public final class NervLegacyDeepFrameR53
{
    public static final String SOURCE="mesh/legacy_deep_frame_r53.json",SOURCE_SHA="ecf4c5d7886be9c06b0f100957a8c82c109855b8daaa3883c8a4a8b32cedb9fa";
    private static Vec3 offset;
    public static synchronized Vec3 translation()throws IOException
    {
        if(offset!=null)return offset;var bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        try{if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)).equals(SOURCE_SHA))throw new IllegalStateException("Selected rigid deep frame changed");}catch(NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
        var j=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
        if(!j.get("schema").getAsString().equals("projectseele.r53.original-assembly-rigid-deep-frame.v1")||!j.get("original_running_source_sha256").getAsString().equals(NervLegacyCarrierRideR52.SOURCE_SHA)||!j.get("floor_overlay_sha256").getAsString().equals(NervLegacyCarrierRideR52.FLOOR_OVERLAY_SHA)||!j.get("service_overlay_sha256").getAsString().equals(NervLegacyServiceBypassR52.SOURCE_SHA)||!j.get("level_overlay_sha256").getAsString().equals(NervLegacyCompactLevelR52.SOURCE_SHA))throw new IllegalStateException("Exact original and all independent overlays required for rigid migration");
        var a=j.getAsJsonArray("translation");offset=new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());if(!offset.equals(new Vec3(0,-384,0)))throw new IllegalStateException("Root approved rigid deep translation required");return offset;
    }
    public static RigidTransform fixedFrame(RigidTransform source)throws IOException
    {return new RigidTransform(source.translation().add(translation()),source.qx(),source.qy(),source.qz(),source.qw());}
    private NervLegacyDeepFrameR53(){}
}

package com.projectseele.world;

import java.util.*;

/** Matching original texture plus the shared primitive geometry contract on client and server. */
public final class RamielRemoteResourcesR52
{
    public static final String TEXTURE="assets/projectseele/textures/entity/ramiel.png";
    public static String hash(byte[] bytes)
    {
        try{var digest=java.security.MessageDigest.getInstance("SHA-256");digest.update("projectseele:ramiel_remote_r45_v1|octahedron8.25|core4.25|dimension-scale-r52".getBytes(java.nio.charset.StandardCharsets.UTF_8));return HexFormat.of().formatHex(digest.digest(bytes));}
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    public static Optional<String> classpathHash()
    {try(var input=RamielRemoteResourcesR52.class.getResourceAsStream("/"+TEXTURE)){return input==null?Optional.empty():Optional.of(hash(input.readAllBytes()));}catch(java.io.IOException error){return Optional.empty();}}
    private RamielRemoteResourcesR52(){}
}

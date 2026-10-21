package com.projectseele.world;

import java.util.*;

/** Matching selected geometry/materials on client and server, including the built-in fallback. */
public final class RamielRemoteResourcesR52
{
    public static final String TEXTURE="assets/projectseele/textures/entity/ramiel.png";
    private static final String ROOT="assets/projectseele/";
    private static final String SELECTION=ROOT+"eva/ramiel_source_r53_sources.json";
    @FunctionalInterface
    public interface Reader { byte[] read(String path) throws java.io.IOException; }
    public static String hash(byte[] bytes)
    {
        try{var digest=java.security.MessageDigest.getInstance("SHA-256");digest.update("projectseele:ramiel_remote_r45_v1|octahedron8.25|core4.25|dimension-scale-r52".getBytes(java.nio.charset.StandardCharsets.UTF_8));return HexFormat.of().formatHex(digest.digest(bytes));}
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    public static Optional<String> classpathHash()
    {
        return resourceHash(path -> {
            try(var input=RamielRemoteResourcesR52.class.getResourceAsStream("/"+path))
            {return input==null?null:input.readAllBytes();}
        });
    }
    public static Optional<String> resourceHash(Reader reader)
    {
        try
        {
            byte[] selection=reader.read(SELECTION);
            if(selection==null)
            {
                byte[] texture=reader.read(TEXTURE);
                return texture==null?Optional.empty():Optional.of(hash(texture));
            }
            var manifest=com.google.gson.JsonParser.parseString(new String(selection,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            if(!"projectseele.r53.ramiel-selection.v1".equals(manifest.get("schema").getAsString()))return Optional.empty();
            var entries=manifest.getAsJsonObject("resources");
            if(!entries.has("mesh/ramiel_source_r53.json"))return Optional.empty();
            var digest=java.security.MessageDigest.getInstance("SHA-256");
            for(var entry:entries.entrySet())
            {
                String path=entry.getKey();
                if(path.startsWith("/")||path.contains("..")||path.contains("\\"))return Optional.empty();
                byte[] bytes=reader.read(ROOT+path);
                if(bytes==null||!HexFormat.of().formatHex(digest.digest(bytes)).equals(entry.getValue().getAsString()))return Optional.empty();
            }
            digest.update("projectseele:ramiel-source-r53-v1|".getBytes(java.nio.charset.StandardCharsets.UTF_8));
            return Optional.of(HexFormat.of().formatHex(digest.digest(selection)));
        }
        catch(java.io.IOException|RuntimeException error){return Optional.empty();}
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    private RamielRemoteResourcesR52(){}
}

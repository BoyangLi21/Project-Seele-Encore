package com.projectseele.world;

import com.google.gson.JsonObject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.Map;

public final class RamielRemoteResourcesR53Test
{
    private static final String ROOT="assets/projectseele/";
    private static final String SELECTION=ROOT+"eva/ramiel_source_r53_sources.json";
    private static void check(boolean value,String why)
    {if(!value)throw new AssertionError(why);}
    private static byte[] bytes(String value){return value.getBytes(StandardCharsets.UTF_8);}
    private static void select(Map<String,byte[]> files)throws Exception
    {
        var entries=new JsonObject();
        for(var entry:files.entrySet())
            if(!entry.getKey().equals(SELECTION)&&!entry.getKey().equals(RamielRemoteResourcesR52.TEXTURE))
                entries.addProperty(entry.getKey().substring(ROOT.length()),HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(entry.getValue())));
        var manifest=new JsonObject();
        manifest.addProperty("schema","projectseele.r53.ramiel-selection.v1");
        manifest.add("resources",entries);files.put(SELECTION,bytes(manifest.toString()));
    }
    public static void main(String[] args)throws Exception
    {
        var files=new HashMap<String,byte[]>();
        files.put(RamielRemoteResourcesR52.TEXTURE,bytes("built-in"));
        String fallback=RamielRemoteResourcesR52.resourceHash(files::get).orElseThrow();
        check(fallback.equals(RamielRemoteResourcesR52.hash(bytes("built-in"))),"Built-in clients retain their existing contract");
        files.put(ROOT+"mesh/ramiel_source_r53.json",bytes("complete mesh fixture"));
        files.put(ROOT+"textures/entity/ramiel_source_r53_0.png",bytes("blue fixture"));
        select(files);
        String selected=RamielRemoteResourcesR52.resourceHash(files::get).orElseThrow();
        check(!fallback.equals(selected),"Source model must not acknowledge the built-in geometry hash");
        byte[] original=files.put(ROOT+"textures/entity/ramiel_source_r53_0.png",bytes("changed material"));
        check(RamielRemoteResourcesR52.resourceHash(files::get).isEmpty(),"Texture mismatch must refuse readiness");
        select(files);
        check(!selected.equals(RamielRemoteResourcesR52.resourceHash(files::get).orElseThrow()),"Approved material changes must change the contract");
        files.remove(ROOT+"textures/entity/ramiel_source_r53_0.png");
        check(RamielRemoteResourcesR52.resourceHash(files::get).isEmpty(),"Missing selected resources must not fall back silently");
        files.put(ROOT+"textures/entity/ramiel_source_r53_0.png",original);
        files.put(SELECTION,bytes("invalid JSON"));
        check(RamielRemoteResourcesR52.resourceHash(files::get).isEmpty(),"Malformed selection must refuse readiness");
        check(RamielRemoteResourcesR52.resourceHash(path->{throw new java.io.IOException("unavailable");}).isEmpty(),"Read failures must refuse readiness");
        System.out.println("Ramiel resource contract: fallback, complete selection, material mismatch/update, missing data, malformed selection and IO failure passed");
    }
    private RamielRemoteResourcesR53Test(){}
}

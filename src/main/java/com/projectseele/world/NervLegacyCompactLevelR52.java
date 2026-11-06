package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Replaces only the obsolete R52 level spans; the original inclined railway is retained. */
public final class NervLegacyCompactLevelR52
{
    public static final String SOURCE="mesh/legacy_compact_level_r52.json";
    static void apply(JsonObject original)throws IOException
    {
        byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        var overlay=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();require(overlay.get("schema").getAsString().equals("projectseele.r52.exact-compact-level-rails.v1"),"Exact original source for compact levels required");
        var expected=new HashMap<String,JsonObject>();for(var raw:original.getAsJsonArray("members")){var row=raw.getAsJsonObject();String name=row.get("part").getAsString();if(levelPart(name))expected.put(name,row);}
        var remove=new HashSet<String>();
        for(var raw:overlay.getAsJsonArray("retired_parts")){var row=raw.getAsJsonObject();String name=row.get("name").getAsString();var member=expected.get(name);require(levelPart(name)&&remove.add(name)&&member!=null&&member.get("role").equals(row.get("role"))&&member.get("frame").getAsString().equals("world")&&row.get("frame").getAsString().equals("world"),"Only exact authored obsolete level members may retire");}
        require(remove.equals(expected.keySet()),"All and only the old level spans must retire");
        var members=new JsonArray();for(var raw:original.getAsJsonArray("members"))if(!remove.contains(raw.getAsJsonObject().get("part").getAsString()))members.add(raw);for(String name:remove)original.getAsJsonObject("parts").remove(name);
        var added=new HashSet<String>();for(var raw:overlay.getAsJsonArray("components")){var row=raw.getAsJsonObject();String name=row.get("name").getAsString(),role=row.get("role").getAsString();var rgb=row.getAsJsonArray("triangles_rgb");require(name.matches("level_(actual|heads)/[0-2]/compact_[A-Za-z0-9_]+")&&added.add(name)&&!original.getAsJsonObject("parts").has(name)&&row.get("frame").getAsString().equals("world")&&role.equals(name.startsWith("level_heads/")?"static_head":"static")&&!rgb.isEmpty()&&rgb.size()%18==0,"Exact complete compact level part required");for(var value:rgb)require(Double.isFinite(value.getAsDouble()),"Finite compact level vertices required");original.getAsJsonObject("parts").add(name,rgb);var member=new JsonObject();member.addProperty("part",name);member.addProperty("role",role);member.addProperty("frame","world");members.add(member);}
        require(!added.isEmpty(),"Compact level floor, head and terminal bridge parts required");original.add("members",members);
    }
    private static boolean levelPart(String name){return name.startsWith("level_actual/")||name.startsWith("level_heads/");}
    private static void require(boolean okay,String why){if(!okay)throw new IllegalArgumentException(why);}
    private NervLegacyCompactLevelR52(){}
}

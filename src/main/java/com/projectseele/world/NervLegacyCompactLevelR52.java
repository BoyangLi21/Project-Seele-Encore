package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** Replaces only the obsolete R52 level spans; the original inclined railway is retained. */
public final class NervLegacyCompactLevelR52
{
    public static final String SOURCE="mesh/legacy_compact_level_r52.json";
    public static final String SOURCE_SHA="c47c055eaa90f97eca46a40b36439804ceaf0f50f1cb88a5fb426fbf0353d001";
    static void apply(JsonObject original)throws IOException
    {
        byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        try
        {
            var digest=MessageDigest.getInstance("SHA-256");require(SOURCE_SHA.equals(HexFormat.of().formatHex(digest.digest(bytes))),"Selected compact level rail source changed");
            var overlay=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();require(overlay.get("schema").getAsString().equals("projectseele.r52.exact-compact-level-rails.v1")&&overlay.get("original_running_source_sha256").getAsString().equals(NervLegacyCarrierRideR52.SOURCE_SHA),"Exact original source for compact levels required");
            var expected=new HashMap<String,JsonObject>();for(var raw:original.getAsJsonArray("members")){var row=raw.getAsJsonObject();String name=row.get("part").getAsString();if(levelPart(name))expected.put(name,row);}
            var remove=new HashSet<String>();var buffer=ByteBuffer.allocate(8);
            for(var raw:overlay.getAsJsonArray("retired_parts")){var row=raw.getAsJsonObject();String name=row.get("name").getAsString();var member=expected.get(name);require(levelPart(name)&&remove.add(name)&&member!=null&&member.get("role").equals(row.get("role"))&&member.get("frame").getAsString().equals("world")&&row.get("frame").getAsString().equals("world"),"Only exact authored obsolete level members may retire");var values=original.getAsJsonObject("parts").getAsJsonArray(name);require(values.size()==row.get("original_triangle_count").getAsInt()*18,"Original level triangle order/count changed");digest.reset();for(var value:values){buffer.clear();buffer.putDouble(value.getAsDouble());digest.update(buffer.array());}require(HexFormat.of().formatHex(digest.digest()).equals(row.get("triangles_f64be_sha256").getAsString()),"Original level vertices changed before compact replacement");}
            require(remove.size()==345&&remove.equals(expected.keySet()),"All and only the old three 57/58-piece level spans must retire");
            var members=new JsonArray();for(var raw:original.getAsJsonArray("members"))if(!remove.contains(raw.getAsJsonObject().get("part").getAsString()))members.add(raw);for(String name:remove)original.getAsJsonObject("parts").remove(name);
            var added=new HashSet<String>();for(var raw:overlay.getAsJsonArray("components")){var row=raw.getAsJsonObject();String name=row.get("name").getAsString(),role=row.get("role").getAsString();var rgb=row.getAsJsonArray("triangles_rgb");require(name.matches("level_(actual|heads)/[0-2]/compact_[A-Za-z0-9_]+")&&added.add(name)&&!original.getAsJsonObject("parts").has(name)&&row.get("frame").getAsString().equals("world")&&role.equals(name.startsWith("level_heads/")?"static_head":"static")&&!rgb.isEmpty()&&rgb.size()%18==0,"Exact complete compact level part required");for(var value:rgb)require(Double.isFinite(value.getAsDouble()),"Finite compact level vertices required");original.getAsJsonObject("parts").add(name,rgb);var member=new JsonObject();member.addProperty("part",name);member.addProperty("role",role);member.addProperty("frame","world");members.add(member);}
            require(added.size()==9,"Each original variant requires its finite floor, head and terminal bridge");original.add("members",members);
        }
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    private static boolean levelPart(String name){return name.startsWith("level_actual/")||name.startsWith("level_heads/");}
    private static void require(boolean okay,String why){if(!okay)throw new IllegalArgumentException(why);}
    private NervLegacyCompactLevelR52(){}
}

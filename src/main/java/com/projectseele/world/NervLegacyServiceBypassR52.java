package com.projectseele.world;

import com.google.gson.*;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;

/** Explicit Root service-pipe replacement, separate from the original running heads. */
public final class NervLegacyServiceBypassR52
{
    public static final String SOURCE="mesh/legacy_service_bypass_r52.json";
    public static final String SOURCE_SHA="c4fe6c5bc5f2f41db8dce7abb3090de67bc4b2d806b85f90fade1e38660bce08";
    public record WallFace(BlockPos block,String state,Vec3 point,int normalX,double halfWidth,double halfHeight,String bracket){}
    private static List<WallFace> faces;
    static synchronized void apply(JsonObject original)throws IOException
    {
        byte[] bytes=EvaOriginalMeshGeometryR52.classpathBytes(SOURCE);
        try
        {
            var digest=MessageDigest.getInstance("SHA-256");require(SOURCE_SHA.equals(HexFormat.of().formatHex(digest.digest(bytes))),"Selected service bypass source changed");
            var overlay=JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
            require(overlay.get("schema").getAsString().equals("projectseele.r52.exact-legacy-service-bypass.v1")&&overlay.get("original_running_source_sha256").getAsString().equals(NervLegacyCarrierRideR52.SOURCE_SHA)&&overlay.get("target_part").getAsString().equals("legacy_original_retained"),"Exact original service-pipe source and target required");
            var source=original.getAsJsonObject("parts").getAsJsonArray("legacy_original_retained");require(source.size()%18==0&&source.size()/18==overlay.get("original_target_triangle_count").getAsInt(),"Original retained triangle order changed");
            var remove=new HashSet<Integer>();int previous=-1;var buffer=ByteBuffer.allocate(8);digest.reset();
            for(var value:overlay.getAsJsonArray("removed_triangle_indices")){int index=value.getAsInt();require(index>previous&&index>=0&&index<source.size()/18,"Ordered exact original triangle indices required");previous=index;remove.add(index);for(int i=0;i<18;i++){buffer.clear();buffer.putDouble(source.get(index*18+i).getAsDouble());digest.update(buffer.array());}}
            require(!remove.isEmpty()&&HexFormat.of().formatHex(digest.digest()).equals(overlay.get("removed_triangles_f64be_sha256").getAsString()),"Original removed service triangles changed");
            var kept=new JsonArray();for(int i=0;i<source.size();i++)if(!remove.contains(i/18))kept.add(source.get(i));original.getAsJsonObject("parts").add("legacy_original_retained",kept);
            var names=new HashSet<String>();for(var raw:overlay.getAsJsonArray("components")){var row=raw.getAsJsonObject();String name=row.get("name").getAsString();var rgb=row.getAsJsonArray("triangles_rgb");require(name.startsWith("service_bypass/")&&names.add(name)&&!original.getAsJsonObject("parts").has(name)&&row.get("frame").getAsString().equals("world")&&row.get("role").getAsString().equals("static")&&!rgb.isEmpty()&&rgb.size()%18==0,"Complete independent actual bypass part required");for(var value:rgb)require(Double.isFinite(value.getAsDouble()),"Finite service bypass vertices required");original.getAsJsonObject("parts").add(name,rgb);var member=new JsonObject();member.addProperty("part",name);member.addProperty("role","static");member.addProperty("frame","world");original.getAsJsonArray("members").add(member);}
            var anchors=new ArrayList<WallFace>();for(var raw:overlay.getAsJsonArray("native_wall_faces")){var row=raw.getAsJsonObject();var a=row.getAsJsonArray("at");var p=row.getAsJsonArray("face_point");var n=row.getAsJsonArray("normal");var block=new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt());var point=new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());int normal=n.get(0).getAsInt();double hw=row.get("half_width").getAsDouble(),hh=row.get("half_height").getAsDouble();String bracket=row.get("bracket").getAsString(),state=row.get("state").getAsString();require(state.equals("projectseele:nerv_structural_panel")&&(normal==1||normal==-1)&&n.get(1).getAsDouble()==0&&n.get(2).getAsDouble()==0&&hw>0&&hh>0&&hw<=.5&&hh<=.5&&Double.isFinite(point.lengthSqr()+hw+hh)&&point.x==block.getX()+(normal>0?1:0)&&point.y-hh>=block.getY()&&point.y+hh<=block.getY()+1&&point.z-hw>=block.getZ()&&point.z+hw<=block.getZ()+1&&names.contains(bracket),"Complete finite external wall contact required");anchors.add(new WallFace(block,state,point,normal,hw,hh,bracket));}
            require(anchors.size()==4,"Both retained service pipes require two actual external wall supports");var delta=NervLegacyDeepFrameR53.translation();faces=anchors.stream().map(a->new WallFace(a.block().offset((int)delta.x,(int)delta.y,(int)delta.z),a.state(),a.point().add(delta),a.normalX(),a.halfWidth(),a.halfHeight(),a.bracket())).toList();
        }
        catch(java.security.NoSuchAlgorithmException impossible){throw new IllegalStateException(impossible);}
    }
    public static List<WallFace> wallFaces(){if(faces==null)throw new IllegalStateException("Selected service bypass is not loaded");return faces;}
    public static boolean nativeFacesBear(ServerLevel level)
    {
        for(var face:wallFaces())
        {
            var at=face.block();if(level.getChunkSource().getChunkNow(at.getX()>>4,at.getZ()>>4)==null||!net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(level.getBlockState(at)).equals(face.state()))return false;boolean covered=false;
            for(var local:level.getBlockState(at).getCollisionShape(level,at).toAabbs()){var box=local.move(at);double plane=face.normalX()>0?box.maxX:box.minX;if(Math.abs(plane-face.point().x)<.0002&&box.minY<=face.point().y-face.halfHeight()&&box.maxY>=face.point().y+face.halfHeight()&&box.minZ<=face.point().z-face.halfWidth()&&box.maxZ>=face.point().z+face.halfWidth()){covered=true;break;}}
            if(!covered)return false;
        }
        return true;
    }
    private static void require(boolean okay,String why){if(!okay)throw new IllegalArgumentException(why);}
    private NervLegacyServiceBypassR52(){}
}

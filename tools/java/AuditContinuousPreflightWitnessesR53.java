package com.projectseele.world;

import com.google.gson.*;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.zip.GZIPInputStream;
import net.minecraft.world.phys.*;

/** Real exported actor/floor negative witnesses. Never loads or writes a native world. */
public final class AuditContinuousPreflightWitnessesR53
{
    private static int checks;
    private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
    private static JsonObject read(Path path)throws IOException{return JsonParser.parseString(Files.readString(path)).getAsJsonObject();}
    private static Vec3 point(JsonArray p){return new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble());}
    private static Vec3 point(String source){String[] v=source.replace("(","").replace(")","").split(",");return new Vec3(Double.parseDouble(v[0].trim()),Double.parseDouble(v[1].trim()),Double.parseDouble(v[2].trim()));}
    private static RigidTransform frame(JsonObject row){return new RigidTransform(point(row.get("translation").getAsString()),row.get("qx").getAsFloat(),row.get("qy").getAsFloat(),row.get("qz").getAsFloat(),row.get("qw").getAsFloat());}
    private static NervRigidMeshSweepR52 mesh(JsonObject row)throws Exception
    {
        double[] values;try(var input=new GZIPInputStream(Files.newInputStream(Path.of(row.get("triangles_file").getAsString())));var reader=new InputStreamReader(input,StandardCharsets.UTF_8)){values=new Gson().fromJson(reader,double[].class);}
        check(values.length==row.get("triangles").getAsInt()*9,"Exported actual topology changed");var bytes=ByteBuffer.allocate(values.length*8).order(ByteOrder.BIG_ENDIAN);for(double v:values){if(!Double.isFinite(v))throw new AssertionError("Nonfinite actual vertex");bytes.putDouble(v);}
        check(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes.array())).equals(row.get("sha256_doubles_big_endian").getAsString()),"Exported actual actor mesh SHA changed");return new NervRigidMeshSweepR52(values);
    }
    public static void main(String[] args)throws Exception
    {
        if(args.length!=3)throw new IllegalArgumentException("native actor report, original carrier source mesh export, original native floor audit required");
        check(NervR50CarrierModeR53.enabled(),"Witness must cover the enabled R50 mode");
        var nativeReport=read(Path.of(args[0]));check(nativeReport.get("state_unchanged_in_server_action").getAsBoolean(),"Export changed original state");check(nativeReport.get("same_production_continuous_rejection").equals(nativeReport.get("rejection_before")),"Native replay did not reproduce original rejection");
        var hit=nativeReport.getAsJsonArray("hits").get(0).getAsJsonObject();check(hit.getAsJsonObject("actor").get("isRestraintGantry").getAsString().equals("true")&&!hit.get("actor_is_coupled_member").getAsBoolean(),"Expected stationary original constraint gantry witness");var moving=mesh(hit.getAsJsonObject("moving_mesh"));var obstacle=mesh(hit.getAsJsonObject("actor_mesh"));
        var from=frame(hit.getAsJsonObject("moving_from"));var to=frame(hit.getAsJsonObject("moving_to"));var otherFrom=frame(hit.getAsJsonObject("actor_test_from"));var otherTo=frame(hit.getAsJsonObject("actor_test_to"));double error=hit.get("outward_error").getAsDouble();var uncertainty=new Vec3(error,error,error);
        check(!moving.intersects(from,from,obstacle,otherFrom,otherFrom,.003,uncertainty),"Actual clear start witness changed");
        check(moving.intersects(from,to,obstacle,otherFrom,otherTo,.003,uncertainty),"Actual stationary constraint gantry disappeared from continuous rear sweep");
        check(moving.intersects(to,to,obstacle,otherTo,otherTo,.003,uncertainty),"Actual end-contact witness changed");
        var root=frame(nativeReport.getAsJsonObject("actual_root"));var sampleRoot=frame(hit.getAsJsonObject("root_from"));var at=new RigidTransform(from.translation().add(root.translation().subtract(sampleRoot.translation())),from.qx(),from.qy(),from.qz(),from.qw());
        check(!moving.intersects(at,at,obstacle,otherFrom,otherFrom,.003,uncertainty),"Current original position is no longer clear");
        check(moving.intersects(at,to,obstacle,otherFrom,otherTo,.003,uncertainty),"Forward span cannot detect the real gantry before committing into it");
        var floorAudit=read(Path.of(args[2]));check(floorAudit.get("hardware_sha256").getAsString().equals(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[1]))))),"Original floor witness source export changed");JsonObject floor=null;
        for(var value:floorAudit.getAsJsonArray("solid_collisions")){var row=value.getAsJsonObject();if(row.get("leg").getAsString().equals("unit1/original_carrier_rise")&&row.get("part").getAsString().equals("carrier/deck")&&row.get("metres").getAsDouble()==64){floor=row;break;}}
        if(floor==null)throw new AssertionError("Original raised-deck floor witness missing");check(floor.get("state").getAsString().equals("minecraft:iron_block"),"Floor witness must retain its native full-cube collision");
        double[] deck=null;for(var value:read(Path.of(args[1])).getAsJsonArray("parts")){var row=value.getAsJsonObject();if(!row.get("name").getAsString().equals("deck"))continue;var rgb=row.getAsJsonArray("triangles_rgb");deck=new double[rgb.size()/2];for(int i=0;i<rgb.size()/6;i++)for(int axis=0;axis<3;axis++)deck[i*3+axis]=rgb.get(i*6+axis).getAsDouble();}
        if(deck==null)throw new AssertionError("Complete original deck topology missing");var deckMesh=new NervRigidMeshSweepR52(deck);var deckRoot=new RigidTransform(point(floor.getAsJsonArray("root")),0,1,0,0);var cell=point(floor.getAsJsonArray("cell"));var floorBox=new AABB(cell,cell.add(1,1,1));
        var piece=new NervOriginalCarrierR52.Part("carrier/deck",NervOriginalCarrierR52.Role.STRUCTURE,deckMesh,deckRoot);
        check(NervOriginalCarrierR52.nativeBlockRejectionR53(List.of(piece),List.of(piece),0,b->true,b->List.of(floorBox))!=null,"R50 full raised deck must retain the actual native floor rejection");
        System.out.println("PASS R50 actual preflight negative witnesses checks="+checks+"; actor="+hit.getAsJsonObject("actor").get("uuid").getAsString()+"; raised_deck_floor="+floor.get("cell")+"; no native movement or acceptance");
    }
    private AuditContinuousPreflightWitnessesR53(){}
}

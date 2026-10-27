package com.projectseele.world;

import com.google.gson.*;
import com.google.gson.stream.JsonWriter;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.Vec3;

/** Sampled production frames for offline native-shape diagnostics. No world writes. */
public final class ExportRearRouteFramesR53
{
    private static String sha(byte[] b)throws Exception
    {return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    private static Vec3 point(JsonArray a)
    {return new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble());}
    private static void frame(JsonWriter writer,RigidTransform f)throws Exception
    {
        var p=f.translation();writer.beginArray();
        for(double v:new double[]{p.x,p.y,p.z,f.qx(),f.qy(),f.qz(),f.qw()})writer.value(v);
        writer.endArray();
    }
    public static void main(String[] args)throws Exception
    {
        byte[] hardwareBytes=Files.readAllBytes(Path.of(args[0])),sourceBytes=Files.readAllBytes(Path.of(args[1]));
        var hardware=CarrierRearGuideR53.readHardware(hardwareBytes,"uninstalled-route-diagnostic");
        var metadata=JsonParser.parseString(new String(hardwareBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        double stow=metadata.get("transfer_stow_lift_m").getAsDouble(),spacing=args.length>3?Double.parseDouble(args[3]):4;
        if(!(spacing>0)||stow>CarrierRearGuideR53.STOW_LIFT)throw new IllegalArgumentException("Bounded declared stroke and sample spacing required");
        var source=JsonParser.parseString(new String(sourceBytes,java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
        int poses=0,legs=0;
        try(var writer=new JsonWriter(Files.newBufferedWriter(Path.of(args[2]))))
        {
            writer.beginObject();writer.name("schema").value("projectseele.r53.rear-route-native-frames.v1");
            writer.name("world_written").value(false);writer.name("continuous_proof").value(false);
            writer.name("kinematics").value("CarrierRearGuideR53.Hardware.partsAt");
            writer.name("hardware_sha256").value(sha(hardwareBytes));writer.name("native_samples_sha256").value(sha(sourceBytes));
            writer.name("sample_spacing_metres").value(spacing);writer.name("transfer_stow_lift_metres").value(stow);
            writer.name("parts").beginArray();
            for(var p:hardware.parts()){writer.beginObject();writer.name("name").value(p.name());writer.name("frame").value(p.frame());writer.name("role").value(p.role());writer.endObject();}
            writer.endArray();writer.name("poses").beginArray();
            for(var raw:source.getAsJsonArray("legs"))
            {
                legs++;var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();
                double lift=id.contains("/exit")?0:stow,next=0;var rows=leg.getAsJsonArray("samples");
                for(int n=0;n<rows.size();n++)
                {
                    var row=rows.get(n).getAsJsonObject();double metres=row.get("metres").getAsDouble();
                    if(metres+1e-9<next&&n!=rows.size()-1)continue;next=metres+spacing;poses++;
                    var q=row.getAsJsonArray("rotation");var root=new RigidTransform(point(row.getAsJsonArray("root")),
                        q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());
                    var parts=hardware.partsAt(root,1,point(row.getAsJsonArray("tangent")),0,lift);
                    writer.beginObject();writer.name("leg").value(id);writer.name("metres").value(metres);writer.name("lift").value(lift);
                    writer.name("root");frame(writer,root);writer.name("frames").beginArray();
                    for(var p:parts)frame(writer,p.frame());writer.endArray();writer.endObject();
                }
            }
            writer.endArray();writer.name("leg_count").value(legs);writer.name("pose_count").value(poses);writer.endObject();
        }
        System.out.println("legs="+legs+" poses="+poses+" parts="+hardware.parts().size());
    }
    private ExportRearRouteFramesR53(){}
}

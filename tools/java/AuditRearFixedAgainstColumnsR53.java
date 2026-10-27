package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.GZIPInputStream;
import java.io.InputStreamReader;
import net.minecraft.world.phys.Vec3;

/** Static complete guide-source versus retained actual fixed-column triangles. */
public final class AuditRearFixedAgainstColumnsR53
{
    private static RigidTransform frame(JsonObject o)
    {var p=o.getAsJsonArray("position");var q=o.getAsJsonArray("quaternion");return new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    public static void main(String[] args)throws Exception
    {
        var nativeReport=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var hit=nativeReport.getAsJsonArray("hits").get(0).getAsJsonObject();var meshPath=Path.of(hit.getAsJsonObject("actor_mesh").get("triangles_file").getAsString());double[] xyz;
        try(var gz=new GZIPInputStream(Files.newInputStream(meshPath));var reader=new InputStreamReader(gz,java.nio.charset.StandardCharsets.UTF_8)){var array=JsonParser.parseReader(reader).getAsJsonArray();xyz=new double[array.size()];for(int i=0;i<xyz.length;i++)xyz[i]=array.get(i).getAsDouble();}
        if(xyz.length!=4912*9)throw new IllegalStateException("Full original fixed columns required");var columns=new NervRigidMeshSweepR52(xyz);
        var sha=java.security.MessageDigest.getInstance("SHA-256");var bytes=java.nio.ByteBuffer.allocate(8);for(double d:xyz){bytes.clear();bytes.putDouble(d);sha.update(bytes.array());}if(!HexFormat.of().formatHex(sha.digest()).equals(hit.getAsJsonObject("actor_mesh").get("sha256_doubles_big_endian").getAsString()))throw new IllegalStateException("Native column mesh changed");
        var owner=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();var frames=new TreeMap<Integer,RigidTransform>();for(var raw:owner.getAsJsonArray("units")){var u=raw.getAsJsonObject();frames.put(u.get("variant").getAsInt(),frame(u.getAsJsonObject("gantry").getAsJsonObject("frame")));}
        var receipt=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();var failures=new ArrayList<Object>();int[] count={0,0};
        try(var stream=Files.newInputStream(Path.of(receipt.get("source").getAsString())))
        {NervUprightGuidewayR52.readVisualR52(stream,receipt.get("sha256").getAsString(),p->{count[0]++;var s=p.steel();var bounds=s.mesh().envelope(s.frame(),s.frame());for(var row:frames.entrySet()){var f=row.getValue();if(!bounds.intersects(columns.envelope(f,f)))continue;count[1]++;if(s.mesh().intersects(s.frame(),s.frame(),columns,f,f,.003,Vec3.ZERO))failures.add(Map.of("variant",row.getKey(),"rail",p.name(),"leg",p.leg(),"component",p.component(),"rail_bounds",bounds));}},a->{});}
        var result=Map.of("world_written",false,"installed",false,"native_actor",hit.getAsJsonObject("actor").get("uuid").getAsString(),"native_source_triangles",4912,"rail_sha256",receipt.get("sha256").getAsString(),"pieces_scanned",count[0],"exact_pair_tests",count[1],"intersections",failures);
        Files.writeString(Path.of(args[3]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println("pieces="+count[0]+" pairs="+count[1]+" intersections="+failures.size());
    }
}

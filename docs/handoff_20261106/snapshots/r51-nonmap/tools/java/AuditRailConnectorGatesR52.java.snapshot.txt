package com.projectseele.world;
import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** Actual source door curves against Root's finite candidate foundation cubes. */
public final class AuditRailConnectorGatesR52
{
    record Gate(String id,RigidTransform frame,NervSiloHatchGeometryR52 silo,NervHangarGateGeometryR52 hangar,AABB bounds)
    {boolean hit(AABB b){return silo!=null?silo.intersects(frame,0,1,b):hangar.intersects(frame,0,1,b);}}
    static RigidTransform frame(JsonObject j)
    {var p=j.getAsJsonArray("position");var q=j.getAsJsonArray("quaternion");return RigidTransform.of(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()));}
    public static void main(String[] args)throws Exception
    {
        var raw=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var gates=new ArrayList<Gate>();
        for(var value:raw.getAsJsonArray("gates"))
        {
            var j=value.getAsJsonObject();var f=frame(j.getAsJsonObject("frame"));NervSiloHatchGeometryR52 s=null;NervHangarGateGeometryR52 h=null;List<AABB> envelopes;
            if(j.get("kind").getAsString().equals("SILO"))
            {var a=j.getAsJsonObject("silo_hatch");s=NervSiloHatchGeometryR52.loadClasspath(new SiloHatchMechanism.Spec(a.get("opening_x").getAsFloat(),a.get("opening_z").getAsFloat(),a.get("open_ticks").getAsInt(),a.get("close_ticks").getAsInt(),a.get("separation_sign").getAsInt(),a.get("beam_bottom").getAsDouble(),a.get("service_column_ports").getAsBoolean()));envelopes=s.envelopes(f,0,1);}
            else
            {var a=j.getAsJsonObject("hangar_stack");h=NervHangarGateGeometryR52.loadClasspath(new NervHangarGateGeometryR52.Spec(j.get("width").getAsFloat(),j.get("height").getAsFloat(),a.get("open_ticks").getAsInt(),a.get("close_ticks").getAsInt()));envelopes=h.envelopes(f,0,1);}
            AABB whole=null;for(var b:envelopes)whole=whole==null?b:whole.minmax(b);gates.add(new Gate(j.get("resource").getAsString(),f,s,h,whole));
        }
        var plan=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();var hits=new ArrayList<Object>();var clear=new ArrayList<Object>();int pairs=0;
        for(var row:plan.getAsJsonArray("candidate_cells"))
        {
            var p=row.getAsJsonArray();int x=p.get(0).getAsInt(),y=p.get(1).getAsInt(),z=p.get(2).getAsInt();var b=new AABB(x,y,z,x+1,y+1,z+1);var at=new int[]{x,y,z};var conflict=new ArrayList<String>();
            for(var g:gates)if(g.bounds.intersects(b)){pairs++;if(g.hit(b))conflict.add(g.id);}
            if(conflict.isEmpty())clear.add(at);else hits.add(Map.of("cell",at,"gates",conflict));
        }
        var out=new LinkedHashMap<String,Object>();out.put("world_written",false);out.put("native_verified",false);out.put("gate_count",gates.size());out.put("actual_curve_pairs",pairs);out.put("clear_cells",clear);out.put("conflicting_cells",hits);
        out.put("candidate_sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[1])))));
        out.put("gates_sha256",HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0])))));
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(out));System.out.println("gates="+gates.size()+" candidates="+(clear.size()+hits.size())+" clear="+clear.size()+" conflict="+hits.size()+" pairs="+pairs);
    }
}

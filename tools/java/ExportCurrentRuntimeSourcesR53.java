package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.SiloHatchMechanism;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import net.minecraft.world.phys.*;

/** Current production parsers and actual source bounds. Does not create a Level. */
public final class ExportCurrentRuntimeSourcesR53
{
    private static final Gson G = new GsonBuilder().setPrettyPrinting().create();
    private static String sha(byte[] b)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));}
    private static String resource(String name)throws Exception{return sha(EvaOriginalMeshGeometryR52.classpathBytes(name));}
    private static JsonObject read(String p)throws Exception{return JsonParser.parseString(Files.readString(Path.of(p))).getAsJsonObject();}
    private static RigidTransform frame(JsonObject j){var p=j.getAsJsonArray("position");var q=j.getAsJsonArray("quaternion");return new RigidTransform(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat());}
    private static double[] box(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
    private static AABB union(AABB a,AABB b){return a==null?b:a.minmax(b);}
    public static void main(String[] args)throws Exception
    {
        if(args.length!=6)throw new IllegalArgumentException("directory guide-source units gates repo output-folder required");
        var directory=NervRouteDirectoryR52.parse(read(args[0]));var out=Path.of(args[5]);Files.createDirectories(out);
        byte[] steel=Files.readAllBytes(Path.of(args[1]));String guideSHA=sha(steel);
        if(!guideSHA.equals(resource("facility/r52_upright_guideway_paths.json")))throw new IllegalStateException("Selected Jar guide bytes differ from explicit final source");
        NervUprightGuidewayR52.install(steel,guideSHA,directory);
        if(!NervUprightGuidewayR52.matchesDirectory(directory)||NervUprightGuidewayR52.anchors().isEmpty())throw new IllegalStateException("Actual production guide parser rejected complete current source");
        var guide=new LinkedHashMap<String,Object>();guide.put("profile","projectseele.r52.upright-captured-guideway.v1");guide.put("directory_geometry_sha256",sha(Files.readAllBytes(Path.of(args[0]))));guide.put("directory_fingerprint",directory.fingerprint());guide.put("path_source_sha256",guideSHA);guide.put("model_source_sha256",resource("mesh/upright_outer_captured_r52.json"));guide.put("head_transfer_source_sha256",resource("mesh/outer_head_transfer_r53.json"));guide.put("gate_source_sha256",sha(Files.readAllBytes(Path.of(args[3]))));guide.put("production_parser_valid",true);guide.put("actual_pieces",NervUprightGuidewayR52.pieces().size());guide.put("actual_anchors",NervUprightGuidewayR52.anchors().size());guide.put("world_written",false);guide.put("native_admission",false);Files.writeString(out.resolve("CURRENT_GUIDEWAY_REPORT.json"),G.toJson(guide));
        var gates=read(args[3]).getAsJsonArray("gates");var rows=new ArrayList<Object>();
        for(var raw:read(args[2]).getAsJsonArray("units"))
        {
            var u=raw.getAsJsonObject();int v=u.get("variant").getAsInt();JsonObject gate=null;
            for(var g:gates)if(g.getAsJsonObject().get("resource").getAsString().equals("bay_"+v+"_service_pit"))gate=g.getAsJsonObject();
            if(gate==null)throw new IllegalArgumentException("Actual current pit required");var h=gate.getAsJsonObject("silo_hatch");
            var hs=new SiloHatchMechanism.Spec(h.get("opening_x").getAsFloat(),h.get("opening_z").getAsFloat(),h.get("open_ticks").getAsInt(),h.get("close_ticks").getAsInt(),h.get("separation_sign").getAsInt(),h.get("beam_bottom").getAsDouble(),true);
            double floor=u.getAsJsonArray("carrier_support").get(0).getAsJsonObject().getAsJsonArray("position").get(1).getAsDouble()+1;
            var root=frame(u.getAsJsonObject("bay_frame"));var spec=new NervServiceFootDriveR52.Spec(v,root,frame(gate.getAsJsonObject("frame")),hs.firstTier(),floor);AABB lead=null,carrier=null;
            for(int bridge=0;bridge<=1;bridge++)for(int k=0;k<=128;k++)for(var p:NervLegacyCarrierRideR52.actualLeadPartsR52(new NervLegacyCarrierRideR52.LeadSampleR52(spec,bridge,k/128F,0)))lead=union(lead,p.mesh().envelope(p.frame(),p.frame()));
            for(int k=0;k<=128;k++)for(var p:NervOriginalCarrierR52.partsAtR52(v,root,k/128F,new Vec3(0,1,0),NervLegacyCarrierRideR52.rest()))carrier=union(carrier,p.mesh().envelope(p.frame(),p.frame()));
            if(lead==null||carrier==null)throw new IllegalStateException("Complete actual source is empty");
            // A further full actuator stroke bounds every intermediate translation.
            // This is reservation only, never a continuous collision assertion.
            rows.add(Map.of("variant",v,"source_bounds",box(lead.inflate(0,64,0)),"sampled_actual_lead_bounds",box(lead),"actual_carrier_reservation_bounds",box(carrier.inflate(0,64,0)),"source_sample_count",258,"geometry_scope","Actual current parts with full64m actuator translation padding; conservative reservation only"));
        }
        var lead=new LinkedHashMap<String,Object>();lead.put("source",NervLegacyCarrierRideR52.SOURCE_SHA);lead.put("full_source",NervOriginalCarrierR52.SOURCE_SHA);lead.put("legacy_helper_java_sha256",sha(Files.readAllBytes(Path.of(args[4]).resolve("src/main/java/com/projectseele/world/NervLegacyCarrierRideR52.java"))));lead.put("actual_source_bytes_sha256",resource(NervLegacyCarrierRideR52.SOURCE));lead.put("floor_overlay_sha256",resource("mesh/legacy_floor_recesses_r52.json"));lead.put("actual_floor_overlay_bytes_sha256",resource("mesh/legacy_floor_recesses_r52.json"));lead.put("rows",rows);lead.put("bounds_only",true);lead.put("world_written",false);lead.put("native_admission",false);Files.writeString(out.resolve("CURRENT_LEGACY_LEAD_REPORT.json"),G.toJson(lead));System.out.println("CURRENT_RUNTIME_SOURCE_EXPORT_COMPLETE; no Level/game/World");
    }
}

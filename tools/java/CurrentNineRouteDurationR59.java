package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.zip.GZIPInputStream;

/** Actual installed directory math and original source clocks; no runtime/world changes. */
public final class CurrentNineRouteDurationR59
{
    private static double duration(double distance,NervRouteDirectoryR52.SpeedProfile p)
    {return new NervMechanicalTravelR52.ContinuousProfile(0,distance,p.cruiseMps(),p.accelerationMps2(),p.decelerationMps2()).durationSeconds();}
    private static int layers(JsonElement declaration,Path owner)throws Exception
    {
        if(declaration.isJsonArray())return declaration.getAsJsonArray().size();var ref=declaration.getAsJsonObject();Path path=owner.toAbsolutePath().getParent().resolve(ref.get("cells_file").getAsString()).normalize();byte[] data=Files.readAllBytes(path);
        if(!HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data)).equals(ref.get("sha256").getAsString()))throw new IllegalStateException("Actual declared LCL table hash differs");
        try(var reader=new com.google.gson.stream.JsonReader(new InputStreamReader(new GZIPInputStream(new ByteArrayInputStream(data)),java.nio.charset.StandardCharsets.UTF_8))){int count=0;reader.beginArray();while(reader.hasNext()){reader.skipValue();count++;}reader.endArray();return count;}
    }
    public static void main(String[] args)throws Exception
    {
        if(args.length!=3)throw new IllegalArgumentException("actual_directory actual_owner fresh_report required");
        Path output=Path.of(args[2]);if(Files.exists(output))throw new IllegalArgumentException("Fresh external output required");
        for(Path p=output.toAbsolutePath();p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        var directory=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());
        var owner=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();var units=new HashMap<Integer,JsonObject>();for(var u:owner.getAsJsonArray("units"))units.put(u.getAsJsonObject().get("variant").getAsInt(),u.getAsJsonObject());
        var rows=new ArrayList<Map<String,Object>>();double total=0;
        for(var route:directory.routes().values().stream().filter(r->!r.recovery()).sorted(Comparator.comparingInt(NervRouteDirectoryR52.Route::bank).thenComparingInt(NervRouteDirectoryR52.Route::variant)).toList())
        {
            var u=units.get(route.variant());String unit=String.format("unit%02d",route.variant()),intent=route.bank()==1?"geofront":route.bank()==2?"surface":"hakone";
            double ready=directory.readyDistanceR53(route),length=directory.routeLength(route);double pre=duration(ready,route.motionProfile().prelaunch()),up=duration(length-ready,route.motionProfile().launch());
            var reverse=directory.routes().values().stream().filter(r->r.recovery()&&r.reverseOf().equals(route.id())).findFirst().orElseThrow();double reverseReady=directory.readyDistanceR53(reverse),down=duration(reverseReady,reverse.motionProfile().launch()),transfer=duration(directory.routeLength(reverse)-reverseReady,reverse.motionProfile().prelaunch());
            var pit=owner.getAsJsonArray("gates").asList().stream().map(JsonElement::getAsJsonObject).filter(g->g.get("resource").getAsString().equals(u.get("service_pit").getAsString())).findFirst().orElseThrow();int pitOpen=pit.getAsJsonObject("silo_hatch").get("open_ticks").getAsInt(),pitClose=pit.getAsJsonObject("silo_hatch").get("close_ticks").getAsInt();
            int raise=u.get("carrier_raise_ticks").getAsInt(),fluid=layers(u.get("lcl"),Path.of(args[1]))*4;
            // Original pressure leaves/boarding/other geometry checks may add real waits.
            double prepareMinimum=(40+190+60+fluid+NervLowerFrameR52.OPEN_TICKS+pitOpen+NervServiceFootDriveR52.BRIDGE_OPEN_TICKS+raise+40)/20D;
            double returnMinimum=(40+raise+NervServiceFootDriveR52.BRIDGE_CLOSE_TICKS+pitClose+NervLowerFrameR52.CLOSE_TICKS+197+fluid+40)/20D;
            var row=new LinkedHashMap<String,Object>();row.put("route",route.id());row.put("reverse",reverse.id());row.put("variant",route.variant());row.put("bank",route.bank());row.put("intent",intent);row.put("total_metres",length);row.put("ready_distance_metres",ready);row.put("prelaunch_transfer_seconds_at20TPS",pre);row.put("actual_ascent_profile_seconds_at20TPS",up);row.put("reverse_descent_profile_seconds_at20TPS",down);row.put("reverse_transfer_seconds_at20TPS",transfer);row.put("original_prepare_mechanical_minimum_seconds_at20TPS",prepareMinimum);row.put("original_return_mechanical_minimum_seconds_at20TPS",returnMinimum);row.put("minimum_roundtrip_seconds_excluding_pilot_gate_shoes_ballistic_holds",prepareMinimum+pre+up+down+transfer+returnMinimum);
            row.put("normal_commands",List.of("seele eva dummy start "+unit,"seele eva prepare "+unit+" "+intent,"seele eva launch "+unit,"seele eva recover "+unit,"seele eva dummy stop "+unit));rows.add(row);total+=prepareMinimum+pre+up+down+transfer+returnMinimum;
        }
        var report=new LinkedHashMap<String,Object>();report.put("scope","Original real directory geometric lengths and production continuous-profile formulas; durations are20TPS minima, not actual native completion or timeout to force progress.");report.put("world_written",false);report.put("game_started",false);report.put("routes",rows);report.put("serial_minimum_seconds",total);report.put("nominal_parallel_waves","3 variant requests may share a bank wave only if original live SPACE/gates/leases permit; do not bypass blockers");Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
    }
}

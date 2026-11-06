package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import org.joml.Quaternionf;

/** Read-only real production parsers and same-source floor contacts. */
public final class ReadRootEncounterContractsR52
{
    public static void main(String[] args)throws Exception
    {
        var surface=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        var first=SurfaceAngelPlanR52.parse(surface,"projectseele:geofront");
        var raw=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();
        if(raw.get("installed").getAsBoolean())throw new IllegalArgumentException("Read-only source validation expects uninstalled controller draft");
        raw.addProperty("installed",true);var station=TvYashimaStationR52.parse(raw,"projectseele:geofront");
        var supports=new ArrayList<Object>();
        for(var part:FixedCannonCradleR52.pieces(station.geometry(),station.cradle(),station.closed(),new Quaternionf()))
            if(part.part().name().equals("floor_plate"))
            {
                var b=part.mesh().envelope(part.frame(),part.frame());
                supports.add(List.of(b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ));
            }
        if(supports.size()!=2)throw new IllegalStateException("Two actual floor plates required");
        var report=Map.of("surface_plan_fingerprint",first.fingerprint(),"surface_chapters",first.sites().keySet(),
            "station_fingerprint",station.fingerprint(),"cannon_uuid",station.cannon().toString(),
            "source_weapon_uuid",station.weapon().toString(),"actual_floor_plate_bounds",supports,
            "world_written",false,"controller_installed",false,"native_verified",false);
        Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(report));
        System.out.println(new Gson().toJson(report));
    }
}

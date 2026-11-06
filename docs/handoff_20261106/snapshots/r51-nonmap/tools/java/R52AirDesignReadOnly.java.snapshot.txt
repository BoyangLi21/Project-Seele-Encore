package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.Map;
/** Actual production design parser; no level, registry installation or actor. */
public final class R52AirDesignReadOnly {
 public static void main(String[] args)throws Exception {
  var d=NervRouteDirectoryR52.parse(JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject());
  var air=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject();air.addProperty("directory_fingerprint",d.fingerprint());air.addProperty("status","design");
  var a=NervAirTransportManifestR52.parse(air,d);
  Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"native_commissioned",false,"production_air_design_parser",true,"directory_fingerprint",d.fingerprint(),"air_fingerprint",a.fingerprint(),"original_aircraft",a.aircraft().size(),"missions",a.missions().size(),"scope","Actual parser on Root design/reference frames; actual pilot/mesh/world admission not claimed")));
  System.out.println("Production AIR design parser PASS aircraft="+a.aircraft().size()+" missions="+a.missions().size());
 }
}

package com.projectseele.world;
import com.google.gson.*;import java.io.*;import java.nio.file.*;import java.security.*;import java.util.*;import java.util.zip.GZIPInputStream;import net.minecraft.world.phys.*;import org.joml.Quaternionf;
/** True dorsal-locked plug alone, on the unchanged nine original prelaunch legs. */
public final class VerifySeatedPlugPrelaunchR53
{
 record Part(String name,NervRigidMeshSweepR52 mesh){}
 record Cell(JsonObject row,AABB bounds,List<AABB> shapes){}
 static final Gson G=new GsonBuilder().setPrettyPrinting().create();
 static String sha(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
 static RigidTransform frame(JsonArray a){return new RigidTransform(new Vec3(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble()),a.get(3).getAsFloat(),a.get(4).getAsFloat(),a.get(5).getAsFloat(),a.get(6).getAsFloat());}
 static AABB box(JsonArray a){return new AABB(a.get(0).getAsDouble(),a.get(1).getAsDouble(),a.get(2).getAsDouble(),a.get(3).getAsDouble(),a.get(4).getAsDouble(),a.get(5).getAsDouble());}
 static double[] values(AABB b){return new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ};}
 static List<Part> parts(Path path)throws Exception{var out=new ArrayList<Part>();try(var in=new DataInputStream(new GZIPInputStream(Files.newInputStream(path)))){int n=in.readInt();for(int i=0;i<n;i++){String name=in.readUTF(),family=in.readUTF();int count=in.readInt();double[] xyz=new double[count];for(int k=0;k<count;k++)xyz[k]=in.readDouble();if(family.equals("PLUG"))out.add(new Part(name,new NervRigidMeshSweepR52(xyz)));}}if(out.size()!=3)throw new AssertionError("Actual three seated plug pieces required");return out;}
 public static void main(String[] args)throws Exception
 {
  Path base=Path.of(args[0]),out=Path.of(args[1]);Files.createDirectories(out);var prepared=JsonParser.parseString(Files.readString(base.resolve("prelaunch_world_current/CURRENT_PRELAUNCH_WINDOWS.json"))).getAsJsonObject();Path current=base.resolve("launch_hulls_v2_seated_plug/final_68cc");var receipt=JsonParser.parseString(Files.readString(current.resolve("ACTUAL_CURRENT_ASSEMBLY_EXPORT.json"))).getAsJsonObject();var candidates=args.length>2?JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject():null;var cells=new ArrayList<Cell>();
  if(candidates!=null){if(!candidates.getAsJsonArray("unknown_shapes").isEmpty())throw new AssertionError("Unknown current shape");for(var raw:candidates.getAsJsonArray("cells")){var c=raw.getAsJsonObject();var shapes=new ArrayList<AABB>();AABB bound=null;for(var b:c.getAsJsonArray("native_boxes")){var shape=box(b.getAsJsonArray());shapes.add(shape);bound=bound==null?shape:bound.minmax(shape);}cells.add(new Cell(c,bound,shapes));}}
  var index=new NervStaticSpatialIndexR52<>(cells,Cell::bounds);var results=new ArrayList<Object>();var sources=new TreeMap<String,String>();long total=0;
  for(var raw:prepared.getAsJsonArray("legs")){var leg=raw.getAsJsonObject();String id=leg.get("leg").getAsString();int v=leg.get("variant").getAsInt();Path path=current.resolve("ACTUAL_FIXED_ASSEMBLY.variant"+v+".bin.gz");sources.put(path.toString(),sha(path));var parts=parts(path);var binding=NervOriginalCarrierR52.nominalBinding(v);var envs=new LinkedHashMap<String,AABB>();var hits=new LinkedHashMap<String,JsonObject>();long tests=0;
   for(var wraw:leg.getAsJsonArray("windows")){var w=wraw.getAsJsonObject();var fa=frame(w.getAsJsonArray("root_from"));var fb=frame(w.getAsJsonArray("root_to"));var a=RigidTransform.of(fa.transformPoint(binding.contactCentre()),new Quaternionf());var b=RigidTransform.of(fb.transformPoint(binding.contactCentre()),new Quaternionf());double error=w.get("root_error_m").getAsDouble();
    for(var p:parts){var env=p.mesh().envelope(a,b).inflate(error);envs.merge(p.name(),env,AABB::minmax);if(candidates==null)continue;for(var c:index.query(env)){for(var shape:c.shapes()){tests++;if(!p.mesh().intersects(a,b,shape.inflate(error),.003))continue;String key=c.row().get("position")+"/"+p.name();var h=hits.get(key);if(h==null){h=c.row().deepCopy();h.addProperty("part",p.name());h.addProperty("first_fraction",w.get("from").getAsDouble());h.addProperty("last_fraction",w.get("to").getAsDouble());h.addProperty("maximum_curve_error_m",error);hits.put(key,h);}else{h.addProperty("last_fraction",w.get("to").getAsDouble());h.addProperty("maximum_curve_error_m",Math.max(error,h.get("maximum_curve_error_m").getAsDouble()));}break;}}}
   }
   total+=tests;var env=new ArrayList<Object>();for(var e:envs.entrySet())env.add(Map.of("part",e.getKey(),"bounds",values(e.getValue())));results.add(Map.of("leg",id,"variant",v,"parts",env,"narrow_phase_tests",tests,"actual_part_cell_hits",hits.values()));System.out.println(id+" true-plug tests="+tests+" hits="+hits.size());
  }
  Files.writeString(out.resolve(candidates==null?"TRUE_PLUG_ENVELOPES.json":"TRUE_PLUG_CURRENT_WORLD.json"),G.toJson(Map.of("world_written",false,"game_started",false,"sources_sha256",sources,"binding_receipt",current.resolve("ACTUAL_SEATED_PLUG_BINDING_RECEIPT.json").toString(),"prelaunch_geometry_rebind",current.resolve("PRELAUNCH_RIGID_GEOMETRY_UNCHANGED.json").toString(),"legs",results,"narrow_phase_tests",total)));
 }
}

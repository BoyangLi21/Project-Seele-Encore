package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.*;
/** Native-sized candidate cubes against every actual fixed guide piece. */
public final class FixedGuideCubeEvidenceR52 {
 public static void main(String[] args)throws Exception{var j=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var rows=new ArrayList<Object>();int hits=0;var fixed=NervFixedFootGuidesR52.pieces();for(var raw:j.getAsJsonArray("candidate_cells")){var c=raw.getAsJsonArray();int x=c.get(0).getAsInt(),y=c.get(1).getAsInt(),z=c.get(2).getAsInt();var b=new AABB(x,y,z,x+1,y+1,z+1);var names=new ArrayList<String>();for(var p:fixed)if(b.intersects(p.mesh().envelope(p.frame(),p.frame()))&&p.mesh().intersects(p.frame(),p.frame(),b,.003))names.add(p.name());if(!names.isEmpty())hits++;rows.add(Map.of("cell",new int[]{x,y,z},"clear",names.isEmpty(),"hits",names));}Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"fixed_source",NervFixedFootGuidesR52.SOURCE_SHA,"fixed_piece_count",fixed.size(),"candidate_support_cells",rows)));System.out.println("cells="+rows.size()+" fixed conflicts="+hits);}
}

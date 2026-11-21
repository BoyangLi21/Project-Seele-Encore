package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.AABB;

/** Same selected source and same predicate; no world or native FPS claim. */
public final class AuditFixedRailIndexR52
{
    public static void main(String[] args)throws Exception
    {
        var source=NervFixedFootGuidesR52.pieces();var bounds=new IdentityHashMap<NervServiceFootDriveR52.Piece,AABB>();
        for(var p:source)bounds.put(p,p.mesh().envelope(p.frame(),p.frame()));
        var index=new NervStaticSpatialIndexR52<>(source,bounds::get);var random=new Random(52);long selected=0;
        for(int i=0;i<1200;i++)
        {
            var box=bounds.get(source.get(random.nextInt(source.size())));var centre=box.getCenter();
            double rx=i%2==0?20:.02,ry=i%2==0?64:.02,rz=i%2==0?20:.02;
            var q=new AABB(centre.x-rx,centre.y-ry,centre.z-rz,centre.x+rx,centre.y+ry,centre.z+rz);
            var expected=source.stream().filter(p->bounds.get(p).intersects(q)).toList();var actual=index.query(q);
            if(!actual.equals(expected))throw new AssertionError("Actual fixed-source order/membership mismatch at query "+i);
            selected+=actual.size();
        }
        var result=Map.of("exact_actual_source_queries",1200,"actual_source_parts",source.size(),"source_sha256",NervFixedFootGuidesR52.SOURCE_SHA,
            "average_matching_parts",selected/1200.0,"bounds_precomputed_once",true,"source_order_preserved",true,
            "world_written",false,"native_fps_verified",false);
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(new Gson().toJson(result));
    }
}

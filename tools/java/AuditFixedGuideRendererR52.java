package com.projectseele.client.render;
import com.google.gson.GsonBuilder;
import com.projectseele.world.*;
import net.minecraft.world.phys.*;
import java.nio.file.*;
import java.util.*;

/** Exact actual-source selection equivalence; no claimed native FPS result. */
public final class AuditFixedGuideRendererR52
{
    public static void main(String[] args)throws Exception
    {
        var anchors=NervFixedFootGuidesR52.anchors();var anchorIndex=new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.actualBearing(),a.actualBearing()));
        var pieces=NervFixedFootGuidesR52.pieces();var boxes=new IdentityHashMap<NervServiceFootDriveR52.Piece,AABB>();
        for(var p:pieces)
        {
            var box=p.mesh().envelope(p.frame(),p.frame());boxes.put(p,box);var centre=box.getCenter();
            var expected=anchors.stream().min(Comparator.comparingDouble(a->a.actualBearing().distanceToSqr(centre))).orElseThrow();
            if(!expected.equals(NervFixedFootGuideRendererR52.nearestAnchor(centre,anchorIndex)))throw new AssertionError("Nearest anchor changed: "+p.name());
        }
        var index=new NervStaticSpatialIndexR52<>(pieces,boxes::get);var random=new Random(52);long candidates=0,visible=0;
        for(int n=0;n<1200;n++)
        {
            var centre=boxes.get(pieces.get(random.nextInt(pieces.size()))).getCenter();var camera=centre.add(random.nextDouble()*64-32,random.nextDouble()*64-32,random.nextDouble()*64-32);
            int x=(int)Math.floor(camera.x/32),y=(int)Math.floor(camera.y/32),z=(int)Math.floor(camera.z/32);
            var region=new AABB(x*32.-180,y*32.-180,z*32.-180,(x+1)*32.+180,(y+1)*32.+180,(z+1)*32.+180);var view=new AABB(camera,camera).inflate(180);
            var nearby=index.query(region);var actual=nearby.stream().filter(p->boxes.get(p).intersects(view)).toList();var expected=pieces.stream().filter(p->boxes.get(p).intersects(view)).toList();
            if(!actual.equals(expected))throw new AssertionError("Camera-cell exact source order/visibility differs");candidates+=nearby.size();visible+=actual.size();
        }
        var report=Map.of("actual_source_parts",pieces.size(),"exact_nearest_anchor_checks",pieces.size(),"camera_selection_checks",1200,
            "mean_cached_camera_candidates",candidates/1200.,"mean_original_visible_parts",visible/1200.,"original_source_order_and_live_anchor_checks_preserved",true,
            "source_sha256",NervFixedFootGuidesR52.SOURCE_SHA,"native_fps_verified",false,"world_written",false);
        Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(report);
    }
}

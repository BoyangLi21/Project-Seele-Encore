package com.projectseele.world;

import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.*;
import net.minecraft.world.phys.shapes.*;
import org.joml.Quaternionf;

/** Real pre-change source vs candidate collision lists; no Level, Entity or game is created. */
public final class CurrentPlantBBoxQueryR58
{
    private static final AABB ALL=new AABB(-1e8,-1e8,-1e8,1e8,1e8,1e8);
    private static long lists,boxes,phaseBounds,far,near,boundary,deep;
    private static RigidTransform frame(CompoundTag t){return new RigidTransform(new Vec3(t.getDouble("X"),t.getDouble("Y"),t.getDouble("Z")),t.getFloat("Qx"),t.getFloat("Qy"),t.getFloat("Qz"),t.getFloat("Qw"));}
    private static void same(List<VoxelShape> before,List<VoxelShape> after,String context)
    {
        lists++;if(before.size()!=after.size())throw new AssertionError(context+" size "+before.size()+" != "+after.size());
        for(int i=0;i<before.size();i++)
        {
            var a=before.get(i).toAabbs();var b=after.get(i).toAabbs();if(a.size()!=b.size())throw new AssertionError(context+" voxel member changed");
            for(int j=0;j<a.size();j++){double[] A={a.get(j).minX,a.get(j).minY,a.get(j).minZ,a.get(j).maxX,a.get(j).maxY,a.get(j).maxZ},B={b.get(j).minX,b.get(j).minY,b.get(j).minZ,b.get(j).maxX,b.get(j).maxY,b.get(j).maxZ};for(int n=0;n<6;n++)if(Double.doubleToLongBits(A[n])!=Double.doubleToLongBits(B[n]))throw new AssertionError(context+" double bits/order changed");boxes++;}
        }
    }
    private static void encloses(AABB domain,AABB b,String context)
    {phaseBounds++;if(!(domain.minX<=b.minX&&domain.minY<=b.minY&&domain.minZ<=b.minZ&&domain.maxX>=b.maxX&&domain.maxY>=b.maxY&&domain.maxZ>=b.maxZ))throw new AssertionError(context+" escaped complete control hull: "+b+" domain="+domain);}
    private static List<VoxelShape> service(NervServiceFootDriveR52.Spec drive,double bridge,AABB query)throws Exception
    {var result=new ArrayList<VoxelShape>();for(var piece:NervServiceFootDriveR52.pieces(drive,bridge)){var box=piece.mesh().envelope(piece.frame(),piece.frame());if(box.intersects(query))result.add(Shapes.create(box));}return result;}
    private static List<VoxelShape> old(int variant,RigidTransform frame,float closed,float lower,NervServiceFootDriveR52.Spec drive,double bridge,AABB query)throws Exception
    {var result=new ArrayList<VoxelShape>(NervPlantMotionBaselineR58.actualCollisionMembers(variant,frame,closed,lower,query));result.addAll(service(drive,bridge,query));return result;}
    private static List<VoxelShape> candidate(AABB domain,int variant,RigidTransform frame,float closed,float lower,NervServiceFootDriveR52.Spec drive,double bridge,AABB query)throws Exception
    {if(!domain.intersects(query)){far++;return List.of();}var result=new ArrayList<VoxelShape>(NervPlantMotionR52.actualCollisionMembers(variant,frame,closed,lower,query));result.addAll(service(drive,bridge,query));return result;}
    private static List<Float> physicalClocks()
    {var values=new TreeSet<Float>();for(int ticks:new int[]{120,180})for(int i=0;i<=ticks;i++)values.add(Math.round(i/(float)ticks*1000)/1000F);values.addAll(List.of(.3F,.375F,.45F,.85F));return List.copyOf(values);}
    private static AABB firstBox(List<VoxelShape> shapes){for(var s:shapes)if(!s.isEmpty())return s.bounds();throw new AssertionError("Expected real near-domain collision boxes");}
    private static void runFrame(String name,int variant,RigidTransform f,NervServiceFootDriveR52.Spec drive,List<Float> clocks)throws Exception
    {
        AABB domain=NervAssemblyOwnerR52.sourceCageDomainR57(f,drive);var t=f.translation();
        AABB close=new AABB(t.x-23,t.y-12,t.z-12,t.x+23,t.y+80,t.z+12),remote=new AABB(-1200,80,1500,-1190,90,1510);
        for(float p:clocks)
        {
            float closed=1-p;double bridge=Math.round(p*1000)/1000F;
            var all=old(variant,f,closed,p,drive,bridge,ALL);for(var shape:all)for(var box:shape.toAabbs())encloses(domain,box,name+" p="+p);
            same(old(variant,f,closed,p,drive,bridge,close),candidate(domain,variant,f,closed,p,drive,bridge,close),name+" near p="+p);near++;
            same(old(variant,f,closed,p,drive,bridge,remote),candidate(domain,variant,f,closed,p,drive,bridge,remote),name+" remote p="+p);
            if(p==0||p==1||p==.3F||p==.375F||p==.45F||p==.85F)
            {
                var b=firstBox(all);double cy=(b.minY+b.maxY)/2,cz=(b.minZ+b.maxZ)/2;
                for(double delta:new double[]{-1e-9,0,1e-9})
                {var q=new AABB(b.maxX+delta,cy-.01,cz-.01,b.maxX+.2+delta,cy+.01,cz+.01);same(old(variant,f,closed,p,drive,bridge,q),candidate(domain,variant,f,closed,p,drive,bridge,q),name+" boundary "+delta);boundary++;}
            }
        }
        // Complete synchronized bridge domain (1001 native integer/1000 positions).
        for(int i=0;i<=1000;i++)for(var piece:NervServiceFootDriveR52.pieces(drive,i/1000F))encloses(domain,piece.mesh().envelope(piece.frame(),piece.frame()),name+" bridge "+i);
    }
    public static void main(String[] args)throws Exception
    {
        if(args.length!=3)throw new IllegalArgumentException("actual_saved_spec_report fresh_output source_radius_receipt required");
        Path output=Path.of(args[1]);if(Files.exists(output))throw new IllegalArgumentException("Fresh external output required");
        for(Path p=output.toAbsolutePath();p!=null;p=p.getParent())if(Files.exists(p.resolve("level.dat"))||Files.exists(p.resolve("session.lock")))throw new IllegalArgumentException("Output inside World");
        // The actual float smooth helper owns vanilla data serializers. Only
        // isolated data registries are initialized; no Level or game is opened.
        net.minecraft.SharedConstants.tryDetectVersion();var boot=net.minecraft.server.Bootstrap.class.getDeclaredField("isBootstrapped");boot.setAccessible(true);boot.setBoolean(null,true);net.minecraft.core.registries.BuiltInRegistries.bootStrap();
        var source=JsonParser.parseString(Files.readString(Path.of(args[2]))).getAsJsonObject();String sha=source.get("sha256").getAsString();NervPlantMotionBaselineR58.install(sha);NervPlantMotionR52.install(sha);
        var specs=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var clocks=physicalClocks();var current=new ArrayList<NervServiceFootDriveR52.Spec>();
        long began=System.nanoTime();
        for(var raw:specs.getAsJsonArray("rows"))
        {
            var row=raw.getAsJsonObject();var nbt=TagParser.parseTag(row.get("snbt").getAsString());int variant=row.get("variant").getAsInt();var s=new NervServiceFootDriveR52.Spec(variant,frame(nbt.getCompound("Bay")),frame(nbt.getCompound("Hatch")),nbt.getDouble("Tier"),nbt.getDouble("FoundationTop"));current.add(s);
            var f=new RigidTransform(new Vec3(s.bay().translation().x,-1062.96,s.bay().translation().z),0,1,0,0);runFrame("actual_saved_variant"+variant,variant,f,s,clocks);
        }
        var s=current.get(0);for(int index=0;index<2;index++)
        {
            var q=index==0?new Quaternionf().rotationY(.71F):new Quaternionf().rotationXYZ(.23F,.71F,.41F);
            var f=RigidTransform.of(new Vec3(72.5,-1062.96,328.5),q);var drive=index==0?new NervServiceFootDriveR52.Spec(s.variant(),RigidTransform.of(s.bay().translation(),q),RigidTransform.of(s.hatch().translation(),q),s.firstTier(),s.foundationTop()):s;runFrame("rotated_full_frame"+index,s.variant(),f,drive,List.of(0F,.01F,.299F,.3F,.301F,.374F,.375F,.376F,.449F,.45F,.451F,.7F,.849F,.85F,.851F,.999F,1F));
            if(index==1){boolean rejected=false;try{NervServiceFootDriveR52.pieces(new NervServiceFootDriveR52.Spec(s.variant(),RigidTransform.of(s.bay().translation(),q),RigidTransform.of(s.hatch().translation(),q),s.firstTier(),s.foundationTop()),0);}catch(IllegalStateException originalGuard){rejected=true;}if(!rejected)throw new AssertionError("Original unsupported tilted guide-up guard changed");}
        }
        // Adversarial real-form Spec extends fixed guide rails far below the original cage sphere.
        var deepSpec=new NervServiceFootDriveR52.Spec(s.variant(),s.bay(),s.hatch(),s.firstTier(),s.foundationTop()-120);
        var root=new RigidTransform(new Vec3(s.bay().translation().x,-1062.96,s.bay().translation().z),0,1,0,0);var domain=NervAssemblyOwnerR52.sourceCageDomainR57(root,deepSpec);
        for(var piece:NervServiceFootDriveR52.pieces(deepSpec,.63))if(piece.name().startsWith("service_fixed_lower/"))
        {
            var b=piece.mesh().envelope(piece.frame(),piece.frame());if(b.getYsize()<1)continue;double yy=b.minY+.25;var query=new AABB(b.minX,yy,b.minZ,b.maxX,yy+.1,b.maxZ);
            if(query.getCenter().distanceTo(root.translation())<=NervPlantMotionR52.cageCollisionRadiusR57())throw new AssertionError("Deep negative case was accidentally within old cage radius");
            var a=old(s.variant(),root,.41F,.63F,deepSpec,.63,query);if(a.isEmpty())throw new AssertionError("Deep original guide rail must collide");same(a,candidate(domain,s.variant(),root,.41F,.63F,deepSpec,.63,query),"deep rail outside old78m sphere");deep++;
        }
        if(deep==0)throw new AssertionError("Missing deep guide negative");
        // Repeated exact pose is reused, frame/progress changes are not rounded.
        var first=NervLowerFrameR52.collisionBoxesR57(root,.6310000419616699);var again=NervLowerFrameR52.collisionBoxesR57(root,.6310000419616699);var next=NervLowerFrameR52.collisionBoxesR57(root,Math.nextUp(.6310000419616699));
        if(first!=again||first==next)throw new AssertionError("Exact pose cache key/reuse changed");
        Field cache=NervLowerFrameR52.class.getDeclaredField("COLLISION_BOXES_R57");cache.setAccessible(true);if(((Map<?,?>)cache.get(null)).size()>8)throw new AssertionError("Unbounded pose cache");
        var pose=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0);
        if(pose!=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0))throw new AssertionError("Plant exact pose was rebuilt");
        if(pose==NervPlantMotionR52.collisionBoxesR58(s.variant(),root,Math.nextDown(1F),0)||pose==NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,Math.nextUp(0F)))throw new AssertionError("Plant clock bits were rounded");
        if(pose==NervPlantMotionR52.collisionBoxesR58((s.variant()+1)%3,root,1,0))throw new AssertionError("Variant omitted from cache key");
        var shifted=new RigidTransform(root.translation().add(.000000001,0,0),root.qx(),root.qy(),root.qz(),root.qw());if(pose==NervPlantMotionR52.collisionBoxesR58(s.variant(),shifted,1,0))throw new AssertionError("Frame omitted from key");
        boolean immutable=false;try{pose.clear();}catch(UnsupportedOperationException correct){immutable=true;}if(!immutable)throw new AssertionError("Cached boxes mutable");
        var q=new AABB(root.translation().x-1,root.translation().y,root.translation().z-1,root.translation().x+1,root.translation().y+2,root.translation().z+1);
        var outputList=NervPlantMotionR52.actualCollisionMembers(s.variant(),root,1,0,q);immutable=false;try{outputList.clear();}catch(UnsupportedOperationException correct){immutable=true;}if(!immutable)throw new AssertionError("Returned query list mutable");
        Field plantCache=NervPlantMotionR52.class.getDeclaredField("COLLISION_BOXES_R58");plantCache.setAccessible(true);var currentCache=(Map<?,?>)plantCache.get(null);
        for(int i=0;i<20;i++)NervPlantMotionR52.collisionBoxesR58(s.variant(),root,i/20F,0);if(currentCache.size()!=8)throw new AssertionError("Plant cache exceeds8");
        var beforeSameInstall=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0);NervPlantMotionR52.install(sha);if(beforeSameInstall!=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0))throw new AssertionError("Same source unnecessarily invalidated");
        boolean invalidRejected=false;try{NervPlantMotionR52.install("wrong-source-sha");}catch(IllegalStateException correct){invalidRejected=true;}if(!invalidRejected||beforeSameInstall!=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0))throw new AssertionError("Failed source selection changed valid cache");
        // Isolated tool resets the installation latch only to execute the real
        // successful reload parser/hash checks with the same selected asset.
        Field components=NervPlantMotionR52.class.getDeclaredField("components");components.setAccessible(true);components.set(null,null);NervPlantMotionR52.install(sha);if(currentCache.size()!=0)throw new AssertionError("Validated source reload did not invalidate cache");
        same(NervPlantMotionBaselineR58.actualCollisionMembers(s.variant(),root,1,0,ALL),NervPlantMotionR52.actualCollisionMembers(s.variant(),root,1,0,ALL),"after successful verified source reload");
        var reused=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0);long perfBegin=System.nanoTime();for(int i=0;i<1000;i++)NervPlantMotionBaselineR58.actualCollisionMembers(s.variant(),root,1,0,q);long baselineNs=System.nanoTime()-perfBegin;
        perfBegin=System.nanoTime();for(int i=0;i<1000;i++)NervPlantMotionR52.actualCollisionMembers(s.variant(),root,1,0,q);long cachedNs=System.nanoTime()-perfBegin;if(reused!=NervPlantMotionR52.collisionBoxesR58(s.variant(),root,1,0))throw new AssertionError("Repeated near path entered transforms");
        var report=new LinkedHashMap<String,Object>();report.put("passed",true);report.put("plant_exact_source_variant_frame_raw_float_key",true);report.put("plant_cache_max",8);report.put("immutable_cached_boxes_and_returned_lists",true);report.put("same_source_reuse_failed_source_preservation_successful_source_reload_invalidation",true);report.put("near1000_baseline_ms",baselineNs/1e6);report.put("near1000_cached_ms",cachedNs/1e6);report.put("near1000_cached_pose_object_reused",true);report.put("collision_lists_byte_and_sequence_equal",lists);report.put("ordered_world_shape_boxes_equal",boxes);report.put("source_control_domain_enclosure_checks",phaseBounds);report.put("far_queries_skipped_current_geometry",far);report.put("near_queries",near);report.put("touching_inside_outside_boundary_queries",boundary);report.put("deep_guide_queries_outside_original_radius",deep);report.put("native_open_close_pose_values",clocks.size());report.put("exact_pose_reuse_and_next_double_miss",true);report.put("pose_cache_limit",8);report.put("elapsed_seconds",(System.nanoTime()-began)/1e9);report.put("scope","Same frozen real source methods and exact real source assets, actual saved original FootDrive specs; tool creates no Entity/Level/game/World. Native TPS/collision feel remains Root validation.");
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
    }
}

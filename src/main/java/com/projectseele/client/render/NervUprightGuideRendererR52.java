package com.projectseele.client.render;

import com.projectseele.ProjectSeele;
import com.projectseele.client.FacilityFrameClientR52;
import com.projectseele.world.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.LevelRenderer;
import net.minecraft.commands.arguments.blocks.BlockStateParser;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;
import net.minecraftforge.client.event.RenderLevelStageEvent;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientPlayerNetworkEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Exact new steel, read once off the render thread and grouped into32m GPU
 * cells. A visual source never installs/enables server machinery. */
@Mod.EventBusSubscriber(modid="projectseele",value=Dist.CLIENT)
public final class NervUprightGuideRendererR52 {
    private static final String SOURCE="/assets/projectseele/facility/r52_upright_guideway_paths.json";
    private static final ExecutorService READER=Executors.newSingleThreadExecutor(r->{var t=new Thread(r,"R52-upright-source-reader");t.setDaemon(true);return t;});
    private record Key(int x,int y,int z){Vec3 origin(){return new Vec3(x*32D,y*32D,z*32D);}String id(){return x+"_"+y+"_"+z;}}
    private static final class Building {final Key key;final RigidMachineryPartR44.Builder mesh=new RigidMachineryPartR44.Builder();final Set<String> legs=new HashSet<>();Building(Key key){this.key=key;}}
    private static final class Cell {
        final Key key;final RigidMachineryPartR44 mesh;final AABB bounds;final List<NervUprightGuidewayR52.Anchor> anchors;
        long nextNativeCheck,lastDrawFrame,lastDrawNanos;boolean nativeReady,gpuUploaded;
        Cell(Key key,RigidMachineryPartR44 mesh,List<NervUprightGuidewayR52.Anchor> anchors){this.key=key;this.mesh=mesh;this.anchors=List.copyOf(anchors);var b=mesh.bounds();var o=key.origin();bounds=new AABB(b[0]+o.x,b[1]+o.y,b[2]+o.z,b[3]+o.x,b[4]+o.y,b[5]+o.z);}
    }
    private record Loaded(String sha,int pieceCount,List<Cell> cells,NervStaticSpatialIndexR52<Cell> index){}
    private static volatile String status="UNDECLARED";private static volatile int parsedParts;private static volatile long generation;
    private static String expected="";private static CompletableFuture<Loaded> loading;private static Loaded loaded;
    private static List<Cell> nearby=List.of();private static Key cameraCell;private static int cameraDistance;private static long frame;
    private static volatile Map<String,Object> diagnostic=Map.of("parse_status","UNDECLARED","ready",false);

    static void clear(){generation++;if(loading!=null)loading.cancel(true);loading=null;if(loaded!=null)for(var cell:loaded.cells())RigidMachineryGpuR44.releaseR52(cell.mesh);loaded=null;nearby=List.of();cameraCell=null;expected="";parsedParts=0;status="UNDECLARED";diagnostic=Map.of("parse_status",status,"ready",false);}
    @SubscribeEvent public static void logout(ClientPlayerNetworkEvent.LoggingOut e){clear();}
    @SubscribeEvent public static void tick(TickEvent.ClientTickEvent e){if(e.phase==TickEvent.Phase.END&&!expected.isEmpty()){var level=Minecraft.getInstance().level;if(level==null||!FacilityFrameClientR52.continuousUprightR52(level))clear();}}
    private static Key key(Vec3 p){return new Key((int)Math.floor(p.x/32),(int)Math.floor(p.y/32),(int)Math.floor(p.z/32));}
    private static Loaded read(String sha,long token)throws IOException {
        var building=new LinkedHashMap<Key,Building>();var anchors=new ArrayList<NervUprightGuidewayR52.Anchor>();int[] count={0};
        try(var input=NervUprightGuideRendererR52.class.getResourceAsStream(SOURCE)){
            if(input==null)throw new FileNotFoundException("Actual declared upright source missing from selected client JAR");
            NervUprightGuidewayR52.readVisualR52(input,sha,p->{
                if(token!=generation)throw new CancellationException("Visual source declaration changed");
                var steel=p.steel();var centre=steel.mesh().envelope(steel.frame(),steel.frame()).getCenter();var k=key(centre);var cell=building.computeIfAbsent(k,Building::new);cell.legs.add(p.leg());var rgb=steel.rgb();
                for(int i=0;i<rgb.length;i+=18)cell.mesh.triangleNormalizedR52(rgb,i,steel.frame(),k.origin());count[0]++;if(token==generation)parsedParts=count[0];
            },anchors::add);
        }
        // Pure parser returned normally: the complete original bytes, schema,
        // model and support declarations have now passed before publication.
        var anchorIndex=new NervStaticSpatialIndexR52<>(anchors,a->new AABB(a.bearing(),a.bearing()).inflate(.000001));var cells=new ArrayList<Cell>();
        for(var row:building.values()){
            var mesh=row.mesh.finish();var b=mesh.bounds();var o=row.key.origin();var centre=new Vec3((b[0]+b[3])/2+o.x,(b[1]+b[4])/2+o.y,(b[2]+b[5])/2+o.z);var selected=new ArrayList<NervUprightGuidewayR52.Anchor>();
            for(var leg:row.legs){NervUprightGuidewayR52.Anchor closest=null;for(double radius=16;radius<=65536&&closest==null;radius*=2)closest=anchorIndex.query(new AABB(centre,centre).inflate(radius)).stream().filter(a->a.leg().equals(leg)).min(Comparator.comparingDouble(a->a.bearing().distanceToSqr(centre))).orElse(null);if(closest==null)throw new IllegalArgumentException("Real visual rail native anchor missing: "+leg);selected.add(closest);}
            cells.add(new Cell(row.key,mesh,selected));
        }
        var frozen=List.copyOf(cells);return new Loaded(sha,count[0],frozen,new NervStaticSpatialIndexR52<>(frozen,c->c.bounds));
    }
    private static boolean chunksLoaded(ClientLevel level,AABB box){for(int x=(int)Math.floor(box.minX/16);x<=(int)Math.floor(box.maxX/16);x++)for(int z=(int)Math.floor(box.minZ/16);z<=(int)Math.floor(box.maxZ/16);z++)if(!level.hasChunkAt(new BlockPos(x*16,(int)Math.floor(box.minY),z*16)))return false;return true;}
    private static boolean anchorBears(ClientLevel level,NervUprightGuidewayR52.Anchor a){
        if(!level.hasChunkAt(a.at())||!BlockStateParser.serialize(level.getBlockState(a.at())).equals(a.state()))return false;
        var n=a.normal();var u=Math.abs(n.x)>.5?new Vec3(0,1,0):new Vec3(1,0,0);var v=n.cross(u);
        for(var shape:level.getBlockState(a.at()).getCollisionShape(level,a.at()).toAabbs()){var b=shape.move(a.at());boolean good=true;for(double x:new double[]{-.05,0,.05})for(double z:new double[]{-.05,0,.05}){var p=a.bearing().add(u.scale(x)).add(v.scale(z));double plane=n.x>0?b.maxX:n.x<0?b.minX:n.y>0?b.maxY:n.y<0?b.minY:n.z>0?b.maxZ:b.minZ;double coordinate=n.x!=0?p.x:n.y!=0?p.y:p.z;if(Math.abs(coordinate-plane)>.0002||p.x<b.minX-.0002||p.x>b.maxX+.0002||p.y<b.minY-.0002||p.y>b.maxY+.0002||p.z<b.minZ-.0002||p.z>b.maxZ+.0002)good=false;}if(good)return true;}return false;
    }
    static void draw(RenderLevelStageEvent event,ClientLevel level){
        if(com.projectseele.world.NervR50CarrierModeR53.enabled())return;
        String selected=FacilityFrameClientR52.uprightGuideSourceR52(level);if(selected.isEmpty()){if(!expected.isEmpty())clear();return;}
        if(!selected.equals(expected)){clear();expected=selected;status="LOADING";long token=generation;loading=CompletableFuture.supplyAsync(()->{try{return read(selected,token);}catch(IOException e){throw new CompletionException(e);}},READER);}
        if(loaded==null&&loading!=null&&loading.isDone()){try{loaded=loading.join();parsedParts=loaded.pieceCount();status="LOADED";}catch(RuntimeException failure){status="FAILED";ProjectSeele.LOGGER.error("Actual declared upright visual source rejected sha={}",expected,failure);}loading=null;}
        frame++;long now=System.nanoTime();var camera=event.getCamera().getPosition();int distance=Math.max(16,Math.min(512,Minecraft.getInstance().options.getEffectiveRenderDistance()*16));var visible=new ArrayList<Map<String,Object>>();
        if(loaded!=null){var at=key(camera);if(!at.equals(cameraCell)||distance!=cameraDistance){nearby=loaded.index().query(new AABB(at.origin(),at.origin().add(32,32,32)).inflate(distance));cameraCell=at;cameraDistance=distance;}
            var view=new AABB(camera,camera).inflate(distance);int coldBudget=4;
            for(var cell:nearby){if(!view.intersects(cell.bounds)||!event.getFrustum().isVisible(cell.bounds))continue;boolean chunks=chunksLoaded(level,cell.bounds);
                if(now>=cell.nextNativeCheck){cell.nativeReady=chunks&&cell.anchors.stream().allMatch(a->anchorBears(level,a));cell.nextNativeCheck=now+200_000_000L;}
                boolean ready=chunks&&cell.nativeReady;
                if(ready&&(RigidMachineryGpuR44.cachedR52(cell.mesh)||coldBudget-->0)){RigidMachineryGpuR44.stateLimitR52(cell.mesh,4);var poses=event.getPoseStack();poses.pushPose();var p=cell.key.origin().subtract(camera);poses.translate(p.x,p.y,p.z);boolean gpu=cell.mesh.drawWithProofR52(poses,TvFacilityMeshes.currentBuffers(),LevelRenderer.getLightColor(level,BlockPos.containing(cell.bounds.getCenter())));poses.popPose();if(gpu){cell.gpuUploaded=true;cell.lastDrawFrame=frame;cell.lastDrawNanos=now;}}
                var row=new LinkedHashMap<String,Object>();row.put("key",cell.key.id());row.put("bounds",List.of(cell.bounds.minX,cell.bounds.minY,cell.bounds.minZ,cell.bounds.maxX,cell.bounds.maxY,cell.bounds.maxZ));row.put("native_loaded",ready);row.put("gpu_uploaded",cell.gpuUploaded);row.put("last_draw_frame",cell.lastDrawFrame);row.put("last_draw_nanos",cell.lastDrawNanos);visible.add(Map.copyOf(row));
            }
        }
        var report=new LinkedHashMap<String,Object>();report.put("expected_source_sha256",expected);report.put("loaded_source_sha256",loaded==null?"":loaded.sha());report.put("model_source_sha256",NervOuterCarrierGuideR52.SOURCE_SHA);report.put("parse_status",status);report.put("parsed_parts",parsedParts);report.put("render_frame",frame);report.put("render_nanos",now);report.put("camera",List.of(camera.x,camera.y,camera.z));report.put("distance_m",distance);report.put("target_visible_cells",List.copyOf(visible));report.put("ready",loaded!=null&&!visible.isEmpty()&&visible.stream().allMatch(r->Boolean.TRUE.equals(r.get("native_loaded"))&&Boolean.TRUE.equals(r.get("gpu_uploaded"))&&Objects.equals(r.get("last_draw_frame"),frame)));diagnostic=Map.copyOf(report);
    }
    /** Immutable actual render-thread snapshot for native observers; no GPU,
     * World, pose, loading, ticket, or render mutation is performed here. */
    public static Map<String,Object> readinessForBoundsR52(AABB bounds){var current=diagnostic;var rows=new ArrayList<Map<String,Object>>();Object raw=current.get("target_visible_cells");if(raw instanceof List<?> list)for(var value:list)if(value instanceof Map<?,?> row){var b=(List<?>)row.get("bounds");var box=new AABB(((Number)b.get(0)).doubleValue(),((Number)b.get(1)).doubleValue(),((Number)b.get(2)).doubleValue(),((Number)b.get(3)).doubleValue(),((Number)b.get(4)).doubleValue(),((Number)b.get(5)).doubleValue());if(bounds.intersects(box)){var copy=new LinkedHashMap<String,Object>();row.forEach((k,v)->copy.put(k.toString(),v));rows.add(Map.copyOf(copy));}}var result=new LinkedHashMap<String,Object>(current);result.put("target_visible_cells",List.copyOf(rows));result.put("ready","LOADED".equals(current.get("parse_status"))&&!rows.isEmpty()&&System.nanoTime()-((Number)current.getOrDefault("render_nanos",0L)).longValue()<500_000_000L&&rows.stream().allMatch(r->Boolean.TRUE.equals(r.get("native_loaded"))&&Boolean.TRUE.equals(r.get("gpu_uploaded"))&&Objects.equals(r.get("last_draw_frame"),current.get("render_frame"))));return Map.copyOf(result);}
    private NervUprightGuideRendererR52(){}
}

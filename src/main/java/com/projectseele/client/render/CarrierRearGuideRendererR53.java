package com.projectseele.client.render;

import com.google.gson.JsonArray;
import com.mojang.blaze3d.vertex.PoseStack;
import com.projectseele.ProjectSeele;
import com.projectseele.client.FacilityFrameClientR52;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.*;
import java.util.*;
import java.util.concurrent.*;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;
import net.minecraftforge.client.event.RenderLevelStageEvent;

/** Same immutable facets and transforms as rear-guide mechanical checks. */
final class CarrierRearGuideRendererR53
{
    private record Key(int x,int y,int z)
    {Vec3 origin(){return new Vec3(x*32D,y*32D,z*32D);}}
    private static final class Cell
    {
        final Key key;final RigidMachineryPartR44 mesh;final AABB bounds;final List<CarrierRearGuideR53.Anchor> anchors;
        long nextCheck;boolean ready;
        Cell(Key key,RigidMachineryPartR44 mesh,List<CarrierRearGuideR53.Anchor> anchors)
        {
            this.key=key;this.mesh=mesh;this.anchors=List.copyOf(anchors);var b=mesh.bounds();var o=key.origin();
            bounds=new AABB(b[0]+o.x,b[1]+o.y,b[2]+o.z,b[3]+o.x,b[4]+o.y,b[5]+o.z);
        }
    }
    private record Loaded(List<Cell> cells,NervStaticSpatialIndexR52<Cell> index,String legacy){}
    private static final ExecutorService READER=Executors.newSingleThreadExecutor(r->{var t=new Thread(r,"seele-rear-guide-reader");t.setDaemon(true);return t;});
    private static final Map<String,RigidMachineryPartR44> MOVING=new HashMap<>();
    private static CompletableFuture<Loaded> pending;
    private static Loaded loaded;
    private static boolean attempted;
    private static volatile Map<String,Object> diagnostic=Map.of("status","UNSELECTED");

    static void clear()
    {
        if(pending!=null)pending.cancel(true);pending=null;
        if(loaded!=null)for(var cell:loaded.cells())RigidMachineryGpuR44.releaseR52(cell.mesh);
        for(var mesh:MOVING.values())RigidMachineryGpuR44.releaseR52(mesh);
        MOVING.clear();loaded=null;attempted=false;diagnostic=Map.of("status","UNSELECTED");
    }

    static void drawMoving(NervCarrierPlatformEntity entity,float partial,PoseStack poses,MultiBufferSource buffers,int light,
                           RigidTransform root,float rise)
    {drawMoving(entity,partial,poses,buffers,light,root,rise,CarrierMountProfileR53.read(entity,partial));}

    static void drawMoving(NervCarrierPlatformEntity entity,float partial,PoseStack poses,MultiBufferSource buffers,int light,
                           RigidTransform root,float rise,CarrierMountProfileR53.State mounting)
    {
        var hardware=CarrierRearGuideR53.selected();if(hardware==null)return;
        boolean outlet=NervR50CarrierModeR53.launchDeckDropR53(root,0)!=0;
        var actual=root.compose(new RigidTransform(new Vec3(0,NervR50CarrierModeR53.launchDeckDropR53(root,rise),0),0,0,0,1));
        var parts=hardware.partsAt(actual,outlet?1:rise,NervOriginalCarrierR52.uprightDirectionR52(entity,partial),NervOriginalCarrierR52.headSlideR53(entity,partial),CarrierRearGuideR53.actualLift(entity,partial),mounting);
        var dispatcher=new Vec3(net.minecraft.util.Mth.lerp((double)partial,entity.xOld,entity.getX()),
                net.minecraft.util.Mth.lerp((double)partial,entity.yOld,entity.getY()),net.minecraft.util.Mth.lerp((double)partial,entity.zOld,entity.getZ()));
        for(var part:parts)
        {
            var mesh=MOVING.computeIfAbsent(hardware.fingerprint()+"/"+mounting.aboveFloor()+"/"+mounting.shallowBay()+"/"+CarrierMountProfileR53.BAY_RECEIVER_REVISION+"/"+part.name(),name->{var encoded=new JsonArray();for(double d:part.rgb())encoded.add(d);return RigidMachineryPartR44.triangles(encoded);});
            var p=part.frame().translation().subtract(dispatcher);
            poses.pushPose();poses.translate(p.x,p.y,p.z);poses.mulPose(part.frame().rotation());mesh.draw(poses,buffers,light);poses.popPose();
        }
    }

    private static Loaded load()
    {
        var source=CarrierRearGuideR53.fixed();var builders=new LinkedHashMap<Key,RigidMachineryPartR44.Builder>();
        var memberships=new HashMap<Key,Set<String>>();
        for(var piece:source.pieces())
        {
            var centre=piece.bounds().getCenter();var key=new Key((int)Math.floor(centre.x/32),(int)Math.floor(centre.y/32),(int)Math.floor(centre.z/32));
            var builder=builders.computeIfAbsent(key,k->new RigidMachineryPartR44.Builder());
            memberships.computeIfAbsent(key,k->new HashSet<>()).add(piece.leg());
            var rgb=piece.steel().rgb();for(int i=0;i<rgb.length;i+=18)builder.triangleNormalizedR52(rgb,i,piece.steel().frame(),key.origin());
        }
        var cells=new ArrayList<Cell>();
        builders.forEach((key,builder)->
        {
            var mesh=builder.finish();var box=mesh.bounds();var centre=key.origin().add((box[0]+box[3])/2,(box[1]+box[4])/2,(box[2]+box[5])/2);
            var anchors=new ArrayList<CarrierRearGuideR53.Anchor>();
            for(var leg:memberships.get(key))
            {
                CarrierRearGuideR53.Anchor found=null;
                for(double radius=32;radius<=4096&&found==null;radius*=2)
                    found=source.anchorIndex().query(new AABB(centre,centre).inflate(radius)).stream().filter(a->a.leg().equals(leg)).min(Comparator.comparingDouble(a->a.point().distanceToSqr(centre))).orElse(null);
                if(found==null)throw new IllegalStateException("Measured rear support missing for "+leg);
                anchors.add(found);
            }
            cells.add(new Cell(key,mesh,anchors));
        });
        return new Loaded(List.copyOf(cells),new NervStaticSpatialIndexR52<>(cells,c->c.bounds),source.legacySource());
    }

    static void drawFixed(RenderLevelStageEvent event,ClientLevel level)
    {
        if(CarrierRearGuideR53.selected()==null||!FacilityFrameClientR52.claimed(level))return;
        if(!attempted){attempted=true;pending=CompletableFuture.supplyAsync(CarrierRearGuideRendererR53::load,READER);}
        if(pending!=null&&pending.isDone())
        {
            try{loaded=pending.join();}catch(RuntimeException failure){ProjectSeele.LOGGER.error("Selected rear rails rejected",failure);diagnostic=Map.of("status","FAILED");}
            pending=null;
        }
        if(loaded==null||!loaded.legacy().equals(FacilityFrameClientR52.uprightGuideSourceR52(level)))return;
        var camera=event.getCamera().getPosition();int distance=Math.min(512,Math.max(FacilityVisibilityR54.DISTANCE,Minecraft.getInstance().options.getEffectiveRenderDistance()*16));
        int budget=4,visible=0,drawn=0;long now=System.nanoTime();
        for(var cell:loaded.index().query(new AABB(camera,camera).inflate(distance)))
        {
            if(!event.getFrustum().isVisible(cell.bounds))continue;visible++;
            if(now>=cell.nextCheck)
            {
                // The connection's exact installed source was matched above.
                // Loaded anchors still veto missing or changed real supports.
                cell.ready=cell.anchors.stream().allMatch(a->!level.hasChunkAt(a.at())||CarrierRearGuideR53.anchorBears(level,a));cell.nextCheck=now+200_000_000L;
            }
            if(!cell.ready||!RigidMachineryGpuR44.cachedR52(cell.mesh)&&budget--<=0)continue;
            RigidMachineryGpuR44.stateLimitR52(cell.mesh,4);var poses=event.getPoseStack();var p=cell.key.origin().subtract(camera);
            poses.pushPose();poses.translate(p.x,p.y,p.z);
            if(cell.mesh.drawWithProofR52(poses,TvFacilityMeshes.currentBuffers(),LevelRenderer.getLightColor(level,BlockPos.containing(cell.bounds.getCenter()))))drawn++;
            poses.popPose();
        }
        diagnostic=Map.of("status","LOADED","cells",loaded.cells().size(),"visible",visible,"drawn",drawn,"render_nanos",now);
    }

    public static Map<String,Object> diagnostic(){return diagnostic;}
    private CarrierRearGuideRendererR53(){}
}

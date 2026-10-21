package com.projectseele.world;

import com.google.gson.*;
import com.projectseele.entity.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.*;
import net.minecraft.world.phys.*;

/** Original sealed capsule and native seated rider on the actual canonical
 * interpolation. No shell box, collision suppression or replacement actor. */
public final class NervMappedPlugMechanicsR52
{
    private static FullAssemblyGeometryR52.Provider sources;
    private static final Map<Integer,List<NervRigidMeshSweepR52>> CAPSULES=new HashMap<>();
    private static final Map<Integer,Map<String,NervRigidMeshSweepR52>> CARRIERS=new HashMap<>();
    public static synchronized void install()throws IOException
    {
        if(sources!=null)return;var receipt=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("eva/full_assembly_geometry_r52_sources.json"),StandardCharsets.UTF_8)).getAsJsonObject();
        var hashes=new HashMap<String,String>();receipt.getAsJsonObject("resources").entrySet().forEach(e->hashes.put(e.getKey(),e.getValue().getAsString()));sources=FullAssemblyGeometryR52.selectedClasspathProviderR52(hashes);
        for(int v=0;v<3;v++)CAPSULES.put(v,sources.closedPlugParts(v).values().stream().map(NervRigidMeshSweepR52::new).toList());
        for(int v=0;v<3;v++)for(boolean rack:new boolean[]{false,true})for(boolean plant:new boolean[]{false,true})
        {
            int key=v*4+(rack?2:0)+(plant?1:0);
            if(NervR50CarrierModeR53.enabled()&&plant){CARRIERS.put(key,CARRIERS.get(key-1));continue;}
            var parts=new HashMap<String,NervRigidMeshSweepR52>();sources.carrierParts(v,1,rack,0,plant?64:rack?3:0).forEach((name,triangles)->parts.put(name,new NervRigidMeshSweepR52(triangles)));CARRIERS.put(key,Map.copyOf(parts));
        }
    }
    public static boolean clearCapsule(ServerLevel l,EvaUnit01Entity eva,EntryPlugCarrierEntity plug,RigidTransform from,RigidTransform to,UUID crane)
    {
        if(sources==null||!NervOriginalActorsR52.managed(plug)||!plug.isHatchFullySealed()||plug.getHatchOpenAmount()!=0||plug.getAssignedVariant()!=eva.getUnitVariant()
                ||!same(plug.getCanonicalTransform(),from)||!plug.isVehicle()||!(plug.getFirstPassenger() instanceof LivingEntity pilot)||pilot.getVehicle()!=plug)return false;
        var fleet=EvaFleetSavedData.get(l.getServer()).entry(eva.getUnitVariant()).orElse(null);if(fleet==null||!eva.getUUID().equals(fleet.canonicalId())||!plug.getUUID().equals(fleet.entryPlugId()))return false;
        // R50 scripted service follows the original sealed capsule; full mesh sweeps remain diagnostic.
        if(NervR50CarrierModeR53.enabled())return loaded(l,plug.getBoundingBox().move(to.translation().subtract(from.translation())));
        Set<UUID> own=new HashSet<>(Set.of(eva.getUUID(),plug.getUUID(),pilot.getUUID()));if(crane!=null)own.add(crane);var meshes=CAPSULES.get(eva.getUnitVariant());
        for(var mesh:meshes){var bound=mesh.envelope(from,to);if(!loaded(l,bound))return false;for(var shape:l.getBlockCollisions(plug,bound))for(var obstacle:shape.toAabbs())if(mesh.intersects(from,to,obstacle,.003))return false;for(var entity:l.getEntities((Entity)null,bound,e->!own.contains(e.getUUID())&&e.isAlive()&&(e instanceof LivingEntity||e.canBeCollidedWith())))if(mesh.intersects(from,to,entity.getBoundingBox(),.003))return false;}
        // Existing native passenger dimensions stay world aligned. The
        // capsule renderer and physical seat use the same original marker.
        var actual=pilot.getBoundingBox();var seat=from.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);if(actual.getCenter().distanceToSqr(seat)>1e-8)return false;
        double r=EntryPlugKinematics.PILOT_SEAT_P.length(),a=NervRigidMeshSweepR52.angular(from,to);int n=NervRigidMeshSweepR52.divisions(r,a,.003);double error=NervRigidMeshSweepR52.error(r,a,n);
        for(int i=0;i<n;i++){var first=from.interpolate(to,(double)i/n).transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var last=from.interpolate(to,(double)(i+1)/n).transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var box=actual.move(first.subtract(seat)).minmax(actual.move(last.subtract(seat))).inflate(error);if(!loaded(l,box)||l.getBlockCollisions(pilot,box).iterator().hasNext()||!l.getEntities((Entity)null,box,e->!own.contains(e.getUUID())&&e.isAlive()&&(e instanceof LivingEntity||e.canBeCollidedWith())).isEmpty())return false;}
        return true;
    }
    public static boolean clearFieldArc(ServerLevel l,EvaUnit01Entity e,EntryPlugCarrierEntity p,RigidTransform start,Vec3 escape,Vec3 landing)
    {
        if(sources==null||!p.isHatchFullySealed()||p.getFirstPassenger()==null)return false;Set<UUID> own=Set.of(e.getUUID(),p.getUUID(),p.getFirstPassenger().getUUID());var previous=start;
        var pilot=p.getFirstPassenger();var initialSeat=start.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var nativeBody=pilot.getBoundingBox();
        for(int age=1;age<=EntryPlugDirector.FIELD_EJECTION_TICKS;age++){var next=EntryPlugDirector.mappedFieldPoseR52(start,escape,landing,age);for(var mesh:CAPSULES.get(e.getUnitVariant())){var bounds=mesh.envelope(previous,next);if(!loaded(l,bounds))return false;for(var shape:l.getBlockCollisions(p,bounds))for(var b:shape.toAabbs())if(mesh.intersects(previous,next,b,.003))return false;for(var actor:l.getEntities((Entity)null,bounds,a->!own.contains(a.getUUID())&&a.isAlive()&&(a instanceof LivingEntity||a.canBeCollidedWith())))if(mesh.intersects(previous,next,actor.getBoundingBox(),.003))return false;}var first=previous.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var last=next.transformPoint(EntryPlugKinematics.PILOT_SEAT_P);var body=nativeBody.move(first.subtract(initialSeat)).minmax(nativeBody.move(last.subtract(initialSeat)));if(!loaded(l,body)||l.getBlockCollisions(pilot,body).iterator().hasNext()||!l.getEntities((Entity)null,body,a->!own.contains(a.getUUID())&&a.isAlive()&&(a instanceof LivingEntity||a.canBeCollidedWith())).isEmpty())return false;previous=next;}
        return true;
    }
    public static boolean applyInsertion(ServerLevel l,EvaUnit01Entity eva,EntryPlugCarrierEntity plug,RigidTransform from,RigidTransform to,UUID crane)
    {if(!clearCapsule(l,eva,plug,from,to,crane))return false;plug.setCanonicalTransform(to);plug.syncPilotPositionNow();return same(plug.getCanonicalTransform(),to)&&plug.getFirstPassenger()!=null&&plug.getFirstPassenger().getVehicle()==plug;}
    /** Exact imported carrier parts. At fixed outer frame their authored
     * rise channel is affine vertical motion, including the recovery deck. */
    public static boolean clearCarrierRise(ServerLevel l,EvaUnit01Entity eva,RigidTransform root,float from,float to,Set<UUID> own)
    {
        if(sources==null||from<0||from>1||to<0||to>1)return false;
        var selected=CarrierAssemblyR53.selected();
        if(selected!=null&&Math.min(from,to)<CarrierAssemblyR53.RISE_END&&Math.max(from,to)>CarrierAssemblyR53.RISE_END)
            return clearCarrierRise(l,eva,root,from,CarrierAssemblyR53.RISE_END,own)&&clearCarrierRise(l,eva,root,CarrierAssemblyR53.RISE_END,to,own);
        for(var row:CARRIERS.get(eva.getUnitVariant()*4+(eva.recoveryRackR39()?2:0)+(EvaMechanicalFrameR52.carrierDeckTravelR52(eva)==64?1:0)).entrySet())
        {
            if(row.getKey().startsWith("sole_bearing_")&&EvaMechanicalFrameR52.carrierDeckTravelR52(eva)!=64)continue;
            var mesh=row.getValue();double speed=row.getKey().equals("deck")?EvaMechanicalFrameR52.carrierDeckTravelR52(eva):64;
            double deckTravel=NervR50CarrierModeR53.enabled()?0:EvaMechanicalFrameR52.carrierDeckTravelR52(eva);
            var first=root.compose(selected==null?new RigidTransform(new Vec3(0,-speed*(1-from),0),0,0,0,1):selected.frame(row.getKey(),from,0,deckTravel));
            var end=root.compose(selected==null?new RigidTransform(new Vec3(0,-speed*(1-to),0),0,0,0,1):selected.frame(row.getKey(),to,0,deckTravel));var bound=mesh.envelope(first,end);
            if(!loaded(l,bound))return false;
            for(var shape:l.getBlockCollisions(eva,bound))for(var b:shape.toAabbs())if(mesh.intersects(first,end,b,.003))return false;
            for(var actor:l.getEntities((Entity)null,bound,e->!own.contains(e.getUUID())&&e.isAlive()&&(e instanceof LivingEntity||e.canBeCollidedWith())))if(mesh.intersects(first,end,actor.getBoundingBox(),.003))return false;
            for(var machine:l.getEntitiesOfClass(NervCarrierPlatformEntity.class,bound.inflate(80),m->m.isRestraintGantry()&&m.hasDeclaredMachineFrameR52()))
            {
                if(EvaMechanicalFrameR52.carrierDeckTravelR52(eva)==64&&machine.getUnitVariant()==eva.getUnitVariant()&&(!machine.lowerFrameDeclaredR52()||machine.lowerFrameProgressR52(1)!=1))return false;
                try{for(var actual:NervPlantMotionR52.actualRenderedMeshesR52(machine))if(mesh.intersects(first,end,actual.mesh(),actual.frame(),actual.endFrame(),.003,Vec3.ZERO))return false;}
                catch(IOException missing){return false;}
            }
        }
        return true;
    }
    public static FullAssemblyGeometryR52.Provider selectedMachinery(){if(sources==null)throw new IllegalStateException("Actual machinery source not installed");return sources;}
    /** A fully raised actuator is not itself a foot-bearing receipt. Require
     * finite, non-collinear real low-sole contacts on the selected deck. */
    public static boolean actualCarrierFootBearing(ServerLevel l,EvaUnit01Entity eva)
    {
        if(sources==null||eva.level()!=l||eva.carrierRiseProgress(1)!=1||!NervR50CarrierModeR53.enabled()&&EvaMechanicalFrameR52.carrierDeckTravelR52(eva)!=64)return false;
        var hardware=EvaMechanicalFrameR52.originalCarrierControllerR52(eva);if(hardware!=null)try{var actual=EvaMechanicalFrameR52.active(eva)?EvaMechanicalFrameR52.capturedGeometry(eva):EvaOriginalMeshGeometryR52.partsForCapture(eva,EvaBodyPose.sample(eva,1),EvaFrozenHandsR52.capture(eva,1));return NervOriginalCarrierR52.carrierFootBearingR52(l,hardware,eva,actual,NervOwnerPlacementR52.actualRoot(eva));}catch(IOException missing){return false;}
        if(EvaMechanicalFrameR52.carrierFrameR52(eva,1).translation().distanceToSqr(NervOwnerPlacementR52.actualRoot(eva).translation())>4e-6||EvaMechanicalFrameR52.carrierFrameR52(eva,1).rotationErrorDegrees(NervOwnerPlacementR52.actualRoot(eva))>.04)return false;
        var geometry=EvaMechanicalFrameR52.active(eva)?EvaMechanicalFrameR52.capturedGeometry(eva):EvaOriginalMeshGeometryR52.partsForCapture(eva,EvaBodyPose.sample(eva,1),EvaFrozenHandsR52.capture(eva,1));
        var parts=sources.carrierParts(eva.getUnitVariant(),1,eva.recoveryRackR39(),0,64);var surfaces=new ArrayList<double[]>();surfaces.add(parts.get("deck"));for(var entry:parts.entrySet())if(entry.getKey().startsWith("sole_bearing_"))surfaces.add(entry.getValue());int count=surfaces.stream().mapToInt(a->a.length).sum();double[] combined=new double[count];int n=0;for(var values:surfaces){System.arraycopy(values,0,combined,n,values.length);n+=values.length;}return actualDeckFootBearing(geometry,combined);
    }
    public static boolean actualDeckFootBearing(EvaOriginalMeshGeometryR52.Geometry geometry,double[] deck)
    {
        for(String bone:List.of("foot_l","foot_r"))
        {
            var contacts=new ArrayList<Vec3>();for(var part:geometry.parts())if(part.bone().equals(bone)){double low=part.bounds().minY;for(var p:part.vertices())if(p.y<=low+.002){double highest=surfaceHeight(deck,p.x,p.z);if(!Double.isFinite(highest)||Math.abs(p.y-highest)>.002)return false;contacts.add(p);}}
            boolean area=false;for(int a=0;a<contacts.size()&&!area;a++)for(int b=a+1;b<contacts.size()&&!area;b++)for(int c=b+1;c<contacts.size();c++){var x=contacts.get(a);var y=contacts.get(b);var z=contacts.get(c);if(Math.abs((y.x-x.x)*(z.z-x.z)-(z.x-x.x)*(y.z-x.z))>.0025){area=true;break;}}if(!area)return false;
        }
        return true;
    }
    /** Exact upward ray against the source triangle faces, without an AABB
     * top-plane surrogate or an invented sole/deck offset. */
    public static double surfaceHeight(double[] triangles,double x,double z)
    {
        double highest=Double.NEGATIVE_INFINITY;for(int i=0;i<triangles.length;i+=9){double ax=triangles[i],az=triangles[i+2],bx=triangles[i+3],bz=triangles[i+5],cx=triangles[i+6],cz=triangles[i+8],det=(bz-cz)*(ax-cx)+(cx-bx)*(az-cz);if(Math.abs(det)<1e-10)continue;double a=((bz-cz)*(x-cx)+(cx-bx)*(z-cz))/det,b=((cz-az)*(x-cx)+(ax-cx)*(z-cz))/det,c=1-a-b;if(a< -1e-8||b< -1e-8||c< -1e-8)continue;highest=Math.max(highest,a*triangles[i+1]+b*triangles[i+4]+c*triangles[i+7]);}return highest;
    }
    /** Prospective solid cells must also see the rendered deck/rack, which
     * the EVA's body-only vanilla bounding box does not contain. */
    public static boolean actualCarrierVisibleR52(EvaUnit01Entity eva)
    {return EvaMechanicalFrameR52.flightCustody(eva)?EvaMechanicalFrameR52.flightCarrierVisible(eva):(!EvaAirTransportR31.active(eva)||EvaMechanicalFrameR52.active(eva))&&(eva.hasActiveCarrierMotion()||EvaMechanicalFrameR52.active(eva)||EvaMechanicalFrameR52.plantCarrierDeclaredR52(eva)||eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR||eva.carrierRiseProgress(1)>.001F);}
    public static boolean clearCarrierClosure(ServerLevel level,EvaUnit01Entity eva,Collection<NervAssemblyOwnerR52.Cell> cells)
    {
        if(sources==null)return false;if(cells.stream().allMatch(c->level.hasChunkAt(c.at())&&level.getBlockState(c.at()).equals(c.closed())))return true;
        boolean visible=actualCarrierVisibleR52(eva);
        if(!visible)return true;var root=EvaMechanicalFrameR52.carrierFrameR52(eva,1);float rise=eva.carrierRiseProgress(1),release=eva.getLaunchPhase()==EvaUnit01Entity.LAUNCH_CLEAR?EvaDorsalMechanism.smooth(1-(eva.getLaunchTicks()-1)/18F):0;
        var meshes=new LinkedHashMap<NervRigidMeshSweepR52,RigidTransform>();for(var row:CARRIERS.get(eva.getUnitVariant()*4+(eva.recoveryRackR39()?2:0)+(EvaMechanicalFrameR52.carrierDeckTravelR52(eva)==64?1:0)).entrySet()){String name=row.getKey();if(name.startsWith("sole_bearing_")&&EvaMechanicalFrameR52.carrierDeckTravelR52(eva)!=64)continue;double speed=name.equals("deck")?EvaMechanicalFrameR52.carrierDeckTravelR52(eva):64;var local=new RigidTransform(new Vec3(0,-speed*(1-rise),name.equals("contact_pads")?1.5F*release:0),0,0,0,1);var selected=CarrierAssemblyR53.selected();if(selected!=null)local=selected.frame(name,rise,release,NervR50CarrierModeR53.enabled()?0:EvaMechanicalFrameR52.carrierDeckTravelR52(eva));meshes.put(row.getValue(),root.compose(local));}
        for(var cell:cells){if(!level.hasChunkAt(cell.at()))return false;if(level.getBlockState(cell.at()).equals(cell.closed()))continue;for(var local:cell.closed().getCollisionShape(level,cell.at()).toAabbs()){var obstacle=local.move(cell.at());for(var entry:meshes.entrySet()){var mesh=entry.getKey();var frame=entry.getValue();if(mesh.envelope(frame,frame).intersects(obstacle)&&mesh.intersects(frame,frame,obstacle,.003))return false;}}}return true;
    }
    private static boolean loaded(ServerLevel l,AABB b){for(int x=(int)Math.floor(b.minX)>>4;x<=((int)Math.floor(b.maxX)>>4);x++)for(int z=(int)Math.floor(b.minZ)>>4;z<=((int)Math.floor(b.maxZ)>>4);z++)if(l.getChunkSource().getChunkNow(x,z)==null)return false;return true;}
    private static boolean same(RigidTransform a,RigidTransform b){return a.translation().distanceToSqr(b.translation())<1e-8&&a.rotationErrorDegrees(b)<.01;}
    private NervMappedPlugMechanicsR52(){}
}

package com.projectseele.world;
import com.projectseele.entity.*;
import java.util.*;
import java.io.IOException;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.core.BlockPos;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;

/** The independent bay lift: real rest pads, supported T guides and an
 * actual sliding bridge. Inputs are the declared bay/hatch frames and one
 * accepted owner bridge sample; no map layout or secondary clock lives here. */
public final class NervServiceFootDriveR52 {
 public static final int BRIDGE_OPEN_TICKS=20,BRIDGE_CLOSE_TICKS=20;
 public record Piece(String name,double[] rgb,NervRigidMeshSweepR52 mesh,RigidTransform frame,boolean moving){}
 public record Spec(int variant,RigidTransform bay,RigidTransform hatch,double firstTier,double foundationTop){public Spec{if(variant<0||variant>2||!Double.isFinite(firstTier+foundationTop)||firstTier<=0)throw new IllegalArgumentException("Actual service drive frames/spec required");}}
 private static double smooth(double t){t=Math.max(0,Math.min(1,t));return t*t*t*(10+t*(-15+6*t));}
 public static RigidTransform footFrame(Spec s)throws IOException {var b=NervFootGuideRigR52.nominalBinding(s.variant());return NervFootGuideRigR52.bearingFrame(s.bay().transformPoint(b.contactCentre()),s.bay().transformVector(b.rightFoot().subtract(b.leftFoot())),new Vec3(0,1,0));}
 private static void triangle(List<Double> a,Vec3 p,Vec3 q,Vec3 r,int shade){for(var v:List.of(p,q,r)){a.add(v.x);a.add(v.y);a.add(v.z);a.add(shade/255D);a.add((shade+10)/255D);a.add((shade+14)/255D);}}
 public static double[] boxRgb(AABB b){var p=new Vec3[]{new Vec3(b.minX,b.minY,b.minZ),new Vec3(b.maxX,b.minY,b.minZ),new Vec3(b.maxX,b.maxY,b.minZ),new Vec3(b.minX,b.maxY,b.minZ),new Vec3(b.minX,b.minY,b.maxZ),new Vec3(b.maxX,b.minY,b.maxZ),new Vec3(b.maxX,b.maxY,b.maxZ),new Vec3(b.minX,b.maxY,b.maxZ)};int[] f={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};var out=new ArrayList<Double>();for(int n=0;n<f.length;n+=3)triangle(out,p[f[n]],p[f[n+1]],p[f[n+2]],75);return out.stream().mapToDouble(x->(float)(double)x).toArray();}
 public static Piece box(String name,AABB b,RigidTransform frame,boolean moving){var rgb=boxRgb(b);double[] xyz=new double[rgb.length/2];for(int i=0,n=0;i<rgb.length;i+=6){xyz[n++]=rgb[i];xyz[n++]=rgb[i+1];xyz[n++]=rgb[i+2];}return new Piece(name,rgb,new NervRigidMeshSweepR52(xyz),frame,moving);}
 private static AABB signed(AABB b,int side){double dx=NervFootGuideRigR52.AXIS_EXTENSION-15.25;return side>0?b.move(dx,0,0):new AABB(-b.maxX-dx,b.minY,b.minZ,-b.minX-dx,b.maxY,b.maxZ);}
 /** All walls/caps are physical boxes; the backing is hollow rather than
  * a filled AABB. Its 1m depth carries the two opposed guide contact faces. */
 public static List<Piece> tGuide(String name,int side,double lower,double upper,RigidTransform frame,boolean moving){if(upper<=lower)return List.of();var result=new ArrayList<Piece>();var rows=List.of(new AABB(15.22,lower,.72,15.28,upper,.88),new AABB(15.28,lower,.79,15.80,upper,.81),new AABB(15.75,lower,.30,15.80,upper,1.30),new AABB(16.40,lower,.30,16.45,upper,1.30),new AABB(15.80,lower,.30,16.40,upper,.35),new AABB(15.80,lower,1.25,16.40,upper,1.30),new AABB(15.80,lower,.35,16.40,Math.min(upper,lower+.05),1.25),new AABB(15.80,Math.max(lower,upper-.05),.35,16.40,upper,1.25));for(int i=0;i<rows.size();i++)result.add(box(name+"/"+i,signed(rows.get(i),side),frame,moving));return List.copyOf(result);}
 public static List<Piece> pieces(Spec s,double bridge)throws IOException {
  if(!Double.isFinite(bridge)||bridge<0||bridge>1)throw new IllegalArgumentException("Actual accepted bridge progress required");var frame=footFrame(s);double footY=frame.translation().y,floorTop=s.hatch().translation().y+.98,minimum=s.hatch().translation().y-(s.firstTier()+3.3)-.08-footY,maximum=floorTop+.08-footY;var out=new ArrayList<Piece>();double base=s.foundationTop()-footY,rest=-64D+(double)(float)-3.2;
  for(int side:new int[]{-1,1}){var restFrame=frame.compose(new RigidTransform(new Vec3(0,rest,0),0,0,0,1));out.add(box("service_rest_plinth/"+side,signed(new AABB(15.025,base-rest,.55,15.525,0,1.05),side),restFrame,false));out.addAll(tGuide("service_fixed_lower/"+side,side,base,minimum,frame,false));out.addAll(tGuide("service_fixed_upper/"+side,side,maximum,3.35,frame,false));double dy=bridge<=.8?-6.5*(1-smooth(bridge/.8)):0,dz=bridge<=.8?1.5:1.5*(1-smooth((bridge-.8)/.2));var moving=frame.compose(new RigidTransform(new Vec3(0,dy,dz),0,0,0,1));out.addAll(tGuide("service_bridge/"+side,side,minimum,maximum,moving,true));}return List.copyOf(out);
 }
 public static List<Piece> pieces(NervCarrierPlatformEntity machine,float partial)throws IOException {var spec=machine.declaredServiceFootDriveR52();return spec==null?List.of():pieces(spec,machine.serviceGuideBridgeR52(partial));}
 public static List<NervFlightProofR52.ObstacleMesh> actualMeshes(NervCarrierPlatformEntity machine)throws IOException {var out=new ArrayList<NervFlightProofR52.ObstacleMesh>();for(var p:pieces(machine,1))out.add(new NervFlightProofR52.ObstacleMesh(p.mesh(),p.frame()));return List.copyOf(out);}
 private static final Vec3 UP=new Vec3(0,1,0);
 /** Real bottom-face load path: the two carriage rest pads and four T-guide
  * backing walls sit on native pit-floor collision tops. */
 public static List<Vec3> foundationPoints(Spec s)throws IOException {var f=footFrame(s);double y=s.foundationTop()-f.translation().y,dx=NervFootGuideRigR52.AXIS_EXTENSION-15.25;var out=new ArrayList<Vec3>();for(int side:new int[]{-1,1})for(double[] p:new double[][]{{15.275,.8},{15.775,.8},{16.425,.8}})out.add(f.transformPoint(new Vec3(side*(p[0]+dx),y,p[1])));return List.copyOf(out);}
 public static boolean foundationsBear(ServerLevel l,Spec s)throws IOException {for(var p:foundationPoints(s)){var at=BlockPos.containing(p.subtract(UP.scale(.001)));if(!l.hasChunkAt(at))return false;boolean bears=false;for(var box:l.getBlockState(at).getCollisionShape(l,at).toAabbs()){var w=box.move(at);if(p.x>w.minX&&p.x<w.maxX&&p.z>w.minZ&&p.z<w.maxZ&&Math.abs(w.maxY-p.y)<.002)bears=true;}if(!bears)return false;}return true;}
 private static boolean joint(Piece a,Piece b){if(!a.moving()&&!b.moving())return true;Piece fixed=a.moving()?b:a,moving=a.moving()?a:b;if(fixed.moving())return false;var A=fixed.mesh().envelope(fixed.frame(),fixed.frame());var B=moving.mesh().envelope(moving.frame(),moving.frame());return (fixed.name().startsWith("service_fixed_")&&moving.name().startsWith("service_bridge/")&&(A.maxY<=B.minY+.000003||B.maxY<=A.minY+.000003));}
 /** Piecewise quintic translation is enclosed by subdivided vertex chords
  * plus its true second-derivative bound. The same accepted bridge sample
  * drives rendering, persistence and this admission. */
 public static boolean clearBridge(ServerLevel l,NervCarrierPlatformEntity machine,double from,double to,Set<UUID> own)throws IOException {
  var spec=machine.declaredServiceFootDriveR52();if(spec==null||!foundationsBear(l,spec)||!Double.isFinite(from)||!Double.isFinite(to)||from<0||from>1||to<0||to>1)return false;
  for(int division=0;division<16;division++){double a=from+(to-from)*division/16,b=from+(to-from)*(division+1)/16;var first=pieces(spec,a);var last=pieces(spec,b);double error=6*1.5/.2/.2*(b-a)*(b-a)/8+.000002;var allowance=new Vec3(error,error,error);
   for(int i=0;i<first.size();i++){var p=first.get(i);var q=last.get(i);if(!p.moving())continue;var box=p.mesh().envelope(p.frame(),q.frame()).inflate(error);if(!EntryPlugEjectionR48.loaded(l,box))return false;
    for(var shape:l.getBlockCollisions(machine,box))for(var obstacle:shape.toAabbs())if(p.mesh().intersects(p.frame(),q.frame(),obstacle.inflate(error),.001))return false;
    for(var actor:l.getEntities((Entity)null,box.inflate(80),e->!e.getUUID().equals(machine.getUUID())&&e.isAlive()&&(e.canBeCollidedWith()||e instanceof net.minecraft.world.entity.LivingEntity||e instanceof NervSiloDoorEntity||e instanceof NervHangarDoorEntity||e instanceof NervCarrierPlatformEntity))){var meshes=NervFlightProofR52.actualObstacleMeshes(actor);if(meshes==null)return false;if(meshes.isEmpty()){if(p.mesh().intersects(p.frame(),q.frame(),actor.getBoundingBox().inflate(error),.001))return false;}else for(var m:meshes)if(p.mesh().intersects(p.frame(),q.frame(),m.mesh(),m.frame(),m.endFrame(),.001,allowance))return false;}
    for(int j=0;j<first.size();j++){var other=first.get(j);if(i==j||other.moving()||joint(p,other)&&joint(q,last.get(j)))continue;if(p.mesh().intersects(p.frame(),q.frame(),other.mesh(),other.frame(),last.get(j).frame(),.001,allowance))return false;}
    for(var m:NervPlantMotionR52.actualStructuralMeshesR52(machine))if(p.mesh().intersects(p.frame(),q.frame(),m.mesh(),m.frame(),m.endFrame(),.001,allowance))return false;
   }
  }return true;
 }
 public static List<net.minecraft.world.phys.shapes.VoxelShape> collisions(NervCarrierPlatformEntity machine,float partial,AABB query)throws IOException {var out=new ArrayList<net.minecraft.world.phys.shapes.VoxelShape>();for(var p:pieces(machine,partial)){var b=p.mesh().envelope(p.frame(),p.frame());if(b.intersects(query))out.add(net.minecraft.world.phys.shapes.Shapes.create(b));}return List.copyOf(out);}
 private NervServiceFootDriveR52(){}
}

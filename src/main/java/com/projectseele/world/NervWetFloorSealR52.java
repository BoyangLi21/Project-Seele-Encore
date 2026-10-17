package com.projectseele.world;
import java.util.*;import net.minecraft.world.phys.*;

/** Optional real bottom seal carried by the existing wet-bay front door.
 * Native seats are explicit side-wall faces. The original door is untouched. */
final class NervWetFloorSealR52 {
 private record Element(NervAirframeGeometryR52.Part part,NervRigidMeshSweepR52 mesh,boolean moving,double liftFactor,double zFactor){}
 private final NervHangarGateGeometryR52.BottomSeal spec;private final List<Element> elements=new ArrayList<>();private final List<Vec3> seats=new ArrayList<>();private final Map<Float,AABB> boundsCache=new HashMap<>();
 private static final int[] FACES={0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5};
 NervWetFloorSealR52(NervHangarGateGeometryR52.Spec gate){spec=gate.bottomSeal();if(spec.version()==2){expanded(gate);return;}AABB b=null;int i=0;for(var box:spec.closedBoxes()){var q=box.bounds();b=b==null?q:b.minmax(q);add("leaf/"+i++,q,true,-1,1,78);}
  if(b==null||b.getXsize()>6||b.getZsize()>16||b.maxY>0||b.minY< -2)throw new IllegalArgumentException("Actual small below-floor seal footprint required");double low=b.minY-spec.dropM(),railTop=low-.60,baseY=low-.48,left=b.minX+.25,right=b.maxX-.25,originalStart=b.minZ-.35,start=b.minZ+1.25,end=b.maxZ+spec.retreatLocalZ()+.35,side=Math.signum(b.getCenter().x),wall=side*gate.width()/2;
  if(side==0||Math.abs(b.getCenter().x)<gate.width()/4)throw new IllegalArgumentException("Actual outer wet floor opening required");
  // Two grounded continuous rails, a real travelling carriage and four short
  // twelve-section hydraulic slides. Minimum overlap at4.2m is96mm.
  for(double x:new double[]{left,right})add("guide/"+x,new AABB(x-.06,railTop-.12,start,x+.06,railTop,end),false,0,0,74);
  add("carriage",new AABB(b.minX-.05,railTop,b.minZ+1.5,b.maxX+.05,baseY+.06,b.maxZ+.05),true,0,1,62);
  // The final eighty-millimetre leaf shares its edge with its thick neighbour.
  // The pit shutter runs below it; no actuator or cross-link enters that cell.
  final double hardwareStart=b.minZ+1.5;var centres=spec.closedBoxes().stream().map(q->q.bounds().getCenter()).filter(c->c.z>=hardwareStart).toList();
  // Connect actual L-shaped leaf centres below the original stationary floor.
  // Only pads inside declared leaf cells rise to their real bearing underside.
  var connected=new HashSet<Integer>();connected.add(0);int arm=0;
  while(connected.size()<centres.size()){double distance=Double.POSITIVE_INFINITY;int ai=-1,bi=-1;for(int aa:connected)for(int bb=0;bb<centres.size();bb++)if(!connected.contains(bb)){double dd=centres.get(aa).distanceToSqr(centres.get(bb));if(dd<distance){distance=dd;ai=aa;bi=bb;}}var A=centres.get(ai);var B=centres.get(bi);add("under_leaf_link/"+arm++,new AABB(Math.min(A.x,B.x)-.06,b.minY-.12,Math.min(A.z,B.z)-.06,Math.max(A.x,B.x)+.06,b.minY-.01,Math.max(A.z,B.z)+.06),true,-1,1,74);connected.add(bi);}
  int pad=0;for(var c:centres)add("owned_leaf_bearing/"+pad++,new AABB(c.x-.10,b.minY-.03,c.z-.10,c.x+.10,b.minY+.005,c.z+.10),true,-1,1,90);
  var posts=new ArrayList<Vec3>();double far=-1;for(var A:centres)for(var B:centres){double dd=A.distanceToSqr(B);if(dd>far){far=dd;posts.clear();posts.add(A);posts.add(B);}}while(posts.size()<4){Vec3 best=null;double score=-1;for(var C:centres){double nearest=Double.POSITIVE_INFINITY;for(var q:posts)nearest=Math.min(nearest,C.distanceToSqr(q));if(nearest>score){score=nearest;best=C;}}posts.add(best);}
  int post=0;for(var c:posts){double x=c.x,z=c.z;for(int k=0;k<12;k++){double w=.12-k*.003,y=baseY+.02+k*spec.dropM()/11;for(int face=0;face<4;face++){AABB tube=switch(face){case 0->new AABB(x-w,y,z-w,x-w+.00201,y+.48,z+w);case 1->new AABB(x+w-.00201,y,z-w,x+w,y+.48,z+w);case 2->new AABB(x-w+.00201,y,z-w,x+w-.00201,y+.48,z-w+.00201);default->new AABB(x-w+.00201,y,z+w-.00201,x+w-.00201,y+.48,z+w);};add("lift/"+post+"/"+k+"/"+face,tube,true,-k/11D,1,90);}}post++;}
  // Wall-supported transverse ties carry both rails, not floating slabs.
  int count=Math.max(1,(int)Math.ceil((end-originalStart)/6));for(int j=0;j<=count;j++){double z=j==0?start:originalStart+(end-originalStart)*j/count,y=railTop-.06;double inner=side<0?right+.06:left-.06;add("wall_tie/"+j,new AABB(Math.min(wall,inner),y-.06,z-.06,Math.max(wall,inner),y+.06,z+.06),false,0,0,74);
   // The original pit leaf crosses the former end hanger. Keep the rail tie
   // and carry it through real steel to the Root-verified fixed floor cap.
   double seatZ=j==0?b.minZ+3.5:z;
   if(j==0)add("end_wall_return/0",new AABB(side<0?wall:wall-.24,y-.12,Math.min(z,seatZ)-.12,side<0?wall+.24:wall,y+.12,Math.max(z,seatZ)+.12),false,0,0,74);
   add("native_wall_plate/"+j,new AABB(side<0?wall:wall-.05,y-.10,seatZ-.10,side<0?wall+.05:wall,y+.10,seatZ+.10),false,0,0,90);seats.add(new Vec3(wall,y,seatZ));}
  double centre=b.getCenter().x,shaftY=railTop-.28;add("lead_screw",new AABB(centre-.025,shaftY-.025,start,centre+.025,shaftY+.025,end),false,0,0,120);add("drive_motor",new AABB(centre-.22,shaftY-.18,end,centre+.22,shaftY+.18,end+.40),false,0,0,62);
  // A nut collar surrounds the shaft and is welded to the carriage underside.
  double nutZ=b.getCenter().z;for(int face=0;face<4;face++){AABB nut=switch(face){case 0->new AABB(centre-.08,shaftY-.08,nutZ-.10,centre-.025,shaftY+.08,nutZ+.10);case 1->new AABB(centre+.025,shaftY-.08,nutZ-.10,centre+.08,shaftY+.08,nutZ+.10);case 2->new AABB(centre-.025,shaftY-.08,nutZ-.10,centre+.025,shaftY-.025,nutZ+.10);default->new AABB(centre-.025,shaftY+.025,nutZ-.10,centre+.025,shaftY+.08,nutZ+.10);};add("drive_nut/"+face,nut,true,0,1,120);}add("nut_carriage_web",new AABB(centre-.06,shaftY+.06,nutZ-.06,centre+.06,railTop+.02,nutZ+.06),true,0,1,74);
 }
 private void expanded(NervHangarGateGeometryR52.Spec gate){
  var retained=spec.closedBoxes().subList(0,spec.retainedBoxCount());var legacy=new NervWetFloorSealR52(new NervHangarGateGeometryR52.Spec(gate.width(),gate.height(),gate.openTicks(),gate.closeTicks(),gate.depthDirection(),new NervHangarGateGeometryR52.BottomSeal(retained,spec.dropM(),spec.retreatLocalZ())));elements.addAll(legacy.elements);seats.addAll(legacy.seats);
  AABB old=null,b=null;for(var q:retained)old=old==null?q.bounds():old.minmax(q.bounds());int index=spec.retainedBoxCount();for(var q:spec.closedBoxes().subList(index,spec.closedBoxes().size())){b=b==null?q.bounds():b.minmax(q.bounds());add("leaf/"+index++,q.bounds(),true,-1,1,78);}
  if(old==null||b==null||old.getCenter().x>=0||b.maxX<=0||b.minX< -gate.width()/2||b.maxX>gate.width()/2||b.getZsize()>12||b.minY!=old.minY||b.maxY>0||b.minY< -2)throw new IllegalArgumentException("Explicit cross-bay extension must join the retained left mechanism and opposite wall inside the net opening");
  double low=b.minY-spec.dropM(),railTop=low-.60,baseY=low-.48,right=b.maxX-.5,start=b.getZsize()>4?b.minZ+.1:b.minZ-.35,end=b.maxZ+spec.retreatLocalZ()+.35,wall=gate.width()/2D;
  for(double x:new double[]{right-.25,right+.25})add("extension/guide/"+x,new AABB(x-.06,railTop-.12,start,x+.06,railTop,end),false,0,0,74);
  add("extension/carriage",new AABB(right-.5,railTop,b.getZsize()>4?b.minZ+.1:b.minZ-.05,right+.5,baseY+.06,b.maxZ+.05),true,0,1,62);
  var zs=new TreeSet<Double>();for(var q:spec.closedBoxes().subList(spec.retainedBoxCount(),spec.closedBoxes().size()))zs.add(q.bounds().getCenter().z);if(zs.size()<2||zs.size()>12)throw new IllegalArgumentException("Actual bounded front-row transverse members required");
  int cross=0;for(double z:zs){add("extension/transverse/"+cross++,new AABB(old.minX+.38,b.minY-.30,z-.12,right+.12,b.minY-.02,z+.12),true,-1,1,74);}
  int pad=0;for(var q:spec.closedBoxes().subList(spec.retainedBoxCount(),spec.closedBoxes().size())){var c=q.bounds().getCenter();add("extension/owned_leaf_bearing/"+pad++,new AABB(c.x-.10,b.minY-.03,c.z-.10,c.x+.10,b.minY+.005,c.z+.10),true,-1,1,90);}
  var postRows=new ArrayList<>(zs);if(postRows.size()>4){var all=new ArrayList<>(postRows);postRows=new ArrayList<>(List.of(all.get(0),all.get((all.size()-1)/3),all.get((all.size()-1)*2/3),all.get(all.size()-1)));add("extension/longitudinal_spine",new AABB(right-.12,b.minY-.30,zs.first()-.12,right+.12,b.minY-.02,zs.last()+.12),true,-1,1,74);}int post=0;for(double z:postRows){for(int k=0;k<12;k++){double w=.12-k*.003,y=baseY+.02+k*spec.dropM()/11;for(int face=0;face<4;face++){AABB tube=switch(face){case 0->new AABB(right-w,y,z-w,right-w+.00201,y+.48,z+w);case 1->new AABB(right+w-.00201,y,z-w,right+w,y+.48,z+w);case 2->new AABB(right-w+.00201,y,z-w,right+w-.00201,y+.48,z-w+.00201);default->new AABB(right-w+.00201,y,z+w-.00201,right+w-.00201,y+.48,z+w);};add("extension/lift/"+post+"/"+k+"/"+face,tube,true,-k/11D,1,90);}}post++;}
  int count=Math.max(1,(int)Math.ceil((end-start)/6));for(int i=0;i<=count;i++){double z=start+(end-start)*i/count,y=railTop-.06;add("extension/wall_tie/"+i,new AABB(right-.31,y-.06,z-.06,wall,y+.06,z+.06),false,0,0,74);double seatZ=b.getZsize()>4&&i==0?b.minZ+3.5:z;if(seatZ!=z)add("extension/end_wall_return/0",new AABB(wall-.24,y-.12,Math.min(z,seatZ)-.06,wall,y+.12,Math.max(z,seatZ)+.12),false,0,0,74);add("extension/native_wall_plate/"+i,new AABB(wall-.05,y-.10,seatZ-.10,wall,y+.10,seatZ+.10),false,0,0,90);seats.add(new Vec3(wall,y,seatZ));}
  double shaftY=railTop-.28;add("extension/lead_screw",new AABB(right-.025,shaftY-.025,start,right+.025,shaftY+.025,end),false,0,0,120);add("extension/drive_motor",new AABB(right-.22,shaftY-.18,end,right+.22,shaftY+.18,end+.40),false,0,0,62);
  double nutZ=b.getCenter().z;for(int face=0;face<4;face++){AABB nut=switch(face){case 0->new AABB(right-.08,shaftY-.08,nutZ-.10,right-.025,shaftY+.08,nutZ+.10);case 1->new AABB(right+.025,shaftY-.08,nutZ-.10,right+.08,shaftY+.08,nutZ+.10);case 2->new AABB(right-.025,shaftY-.08,nutZ-.10,right+.025,shaftY-.025,nutZ+.10);default->new AABB(right-.025,shaftY+.025,nutZ-.10,right+.025,shaftY+.08,nutZ+.10);};add("extension/drive_nut/"+face,nut,true,0,1,120);}add("extension/nut_carriage_web",new AABB(right-.06,shaftY+.06,nutZ-.06,right+.06,railTop+.02,nutZ+.06),true,0,1,74);
 }
 private void add(String name,AABB b,boolean moving,double lift,double z,int color){var p=new Vec3[]{new Vec3(b.minX,b.minY,b.minZ),new Vec3(b.maxX,b.minY,b.minZ),new Vec3(b.maxX,b.maxY,b.minZ),new Vec3(b.minX,b.maxY,b.minZ),new Vec3(b.minX,b.minY,b.maxZ),new Vec3(b.maxX,b.minY,b.maxZ),new Vec3(b.maxX,b.maxY,b.maxZ),new Vec3(b.minX,b.maxY,b.maxZ)};var values=new double[FACES.length*6];for(int i=0;i<FACES.length;i++){var v=p[FACES[i]];int n=i*6;values[n]=v.x;values[n+1]=v.y;values[n+2]=v.z;values[n+3]=color;values[n+4]=color+10;values[n+5]=color+14;}var part=new NervAirframeGeometryR52.Part("bottom_seal/"+name,values);elements.add(new Element(part,new NervRigidMeshSweepR52(part.xyz()),moving,lift,z));}
 private static double smooth(double t){t=Math.max(0,Math.min(1,t));return t*t*(3-2*t);}
 private RigidTransform frame(Element e,RigidTransform base,float p){return base.compose(new RigidTransform(new Vec3(0,e.liftFactor()*spec.dropM()*smooth(p/.25),e.zFactor()*spec.retreatLocalZ()*smooth((p-.25)/.75)),0,0,0,1));}
 List<NervHangarGateGeometryR52.Piece> pieces(float p){var rows=new ArrayList<NervHangarGateGeometryR52.Piece>();for(var e:elements)rows.add(new NervHangarGateGeometryR52.Piece(e.part(),frame(e,RigidTransform.identity(),p),e.moving()));return List.copyOf(rows);}
 List<Vec3> bearingPoints(){return List.copyOf(seats);}
 AABB bounds(float p){var known=boundsCache.get(p);if(known!=null)return known;AABB b=null;for(var e:elements){var q=e.mesh().envelope(frame(e,RigidTransform.identity(),p),frame(e,RigidTransform.identity(),p));b=b==null?q:b.minmax(q);}if(boundsCache.size()<512)boundsCache.put(p,b);return b;}
 private int divisions(float from,float to){return Math.max(1,(int)Math.ceil(Math.abs(to-from)*Math.sqrt(Math.max(spec.dropM()*6/(.25*.25),spec.retreatLocalZ()*6/(.75*.75))/(8*.003))));}
 // A clamped axis has no curvature error. Inflating it creates false
 // penetration into adjacent stationary floor cells at the first drop step.
 private Vec3 error(RigidTransform base,float a,float b,Element e){double h=b-a,dy=Math.min(a,b)>=.25?0:Math.abs(e.liftFactor())*spec.dropM()*6*h*h/(.25*.25*8),dz=Math.max(a,b)<=.25?0:Math.abs(e.zFactor())*spec.retreatLocalZ()*6*h*h/(.75*.75*8);var y=base.transformVector(new Vec3(0,1,0));var z=base.transformVector(new Vec3(0,0,1));return new Vec3(Math.abs(y.x)*dy+Math.abs(z.x)*dz,Math.abs(y.y)*dy+Math.abs(z.y)*dz,Math.abs(y.z)*dy+Math.abs(z.z)*dz);}
 List<AABB> envelopes(RigidTransform base,float from,float to){var result=new ArrayList<AABB>();int n=divisions(from,to);for(int k=0;k<n;k++){float a=from+(to-from)*k/n,b=from+(to-from)*(k+1)/n;for(var e:elements){var pad=error(base,a,b,e);for(var q:e.mesh().leafEnvelopes(frame(e,base,a),frame(e,base,b)))result.add(e.moving()?q.inflate(pad.x,pad.y,pad.z):q);}}return List.copyOf(result);}
 boolean intersects(RigidTransform base,float from,float to,AABB obstacle){
  if(!NervRigidMeshSweepR52.transformed(bounds(from).minmax(bounds(to)),base).intersects(obstacle))return false;
  // Against a stationary block, monotone easing traverses exactly the same
  // straight sweep. Split at the real drop/retreat corner; padding the curve
  // beyond its endpoint falsely penetrates the untouched pocket end wall.
  if(Math.min(from,to)<.25F&&Math.max(from,to)>.25F)
   return straightBlockSweep(base,from,.25F,obstacle)||straightBlockSweep(base,.25F,to,obstacle);
  return straightBlockSweep(base,from,to,obstacle);
 }
 private boolean straightBlockSweep(RigidTransform base,float from,float to,AABB obstacle){
  for(var e:elements)if(e.mesh().intersects(frame(e,base,from),frame(e,base,to),obstacle,.003))return true;
  return false;
 }
 boolean intersects(RigidTransform base,float from,float to,NervRigidMeshSweepR52 obstacle,RigidTransform obstacleFrom,RigidTransform obstacleTo){if(!NervRigidMeshSweepR52.transformed(bounds(from).minmax(bounds(to)),base).intersects(obstacle.envelope(obstacleFrom,obstacleTo)))return false;int n=divisions(from,to);for(int k=0;k<n;k++){float a=from+(to-from)*k/n,b=from+(to-from)*(k+1)/n;var oa=obstacleFrom.interpolate(obstacleTo,k/(double)n);var ob=obstacleFrom.interpolate(obstacleTo,(k+1D)/n);for(var e:elements){var pad=error(base,a,b,e);if(e.mesh().intersects(frame(e,base,a),frame(e,base,b),obstacle,oa,ob,.003,e.moving()?pad:Vec3.ZERO))return true;}}return false;}
}

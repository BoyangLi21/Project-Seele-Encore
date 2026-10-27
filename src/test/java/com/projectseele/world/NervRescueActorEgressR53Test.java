package com.projectseele.world;
import java.util.*;
import net.minecraft.world.phys.*;
public final class NervRescueActorEgressR53Test {
 static int checks;static void check(boolean x,String s){checks++;if(!x)throw new AssertionError(s);}
 static RigidTransform at(double x,double y,double z){return new RigidTransform(new Vec3(x,y,z),0,0,0,1);}
 static double[] vertical(double y){return new double[]{-1,y-1,0,1,y-1,0,0,y+1,0};}
 static double[] floor(double y){return new double[]{-2,y,-2,2,y,-2,0,y,2};}
 static NervRescueActorEgressR53 make(List<double[]> cargo,List<double[]> peer){var parts=new ArrayList<EvaOriginalMeshGeometryR52.Part>();for(var a:cargo)parts.add(new EvaOriginalMeshGeometryR52.Part("body","test","test",a,new AABB(-10,-10,-10,10,10,10)));return new NervRescueActorEgressR53(new EvaOriginalMeshGeometryR52.Geometry(2,"test",parts),at(0,0,0),peer.stream().map(NervRigidMeshSweepR52::new).toList(),at(0,0,0));}
 public static void main(String[] args){var zero=at(0,0,0);var e=make(List.of(vertical(0)),List.of(floor(0)));
 check(e.separates(zero,zero),"stationary initial body contact");check(e.separates(zero,at(0,2,0)),"finite upward exit");check(e.separates(at(0,.5,0),at(0,2,0)),"same captured later prefix");
 check(!e.separates(zero,at(.01,2,0)),"horizontal motion rejected");check(!e.separates(zero,at(0,-.01,0)),"downward motion rejected");check(!e.separates(at(0,.5,0),at(0,.4,0)),"backward later step rejected");check(!e.separates(at(0,1.1,0),at(0,2,0)),"permission expires beyond separation");
 check(!e.separates(zero,new RigidTransform(new Vec3(0,1,0),0,.1f,0,.9949874f)),"rotation rejected");
 var overhead=make(List.of(vertical(0)),List.of(floor(0),floor(3)));check(overhead.separates(zero,at(0,1.5,0)),"clear before later part");check(!overhead.separates(zero,at(0,2.5,0)),"new peer part entry rejected");
 var newBody=make(List.of(vertical(0),vertical(-3)),List.of(floor(0)));check(!newBody.separates(zero,at(0,2.5,0)),"new disconnected moving part rejected");
 var noContact=make(List.of(vertical(-3)),List.of(floor(0)));check(!noContact.separates(zero,at(0,4,0)),"no initial contact gives no permission");
 var apart=make(List.of(new double[]{3,0,0,4,0,0,3,0,1}),List.of(floor(0)));check(!apart.separates(zero,zero),"coplanar disjoint surfaces stay disjoint");
 var coplanar=make(List.of(floor(0)),List.of(floor(0)));check(!coplanar.separates(zero,at(0,1,0)),"coplanar touching has no native penetration permission");
 check(!e.separates(at(.01,0,0),at(.01,1,0)),"changed initial x rejected");
 check(!e.separates(zero,at(0,Double.NaN,0)),"nonfinite movement rejected");
 var fragment=make(List.of(vertical(0),new double[]{9,9,9,9,9,9,9,9,9}),List.of(floor(0)));check(fragment.separates(zero,at(0,2,0)),"zero-area exported fragment does not throw or invalidate unrelated contact");
 var degenerate=make(List.of(new double[]{0,-1,0,0,0,0,0,1,0}),List.of(floor(0)));check(degenerate.separates(zero,at(0,2,0)),"native SAT line contact retains a finite upward separation interval");
 var continuous=make(List.of(vertical(0)),List.of(floor(0),floor(1.5)));check(continuous.separates(zero,at(0,3,0)),"one frozen body remains in continuous initial overlap across exported parts");
 check(!continuous.separates(at(0,2.6,0),at(0,3,0)),"complete body exit still expires");
 var gap=make(List.of(vertical(0)),List.of(floor(0),floor(1.5),floor(5)));check(!gap.separates(zero,at(0,4.5,0)),"new contact after whole-body separation remains blocked");
 var assembly=new EvaOriginalMeshGeometryR52.Geometry(1,"test",List.of(new EvaOriginalMeshGeometryR52.Part("body","test","test",vertical(0),new AABB(-1,-1,0,1,1,0)),new EvaOriginalMeshGeometryR52.Part("original-plug","test","test",vertical(-3),new AABB(-1,-4,0,1,-2,0))));
 var trapped=new NervRescueActorEgressR53(assembly,zero,List.of(new NervRigidMeshSweepR52(floor(0))),zero,new Vec3(0,1,0),true);
 check(trapped.separates(zero,at(0,5,0)),"complete captured original assembly exits the same equipment including its plug");
 check(!trapped.separates(zero,at(1,5,0)),"chosen extraction ray cannot silently change");
 check(!trapped.separates(at(0,5,0),at(0,6,0)),"complete assembly permission expires after leaving equipment");
 var sideMesh=new double[]{0,-2,-2,0,2,-2,0,0,2};
 var sideBody=new double[]{-1,0,0,1,0,0,0,0,1};
 var sideGeometry=new EvaOriginalMeshGeometryR52.Geometry(1,"test",List.of(new EvaOriginalMeshGeometryR52.Part("body","test","test",sideBody,new AABB(-1,0,0,1,0,1))));
 var sideExit=new NervRescueActorEgressR53(sideGeometry,zero,List.of(new NervRigidMeshSweepR52(sideMesh)),zero,new Vec3(1,0,0),true);
 check(sideExit.separates(zero,at(2,0,0)),"horizontal mechanical extraction uses the same complete source math");
 check(!sideExit.separates(zero,at(-2,0,0)),"reverse movement does not reuse a forward receipt");
 check(!sideExit.separates(zero,new RigidTransform(new Vec3(2,0,0),0,.1f,0,.9949874f)),"posture cannot rotate while still extracting");
 var snapshot=new NervStationaryActorContactR54.Snapshot("source",List.of(new NervFlightProofR52.ObstacleMesh(new NervRigidMeshSweepR52(sideMesh),zero)));
 check(snapshot.current(new NervStationaryActorContactR54.Snapshot("source",List.of(new NervFlightProofR52.ObstacleMesh(new NervRigidMeshSweepR52(sideMesh),zero)))),"identical rebuilt source retained");
 check(!snapshot.current(new NervStationaryActorContactR54.Snapshot("changed",snapshot.meshes())),"changed assembly source invalidates receipt");
 check(!snapshot.current(new NervStationaryActorContactR54.Snapshot("source",List.of(new NervFlightProofR52.ObstacleMesh(new NervRigidMeshSweepR52(sideMesh),at(0,.01,0))))),"actual obstacle movement invalidates receipt");
 var diagonalFloor=new double[]{-10,0,-10,200,0,-10,-10,0,200};
 var diagonalBody=new EvaOriginalMeshGeometryR52.Geometry(1,"test",List.of(new EvaOriginalMeshGeometryR52.Part("body","test","test",vertical(0),new AABB(-1,-1,0,1,1,0))));
 var diagonal=new NervRescueActorEgressR53(diagonalBody,zero,List.of(new NervRigidMeshSweepR52(diagonalFloor)),zero,new Vec3(1e-7,0,1e-7),true);
 var previous=zero;double inv=Math.sqrt(.5);
 for(double distance:new double[]{1e-7,1e-5,.001,.1,1,16,48,96})
 {
  var next=at(distance*inv,0,distance*inv);
  check(diagonal.separates(previous,next),"tiny diagonal start through full 96m continuous extraction: "+distance);previous=next;
 }
 check(diagonal.separates(at(96*inv+.002,0,96*inv-.002),at(97*inv+.002,0,97*inv-.002)),"sub-collision-precision lateral error is tolerated");
 check(!diagonal.separates(at(96*inv+.01,0,96*inv-.01),at(97*inv+.01,0,97*inv-.01)),"actual lateral departure remains rejected");
 check(!diagonal.separates(at(200*inv,0,200*inv),at(201*inv,0,201*inv)),"diagonal receipt expires after complete finite exit");
 System.out.println("PASS R53 frozen actor contact intervals: "+checks);
 }
}

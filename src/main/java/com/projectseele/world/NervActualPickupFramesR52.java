package com.projectseele.world;
import com.projectseele.world.NervAirTransportManifestR52.*;
import net.minecraft.world.phys.Vec3;

/** Translate only Root's existing pickup and adjacent vertical cruise nodes.
 * Cruise heights and every other declared node remain authored by Root. */
public final class NervActualPickupFramesR52 {
 public static boolean pickupCruise(NervAirTransportManifestR52 m,Mission job,String node){
  for(String id:job.loaded()){var c=m.corridor(id);if(c.from().equals(job.pickupNode()))return c.to().equals(node);}
  return false;
 }
 public static Frame at(NervAirTransportManifestR52 m,Mission job,String node,RigidTransform actualPickup,boolean loaded){
  var declared=m.node(node).frame();var reference=m.node(job.pickupNode()).frame().cargo();if(reference==null)throw new IllegalArgumentException("Root pickup cargo datum required");var delta=actualPickup.translation().subtract(reference.translation());boolean pickup=node.equals(job.pickupNode()),cruise=pickupCruise(m,job,node);var plane=declared.plane();RigidTransform cargo=loaded?declared.cargo():null;
  if(pickup){plane=RigidTransform.of(plane.translation().add(delta),plane.rotation());if(loaded)cargo=actualPickup;}
  else if(cruise){if(declared.cargo()==null||Math.abs(declared.cargo().translation().x-reference.translation().x)>1e-5||Math.abs(declared.cargo().translation().z-reference.translation().z)>1e-5)throw new IllegalArgumentException("Root pickup cruise must be its actual vertical continuation");double lift=0;if(m.pickupVerticalClearanceR52()>0){double actualPickupPlaneY=m.node(job.pickupNode()).frame().plane().translation().y+delta.y;lift=Math.max(0,actualPickupPlaneY+m.pickupVerticalClearanceR52()-plane.translation().y);}var continuation=new Vec3(delta.x,lift,delta.z);plane=RigidTransform.of(plane.translation().add(continuation),plane.rotation());if(loaded)cargo=RigidTransform.of(cargo.translation().add(continuation),cargo.rotation());}
  return new Frame(plane,cargo,new Rig(declared.rig().hoist(),loaded?1:0,loaded?0:1));
 }
 private NervActualPickupFramesR52(){}
}

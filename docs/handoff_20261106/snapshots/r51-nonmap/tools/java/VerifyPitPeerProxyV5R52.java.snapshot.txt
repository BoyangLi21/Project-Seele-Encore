package com.projectseele.world;
import com.google.gson.*;
import com.projectseele.entity.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.*;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import org.joml.Quaternionf;
import net.minecraft.world.phys.Vec3;
/** Actual Owner policy and entity mesh-dispatch checks; no World/game. */
public final class VerifyPitPeerProxyV5R52 {
 static int checks;static void need(boolean p,String s){if(!p)throw new AssertionError(s);checks++;}
 static Method method(Class<?> c,String s,Class<?>...t)throws Exception{var m=c.getDeclaredMethod(s,t);m.setAccessible(true);return m;}
 static RigidTransform frame(JsonObject g){var f=g.getAsJsonObject("frame");var p=f.getAsJsonArray("position");var q=f.getAsJsonArray("quaternion");return RigidTransform.of(new Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()),new Quaternionf(q.get(0).getAsFloat(),q.get(1).getAsFloat(),q.get(2).getAsFloat(),q.get(3).getAsFloat()));}
 public static void main(String[] args)throws Exception {
  SharedConstants.tryDetectVersion();Bootstrap.bootStrap();
  var motion=method(NervAssemblyOwnerR52.class,"wetSealMotionPermitR52",boolean.class,boolean.class,boolean.class);
  need(!(boolean)motion.invoke(null,false,true,false),"actual dry/visual0/body-clear cannot move bottom while PIT closed");need((boolean)motion.invoke(null,false,true,true),"actual dry and actual open PIT permits subsequent real sweep");need(!(boolean)motion.invoke(null,false,false,true),"wet bay cannot move bottom even with open PIT");need((boolean)motion.invoke(null,true,false,false),"already closed target can be read with closed PIT without moving");
  var peer=method(NervAssemblyOwnerR52.class,"wetPeerProxyPermitR52",boolean.class,boolean.class,boolean.class,int.class,boolean.class,boolean.class);
  need((boolean)peer.invoke(null,true,true,true,14,true,true),"exact paired live closed Spec/14states/actual supports permit coarse dispatch");
  need(!(boolean)peer.invoke(null,false,true,true,14,true,true),"nonpaired door rejected");need(!(boolean)peer.invoke(null,true,false,true,14,true,true),"missing/wrong live UUID frame or Spec rejected");need(!(boolean)peer.invoke(null,true,true,false,14,true,true),"partly open peer rejected");need(!(boolean)peer.invoke(null,true,true,true,13,true,true),"missing owned proxy rejected");need(!(boolean)peer.invoke(null,true,true,true,14,false,true),"changed closed block state rejected");need(!(boolean)peer.invoke(null,true,true,true,14,true,false),"missing real native support rejected");
  var next=method(NervAssemblyOwnerR52.class,"nextAfterServiceBridgeCloseR52",boolean.class);need(next.invoke(null,true).equals("FRONT_SEAL_CLOSE"),"normal sealed return closes front before PIT");need(next.invoke(null,false).equals("PIT_CLOSE"),"legacy no-seal return remains compatible");
  var ready=method(NervAssemblyOwnerR52.class,"wetFrontReturnClosePermitR52",boolean.class,float.class,boolean.class,boolean.class,boolean.class);need((boolean)ready.invoke(null,true,0F,true,true,true),"actual lowered/dry/clamp/service bridge0/open PIT required for front return");need(!(boolean)ready.invoke(null,true,.1F,true,true,true),"raised carrier return rejected");need(!(boolean)ready.invoke(null,true,0F,false,true,true),"unclamped carrier return rejected");need(!(boolean)ready.invoke(null,true,0F,true,false,true),"open service bridge return rejected");need(!(boolean)ready.invoke(null,true,0F,true,true,false),"closed PIT front return rejected");
  var close=method(NervAssemblyOwnerR52.class,"wetPitClosePermitR52",boolean.class,boolean.class);need(!(boolean)close.invoke(null,true,false),"old unexpected PIT_CLOSE with front open must HOLD");need((boolean)close.invoke(null,true,true),"actual complete front/14seal close enables later PIT close");
  var sets=method(NervSiloDoorEntity.class,"peerProxySetsR52",Set.class,Set.class,Set.class);var cells=new HashSet<BlockPos>();for(int z=0;z<14;z++)cells.add(new BlockPos(85,-679,301+z));need((boolean)sets.invoke(null,Set.of(),Set.of(),cells),"peer14 remains separate from own moving and support sets");need(!(boolean)sets.invoke(null,cells,Set.of(),cells),"peer cells cannot be mixed into own closure volumes");need(!(boolean)sets.invoke(null,Set.of(),cells,cells),"peer cells cannot replace fixed supports");need(!(boolean)sets.invoke(null,Set.of(),Set.of(),null),"missing dispatch set rejected");
  var gates=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject().getAsJsonArray("gates");JsonObject pit=null,front=null;for(var r:gates){var g=r.getAsJsonObject();if(g.get("resource").getAsString().equals("bay_0_service_pit"))pit=g;if(g.get("resource").getAsString().equals("bay_0_front"))front=g;}
  var actual=JsonParser.parseString(Files.readString(Path.of(args[1]))).getAsJsonObject().getAsJsonArray("gates").get(0).getAsJsonObject().getAsJsonObject("actual_spec");var seal=actual.getAsJsonObject("bottomSeal");var boxes=new ArrayList<NervHangarGateGeometryR52.SealBox>();int thin=-1;for(var r:seal.getAsJsonArray("closedBoxes")){var b=r.getAsJsonObject();if(b.get("minY").getAsDouble()==-.01)thin=boxes.size();boxes.add(new NervHangarGateGeometryR52.SealBox(b.get("minX").getAsDouble(),b.get("minY").getAsDouble(),b.get("minZ").getAsDouble(),b.get("maxX").getAsDouble(),b.get("maxY").getAsDouble(),b.get("maxZ").getAsDouble()));}need(thin>=0,"actual selected V5 terminal leaf is10mm");
  var hs=new NervHangarGateGeometryR52.Spec(33,72,120,180,1,new NervHangarGateGeometryR52.BottomSeal(boxes,seal.get("dropM").getAsDouble(),seal.get("retreatLocalZ").getAsDouble()));var writer=method(NervHangarDoorEntity.class,"writeSpecR52",CompoundTag.class,NervHangarGateGeometryR52.Spec.class);var reader=method(NervHangarDoorEntity.class,"readSpec",CompoundTag.class);var tag=new CompoundTag();writer.invoke(null,tag,hs);need(hs.equals(reader.invoke(null,tag)),"actual V5 ten-mm double thickness native Spec roundtrip");
  var h=pit.getAsJsonObject("silo_hatch");var ps=new SiloHatchMechanism.Spec(h.get("opening_x").getAsFloat(),h.get("opening_z").getAsFloat(),h.get("open_ticks").getAsInt(),h.get("close_ticks").getAsInt(),h.get("separation_sign").getAsInt(),h.get("beam_bottom").getAsDouble(),true);var pg=NervSiloHatchGeometryR52.loadClasspath(ps);var fg=NervHangarGateGeometryR52.loadClasspath(hs);final int thinIndex=thin;var p0=fg.pieces(0).stream().filter(p->p.part().name().equals("bottom_seal/leaf/"+thinIndex)).findFirst().orElseThrow();var p1=fg.pieces(.05F).stream().filter(p->p.part().name().equals(p0.part().name())).findFirst().orElseThrow();var obstacle=new NervFlightProofR52.ObstacleMesh(new NervRigidMeshSweepR52(p0.part().xyz()),frame(front).compose(p0.local()),frame(front).compose(p1.local()));
  var dispatch=method(NervSiloDoorEntity.class,"actualGateMeshIntersectsR52",NervSiloHatchGeometryR52.class,RigidTransform.class,float.class,float.class,NervFlightProofR52.ObstacleMesh.class);
  need((boolean)dispatch.invoke(null,pg,frame(pit),0F,0F,obstacle),"actual real thin leaf crossing CLOSED PIT remains blocked despite native proxy dispatch");
  need(!(boolean)dispatch.invoke(null,pg,frame(pit),1F,1F,obstacle),"same selected thin leaf initial motion is clear only against actual OPEN PIT");
  System.out.println("Actual Owner policy/return order/peer-set boundaries/V5 real mesh dispatch PASS="+checks+"; no World/game/installation");
 }
}

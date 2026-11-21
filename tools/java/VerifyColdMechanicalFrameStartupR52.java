package com.projectseele.entity;

import com.google.gson.*;
import com.projectseele.world.*;
import java.lang.reflect.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.nbt.*;
import net.minecraft.world.level.Level;
import net.minecraft.world.phys.*;
import org.joml.Quaternionf;
import sun.misc.Unsafe;

/** Actual packaged mesh + native NBT cold input, in memory only. */
public final class VerifyColdMechanicalFrameStartupR52 {
 static final Unsafe U;static int checks,serial;
 static {try{var f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);U=(Unsafe)f.get(null);}catch(Exception e){throw new RuntimeException(e);}}
 static void need(boolean b,String m){if(!b)throw new AssertionError(m);checks++;}
 static Field field(Class<?> c,String n)throws Exception{for(;c!=null;c=c.getSuperclass())try{var f=c.getDeclaredField(n);f.setAccessible(true);return f;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(n);}
 static final class ColdEva extends EvaUnit01Entity {
  Level clock;SynchedEntityData values;
  ColdEva(){super(null,null);}
  public Level level(){return clock;}public SynchedEntityData getEntityData(){return values;}
  public int getUnitVariant(){return 0;}public boolean isExperimentalUnit(){return false;}
  public boolean isNervLogisticsLocked(){return true;}public boolean isFirstBattleActive(){return false;}public boolean isBerserk(){return false;}public int getWeapon(){return WEAPON_FISTS;}
  public Set<String> getTags(){return Set.of();}
 }
 static ColdEva actor()throws Exception{
  var e=(ColdEva)U.allocateInstance(ColdEva.class);e.clock=(ServerLevel)U.allocateInstance(ServerLevel.class);
  var id=field(net.minecraft.world.entity.Entity.class,"id");U.putInt(e,U.objectFieldOffset(id),++serial);
  var f=field(ServerLevel.class,"levelData");var data=Proxy.newProxyInstance(f.getType().getClassLoader(),new Class<?>[]{f.getType()},(p,m,a)->{if(m.getReturnType()==long.class)return 100L;if(m.getReturnType()==int.class)return 0;if(m.getReturnType()==boolean.class)return false;if(m.getReturnType()==float.class)return 0F;return null;});U.putObject(e.clock,U.objectFieldOffset(f),data);
  e.values=new SynchedEntityData(e);EvaMechanicalFrameR52.define(e.values);EvaAirTransportR31.define(e.values);EvaDorsalMechanism.define(e.values);return e;
 }
 static boolean denied(Runnable action){try{action.run();return false;}catch(IllegalStateException held){return true;}}
 static CompoundTag transform(){var t=new CompoundTag();t.putDouble("X",12);t.putDouble("Y",-614);t.putDouble("Z",302);t.putFloat("QX",0);t.putFloat("QY",0);t.putFloat("QZ",0);t.putFloat("QW",1);return t;}
 static CompoundTag active(){var t=new CompoundTag();t.putBoolean("Active",true);t.putLong("CapturedAt",52);t.putLong("AcceptedAt",100);t.putLong("Epoch",52);t.put("Current",transform());t.put("Previous",transform());t.putFloat("BaseYaw",180);var root=new CompoundTag();root.put("R52MechanicalSample",t);return root;}
 static String geometryHash(EvaOriginalMeshGeometryR52.Geometry geometry)throws Exception{var d=MessageDigest.getInstance("SHA-256");for(var p:geometry.parts()){d.update(p.bone().getBytes(java.nio.charset.StandardCharsets.UTF_8));for(double v:p.triangles())d.update(java.nio.ByteBuffer.allocate(8).putLong(Double.doubleToRawLongBits(v)).array());}return HexFormat.of().formatHex(d.digest());}
 public static void main(String[] args)throws Exception{
  for(String key:List.of("projectseele.r44CapturedSupportOwnership","projectseele.weaponHandlingReviewR45","projectseele.r45CannonContactCandidate","projectseele.r44TvCageReview","projectseele.r44TvPersonnelPlatformsReview"))System.setProperty(key,"false");System.setProperty("projectseele.capturedLocomotionDirectory","");
  System.setProperty("projectseele.bodyPoseReviewDirectory",args[0]);System.setProperty("projectseele.gameplayReviewDirectory",args[0]);System.setProperty("projectseele.bodyPhysicsProfiles",Path.of(args[0]).resolve("articulated_bodies_r35.json").toString());
  var eventLists=Class.forName("com.projectseele.entity.EvaKnifeRecoveryR52Test").getDeclaredMethod("dataOnlyEventLists");eventLists.setAccessible(true);eventLists.invoke(null);SharedConstants.tryDetectVersion();Bootstrap.bootStrap();
  Path out=Path.of(args[1]);Files.createDirectories(out);var cold=actor();var saved=active();EvaMechanicalFrameR52.load(cold,saved);
  need(!EvaMechanicalFrameR52.geometryReadyR52(),"Cold process was already warmed");
  var held=new CountDownLatch(1);var release=new CountDownLatch(1);var monitor=new Thread(()->{synchronized(EvaMechanicalFrameR52.class){held.countDown();try{release.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}}});monitor.start();held.await();
  long begin=System.nanoTime();boolean rejected;try{rejected=denied(()->EvaMechanicalFrameR52.capturedGeometry(cold));}finally{release.countDown();monitor.join();}double elapsed=(System.nanoTime()-begin)/1e6;
  need(rejected&&elapsed<100,"Cold server source gate blocked on installation monitor or accepted missing geometry");need(!EvaMechanicalFrameR52.geometryReadyR52(),"Cold entity performed source IO");
  var heldTag=new CompoundTag();heldTag.putBoolean("ServiceSourceHeldR52",true);var heldSaved=new CompoundTag();heldSaved.put("R52MechanicalSample",heldTag);var service=actor();EvaMechanicalFrameR52.load(service,heldSaved);need(denied(()->EvaMechanicalFrameR52.serviceGeometryR52(service)),"Missing held source was falsely accepted");
  begin=System.nanoTime();EvaMechanicalFrameR52.prepareBeforeServerLoadR52(new net.minecraftforge.event.server.ServerAboutToStartEvent(null));double prepareMs=(System.nanoTime()-begin)/1e6;need(EvaMechanicalFrameR52.geometryReadyR52(),"Startup pure-source hook did not publish actual provider");var provider=EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52();EvaMechanicalFrameR52.installGeometry();need(provider==EvaOriginalMeshGeometryR52.readOnlySelectedProviderR52(),"Owner warmup duplicated startup provider");
  var body=EvaBodyPose.neutralForTransportR32(cold);var joints=new HashMap<String,Quaternionf>();var geo=JsonParser.parseString(new String(EvaOriginalMeshGeometryR52.classpathBytes("geo/eva_unit00.geo.json"),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
  for(var row:geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones")){var b=row.getAsJsonObject();String n=b.get("name").getAsString();if(!provider.handJoints(0).contains(n))continue;var q=new Quaternionf();if(b.has("rotation")){var a=b.getAsJsonArray("rotation");q.rotationZYX((float)Math.toRadians(a.get(2).getAsFloat()),-(float)Math.toRadians(a.get(1).getAsFloat()),-(float)Math.toRadians(a.get(0).getAsFloat()));}joints.put(n,q);}
  var hands=new EvaAnatomicalHandsR45.Pose("actual_bind","actual_bind",Map.copyOf(joints));var snapshot=EvaFrozenHandsR52.encode(0,provider.handContractFingerprint(0),hands);var origin=new CompoundTag();origin.putBoolean("MechanicalFrameR52",true);origin.put("Origin",EvaShutdownR30.encode(body));origin.put(EvaFrozenHandsR52.KEY,snapshot);origin.putString("GeometrySourceR52",provider.sourceFingerprint());saved.put("R31AirCradle",origin);
  NbtIo.writeCompressed(saved,out.resolve("ACTUAL_SOURCE_COLD_ACTIVE_INPUT.nbt").toFile());var disk=NbtIo.readCompressed(out.resolve("ACTUAL_SOURCE_COLD_ACTIVE_INPUT.nbt").toFile());var restored=actor();EvaAirTransportR31.load(restored,disk);EvaMechanicalFrameR52.load(restored,disk);need(EvaMechanicalFrameR52.active(restored),"Cold Active state lost");
  var actual=EvaMechanicalFrameR52.capturedGeometry(restored);var expected=provider.evaluate(0,body,hands);need(geometryHash(actual).equals(geometryHash(expected)),"Cold actual source triangles differ");need(actual==EvaMechanicalFrameR52.capturedGeometry(restored),"Cold capture was not cached");var bounds=EvaMechanicalFrameR52.bounds(restored);need(bounds.getXsize()>0&&bounds.getYsize()>50&&bounds.getZsize()>0,"Cold actual full mesh bounds absent");
  var roundtrip=new CompoundTag();EvaMechanicalFrameR52.save(restored,roundtrip);need(roundtrip.getCompound("R52MechanicalSample").equals(disk.getCompound("R52MechanicalSample")),"Cold sample changed saved root/identity/clock");
  heldTag.putString("HeldGeometrySource",provider.sourceFingerprint());heldTag.put("HeldBody",EvaShutdownR30.encode(body));heldTag.put("HeldHands",snapshot);heldTag.putFloat("HeldYaw",180);heldTag.putLong("HeldAt",52);EvaMechanicalFrameR52.load(service,heldSaved);var heldGeometry=EvaMechanicalFrameR52.serviceGeometryR52(service);need(heldGeometry.triangleCount()>0&&EvaMechanicalFrameR52.serviceBoundsR52(service).getYsize()>50,"Cold held source did not retain actual full geometry");
  var wrong=disk.copy();wrong.getCompound("R31AirCradle").putString("GeometrySourceR52","0".repeat(64));var mismatch=actor();EvaAirTransportR31.load(mismatch,wrong);EvaMechanicalFrameR52.load(mismatch,wrong);need(denied(()->EvaMechanicalFrameR52.capturedGeometry(mismatch)),"Wrong saved geometry source was accepted");
  var report=Map.of("checks",checks,"pending_gate_ms",elapsed,"startup_prepare_ms",prepareMs,"source_fingerprint",provider.sourceFingerprint(),"actual_body_triangles",actual.triangleCount(),"ordered_triangle_sha256",geometryHash(actual),"world_written",false,"game_started",false,"scope","Direct production startup handler, source gate and native cold Active/ServiceHeld NBT in memory. Forge source order independently pinned; not a native server startup claim.");Files.writeString(out.resolve("COLD_ACTIVE_SOURCE_GATE_RESULT.json"),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println(new Gson().toJson(report));
 }
}

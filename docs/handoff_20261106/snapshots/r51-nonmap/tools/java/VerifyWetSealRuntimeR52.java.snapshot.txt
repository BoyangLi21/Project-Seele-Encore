package com.projectseele.world;
import com.google.gson.*;
import com.projectseele.entity.NervHangarDoorEntity;
import java.lang.reflect.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.network.syncher.SynchedEntityData;
import net.minecraft.nbt.*;
import net.minecraft.world.phys.Vec3;
import net.minecraft.world.phys.AABB;
import sun.misc.Unsafe;
/** Calls actual production policy and native NBT read/add methods; no World/game/commission. */
public final class VerifyWetSealRuntimeR52 {
 static int count;static final Unsafe U;
 static {try{var f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);U=(Unsafe)f.get(null);}catch(Exception e){throw new RuntimeException(e);}}
 static void need(boolean p,String s){if(!p)throw new AssertionError(s);count++;}
 static Method method(Class<?> t,String name,Class<?>...types)throws Exception{var m=t.getDeclaredMethod(name,types);m.setAccessible(true);return m;}
 static Field field(Class<?> type,String name)throws Exception{for(var c=type;c!=null;c=c.getSuperclass())try{var f=c.getDeclaredField(name);f.setAccessible(true);return f;}catch(NoSuchFieldException ignored){}throw new NoSuchFieldException(name);}
 static void value(Object object,String name,Object value)throws Exception{var f=field(object.getClass(),name);U.putObject(object,U.objectFieldOffset(f),value);}
 static NervHangarDoorEntity door()throws Exception{
  var d=(NervHangarDoorEntity)U.allocateInstance(NervHangarDoorEntity.class);
  var level=(ServerLevel)U.allocateInstance(ServerLevel.class);var f=field(level.getClass(),"levelData");
  var data=Proxy.newProxyInstance(f.getType().getClassLoader(),new Class[]{f.getType()},(p,m,a)->{if(m.getReturnType()==long.class)return 100L;if(m.getReturnType()==int.class)return 0;if(m.getReturnType()==float.class)return 0F;if(m.getReturnType()==boolean.class)return false;return null;});
  value(level,"levelData",data);value(d,"level",level);value(d,"position",Vec3.ZERO);value(d,"entityData",new SynchedEntityData(d));value(d,"savedStackR52",new CompoundTag());
  method(NervHangarDoorEntity.class,"defineSynchedData").invoke(d);return d;
 }
 static CompoundTag saved(CompoundTag spec){var t=new CompoundTag();t.putInt("Version",52);t.put("Spec",spec.copy());t.putFloat("Raw",.4F);t.putFloat("Target",1);t.putInt("Variant",1);t.putFloat("ClockStart",0);t.putFloat("ClockGoal",1);t.putInt("ClockStep",40);t.putInt("ClockDuration",100);var out=new CompoundTag();out.put("R52SideStack",t);return out;}
 static boolean throwsInvocation(RunnableThrow f)throws Exception{try{f.run();return false;}catch(InvocationTargetException e){return e.getCause() instanceof RuntimeException;}}
 interface RunnableThrow{void run()throws Exception;}
 public static void main(String[] args)throws Exception {
  SharedConstants.tryDetectVersion();Bootstrap.bootStrap();
  var legacy=new NervHangarGateGeometryR52.Spec(33,72,120,180);need(legacy.bottomSeal()==null&&legacy.depthDirection()==1,"legacy4arg unchanged");
  need(new NervHangarGateGeometryR52.Spec(33,72,120,180,-1).bottomSeal()==null,"rear5arg unchanged");
  var boxes=new ArrayList<NervHangarGateGeometryR52.SealBox>();for(int z=0;z<14;z++)boxes.add(new NervHangarGateGeometryR52.SealBox(12,-1,z,13,0,z+1));
  var spec=new NervHangarGateGeometryR52.Spec(33,72,120,180,1,new NervHangarGateGeometryR52.BottomSeal(boxes,4.2,24));
  var write=method(NervHangarDoorEntity.class,"writeSpecR52",CompoundTag.class,NervHangarGateGeometryR52.Spec.class);var read=method(NervHangarDoorEntity.class,"readSpec",CompoundTag.class);
  var tag=new CompoundTag();write.invoke(null,tag,spec);var before=tag.copy();need(spec.equals(read.invoke(null,tag)),"actual Spec NBT roundtrip");need(before.equals(tag),"reader immutable");
  var compressed=java.nio.file.Path.of(args[0]);NbtIo.writeCompressed(saved(tag),compressed.toFile());var disk=NbtIo.readCompressed(compressed.toFile());
  var entity=door();method(NervHangarDoorEntity.class,"readAdditionalSaveData",CompoundTag.class).invoke(entity,disk);need(entity.matchesDeclaredR52(spec),"actual entity cold reader retains seal");need(Math.abs(entity.actualOpenProgressR52()-com.projectseele.entity.EvaDorsalMechanism.smooth(.4F))<1e-6,"actual partial clock/progress retained");
  var output=new CompoundTag();method(NervHangarDoorEntity.class,"addAdditionalSaveData",CompoundTag.class).invoke(entity,output);need(output.getCompound("R52SideStack").getCompound("Spec").equals(tag),"actual entity save retains full Spec");
  var old=new CompoundTag();write.invoke(null,old,legacy);old.remove("DepthDirection");need(legacy.equals(read.invoke(null,old)),"cold old missing depth/seal defaults compatible");
  var oldDoor=door();method(NervHangarDoorEntity.class,"readAdditionalSaveData",CompoundTag.class).invoke(oldDoor,saved(old));need(oldDoor.matchesDeclaredR52(legacy),"actual entity loads old no-seal tag");
  var bad=tag.copy();bad.getCompound("FloorSeal").putInt("Version",999);need(throwsInvocation(()->read.invoke(null,bad)),"unknown seal version rejects");
  var badSaved=saved(bad);var held=door();method(NervHangarDoorEntity.class,"readAdditionalSaveData",CompoundTag.class).invoke(held,badSaved);need(held.declaredGeometryMissingR52()&&!held.matchesDeclaredR52(spec),"invalid cold seal holds, cannot match live declaration");var heldOut=new CompoundTag();method(NervHangarDoorEntity.class,"addAdditionalSaveData",CompoundTag.class).invoke(held,heldOut);need(heldOut.equals(badSaved),"invalid original NBT preserved, no silent reset");
  var malformed=tag.copy();malformed.getCompound("FloorSeal").put("ClosedBoxes",new ListTag());need(throwsInvocation(()->read.invoke(null,malformed)),"empty seal boxes reject");
  var parse=method(NervAssemblyOwnerR52.class,"hangarSpec",JsonObject.class);var json=new JsonObject();json.addProperty("width",33);json.addProperty("height",72);var stack=new JsonObject();stack.addProperty("open_ticks",120);stack.addProperty("close_ticks",180);json.add("hangar_stack",stack);need(legacy.equals(parse.invoke(null,json)),"old Owner JSON stays legacy");
  var seal=new JsonObject();seal.addProperty("drop_m",4.2);seal.addProperty("retreat_local_z_m",24);var rows=new JsonArray();for(var b:boxes){var row=new JsonArray();for(double n:new double[]{b.minX(),b.minY(),b.minZ(),b.maxX(),b.maxY(),b.maxZ()})row.add(n);rows.add(row);}seal.add("closed_boxes",rows);stack.add("floor_seal",seal);need(spec.equals(parse.invoke(null,json)),"actual Owner JSON matches persisted seal Spec");
  var dry=method(NervAssemblyOwnerR52.class,"wetSealDryInputsR52",boolean.class,float.class);
  need(!(boolean)dry.invoke(null,false,0F),"fake visual empty cannot bypass actual wet44 layer");need(!(boolean)dry.invoke(null,true,1F),"actual dry with nonzero liquid sample blocks opening");need((boolean)dry.invoke(null,true,0F),"actual dry and zero sample permits subsequent geometry check");need(!(boolean)dry.invoke(null,true,Float.NaN)&&!(boolean)dry.invoke(null,true,Float.POSITIVE_INFINITY),"invalid liquid sample blocks");
  var data=new CompoundTag();data.putInt("FinishTicks",180);var calls=new AtomicInteger();
  need(!NervAssemblyOwnerR52.wetSealRefillReadyR52(false,false,0,data,()->{calls.incrementAndGet();return true;})&&calls.get()==0&&data.getInt("FinishTicks")==180,"wet actual bay cannot force closure/refill");
  need(!NervAssemblyOwnerR52.wetSealRefillReadyR52(false,true,1,data,()->{calls.incrementAndGet();return true;})&&calls.get()==0,"partial old refill cannot bypass unclosed seal");
  need(!NervAssemblyOwnerR52.wetSealRefillReadyR52(false,true,0,data,()->{calls.incrementAndGet();return false;})&&calls.get()==1&&data.getInt("FinishTicks")==180,"blocked real close holds original refill clock");
  need(!NervAssemblyOwnerR52.wetSealRefillReadyR52(false,true,0,data,()->true)&&data.getInt("FinishTicks")==0,"completed close cannot dump44 layers using closing age");
  need(NervAssemblyOwnerR52.wetSealRefillReadyR52(true,false,10,data,()->{throw new AssertionError("closed seal must not re-open or re-close");}),"closed actual seal allows exact partial-refill continuation");
  var face=method(NervHangarDoorEntity.class,"actualWetSealFaceR52",Vec3.class,Vec3.class,List.class);var p=new Vec3(89,-683.86,312.35);var normal=new Vec3(-1,0,0);
  need((boolean)face.invoke(null,p,normal,List.of(new AABB(89,-684,312,90,-683,313))),"actual .20m plate full native wall face bears");
  need(!(boolean)face.invoke(null,p,normal,List.of()),"air cannot bear real wall plate");
  need(!(boolean)face.invoke(null,p,normal,List.of(new AABB(89,-683.90,312.31,90,-683.82,312.39))),"centre-only small native shape cannot bear plate corners");
  need(!(boolean)face.invoke(null,p,normal,List.of(new AABB(89.01,-684,312,90,-683,313))),"wrong native face plane rejects");
  need(!(boolean)face.invoke(null,p,normal,List.of(new AABB(89,-684,312,90,-683.90,313))),"occupied lower native slab without plate face rejects");
  need((boolean)face.invoke(null,p,normal,List.of(new AABB(89,-684,312,90,-683.86,313),new AABB(89,-683.86,312,90,-683,313))),"actual connected native face union bears all nine points");
  var thinBoxes=new ArrayList<>(boxes);thinBoxes.set(13,new NervHangarGateGeometryR52.SealBox(12,-.08,13,13,0,14));var thin=new NervHangarGateGeometryR52.Spec(33,72,120,180,1,new NervHangarGateGeometryR52.BottomSeal(thinBoxes,4.2,24));var thinTag=new CompoundTag();write.invoke(null,thinTag,thin);
  need(thin.equals(read.invoke(null,thinTag)),"actual80mm leaf Spec persists exact double thickness without rounding to cube");
  var thinDoor=door();method(NervHangarDoorEntity.class,"readAdditionalSaveData",CompoundTag.class).invoke(thinDoor,saved(thinTag));need(thinDoor.matchesDeclaredR52(thin),"actual entity cold read accepts partial-thickness physical leaf");
  var thinOut=new CompoundTag();method(NervHangarDoorEntity.class,"addAdditionalSaveData",CompoundTag.class).invoke(thinDoor,thinOut);need(thinOut.getCompound("R52SideStack").getCompound("Spec").equals(thinTag),"actual cold/save roundtrip preserves80mm leaf and original clock fields");
  System.out.println("Actual production wet-seal policy / Owner JSON / entity NBT cold compatibility checks PASS="+count+"; no World/game/native commissioning");
 }
}

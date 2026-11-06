package com.projectseele.client.render;
import com.google.gson.*;
import com.projectseele.entity.EvaUnit01Entity;
import java.lang.reflect.*;
import java.nio.file.*;
import java.util.*;
import java.util.zip.ZipFile;
import net.minecraft.SharedConstants;
import net.minecraft.server.Bootstrap;
import org.joml.*;
import software.bernie.geckolib.cache.object.*;
import sun.misc.Unsafe;

/** Calls the complete old/new production apply against actual selected meshes. */
public final class VerifyHeadClearancePerfR52 {
 static final Unsafe U;static int checks;
 static {try{var f=Unsafe.class.getDeclaredField("theUnsafe");f.setAccessible(true);U=(Unsafe)f.get(null);}catch(Exception e){throw new RuntimeException(e);}}
 static final class Actor extends EvaUnit01Entity {float stance;boolean locked,launch;Actor(){super(null,null);}public int getUnitVariant(){return 1;}public float rifleStanceLevel(float p){return stance;}public boolean isNervLogisticsLocked(){return locked;}public boolean isLaunchSequenceActive(){return launch;}}
 static void need(boolean b,String m){if(!b)throw new AssertionError(m);checks++;}
 static JsonObject json(ZipFile z,String name)throws Exception{try(var in=z.getInputStream(z.getEntry("assets/projectseele/"+name))){return JsonParser.parseReader(new java.io.InputStreamReader(in)).getAsJsonObject();}}
 static List<?> triangles(Class<?> type,JsonObject mesh,String name)throws Exception{
  var p=mesh.getAsJsonObject("parts").getAsJsonObject(name);var pivot=p.getAsJsonArray("pivot");var values=p.getAsJsonArray("vertices");var ctor=Class.forName(type.getName()+"$Triangle").getDeclaredConstructor(Vector3f.class,Vector3f.class,Vector3f.class);ctor.setAccessible(true);var result=new ArrayList<>();
  for(int n=0;n<values.size();n+=24){var points=new Vector3f[3];for(int k=0;k<3;k++){int at=n+k*8;points[k]=new Vector3f(-(values.get(at).getAsFloat()+pivot.get(0).getAsFloat())/16,(values.get(at+1).getAsFloat()+pivot.get(1).getAsFloat())/16,(values.get(at+2).getAsFloat()+pivot.get(2).getAsFloat())/16);}result.add(ctor.newInstance((Object[])points));}return result;
 }
 static Field field(Class<?> c,String name)throws Exception{var f=c.getDeclaredField(name);f.setAccessible(true);return f;}
 static void seed(Class<?> type,JsonObject body,JsonObject gun)throws Exception{
  ((Map<Integer,Object>)field(type,"HEADS").get(null)).put(1,triangles(type,body,"head"));var tree=type.getDeclaredMethod("tree",List.class);tree.setAccessible(true);field(type,"rifle").set(null,tree.invoke(null,triangles(type,gun,"cannon")));
  var backs=(Map<String,Object>)field(type,"BACKS").get(null);for(String n:List.of("torso_upper","pylon_l","pylon_r","dorsal_cover"))backs.put("eva_unit01/"+n,tree.invoke(null,triangles(type,body,n)));
 }
 static BakedGeoModel model(JsonObject geo,JsonObject frame,int kind){
  var specs=geo.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones");var bones=new LinkedHashMap<String,GeoBone>();
  for(var raw:specs){var s=raw.getAsJsonObject();String name=s.get("name").getAsString();var parent=s.has("parent")?bones.get(s.get("parent").getAsString()):null;var b=new GeoBone(parent,name,false,0D,false,false);if(parent!=null)parent.getChildBones().add(b);var p=s.getAsJsonArray("pivot");b.setPivotX(-p.get(0).getAsFloat());b.setPivotY(p.get(1).getAsFloat());b.setPivotZ(p.get(2).getAsFloat());bones.put(name,b);}
  var matrices=frame.getAsJsonObject("final_rendered_model_bones");
  for(var e:bones.entrySet()){
   var b=e.getValue();var row=matrices.getAsJsonArray(e.getKey());if(row==null)continue;float[] v=new float[16];for(int i=0;i<16;i++)v[i]=row.get(i).getAsFloat();var global=new Matrix4f().set(v);var local=new Matrix4f(global);
   if(b.getParent()!=null&&matrices.has(b.getParent().getName())){var a=matrices.getAsJsonArray(b.getParent().getName());for(int i=0;i<16;i++)v[i]=a.get(i).getAsFloat();local=new Matrix4f().set(v).invert().mul(global);}
   var q=local.getUnnormalizedRotation(new Quaternionf()).normalize();EvaRigTransforms.rotate(b,q);var scale=local.getScale(new Vector3f());b.setScaleX(scale.x);b.setScaleY(scale.y);b.setScaleZ(scale.z);var pivot=EvaRigTransforms.pivot(b);var offset=local.getTranslation(new Vector3f()).sub(pivot).add(local.transformDirection(new Vector3f(pivot)));b.setPosX(-offset.x*16);b.setPosY(offset.y*16);b.setPosZ(offset.z*16);
  }
  if(kind>=3){var torso=bones.get("torso_upper");torso.setRotX(torso.getRotX()+(kind==3?.7F:1.2F));var back=bones.get("dorsal_cover");back.setRotX(back.getRotX()+.3F);}
  return new BakedGeoModel(bones.values().stream().filter(b->b.getParent()==null).toList(),null);
 }
 static Matrix4f matrix(JsonArray a){float[] v=new float[16];for(int i=0;i<16;i++)v[i]=a.get(i).getAsFloat();return new Matrix4f().set(v);}
 static List<float[]> execute(Class<?> type,Actor actor,BakedGeoModel m,Matrix4f world,Matrix4f gun)throws Exception{
  var method=type.getDeclaredMethod("apply",EvaUnit01Entity.class,GeoBone.class,Matrix4f.class,Matrix4f.class,Quaternionf.class,Vector3f.class,Vector3f.class,float.class,BakedGeoModel.class);method.setAccessible(true);var head=m.getBone("head").orElseThrow();var desired=EvaRigTransforms.rotation(new Matrix4f(world).mul(EvaRigTransforms.model(head)));var right=gun.getColumn(0,new Vector3f()).normalize();var forward=gun.getColumn(1,new Vector3f()).negate().normalize();var rows=new ArrayList<float[]>();
  for(int k=0;k<4;k++){actor.tickCount=40+k;method.invoke(null,actor,head,world,gun,desired,right,forward,.25F,m);rows.add(new float[]{head.getRotX(),head.getRotY(),head.getRotZ(),head.getPosX(),head.getPosY(),head.getPosZ()});}return rows;
 }
 public static void main(String[] args)throws Exception{
  for(String p:List.of("projectseele.r44CapturedSupportOwnership","projectseele.weaponHandlingReviewR45","projectseele.r45CannonContactCandidate","projectseele.r44TvCageReview","projectseele.r44TvPersonnelPlatformsReview"))System.setProperty(p,"false");System.setProperty("projectseele.capturedLocomotionDirectory","");var init=Class.forName("com.projectseele.entity.EvaKnifeRecoveryR52Test").getDeclaredMethod("dataOnlyEventLists");init.setAccessible(true);init.invoke(null);SharedConstants.tryDetectVersion();Bootstrap.bootStrap();
  var frames=new ArrayList<JsonObject>();for(String line:Files.readAllLines(Path.of(args[1]))){var row=JsonParser.parseString(line).getAsJsonObject();if(frames.isEmpty()||row.get("age").getAsInt()!=frames.get(frames.size()-1).get("age").getAsInt())frames.add(row);}var chosen=List.of(frames.get(0),frames.get(frames.size()/2),frames.get(frames.size()-1));
  var bean=(com.sun.management.ThreadMXBean)java.lang.management.ManagementFactory.getThreadMXBean();long tid=Thread.currentThread().getId();var report=new ArrayList<Map<String,Object>>();long oldNanos=0,newNanos=0,oldBytes=0,newBytes=0;
  try(var zip=new ZipFile(args[0])){var body=json(zip,"mesh/eva_unit01.mesh.json");var gunSource=json(zip,"mesh/eva_pallet_smg.mesh.json");var geo=json(zip,"geo/eva_unit01.geo.json");seed(EvaHeadClearanceOld.class,body,gunSource);seed(EvaHeadClearance.class,body,gunSource);
   for(int c=0;c<6;c++){var f=chosen.get(c%3);var world=matrix(f.getAsJsonArray("model_to_world"));var a=model(geo,f,c);var b=model(geo,f,c);var cannon=a.getBone("cannon").orElseThrow();var gun=new Matrix4f(world).mul(EvaRigTransforms.model(cannon));if(c==5)gun.translate(.04F,.01F,-.02F);var actor=(Actor)U.allocateInstance(Actor.class);actor.stance=c>=3?3:0;
    long alloc=bean.getThreadAllocatedBytes(tid),start=System.nanoTime();var before=execute(EvaHeadClearanceOld.class,actor,a,world,gun);long ns=System.nanoTime()-start,bytes=bean.getThreadAllocatedBytes(tid)-alloc;oldNanos+=ns;oldBytes+=bytes;
    alloc=bean.getThreadAllocatedBytes(tid);start=System.nanoTime();var after=execute(EvaHeadClearance.class,actor,b,world,gun);long nextNs=System.nanoTime()-start,nextBytes=bean.getThreadAllocatedBytes(tid)-alloc;newNanos+=nextNs;newBytes+=nextBytes;
    for(int i=0;i<before.size();i++)need(Arrays.equals(before.get(i),after.get(i)),"Actual old/new head channel differs case"+c+" frame"+i);report.add(Map.of("case",c,"source_age",f.get("age").getAsInt(),"stance",actor.stance,"actual_back_pose_modified",c>=3,"old_ns",ns,"new_ns",nextNs,"old_allocated_bytes",bytes,"new_allocated_bytes",nextBytes));
   }
  }
  int obstacle=0;var actor=(Actor)U.allocateInstance(Actor.class);var position=net.minecraft.world.entity.Entity.class.getDeclaredField("position");U.putObject(actor,U.objectFieldOffset(position),new net.minecraft.world.phys.Vec3(0,-60,0));
  try(var loader=new java.net.URLClassLoader(new java.net.URL[]{Path.of("C:/Users/liboy/.codex/worktrees/r51-nonmap/eva/build/classes/java/main").toUri().toURL()},VerifyHeadClearancePerfR52.class.getClassLoader()){
   protected synchronized Class<?> loadClass(String n,boolean resolve)throws ClassNotFoundException{if(n.equals("com.projectseele.entity.EvaObstacleCollision")){var type=findLoadedClass(n);if(type==null)type=findClass(n);if(resolve)resolveClass(type);return type;}return super.loadClass(n,resolve);}
  }){
   var old=loader.loadClass("com.projectseele.entity.EvaObstacleCollision").getMethod("ignores",EvaUnit01Entity.class,net.minecraft.world.level.block.state.BlockState.class,net.minecraft.core.BlockPos.class,net.minecraft.world.phys.shapes.VoxelShape.class);
   var blocks=List.of(net.minecraft.world.level.block.Blocks.STONE,net.minecraft.world.level.block.Blocks.DIRT,net.minecraft.world.level.block.Blocks.OAK_FENCE,net.minecraft.world.level.block.Blocks.COBBLESTONE_WALL,net.minecraft.world.level.block.Blocks.IRON_BARS,net.minecraft.world.level.block.Blocks.BARRIER,net.minecraft.world.level.block.Blocks.OAK_DOOR,net.minecraft.world.level.block.Blocks.OAK_TRAPDOOR,net.minecraft.world.level.block.Blocks.OAK_SLAB,net.minecraft.world.level.block.Blocks.OAK_STAIRS);
   var shapes=List.of(net.minecraft.world.phys.shapes.Shapes.block(),net.minecraft.world.phys.shapes.Shapes.empty(),net.minecraft.world.phys.shapes.Shapes.box(0,0,0,.2,1,.2),net.minecraft.world.phys.shapes.Shapes.box(0,0,0,1,.5,1));
   for(var block:blocks)for(var shape:shapes)for(int y=-63;y<=-57;y++)for(int status=0;status<3;status++){actor.locked=status==1;actor.launch=status==2;var state=block.defaultBlockState();var at=new net.minecraft.core.BlockPos(0,y,0);need((Boolean)old.invoke(null,actor,state,at,shape)==com.projectseele.entity.EvaObstacleCollision.ignores(actor,state,at,shape),"Old/new actual obstacle policy differs");obstacle++;}
  }
  var result=new LinkedHashMap<String,Object>();result.put("checks",checks);result.put("actual_source_poses",6);result.put("head_channel_float_bits_equal",true);result.put("model_or_triangles_changed",false);result.put("old_ms",oldNanos/1e6);result.put("new_ms",newNanos/1e6);result.put("old_allocated_bytes",oldBytes);result.put("new_allocated_bytes",newBytes);result.put("obstacle_original_C11_policy_comparisons",obstacle);result.put("cases",report);Files.writeString(Path.of(args[2]),new GsonBuilder().setPrettyPrinting().create().toJson(result));System.out.println(new Gson().toJson(result));
 }
}

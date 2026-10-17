package com.projectseele.world;
/** User restoration: R50 carrier/deck; no excavated storage or added runner assemblies. */
public final class NervR50CarrierModeR53 {
 public static boolean enabled(){return true;}
 public static boolean retiredPit(String id){return id!=null&&id.matches("bay_[0-2]_service_pit");}
 /** The existing 64 m launch return stroke lowers the entire old deck into
  * the launch shaft. The three deep service bays keep their original floor. */
 private static final java.util.List<net.minecraft.world.phys.Vec3> OUTLETS=readOutlets();
 private static java.util.List<net.minecraft.world.phys.Vec3> readOutlets(){
  try(var stream=NervR50CarrierModeR53.class.getResourceAsStream("/assets/projectseele/facility/r53_outlet_frames.json");var reader=new java.io.InputStreamReader(java.util.Objects.requireNonNull(stream),java.nio.charset.StandardCharsets.UTF_8)){
   var data=com.google.gson.JsonParser.parseReader(reader).getAsJsonObject();var result=new java.util.ArrayList<net.minecraft.world.phys.Vec3>();
   for(var value:data.getAsJsonArray("outlets")){var p=value.getAsJsonObject().getAsJsonArray("position");result.add(new net.minecraft.world.phys.Vec3(p.get(0).getAsDouble(),p.get(1).getAsDouble(),p.get(2).getAsDouble()));}return java.util.List.copyOf(result);
  }catch(java.io.IOException ex){throw new java.io.UncheckedIOException(ex);}
 }
 public static double launchDeckDropR53(RigidTransform root,float rise){return enabled()&&OUTLETS.stream().anyMatch(p->p.distanceToSqr(root.translation())<.0004)?-64D*(1-rise):0;}
 private NervR50CarrierModeR53(){}
}

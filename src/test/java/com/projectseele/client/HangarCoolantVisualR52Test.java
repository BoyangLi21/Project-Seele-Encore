package com.projectseele.client;
import com.projectseele.fluid.LclFluidType;
import com.projectseele.entity.SiloHatchMechanism;
import com.projectseele.entity.NervSiloDoorEntity;
import net.minecraft.nbt.*;
import net.minecraft.core.BlockPos;
import java.io.*;

/** Scope and compressed declared-spec persistence only; native shade/World not claimed. */
public final class HangarCoolantVisualR52Test {
 private static int checks;
 private static void check(boolean value,String why){checks++;if(!value)throw new AssertionError(why);}
 private static int tint(boolean claimed,boolean world,int x,int y,int z){return HangarCoolantVisualR52.paletteAtR52(claimed,world,x,y,z);}
 private static void rejects(Runnable operation,String why){boolean failed=false;try{operation.run();}catch(RuntimeException correct){failed=true;}check(failed,why);}
 public static void main(String[] args)throws Exception {
  for(int[] x:new int[][]{{53,91},{11,49},{-31,7}})for(int xx:new int[]{x[0],(x[0]+x[1])/2,x[1]})for(int y:new int[]{-678,-657,-635})for(int z:new int[]{302,328,354}) {
   check(tint(true,true,xx,y,z)==HangarCoolantVisualR52.TV_COOLANT_TINT,"Measured bay boundary/interior lost TV appearance");check(tint(false,true,xx,y,z)==LclFluidType.TINT,"Unclaimed world recolored");check(tint(true,false,xx,y,z)==LclFluidType.TINT,"Another render world recolored");
  }
  for(int[] p:new int[][]{{52,-660,330},{92,-660,330},{10,-660,330},{50,-660,330},{-32,-660,330},{8,-660,330},{70,-679,330},{70,-634,330},{70,-660,301},{70,-660,355},{0,-880,305},{0,64,0}})check(tint(true,true,p[0],p[1],p[2])==LclFluidType.TINT,"Outside/Terminal LCL changed its original palette");
  check(HangarCoolantVisualR52.tint(null,new BlockPos(70,-660,330))==LclFluidType.TINT,"Contextless inventory tint changed");check(HangarCoolantVisualR52.tint(null,null)==LclFluidType.TINT,"Default fluid tint changed");
  check((HangarCoolantVisualR52.TV_COOLANT_TINT>>>24)==255&&((HangarCoolantVisualR52.TV_COOLANT_TINT>>8)&255)<100,"Coolant became luminous fluorescent pink/transparent");
  var legacy=new SiloHatchMechanism.Spec(31,31,40,40,1,-2.01,false);check(!legacy.uprightGuidePorts(),"Legacy 7arg source changed");var selected=new SiloHatchMechanism.Spec(31,31,40,40,1,-2.01,false,true);check(selected.uprightGuidePorts(),"Declared actual guide-port mode missing");rejects(()->new SiloHatchMechanism.Spec(33,33,40,40,-1,-2.01,true,true),"Service pit inherited launch guide slots");rejects(()->new SiloHatchMechanism.Spec(64,64,40,40,1,-2.01,false,true),"Undeclared aperture inherited narrow actual slots");
  var tag=new CompoundTag();tag.putFloat("OpeningX",31);tag.putFloat("OpeningZ",31);tag.putInt("OpenTicks",40);tag.putInt("CloseTicks",40);tag.putInt("SeparationSign",1);tag.putDouble("BeamBottom",-2.01);tag.putBoolean("ServiceColumnPorts",false);tag.putBoolean("UprightGuidePorts",true);var bytes=new ByteArrayOutputStream();NbtIo.writeCompressed(tag,bytes);var restored=NbtIo.readCompressed(new ByteArrayInputStream(bytes.toByteArray()));net.minecraft.SharedConstants.tryDetectVersion();net.minecraftforge.fml.loading.FMLPaths.loadAbsolutePaths(java.nio.file.Path.of(".Codex/r52_runtime_close/coolant_visual/runtime_context").toAbsolutePath());try{net.minecraft.server.Bootstrap.bootStrap();}catch(ExceptionInInitializerError error){if(java.util.Arrays.stream(error.getStackTrace()).noneMatch(f->f.getClassName().equals("net.minecraftforge.network.NetworkHooks"))||net.minecraft.core.registries.BuiltInRegistries.BLOCK.size()<1000)throw error;System.out.println("Isolated codec fixture: unused untransformed Forge network bootstrap unavailable; vanilla registry initialized");}var method=NervSiloDoorEntity.class.getDeclaredMethod("readSpec",CompoundTag.class);method.setAccessible(true);check(selected.equals(method.invoke(null,restored)),"Production hatch NBT read dropped guide slots");restored.remove("UprightGuidePorts");check(legacy.equals(method.invoke(null,restored)),"Original no-slot NBT became slotted on reload");
  System.out.println("R52 coolant immutable scope / production door-spec NBT PASS checks="+checks+" tint=#773A61; no native visual or World acceptance");
 }
}

package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.world.phys.Vec3;
/** Byte/loader compatibility only; no level, actor or geometry admission. */
public final class FullSourceLoadReadOnlyR52 {
 public static void main(String[] args)throws Exception {
  FullAssemblyGeometryR52.installClasspath();NervMappedPlugMechanicsR52.install();var selected=NervMappedPlugMechanicsR52.selectedMachinery();if(!selected.selectedRunningDeckR52())throw new AssertionError("Current selected housing deck not enabled in provider");var counts=new ArrayList<Integer>();for(int variant=0;variant<3;variant++){var parts=NervOriginalCarrierR52.partsAtR52(variant,RigidTransform.identity(),0,new Vec3(0,1,0));if(parts.isEmpty())throw new AssertionError("Original full source empty");counts.add(parts.size());}var report=Map.of("world_written",false,"native_accepted",false,"production_full_loader",true,"full_source_sha256",NervOriginalCarrierR52.SOURCE_SHA,"legacy_source_sha256",NervLegacyCarrierRideR52.SOURCE_SHA,"original_variant_part_counts",counts,"scope","Complete current source byte/provider contract loads; Dock and mechanical paths are not commissioned or admitted");Files.writeString(Path.of(args[0]),new GsonBuilder().setPrettyPrinting().create().toJson(report));System.out.println("Full current source/provider loader PASS "+NervOriginalCarrierR52.SOURCE_SHA+" parts="+counts);
 }
}

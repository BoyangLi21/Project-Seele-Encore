package com.projectseele.world;
import com.google.gson.*;import com.projectseele.entity.*;import java.nio.file.*;import java.util.*;import net.minecraft.nbt.*;import net.minecraft.core.BlockPos;

/** Actual persisted Spec codecs and bounded peer sets; no Level or entity created. */
public final class CheckExpandedWetSealCodecR53
{
    public static void main(String[] args)throws Exception
    {
        net.minecraft.SharedConstants.tryDetectVersion();var boot=net.minecraft.server.Bootstrap.class.getDeclaredField("isBootstrapped");boot.setAccessible(true);boot.setBoolean(null,true);net.minecraft.core.registries.BuiltInRegistries.bootStrap();
        var parse=NervAssemblyOwnerR52.class.getDeclaredMethod("hangarSpec",JsonObject.class);parse.setAccessible(true);var write=NervHangarDoorEntity.class.getDeclaredMethod("writeSpecR52",CompoundTag.class,NervHangarGateGeometryR52.Spec.class);write.setAccessible(true);var read=NervHangarDoorEntity.class.getDeclaredMethod("readSpec",CompoundTag.class);read.setAccessible(true);var peer=NervSiloDoorEntity.class.getDeclaredMethod("peerProxySetsR52",Set.class,Set.class,Set.class);peer.setAccessible(true);int checks=0;
        var doc=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();for(var raw:doc.getAsJsonArray("gates")){var g=raw.getAsJsonObject();if(!g.get("resource").getAsString().startsWith("bay_")||!g.get("resource").getAsString().endsWith("_front"))continue;var spec=(NervHangarGateGeometryR52.Spec)parse.invoke(null,g);var tag=new CompoundTag();write.invoke(null,tag,spec);if(!spec.equals(read.invoke(null,tag))||tag.getCompound("FloorSeal").getInt("Version")!=2||tag.getCompound("FloorSeal").getInt("RetainedBoxCount")!=14||spec.bottomSeal().closedBoxes().size()!=293)throw new AssertionError("Actual expanded NBT fields/complete boxes lost");checks++;
            var old=new NervHangarGateGeometryR52.Spec(spec.width(),spec.height(),spec.openTicks(),spec.closeTicks(),spec.depthDirection(),new NervHangarGateGeometryR52.BottomSeal(spec.bottomSeal().closedBoxes().subList(0,14),spec.bottomSeal().dropM(),spec.bottomSeal().retreatLocalZ()));var legacy=new CompoundTag();write.invoke(null,legacy,old);if(!old.equals(read.invoke(null,legacy))||legacy.getCompound("FloorSeal").getInt("Version")!=1||legacy.getCompound("FloorSeal").contains("RetainedBoxCount"))throw new AssertionError("Legacy original seal codec changed");checks++;
            var cells=new HashSet<BlockPos>();for(var p:g.getAsJsonArray("floor_seal_original_cells")){var a=p.getAsJsonArray();cells.add(new BlockPos(a.get(0).getAsInt(),a.get(1).getAsInt(),a.get(2).getAsInt()));}if(cells.size()!=293||!(boolean)peer.invoke(null,Set.of(),Set.of(),cells)||(boolean)peer.invoke(null,Set.of(cells.iterator().next()),Set.of(),cells)||(boolean)peer.invoke(null,Set.of(),Set.of(cells.iterator().next()),cells))throw new AssertionError("Expanded peer proxies lost disjoint moving/support protection");checks++;
        }
        var tooMany=new HashSet<BlockPos>();for(int i=0;i<513;i++)tooMany.add(new BlockPos(i,0,0));if((boolean)peer.invoke(null,Set.of(),Set.of(),tooMany))throw new AssertionError("Unbounded peer set admitted");checks++;System.out.println("EXPANDED_WET_SEAL_CODEC_PASS="+checks+"; no Level/game/World written");
    }
}

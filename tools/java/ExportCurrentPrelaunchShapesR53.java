package com.projectseele.world;
import com.google.gson.*;
import java.nio.file.*;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.block.*;
import net.minecraft.world.level.block.state.*;
import net.minecraft.world.level.block.state.properties.*;
import net.minecraft.world.phys.shapes.CollisionContext;

/** Actual context-independent production block factory shapes; never starts a Level. */
public final class ExportCurrentPrelaunchShapesR53
{
    @SuppressWarnings({"unchecked","rawtypes"}) private static BlockState set(BlockState s,Property property,String value){var parsed=property.getValue(value);if(parsed.isEmpty())throw new IllegalArgumentException("Unknown stored property value");return s.setValue(property,(Comparable)parsed.get());}
    public static void main(String[] args)throws Exception
    {
        net.minecraft.SharedConstants.tryDetectVersion();var boot=net.minecraft.server.Bootstrap.class.getDeclaredField("isBootstrapped");boot.setAccessible(true);boot.setBoolean(null,true);net.minecraft.core.registries.BuiltInRegistries.bootStrap();
        ((net.minecraftforge.registries.ForgeRegistry<?>)net.minecraftforge.registries.ForgeRegistries.BLOCKS).unfreeze();
        var wrapper=net.minecraft.core.registries.BuiltInRegistries.BLOCK;var unfreeze=wrapper.getClass().getMethod("unfreeze");unfreeze.setAccessible(true);unfreeze.invoke(wrapper);
        var blocks=Map.<String,Block>of("projectseele:nerv_strip_light",new FacilityStripLightR47(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK)),"projectseele:entry_plug_bridge_deck",new EntryPlugBridgeDeckR48(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).noOcclusion()),"projectseele:entry_plug_bridge_guard",new FacilityEdgeRailR41(BlockBehaviour.Properties.copy(Blocks.IRON_BARS).noOcclusion(),true),"projectseele:nerv_room_partition",new NervRoomPartitionR47(BlockBehaviour.Properties.copy(Blocks.IRON_BLOCK).noOcclusion()));
        var input=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();var unknown=new TreeSet<String>();if(input.has("legs")){for(var leg:input.getAsJsonArray("legs"))for(var c:leg.getAsJsonObject().getAsJsonArray("unknown_shapes"))unknown.add(c.getAsJsonObject().get("state").getAsString());}else for(var c:input.getAsJsonArray("unknown_shapes"))unknown.add(c.getAsJsonObject().get("state").getAsString());var rows=new LinkedHashMap<String,Object>();
        for(String source:unknown)
        {
            int bracket=source.indexOf('[');String id=bracket<0?source:source.substring(0,bracket);var block=blocks.get(id);if(block==null&&id.equals("minecraft:barrel"))block=Blocks.BARREL;if(block==null)throw new AssertionError("Unresolved actual production class "+id);var state=block.defaultBlockState();var specified=new HashSet<String>();
            if(bracket>=0)for(String field:source.substring(bracket+1,source.length()-1).split(",")){String[] split=field.split("=");var property=block.getStateDefinition().getProperty(split[0]);if(property==null)throw new AssertionError("Unknown original stored property "+split[0]);state=set(state,property,split[1]);specified.add(split[0]);}
            var defaults=new TreeMap<String,String>();for(var p:state.getProperties())if(!specified.contains(p.getName()))defaults.put(p.getName(),String.valueOf(state.getValue(p)));
            var boxes=block.getCollisionShape(state,null,BlockPos.ZERO,CollisionContext.empty()).toAabbs().stream().map(b->new double[]{b.minX,b.minY,b.minZ,b.maxX,b.maxY,b.maxZ}).toList();
            rows.put(source,Map.of("native_boxes",boxes,"actual_factory",block.getClass().getName(),"omitted_properties_use_production_default",defaults));
        }
        Files.writeString(Path.of(args[1]),new GsonBuilder().setPrettyPrinting().create().toJson(Map.of("world_written",false,"game_started",false,"rows",rows,"scope","Current production Block constructors and getCollisionShape(empty context) for four audited context-independent classes. No Level, no native game admission, no map mutation. Omitted old palette properties resolve explicitly from actual production default state, as vanilla NBT loading does.")));System.out.println("Actual four production factories resolved stored states="+rows.size());
    }
}

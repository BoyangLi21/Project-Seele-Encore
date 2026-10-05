package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.SeeleMonolithEntityR47;
import com.projectseele.registry.SeeleConferenceEntitiesR47;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

/** Commission only the new, declared communication props; unloaded originals are never replaced. */
@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class SeeleConferencePropsR47
{
    private record Prop(int number,double x,double y,double z,float yaw){}
    private static final Map<ServerLevel,List<Prop>> PLANS=new WeakHashMap<>();
    public static final class State extends SavedData
    {
        final Map<Integer,UUID> ids=new HashMap<>();
        public static State load(CompoundTag tag)
        {var state=new State();var props=tag.getCompound("Monoliths");for(String name:props.getAllKeys())if(props.hasUUID(name))state.ids.put(Integer.parseInt(name),props.getUUID(name));return state;}
        @Override public CompoundTag save(CompoundTag tag)
        {var props=new CompoundTag();ids.forEach((n,id)->props.putUUID(Integer.toString(n),id));tag.put("Monoliths",props);return tag;}
    }
    private static List<Prop> plans(ServerLevel level)
    {
        return PLANS.computeIfAbsent(level,key->
        {
            var file=level.getServer().getWorldPath(LevelResource.ROOT).resolve("r47_seele_conference.json");
            if(!Files.isRegularFile(file))return List.of();
            try
            {
                var root=JsonParser.parseString(Files.readString(file)).getAsJsonObject();
                if(root.get("schema").getAsInt()!=47||!"r47-seele-middle-stop-v1".equals(root.get("epoch").getAsString()))throw new IllegalArgumentException("Conference world epoch differs");
                var room=root.getAsJsonObject("room");var centre=room.getAsJsonArray("table_and_chair_light_centre");
                double cx=centre.get(0).getAsDouble(),cz=centre.get(2).getAsDouble();var out=new ArrayList<Prop>();var seen=new HashSet<Integer>();
                for(var item:room.getAsJsonArray("monoliths"))
                {
                    var row=item.getAsJsonObject();int index=row.get("index").getAsInt();var p=row.getAsJsonArray("centre");
                    if(index<1||index>12||!seen.add(index))throw new IllegalArgumentException("Council number differs");
                    double x=p.get(0).getAsDouble(),y=p.get(1).getAsDouble(),z=p.get(2).getAsDouble();
                    out.add(new Prop(index,x,y,z,(float)Math.toDegrees(Math.atan2(-(cx-x),cz-z))));
                }
                if(out.size()!=12)throw new IllegalArgumentException("TV council layout is incomplete");
                var desk=room.has("table_centre_r48")?room.getAsJsonArray("table_centre_r48"):centre;
                out.add(new Prop(0,desk.get(0).getAsDouble(),desk.get(1).getAsDouble(),desk.get(2).getAsDouble(),0));return List.copyOf(out);
            }
            catch(Exception error){throw new IllegalStateException("SEELE meeting props have no complete world plan",error);}
        });
    }
    @SubscribeEvent public static void tick(TickEvent.LevelTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END||!(event.level instanceof ServerLevel level)||!level.dimension().equals(FacilitySchemaV2.DIMENSION)||level.getGameTime()%40!=0)return;
        var props=plans(level);if(props.isEmpty())return;
        var state=level.getDataStorage().computeIfAbsent(State::load,State::new,"projectseele_seele_conference_r47");
        for(var prop:props)
        {
            BlockPos pos=BlockPos.containing(prop.x,prop.y,prop.z);
            if(!level.hasChunkAt(pos))continue;
            UUID id=state.ids.get(prop.number);
            if(id!=null)continue;
            var entity=(prop.number==0?SeeleConferenceEntitiesR47.DESK.get():SeeleConferenceEntitiesR47.MONOLITH.get()).create(level);if(entity==null)continue;
            entity.setNumber(prop.number);entity.moveTo(prop.x,prop.y,prop.z,prop.yaw,0);
            if(level.addFreshEntity(entity)){state.ids.put(prop.number,entity.getUUID());state.setDirty();}
        }
    }
    private SeeleConferencePropsR47(){}
}

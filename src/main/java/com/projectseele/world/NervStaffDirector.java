package com.projectseele.world;

import com.google.gson.JsonParser;
import com.projectseele.ProjectSeele;
import com.projectseele.entity.NervStaffEntity;
import com.projectseele.registry.ModEntities;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.storage.LevelResource;
import net.minecraft.world.phys.AABB;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import java.nio.file.Files;
import java.util.*;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID)
public final class NervStaffDirector
{
    public record Station(String id,String name,String role,String skin,BlockPos feet,float yaw) {}
    private static final Map<ServerLevel,List<Station>> ROSTERS=new WeakHashMap<>();
    private static final Map<ServerLevel,Map<Long,Integer>> LOADED=new WeakHashMap<>();
    public static List<Station> roster(ServerLevel level)
    {
        return ROSTERS.computeIfAbsent(level,key->{
            var path=level.getServer().getWorldPath(LevelResource.ROOT).resolve("nerv_staff_r15.json");if(!Files.isRegularFile(path))return List.of();
            try
            {
                var json=JsonParser.parseString(Files.readString(path)).getAsJsonObject();if(!json.get("dimension").getAsString().equals(level.dimension().location().toString()))return List.of();
                List<Station> result=new ArrayList<>();Set<String> ids=new HashSet<>();
                for(var item:json.getAsJsonArray("stations"))
                {
                    var d=item.getAsJsonObject();String id=d.get("id").getAsString();if(!id.matches("[A-Za-z0-9_./-]{1,96}")||!ids.add(id))throw new IllegalArgumentException("Invalid staff identity");var p=d.getAsJsonArray("feet");
                    result.add(new Station(id,d.get("name").getAsString(),d.get("role").getAsString(),d.get("skin").getAsString(),new BlockPos(p.get(0).getAsInt(),p.get(1).getAsInt(),p.get(2).getAsInt()),d.get("yaw").getAsFloat()));
                }
                if(result.size()>400)throw new IllegalArgumentException("Roster budget exceeded");return List.copyOf(result);
            }
            catch(Exception e){ProjectSeele.LOGGER.error("Staff roster rejected",e);return List.of();}
        });
    }
    @SubscribeEvent public static void tick(TickEvent.ServerTickEvent event)
    {
        if(event.phase!=TickEvent.Phase.END)return;
        for(var level:event.getServer().getAllLevels())
        {
            if(level.getGameTime()%20!=0)continue;var roster=roster(level);if(roster.isEmpty())continue;var state=NervStaffSavedData.get(level);var age=LOADED.computeIfAbsent(level,l->new HashMap<>());
            Set<Long> visible=new HashSet<>();for(var station:roster)
            {
                if(state.identity(station.id())!=null)continue;BlockPos p=station.feet();long chunk=net.minecraft.world.level.ChunkPos.asLong(p.getX()>>4,p.getZ()>>4);
                // Never force distant chunks or interpret an unloaded persistent NPC as missing.
                if(!level.hasChunkAt(p)||level.players().stream().noneMatch(player->!player.isRemoved()&&player.distanceToSqr(p.getX()+.5,p.getY(),p.getZ()+.5)<=96*96))continue;visible.add(chunk);
            }
            age.keySet().retainAll(visible);for(long c:visible)age.merge(c,1,Integer::sum);
            int spawned=0;
            for(var station:roster)
            {
                if(spawned>=4)break;if(state.identity(station.id())!=null)continue;BlockPos p=station.feet();long chunk=net.minecraft.world.level.ChunkPos.asLong(p.getX()>>4,p.getZ()>>4);if(age.getOrDefault(chunk,0)<4)continue;
                var prior=level.getEntitiesOfClass(NervStaffEntity.class,new AABB(p).inflate(24),e->e.memberId().equals(station.id()));
                if(!prior.isEmpty()){state.record(station.id(),prior.get(0).getUUID());continue;}
                var npc=ModEntities.NERV_STAFF.get().create(level);if(npc==null)continue;npc.assign(station.id(),station.name(),station.role(),station.skin(),p);npc.stationYaw(station.yaw());npc.moveTo(p.getX()+.5,p.getY(),p.getZ()+.5,station.yaw(),0);npc.yBodyRot=station.yaw();npc.setYHeadRot(station.yaw());
                if(!level.noCollision(npc)||level.getBlockState(p.below()).getCollisionShape(level,p.below()).isEmpty())continue;
                if(level.addFreshEntity(npc)){state.record(station.id(),npc.getUUID());spawned++;}
            }
        }
    }
    private NervStaffDirector() {}
}

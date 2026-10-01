package com.projectseele.world;

import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/** A persisted per-save identity shared by cargo journals and native QA snapshots. */
public final class Tokyo3BuildingWorldIdentityR44 extends SavedData
{
    private static final String NAME="projectseele_tokyo3_building_world_id_r44";
    private String id="";
    private static Tokyo3BuildingWorldIdentityR44 data(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(tag->{
            Tokyo3BuildingWorldIdentityR44 value=new Tokyo3BuildingWorldIdentityR44();
            value.id=tag.getString("WorldUUID");return value;
        },Tokyo3BuildingWorldIdentityR44::new,NAME);
    }
    public static String get(ServerLevel level)
    {
        Tokyo3BuildingWorldIdentityR44 value=data(level);
        if(value.id.isEmpty())
        {
            String job=System.getProperty("projectseele.r44TokyoQualityJob","");
            if(!job.isEmpty())
            {
                try
                {
                    var input=com.google.gson.JsonParser.parseString(java.nio.file.Files.readString(java.nio.file.Path.of(job))).getAsJsonObject();
                    java.nio.file.Path world=level.getServer().getWorldPath(net.minecraft.world.level.storage.LevelResource.ROOT).toAbsolutePath().normalize();
                    if(!world.equals(java.nio.file.Path.of(input.get("world").getAsString()).toAbsolutePath().normalize())||level.getSeed()!=input.get("world_seed").getAsLong())
                        throw new IllegalStateException("Configured city identity belongs to a different world");
                    value.id=UUID.fromString(input.get("world_id").getAsString()).toString();
                }
                catch(Exception error){throw new IllegalStateException("Cannot bind the explicitly scheduled QA identity",error);}
            }
            else value.id=UUID.randomUUID().toString();
            value.setDirty();level.getDataStorage().save();
        }
        return value.id;
    }
    public static void bindFirstIdentity(ServerLevel level,String requested)
    {
        UUID.fromString(requested);Tokyo3BuildingWorldIdentityR44 value=data(level);
        if(!value.id.isEmpty()&&!value.id.equals(requested))throw new IllegalStateException("Different persisted city WorldUUID");
        if(value.id.isEmpty()){value.id=requested;value.setDirty();level.getDataStorage().save();}
    }
    @Override public CompoundTag save(CompoundTag tag){tag.putString("WorldUUID",id);return tag;}
    private Tokyo3BuildingWorldIdentityR44(){}
}

package com.projectseele.world;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.saveddata.SavedData;

/** References to one authorized caller and original operator; never writes either actor's data. */
public final class CityMotionReportSavedDataR49 extends SavedData
{
    public static final int MAX_SUBSCRIPTIONS = 64;
    public static final class Watch
    {
        final UUID caller, operator;
        final BlockPos origin;
        String previous;
        long next;
        boolean suspended;

        Watch(UUID caller, UUID operator, BlockPos origin, String previous, long next, boolean suspended)
        {
            this.caller=caller;this.operator=operator;this.origin=origin.immutable();
            this.previous=previous;this.next=next;this.suspended=suspended;
        }
    }
    final Map<UUID, Watch> watches = new LinkedHashMap<>();

    public static CityMotionReportSavedDataR49 get(ServerLevel level)
    {
        return level.getDataStorage().computeIfAbsent(CityMotionReportSavedDataR49::load,
                CityMotionReportSavedDataR49::new, "projectseele_city_motion_reports_r49");
    }

    public boolean bind(UUID caller, UUID operator, BlockPos origin, String previous, long now)
    {
        if(!watches.containsKey(caller)&&watches.size()>=MAX_SUBSCRIPTIONS)return false;
        watches.put(caller,new Watch(caller,operator,origin,previous,now+200,false));setDirty();return true;
    }

    public void remove(UUID caller)
    {if(watches.remove(caller)!=null)setDirty();}

    static CityMotionReportSavedDataR49 load(CompoundTag tag)
    {
        var state=new CityMotionReportSavedDataR49();
        if(tag.getInt("Version")!=1)return state;
        for(var raw:tag.getList("Subscriptions",Tag.TAG_COMPOUND))
        {
            var row=(CompoundTag)raw;
            if(!row.hasUUID("Caller")||!row.hasUUID("Operator")||!row.contains("Origin",Tag.TAG_LONG))continue;
            if(state.watches.size()>=MAX_SUBSCRIPTIONS)break;
            UUID caller=row.getUUID("Caller");
            state.watches.putIfAbsent(caller,new Watch(caller,row.getUUID("Operator"),BlockPos.of(row.getLong("Origin")),
                    row.getString("Previous"),0,true));
        }
        return state;
    }

    @Override public CompoundTag save(CompoundTag tag)
    {
        tag.putInt("Version",1);var rows=new ListTag();
        for(var watch:watches.values())
        {
            var row=new CompoundTag();row.putUUID("Caller",watch.caller);row.putUUID("Operator",watch.operator);
            row.putLong("Origin",watch.origin.asLong());row.putString("Previous",watch.previous);rows.add(row);
        }
        tag.put("Subscriptions",rows);return tag;
    }
}

package com.projectseele.visual;

import com.google.gson.JsonObject;
import net.minecraft.world.entity.Entity;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

/** Small opt-in callback trace; no ride graph or metadata mutation. */
public final class PassengerAuthorityWitnessR44
{
    private static final String OUTPUT=System.getProperty("projectseele.r44PassengerWitnessPath","");
    public static boolean enabled(){return !OUTPUT.isEmpty();}
    public static void capture(Entity host,Entity passenger,String stage,JsonObject fields)
    {
        if(!enabled())return;
        JsonObject row=new JsonObject();row.addProperty("side",host.level().isClientSide?"client":"server");
        row.addProperty("stage",stage);row.addProperty("host_uuid",host.getUUID().toString());row.addProperty("host_id",host.getId());
        row.addProperty("passenger_id",passenger==null?-1:passenger.getId());row.addProperty("tick",host.level().getGameTime());
        row.addProperty("entity_tick",host.tickCount);row.addProperty("ride_graph_passengers",host.getPassengers().size());
        row.add("actual_authoritative_fields",fields);
        try{Path file=Path.of(OUTPUT).toAbsolutePath();Files.createDirectories(file.getParent());Files.writeString(file,row+"\n",StandardOpenOption.CREATE,StandardOpenOption.APPEND);}
        catch(Exception error){throw new IllegalStateException("Actual passenger callback trace could not be recorded",error);}
    }
    private PassengerAuthorityWitnessR44(){}
}

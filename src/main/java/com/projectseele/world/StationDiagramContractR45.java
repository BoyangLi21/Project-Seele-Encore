package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.projectseele.visual.RegionalNativeTransitInspection;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;

/** Complete diagram identity/topology/read-side contract, independent of board renderer. */
public final class StationDiagramContractR45
{
    private static JsonObject reject(JsonObject result,String reason)
    {result.addProperty("passed",false);result.addProperty("reason",reason);return result;}
    public static JsonObject inspect(ServerLevel level,BlockPos at,JsonObject test)
    {
        JsonObject result=new JsonObject();result.addProperty("position",at.toShortString());
        try
        {
            var state=level.getBlockState(at);var entity=level.getBlockEntity(at);
            if(entity==null)return reject(result,"missing_actual_complete_BE");
            CompoundTag tag=entity.saveWithFullMetadata();
            String block=net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(state.getBlock()).toString();
            boolean nativeMap=block.equals("mtr:route_sign_wall_light");long platformId;
            result.addProperty("block",block);result.addProperty("actual_BE_id",tag.getString("id"));
            result.addProperty("native_two_high",nativeMap);
            List<String> authoredRows=new ArrayList<>();
            if(nativeMap)
            {
                BlockPos lower=at;
                var half=state.getProperties().stream().filter(p->p.getName().equals("half")).findFirst().orElse(null);
                if(half==null)return reject(result,"native_map_missing_half_contract");
                if(state.getValue(half).toString().equals("upper"))lower=at.below();
                platformId=Long.MIN_VALUE;
                for(BlockPos member:new BlockPos[]{lower,lower.above()})
                {
                    var memberState=level.getBlockState(member);var memberBE=level.getBlockEntity(member);
                    if(!net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(memberState.getBlock()).toString().equals(block)||memberBE==null)
                        return reject(result,"native_map_incomplete_pair");
                    CompoundTag nativeTag=memberBE.saveWithFullMetadata();
                    if(!nativeTag.getString("id").equals("mtr:route_sign_wall_light")||!nativeTag.contains("platform_id",net.minecraft.nbt.Tag.TAG_LONG))
                        return reject(result,"native_map_incompatible_BE_schema");
                    long id=nativeTag.getLong("platform_id");
                    if(platformId!=Long.MIN_VALUE&&platformId!=id)return reject(result,"native_pair_platform_binding_disagrees");
                    platformId=id;
                }
                result.addProperty("lower",lower.toShortString());
            }
            else
            {
                if(!(entity instanceof StationDepartureBoardBlockEntity board))return reject(result,"unknown_actual_diagram_type");
                boolean wayfinding=test.has("readingWayfinding")&&test.get("readingWayfinding").getAsBoolean();
                if(wayfinding?board.rows().size()<3:!board.routeMap()||board.rows().size()<4)
                    return reject(result,"missing_complete_authored_rows");
                authoredRows.addAll(board.rows());platformId=tag.getLong("NativePlatformId");
            }
            result.addProperty("native_platform_id",platformId);
            if(test.has("expectedNativePlatformId")&&platformId!=Long.parseLong(test.get("expectedNativePlatformId").getAsString()))
                return reject(result,"wrong_explicit_native_platform_binding");
            Object simulator=RegionalNativeTransitInspection.simulator();
            if(simulator==null)return reject(result,"native_simulator_not_loaded");
            Object found=null;
            for(Object platform:(Iterable<?>)TransportLifecycleTraceR45.field(simulator,"platforms"))
                if(((Number)TransportLifecycleTraceR45.call(platform,"getId")).longValue()==platformId){found=platform;break;}
            if(found==null)return reject(result,"bound_platform_missing_in_actual_native_simulator");
            LinkedHashSet<String> stationOrder=new LinkedHashSet<>();int routes=0;
            for(Object route:(Iterable<?>)TransportLifecycleTraceR45.field(found,"routes"))
            {
                routes++;
                for(Object stop:(Iterable<?>)TransportLifecycleTraceR45.call(route,"getRoutePlatforms"))
                {
                    Object platform=TransportLifecycleTraceR45.call(stop,"getPlatform");
                    if(platform!=null)stationOrder.add(String.valueOf(TransportLifecycleTraceR45.call(platform,"getStationName")).split("\\|",2)[0].trim());
                }
            }
            if(routes==0||stationOrder.size()<2)return reject(result,"no_complete_operating_route_topology");
            JsonArray ordered=new JsonArray();stationOrder.forEach(ordered::add);result.add("actual_chinese_station_sequence",ordered);
            if(stationOrder.stream().noneMatch(name->name.codePoints().anyMatch(c->Character.UnicodeScript.of(c)==Character.UnicodeScript.HAN)))
                return reject(result,"native_route_has_no_chinese_station_names");
            if(test.has("expectedChineseStations"))for(var name:test.getAsJsonArray("expectedChineseStations"))
                if(!stationOrder.contains(name.getAsString()))return reject(result,"actual_native_station_sequence_mismatch");
            if(!nativeMap&&!authoredRows.isEmpty())for(String name:stationOrder)
                if(authoredRows.stream().noneMatch(row->row.contains(name)))return reject(result,"authored_map_omits_actual_station");
            var facing=state.getProperties().stream().filter(p->p.getName().equals("facing")).findFirst().orElse(null);
            if(facing==null||!test.has("path"))return reject(result,"reader_facing_or_path_unknown");
            String face=state.getValue(facing).toString();int dx=face.equals("east")?1:face.equals("west")?-1:0,dz=face.equals("south")?1:face.equals("north")?-1:0;
            if(nativeMap){dx=-dx;dz=-dz;}
            JsonArray end=test.getAsJsonArray("path").get(test.getAsJsonArray("path").size()-1).getAsJsonArray();
            double side=(end.get(0).getAsDouble()-at.getX()-.5)*dx+(end.get(2).getAsDouble()-at.getZ()-.5)*dz;
            if(side<.25)return reject(result,"reader_on_wrong_actual_model_face");
            result.addProperty("actual_front_reader",true);result.addProperty("native_routes",routes);result.addProperty("passed",true);
            result.addProperty("actual_client_glyph_and_legibility_verified",false);
            result.addProperty("scope","Pair/complete NBT/native ID/actual route topology/Chinese station data/front side. Caller still performs the real outline ray; actual client glyphs and shader photos remain required.");
            return result;
        }
        catch(Exception error){return reject(result,"native_diagram_contract_unavailable: "+error);}
    }
    private StationDiagramContractR45(){}
}

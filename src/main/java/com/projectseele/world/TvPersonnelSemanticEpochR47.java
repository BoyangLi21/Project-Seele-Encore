package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.TreeMap;

/** Same finite layout/geometry/recipe epoch, independent of JSON whitespace. */
public final class TvPersonnelSemanticEpochR47
{
    public static final String EPOCH="R47_PERSONNEL_LAYOUT_V4_ALIGNED_GATES_V1";
    // Existing source identities are version references, never byte-hash tests.
    private static final String LAYOUT="7960312844899676b73c84f18ea08484f437daa91b29aaa3af94406307e1bd01";
    private static final String GEOMETRY="b6cb6756d6436c54eb4635e964abc42b82bf8fd59eb4f74fded9dfdc0be31b81";
    private static final String OPERATIONS="e62e1e2fa2ef71ac1cc673a1fd1a3cbbdc30d21ea5f6e0fce87799e060d9bc8e";
    private static final String INVERSE="15fde33c950f2fb7acf22c1dd6ed97211b75e8d0c18aed52311ab9e4c518cb40";
    private static JsonObject recipe;
    private static Boolean modelReady;
    private static String modelFailure="";
    private TvPersonnelSemanticEpochR47() {}

    private static JsonObject resource(String path,int maximum)throws Exception
    {
        try(var input=TvPersonnelSemanticEpochR47.class.getResourceAsStream(path))
        {
            require(input!=null,"Missing bundled semantic resource "+path);
            byte[] bytes=input.readNBytes(maximum+1);require(bytes.length<=maximum,"Oversize semantic resource "+path);
            return JsonParser.parseString(new String(bytes,StandardCharsets.UTF_8)).getAsJsonObject();
        }
    }
    public static synchronized JsonObject recipe()throws Exception
    {
        if(recipe!=null)return recipe;
        JsonObject r=resource("/data/projectseele/worldgen/authored/tv_personnel_recipe_r44.json",1_000_000);
        require(r.get("schema").getAsInt()==44,"recipe.schema must be44");
        require(r.getAsJsonArray("operations").size()==427&&r.getAsJsonArray("entry_gate_pairs").size()==6,"Recipe finite427/6 source epoch incomplete");
        require(OPERATIONS.equals(r.get("operations_sha256").getAsString())&&INVERSE.equals(r.get("inverse_sha256").getAsString()),"Recipe source operations/inverse version differs");
        require(r.get("root_application_before_source_activation_required").getAsBoolean(),"Recipe root-before-activation constraint absent");
        var beds=r.getAsJsonArray("bed_owners");require(beds.size()==3,"Recipe original three bed owners incomplete");
        for(int v=0;v<3;v++)
        {var p=beds.get(v).getAsJsonArray();require(p.size()==3&&p.get(0).getAsInt()==-12+42*v&&p.get(1).getAsInt()==-443&&p.get(2).getAsInt()==-240,"Foreign recipe bed owner "+v);}
        recipe=r;return r;
    }
    private static Map<String,JsonObject> operations(JsonArray rows)
    {
        var result=new TreeMap<String,JsonObject>();
        for(var value:rows)
        {
            var row=value.getAsJsonObject();var p=row.getAsJsonArray("position");require(p.size()==3,"Owner position must have3 coordinates");
            for(var coordinate:p){double n=coordinate.getAsDouble();require(Double.isFinite(n)&&n==Math.rint(n),"Fractional/nonfinite owner coordinate "+p);}
            String key=p.get(0).getAsInt()+"/"+p.get(1).getAsInt()+"/"+p.get(2).getAsInt();
            require(result.put(key,row)==null,"Duplicate semantic operation owner "+key);
        }
        return result;
    }
    private static Map<String,JsonObject> gates(JsonArray rows)
    {
        var result=new TreeMap<String,JsonObject>();
        for(var value:rows)
        {var row=value.getAsJsonObject();String key=row.get("variant").getAsInt()+"/"+row.get("side").getAsInt();require(result.put(key,row)==null,"Duplicate semantic gate "+key);}
        return result;
    }
    public static void requireMetadata(JsonObject document)throws Exception
    {
        require(document.get("schema").getAsInt()==44&&"projectseele:geofront".equals(document.get("dimension").getAsString()),"Wrong personnel semantic schema/dimension");
        var p=document.getAsJsonObject("owner_provenance");
        require(LAYOUT.equals(p.get("source_layout_sha256").getAsString()),"owner_provenance.source_layout version differs");
        require(GEOMETRY.equals(p.get("geometry_sha256").getAsString()),"owner_provenance.geometry version differs");
        require(OPERATIONS.equals(p.get("operations_sha256").getAsString())&&INVERSE.equals(p.get("inverse_sha256").getAsString()),"owner_provenance.operations/inverse versions differ");
        var r=recipe();
        require(operations(p.getAsJsonArray("installed_owned_operations")).equals(operations(r.getAsJsonArray("operations"))),"Installed complete427 before/after/role semantics differ from bundled recipe");
        require(gates(document.getAsJsonArray("entry_gate_pairs")).equals(gates(r.getAsJsonArray("entry_gate_pairs"))),"Installed six gate owner/approach/facing semantics differ from bundled recipe");
        requireModel();
    }
    public static synchronized void requireModel()throws Exception
    {
        if(modelReady!=null){require(modelReady,modelFailure);return;}
        try
        {
            var m=resource("/assets/projectseele/mesh/tv_shoulder_shells_r44.json",32_000_000);var p=m.getAsJsonObject("personnel_platform_revision");
            require(p.get("permanent_world_grating_not_entity_floor").getAsBoolean()&&p.get("whole_operator_surface_interlock_required").getAsBoolean(),"Mesh permanent grating/whole-surface interlock constraints absent");
            require("personnel_platforms_v5_layout_v4".equals(p.get("world_layout_requires").getAsString()),"Mesh personnel world_layout_requires differs");
            require("r47_gate_alignment/r44_tv_personnel_platforms.json".equals(p.get("metadata_requires").getAsString()),"Mesh requires another personnel gate deployment epoch");
            require(LAYOUT.equals(p.get("layout_sha256").getAsString())&&OPERATIONS.equals(p.get("world_operations_sha256").getAsString())
                    &&GEOMETRY.equals(p.get("geometry_identical_draft11_sha256").getAsString()),"Mesh/metadata layout, operations or fixed geometry versions differ");
            for(String part:new String[]{"fixed_support_l","fixed_support_r","fixed_support_2_r"})
            {
                require(m.getAsJsonObject("collision_parts").has(part)&&!m.getAsJsonObject("collision_parts").getAsJsonArray(part).isEmpty(),"Mesh fixed collision part missing: "+part);
                boolean fixed=false;
                for(var value:m.getAsJsonArray("components")){var c=value.getAsJsonObject();if(part.equals(c.get("part").getAsString())){require("fixed".equals(c.get("motion").getAsString()),"Personnel fixed support changed to moving part: "+part);fixed=true;}}
                require(fixed,"Mesh fixed component missing: "+part);
            }
            modelReady=true;
        }
        catch(Exception failure){modelReady=false;modelFailure="Personnel model semantic epoch rejected: "+failure.getMessage();throw failure;}
    }
    public static void requireReferenceAgreement(JsonObject first,JsonObject second)
    {
        // Keep deployment provenance between graph/proof/manifest consistent;
        // these fields do not grant permission by hashing a formatted JSON file.
        for(String field:new String[]{"metadata_sha256","model_sha256"})
            require(first.has(field)&&second.has(field)&&first.get(field).equals(second.get(field)),"Declared semantic navigation reference mismatch: "+field);
        for(JsonObject binding:new JsonObject[]{first,second})if(binding.has("personnel_semantic_epoch"))
            require(EPOCH.equals(binding.get("personnel_semantic_epoch").getAsString()),"Unknown personnel_semantic_epoch");
    }
    private static void require(boolean value,String message){if(!value)throw new IllegalArgumentException(message);}
}

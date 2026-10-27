import com.google.gson.*;
import com.projectseele.entity.Unit03ReviewContractR53;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;

/** Runs production contract admission against independent malformed fixtures. */
public final class AuditUnit03ReviewContractR53
{
    private static final Gson GSON=new Gson();
    private static String hash(Path p)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(p)));}
    private static JsonObject json(Path p)throws Exception{return JsonParser.parseString(Files.readString(p)).getAsJsonObject();}
    private static void write(Path p,JsonObject j)throws Exception{Files.writeString(p,GSON.toJson(j));}
    private static Properties properties(JsonObject c)
    {var p=new Properties();c.getAsJsonObject("properties").entrySet().forEach(e->p.setProperty(e.getKey(),e.getValue().getAsString()));return p;}
    public static void main(String[] args)throws Exception
    {
        Path source=Path.of(args[0]).toAbsolutePath().normalize(),root=Path.of(args[1]).toAbsolutePath().normalize();
        if(Files.exists(root)||source.equals(root))throw new IllegalStateException("Fresh independent negative-control directory required");
        Files.createDirectories(root);
        try(var stream=Files.walk(source))
        {for(Path p:stream.toList()){Path dest=root.resolve(source.relativize(p));if(Files.isDirectory(p))Files.createDirectories(dest);else Files.copy(p,dest);}}
        Path manifest=root.resolve("unit03_review_contract.json");JsonObject original=json(manifest);
        for(var e:original.getAsJsonObject("properties").entrySet())
            e.setValue(new JsonPrimitive(root.resolve(source.relativize(Path.of(e.getValue().getAsString()))).toString()));
        original.addProperty("world",root.resolve("isolated-client/saves/SEELE_R53_UNIT03_SOURCE_REVIEW").toString());write(manifest,original);
        Properties props=properties(original);var results=new JsonObject();
        var accepted=Unit03ReviewContractR53.validate(source,properties(json(source.resolve("unit03_review_contract.json"))));
        results.addProperty("real_candidate_accepted",accepted.poses().size()==6);
        Unit03ReviewContractR53.validate(root,props);
        for(String fault:List.of("partial_overlay","wrong_world","conflicting_body_override","body_geo_mismatch","unadmitted_stride","altered_hand_bytes","missing_hand_fingerprint","unknown_pose","promoted_gameplay"))
        {
            JsonObject c=original.deepCopy();Properties effective=(Properties)props.clone();Path changed=null;byte[] before=null;
            switch(fault)
            {
                case "partial_overlay" -> {changed=root.resolve("runtime/combat_bundle_r44.json");before=Files.readAllBytes(changed);var j=json(changed);j.getAsJsonObject("files").remove("eva_gameplay_r44_0.json");write(changed,j);c.getAsJsonObject("files").addProperty("runtime/combat_bundle_r44.json",hash(changed));}
                case "wrong_world" -> c.addProperty("world",source.resolve("../../client/saves/SEELE_R53_WORLD").normalize().toString());
                case "conflicting_body_override" -> effective.setProperty("projectseele.bodyPoseReview",source.resolve("runtime/eva_body_r44.json").toString());
                case "body_geo_mismatch" -> {changed=root.resolve("resources/assets/projectseele/geo/eva_un01.geo.json");before=Files.readAllBytes(changed);var j=json(changed);j.getAsJsonArray("minecraft:geometry").get(0).getAsJsonObject().getAsJsonArray("bones").remove(0);write(changed,j);c.getAsJsonObject("files").addProperty("resources/assets/projectseele/geo/eva_un01.geo.json",hash(changed));}
                case "unadmitted_stride" -> {changed=root.resolve("captured/eva_locomotion_capture_r44_4.json");Files.writeString(changed,"{}");}
                case "altered_hand_bytes" -> {changed=root.resolve("hands/unit04/hand_rig_contract.json");before=Files.readAllBytes(changed);Files.writeString(changed," ",StandardOpenOption.APPEND);}
                case "missing_hand_fingerprint" -> c.getAsJsonObject("files").remove("hands/unit04/hand_rig_contract.json");
                case "unknown_pose" -> {changed=root.resolve("keyposes.json");before=Files.readAllBytes(changed);var j=json(changed);j.getAsJsonObject("poses").add("full_combat",j.getAsJsonObject("poses").get("idle"));write(changed,j);c.getAsJsonObject("files").addProperty("keyposes.json",hash(changed));}
                case "promoted_gameplay" -> c.addProperty("combat_gameplay_admitted",true);
            }
            write(manifest,c);boolean rejected=false;String reason="";
            try{Unit03ReviewContractR53.validate(root,effective);}catch(IllegalArgumentException expected){rejected=true;reason=expected.getMessage();}
            finally{if(changed!=null){if(before==null)Files.delete(changed);else Files.write(changed,before);}write(manifest,original);}
            if(!rejected)throw new AssertionError("Unsafe fixture accepted: "+fault);
            results.addProperty(fault,reason);
        }
        Unit03ReviewContractR53.validate(root,props);results.addProperty("fixture_restored_and_reaccepted",true);
        Files.writeString(Path.of(args[2]),GSON.toJson(results));System.out.println(GSON.toJson(results));
    }
}

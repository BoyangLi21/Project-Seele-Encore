import java.util.*;
/** Adversarial observer inputs only; does not load any Minecraft class. */
public final class R52FinalPhotoEvidence {
    static int checks;
    static void check(boolean value,String reason){checks++;if(!value)throw new AssertionError(reason);}
    public static void main(String[] args)throws Exception{
        var block=R52TerrainReadyReadOnlyAgent.class.getDeclaredMethod("blockState",Object.class);block.setAccessible(true);
        var parts=R52TerrainReadyReadOnlyAgent.class.getDeclaredMethod("stateParts",String.class);parts.setAccessible(true);
        String actual=(String)block.invoke(null,"Block{minecraft:polished_blackstone_button}[face=wall,facing=east,powered=false]");
        check(parts.invoke(null,actual).equals(parts.invoke(null,"minecraft:polished_blackstone_button[powered=false,facing=east,face=wall]")),"Palette property order must not invent a stale world");
        check(!parts.invoke(null,actual).equals(parts.invoke(null,"minecraft:polished_blackstone_button[powered=true,facing=east,face=wall]")),"Actual pressed button cannot borrow an unpressed source state");
        check(!parts.invoke(null,"projectseele:wall_artwork").equals(parts.invoke(null,"minecraft:air")),"Missing artwork cannot pass a source anchor");
        var method=R52TerrainReadyReadOnlyAgent.class.getDeclaredMethod("guideReadyR52",Map.class,Map.class);method.setAccessible(true);
        String source="a".repeat(64),model="b".repeat(64);
        var plan=Map.of("guide_source_sha256",source,"guide_model_sha256",model);
        var cell=new HashMap<String,Object>(Map.of("native_loaded",true,"gpu_uploaded",true,"last_draw_frame",42L));
        var base=new HashMap<String,Object>(Map.of("ready",true,"expected_source_sha256",source,"loaded_source_sha256",source,"model_source_sha256",model,"render_frame",42L,"target_visible_cells",List.of(cell)));
        check((boolean)method.invoke(null,base,plan),"Same-source actual native/GPU/current-draw proof should qualify");
        for(String key:List.of("expected_source_sha256","loaded_source_sha256","model_source_sha256")){var altered=new HashMap<>(base);altered.put(key,"c".repeat(64));check(!(boolean)method.invoke(null,altered,plan),"Wrong "+key+" cannot qualify even with claimed ready");}
        for(String key:List.of("native_loaded","gpu_uploaded")){var alteredCell=new HashMap<>(cell);alteredCell.put(key,false);var altered=new HashMap<>(base);altered.put("target_visible_cells",List.of(alteredCell));check(!(boolean)method.invoke(null,altered,plan),"Missing "+key+" cannot qualify");}
        var oldCell=new HashMap<>(cell);oldCell.put("last_draw_frame",41L);var old=new HashMap<>(base);old.put("target_visible_cells",List.of(oldCell));check(!(boolean)method.invoke(null,old,plan),"Previous-frame GPU upload cannot substitute for actual current draw");
        var empty=new HashMap<>(base);empty.put("target_visible_cells",List.of());check(!(boolean)method.invoke(null,empty,plan),"An invisible guide cannot be accepted by chunk readiness alone");
        var held=new HashMap<>(base);held.put("ready",false);check(!(boolean)method.invoke(null,held,plan),"Renderer parse/native/freshness HOLD remains HOLD");
        System.out.println("Final photo observer PASS "+checks+" adversarial checks; no game, pixels or native acceptance");
    }
}

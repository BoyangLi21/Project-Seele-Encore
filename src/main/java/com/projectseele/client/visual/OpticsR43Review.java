package com.projectseele.client.visual;

import com.google.gson.*;
import com.projectseele.entity.*;
import com.projectseele.visual.CombatR31Review;
import net.minecraft.resources.ResourceLocation;
import java.nio.file.*;
import java.util.*;

/** Observes the selected texture in the real mesh draw, in an isolated fixture only. */
public final class OpticsR43Review
{
    public static final boolean ENABLED=Boolean.getBoolean("projectseele.r43OpticsStates");
    private static final Map<String,JsonObject> SAMPLES=new LinkedHashMap<>();
    public static void draw(EvaUnit01Entity eva,ResourceLocation texture,int light)
    {
        if(!ENABLED||!CombatR31Review.ENABLED||eva.getId()!=CombatR31Review.evaId)return;
        String label=CombatR31Review.photo;if(!label.startsWith("r43_optics_"))return;
        boolean dark=label.equals("r43_optics_parked")||label.equals("r43_optics_post_berserk");
        boolean actualDark=texture.getPath().equals("dynamic/unit01_eyes_dormant");
        boolean normal=texture.getPath().equals("textures/entity/eva_unit01_eyes.png");
        var row=new JsonObject();row.addProperty("case",label);row.addProperty("texture",texture.toString());
        row.addProperty("light",light);row.addProperty("powered",eva.isPoweredOn());row.addProperty("eyes_enabled",EvaDorsalMechanism.eyesEnabled(eva));
        row.addProperty("expected_surface",dark?"black":"normal painted eye");row.addProperty("passed",dark?actualDark:normal);
        SAMPLES.put(label,row);
    }
    public static void write(Path folder)throws Exception
    {
        if(!ENABLED)return;var rows=new JsonArray();SAMPLES.values().forEach(rows::add);
        var result=new JsonObject();result.add("samples",rows);
        result.addProperty("passed",SAMPLES.size()==4&&SAMPLES.values().stream().allMatch(r->r.get("passed").getAsBoolean()));
        Files.writeString(folder.resolve("optics_r43.json"),new GsonBuilder().setPrettyPrinting().create().toJson(result));
    }
    private OpticsR43Review(){}
}

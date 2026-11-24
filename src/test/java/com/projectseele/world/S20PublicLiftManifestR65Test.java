package com.projectseele.world;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;

/** The R65 public lift file: an open lift parses, and nothing that belongs to headquarters lifts gets through. */
public final class S20PublicLiftManifestR65Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    private static JsonObject floor(int y, String exit, boolean restricted, String callKind)
    {
        String door = exit.equals("east") ? "[156," + y + ",768]" : "[153," + y + ",771]";
        String cabinDoor = exit.equals("east") ? "[155," + y + ",768]" : "[153," + y + ",770]";
        return JsonParser.parseString("{\"label\":\"stop " + y + "\",\"cabin\":[153," + y + ",768],\"exit\":\"" + exit + "\",\"approach_y\":" + y
                + ",\"controller\":[150," + y + ",768],\"restricted\":" + restricted
                + ",\"calls\":[{\"kind\":\"" + callKind + "\",\"position\":[157," + (y + 1) + ",766],"
                + "\"state\":\"minecraft:polished_blackstone_button[face=wall,facing=east,powered=false]\",\"facing\":\"east\","
                + "\"target_controller\":[150," + y + ",768]}],"
                + "\"landing_doors\":[{\"pos\":" + door + ",\"closed_state\":\"minecraft:gray_stained_glass\"}],"
                + "\"cabin_doors\":[{\"pos\":" + cabinDoor + ",\"closed_state\":\"minecraft:light_gray_stained_glass\"}]}").getAsJsonObject();
    }

    private static JsonObject manifest(String id, JsonObject... floors)
    {
        var lift = JsonParser.parseString("{\"id\":\"" + id + "\",\"controller_side\":\"west\",\"controller_facing\":\"east\","
                + "\"inside_button_offset\":[-2,1,0],\"inside_display_offset\":[-2,2,0]}").getAsJsonObject();
        var rows = new JsonArray();
        for (var f : floors) rows.add(f);
        lift.add("floors", rows);
        var root = new JsonObject();
        root.addProperty("schema", S20LiftManifestR52.PUBLIC_SCHEMA);
        var lifts = new JsonArray();
        lifts.add(lift);
        root.add("lifts", lifts);
        return root;
    }

    private static boolean refused(JsonObject root)
    {
        try
        {
            S20LiftManifestR52.parsePublic(root, null);
            return false;
        }
        catch (IllegalArgumentException expected)
        {
            return true;
        }
    }

    public static void main(String[] args)
    {
        String id = "r65-public-south-residential";
        var lifts = S20LiftManifestR52.parsePublic(manifest(id, floor(63, "east", false, "vanilla_button"),
                floor(81, "east", false, "vanilla_button"), floor(161, "south", false, "vanilla_button")), null);
        check(lifts.size() == 1 && lifts.get(0).id().equals(id), "A three-stop public lift parses");
        check(lifts.get(0).floors().size() == 3 && lifts.get(0).floor(161).exit() == net.minecraft.core.Direction.SOUTH,
                "Each stop keeps its own exit");
        check(lifts.get(0).spec().stops().size() == 3, "It becomes a lift the director can run");

        check(refused(manifest("s20-command-rear-x12-z253-v4", floor(63, "east", false, "vanilla_button"), floor(81, "east", false, "vanilla_button"))),
                "A headquarters identity cannot be declared as public");
        check(refused(manifest(id, floor(63, "east", false, "vanilla_button"), floor(81, "east", true, "vanilla_button"))),
                "A public lift has no card floors");
        check(refused(manifest(id, floor(63, "east", false, "vanilla_button"), floor(81, "east", false, "seele_reader"))),
                "A public lift has no card readers");
        check(refused(manifest(id, floor(63, "east", false, "vanilla_button"))), "A public lift needs two stops");
        check(refused(manifest(id, floor(81, "east", false, "vanilla_button"), floor(63, "east", false, "vanilla_button"))),
                "Stops are listed bottom to top");
        var wrong = manifest(id, floor(63, "east", false, "vanilla_button"), floor(81, "east", false, "vanilla_button"));
        wrong.addProperty("schema", S20LiftManifestR52.SCHEMA);
        check(refused(wrong), "The headquarters schema is not a public lift file");
        System.out.println("S20PublicLiftManifestR65Test: " + checks + " checks");
    }
}

package com.projectseele.world;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Collections;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import net.minecraft.world.phys.Vec3;

/** One immutable geometry and actuator definition for the supplied replacement carrier. */
public final class CarrierAssemblyR53
{
    public static final float RISE_END = .9F;
    public static final String SELECTION = "eva/carrier_assembly_r53_sources.json";
    public static final String MESH = "mesh/carrier_mk2_r53.json";
    public static final String MAST_SLOT_REVISION = "rear-slot-xneg8p6-z6p4-closed-v1";
    private static boolean checked;
    private static Profile installed;

    public static synchronized Profile selected()
    {
        if (checked) return installed;
        try (var stream = CarrierAssemblyR53.class.getResourceAsStream("/assets/projectseele/" + SELECTION))
        {
            if (stream != null)
            {
                byte[] selection = stream.readAllBytes();
                var manifest = parse(selection);
                require("projectseele.r53.carrier-selection.v1".equals(manifest.get("schema").getAsString()), "Carrier selection schema");
                var hashes = manifest.getAsJsonObject("resources");
                require(hashes.has(MESH), "Selected carrier mesh missing");
                byte[] source = null;
                for (var entry : hashes.entrySet())
                {
                    byte[] bytes = EvaOriginalMeshGeometryR52.classpathBytes(entry.getKey());
                    require(sha(bytes).equals(entry.getValue().getAsString()), "Changed carrier resource: " + entry.getKey());
                    if (entry.getKey().equals(MESH)) source = bytes;
                }
                installed = read(parse(source), sha(selection));
            }
            checked = true;
            return installed;
        }
        catch (IOException failure)
        {
            throw new IllegalStateException("Selected carrier source unavailable", failure);
        }
    }

    // These five connected source members are the two load feet, central spine,
    // and upper joins. The other 34 members belong to the replaced clamp drive.
    private static final int[] RETAINED_HANGER_TRIANGLES = {0,1,2,3,4,5,6,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,214,215,216,217,218,219,220,221,222,223,272,273,274,275,276,277,278,279,280,281,282,283,716,717,718,719,720,721,722,723,732,733,734,735,822,823,824,825,828,829,1108,1109,1110,1111,1112,1113,1114,1115,1116,1117,1118,1119,1120,1121,1122,1123,1124,1125,1126,1127,1128,1129,1130,1131,1132,1133,1134,1135,1136,1137,1138,1139,1140,1141,1142,1143,1144,1145,1146,1147,1148,1149,1198,1199,1200,1201,1632,1633,1634,1635,1636,1637,1648,1649,1650,1651,1652,1653,1658,1659,2012,2013,2014,2015,2016,2017,2018,2019,2020,2021,2022,2023,2024,2025,2026,2027,2028,2029,2030,2031,2032,2033,2034,2035,2036,2037,2038,2039,2040,2041,2042,2043,2044,2045,2046,2047,2048,2049,2050,2051};
    private static boolean declaredHangerRefit(JsonObject old, JsonObject now)
    {
        if (!now.has("duplicate_hanger_refit_r53")) return false;
        var declaration = now.getAsJsonObject("duplicate_hanger_refit_r53");
        if (!"four_jaw_hollow_drive_replaces_redundant_side_hangers".equals(declaration.get("mode").getAsString())
                || !"retract_body".equals(declaration.get("part").getAsString())
                || declaration.get("retired_components").getAsInt() != 34
                || declaration.get("retired_triangles").getAsInt() != 1894) return false;
        var before = old.getAsJsonObject("parts").getAsJsonArray("retract_body");
        var after = now.getAsJsonObject("parts").getAsJsonArray("retract_body");
        if (before.size() != 2056 * 24 || after.size() != RETAINED_HANGER_TRIANGLES.length * 24) return false;
        int offset = 0;
        for (int triangle : RETAINED_HANGER_TRIANGLES)
            for (int value = 0; value < 24; value++)
                if (!before.get(triangle * 24 + value).equals(after.get(offset++))) return false;
        var interfaces = now.getAsJsonObject("engineering_upright_drive_r53").getAsJsonArray("interfaces");
        for (var item : interfaces)
        {
            var joint = item.getAsJsonObject();
            if (!joint.get("jaw").getAsString().equals("clamp_upper_r")) continue;
            if (!joint.get("body_anchor_part").getAsString().equals("retract_spine")) return false;
            var spine = now.getAsJsonObject("parts").getAsJsonArray("retract_spine");
            int start = joint.get("body_anchor_triangle").getAsInt() * 24;
            var patch = joint.getAsJsonArray("body_anchor_patch");
            for (int v = 0; v < 3; v++) for (int axis = 0; axis < 3; axis++)
                if (spine.get(start + v * 8 + axis).getAsFloat() != patch.get(v).getAsJsonArray().get(axis).getAsFloat()) return false;
            return true;
        }
        return false;
    }

    private static final Map<String,Boolean> RETAINED = new LinkedHashMap<>();
    /** Load surfaces retain their exact predecessor. The declared four-jaw
     * refit may replace only the enumerated redundant side-hanger components. */
    public static synchronized boolean retainsSourceSurface(String expected) throws IOException
    {
        var cached=RETAINED.get(expected);if(cached!=null)return cached;
        byte[] current=EvaOriginalMeshGeometryR52.classpathBytes(MESH);
        if(sha(current).equals(expected)){RETAINED.put(expected,true);return true;}
        var now=parse(current);if(!now.has("retained_surface_predecessor"))return false;
        String path=now.get("retained_surface_predecessor").getAsString();
        if(!path.equals("mesh/carrier_mk2_pre_upright_r53.json"))return false;
        byte[] previous=EvaOriginalMeshGeometryR52.classpathBytes(path);
        if(!sha(previous).equals(expected))return false;
        var old=parse(previous);var oldParts=old.getAsJsonObject("parts");var newParts=now.getAsJsonObject("parts");
        var material=old.getAsJsonObject("materials");int count=0;
        for(var part:oldParts.entrySet())if(material==null||!material.has(part.getKey()))
        {if((!part.getValue().equals(newParts.get(part.getKey())) && !(part.getKey().equals("retract_body") && declaredHangerRefit(old,now))) ||now.getAsJsonObject("materials").has(part.getKey()))return false;count+=part.getValue().getAsJsonArray().size()/24;}
        boolean same=count==8727&&old.get("anchors").equals(now.get("anchors"))&&old.get("texture").equals(now.get("texture"));
        RETAINED.put(expected,same);return same;
    }

    private static Profile read(JsonObject source, String fingerprint)
    {
        require("projectseele.r53.carrier-assembly.v1".equals(source.get("schema").getAsString())
                && source.get("stride").getAsInt() == 8, "Carrier surface schema");
        boolean hangerRefit = source.has("duplicate_hanger_refit_r53");
        if (hangerRefit)
        {
            try
            {
                var previous = parse(EvaOriginalMeshGeometryR52.classpathBytes("mesh/carrier_mk2_pre_upright_r53.json"));
                require(declaredHangerRefit(previous, source), "Exact declared duplicate hanger replacement required");
                for (var part : previous.getAsJsonObject("parts").entrySet())
                    if (!part.getKey().equals("retract_body") && !previous.getAsJsonObject("materials").has(part.getKey()))
                        require(part.getValue().equals(source.getAsJsonObject("parts").get(part.getKey())), "Original load member changed");
            }
            catch (IOException missing) { throw new IllegalStateException("Original hanger replacement source missing", missing); }
        }
        require(source.get("source_triangles").getAsInt() == 8727
                && source.getAsJsonObject("fitting").get("source_faces_removed").getAsInt() == (hangerRefit ? 1894 : 0),
                "Complete declared carrier assembly required");
        var materials = source.getAsJsonObject("materials");
        String texture = source.get("texture").getAsString();
        var parts = new LinkedHashMap<String, Surface>();
        int imported = 0;
        for (var entry : source.getAsJsonObject("parts").entrySet())
        {
            String name = entry.getKey();
            var values = entry.getValue().getAsJsonArray();
            require(!values.isEmpty() && values.size() % 24 == 0, "Complete carrier triangles required");
            float[] encoded = new float[values.size()];
            for (int i = 0; i < encoded.length; i++)
            {
                encoded[i] = values.get(i).getAsFloat();
                require(Float.isFinite(encoded[i]), "Finite carrier vertices required");
            }
            boolean engineering = materials != null && materials.has(name);
            if (!engineering) imported += encoded.length / 24;
            parts.put(name, new Surface(encoded, engineering ? materials.get(name).getAsString() : texture));
        }
        require(imported == (hangerRefit ? 6833 : 8727) && parts.keySet().containsAll(Set.of("body", "deck", "toe_l", "toe_r",
                "clamp_upper_l", "clamp_upper_r", "clamp_lower_l", "clamp_lower_r")), "Carrier assemblies incomplete");
        var anchor = source.getAsJsonObject("anchors").getAsJsonArray("power_reel");
        var power = new Vec3(anchor.get(0).getAsDouble(), anchor.get(1).getAsDouble(), anchor.get(2).getAsDouble());
        require(Double.isFinite(power.lengthSqr()), "Finite carrier reel anchor required");
        applyMastSlotR54(parts);
        return new Profile(Collections.unmodifiableMap(parts), power, sha((fingerprint+MAST_SLOT_REVISION).getBytes(StandardCharsets.UTF_8)));
    }

    /** Explicit machining of three stationary rear members. The original input
     * is still validated above; collision and rendering consume this one result.
     * Six sole supports end at Z5.55973, ahead of the unchanged Z6.4 boundary. */
    private static void applyMastSlotR54(Map<String,Surface> parts)
    {
        try
        {
            var revision=parse(EvaOriginalMeshGeometryR52.classpathBytes("mesh/carrier_mast_slot_r54.json"));
            require(revision.get("schema").getAsString().equals("projectseele.carrier-mast-slot.r54.v1")
                    &&revision.get("revision").getAsString().equals(MAST_SLOT_REVISION),"Declared rear service slot required");
            var cut=revision.getAsJsonObject("cut");
            require(cut.get("min_x").getAsDouble()==-8.6&&cut.get("min_z").getAsDouble()==6.4,"Fixed original foot-isolation boundary required");
            for(String name:Set.of("deck","toe_l","toe_r"))
            {
                var original=parts.get(name);var report=revision.getAsJsonObject("report").getAsJsonObject(name);
                require(original.encoded.length/24==report.get("original_triangles").getAsInt(),"Original stationary member revision changed");
                var values=revision.getAsJsonObject("parts").getAsJsonArray(name);var encoded=new float[values.size()];
                require(encoded.length%24==0&&report.get("closure_triangles").getAsInt()>0,"Complete capped slot triangles required");
                for(int i=0;i<encoded.length;i++)
                {encoded[i]=values.get(i).getAsFloat();require(Float.isFinite(encoded[i]),"Finite rear refit vertices required");}
                for(int i=0;i<encoded.length;i+=8)require(encoded[i]<=-8.6+1e-5||encoded[i+2]<=6.4+1e-5,"Rear vertical channel must remain clear");
                parts.put(name,new Surface(encoded,original.texture));
            }
        }
        catch(IOException missing){throw new IllegalStateException("Declared capped rear service slot unavailable",missing);}
    }

    public static final class Surface
    {
        private final float[] encoded;
        private final double[] positions;
        private final String texture;

        private Surface(float[] encoded, String texture)
        {
            this.encoded = encoded;
            this.texture = texture;
            positions = new double[encoded.length / 8 * 3];
            for (int i = 0; i < encoded.length / 8; i++)
                for (int axis = 0; axis < 3; axis++) positions[i * 3 + axis] = encoded[i * 8 + axis];
        }

        public float[] encoded() { return encoded.clone(); }
        public String texture() { return texture; }
        public double[] positions() { return positions.clone(); }
    }

    public record Profile(Map<String, Surface> parts, Vec3 powerReel, String fingerprint)
    {
        public RigidTransform frame(String part, float rise, float release, double deckTravel, CarrierMountProfileR53.State mounting)
        { return mounting.carrierLocalFrame(this, part, rise, release, deckTravel); }

        public RigidTransform frame(String part, float rise, float release, double deckTravel)
        {
            require(parts.containsKey(part) && Float.isFinite(rise) && rise >= 0 && rise <= 1
                    && Float.isFinite(release) && release >= 0 && release <= 1, "Bounded carrier actuator required");
            require(deckTravel == 0 || deckTravel == 3 || deckTravel == 64, "Declared deck travel required");
            boolean deck = part.equals("deck") || part.startsWith("toe_");
            double opening = Math.min(1, Math.max(0, (1D - rise) / (1D - RISE_END)));
            double y = deck ? -deckTravel * (1 - rise) : -64 * Math.max(0, 1 - rise / (double)RISE_END);
            double retraction = part.equals("retract_spine") ? 2.5 :
                    part.startsWith("retract_") || part.startsWith("clamp_") ? 8 : 0;
            double z = retraction * opening;
            double x = 0;
            if (part.startsWith("clamp_"))
            {
                // Raise behind the armour, then advance and close. Both
                // segments are affine and are swept separately by callers.
                boolean left = part.endsWith("_l") || part.contains("_l_");
                x = (left ? -1 : 1) * 4.5D * Math.max(release, opening);
            }
            return new RigidTransform(new Vec3(x, y, z), 0, 0, 0, 1);
        }

        public Map<String, double[]> posed(float rise, float release, double deckTravel)
        {
            var result = new LinkedHashMap<String, double[]>();
            parts.forEach((name, surface) ->
            {
                var frame = frame(name, rise, release, deckTravel);
                var xyz = surface.positions();
                for (int i = 0; i < xyz.length; i += 3)
                {
                    var point = frame.transformPoint(new Vec3(xyz[i], xyz[i + 1], xyz[i + 2]));
                    xyz[i] = point.x;xyz[i + 1] = point.y;xyz[i + 2] = point.z;
                }
                result.put(name, xyz);
            });
            return Collections.unmodifiableMap(result);
        }
    }

    private static JsonObject parse(byte[] bytes)
    { return JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject(); }

    private static String sha(byte[] bytes)
    {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }

    private static void require(boolean condition, String reason)
    { if (!condition) throw new IllegalArgumentException(reason); }

    private CarrierAssemblyR53() { }
}

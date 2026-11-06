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
    public static final String MAST_SLOT_REVISION = "rear-slot-xneg15-z6p4-closed-v2";
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
                installed = read(parse(EvaOriginalMeshGeometryR52.classpathBytes(MESH)), sha(selection));
            }
            checked = true;
            return installed;
        }
        catch (IOException failure)
        {
            throw new IllegalStateException("Selected carrier source unavailable", failure);
        }
    }

    private static Profile read(JsonObject source, String fingerprint)
    {
        require("projectseele.r53.carrier-assembly.v1".equals(source.get("schema").getAsString())
                && source.get("stride").getAsInt() == 8, "Carrier surface schema");
        var materials = source.getAsJsonObject("materials");
        String texture = source.get("texture").getAsString();
        var parts = new LinkedHashMap<String, Surface>();
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
            parts.put(name, new Surface(encoded, engineering ? materials.get(name).getAsString() : texture));
        }
        require(parts.keySet().containsAll(Set.of("body", "deck", "toe_l", "toe_r",
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
            require(cut.get("min_x").getAsDouble()==-15&&cut.get("min_z").getAsDouble()==6.4,"Fixed original foot-isolation boundary required");
            for(String name:Set.of("deck","toe_l","toe_r"))
            {
                var original=parts.get(name);var report=revision.getAsJsonObject("report").getAsJsonObject(name);
                var values=revision.getAsJsonObject("parts").getAsJsonArray(name);var encoded=new float[values.size()];
                require(encoded.length%24==0&&report.get("closure_triangles").getAsInt()>0,"Complete capped slot triangles required");
                for(int i=0;i<encoded.length;i++)
                {encoded[i]=values.get(i).getAsFloat();require(Float.isFinite(encoded[i]),"Finite rear refit vertices required");}
                for(int i=0;i<encoded.length;i+=8)require(encoded[i]<=-15+1e-5||encoded[i+2]<=6.4+1e-5,"Rear vertical channel must remain clear");
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

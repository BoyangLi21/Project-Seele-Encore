package com.projectseele.client;

import java.lang.reflect.Field;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.InputEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/** Eidan 9000 window modules repeat at 0 and ±80 model pixels. Each bench top
 * spans x=11.5..19.5, z=-26..26 pixels above both sides of the aisle. */
@Mod.EventBusSubscriber(modid = "projectseele", value = Dist.CLIENT)
public final class RailSeatsR65
{
    private static long vehicle;
    private static int car;
    private static Object level;
    private static boolean compatible, seated, changed;
    private static long lastFrame;
    private static double localX, floor, localZ, yaw, pitch, seatX, seatZ;
    private static Field yawField, pitchField;

    public static void frame(long current, int carIndex, double x, double y, double z, Object pose)
    {
        var mc = Minecraft.getInstance();
        if (vehicle != current || car != carIndex || level != mc.level)
        {
            level = mc.level; vehicle = current; car = carIndex; seated = changed = false;
            compatible = eidan(current, carIndex);
        }
        if (!compatible) return;
        try
        {
            if (yawField == null)
            {
                yawField = pose.getClass().getField("yaw");
                pitchField = pose.getClass().getField("pitch");
            }
            yaw = yawField.getDouble(pose); pitch = pitchField.getDouble(pose);
        }
        catch (ReflectiveOperationException ex) { compatible = false; return; }
        lastFrame = System.nanoTime();
        if (!seated && !changed) { localX = x; floor = y; localZ = z; }
        if (seated && mc.options.keyShift.isDown()) { seated = false; changed = true; }
    }

    private static boolean eidan(long current, int index)
    {
        try
        {
            Object data = Class.forName("org.mtr.mod.client.MinecraftClientData").getMethod("getInstance").invoke(null);
            for (Object v : (Iterable<?>)data.getClass().getField("vehicles").get(data))
            {
                if ((long)v.getClass().getMethod("getId").invoke(v) != current) continue;
                Object extra = v.getClass().getField("vehicleExtraData").get(v);
                var cars = (List<?>)extra.getClass().getField("immutableVehicleCars").get(extra);
                if (index < 0 || index >= cars.size()) return false;
                Object model = cars.get(index);
                String name = (String)model.getClass().getMethod("getVehicleId").invoke(model);
                return name.equals("eidan_9000_cab_1") || name.equals("eidan_9000_trailer") || name.equals("eidan_9000_cab_2");
            }
        }
        catch (ReflectiveOperationException ex) { return false; }
        return false;
    }

    public static boolean seated() { return seated && compatible && level == Minecraft.getInstance().level; }
    private static boolean recent()
    {
        return compatible && level == Minecraft.getInstance().level && System.nanoTime() - lastFrame < 300_000_000L;
    }
    public static double aisleX() { return Math.copySign(.38, seatX); }
    public static double floor() { return floor; }
    public static double seatX() { return seatX; }
    public static double seatZ() { return seatZ; }
    public static boolean changed() { return changed; }
    public static void sent() { changed = false; }
    public static void leave() { vehicle = 0; compatible = seated = changed = false; }

    @SubscribeEvent
    public static void use(InputEvent.InteractionKeyMappingTriggered event)
    {
        var mc = Minecraft.getInstance();
        if (!event.isUseItem() || event.getHand() != InteractionHand.MAIN_HAND || !recent() || seated
                || mc.player == null || mc.screen != null || mc.player.isShiftKeyDown()) return;
        Vec3 ray = mc.player.getLookAngle().yRot((float)-yaw).xRot((float)-pitch);
        if (ray.y >= -.02) return;
        double distance = (mc.player.getEyeHeight() - 6.0 / 16) / -ray.y;
        if (distance < 0 || distance > 4.5) return;
        double x = localX + distance * ray.x, z = localZ + distance * ray.z;
        double centre = 5 * Math.rint(z / 5);
        if (Math.abs(x) < 11.5 / 16 || Math.abs(x) > 19.5 / 16 || Math.abs(centre) > 5
                || Math.abs(z - centre) > 26.0 / 16) return;
        seatX = Math.copySign(15.0 / 16, x);
        // Four equally spaced adult places on the 3.25-block bench.
        int place = Math.min(3, (int)Math.floor((z - centre + 26.0 / 16) / (13.0 / 16)));
        seatZ = centre + (place - 1.5) * 13.0 / 16;
        if (mc.level != null)
        {
            Vec3 delta = new Vec3(seatX-localX, -.36, seatZ-localZ).xRot((float)pitch).yRot((float)yaw);
            Vec3 target = mc.player.position().add(delta);
            if (mc.level.players().stream().anyMatch(p -> p != mc.player && p.distanceToSqr(target) < .30)) return;
        }
        seated = changed = true;
        event.setCanceled(true); event.setSwingHand(false);
    }
    private RailSeatsR65() {}
}

package com.projectseele.client.cockpit;

import com.projectseele.ProjectSeele;
import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.client.ClientForgeEvents;
import com.projectseele.client.EncounterObserverCacheR45;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.RamielEntity;
import com.projectseele.entity.YashimaCannonGeometryR52;
import com.projectseele.network.ClientboundCannonBeamPacket;
import com.projectseele.network.ClientboundCannonServiceR64;
import com.projectseele.network.ClientboundEncounterObserverPacket;
import com.projectseele.registry.ModSounds;
import com.projectseele.world.EvaPilotResolver;
import java.util.Locale;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.resources.language.I18n;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.sounds.SoundEvent;
import net.minecraft.util.Mth;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ViewportEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

/**
 * R64: the positron cannon's sight, in first person in the plug.
 * <p>
 * In the original the sniper does not aim with the Unit's eyes: a sight comes down over the pilot's face, and in it
 * a fixed mark stands in the middle while others drift towards it; the shot is let go when they meet. This is that
 * sight, by this mod's own design. Its housing is part of the plug's inside (CockpitMeshR64.visor: it swings down
 * from a hinge over the pilot's head); what is drawn here is its glass and its display, and each mark on the
 * display is a true thing (CannonSightMathR64):
 * <ul>
 * <li>the barrel's mark is the point the bore's ray reaches, seen from the pilot's eye. The emplaced gun at Yashima
 * fires along its barrel, which follows the view at two degrees a tick inside a sector about the target: the mark
 * trails a quick look and stops at the sector's edge. The carried cannon's barrel is the view itself, held to the
 * arms' limits and seen from beside the muzzle;</li>
 * <li>the energy's mark (three arrowheads) winds in on the barrel's as the charge rises;</li>
 * <li>the core's mark is the target's core where it is, shut or open, and whether the bore's ray passes through it.</li>
 * </ul>
 * Beside the picture stand the figures of the shot, all read from the game (range, the barrel's elevation and
 * bearing, how far it still has to turn, the charge, and at Yashima the power that reaches the gun and the target's
 * own charge), and after a shot the gun's service as the server counts it. Firing whites the picture out and leaves
 * an after-image. No number of the cannon is changed by any of it.
 * <p>
 * Off with the plug's first person (-Dprojectseele.cockpitR64=false) or with cockpit.cannonSight in the client
 * config: the scope of R63 is drawn then.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PlugCannonSightR64
{
    private static final int AMBER = 0xFFE8A058, GREEN = 0xFF7CF08A, PALE = 0xFFDCE4DC, RED = 0xFFF16B51, MUTED = 0xFF8FA09A;
    /** Seconds the sight takes to come down, and how long it stays down after a shot. */
    private static final float TRAVEL = .6F, STAY = 2.6F;
    /** From this much of its way down the housing is before the eyes: the wall's windows are behind it from here on. */
    public static final float SETTLING = .8F;
    /** From this much of its way down the housing's shell is passing before the plug's wall: the wall's side windows are behind it. */
    public static final float COVERING = .35F;
    /** From this far down the lens takes the picture and the field of view begins to narrow. */
    private static final float LENS = .55F;

    /** What the sight shows this frame: where each mark is on the picture, and the figures beside it. */
    private static final class Solve
    {
        boolean valid, fixed, limit, coreInPlay, coreOpen, through, reaches, on, coreSeen;
        float boreX, boreY, coreX, coreY, coreR, charge, closing;
        double barrelOff, wishOff, range = -1, elevation, bearing, coreMiss;
    }
    private static final Solve NOW = new Solve();

    private static float down, flash, ghost, shotAge = 99, ghostX, ghostY;
    private static long frame, stayUntil, solvedAt;
    private static double fov = 70;
    private static float roll;
    private static boolean wanted, wasOn, wasCooling, wasDown;
    private static int tickClock, sinceTick, ventAt = -1, fuseAt = -1;
    private static ClientboundCannonServiceR64 service;
    private static long serviceAt;
    private static RamielEntity target;
    private static int targetLooked = -100;

    private PlugCannonSightR64() {}

    /** The sight is the plug's (and not the R63 scope) for this pilot. */
    public static boolean enabled()
    {
        return PilotCockpitR64.ON && SeeleConfig.COCKPIT_CANNON_SIGHT.get();
    }

    /** How far the sight is down over the pilot's face, 0..1. */
    public static float down()
    {
        return enabled() ? down : 0;
    }

    /** The field of view's share with the sight where it is and the charge where it is. */
    public static float field(EvaUnit01Entity eva)
    {
        // The lens takes the picture as the housing settles before the eyes, not while it is still swinging down.
        return CannonSightMathR64.field(Mth.clamp((down - LENS) / (1 - LENS), 0, 1), eva == null ? 0 : eva.chargeProgress());
    }

    /** The lens has the picture: the gun itself, which lies beside the pilot's eye, is left out of the magnified view. */
    public static boolean magnifying()
    {
        return enabled() && down > LENS;
    }

    public static void receive(ClientboundCannonServiceR64 packet)
    {
        var level = Minecraft.getInstance().level;
        if (level == null) return;
        service = packet;
        serviceAt = level.getGameTime();
    }

    /** The server's gunnery for this Unit, no older than two seconds; null elsewhere. */
    private static ClientboundCannonServiceR64 service(EvaUnit01Entity eva)
    {
        var level = Minecraft.getInstance().level;
        return service != null && level != null && eva != null && service.entity() == eva.getId() && level.getGameTime() - serviceAt <= 40 ? service : null;
    }

    private static int serviceAge()
    {
        var level = Minecraft.getInstance().level;
        return level == null ? 0 : (int) Mth.clamp(level.getGameTime() - serviceAt, 0, 40);
    }

    /** A beam has left a cannon: if it is this pilot's own, the picture whites out and the sight stays down a while. */
    public static boolean fired(ClientboundCannonBeamPacket packet)
    {
        Minecraft mc = Minecraft.getInstance();
        EvaUnit01Entity eva = mc.player == null ? null : EvaPilotResolver.controlTarget(mc.player);
        if (!enabled() || eva == null || eva.getWeapon() != EvaUnit01Entity.WEAPON_CANNON) return false;
        Vec3 muzzle = muzzle(eva, bore(eva, mc.player, 1), 1);
        if (muzzle == null || muzzle.distanceToSqr(packet.x1, packet.y1, packet.z1) > 100) return false;
        flash = 1; ghost = 1; shotAge = 0;
        ghostX = NOW.boreX; ghostY = NOW.boreY;
        stayUntil = System.nanoTime() + (long) (STAY * 1e9);
        ventAt = tickClock + 3; fuseAt = tickClock + 26;
        return true;
    }

    /** The bore's direction: the emplaced gun's own barrel, or the carried cannon's (the view within the arms' limits). */
    private static Vec3 bore(EvaUnit01Entity eva, LocalPlayer player, float partial)
    {
        var gun = eva.fixedCannonBodyR52();
        var geometry = gun == null ? null : gun.geometryR52();
        if (geometry != null) return geometry.boreWorld(gun.aimR52(partial));
        return Vec3.directionFromRotation(eva.clampPilotWeaponPitch(player.getViewXRot(partial), partial), eva.clampPilotWeaponYaw(player.getViewYRot(partial), partial));
    }

    private static Vec3 muzzle(EvaUnit01Entity eva, Vec3 bore, float partial)
    {
        var gun = eva.fixedCannonBodyR52();
        var geometry = gun == null ? null : gun.geometryR52();
        if (geometry != null) return geometry.point(gun.getPosition(partial), gun.aimR52(partial), geometry.muzzle());
        return eva.getMuzzlePositionForPoseCapture(bore);
    }

    /** Every frame, whatever is drawn: the sight comes down while the trigger is held and for a while after a shot. */
    @SubscribeEvent
    public static void advance(TickEvent.RenderTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (event.phase != TickEvent.Phase.START || mc.isPaused()) return;
        long now = AircraftRenderClockR21.frameNanos();
        float dt = frame == 0 ? 0 : Mth.clamp((now - frame) / 1e9F, 0, .1F);
        if (now == frame) return;
        frame = now;
        LocalPlayer player = mc.player;
        EvaUnit01Entity eva = player == null ? null : EvaPilotResolver.controlTarget(player);
        boolean cannon = enabled() && eva != null && eva.getWeapon() == EvaUnit01Entity.WEAPON_CANNON && mc.options.getCameraType().isFirstPerson();
        wanted = cannon && (ClientForgeEvents.isCannonScopeActive(eva) || System.nanoTime() < stayUntil);
        down = Mth.clamp(down + (wanted ? dt : -dt) / TRAVEL, 0, 1);
        flash *= (float) Math.exp(-dt / .16F);
        ghost = Math.max(0, ghost - dt / 2.4F);
        shotAge += dt;
    }

    /** The field of view and the roll the world is drawn with, after every other handler: the marks are laid with them. */
    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void drawnFov(ViewportEvent.ComputeFov event)
    {
        if (event.usedConfiguredFov()) fov = event.getFOV();
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void drawnAngles(ViewportEvent.ComputeCameraAngles event)
    {
        roll = event.getRoll();
    }

    /**
     * The window of the sight on the picture: left, top, right, bottom, and the margin its writing keeps from its
     * edges. The housing itself is part of the plug's inside (CockpitMeshR64.visor), which is given these measures.
     */
    public static int[] window(int width, int height)
    {
        int high = Math.round(height * .60F), wide = Math.min(Math.round(width * .74F), Math.round(high * 1.6F));
        int left = (width - wide) / 2, top = (height - high) / 2;
        return new int[]{left, top, left + wide, top + high, 6};
    }

    private static float smooth(float value)
    {
        return value * value * (3 - 2 * value);
    }

    /** The kick a shot gives the housing, in radians about its hinge. */
    public static float jolt()
    {
        return shotAge < 1.2F ? (float) (Math.sin(shotAge * 34) * Math.exp(-shotAge * 7) * .012) : 0;
    }

    /** The charge the sight last showed, 0..1, and whether the shot was on: the housing's lamps show them too. */
    public static float charge()
    {
        Minecraft mc = Minecraft.getInstance();
        return NOW.valid && mc.level != null && mc.level.getGameTime() - solvedAt <= 2 ? NOW.charge : 0;
    }

    public static boolean locked()
    {
        Minecraft mc = Minecraft.getInstance();
        return NOW.valid && NOW.on && mc.level != null && mc.level.getGameTime() - solvedAt <= 2;
    }

    /** How much of the sight's own display is lit: it comes on as the housing settles before the eyes. */
    private static float lit()
    {
        return smooth(Mth.clamp((down - SETTLING) / (1 - SETTLING), 0, 1));
    }

    /**
     * The sight's glass, drawn under the housing and the pilot's hands: a little of its own colour, the lines of
     * its screen, the flash of a shot and what a flash leaves in the eye.
     */
    public static void hood(GuiGraphics g, int width, int height)
    {
        float see = lit();
        if (!enabled() || see <= .02F) return;
        int[] w = window(width, height);
        int left = w[0], top = w[1], right = w[2], bottom = w[3];
        // What is seen through the sight is the sight's own picture: its phosphor's colour over the whole of it, the
        // lines of its screen, one brighter line that runs down it every few seconds, and its corners and edges dark.
        g.fill(left, top, right, bottom, Math.round(44 * see) << 24 | 0x5A7A30);
        for (int y = top; y < bottom; y += 2) g.fill(left, y, right, y + 1, Math.round(26 * see) << 24);
        int run = top + (int) (frame / 12_000_000L % Math.max(1, (bottom - top) * 2));
        if (run < bottom - 3) g.fill(left, run, right, run + 3, Math.round(14 * see) << 24 | 0xD8FFC0);
        for (int ring = 0; ring < 9; ring++)
        {
            int inset = ring * 3, shade = Math.round((9 - ring) * (9 - ring) * 1.5F * see) << 24;
            g.fill(left + inset, top + inset, right - inset, top + inset + 3, shade);
            g.fill(left + inset, bottom - inset - 3, right - inset, bottom - inset, shade);
            g.fill(left + inset, top + inset + 3, left + inset + 3, bottom - inset - 3, shade);
            g.fill(right - inset - 3, top + inset + 3, right - inset, bottom - inset - 3, shade);
        }
        if (ghost > 0)
        {
            // The after-image: the bright core of the flash burnt in where the barrel pointed (dark, as an eye keeps
            // it), soft at its edge, and grain over the glass.
            int gx = Math.round(ghostX), gy = Math.round(ghostY), alpha = Math.round(ghost * ghost * 44), size = Math.max(1, Math.round(height / 240F));
            for (int layer = 0; layer < 5; layer++)
            {
                int rx = Math.round(40 * size * (1 - layer * .19F)), ry = Math.round(24 * size * (1 - layer * .19F));
                for (int dy = -ry; dy <= ry; dy++)
                {
                    int y = gy + dy, half = Math.round(rx * (float) Math.sqrt(1 - dy * dy / (float) (ry * ry + 1)));
                    if (y >= top && y < bottom) g.fill(Math.max(left, gx - half), y, Math.min(right, gx + half + 1), y + 1, alpha << 24 | 0x1C1030);
                }
            }
            long seed = frame * 0x9E3779B97F4A7C15L;
            int grains = Math.round(ghost * 90);
            for (int i = 0; i < grains; i++)
            {
                seed = seed * 6364136223846793005L + 1442695040888963407L;
                int x = left + (int) ((seed >>> 33) % Math.max(1, right - left)), y = top + (int) ((seed >>> 17 & 0x7FFF) % Math.max(1, bottom - top));
                g.fill(x, y, x + 1 + (int) (seed >>> 60 & 1), y + 1, (int) (ghost * 110) << 24 | ((seed >>> 50 & 1) == 0 ? 0xFFFFFF : 0x000000));
            }
        }
        if (flash > .004F) g.fill(left, top, right, bottom, Math.min(255, Math.round(flash * 300)) << 24 | 0xFFF6E2);
    }

    /**
     * A light that would cover the whole picture (the strategic blast's overexposure) is, under the sight, on its
     * glass only. True when the sight took it.
     */
    public static boolean glass(GuiGraphics g, int width, int height, int colour)
    {
        if (!enabled() || down < SETTLING) return false;
        int[] w = window(width, height);
        g.fill(w[0], w[1], w[2], w[3], colour);
        return true;
    }

    /** A line kept to the window. */
    private static void line(GuiGraphics g, int x0, int y0, int x1, int y1, int colour, int[] w)
    {
        int steps = Math.max(1, Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)));
        for (int i = 0; i <= steps; i++) dot(g, Math.round(Mth.lerp(i / (float) steps, x0, x1)), Math.round(Mth.lerp(i / (float) steps, y0, y1)), colour, w);
    }

    /** A ring of so many dashes (0 for a whole one), turned by an angle. */
    private static void ring(GuiGraphics g, float cx, float cy, float radius, int colour, int dashes, float turn, int[] w)
    {
        int steps = Math.max(16, Math.round(radius * 6.4F));
        for (int i = 0; i < steps; i++)
        {
            float angle = i * Mth.TWO_PI / steps;
            if (dashes > 0 && Math.floorMod(Math.round((angle + turn) * dashes / Mth.PI), 2) == 1) continue;
            dot(g, Math.round(cx + Mth.cos(angle) * radius), Math.round(cy + Mth.sin(angle) * radius), colour, w);
        }
    }

    private static void dot(GuiGraphics g, int x, int y, int colour, int[] w)
    {
        if (x >= w[0] && x < w[2] && y >= w[1] && y < w[3]) g.fill(x, y, x + 1, y + 1, colour);
    }

    private static void box(GuiGraphics g, int x0, int y0, int x1, int y1, int colour, int[] w)
    {
        x0 = Math.max(x0, w[0]); y0 = Math.max(y0, w[1]); x1 = Math.min(x1, w[2]); y1 = Math.min(y1, w[3]);
        if (x1 > x0 && y1 > y0) g.fill(x0, y0, x1, y1, colour);
    }

    /** The target, where the pilot's client has it: looked for twice a second. */
    private static RamielEntity target(Minecraft mc, Vec3 from, double range)
    {
        if (tickClock - targetLooked >= 10 || target != null && (!target.isAlive() || target.level() != mc.level))
        {
            targetLooked = tickClock;
            target = null;
            double nearest = range * range;
            for (var entity : mc.level.entitiesForRendering())
                if (entity instanceof RamielEntity ramiel && ramiel.isAlive() && ramiel.distanceToSqr(from) < nearest) { nearest = ramiel.distanceToSqr(from); target = ramiel; }
        }
        return target;
    }

    /** Where each mark is this frame. */
    private static void solve(Minecraft mc, LocalPlayer player, EvaUnit01Entity eva, float partial, int width, int height)
    {
        Solve s = NOW;
        s.valid = false;
        var camera = mc.gameRenderer.getMainCamera();
        Vec3 eye = camera.getPosition();
        var look = camera.getLookVector(); var up = camera.getUpVector(); var left = camera.getLeftVector();
        double[] forward = {look.x(), look.y(), look.z()}, upward = {up.x(), up.y(), up.z()}, right = {-left.x(), -left.y(), -left.z()};
        Vec3 bore = bore(eva, player, partial);
        Vec3 muzzle = muzzle(eva, bore, partial);
        if (bore == null || muzzle == null) return;
        var gun = eva.fixedCannonBodyR52();
        var geometry = gun == null ? null : gun.geometryR52();
        s.fixed = geometry != null && eva.fixedCannonOperatingR52();
        double range = eva.effectiveCannonRangeR45();
        ClientboundCannonServiceR64 told = service(eva);

        // The core: the target the client has; too far for that (Yashima), the far view of it that its picture is
        // drawn from; failing both, what the server tells the sight.
        RamielEntity ramiel = target(mc, muzzle, range + 64);
        Vec3 core = null; double coreRadius = 0; boolean open = false; AABB box = null;
        if (ramiel != null)
        {
            core = ramiel.getPosition(partial).add(0, ramiel.getBbHeight() * .5, 0);
            coreRadius = RamielEntity.CORE_RADIUS * ramiel.modelScaleR52();
            open = ramiel.isExposed();
            box = ramiel.getBoundingBox();
        }
        else
        {
            var view = EncounterObserverCacheR45.freshView().orElse(null);
            var seen = view == null || !ClientboundEncounterObserverPacket.RAMIEL.equals(view.current().entityType()) ? null : view.current().snapshot();
            if (seen != null && (seen.flags() & ClientboundEncounterObserverPacket.ALIVE) != 0)
            {
                core = seen.position().add(0, seen.height() * .5, 0);
                coreRadius = RamielEntity.CORE_RADIUS * seen.height() / 15F;
                open = (seen.flags() & ClientboundEncounterObserverPacket.EXPOSED) != 0;
                double half = seen.width() * .5;
                box = new AABB(seen.position().x - half, seen.position().y, seen.position().z - half, seen.position().x + half, seen.position().y + seen.height(), seen.position().z + half);
            }
            else if (told != null)
            {
                core = new Vec3(told.coreX(), told.coreY(), told.coreZ()); coreRadius = told.coreRadius(); open = told.exposed();
            }
        }
        // A core far off the barrel's line (behind the gun, or another fight's) is not this shot's.
        s.coreSeen = box != null;
        s.coreInPlay = core != null && CannonSightMathR64.apart(bore.x, bore.y, bore.z, core.x - muzzle.x, core.y - muzzle.y, core.z - muzzle.z) < 50;
        s.coreOpen = open;

        // Where the bore's ray ends: at the ground or a wall within sight, else at the core's distance or the gun's reach.
        double reach = s.coreInPlay ? Math.min(range, core.distanceTo(muzzle)) : range;
        Vec3 far = muzzle.add(bore.scale(Math.min(reach, 384)));
        var ground = player.level().clip(new ClipContext(muzzle, far, ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player));
        boolean wall = ground.getType() != HitResult.Type.MISS;
        Vec3 end = wall ? ground.getLocation() : muzzle.add(bore.scale(reach));
        boolean body = false;
        if (!wall && !s.coreInPlay && range <= 640)
        {
            var hit = com.projectseele.physics.CombatDamageTargetsR44.ray(player.level(), muzzle, end, .3, eva, player);
            if (hit != null) { body = true; end = hit.getLocation(); }
        }
        s.reaches = wall || body;
        s.coreMiss = s.coreInPlay ? CannonSightMathR64.missBy(muzzle.x, muzzle.y, muzzle.z, bore.x, bore.y, bore.z, core.x, core.y, core.z) : 0;
        s.through = s.coreInPlay && !wall && s.coreMiss <= coreRadius && core.distanceTo(muzzle) <= range;
        s.range = s.coreInPlay && !wall ? core.distanceTo(muzzle) : s.reaches ? end.distanceTo(muzzle) : -1;
        s.elevation = Math.toDegrees(Math.asin(Mth.clamp(bore.y, -1, 1)));
        s.bearing = (Math.toDegrees(Math.atan2(bore.x, -bore.z)) + 360) % 360;

        // How far the barrel still is from where it is being sent.
        Vec3 sent = Vec3.directionFromRotation(eva.clampPilotWeaponPitch(player.getViewXRot(partial), partial), eva.clampPilotWeaponYaw(player.getViewYRot(partial), partial));
        s.limit = false;
        if (s.fixed)
        {
            // As the server sends it: to the point the optical line reaches, held to the sector about the target.
            Vec3 point = eye.add(sent.scale(range));
            if (box != null)
            {
                var struck = box.clip(eye, point);
                if (struck.isPresent()) point = struck.get();
            }
            else if (core != null && CannonSightMathR64.missBy(eye.x, eye.y, eye.z, sent.x, sent.y, sent.z, core.x, core.y, core.z) < coreRadius * 1.4) point = eye.add(sent.scale(core.distanceTo(eye)));
            var held = YashimaCannonGeometryR52.aimWithinSectorR54(geometry, gun.getPosition(partial), point, box != null ? box.getCenter() : core);
            Vec3 can = geometry.boreWorld(held);
            Vec3 wish = point.subtract(geometry.point(gun.getPosition(partial), held, geometry.muzzle()));
            s.barrelOff = CannonSightMathR64.apart(bore.x, bore.y, bore.z, can.x, can.y, can.z);
            s.limit = CannonSightMathR64.apart(can.x, can.y, can.z, wish.x, wish.y, wish.z) > .25;
            // The figure beside the picture is how far the barrel is from where the pilot looks, sector or no sector.
            s.wishOff = CannonSightMathR64.apart(bore.x, bore.y, bore.z, point.x - muzzle.x, point.y - muzzle.y, point.z - muzzle.z);
        }
        else
        {
            Vec3 view = player.getViewVector(partial);
            s.barrelOff = CannonSightMathR64.apart(bore.x, bore.y, bore.z, view.x, view.y, view.z);
            s.limit = s.barrelOff > .25;
            s.wishOff = s.barrelOff;
        }

        double[] at = CannonSightMathR64.onPicture(end.x - eye.x, end.y - eye.y, end.z - eye.z, forward, upward, right, fov);
        if (at == null) return;
        float half = height * .5F, cos = Mth.cos(roll * Mth.DEG_TO_RAD), sin = Mth.sin(roll * Mth.DEG_TO_RAD);
        // The view's roll turns the picture about its middle (x to the right, y downwards here).
        s.boreX = width * .5F + (float) (at[0] * cos + at[1] * sin) * half;
        s.boreY = half + (float) (-at[0] * sin + at[1] * cos) * half;
        if (s.coreInPlay)
        {
            double[] c = CannonSightMathR64.onPicture(core.x - eye.x, core.y - eye.y, core.z - eye.z, forward, upward, right, fov);
            if (c == null) s.coreInPlay = false;
            else
            {
                s.coreX = width * .5F + (float) (c[0] * cos + c[1] * sin) * half;
                s.coreY = half + (float) (-c[0] * sin + c[1] * cos) * half;
                s.coreR = (float) (coreRadius / Math.max(1, core.distanceTo(eye)) / Math.tan(Math.toRadians(fov) / 2)) * half;
            }
        }
        s.charge = eva.chargeProgress();
        s.on = CannonSightMathR64.on(s.limit ? 99 : s.barrelOff, s.charge, s.coreInPlay, s.coreOpen, s.through, s.reaches);
        s.closing = CannonSightMathR64.closing(s.limit ? 99 : s.barrelOff, s.charge, s.coreInPlay, s.coreMiss, coreRadius, s.reaches);
        s.valid = true;
        solvedAt = mc.level.getGameTime();
    }

    /** An arrowhead whose point is at (x, y) and which points along (dx, dy). */
    private static void arrow(GuiGraphics g, float x, float y, float dx, float dy, float reach, int colour, int[] w)
    {
        for (int side = -1; side <= 1; side += 2)
        {
            float cos = Mth.cos(side * .5F), sin = Mth.sin(side * .5F), bx = dx * cos - dy * sin, by = dx * sin + dy * cos;
            line(g, Math.round(x), Math.round(y), Math.round(x - bx * reach), Math.round(y - by * reach), colour, w);
        }
    }

    /** The three corners of the barrel's mark, a triangle standing on its point: upper left, upper right, bottom. */
    private static final float[][] CORNERS = {{-.866F, -.5F}, {.866F, -.5F}, {0, 1}};

    /**
     * The scales along the window's edges: the view's elevation up its left edge and its bearing along its lower
     * edge, a tick a degree and a figure every fifth, moving as the pilot looks about. Read from the camera.
     */
    private static void scales(Font font, GuiGraphics g, Minecraft mc, int[] w, int cx, int cy, int height, float see)
    {
        var look = mc.gameRenderer.getMainCamera().getLookVector();
        double elevation = Math.toDegrees(Math.asin(Mth.clamp(look.y(), -1, 1))), bearing = (Math.toDegrees(Math.atan2(look.x(), -look.z())) + 360) % 360;
        double each = height * .5 * Math.tan(Math.toRadians(1)) / Math.tan(Math.toRadians(fov) / 2);
        if (each < 2.5) return;
        int tick = fade(AMBER, see * .55F), figure = fade(AMBER, see * .8F);
        int x = w[0] + 5, y = w[3] - 6;
        for (int degree = (int) Math.floor(elevation - (cy - w[1]) / each); degree <= elevation + (w[3] - cy) / each; degree++)
        {
            int at = cy + (int) Math.round((elevation - degree) * each);
            if (at < w[1] + 14 || at > w[3] - 26) continue;
            boolean fifth = Math.floorMod(degree, 5) == 0;
            g.fill(x, at, x + (fifth ? 8 : 4), at + 1, tick);
            if (fifth || each >= 14) g.drawString(font, String.format(Locale.ROOT, "%+d", degree), x + 11, at - 4, figure, false);
        }
        g.fill(x - 3, cy, x - 1, cy + 1, fade(PALE, see));
        for (int degree = (int) Math.floor(bearing - (cx - w[0]) / each); degree <= bearing + (w[2] - cx) / each; degree++)
        {
            int at = cx + (int) Math.round((degree - bearing) * each);
            if (at < w[0] + 40 || at > w[2] - 12) continue;
            boolean fifth = Math.floorMod(degree, 5) == 0;
            g.fill(at, y - (fifth ? 8 : 4), at + 1, y, tick);
            // A figure to a degree only where a degree is wide enough for three of them and a gap.
            if (fifth || each >= 30)
            {
                String text = String.format(Locale.ROOT, "%03d", Math.floorMod(degree, 360));
                g.drawString(font, text, at - font.width(text) / 2, y - 18, figure, false);
            }
        }
        g.fill(cx, y + 1, cx + 1, y + 3, fade(PALE, see));
    }

    /**
     * The marks and the figures, over the display's readouts. True when this sight has the cannon (the R63 scope is
     * not drawn then).
     */
    public static boolean sight(Font font, GuiGraphics g, LocalPlayer player, EvaUnit01Entity eva, float partial, int width, int height)
    {
        if (!enabled() || eva.getWeapon() != EvaUnit01Entity.WEAPON_CANNON) return false;
        float see = lit();
        if (see <= .02F) return true;
        Minecraft mc = Minecraft.getInstance();
        int[] w = window(width, height);
        solve(mc, player, eva, partial, width, height);
        Solve s = NOW;
        int unit = Math.max(1, Math.round(height / 240F));
        int cx = width / 2, cy = height / 2;
        ClientboundCannonServiceR64 told = service(eva);
        float time = (player.tickCount + partial) / 20F;
        boolean blink = (int) (time * 4) % 2 == 0;

        // The display's own frame: a faint line inside the window and a bracket at each corner.
        int faint = fade(AMBER, see * .28F), bright = fade(AMBER, see * .8F), reach = 9 * unit;
        g.fill(w[0] + 2, w[1] + 2, w[2] - 2, w[1] + 3, faint); g.fill(w[0] + 2, w[3] - 3, w[2] - 2, w[3] - 2, faint);
        g.fill(w[0] + 2, w[1] + 3, w[0] + 3, w[3] - 3, faint); g.fill(w[2] - 3, w[1] + 3, w[2] - 2, w[3] - 3, faint);
        for (int sx = 0; sx <= 1; sx++)
            for (int sy = 0; sy <= 1; sy++)
            {
                int x = sx == 0 ? w[0] + 2 : w[2] - 3, y = sy == 0 ? w[1] + 2 : w[3] - 3;
                g.fill(sx == 0 ? x : x - reach, y, sx == 0 ? x + reach + 1 : x + 1, y + 1, bright);
                g.fill(x, sy == 0 ? y : y - reach, x + 1, sy == 0 ? y + reach + 1 : y + 1, bright);
            }
        scales(font, g, mc, w, cx, cy, height, see);

        // The fixed mark: the sight's own axis.
        int gap = 5 * unit, arm = 15 * unit;
        box(g, cx - arm, cy, cx - gap, cy + 1, fade(PALE, see * .8F), w); box(g, cx + gap + 1, cy, cx + arm + 1, cy + 1, fade(PALE, see * .8F), w);
        box(g, cx, cy - arm, cx + 1, cy - gap, fade(PALE, see * .8F), w); box(g, cx, cy + gap + 1, cx + 1, cy + arm + 1, fade(PALE, see * .8F), w);
        box(g, cx, cy, cx + 1, cy + 1, fade(PALE, see), w);
        if (!s.valid) return true;
        // The barrel's mark stays in the window: where its place is outside the picture it stands at the window's edge on that side.
        int size = 9 * unit;
        int bx = Mth.clamp(Math.round(s.boreX), w[0] + size + 3, w[2] - size - 4), by = Mth.clamp(Math.round(s.boreY), w[1] + size + 3, w[3] - size - 4);

        // The core's mark: where the core is. Shut: a dashed ring. Open: whole and bright. The bore's ray through it: green.
        if (s.coreInPlay)
        {
            float kx = s.coreX, ky = s.coreY, radius = Math.max(size + 3 * unit, s.coreR);
            int colour = !s.coreOpen ? fade(AMBER, see * .75F) : s.through ? fade(GREEN, see) : fade(blink ? 0xFFFFFFFF : RED, see);
            if (kx < w[0] + 4 || kx > w[2] - 4 || ky < w[1] + 4 || ky > w[3] - 4)
            {
                // Out of the picture: an arrowhead at the window's edge, pointing to it (beside the barrel's mark if that is there too).
                float ex = Mth.clamp(kx, w[0] + 6, w[2] - 7), ey = Mth.clamp(ky, w[1] + 6, w[3] - 7);
                if (Math.abs(ex - bx) + Math.abs(ey - by) < 3 * size) ey += ey - 4 * size > w[1] + 6 ? -4 * size : 4 * size;
                float tx = kx - cx, ty = ky - cy, far = Math.max(1, Mth.sqrt(tx * tx + ty * ty));
                arrow(g, ex, ey, tx / far, ty / far, 7 * unit, colour, w);
            }
            else
            {
                ring(g, kx, ky, radius, colour, s.coreOpen ? 0 : 10, time * .6F, w);
                if (s.coreOpen) ring(g, kx, ky, radius + 2 * unit, fade(colour, .5F), 0, 0, w);
                // Four ticks on the ring, as a target's mark has.
                for (int quarter = 0; quarter < 4; quarter++)
                {
                    float dx = Mth.cos(quarter * Mth.HALF_PI), dy = Mth.sin(quarter * Mth.HALF_PI);
                    line(g, Math.round(kx + dx * (radius + 2 * unit)), Math.round(ky + dy * (radius + 2 * unit)),
                            Math.round(kx + dx * (radius + 6 * unit)), Math.round(ky + dy * (radius + 6 * unit)), colour, w);
                }
                String name = I18n.get(s.coreOpen ? "hud.projectseele.sight.core_open" : "hud.projectseele.sight.core_shut");
                g.drawString(font, name, Mth.clamp(Math.round(kx) - font.width(name) / 2, w[0] + 3, w[2] - 3 - font.width(name)),
                        Mth.clamp(Math.round(ky - radius) - 12 - 6 * unit, w[1] + 14, w[3] - 12), colour, true);
            }
        }

        // The barrel's mark: a triangle on its point, where the bore's ray ends. A line back to the axis while it is off it.
        boolean settled = !s.limit && s.barrelOff <= CannonSightMathR64.SETTLED;
        int barrel = fade(settled ? s.on ? GREEN : PALE : s.limit && blink ? RED : AMBER, see);
        if (Math.abs(bx - cx) + Math.abs(by - cy) > 4 * unit) line(g, cx, cy, bx, by, fade(barrel, .35F), w);
        for (int i = 0; i < 3; i++)
        {
            float[] from = CORNERS[i], to = CORNERS[(i + 1) % 3];
            line(g, Math.round(bx + from[0] * size), Math.round(by + from[1] * size), Math.round(bx + to[0] * size), Math.round(by + to[1] * size), barrel, w);
        }
        box(g, bx - 1, by, bx + 2, by + 1, barrel, w); box(g, bx, by - 1, bx + 1, by + 2, barrel, w);
        if (s.limit)
        {
            String edge = I18n.get(s.fixed ? "hud.projectseele.sight.sector" : "hud.projectseele.sight.arms");
            g.drawString(font, edge, Mth.clamp(bx - font.width(edge) / 2, w[0] + 3, w[2] - 3 - font.width(edge)), Mth.clamp(by + size + 5, w[1] + 3, w[3] - 12), barrel, true);
        }

        // The energy's mark: three arrowheads that wind in on the barrel's mark as the charge rises, and stand on
        // its three corners when the charge is full.
        if (s.charge > 0)
        {
            float eased = smooth(s.charge), out = Mth.lerp(eased, 46 * unit, size + 2 * unit), wind = (1 - eased) * 1.5F;
            int energy = fade(s.charge >= 1 ? s.on ? GREEN : PALE : AMBER, see);
            float cos = Mth.cos(wind), sin = Mth.sin(wind);
            for (float[] corner : CORNERS)
            {
                float dx = corner[0] * cos - corner[1] * sin, dy = corner[0] * sin + corner[1] * cos;
                arrow(g, bx + dx * out, by + dy * out, -dx, -dy, 6 * unit, energy, w);
                if (s.charge < 1) line(g, Math.round(bx + dx * (out + 3 * unit)), Math.round(by + dy * (out + 3 * unit)),
                        Math.round(bx + dx * (out + 9 * unit)), Math.round(by + dy * (out + 9 * unit)), fade(energy, .5F), w);
            }
        }

        // All three in place: brackets close round the mark.
        if (s.on)
        {
            int lock = fade(blink ? GREEN : 0xFFFFFFFF, see), wide = 24 * unit, tall = 17 * unit, lip = 6 * unit;
            for (int side = -1; side <= 1; side += 2)
            {
                box(g, bx + side * wide - (side < 0 ? 0 : 1), by - tall, bx + side * wide + (side < 0 ? 2 : 1), by + tall + 1, lock, w);
                box(g, Math.min(bx + side * wide, bx + side * (wide - lip)), by - tall, Math.max(bx + side * wide, bx + side * (wide - lip)) + 1, by - tall + 2, lock, w);
                box(g, Math.min(bx + side * wide, bx + side * (wide - lip)), by + tall - 1, Math.max(bx + side * wide, bx + side * (wide - lip)) + 1, by + tall + 1, lock, w);
            }
        }

        // Under the axis: which of the three is in place, and the one line that says what the sight waits for.
        String[] names = {I18n.get("hud.projectseele.sight.barrel"), I18n.get("hud.projectseele.sight.energy"), I18n.get(s.coreInPlay ? "hud.projectseele.sight.core" : "hud.projectseele.sight.target")};
        boolean[] in = {settled, s.charge >= 1, s.coreInPlay ? s.coreOpen && s.through : s.reaches};
        int total = 0;
        for (String name : names) total += font.width(name) + 8;
        total += 10 * 2;
        int lx = cx - total / 2, ly = w[3] - 48;
        if (ly > cy + 20 * unit)
        {
            for (int i = 0; i < 3; i++)
            {
                int colour = fade(in[i] ? GREEN : i == 1 || blink ? AMBER : 0xFF7A5A30, see);
                g.fill(lx, ly + 1, lx + 5, ly + 6, colour);
                g.drawString(font, names[i], lx + 8, ly, fade(in[i] ? GREEN : MUTED, see), true);
                lx += font.width(names[i]) + 8 + 10;
            }
            boolean cooling = eva.getCannonCooldown() > 0 || told != null && told.shots() > 0 && !(told.reload() && told.coolant());
            String word = s.on ? I18n.get("hud.projectseele.sight.fire")
                    : cooling ? I18n.get("hud.projectseele.sight.service")
                    : told != null && !told.permitted() ? I18n.get("hud.projectseele.sight.held")
                    : s.charge <= 0 ? I18n.get("hud.projectseele.sight.standby")
                    : s.charge < 1 ? I18n.get("hud.projectseele.sight.charging", String.format(Locale.ROOT, "%.1f", (1 - s.charge) * SeeleConfig.CANNON_CHARGE_TICKS.get() / 20F))
                    : I18n.get("hud.projectseele.sight.waiting", names[!in[0] ? 0 : 2]);
            int colour = s.on ? blink ? GREEN : 0xFFFFFFFF : cooling || told != null && !told.permitted() ? MUTED : AMBER;
            g.drawString(font, word, cx - font.width(word) / 2, ly + 11, fade(colour, see), true);
        }

        // At Yashima the operation's own notice (what holds the gun, or that it is clear) stands on the bar at the top
        // of the screen, which is behind the sight's shell: its last clause is said here, along the window's top.
        if (told != null && !told.notice().isEmpty())
        {
            String rest = told.notice();
            for (int row = 0, y = w[1] + 6; row < 2 && !rest.isEmpty() && y < cy - 30 * unit; row++, y += 10)
            {
                String part = font.plainSubstrByWidth(rest, w[2] - w[0] - 40);
                g.drawString(font, part, cx - font.width(part) / 2, y, fade(told.permitted() ? MUTED : AMBER, see), true);
                rest = rest.substring(part.length());
            }
        }

        figures(font, g, eva, s, told, width, height, w, see);
        boolean beside = w[2] + 6 + COLUMN <= width - 2;
        bars(font, g, eva, told, beside ? w[2] + 6 : w[2] - COLUMN - 8, w[3] - 2, true, !beside, see);
        return true;
    }

    /** The width of a column of figures beside the window. */
    private static final int COLUMN = 88;

    /**
     * The shot's figures, in a column at each side of the window (on the housing; inside the window's edge where
     * the housing has no room): the gun's own at the left (range, elevation, bearing), at the right how far the
     * barrel is from the pilot's look and the charge, and at Yashima under those the power that reaches the gun
     * and the target's own charge. Every one is read from the game.
     */
    private static void figures(Font font, GuiGraphics g, EvaUnit01Entity eva, Solve s, ClientboundCannonServiceR64 told, int width, int height, int[] w, float see)
    {
        boolean roomLeft = w[0] - COLUMN - 6 >= 2, roomRight = w[2] + 6 + COLUMN <= width - 2;
        int lx = roomLeft ? w[0] - COLUMN - 6 : w[0] + 44, rx = roomRight ? w[2] + 6 : w[2] - COLUMN - 8, top = w[1] + 4;
        int value = fade(PALE, see), plate = fade(0xFF0B0D0F, see);
        if (roomLeft) g.fill(lx - 3, top - 3, lx + COLUMN + 2, top + 3 * 22 - 1, plate);
        int y = top;
        y = cell(font, g, "range", s.range < 0 ? "----" : String.format(Locale.ROOT, "%.0f m", s.range), value, lx, y, see, !roomLeft);
        y = cell(font, g, "elevation", String.format(Locale.ROOT, "%+.1f°", s.elevation), value, lx, y, see, !roomLeft);
        cell(font, g, "bearing", String.format(Locale.ROOT, "%05.1f°", s.bearing), value, lx, y, see, !roomLeft);

        if (roomRight) g.fill(rx - 3, top - 3, rx + COLUMN + 2, top + (told == null ? 2 * 22 : 3 * 22 + 3 * 11 + 2) - 1, plate);
        y = top;
        y = cell(font, g, "off", String.format(Locale.ROOT, "%.1f°", s.wishOff), s.wishOff > CannonSightMathR64.SETTLED ? fade(AMBER, see) : value, rx, y, see, !roomRight);
        y = cell(font, g, "charge", String.format(Locale.ROOT, "%d%%", Math.round(s.charge * 100)), s.charge >= 1 ? fade(GREEN, see) : value, rx, y, see, !roomRight);
        if (told == null) return;
        // Yashima: the power that reaches the gun, lit as each part of it is there, and the target's own charge.
        String grid = I18n.get("hud.projectseele.sight.grid"), code = I18n.get("hud.projectseele.sight.code_grid");
        g.drawString(font, grid, rx + 4, y, fade(MUTED, see), !roomRight);
        if (!code.isEmpty()) g.drawString(font, code, rx + 4 + font.width(grid) + 4, y, fade(AMBER, see * .55F), !roomRight);
        for (int i = 0; i < 3; i++) g.fill(rx + COLUMN - 24 + i * 8, y + 1, rx + COLUMN - 18 + i * 8, y + 7, fade(i < told.grid() ? GREEN : 0xFF4A3A2A, see));
        g.fill(rx, y, rx + 1, y + 3 * 11 - 2, fade(AMBER, see * .7F));
        y += 11;
        lamp(font, g, "pylon", told.pylons(), rx, y, see, !roomRight); y += 11;
        lamp(font, g, "cable", told.umbilical(), rx, y, see, !roomRight); y += 13;
        int age = serviceAge();
        if (told.beam() - age > 0) cell(font, g, "foe_open", String.format(Locale.ROOT, "%.1f s", (told.beam() - age) / 20F), fade(GREEN, see), rx, y, see, !roomRight);
        else if (told.targetCharge() - age > 0)
            cell(font, g, "foe_charge", String.format(Locale.ROOT, "%.1f s", (told.targetCharge() - age) / 20F), fade(told.targetCharge() - age <= 20 ? GREEN : AMBER, see), rx, y, see, !roomRight);
        else cell(font, g, "foe_idle", "--", fade(MUTED, see), rx, y, see, !roomRight);
    }

    /**
     * One figure: a rule at its left, its name (and, where the language is not English, its code in English, as
     * the plug's other windows write theirs) over its value. Returns where the next one goes.
     */
    private static int cell(Font font, GuiGraphics g, String key, String value, int colour, int x, int y, float see, boolean shadow)
    {
        String name = I18n.get("hud.projectseele.sight." + key), code = I18n.get("hud.projectseele.sight.code_" + key);
        g.fill(x, y, x + 1, y + 19, fade(AMBER, see * .7F));
        g.drawString(font, name, x + 4, y, fade(MUTED, see), shadow);
        if (!code.isEmpty()) g.drawString(font, code, x + COLUMN - font.width(code), y, fade(AMBER, see * .55F), shadow);
        g.drawString(font, value, x + COLUMN - font.width(value), y + 10, colour, shadow);
        return y + 22;
    }

    private static void lamp(Font font, GuiGraphics g, String key, boolean lit, int x, int y, float see, boolean shadow)
    {
        String name = I18n.get("hud.projectseele.sight." + key), code = I18n.get("hud.projectseele.sight.code_" + key);
        g.drawString(font, name, x + 4, y, fade(MUTED, see), shadow);
        if (!code.isEmpty()) g.drawString(font, code, x + 4 + font.width(name) + 4, y, fade(AMBER, see * .55F), shadow);
        g.fill(x + COLUMN - 8, y + 1, x + COLUMN - 2, y + 7, fade(lit ? GREEN : 0xFF4A3A2A, see));
    }

    /**
     * The gun's service after a shot, as bars: at Yashima the fuse (the reload, 100 ticks of the server's service)
     * and the barrel's cooling (120), and everywhere the recharge (the cannon's cooldown and then the next charge).
     */
    private static void bars(Font font, GuiGraphics g, EvaUnit01Entity eva, ClientboundCannonServiceR64 told, int x, int y, boolean upwards, boolean inside, float see)
    {
        int cooldown = eva.getCannonCooldown(), most = SeeleConfig.CANNON_COOLDOWN_TICKS.get(), charge = SeeleConfig.CANNON_CHARGE_TICKS.get();
        boolean served = told != null && told.shots() > 0;
        float fuse = 1, barrel = 1;
        if (served)
        {
            boolean powered = told.grid() == 3 && told.pylons() && told.umbilical();
            int ticks = Math.min(120, told.service() + (powered ? serviceAge() : 0));
            fuse = told.reload() ? 1 : Mth.clamp(ticks / 100F, 0, 1);
            barrel = told.coolant() ? 1 : Mth.clamp(ticks / 120F, 0, 1);
        }
        float recharge = Mth.clamp((most - cooldown + eva.getCannonCharge()) / (float) (most + charge), 0, 1);
        boolean busy = cooldown > 0 || fuse < 1 || barrel < 1;
        if (!busy && shotAge > STAY) return;
        int wide = COLUMN, tall = served ? 30 : 10;
        if (upwards) y -= tall;
        if (!inside) g.fill(x - 3, y - 3, x + wide + 1, y + tall + 1, fade(0xFF0B0D0F, see));
        if (served)
        {
            bar(font, g, I18n.get("hud.projectseele.sight.fuse"), fuse, x, y, wide, see, inside); y += 10;
            bar(font, g, I18n.get("hud.projectseele.sight.cooling"), barrel, x, y, wide, see, inside); y += 10;
        }
        bar(font, g, I18n.get("hud.projectseele.sight.recharge"), recharge, x, y, wide, see, inside);
    }

    /**
     * The same bars with the sight up, under the display's weapon window: the gun's service goes on when the pilot
     * has let the trigger go.
     */
    public static void serviceBelow(Font font, GuiGraphics g, EvaUnit01Entity eva, int x, int y)
    {
        if (!enabled() || eva.getWeapon() != EvaUnit01Entity.WEAPON_CANNON || down > COVERING) return;
        bars(font, g, eva, service(eva), x, y, false, true, 1 - down / COVERING);
    }

    private static void bar(Font font, GuiGraphics g, String name, float value, int x, int y, int wide, float see, boolean shadow)
    {
        g.drawString(font, name, x, y, fade(value >= 1 ? GREEN : MUTED, see), shadow);
        int from = x + Math.min(40, font.width(name) + 4), to = x + wide - 2;
        g.fill(from, y + 3, to, y + 6, fade(0xFF2A2F33, see));
        g.fill(from, y + 3, from + Math.round((to - from) * Mth.clamp(value, 0, 1)), y + 6, fade(value >= 1 ? GREEN : AMBER, see));
    }

    private static int fade(int colour, float amount)
    {
        // Never under 4: the game's font takes a colour with no alpha to speak of for an opaque one.
        return Mth.clamp(Math.round((colour >>> 24) * Mth.clamp(amount, 0, 1)), 4, 255) << 24 | colour & 0xFFFFFF;
    }

    private static void play(Minecraft mc, SoundEvent sound, float pitch, float volume)
    {
        mc.getSoundManager().play(SimpleSoundInstance.forUI(sound, pitch, volume));
    }

    /** The sight's own sounds, in the pilot's ears only: its coming down, the marks closing, their meeting, the gun's service. */
    @SubscribeEvent
    public static void sounds(TickEvent.ClientTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (event.phase != TickEvent.Phase.END || mc.player == null || mc.level == null || mc.isPaused()) return;
        tickClock++;
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(mc.player);
        boolean mine = enabled() && eva != null && eva.getWeapon() == EvaUnit01Entity.WEAPON_CANNON && mc.options.getCameraType().isFirstPerson();
        if (!mine) { wasOn = false; wasDown = false; ventAt = fuseAt = -1; wasCooling = false; return; }
        if (wanted != wasDown) { wasDown = wanted; play(mc, ModSounds.CANNON_VISOR.get(), wanted ? 1F : .84F, .32F); }
        if (ventAt >= 0 && tickClock >= ventAt) { ventAt = -1; play(mc, ModSounds.CANNON_VENT.get(), 1, .42F); }
        if (fuseAt >= 0 && tickClock >= fuseAt) { fuseAt = -1; play(mc, ModSounds.CANNON_FUSE.get(), .86F, .40F); }
        // The service done: the new fuse goes home (at Yashima when the server's reload is in; elsewhere when the cooldown has run out).
        ClientboundCannonServiceR64 told = service(eva);
        boolean cooling = told != null && told.shots() > 0 ? !told.reload() : eva.getCannonCooldown() > 0;
        if (wasCooling && !cooling) play(mc, ModSounds.CANNON_FUSE.get(), 1.12F, .40F);
        wasCooling = cooling;
        Solve s = NOW;
        boolean live = s.valid && down > .9F && mc.level.getGameTime() - solvedAt <= 2;
        boolean on = live && s.on;
        if (on && !wasOn) play(mc, ModSounds.CANNON_SIGHT_LOCK.get(), 1, .34F);
        wasOn = on;
        if (!live || s.charge <= 0) { sinceTick = 0; return; }
        // The marks closing: the nearer they are to meeting, the quicker and higher the tick; met, a fast even one.
        int every = on ? 3 : Math.round(Mth.lerp(s.closing, 13, 4));
        if (++sinceTick >= every)
        {
            sinceTick = 0;
            play(mc, ModSounds.CANNON_SIGHT_TICK.get(), on ? 1.5F : .9F + .45F * s.closing, on ? .20F : .16F);
        }
    }
}

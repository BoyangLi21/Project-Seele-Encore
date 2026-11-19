package com.projectseele.client.cockpit;

import com.mojang.blaze3d.systems.RenderSystem;
import com.mojang.blaze3d.vertex.BufferBuilder;
import com.mojang.blaze3d.vertex.BufferUploader;
import com.mojang.blaze3d.vertex.DefaultVertexFormat;
import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.blaze3d.vertex.Tesselator;
import com.mojang.blaze3d.vertex.VertexFormat;
import com.mojang.blaze3d.vertex.VertexSorting;
import com.projectseele.ProjectSeele;
import com.projectseele.client.AircraftRenderClockR21;
import com.projectseele.client.ClientForgeEvents;
import com.projectseele.client.FirstBattleClient;
import com.projectseele.client.Keybinds;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.world.EvaPilotResolver;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.player.LocalPlayer;
import net.minecraft.client.renderer.GameRenderer;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.sounds.SoundEvents;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;
import org.joml.Matrix4f;

/**
 * R64: what the pilot sees of the plug around them, in first person.
 * <p>
 * The original shows the pilot in a seat with a control yoke in each hand, the plug's wall around them carrying
 * the picture of the Unit's eyes, and the plug filled with LCL. Up to R63 first person was the Unit's eye and a
 * few tiles of numbers. This draws the seat's front, the two yokes and the pilot's hands on them (they move with
 * what the pilot does), and the LCL, over the picture and under the display's readouts.
 * <p>
 * It is drawn with the interface, after the world and whatever shader pack has finished with it, with a
 * projection of its own: it never touches the world's depth, and F1 takes it away with the rest of the interface.
 * Rollback: -Dprojectseele.cockpitR64=false; the parts have their own switches in the client config (cockpit.*).
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PilotCockpitR64
{
    /** The whole of R64's first-person work: the steadier view, the plug's inside, the LCL, the pilot's seated pose. */
    public static final boolean ON = !"false".equals(System.getProperty("projectseele.cockpitR64"));
    /** The cockpit's own field of view (degrees, vertical) and near plane (blocks): the game's own may be anything. */
    public static final float FOV = 70, NEAR = .05F;
    /**
     * The steps of the cabin sequence, 0..1, in the original's order: the capsule is carried and driven in (its
     * own part, up to STEP_INSERTED: EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT), locks, fills with LCL from
     * STEP_LCL, the nerve connection runs from STEP_NERVE, the synchronisation from STEP_SYNC, when the wall
     * comes on. From STEP_INSERTED on it is the Unit's activation that counts.
     */
    public static final float STEP_INSERTED = EntryPlugCarrierEntity.CABIN_TRANSFER_PERCENT / 100F, STEP_LCL = .14F, STEP_NERVE = .45F, STEP_SYNC = .72F;

    /** How far the seat is drawn down the plug as it locks (blocks). */
    public static final float SEAT_SLIDE = .8F;

    /**
     * The original draws the pilot's seat down the plug to its working depth once the plug is seated. Here the
     * pilot's eye goes that way, towards the insertion tip, during the lock step, and stays there while the cabin
     * is seen; the glide to the Unit's eyes starts from there.
     */
    public static net.minecraft.world.phys.Vec3 seatSlide(EntryPlugCarrierEntity plug, EvaUnit01Entity eva, float partial)
    {
        if (!ON || eva == null || !plug.isLockedToEva() || !eva.isActivationCinematicActive()) return net.minecraft.world.phys.Vec3.ZERO;
        float t = Mth.clamp((eva.getActivationProgress(partial) - STEP_INSERTED) / (STEP_LCL - STEP_INSERTED), 0, 1);
        return plug.getInterpolatedCanonicalTransform(partial).transformVector(new net.minecraft.world.phys.Vec3(0, 0, -SEAT_SLIDE * t * t * (3 - 2 * t)));
    }

    /**
     * The capsule is not drawn once it is inside its Unit. Its own pilot still sits in it: until the wall comes on
     * they see the cabin around them, where the LCL rises and the nerve connection runs.
     */
    public static boolean cabinStillSeen(EntryPlugCarrierEntity plug)
    {
        Minecraft mc = Minecraft.getInstance();
        if (!ON || mc.player == null || mc.player.getVehicle() != plug || !plug.isLockedToEva()
                || !mc.options.getCameraType().isFirstPerson() || mc.getCameraEntity() != mc.player) return false;
        EvaUnit01Entity eva = plug.getLinkedEva();
        return eva != null && eva.isActivationCinematicActive() && eva.getActivationProgress(mc.getFrameTime()) < STEP_SYNC;
    }

    private static final CockpitMeshR64 MESH = new CockpitMeshR64();
    private static final CockpitMeshR64.State STATE = new CockpitMeshR64.State();
    private static long frame;
    private static float seconds, shown, light = 1, lastYaw, lastPitch, lagX, lagY;
    private static float leftPush, rightPush, tilt, leftTrigger, rightTrigger, swayX, swayY, roll;
    private static boolean seated, hadLook;
    private static float[] far = new float[256];

    private PilotCockpitR64() {}

    public static boolean interior()
    {
        return ON && SeeleConfig.COCKPIT_INTERIOR.get();
    }

    /**
     * The cabin sequence the player is in, 0..1 (lock, LCL, nerve connection, synchronisation), or -1 with none
     * running. The capsule owns it up to the socket, the Unit's activation from there: one number for the
     * insertion overlay and for the LCL.
     */
    public static float sequence(LocalPlayer player, float partial)
    {
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(player);
        EntryPlugCarrierEntity plug = player.getVehicle() instanceof EntryPlugCarrierEntity carrier ? carrier : null;
        float activation = eva == null ? 0 : eva.getActivationProgress(partial);
        // Never the terminal 100% frame: entity data can arrive one packet after the launch phase.
        boolean activating = eva != null && eva.isActivationCinematicActive() && activation < .995F;
        // The synced insertion stage is the authority: the locked stage can arrive a packet before the host.
        boolean external = plug != null && eva == null && plug.getInsertionStage() != EntryPlugCarrierEntity.STAGE_LOCKED;
        boolean recovered = plug != null && plug.getCabinStage() == EntryPlugCarrierEntity.CABIN_RECOVERED_IDLE;
        boolean capsule = plug != null && !recovered && (external || activating);
        if (!activating && !capsule) return -1;
        if (plug != null && plug.getCabinStage() == EntryPlugCarrierEntity.CABIN_SEALED_DARK) return 0;
        return capsule && external ? plug.getCabinProgress(partial) / 100F : activating ? activation : 0;
    }

    /**
     * The LCL follows the pilot whatever the view: every frame, before anything is drawn, also in third person and
     * with the interface hidden, so that a seat left behind an outside camera does not run out a minute later.
     */
    @SubscribeEvent
    public static void track(TickEvent.RenderTickEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        LocalPlayer player = mc.player;
        if (!ON || event.phase != TickEvent.Phase.START || player == null || mc.isPaused()) return;
        long now = AircraftRenderClockR21.frameNanos();
        float dt = lclFrame == 0 ? 0 : Mth.clamp((now - lclFrame) / 1e9F, 0, .1F);
        if (now == lclFrame) return;
        lclFrame = now;
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(player);
        EntryPlugCarrierEntity plug = player.getVehicle() instanceof EntryPlugCarrierEntity carrier ? carrier : null;
        boolean driving = eva != null && (plug == null || plug.isLockedToEva());
        float before = PilotLclR64.fill(), level = PilotLclR64.level();
        PilotLclR64.frame(plug, driving, sequence(player, event.renderTickTime), dt);
        if (!PilotLclR64.on()) return;
        // The game's own water sounds, quietly: the first of the liquid, the surface closing over the eye, its going.
        float after = PilotLclR64.fill();
        var sounds = mc.getSoundManager();
        if (before <= 0 && after > 0 && after < .5F) sounds.play(SimpleSoundInstance.forUI(SoundEvents.BUBBLE_COLUMN_UPWARDS_INSIDE, .8F, .30F));
        if (level < 0 && PilotLclR64.level() >= 0 && after > before) sounds.play(SimpleSoundInstance.forUI(SoundEvents.AMBIENT_UNDERWATER_ENTER, .9F, .35F));
        if (before >= 1 && after < 1) sounds.play(SimpleSoundInstance.forUI(SoundEvents.AMBIENT_UNDERWATER_EXIT, .9F, .35F));
    }
    private static long lclFrame;

    public static final IGuiOverlay OVERLAY = (gui, graphics, partial, width, height) ->
    {
        Minecraft mc = Minecraft.getInstance();
        LocalPlayer player = mc.player;
        if (!ON || player == null || !mc.options.getCameraType().isFirstPerson() || mc.getCameraEntity() != player
                || FirstBattleClient.active())
        {
            seated = false; hadLook = false;
            return;
        }
        advance(mc, player, partial);
        float strength = PilotLclR64.strength(), under = PilotLclR64.under();
        // In the liquid the whole picture is its colour; the plug's own parts, close to the eye, take less of it.
        if (strength > 0 && under > 0) graphics.fill(0, 0, width, height, colour(CockpitMeshR64.LCL, under * strength * .66F));
        boolean parts = seated && interior() && shown > .01F;
        var airframe = EvaPilotResolver.controlTarget(player);
        boolean emergency = PilotBerserkViewR64.active(airframe);
        int trim = emergency ? (airframe.isBerserk() ? 0xA32622 : 0x835B32) : 0xE8C8A0;
        if (parts && light > .5F) panorama(graphics, width, height, (light - .5F) * 2 * shown, trim);
        // The cannon's sight is part of the plug's inside: its housing swings down in the same picture as the yokes,
        // round the window the sight's own display is laid in. Its glass is drawn first, under it.
        int[] sight = PlugCannonSightR64.window(width, height);
        float tangent = (float) Math.tan(FOV * Mth.DEG_TO_RAD / 2);
        STATE.visor = seated ? PlugCannonSightR64.down() : 0;
        STATE.visorWide = tangent * (sight[2] - sight[0]) / height;
        STATE.visorHigh = tangent * (sight[3] - sight[1]) / height;
        STATE.visorJolt = PlugCannonSightR64.jolt();
        STATE.visorCharge = PlugCannonSightR64.charge();
        STATE.visorLock = PlugCannonSightR64.locked();
        if (seated) PlugCannonSightR64.hood(graphics, width, height);
        if (parts || STATE.visor > 0 || strength > 0 && PilotLclR64.level() > PilotLclR64.FLOOR)
        {
            STATE.parts = parts;
            MESH.build(STATE);
            draw(graphics, mc);
        }
        if (strength > 0 && under > 0) graphics.fill(0, 0, width, height, colour(CockpitMeshR64.LCL, under * strength * .16F));
        if (emergency && seated) graphics.fill(0, 0, width, height, airframe.isBerserk() ? 0x52220408 : 0x4422180B);
    };

    /**
     * The picture is on the plug's round wall: two faint rings about the middle of the view, the outer one seen
     * only in the corners, with the wall's joints as short spokes between them. Nothing crosses the picture itself.
     */
    private static void panorama(GuiGraphics g, int width, int height, float amount, int trim)
    {
        int alpha = Math.round(24 * Mth.clamp(amount, 0, 1));
        if (alpha <= 2) return;
        int line = alpha << 24 | trim, faint = alpha / 2 << 24 | trim;
        float cx = width * .5F, cy = height * .5F, inner = width * .468F, outer = width * .532F;
        for (int y = 0; y < height; y++)
        {
            float dy = y + .5F - cy;
            for (int ring = 0; ring < 2; ring++)
            {
                float radius = ring == 0 ? inner : outer;
                if (Math.abs(dy) >= radius) continue;
                int reach = Math.round((float) Math.sqrt(radius * radius - dy * dy));
                int left = Math.round(cx) - reach, right = Math.round(cx) + reach;
                if (left >= 0) g.fill(left, y, left + 1, y + 1, ring == 0 ? line : faint);
                if (right < width) g.fill(right - 1, y, right, y + 1, ring == 0 ? line : faint);
            }
        }
        // The joints between the wall's panels, every fifteen degrees, between the two rings.
        for (int k = -11; k <= 11; k++)
        {
            double angle = Math.toRadians(k * 15);
            for (int side = -1; side <= 1; side += 2)
                for (int step = 0; step < 14; step++)
                {
                    float radius = inner + 3 + (outer - inner - 6) * step / 13F;
                    int x = Math.round(cx + side * (float) Math.cos(angle) * radius), y = Math.round(cy + (float) Math.sin(angle) * radius);
                    if (x >= 0 && x < width && y >= 0 && y < height) g.fill(x, y, x + 1, y + 1, faint);
                }
        }
    }

    private static int colour(float[] rgb, float alpha)
    {
        return Mth.clamp(Math.round(alpha * 255), 0, 255) << 24 | Math.round(rgb[0] * 255) << 16 | Math.round(rgb[1] * 255) << 8 | Math.round(rgb[2] * 255);
    }

    /** Once a frame: what the pilot is doing, eased, into what the cockpit shows. */
    private static void advance(Minecraft mc, LocalPlayer player, float partial)
    {
        long now = AircraftRenderClockR21.frameNanos();
        float dt = frame == 0 ? 0 : Mth.clamp((now - frame) / 1e9F, 0, .1F);
        if (now == frame) return;
        frame = now;
        seconds += dt;
        EvaUnit01Entity eva = EvaPilotResolver.controlTarget(player);
        EntryPlugCarrierEntity plug = player.getVehicle() instanceof EntryPlugCarrierEntity carrier ? carrier : null;
        boolean driving = eva != null && (plug == null || plug.isLockedToEva());
        // A capsule waiting open on its bridge is boarded and left on foot: the seat is the pilot's once it is sealed.
        seated = driving || plug != null && plug.getCabinStage() != EntryPlugCarrierEntity.CABIN_OPEN;
        float progress = sequence(player, partial);

        // Behind a sight the pilot's hands are out of the picture: the cockpit sinks away while one is up.
        boolean sighted = driving && (ClientForgeEvents.isRifleSightActive(eva) || ClientForgeEvents.isCannonScopeActive(eva));
        // Under the cannon's sight the yokes stay at the picture's lower edge, in front of its shell: the trigger is on them.
        float under = driving ? PlugCannonSightR64.down() : 0;
        shown += ((under > 0 ? .8F : sighted ? 0 : 1) - shown) * ease(dt, .12F);
        // The wall carries the picture once the Unit is synchronised; before that the plug has only its own lamps.
        float wantedLight = driving && (progress < 0 || progress > STEP_SYNC) ? 1 : progress > STEP_NERVE ? .55F : .30F;
        light += (wantedLight - light) * ease(dt, .35F);

        float forward = 0, strafe = 0;
        boolean strike = false, heavy = false, jump = false, sprint = false;
        if (driving && mc.screen == null)
        {
            forward = player.input.forwardImpulse; strafe = player.input.leftImpulse;
            strike = mc.options.keyAttack.isDown(); heavy = mc.options.keyUse.isDown();
            jump = mc.options.keyJump.isDown(); sprint = mc.options.keySprint.isDown() || Keybinds.EVA_DASH.isDown();
        }
        float yaw = player.getViewYRot(partial), pitch = player.getViewXRot(partial);
        float turn = 0, nod = 0;
        if (hadLook && dt > 0) { turn = Mth.wrapDegrees(yaw - lastYaw) / dt; nod = (pitch - lastPitch) / dt; }
        lastYaw = yaw; lastPitch = pitch; hadLook = true;
        // Both yokes go forward to walk and further to run, come back to step back or to gather for a jump, lean
        // to step aside; turning pushes the outer one ahead of the inner. A blow thrusts the right, the heavy the left.
        float go = forward * (sprint && forward > 0 ? 1F : .62F) - (jump ? .7F : 0);
        float steer = Mth.clamp(turn / 240F, -1, 1) * .35F;
        float fast = ease(dt, .07F), slow = ease(dt, .11F);
        leftPush += (Mth.clamp(go + steer + (heavy ? .75F : 0), -1, 1) - leftPush) * (heavy ? fast : slow);
        rightPush += (Mth.clamp(go - steer + (strike ? .75F : 0), -1, 1) - rightPush) * (strike ? fast : slow);
        tilt += (Mth.clamp(-strafe, -1, 1) - tilt) * slow;
        leftTrigger += ((heavy ? 1 : 0) - leftTrigger) * fast;
        rightTrigger += ((strike ? 1 : 0) - rightTrigger) * fast;

        // The seat is in the body: what the steadier view left out of the head's movement is felt in the seat,
        // and the pilot's head trails a quick look round by a little.
        var removed = PilotViewSteadyR64.removed();
        float wantedX = driving ? Mth.clamp((float) removed.x * .018F, -.03F, .03F) : 0;
        float wantedY = driving ? Mth.clamp((float) removed.y * .020F, -.04F, .04F) : 0;
        swayX += (wantedX - swayX) * ease(dt, .05F);
        swayY += (wantedY - swayY) * ease(dt, .05F);
        lagX += (Mth.clamp(turn * .00022F, -.035F, .035F) - lagX) * ease(dt, .09F);
        lagY += (Mth.clamp(-nod * .00022F, -.03F, .03F) - lagY) * ease(dt, .09F);
        roll += (Mth.clamp(-turn * .00030F + (float) removed.x * .010F, -.05F, .05F) - roll) * ease(dt, .10F);

        STATE.unit = eva == null ? plug == null ? 1 : plug.isIndependentUNPlug() ? 3 : Mth.clamp(plug.getAssignedVariant(), 0, 2)
                : eva.isExperimentalUnit() ? 3 : Mth.clamp(eva.getUnitVariant(), 0, 2);
        STATE.time = seconds;
        STATE.leftPush = leftPush; STATE.rightPush = rightPush; STATE.leftTilt = STATE.rightTilt = tilt;
        STATE.leftTrigger = leftTrigger; STATE.rightTrigger = rightTrigger;
        // Looking down brings the seat up into the view by a third of the angle; looking up leaves the sky clear.
        STATE.pitch = Mth.clamp(.10F + pitch * Mth.DEG_TO_RAD * .34F, -.22F, .50F);
        STATE.swayX = swayX + lagX; STATE.swayY = swayY + lagY; STATE.roll = roll;
        STATE.drop = (1 - shown) * .55F;
        STATE.lclLevel = PilotLclR64.level(); STATE.lclAlpha = PilotLclR64.strength(); STATE.bubbles = PilotLclR64.bubbles();
        STATE.light = light;
    }

    private static float ease(float dt, float time)
    {
        return 1 - (float) Math.exp(-dt / time);
    }

    private static void draw(GuiGraphics graphics, Minecraft mc)
    {
        graphics.flush();
        var window = mc.getWindow();
        Matrix4f projection = new Matrix4f().setPerspective(FOV * Mth.DEG_TO_RAD,
                (float) window.getWidth() / Math.max(1, window.getHeight()), NEAR, 64F);
        Matrix4f oldProjection = RenderSystem.getProjectionMatrix();
        VertexSorting oldSorting = RenderSystem.getVertexSorting();
        RenderSystem.setProjectionMatrix(projection, VertexSorting.DISTANCE_TO_ORIGIN);
        PoseStack view = RenderSystem.getModelViewStack();
        view.pushPose();
        view.setIdentity();
        RenderSystem.applyModelViewMatrix();
        // The interface's depth, not the world's: the world and its shaders are finished before the interface starts.
        RenderSystem.clear(256, Minecraft.ON_OSX);
        RenderSystem.enableDepthTest();
        RenderSystem.depthFunc(515);
        RenderSystem.depthMask(true);
        RenderSystem.disableCull();
        RenderSystem.disableBlend();
        RenderSystem.setShaderColor(1, 1, 1, 1);
        RenderSystem.setShader(GameRenderer::getPositionColorShader);
        BufferBuilder buffer = Tesselator.getInstance().getBuilder();
        if (MESH.solidCount > 0)
        {
            buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
            put(buffer, MESH.solid, 0, MESH.solidCount);
            BufferUploader.drawWithShader(buffer.end());
        }
        if (MESH.clearCount > 0)
        {
            // See-through quads from the farthest to the nearest, over the solid ones and never into the depth.
            int quads = MESH.clearCount / 28;
            if (far.length < quads) far = new float[quads * 2];
            Integer[] sorted = new Integer[quads];
            for (int q = 0; q < quads; q++)
            {
                float x = 0, y = 0, z = 0;
                for (int i = 0; i < 4; i++) { int at = q * 28 + i * 7; x += MESH.clear[at]; y += MESH.clear[at + 1]; z += MESH.clear[at + 2]; }
                far[q] = x * x + y * y + z * z; sorted[q] = q;
            }
            java.util.Arrays.sort(sorted, (a, b) -> Float.compare(far[b], far[a]));
            RenderSystem.enableBlend();
            RenderSystem.defaultBlendFunc();
            RenderSystem.depthMask(false);
            buffer.begin(VertexFormat.Mode.QUADS, DefaultVertexFormat.POSITION_COLOR);
            for (int q : sorted) put(buffer, MESH.clear, q * 28, q * 28 + 28);
            BufferUploader.drawWithShader(buffer.end());
            RenderSystem.depthMask(true);
        }
        RenderSystem.enableBlend();
        RenderSystem.defaultBlendFunc();
        RenderSystem.enableCull();
        // The readouts that follow are flat: they must not be hidden behind the yokes' depth.
        RenderSystem.clear(256, Minecraft.ON_OSX);
        view.popPose();
        RenderSystem.applyModelViewMatrix();
        RenderSystem.setProjectionMatrix(oldProjection, oldSorting);
    }

    private static void put(BufferBuilder buffer, float[] v, int from, int to)
    {
        for (int at = from; at < to; at += 7)
            buffer.vertex(v[at], v[at + 1], v[at + 2]).color(v[at + 3], v[at + 4], v[at + 5], v[at + 6]).endVertex();
    }
}

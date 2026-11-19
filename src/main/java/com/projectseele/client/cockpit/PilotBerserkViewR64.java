package com.projectseele.client.cockpit;

import com.projectseele.client.FirstBattleClient;
import com.projectseele.client.Keybinds;
import com.projectseele.entity.EvaUnit01Entity;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.resources.language.I18n;

/** Emergency instruments fitted to the entry plug. Time comes from the server's phase transition. */
public final class PilotBerserkViewR64
{
    private static int seat = -1;
    private static int heldKeys;
    private static long deniedUntil;
    private PilotBerserkViewR64() {}

    public static boolean active(EvaUnit01Entity eva)
    {
        return eva != null && !FirstBattleClient.active() && (eva.isBerserk() || eva.getBerserkRecoveryTicks() > 0);
    }

    public static void inputs(EvaUnit01Entity eva)
    {
        var mc = Minecraft.getInstance();
        if (!active(eva) || !mc.options.getCameraType().isFirstPerson() || mc.screen != null) {
            seat = -1;
            heldKeys = 0;
            deniedUntil = 0;
            return;
        }
        var o = mc.options;
        int keys = (o.keyUp.isDown() ? 1 : 0) | (o.keyDown.isDown() ? 2 : 0) | (o.keyLeft.isDown() ? 4 : 0)
                | (o.keyRight.isDown() ? 8 : 0) | (o.keyAttack.isDown() ? 16 : 0)
                | (Keybinds.CYCLE_WEAPON.isDown() ? 32 : 0) | (o.keyJump.isDown() ? 64 : 0);
        if (seat != eva.getId()) { heldKeys = 0; deniedUntil = 0; }
        if ((keys & ~heldKeys) != 0) deniedUntil = eva.level().getGameTime() + 13;
        heldKeys = keys;
        seat = eva.getId();
    }

    public static void instruments(GuiGraphics g, Font font, EvaUnit01Entity eva, float partial, int width, int height)
    {
        float age = eva.berserkPhaseAge(partial);
        boolean running = eva.isBerserk();
        if (!running && age < 20 || running && age < 4) {
            g.fill(0, 0, width, height, running ? 0xF21D0506 : 0xFA030203);
            return;
        }
        int cx = width / 2, top = Math.max(6, height / 22);
        int frame = (int) (age / 2);
        int jitter = running && (age < 60 || frame % 49 < 2) ? frame % 7 - 3 : 0;
        int edge = running ? 0xFFFF705E : 0xFFC79152;
        int panelWidth = Math.min(width - 16, 150), left = cx - panelWidth / 2 + jitter;
        g.fill(left, top, left + panelWidth, top + 32, 0xCA220C0B);
        g.fill(left, top, left + panelWidth, top + 1, edge);
        g.drawCenteredString(font, I18n.get(running ? "hud.projectseele.plug.internal" : "hud.projectseele.berserk.stopped"), cx + jitter, top + 4, edge);
        g.drawCenteredString(font, running ? "0:00:00" : eva.synchronizationText(partial).getString(), cx + jitter, top + 17, edge);
        if (running) {
            int side = Math.max(4, width / 45), y = height * 2 / 5;
            String ratio = eva.synchronizationText(partial).getString();
            g.fill(side + jitter, y, side + Math.min(width / 2 - 8, font.width(ratio) + 12) + jitter, y + 17, 0xC41C090A);
            g.drawString(font, ratio, side + 4 + jitter, y + 4, eva.getSynchronizationRatio(partial) > 100 ? 0xFFFF4B40 : edge, false);
            if ((age < 60 && frame % 3 != 0) || frame % 53 == 0) {
                int n = age < 60 ? 11 : 3;
                for (int i = 0; i < n; i++) {
                    int x = left + Math.floorMod(frame * 17 + i * 37, panelWidth);
                    int sy = top + Math.floorMod(frame * 11 + i * 9, 31);
                    g.fill(x, sy, Math.min(left + panelWidth, x + 3 + i), sy + 1, 0x8CD67C71);
                }
            }
        }
        boolean denied = seat == eva.getId() && eva.level().getGameTime() < deniedUntil;
        if (denied || running && age < 60 && (int) age / 6 % 2 == 0)
            g.drawCenteredString(font, I18n.get(denied ? (running ? "hud.projectseele.berserk.denied" : "hud.projectseele.berserk.forced")
                    : "hud.projectseele.berserk.interrupted"), cx, top + 37, edge);
    }
}

package com.projectseele.client.cockpit;

import com.projectseele.ProjectSeele;
import com.projectseele.client.ClientForgeEvents;
import com.projectseele.client.cockpit.PlugChatSourceR64.Kind;
import com.projectseele.client.cockpit.PlugChatSourceR64.Line;
import com.projectseele.config.SeeleConfig;
import com.projectseele.entity.EntryPlugCarrierEntity;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.visual.EvaLogisticsCommands;
import com.projectseele.world.EvaPilotResolver;
import com.projectseele.world.NervStaffDialogue;
import net.minecraft.Util;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.Font;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.ChatScreen;
import net.minecraft.client.resources.language.I18n;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.Style;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraft.util.FormattedCharSequence;
import net.minecraft.util.Mth;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.client.event.ClientChatReceivedEvent;
import net.minecraftforge.client.event.RenderGuiOverlayEvent;
import net.minecraftforge.client.gui.overlay.IGuiOverlay;
import net.minecraftforge.client.gui.overlay.VanillaGuiOverlay;
import net.minecraftforge.eventbus.api.EventPriority;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * R64: the chat of a pilot in the plug. In first person the game's chat lay across the lower left of the view, large,
 * opaque white on a dark ground that blotted the LCL out, over the synchronisation window. Here it is a small window
 * in the upper right corner of the wall, in the cockpit's own hand: no ground, the words let the picture through,
 * each line says who speaks ((系统), (指挥), a name), a few lines at a time, and they fade.
 * <p>
 * Only what is drawn changes. Every message still goes into the game's chat, so its history, its scrolling and the
 * typing line are as ever once the chat is opened; and out of the plug or in third person the game's chat is drawn
 * as ever. A line that is already up is not put up a second time.
 */
@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class PilotChatPanelR64
{
    /** Messages up at once, their rows together, and the rows of one message. */
    private static final int MOST = 5, ROWS = 7, ROWS_EACH = 3;
    private static final int WHITE = 0xE2E7DF, PLAIN = 0xC4CCC8, MUTED = 0xA9B4B0, AMBER = 0xE8A058, CYAN = 0x75D0DA, RED = 0xF16B51;
    private static final float STRENGTH = .86F;

    private static final class Shown
    {
        final Kind kind; final String tag, body; final long born; long until;
        Shown(Line line, long born, long until) { this.kind = line.kind(); this.tag = line.tag(); this.body = line.body(); this.born = born; this.until = until; }
    }

    private static final ArrayDeque<Shown> LINES = new ArrayDeque<>();

    private PilotChatPanelR64() {}

    /** The pilot sits in the plug (the capsule, or a Unit they drive) and looks out of their own eyes. */
    public static boolean active(Minecraft mc)
    {
        if (!PilotCockpitR64.ON || mc.player == null || mc.level == null || !SeeleConfig.COCKPIT_CHAT_PANEL.get()) return false;
        if (!mc.options.getCameraType().isFirstPerson() || mc.getCameraEntity() != mc.player) return false;
        return mc.player.getVehicle() instanceof EntryPlugCarrierEntity || EvaPilotResolver.controlTarget(mc.player) != null;
    }

    /** Whatever is on its way into the chat (not the line over the hotbar) is also put up here. */
    @SubscribeEvent(priority = EventPriority.LOWEST)
    public static void heard(ClientChatReceivedEvent event)
    {
        Minecraft mc = Minecraft.getInstance();
        if (!active(mc)) return;
        if (event instanceof ClientChatReceivedEvent.System system && system.isOverlay()) return;
        Component message = event.getMessage();
        if (event instanceof ClientChatReceivedEvent.Player chat)
        {
            // The game says who sent it; what they wrote is taken without the decoration around it.
            String name = chat.getBoundChatType() == null ? "" : chat.getBoundChatType().name().getString();
            String said = chat.getPlayerChatMessage().decoratedContent().getString();
            add(name.isBlank() ? PlugChatSourceR64.system(message.getString()) : PlugChatSourceR64.player(name, said));
            return;
        }
        Line status = status(message);
        add(status != null ? status : PlugChatSourceR64.system(message.getString()));
    }

    /**
     * A Unit's status line (/seele eva status) carries its phase by name, its registry id, its LCL layers and a
     * timer: a pilot is told the phase in plain words and nothing else. The chat keeps the whole line.
     */
    private static Line status(Component message)
    {
        if (!(message.getContents() instanceof TranslatableContents line) || !EvaLogisticsCommands.STATUS_KEY.equals(line.getKey())
                || line.getArgs().length < 3) return null;
        String unit = word(line.getArgs()[0]), phase = word(line.getArgs()[1]), loaded = word(line.getArgs()[2]);
        return new Line(Kind.SYSTEM, PlugChatSourceR64.SYSTEM,
                unit + "：" + NervStaffDialogue.stage(phase) + (EvaLogisticsCommands.STATUS_UNLOADED.equals(loaded) ? "，机体未加载" : ""));
    }

    private static String word(Object argument)
    {
        return argument instanceof Component text ? text.getString() : String.valueOf(argument);
    }

    private static void add(Line line)
    {
        if (line.body().isEmpty()) return;
        long now = Util.getMillis();
        // Long enough to read: six seconds and a little for every character, fourteen at most.
        long lasts = Math.max(8000L, Math.min(14000L, 6000L + line.body().length() * 80L));
        LINES.removeIf(shown -> now >= shown.until);
        // The same words from the same mouth while they are still up: they stay up longer, they are not repeated.
        for (Shown shown : LINES)
            if (shown.kind == line.kind() && shown.tag.equals(line.tag()) && shown.body.equals(line.body()))
            {
                shown.until = now + lasts;
                return;
            }
        LINES.addLast(new Shown(line, now, now + lasts));
        while (LINES.size() > MOST) LINES.removeFirst();
    }

    /** The game's own chat is not drawn while the panel has it; with the chat opened it is, whole. */
    @SubscribeEvent
    public static void vanilla(RenderGuiOverlayEvent.Pre event)
    {
        if (event.getOverlay() != VanillaGuiOverlay.CHAT_PANEL.type()) return;
        Minecraft mc = Minecraft.getInstance();
        if (active(mc) && !(mc.screen instanceof ChatScreen)) event.setCanceled(true);
    }

    public static final IGuiOverlay OVERLAY = (gui, g, partial, width, height) ->
    {
        Minecraft mc = Minecraft.getInstance();
        if (!active(mc)) { LINES.clear(); return; }
        if (mc.options.hideGui || mc.screen instanceof ChatScreen) return;
        long now = Util.getMillis();
        LINES.removeIf(shown -> now >= shown.until);
        if (LINES.isEmpty()) return;
        draw(g, mc.font, EvaPilotResolver.controlTarget(mc.player), PilotCockpitR64.sequence(mc.player, partial) >= 0, now, width, height);
    };

    private static void draw(GuiGraphics g, Font font, EvaUnit01Entity eva, boolean sequence, long now, int width, int height)
    {
        // The same measures as the cockpit's windows (EvaPilotDisplayR45): the countdown is 104 wide at the top,
        // in the middle; the weapon's window stands at the right, two fifths down. The cabin sequence writes its
        // line a fifth down, across the middle (PilotSequenceDisplayR64).
        int margin = Math.max(8, Math.min(16, width / 45)), top = Math.max(4, margin - 4);
        int side = Math.min(132, width / 2 - margin * 2), below = Math.max(top + 46, height * 2 / 5 - 20);
        int room = width - margin - ((width + 104) / 2 + 6), line = Math.max(26, height / 5);
        int x, y, w, most;
        int[] sight = PlugCannonSightR64.down() > PlugCannonSightR64.SETTLING ? PlugCannonSightR64.window(width, height) : null;
        if (sight != null && width - margin - 104 - 6 - (sight[0] + (sight[2] - sight[0]) / 20 + 6) >= 90)
        {
            // Under the cannon's sight the wall's windows are behind its shell: what is said stands on the shell
            // above the picture, between the sight's two arms and left of the countdown.
            x = sight[0] + (sight[2] - sight[0]) / 20 + 6; w = Math.min(190, width - margin - 104 - 6 - x); y = top;
            most = Mth.clamp((sight[1] - top - 15) / 10, 1, ROWS - 2);
        }
        else if (eva != null && eva.isExperimentalUnit())
        {
            // A UN unit writes its own readouts in the corner: under them (and under the sequence's line).
            w = Mth.clamp(width / 3, 96, 172); x = width - margin - w; y = sequence ? line + 30 : top + 46; most = ROWS - 1;
        }
        else if (room < 110 || eva != null && (ClientForgeEvents.isCannonScopeActive(eva) || PlugCannonSightR64.down() > 0))
        {
            // No room beside the countdown in a narrow window, and the cannon's scope moves the countdown into
            // the corner: under the weapon's window.
            w = side; x = width - margin - w; y = below + 34; most = ROWS - 2;
        }
        else
        {
            // The corner: right of the countdown, above the weapon's window; above the sequence's line while it runs.
            w = Math.min(room, 190); x = width - margin - w; y = top;
            most = Mth.clamp(((sequence ? line : below) - top - 15) / 10, 2, ROWS);
        }

        // The newest last; when the rows run out the oldest give way.
        List<Shown> shown = new ArrayList<>();
        List<List<FormattedCharSequence>> text = new ArrayList<>();
        int rows = 0;
        for (Iterator<Shown> lines = LINES.descendingIterator(); lines.hasNext(); )
        {
            Shown entry = lines.next();
            List<FormattedCharSequence> wrapped = wrap(font, entry, w - 9, Math.min(ROWS_EACH, most));
            if (rows + wrapped.size() > most) break;
            rows += wrapped.size(); shown.add(0, entry); text.add(0, wrapped);
        }
        if (shown.isEmpty()) return;

        float strongest = 0;
        Shown voice = null;
        for (Shown entry : shown)
        {
            strongest = Math.max(strongest, strength(entry, now));
            if (entry.kind == Kind.PERSON || entry.kind == Kind.COMMAND) voice = entry;
        }
        int h = 13 + rows * 10, edge = voice != null ? RED : AMBER;
        // A window like the others on the wall, without their pane: an edge at its left, a notch at its top.
        g.fill(x, y, x + 1, y + h, alpha(strongest) << 24 | edge);
        g.fill(x + 1, y, x + Math.min(30, w), y + 1, alpha(strongest) << 24 | edge);
        g.fill(x + w - 6, y + h - 1, x + w, y + h, alpha(strongest * .5F) << 24 | edge);
        if (voice != null)
        {
            // Somebody's voice: the original marks a link without a picture so, and the level moves while they speak.
            int ink = alpha(strength(voice, now));
            g.drawString(font, "SOUND ONLY", x + 5, y + 3, ink << 24 | RED, true);
            boolean speaking = now - voice.born < 3500;
            for (int i = 0; i < 7; i++)
            {
                int level = speaking ? 2 + Math.round(3 * Math.abs(Mth.sin((now - voice.born) * .012F + i * 1.7F))) : 1;
                g.fill(x + w - 8 - i * 3, y + 10 - level, x + w - 6 - i * 3, y + 10, ink << 24 | AMBER);
            }
        }
        else g.drawString(font, I18n.get(PlugChatSourceR64.KEY_HEADER), x + 5, y + 3, alpha(strongest) << 24 | MUTED, true);

        int row = y + 13;
        for (int i = 0; i < shown.size(); i++)
        {
            int ink = alpha(strength(shown.get(i), now)) << 24 | 0xFFFFFF;
            for (FormattedCharSequence part : text.get(i))
            {
                g.drawString(font, part, x + 5, row, ink, true);
                row += 10;
            }
        }
    }

    /**
     * "(who): what", the tag in its source's colour and what is said beginning on the tag's own row, on the rows
     * PlugChatRowsR64 lays it on.
     */
    private static List<FormattedCharSequence> wrap(Font font, Shown line, int width, int most)
    {
        String tag = "(" + label(line) + "):";
        Style who = Style.EMPTY.withColor(switch (line.kind) { case PLAYER -> WHITE; case PERSON -> CYAN; case COMMAND -> AMBER; case SYSTEM -> MUTED; });
        Style what = Style.EMPTY.withColor(line.kind == Kind.SYSTEM ? PLAIN : WHITE);
        List<String> parts = PlugChatRowsR64.split(line.body, font.width(tag + " "), width, most, sign -> font.width(String.valueOf((char) sign)));
        List<FormattedCharSequence> rows = new ArrayList<>();
        for (int row = 0; row < parts.size(); row++)
        {
            String part = parts.get(row);
            rows.add(row > 0 ? Component.literal(part).withStyle(what).getVisualOrderText()
                    : Component.literal(tag).withStyle(who).append(Component.literal(part.isEmpty() ? "" : " " + part).withStyle(what)).getVisualOrderText());
        }
        return rows;
    }

    /**
     * The tag in the reader's language: the system, the command post and the staff's names have their keys. A
     * player whose name would pass for one of those is called a player before it.
     */
    private static String label(Shown line)
    {
        if (line.kind == Kind.PLAYER) return PlugChatSourceR64.taken(line.tag) ? I18n.get(PlugChatSourceR64.KEY_PLAYER, line.tag) : line.tag;
        String key = PlugChatSourceR64.key(new Line(line.kind, line.tag, ""));
        return key != null && I18n.exists(key) ? I18n.get(key) : line.tag;
    }

    /** In over a sixth of a second, out over the last second. */
    private static float strength(Shown line, long now)
    {
        return Math.min(Mth.clamp((now - line.born) / 160F, 0, 1), Mth.clamp((line.until - now) / 1000F, 0, 1));
    }

    private static int alpha(float strength)
    {
        // The font takes an alpha under 4 for none given and draws opaque.
        return Math.max(4, Math.round(255 * STRENGTH * Mth.clamp(strength, 0, 1)));
    }
}

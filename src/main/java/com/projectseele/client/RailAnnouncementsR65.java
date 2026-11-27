package com.projectseele.client;

import com.mojang.text2speech.Narrator;
import com.projectseele.ProjectSeele;
import java.util.ArrayDeque;
import java.util.List;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.sounds.SimpleSoundInstance;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.sounds.SoundEvent;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import net.minecraftforge.fml.common.Mod;

@Mod.EventBusSubscriber(modid = ProjectSeele.MODID, value = Dist.CLIENT)
public final class RailAnnouncementsR65
{
    private static final ThreadLocal<RailAnnouncementSpeechR65.Speech> NARRATION = new ThreadLocal<>();
    private static final ArrayDeque<String> pending = new ArrayDeque<>();
    private static SimpleSoundInstance playing;
    private static String remaining = "";
    private static int graceTicks;
    private static java.lang.reflect.Method translation;

    public static String format(Object key, Object latin, int count, String[] args, Object vehicle)
    {
        try
        {
            String label = (String)key.getClass().getField("key").get(key);
            boolean terminal = vehicle != null && label.equals("gui.mtr.next_station_announcement_cjk")
                    && args.length > 0 && endsAt(vehicle, args[0]);
            String corrected = RailAnnouncementSpeechR65.translated(label, args, terminal);
            if (corrected != null) return corrected;
            if (translation == null) translation = Class.forName("org.mtr.mod.data.IGui").getMethod(
                    "insertTranslation", key.getClass(), latin.getClass(), int.class, String[].class);
            return (String)translation.invoke(null, key, latin, count, args);
        }
        catch (ReflectiveOperationException ex) { throw new IllegalStateException("MTR vehicle sentence", ex); }
    }

    private static boolean endsAt(Object vehicle, String stop) throws ReflectiveOperationException
    {
        Object data = vehicle.getClass().getField("vehicleExtraData").get(vehicle);
        Class<?> type = data.getClass();
        String destination = (String)type.getMethod("getThisRouteDestination").invoke(data);
        if (!stop.equals(destination)) return false;
        String route = (String)type.getMethod("getThisRouteName").invoke(data);
        String next = (String)type.getMethod("getNextRouteName").invoke(data);
        return (next.isEmpty() || next.equals(route))
                && "NONE".equals(String.valueOf(type.getMethod("getThisRouteCircularState").invoke(data)));
    }

    public static List<String> prepare(List<String> clauses)
    {
        NARRATION.set(RailAnnouncementSpeechR65.plan(clauses));
        return clauses;
    }

    public static String spoken(String text)
    {
        var speech = NARRATION.get();
        NARRATION.remove();
        if (speech == null) return FacilityPronunciationR22.spoken(text);
        try
        {
            Object config = Class.forName("org.mtr.mod.config.Config").getMethod("getClient").invoke(null);
            if (!(boolean)config.getClass().getMethod("getTextToSpeechAnnouncements").invoke(config)) return "";
        }
        catch (ReflectiveOperationException ex) { return FacilityPronunciationR22.spoken(text); }
        var manager = Minecraft.getInstance().getSoundManager();
        if (playing != null) manager.stop(playing);
        Narrator.getNarrator().clear();
        pending.clear();
        pending.addAll(speech.clips());
        remaining = FacilityPronunciationR22.spoken(speech.chinese()) + " " + FacilityPronunciationR22.spoken(speech.english());
        playNext();
        return "";
    }

    private static void playNext()
    {
        String clip = pending.removeFirst();
        var sound = SoundEvent.createVariableRangeEvent(new ResourceLocation("projectseele_rail", clip));
        playing = SimpleSoundInstance.forUI(sound, 1.0F, 1.0F);
        Minecraft.getInstance().getSoundManager().play(playing);
        graceTicks = 4;
    }

    @SubscribeEvent
    public static void tick(TickEvent.ClientTickEvent event)
    {
        if (event.phase != TickEvent.Phase.END || playing == null) return;
        var mc = Minecraft.getInstance();
        if (mc.level == null) { playing = null; pending.clear(); remaining = ""; return; }
        if (mc.isPaused() || graceTicks-- > 0 || mc.getSoundManager().isActive(playing)) return;
        if (!pending.isEmpty()) { playNext(); return; }
        playing = null;
        if (!remaining.isBlank()) Narrator.getNarrator().say(remaining, true);
        remaining = "";
    }

    private RailAnnouncementsR65() {}
}

package com.projectseele.world;

/** Run with AllChecks: when a TV combat mission holds the city alarm. */
public final class MissionAudioR64Test
{
    private static void check(boolean expected, boolean actual, String name)
    {
        if (expected != actual) throw new AssertionError(name + ": expected " + expected + " but got " + actual);
    }

    public static void main(String[] args)
    {
        long lost = MissionAudioR64.ANGEL_MISSING_GRACE;
        for (String phase : new String[] {"alert", "approach", "combat"})
            check(true, MissionAudioR64.alarmHolds("ramiel", phase, false, true, 0), "running mission, " + phase);
        check(false, MissionAudioR64.alarmHolds("", "combat", false, true, 0), "no mission");
        for (String phase : new String[] {"idle", "cancel", "failure", "combat_victory", "episode_archived"})
            check(false, MissionAudioR64.alarmHolds("ramiel", phase, false, true, 0), "mission over, " + phase);
        check(false, MissionAudioR64.alarmHolds("ramiel", "combat", true, true, 0), "Angel confirmed dead");
        check(false, MissionAudioR64.alarmHolds("ramiel", "combat", false, false, 0), "commander offline, mission paused");
        check(true, MissionAudioR64.alarmHolds("ramiel", "combat", false, true, lost - 1), "Angel missing for a moment");
        check(false, MissionAudioR64.alarmHolds("ramiel", "combat", false, true, lost), "Angel lost");
    }

    private MissionAudioR64Test() { }
}

package com.projectseele.world;

/** Event ordering and duplicate suppression without a server, world, or sound playback. */
public final class TvYashimaCombatCommsR54Test
{
    public static void main(String[] args)
    {
        var pulse = new TvYashimaCombatCommsR54.Pulse();
        require(!pulse.cancel() && !pulse.end(), "Idle must stay silent");
        require(pulse.charge(160) && !pulse.charge(160), "Charge begins once");
        int cues = 0;
        for (int remaining = 159; remaining > 0; remaining--)
        {
            int cue = pulse.countdown(remaining);
            if (remaining == 60) require(cue == 3, "Three-second warning");
            else if (remaining == 20) require(cue == 1, "One-second warning");
            else require(cue == 0, "No per-tick chatter");
            if (cue != 0) cues++;
            require(pulse.countdown(remaining) == 0, "Repeated tick must stay silent");
        }
        require(cues == 2 && pulse.fire() && !pulse.fire(), "One actual fire report");
        require(!pulse.cancel() && pulse.end() && !pulse.end(), "Only actual beam end reports closure");
        require(pulse.charge(160), "Next real attack re-arms warnings");
        require(pulse.countdown(59) == 3 && pulse.countdown(19) == 1, "Delayed ticks cross warning thresholds");
        require(pulse.cancel() && !pulse.cancel(), "Cancellation reported once");
        require(pulse.countdown(1) == 0 && !pulse.end(), "Cancelled charge cannot announce firing window closure");
        require(pulse.charge(30) && pulse.countdown(20) == 1, "Short charge skips inapplicable three-second cue");
        require(pulse.countdown(40) == 0 && pulse.countdown(20) == 0, "Extended effective duration cannot repeat cue");
        require(pulse.cancel(), "Short charge still cancellable");
        System.out.println("PASS: actual-event ordering, two countdown cues, duplicate suppression, cancellation, and repeat attack");
    }

    private static void require(boolean condition, String message)
    { if (!condition) throw new AssertionError(message); }
}

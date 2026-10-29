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
        require(TvYashimaCombatCommsR54.shotResult(false,true,false,true,true,420,210)==TvYashimaCombatCommsR54.ShotResult.MISS,
                "A different hit entity cannot become this mission's core hit");
        require(TvYashimaCombatCommsR54.shotResult(true,false,true,false,false,420,420)==TvYashimaCombatCommsR54.ShotResult.AT_BLOCKED,
                "Closed core with active AT field reports no core damage");
        require(TvYashimaCombatCommsR54.shotResult(true,false,false,false,false,420,420)==TvYashimaCombatCommsR54.ShotResult.CORE_CLOSED,
                "Exhausted AT field does not open a sealed core");
        require(TvYashimaCombatCommsR54.shotResult(true,true,true,false,false,420,420)==TvYashimaCombatCommsR54.ShotResult.CORE_MISSED,
                "An exposed shell hit is not a core hit");
        require(TvYashimaCombatCommsR54.shotResult(true,true,true,true,false,420,420)==TvYashimaCombatCommsR54.ShotResult.NO_DAMAGE,
                "Rejected hurt cannot claim effective damage");
        require(TvYashimaCombatCommsR54.shotResult(true,true,true,true,true,420,420)==TvYashimaCombatCommsR54.ShotResult.NO_DAMAGE,
                "Accepted hurt without real health loss cannot claim effective damage");
        require(TvYashimaCombatCommsR54.shotResult(true,true,true,true,true,420,210)==TvYashimaCombatCommsR54.ShotResult.CORE_HIT,
                "The actual exposed core hit bypasses the remaining AT pool");
        require(TvYashimaCombatCommsR54.shotResult(true,true,true,true,true,210,0)==TvYashimaCombatCommsR54.ShotResult.CORE_DESTROYED,
                "Lethal core hit keeps its final result");
        require(TvYashimaCombatCommsR54.shotResult(true,true,false,true,true,Float.NaN,0)==TvYashimaCombatCommsR54.ShotResult.NO_DAMAGE,
                "Invalid health values cannot invent confirmation");
        System.out.println("PASS: actual-event ordering, two countdown cues, duplicate suppression, cancellation, and repeat attack");
        System.out.println("PASS: misses, closed core, AT protection, shell hits, rejected/no-damage hits, effective and lethal core damage");
    }

    private static void require(boolean condition, String message)
    { if (!condition) throw new AssertionError(message); }
}

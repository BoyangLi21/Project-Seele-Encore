package com.projectseele.client.cockpit;

/** R64: the eject key asks first; a second press ejects, the cancel key or time takes the warning down. */
public final class PlugEjectConfirmR64Test
{
    private static int checked;

    private static void check(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    public static void main(String[] args)
    {
        check(!PlugEjectConfirmR64.asking(), "No warning before any key");
        check(!PlugEjectConfirmR64.cancelled(), "Nothing to cancel before any key");
        // One press asks, the second ejects.
        check(!PlugEjectConfirmR64.pressed(7) && PlugEjectConfirmR64.asking(), "The first press only puts the warning up");
        PlugEjectConfirmR64.tick(7);
        check(PlugEjectConfirmR64.pressed(7) && !PlugEjectConfirmR64.asking(), "The second press ejects and takes the warning down");
        check(!PlugEjectConfirmR64.pressed(7), "After an ejection the next press asks again");
        // The cancel key.
        check(PlugEjectConfirmR64.cancelled() && !PlugEjectConfirmR64.asking(), "The cancel key takes the warning down");
        check(!PlugEjectConfirmR64.pressed(7), "After a cancel the next press asks again, it does not eject");
        // Time: the warning stands for the whole window and not a tick longer.
        for (int tick = 0; tick < PlugEjectConfirmR64.WINDOW - 1; tick++) PlugEjectConfirmR64.tick(7);
        check(PlugEjectConfirmR64.asking(), "The warning still stands one tick before its time is up");
        PlugEjectConfirmR64.tick(7);
        check(!PlugEjectConfirmR64.asking(), "The warning goes when its time is up");
        check(!PlugEjectConfirmR64.pressed(7), "A press after the time is up asks again");
        // Another Unit, or none: the warning asked in one Unit ejects nobody from another.
        PlugEjectConfirmR64.tick(-1);
        check(!PlugEjectConfirmR64.asking(), "The warning goes at once outside the Unit");
        check(!PlugEjectConfirmR64.pressed(7) && !PlugEjectConfirmR64.pressed(8) && PlugEjectConfirmR64.asking(), "A press in another Unit asks anew");
        check(PlugEjectConfirmR64.pressed(8), "And its second press ejects from that one");
        System.out.println("PlugEjectConfirmR64Test: " + checked + " checks passed.");
    }
}

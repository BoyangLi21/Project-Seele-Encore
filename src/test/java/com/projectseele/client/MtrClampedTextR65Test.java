package com.projectseele.client;

import com.projectseele.compat.MtrClampedTextR65;

/** Only the images MTR copies into a smaller texture are closed; the ones it keeps are never touched. */
public final class MtrClampedTextR65Test
{
    private static int checked;

    private static void that(boolean condition, String message)
    {
        if (!condition) throw new AssertionError(message);
        checked++;
    }

    /** Stands in for MTR's image holder: the three methods the fix calls. */
    public static final class FakeImage
    {
        final int width, height;
        boolean closed;

        FakeImage(int width, int height)
        {
            this.width = width;
            this.height = height;
        }

        public int getWidth() { return width; }

        public int getHeight() { return height; }

        public void close() { closed = true; }
    }

    public static void main(String[] args)
    {
        that(MtrClampedTextR65.limit(0) == 2048, "resolution 0 keeps 2048");
        that(MtrClampedTextR65.limit(2) == 8192, "the shipped resolution 2 keeps 8192");
        that(!MtrClampedTextR65.clamped(8192, 8192, 2), "an image at the limit is used as it is");
        that(MtrClampedTextR65.clamped(8193, 96, 2), "one pixel wider is copied");
        that(MtrClampedTextR65.clamped(96, 9000, 2), "too tall is copied too");

        var wide = new FakeImage(9600, 96);
        MtrClampedTextR65.closeIfClamped(wide, 2);
        that(wide.closed, "a long scrolling message, copied by MTR, has its original closed");
        var kept = new FakeImage(4000, 96);
        MtrClampedTextR65.closeIfClamped(kept, 2);
        that(!kept.closed, "an image MTR uses as its texture is never closed");
        var atOne = new FakeImage(4000, 96);
        MtrClampedTextR65.closeIfClamped(atOne, 0);
        that(atOne.closed, "at resolution 0 the same image is over the limit and closed");
        that(MtrClampedTextR65.closedCount() == 2, "two originals closed");
        MtrClampedTextR65.closeIfClamped(null, 2);
        that(MtrClampedTextR65.closedCount() == 2, "nothing to close is nothing closed");
        // Without MTR (as in this check) the config cannot be read: the fix stands down instead of failing.
        var noMtr = new FakeImage(9600, 96);
        MtrClampedTextR65.closeIfClamped(noMtr);
        that(!noMtr.closed, "without MTR's config nothing is closed");
        var after = new FakeImage(9600, 96);
        MtrClampedTextR65.closeIfClamped(after, 2);
        that(!after.closed, "and after standing down it stays down");
        System.out.println("MtrClampedTextR65Test: " + checked + " checks passed");
    }
}

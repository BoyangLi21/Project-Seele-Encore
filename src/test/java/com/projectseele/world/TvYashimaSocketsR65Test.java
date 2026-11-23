package com.projectseele.world;

import net.minecraft.core.BlockPos;
import java.util.List;

/** Run with AllChecks: which sockets a unit at the Yashima position takes its power from (R65). */
public final class TvYashimaSocketsR65Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    public static void main(String[] args)
    {
        List<BlockPos> gun = List.of(new BlockPos(-1305, 187, -1374), new BlockPos(-1305, 187, -1369), new BlockPos(-1305, 187, -1364));
        List<BlockPos> cover = List.of(new BlockPos(-1210, 187, -1420));
        check(TvYashimaDirectorR50.socketsR65(0, gun, cover) == cover, "Unit-00 takes its own sockets where the site names any");
        check(TvYashimaDirectorR50.socketsR65(1, gun, cover) == gun, "The gunner stays on the gun's sockets");
        check(TvYashimaDirectorR50.socketsR65(2, gun, cover) == gun, "So does any other unit");
        check(TvYashimaDirectorR50.socketsR65(0, gun, List.of()) == gun, "A site that names none leaves Unit-00 on the gun's sockets, as before R65");
        System.out.println("TvYashimaSocketsR65Test: " + checks + " checks passed");
    }
}

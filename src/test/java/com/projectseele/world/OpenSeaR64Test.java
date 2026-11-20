package com.projectseele.world;

/** Run with AllChecks: the generated sea beyond the saved chunks (R64 M6). */
public final class OpenSeaR64Test
{
    private static void check(boolean ok, String name)
    {
        if (!ok) throw new AssertionError(name);
    }

    public static void main(String[] args)
    {
        // The adjacent cliff columns and the shoreline south of the second viewpoint
        // are surveyed ground. A new chunk must produce the same profile as the patched save.
        int[][] banks = {{3279, -2106, 97}, {3280, -2106, 96}, {3306, -2145, 65}, {3306, -2144, 62}};
        if (PlaytestLandscapeR64.hasSurvey()) for (int[] column : banks)
        {
            var regenerated = HakoneSurfaceField.sample(column[0], column[1], 70);
            check(regenerated.ground() == column[2], "playtest bank at " + column[0] + "," + column[1] + " = " + regenerated.ground());
        }
        // Straight out from the east edge of the saved chunks (x 4511) through open water.
        int z = 800, previous = 0;
        for (int d : new int[] {1, 48, 100, 300, 800, 1600, 3000})
        {
            var s = HakoneSurfaceField.sample(4511 + d, z, 0);
            String at = "east +" + d + " ground " + s.ground();
            check(s.water() == HakoneSurfaceField.SEA_Y, at + ": water stays at the sea datum");
            check(s.ground() < HakoneSurfaceField.SEA_Y - 3 && s.ground() >= OuterBoundaryTerrain.SEA_FLOOR, at + ": open water, above the floor");
            check(OuterBoundaryTerrain.cover(4511 + d, z, s.ground()) != 1, at + ": no sand out at sea");
            if (d == 1) check(Math.abs(s.ground() - OuterBoundaryTerrain.SEAM_BED) <= 1, at + ": meets the saved -90 seabed");
            if (d == 100) check(s.ground() <= -92 && s.ground() >= -99, at + ": about -95 a hundred blocks out");
            if (d >= 1600) check(s.ground() <= -114, at + ": near the floor far out");
            if (d >= 300) check(s.ground() <= previous + 3, at + ": keeps deepening outward");
            previous = s.ground();
        }
        // Unsaved surveyed sea south of the saved chunks deepens too, instead of the flat -90 shelf.
        var south = HakoneSurfaceField.sample(3800, 3400, 0);
        check(south.water() == HakoneSurfaceField.SEA_Y && south.ground() < -100, "south sea ground " + south.ground() + " deepens");
        // The bed formula on its own: seam value, floor, never dry.
        check(Math.abs(OuterBoundaryTerrain.openSeaBed(4512, z, 2000) - OuterBoundaryTerrain.SEAM_BED) < 1, "bed at the seam");
        for (int x = 4600; x < 9000; x += 97)
        {
            double bed = OuterBoundaryTerrain.openSeaBed(x, z, 2000);
            check(bed >= OuterBoundaryTerrain.SEA_FLOOR && bed <= HakoneSurfaceField.SEA_Y - 1, "bed at x " + x + " = " + bed);
        }
        // A shoreface rises to any coast.
        check(OuterBoundaryTerrain.openSeaBed(7000, z, 5) > OuterBoundaryTerrain.openSeaBed(7000, z, 400), "shoreface");
    }

    private OpenSeaR64Test() { }
}

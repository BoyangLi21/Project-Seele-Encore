package com.projectseele.world;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Random;
import java.util.Set;

/** Run with AllChecks: the cell set behind the street-pass list, and the form it is sent to clients in. */
public final class StreetPassCellsR64Test
{
    private static int checks;
    private static void check(boolean value, String why)
    {
        checks++;
        if (!value) throw new AssertionError(why);
    }

    private static long key(int x, int y, int z)
    {
        return ((long) x << 40) ^ ((long) z << 16) ^ (y & 0xFFFF);
    }

    public static void main(String[] args)
    {
        // Membership, across section edges and on both sides of zero.
        int[] some = {0, 80, 0, -1, 80, -1, 15, 95, 15, 16, 96, 16, -17, -64, -33, 5, 89, 20, 5, 81, 20, 1_000_000, 300, -1_000_000};
        StreetPassCellsR64 cells = StreetPassCellsR64.of(some);
        check(cells.size() == 8, "Eight cells listed, eight held: " + cells.size());
        for (int i = 0; i < some.length; i += 3) check(cells.contains(some[i], some[i + 1], some[i + 2]), "Listed cell " + i / 3 + " is held");
        check(!cells.contains(0, 81, 0) && !cells.contains(1, 80, 0) && !cells.contains(0, 80, 1), "A neighbour of a listed cell is not held");
        check(!cells.contains(-1, 80, 0) && !cells.contains(15, 95, 16) && !cells.contains(16, 96, 15), "Cells over a section edge are told apart");
        check(!cells.contains(5, 82, 20), "A pole listed at 81 and 89 does not hold 82");
        check(!cells.contains(Integer.MAX_VALUE, 0, 0) && !cells.contains(0, Integer.MIN_VALUE, 0), "Far outside, nothing");
        check(StreetPassCellsR64.of(new int[]{3, 4, 5, 3, 4, 5}).size() == 1, "A repeated cell counts once");
        check(StreetPassCellsR64.of(new int[0]) == StreetPassCellsR64.EMPTY && StreetPassCellsR64.EMPTY.isEmpty(), "No cells, the empty set");
        check(!StreetPassCellsR64.EMPTY.contains(0, 0, 0), "The empty set holds nothing");
        try
        {
            StreetPassCellsR64.of(new int[]{1, 2});
            check(false, "Cells that are not triples are refused");
        }
        catch (IllegalArgumentException expected)
        {
            checks++;
        }

        // The sent form gives back exactly the same cells.
        StreetPassCellsR64 back = StreetPassCellsR64.decode(cells.encode());
        check(Arrays.equals(back.cells(), cells.cells()) && back.size() == cells.size(), "The sent form gives back the same cells");
        check(StreetPassCellsR64.decode(StreetPassCellsR64.EMPTY.encode()).isEmpty(), "An empty list goes and comes back empty");
        check(StreetPassCellsR64.decode(new byte[0]).isEmpty(), "No bytes, no cells");

        // A list the size of the city's street furniture: 1,483 poles of nine cells and 1,344 wire spans of ten.
        Random random = new Random(511);
        Set<Long> wanted = new HashSet<>();
        int[] city = new int[(1483 * 9 + 1344 * 10) * 3];
        int n = 0;
        for (int pole = 0; pole < 1483; pole++)
        {
            int x = -306 + random.nextInt(592), z = 4 + random.nextInt(552);
            for (int y = 81; y <= 89; y++)
            {
                city[n++] = x; city[n++] = y; city[n++] = z;
                wanted.add(key(x, y, z));
            }
        }
        for (int span = 0; span < 1344; span++)
        {
            int x = -306 + random.nextInt(592), z = 4 + random.nextInt(552);
            boolean alongX = random.nextBoolean();
            for (int i = 0; i < 10; i++)
            {
                int cx = alongX ? x + i : x, cz = alongX ? z : z + i;
                city[n++] = cx; city[n++] = 88; city[n++] = cz;
                wanted.add(key(cx, 88, cz));
            }
        }
        StreetPassCellsR64 big = StreetPassCellsR64.of(city);
        check(big.size() == wanted.size(), "Every distinct cell is held once: " + big.size() + " of " + wanted.size());
        byte[] sent = big.encode();
        check(sent.length < StreetPassCellsR64.MAX_ENCODED, "The city's list fits one message: " + sent.length + " bytes");
        check(sent.length < big.size() * 4, "The sent form is compact: " + sent.length + " bytes for " + big.size() + " cells");
        StreetPassCellsR64 bigBack = StreetPassCellsR64.decode(sent);
        check(Arrays.equals(bigBack.cells(), big.cells()), "The city's list comes back cell for cell");
        int misses = 0;
        for (int i = 0; i < 20000; i++)
        {
            int x = -320 + random.nextInt(620), y = 78 + random.nextInt(14), z = -10 + random.nextInt(580);
            if (big.contains(x, y, z) != wanted.contains(key(x, y, z))) misses++;
        }
        check(misses == 0, "Random cells answer as the plain set does: " + misses + " differ");

        // A damaged message is refused, never half read.
        byte[] cut = Arrays.copyOf(sent, sent.length / 2);
        boolean refused = false;
        try
        {
            StreetPassCellsR64.decode(cut);
        }
        catch (IllegalArgumentException expected)
        {
            refused = true;
        }
        check(refused, "A message cut in half is refused");
        refused = false;
        try
        {
            StreetPassCellsR64.decode(new byte[]{1, 2, 3, 4, 5});
        }
        catch (IllegalArgumentException expected)
        {
            refused = true;
        }
        check(refused, "Bytes that are not a list are refused");
        System.out.println("StreetPassCellsR64Test: " + checks + " checks passed");
    }
}

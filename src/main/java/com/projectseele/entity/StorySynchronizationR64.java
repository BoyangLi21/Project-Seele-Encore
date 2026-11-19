package com.projectseele.entity;

/** Authored cockpit baselines in unit order 01, 00, 02. A missing sortie has no measurement. */
public final class StorySynchronizationR64
{
    private StorySynchronizationR64() {}

    public static final float UNAVAILABLE = -1F;
    private enum Chapter
    {
        sachiel(41.3F, -1, -1), shamshel(46, -1, -1), rain(44, 36, -1),
        ramiel(52, 38, -1), jet_alone(54, 40, -1), gaghiel(55, 41, 72),
        israfel(58, 42, 74), sandalphon(60, 43, 76), matarael(62, 44, 77),
        sahaquiel(65, 45, 78), ireul(66, 46, 78), compatibility(70, 47, 78),
        leliel(79, 48, 77), fourth_child(78, 48, 74), bardiel(76, 49, 72),
        zeruel(80, 50, 60), recovery(-1, 51, 52), arael(82, 52, 38),
        armisael(83, 54, 12), tabris(84, 50, 0);

        final float shinji, rei, asuka;
        Chapter(float shinji, float rei, float asuka)
        {
            this.shinji = shinji;
            this.rei = rei;
            this.asuka = asuka;
        }
    }

    public static float baseline(String chapter, int variant)
    {
        Chapter row;
        try { row = Chapter.valueOf(chapter.isEmpty() ? "sachiel" : chapter); }
        catch (IllegalArgumentException unknownChapter) { row = Chapter.sachiel; }
        return switch (variant) {
            case 0 -> row.rei;
            case 1 -> row.shinji;
            case 2 -> row.asuka;
            default -> UNAVAILABLE;
        };
    }
}

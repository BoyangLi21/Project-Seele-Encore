package com.projectseele.visual;

/** Explicit private review target; ordinary stage/player worlds never match. */
public final class NativeReviewWorldsR45
{
    private static final String EXPECTED=System.getProperty(
            "projectseele.nativeReviewWorld","SEELE_FIELD_R44_REVIEW");
    static
    {
        if(!EXPECTED.equals("SEELE_FIELD_R44_REVIEW")&&!EXPECTED.equals("SEELE_FIELD_R45_REVIEW"))
            throw new IllegalArgumentException("Unrecognized private native review world");
    }
    public static String expectedName(){return EXPECTED;}
    private NativeReviewWorldsR45() {}
}

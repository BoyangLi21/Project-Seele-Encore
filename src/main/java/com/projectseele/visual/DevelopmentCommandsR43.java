package com.projectseele.visual;

/** Historical builders and laboratories do not belong in the playable command tree. */
public final class DevelopmentCommandsR43
{
    public static boolean enabled()
    {
        return Boolean.getBoolean("projectseele.developerCommands")
                ||!System.getProperty("projectseele.regionalBuild","").isBlank();
    }
    private DevelopmentCommandsR43() {}
}

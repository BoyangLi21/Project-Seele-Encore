package com.projectseele.world;

import java.nio.file.*;
import java.nio.file.attribute.BasicFileAttributes;
import java.io.IOException;

/** File-only positive/negative metadata cache. It grants no world readiness,
 * legacy fallback, body movement or geometry permission. */
public final class NervManifestPollR52
{
    public record Probe(boolean available,boolean changed,long modified,long size,String fault){}
    private Path path;private long polled=Long.MIN_VALUE,modified=-1,size=-1,lastWarn=Long.MIN_VALUE;
    private boolean available,invalidated=true;private String fault="",warned="";
    public void invalidate(){invalidated=true;polled=Long.MIN_VALUE;}
    public Probe probe(Path requested,long tick)throws IOException
    {
        var actual=requested.toAbsolutePath().normalize();boolean changedPath=!actual.equals(path);if(!invalidated&&!changedPath&&polled!=Long.MIN_VALUE&&tick>=polled&&tick-polled<20)return new Probe(available,false,modified,size,fault);
        boolean forced=invalidated||changedPath;invalidated=false;path=actual;polled=tick;
        if(!Files.isRegularFile(actual)){boolean changed=forced||available;available=false;modified=-1;size=-1;fault="Missing/unavailable explicit Root lift manifest: "+actual;return new Probe(false,changed,-1,-1,fault);}
        var attrs=Files.readAttributes(actual,BasicFileAttributes.class);long nextModified=attrs.lastModifiedTime().toMillis(),nextSize=attrs.size();boolean changed=forced||!available||modified!=nextModified||size!=nextSize;available=true;modified=nextModified;size=nextSize;fault="";return new Probe(true,changed,modified,size,"");
    }
    public boolean warningDue(String reason,long tick)
    {if(reason.equals(warned)&&lastWarn!=Long.MIN_VALUE&&tick>=lastWarn&&tick-lastWarn<1200)return false;warned=reason;lastWarn=tick;return true;}
}

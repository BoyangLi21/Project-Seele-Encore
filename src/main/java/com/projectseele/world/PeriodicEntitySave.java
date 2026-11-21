package com.projectseele.world;

/** Applies only to the next non-flushing, vanilla scheduled autosave in this dimension. */
public interface PeriodicEntitySave
{
    void seele$periodicSave(boolean scheduled);
}

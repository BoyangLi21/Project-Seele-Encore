package com.projectseele.world;

import java.lang.ref.WeakReference;
import java.util.Map;
import java.util.WeakHashMap;
import java.util.function.Supplier;

/**
 * Presentation state that belongs to one entity object. Entities compare by network id, and one that leaves a
 * player's range and comes back is a new client object with the old id: in a map keyed by the entity it finds
 * the state of the object that was removed, for as long as that one has not been collected. Samples from before
 * the gap must not be blended into the ones after it.
 */
public final class ClientEntityStateR64<E, S>
{
    private record Held<E, S>(WeakReference<E> owner, S state) {}
    private final Map<E, Held<E, S>> states = new WeakHashMap<>();

    public synchronized S of(E entity, Supplier<S> fresh)
    {
        Held<E, S> held = states.get(entity);
        if (held == null || held.owner().get() != entity)
        {
            // Out with the old key as well: put alone would keep it, and the entry would go when it is collected.
            states.remove(entity);
            held = new Held<>(new WeakReference<>(entity), fresh.get());
            states.put(entity, held);
        }
        return held.state();
    }

    public synchronized int size()
    {
        return states.size();
    }
}

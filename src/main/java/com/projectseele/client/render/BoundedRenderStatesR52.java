package com.projectseele.client.render;

import java.util.LinkedHashMap;
import java.util.function.Consumer;

/** A few actual render states per source part; eviction releases the old resource. */
final class BoundedRenderStatesR52<K, V>
{
    private final int limit;
    private final Consumer<V> release;
    private final LinkedHashMap<K, V> states = new LinkedHashMap<>(8, .75F, true);

    BoundedRenderStatesR52(int limit, Consumer<V> release)
    {
        if (limit < 1) throw new IllegalArgumentException("Positive render-state limit required");
        this.limit = limit;
        this.release = release;
    }

    V get(K key) { return this.states.get(key); }

    boolean put(K key, V value)
    {
        this.states.put(key, value);
        if (this.states.size() <= this.limit) return false;
        var oldest = this.states.entrySet().iterator();
        this.release.accept(oldest.next().getValue());
        oldest.remove();
        return true;
    }

    void clear()
    {
        this.states.values().forEach(this.release);
        this.states.clear();
    }

    int retain(K key)
    {
        int released = 0;
        var entries = this.states.entrySet().iterator();
        while (entries.hasNext())
        {
            var entry = entries.next();
            if (entry.getKey().equals(key)) continue;
            this.release.accept(entry.getValue());
            entries.remove();
            released++;
        }
        return released;
    }

    int size() { return this.states.size(); }
}

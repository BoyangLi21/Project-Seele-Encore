package com.projectseele.world;

import java.util.List;
import java.util.function.BooleanSupplier;

/** Yield between original owners; a complete owner verification remains indivisible. */
final class CityEndpointFinalizerR51<T>
{
    @FunctionalInterface
    interface Action<T>
    {
        void apply(T owner) throws Exception;
    }

    private final List<T> owners;
    private int verified, removed;

    CityEndpointFinalizerR51(List<T> owners)
    {
        this.owners = List.copyOf(owners);
    }

    boolean step(Action<T> verify, Action<T> remove, int ownerLimit, BooleanSupplier timeAvailable) throws Exception
    {
        if (ownerLimit <= 0) throw new IllegalArgumentException("Positive endpoint owner limit required");
        int processed = 0;
        if (verified < owners.size())
        {
            while (verified < owners.size() && processed < ownerLimit && timeAvailable.getAsBoolean())
            {
                verify.apply(owners.get(verified));
                verified++; processed++;
            }
            return false;
        }
        while (removed < owners.size() && processed < ownerLimit && timeAvailable.getAsBoolean())
        {
            T owner = owners.get(removed);
            // Earlier checks ran on other ticks. Full live NBT must still
            // match immediately before this original owner is removed.
            verify.apply(owner);
            remove.apply(owner);
            removed++; processed++;
        }
        return removed == owners.size();
    }

    int verified() { return verified; }
    int removed() { return removed; }
    int size() { return owners.size(); }
}

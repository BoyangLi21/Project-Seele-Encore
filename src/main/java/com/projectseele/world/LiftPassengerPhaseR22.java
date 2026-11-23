package com.projectseele.world;
import net.minecraft.world.entity.player.Player;
import java.util.function.BiConsumer;
/** Optional client hook, avoiding a dedicated-server dependency on client classes. */
public final class LiftPassengerPhaseR22
{
    public static BiConsumer<Player,Double> afterClientCarry=(p,dy)->{};
    /** Client: after a moving car carried its riders, place the other players standing in it (car in world space). */
    public interface RemoteRiders{void place(net.minecraft.world.level.Level level,net.minecraft.world.phys.AABB car,double floor);}
    public static RemoteRiders remoteRiders=(level,car,floor)->{};
    private LiftPassengerPhaseR22(){}
}

package com.projectseele.mixin;

import com.projectseele.physics.FullCubeBoxesR53;
import net.minecraft.world.phys.shapes.Shapes;
import net.minecraft.world.phys.shapes.VoxelShape;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Pseudo;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

@Pseudo
@Mixin(targets="com.atsuishio.superbwarfare.entity.vehicle.utils.VehicleMotionUtils", remap=false)
public abstract class SbwTerrainBoxesR53Mixin
{
    @Redirect(method="sampleTerrainTop", remap=false,
            at=@At(value="INVOKE", target="Lnet/minecraft/world/phys/shapes/VoxelShape;forAllBoxes(Lnet/minecraft/world/phys/shapes/Shapes$DoubleLineConsumer;)V", remap=true))
    private void seele$terrainBoxes(VoxelShape shape, Shapes.DoubleLineConsumer consumer)
    {
        FullCubeBoxesR53.visit(shape, consumer);
    }
}

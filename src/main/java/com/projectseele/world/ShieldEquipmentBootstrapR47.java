package com.projectseele.world;

import com.projectseele.ProjectSeele;
import com.projectseele.entity.EvaShieldRigR47;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.world.phys.Vec3;
import net.minecraftforge.fml.event.lifecycle.FMLCommonSetupEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.eventbus.api.SubscribeEvent;
import java.util.Optional;

@Mod.EventBusSubscriber(modid=ProjectSeele.MODID,bus=Mod.EventBusSubscriber.Bus.MOD)
public final class ShieldEquipmentBootstrapR47
{
    @SubscribeEvent
    public static void setup(FMLCommonSetupEvent event)
    {
        event.enqueueWork(()->TvEncounterEquipmentControlR45.install(new TvEncounterEquipmentControlR45.ShieldGeometry()
        {
            public boolean equipped(EvaUnit01Entity eva){return EvaShieldRigR47.equipped(eva);}
            public boolean intersects(EvaUnit01Entity eva,Vec3 from,Vec3 to){return EvaShieldRigR47.intercept(eva,from,to).isPresent();}
            public Optional<Vec3> firstIntersection(EvaUnit01Entity eva,Vec3 from,Vec3 to){return EvaShieldRigR47.intercept(eva,from,to);}
            public boolean input(EvaUnit01Entity eva,TrainingPilotEntity pilot,boolean brace){return eva.autonomousShieldBraceR47(pilot,brace);}
        }));
    }
    private ShieldEquipmentBootstrapR47(){}
}

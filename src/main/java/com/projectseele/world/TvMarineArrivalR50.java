package com.projectseele.world;

import com.projectseele.entity.EvaAirTransportR31;
import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;

/** The existing NERV aircraft carries the original launched fleet to its measured naval port. */
public final class TvMarineArrivalR50
{
    public static boolean holdForDelivery(ServerLevel level,TvCampaignSavedData data,EvaUnit01Entity eva,
            TrainingPilotEntity pilot,ServerPlayer commander,Vec3 port)
    {
        if(!data.active.equals("gaghiel")||port==null||eva.getUnitVariant()>2)return false;
        var sortie=data.sorties.get(eva.getUnitVariant());
        if(sortie==null||!sortie.npc||sortie.eva==null||!sortie.eva.equals(eva.getUUID())||sortie.pilotR45==null
                ||!sortie.pilotR45.equals(pilot.getUUID())||eva.getPilotEntity()!=pilot||commander==null
                ||!commander.getUUID().equals(sortie.commander))
        {eva.stopAutonomousR30();return true;}
        var tags=eva.getPersistentData();
        boolean receipt=tags.getLong("R50MarineArrivalGeneration")==data.generationR43
                &&tags.getString("R50MarineArrivalLayout").equals(data.encounterLayoutR45);
        if(receipt)return false;
        // An actual body-support contact after release owns arrival. A flight
        // order, location interpolation or a nearby ship bridge is not receipt.
        if(!EvaAirTransportR31.active(eva)&&!NervAirLiftR30.ownsMotion(eva)
                &&eva.position().subtract(port).horizontalDistance()<=16&&Math.abs(eva.getY()-port.y)<=16
                &&AirCradleClearanceR31.touchdownContact(eva)!=null)
        {
            tags.putLong("R50MarineArrivalGeneration",data.generationR43);
            tags.putString("R50MarineArrivalLayout",data.encounterLayoutR45);
            data.notice="原机体与原插入栓已在海战接应冠实际接地，交由海战驾驶员继续行动。";data.setDirty();return false;
        }
        eva.stopAutonomousR30();
        if(EvaAirTransportR31.active(eva)||NervAirLiftR30.deliveryPendingR50(level,eva,commander.getUUID()))
        {data.notice="原重型运输机正将本机送往海战接应冠 · "+NervAirLiftR30.status(level);return true;}
        if(!EvaLogisticsDirector.status(level,eva.getUnitVariant()).phase().equals("DEPLOYED")||eva.getY()<64)
        {data.notice="等待原机按原机库与发射井流程抵达地表；地下不得起吊。";return true;}
        if(NervAirLiftR30.busy(level)){data.notice="等待原重型运输机完成当前任务，再接本机前往港区。";return true;}
        long next=tags.getLong("R50MarineDeliveryNextRequest");
        if(level.getGameTime()<next&&next-level.getGameTime()<=100)return true;
        tags.putLong("R50MarineDeliveryNextRequest",level.getGameTime()+100);
        eva.settleAutonomousAttackR30(pilot);eva.autonomousWeaponR30(pilot,EvaUnit01Entity.WEAPON_FISTS);
        String result=NervAirLiftR30.request(commander,eva.getUnitVariant(),false,(int)Math.floor(port.x),(int)Math.floor(port.z));
        data.notice=result;data.setDirty();return true;
    }
    private TvMarineArrivalR50(){}
}

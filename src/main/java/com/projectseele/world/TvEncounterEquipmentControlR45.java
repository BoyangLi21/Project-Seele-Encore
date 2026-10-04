package com.projectseele.world;

import com.projectseele.entity.EvaUnit01Entity;
import com.projectseele.entity.NervArmamentStationEntity;
import com.projectseele.entity.TrainingPilotEntity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.phys.Vec3;

/** Physical entity bridge; missing measured shield geometry keeps the mission blocked. */
public final class TvEncounterEquipmentControlR45 implements TvEncounterRulesR45.EquipmentControl
{
    public interface CannonAccess
    {
        double effectiveCannonRangeR45();
        boolean missionCannonInputR45(TrainingPilotEntity pilot,Vec3 aim,boolean hold,boolean release);
    }
    public interface CargoRackAccess
    {boolean issueTvMissionEquipmentR45(LivingEntity actualPilot,EvaUnit01Entity eva);}
    /** Root supplies the same real shield surface used by rendering and incoming-ray contact. */
    public interface ShieldGeometry
    {
        boolean equipped(EvaUnit01Entity eva);
        boolean intersects(EvaUnit01Entity eva,Vec3 from,Vec3 to);
        /** Exact first point on the root-owned rendered shield; no guessed plane fallback. */
        default java.util.Optional<Vec3> firstIntersection(EvaUnit01Entity eva,Vec3 from,Vec3 to)
        {return java.util.Optional.empty();}
        boolean input(EvaUnit01Entity eva,TrainingPilotEntity pilot,boolean brace);
    }
    private final ShieldGeometry shield;
    private TvEncounterEquipmentControlR45(ShieldGeometry shield){this.shield=shield;}
    /** Physical inventory and real cannon work before a measured shield is installed. */
    public static TvEncounterRulesR45.EquipmentControl serverCargoAndCannonR45()
    {return new TvEncounterEquipmentControlR45(null);}
    public static void install(ShieldGeometry actualShield)
    {TvEncounterRulesR45.installEquipmentControl(new TvEncounterEquipmentControlR45(actualShield));}
    @Override public boolean issueMissionAtStation(NervArmamentStationEntity station,EvaUnit01Entity eva,LivingEntity pilot)
    {return (Object)station instanceof CargoRackAccess rack&&rack.issueTvMissionEquipmentR45(pilot,eva);}
    @Override public boolean cannonReady(EvaUnit01Entity eva)
    {
        return eva instanceof CannonAccess&&TvMissionEquipmentR45.cannonAuthorized(eva)
                &&(eva.getArmamentMask()&(1<<EvaUnit01Entity.WEAPON_CANNON))!=0
                &&eva.getWeapon()==EvaUnit01Entity.WEAPON_CANNON;
    }
    @Override public boolean rangesReady(EvaUnit01Entity eva,double metres)
    {return Double.isFinite(metres)&&(Object)eva instanceof CannonAccess cannon&&cannon.effectiveCannonRangeR45()>=metres;}
    @Override public boolean shieldEquipped(EvaUnit01Entity eva)
    {return shield!=null&&TvMissionEquipmentR45.shieldAuthorized(eva)&&shield.equipped(eva);}
    @Override public boolean shieldRayIntersects(EvaUnit01Entity eva,Vec3 from,Vec3 to)
    {return shieldBeamContact(eva,from,to).isPresent();}
    @Override public java.util.Optional<Vec3> shieldBeamContact(EvaUnit01Entity eva,Vec3 from,Vec3 to)
    {
        if(!shieldEquipped(eva)||!TvMissionEquipmentR45.operational(eva)||!finiteR45(from)||!finiteR45(to)
                ||!shield.intersects(eva,from,to))return java.util.Optional.empty();
        Vec3 segment=to.subtract(from);double length=segment.lengthSqr();
        if(length<=1e-12)return java.util.Optional.empty();
        return shield.firstIntersection(eva,from,to).filter(point->{
            if(!finiteR45(point))return false;
            double t=point.subtract(from).dot(segment)/length;
            return t>=0&&t<=1&&point.distanceToSqr(from.add(segment.scale(t)))<=1e-8;
        });
    }
    private static boolean finiteR45(Vec3 point)
    {return point!=null&&Double.isFinite(point.x)&&Double.isFinite(point.y)&&Double.isFinite(point.z);}
    @Override public boolean cannonInput(EvaUnit01Entity eva,TrainingPilotEntity pilot,Vec3 aim,boolean hold,boolean release)
    {return (Object)eva instanceof CannonAccess cannon&&cannon.missionCannonInputR45(pilot,aim,hold,release);}
    @Override public boolean shieldInput(EvaUnit01Entity eva,TrainingPilotEntity pilot,boolean brace)
    {
        if(shield==null||pilot==null||eva.getPilotEntity()!=pilot)return false;
        return shield.input(eva,pilot,brace&&TvMissionEquipmentR45.operational(eva)&&shieldEquipped(eva));
    }
}

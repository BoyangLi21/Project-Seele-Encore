package com.projectseele.world;

import com.google.gson.JsonObject;
import com.projectseele.entity.NervCarrierPlatformEntity;
import com.projectseele.world.NervRouteDirectoryR52.*;
import java.io.IOException;
import java.util.*;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.phys.Vec3;

/** A rail is the selected steel source on one actual Root path. Native cells
 * are its finite foundations, never a substitute track or a collision waiver. */
public final class NervMechanicalRailBindingR52 {
    public enum Kind { FIXED_FOOT_GUIDE, FOOT_TURN_STATION, LEGACY_RUNNING_HEAD, UPRIGHT_CAPTURED_GUIDEWAY }
    public record Spec(Kind kind,String leg,String sourceSha,String guideSha,UUID controller,Double foundationTop) {
        public Spec {
            if(kind==null||leg==null||!leg.matches("[A-Za-z0-9_./:-]{1,160}")||sourceSha==null||!sourceSha.matches("[0-9a-f]{64}")||guideSha==null||!guideSha.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("Explicit typed mechanical rail source and path required");
            if((kind==Kind.FIXED_FOOT_GUIDE||kind==Kind.UPRIGHT_CAPTURED_GUIDEWAY)&&(controller!=null||foundationTop!=null)||kind!=Kind.FIXED_FOOT_GUIDE&&kind!=Kind.UPRIGHT_CAPTURED_GUIDEWAY&&controller==null||kind==Kind.FOOT_TURN_STATION&&(foundationTop==null||!Double.isFinite(foundationTop))||kind==Kind.LEGACY_RUNNING_HEAD&&foundationTop!=null)throw new IllegalArgumentException("Mechanical rail family/controller/foundation contract differs");
        }
    }

    public static int variant(NervRouteDirectoryR52 d,String leg) {
        int found=-1;
        for(var route:d.routes().values())if(route.legs().contains(leg)) {
            if(found>=0&&found!=route.variant())throw new IllegalArgumentException("Mechanical rail path crosses original variants");
            found=route.variant();
        }
        if(found<0)throw new IllegalArgumentException("Mechanical rail path has no actual Root route");
        return found;
    }
    public static Spec parse(JsonObject row,String resource,NervRouteDirectoryR52 d,List<NervRouteNativeR52.Cell> cells) {
        var allowed=Set.of("kind","leg","source_sha256","guide_source_sha256","controller_uuid","foundation_top_m","floor_overlay_sha256");
        if(!allowed.containsAll(row.keySet()))throw new IllegalArgumentException("Unknown mechanical rail source field");
        var s=new Spec(Kind.valueOf(row.get("kind").getAsString()),row.get("leg").getAsString(),row.get("source_sha256").getAsString(),row.get("guide_source_sha256").getAsString(),row.has("controller_uuid")&&!row.get("controller_uuid").isJsonNull()?UUID.fromString(row.get("controller_uuid").getAsString()):null,row.has("foundation_top_m")&&!row.get("foundation_top_m").isJsonNull()?row.get("foundation_top_m").getAsDouble():null);
        boolean continuous=d.routes().values().stream().anyMatch(r->r.continuousUpright()&&r.legs().contains(s.leg()));
        if(row.has("floor_overlay_sha256")) {
            if(s.kind()!=Kind.LEGACY_RUNNING_HEAD||row.get("floor_overlay_sha256").isJsonNull()||!NervLegacyCarrierRideR52.FLOOR_OVERLAY_SHA.equals(row.get("floor_overlay_sha256").getAsString()))throw new IllegalArgumentException("Exact independent original floor overlay belongs only to a legacy running head");
        } else if(continuous&&s.kind()==Kind.LEGACY_RUNNING_HEAD)throw new IllegalArgumentException("Continuous original running head requires its actual floor overlay source");
        var leg=d.leg(s.leg());
        if(leg==null||s.leg().endsWith("/reverse")||!leg.rails().equals(List.of(resource)))throw new IllegalArgumentException("Unique canonical mechanical rail path/resource required");
        var uses=new HashSet<String>();
        for(var route:d.routes().values())for(String id:route.legs())if(d.leg(id).rails().contains(resource))uses.add(id);
        if(!uses.equals(Set.of(s.leg(),s.leg()+"/reverse")))throw new IllegalArgumentException("Mechanical rail must bind its exact forward/reverse pair");
        variant(d,s.leg());
        if(!s.guideSha().equals(s.kind()==Kind.UPRIGHT_CAPTURED_GUIDEWAY?NervOuterCarrierGuideR52.SOURCE_SHA:NervFootGuideRigR52.SOURCE_SHA))throw new IllegalArgumentException("Mechanical rail guide source differs");
        var positions=new HashSet<BlockPos>();
        for(var c:cells)if(!positions.add(c.position())||c.state().isBlank()||Set.of("minecraft:air","minecraft:cave_air","minecraft:void_air").contains(c.state().split("\\[")[0]))throw new IllegalArgumentException("Unique real mechanical rail foundation states required; air is not a rail");
        if(cells.isEmpty())throw new IllegalArgumentException("Actual finite mechanical rail foundations required");
        try {
            switch(s.kind()) {
                case UPRIGHT_CAPTURED_GUIDEWAY -> {
                    if(leg.centreCurve()==null||!s.sourceSha().equals(NervUprightGuidewayR52.sourceSha256())||!NervUprightGuidewayR52.matchesDirectory(d))throw new IllegalArgumentException("Actual selected continuous upright steel/Root curve required");
                    var expected=new HashMap<BlockPos,String>();for(var a:NervUprightGuidewayR52.anchors())if(a.leg().equals(s.leg())){var prior=expected.putIfAbsent(a.at(),a.state());if(prior!=null&&!prior.equals(a.state()))throw new IllegalArgumentException("Upright native supports disagree");}
                    if(!positions.equals(expected.keySet())||cells.stream().anyMatch(c->!c.state().equals(expected.get(c.position()))))throw new IllegalArgumentException("Upright native foundations differ from actual source");
                }
                case FIXED_FOOT_GUIDE -> {
                    if(!s.sourceSha().equals(NervFixedFootGuidesR52.SOURCE_SHA)||s.controller()!=null||s.foundationTop()!=null||!NervFixedFootGuidesR52.matchesDirectory(d))throw new IllegalArgumentException("Selected fixed guide source/Root directory required");
                    var path=NervFixedFootGuidesR52.paths().stream().filter(p->p.id().equals(s.leg())&&p.rails().equals(List.of(resource))).findFirst().orElseThrow(()->new IllegalArgumentException("No actual fixed guide path for rail"));
                    var actual=new HashMap<BlockPos,String>();for(var a:NervFixedFootGuidesR52.anchors())if(a.path().equals(path.id()))actual.put(a.at(),a.state());
                    if(!positions.equals(actual.keySet())||cells.stream().anyMatch(c->!c.state().equals(actual.get(c.position()))))throw new IllegalArgumentException("Fixed rail foundations differ from actual source anchors");
                }
                case FOOT_TURN_STATION -> {
                    if(leg.motion()!=Motion.FOOT_BEARING_TURN||!s.sourceSha().equals(NervFootGuideDockR52.SOURCE_SHA)||s.foundationTop()==null||!Double.isFinite(s.foundationTop())||!NervFootGuideStationR52.proposedIdentityR52(d.epoch(),s.leg()).equals(s.controller()))throw new IllegalArgumentException("Actual canonical turn station identity/source/foundation required");
                    if(!positions.equals(stationCells(stationSpec(d,s))))throw new IllegalArgumentException("Turn rail foundations differ from finite source feet");
                }
                case LEGACY_RUNNING_HEAD -> {
                    if((leg.motion()!=Motion.ORIGINAL_UPRIGHT_TRANSFER&&leg.motion()!=Motion.TRACKED_BANK_TRANSFER)||!s.sourceSha().equals(NervLegacyCarrierRideR52.SOURCE_SHA)||s.controller()==null||s.foundationTop()!=null)throw new IllegalArgumentException("Actual original running-head source/controller required");
                    // Loading verifies the exact selected triangles; it does not enable them.
                    if(NervLegacyCarrierRideR52.fixedPartsR52().isEmpty())throw new IllegalArgumentException("Actual running-head steel source is empty");
                    var binding=NervOriginalCarrierR52.nominalBinding(variant(d,s.leg()));
                    // This identifies the steel line at the actual Root datum.
                    // Four shoe contacts, including fore/aft end overhang, are
                    // a separate private carrying proof on every motion step.
                    for(int i=0;i<=16;i++){var root=d.sample(leg,i/16D,binding).evaRoot();for(int side:new int[]{-1,1}){var p=root.transformPoint(new Vec3(side*6,-2.2,0));var head=NervLegacyCarrierRideR52.actualHeadR52(p.x,p.z);if(head==null||p.y-head.point().y<-.0002||p.y-head.point().y>NervLegacyCarrierRideR52.MAX_DROP+.0002)throw new IllegalArgumentException("Root legacy path leaves the actual selected head line: leg="+s.leg()+" sample="+i+" root="+root);}}
                }
            }
        } catch(IOException unavailable) {throw new IllegalArgumentException("Mechanical rail source unavailable",unavailable);}
        return s;
    }
    public static NervFootGuideDockR52.Spec stationSpec(NervRouteDirectoryR52 d,Spec s)throws IOException {
        var leg=d.leg(s.leg());Vec3 incoming=null,outgoing=null;
        for(var route:d.routes().values()){int index=route.legs().indexOf(s.leg());if(index<1||index+1>=route.legs().size())continue;var a=NervFixedFootGuidesR52.up(d,d.leg(route.legs().get(index-1)));var b=NervFixedFootGuidesR52.up(d,d.leg(route.legs().get(index+1)));if(a==null||b==null)continue;if(incoming!=null&&(incoming.distanceTo(a)>1e-8||outgoing.distanceTo(b)>1e-8))throw new IllegalArgumentException("Ambiguous mechanical turn guide axes");incoming=a;outgoing=b;}
        if(incoming==null)throw new IllegalArgumentException("Actual incoming/outgoing source guides required");
        return new NervFootGuideDockR52.Spec(d,leg,NervOriginalCarrierR52.nominalBinding(variant(d,s.leg())),incoming,outgoing,s.foundationTop());
    }
    public static Set<BlockPos> stationCells(NervFootGuideDockR52.Spec spec)throws IOException {
        var cells=new HashSet<BlockPos>();for(var f:NervFootGuideDockR52.feet(spec)){var p=f.centre();int y=(int)Math.floor(p.y-.001);for(int x=(int)Math.floor(p.x-f.halfX()+1e-7);x<=Math.floor(p.x+f.halfX()-1e-7);x++)for(int z=(int)Math.floor(p.z-f.halfZ()+1e-7);z<=Math.floor(p.z+f.halfZ()-1e-7);z++)cells.add(new BlockPos(x,y,z));}return Set.copyOf(cells);
    }
    /** Readiness does not imply admission to move: all existing world/actor
     * triangle sweeps and resource leases remain mandatory. */
    public static boolean ready(ServerLevel l,NervRouteDirectoryR52 d,Spec s) {
        try {
            if(!s.guideSha().equals(s.kind()==Kind.UPRIGHT_CAPTURED_GUIDEWAY?NervOuterCarrierGuideR52.SOURCE_SHA:NervFootGuideRigR52.SOURCE_SHA))return false;
            return switch(s.kind()) {
                case UPRIGHT_CAPTURED_GUIDEWAY -> s.sourceSha().equals(NervUprightGuidewayR52.sourceSha256())&&NervUprightGuidewayR52.enabledForDirectoryR52(l,d)&&NervUprightGuidewayR52.matchesDirectory(d)&&NervUprightGuidewayR52.pathAnchorsBearR52(l,s.leg());
                case FIXED_FOOT_GUIDE -> s.sourceSha().equals(NervFixedFootGuidesR52.SOURCE_SHA)&&NervFixedFootGuidesR52.enabledForDirectoryR52(l,d)&&NervFixedFootGuidesR52.matchesDirectory(d)&&NervFixedFootGuidesR52.pathAnchorsBearR52(l,s.leg());
                case FOOT_TURN_STATION -> {var spec=stationSpec(d,s);var actor=NervFootGuideStationR52.controller(l,spec);yield s.sourceSha().equals(NervFootGuideDockR52.SOURCE_SHA)&&actor!=null&&actor.isAlive()&&actor.getUUID().equals(s.controller())&&NervFootGuideStationR52.finiteFeetBear(l,spec);}
                case LEGACY_RUNNING_HEAD -> s.sourceSha().equals(NervLegacyCarrierRideR52.SOURCE_SHA)&&(NervFixedFootGuidesR52.enabledForDirectoryR52(l,d)||NervUprightGuidewayR52.enabledForDirectoryR52(l,d))&&l.getEntity(s.controller()) instanceof NervCarrierPlatformEntity g&&g.isAlive()&&g.isRestraintGantry()&&g.hasDeclaredMachineFrameR52()&&g.lowerFrameDeclaredR52()&&g.declaredServiceFootDriveR52()!=null&&g.getUnitVariant()==variant(d,s.leg());
            };
        } catch(IOException|IllegalArgumentException|IllegalStateException invalid) {return false;}
    }
    public static String diagnostic(ServerLevel l,NervRouteDirectoryR52 d,Spec s,List<NervRouteNativeR52.Cell> foundations) {
        for(var c:foundations){var p=c.position();if(l.getChunkSource().getChunkNow(p.getX()>>4,p.getZ()>>4)==null)return "leg="+s.leg()+" foundation="+p.toShortString()+" expected="+c.state()+" current=UNLOADED";String actual=net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(l.getBlockState(p));if(!actual.equals(c.state()))return "leg="+s.leg()+" foundation="+p.toShortString()+" expected="+c.state()+" current="+actual;}
        if(s.controller()!=null){var actor=l.getEntity(s.controller());if(actor==null)return "leg="+s.leg()+" source="+s.sourceSha()+" missing_controller_uuid="+s.controller();if(!(actor instanceof NervCarrierPlatformEntity machine))return "leg="+s.leg()+" expected_controller="+s.controller()+" actual_type="+actor.getType()+" actual_position="+actor.position();if(s.kind()==Kind.FOOT_TURN_STATION){try{return "leg="+s.leg()+" controller="+s.controller()+" source="+s.sourceSha()+" current="+NervFootGuideStationR52.rawState(machine)+" finite_foot="+NervFootGuideStationR52.firstMissingFootR52(l,stationSpec(d,s));}catch(IOException|RuntimeException invalid){return "leg="+s.leg()+" station_source_unavailable="+invalid;}}return "leg="+s.leg()+" controller="+s.controller()+" actual_frame="+RigidTransform.of(machine.position(),machine.declaredMachineRotationR52())+" actual_drive="+machine.declaredServiceFootDriveR52()+" expected_source="+s.sourceSha()+" epoch="+machine.getPersistentData().getLong("MachineEpochR52")+" directory="+machine.getPersistentData().getString("MachineDirectoryR52");}
        if(s.kind()==Kind.UPRIGHT_CAPTURED_GUIDEWAY)return "leg="+s.leg()+" source="+s.sourceSha()+" directory_enabled="+NervUprightGuidewayR52.enabledForDirectoryR52(l,d)+" geometry_matches="+NervUprightGuidewayR52.matchesDirectory(d)+" native_bearing="+NervUprightGuidewayR52.pathAnchorsBearR52(l,s.leg());
        try{return "leg="+s.leg()+" source="+s.sourceSha()+" directory_enabled="+NervFixedFootGuidesR52.enabledForDirectoryR52(l,d)+" directory_matches="+NervFixedFootGuidesR52.matchesDirectory(d)+" finite_path_anchors="+NervFixedFootGuidesR52.pathAnchorsBearR52(l,s.leg());}catch(IOException|RuntimeException invalid){return "leg="+s.leg()+" fixed_source_unavailable="+invalid;}
    }
    private NervMechanicalRailBindingR52(){}
}

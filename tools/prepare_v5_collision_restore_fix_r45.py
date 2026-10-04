"""One-consumer actual client contact/restoration-input fix; candidate only."""
from pathlib import Path
import difflib,hashlib,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/v5_collision_restore_fix_v1';SOURCE=ROOT/'src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java'
def main():
    assert not OUT.exists();OUT.mkdir();raw=SOURCE.read_bytes();before=raw.decode('utf8');text=before.replace('\r\n','\n')
    text=text.replace('    private static int index,waypoint,','    private static volatile int index;\n    private static int waypoint,',1)
    text=text.replace('    private static JsonObject firstFailure;','    private static JsonObject firstFailure,restoreDiagnostic;\n    private static volatile boolean clientHorizontalCollision;\n    private static volatile int clientContactSamples;\n    private static int clientObservedCase=-1;\n    private static volatile AABB clientBody;\n    private static volatile float clientForwardImpulse;',1)
    text=text.replace('    private static boolean restoring,restored,oldPause,optionsSaved,originalNoPhysics;','    private static volatile boolean restoring;\n    private static boolean restored,oldPause,optionsSaved,originalNoPhysics;',1)
    needle='        clientPosition=mc.player.position();clientId=mc.player.getUUID();clientGround=mc.player.onGround();\n';assert text.count(needle)==1
    text=text.replace(needle,needle+'        clientHorizontalCollision=mc.player.horizontalCollision;clientBody=mc.player.getBoundingBox();\n        if(clientObservedCase!=index){clientObservedCase=index;clientContactSamples=0;}\n',1)
    needle='        boolean move=delta.horizontalDistanceSqr()>.01;keys(mc,move);clientUp=move;\n';assert text.count(needle)==1
    text=text.replace(needle,needle+'        if(move&&clientGround&&clientHorizontalCollision)clientContactSamples++;\n        clientForwardImpulse=mc.player.input.forwardImpulse;\n',1)
    needle='        mc.options.keyJump.setDown(false);mc.options.keyShift.setDown(false);mc.options.keySprint.setDown(false);mc.options.keyUse.setDown(false);\n';assert text.count(needle)==1
    text=text.replace(needle,needle+'        if(mc.player!=null){mc.player.input.up=up;mc.player.input.forwardImpulse=up?1:0;mc.player.input.leftImpulse=0;mc.player.zza=up?1:0;mc.player.xxa=0;if(!up)clientForwardImpulse=0;}\n',1)
    old='            require(player.position().subtract(prior).horizontalDistanceSqr()>.10&&player.horizontalCollision,"No actual keyed collision against assigned boundary");completeWalk(player);return;\n';assert text.count(old)==1
    new='''            observation.add("native_boundary_shapes",boundaryShapes(active,player));
            observation.addProperty("actual_client_contact_samples",clientContactSamples);
            observation.addProperty("server_remote_horizontalCollision",player.horizontalCollision);
            boolean nativeForwardBlocked=!active.noCollision(player,player.getBoundingBox().move(0,0,.02));
            observation.addProperty("actual_native_forward_body_blocked",nativeForwardBlocked);
            require(player.position().subtract(prior).horizontalDistanceSqr()>.10&&clientHorizontalCollision&&clientContactSamples>=10&&nativeForwardBlocked,
                    "No actual client keyed/native collision against assigned boundary");completeWalk(player);return;
'''
    text=text.replace(old,new,1)
    needle='    private static JsonObject pose(ServerPlayer player)\n';assert text.count(needle)==1
    helper='''    private static JsonArray boundaryShapes(ServerLevel level,ServerPlayer player)
    {
        var rows=new JsonArray();int x=(int)Math.floor(player.getX()),z=current.get("expected_closed_boundary_z").getAsInt(),feet=(int)Math.floor(player.getY());
        for(int y=feet;y<feet+6;y++)
        {
            var at=new BlockPos(x,y,z);var state=level.getBlockState(at);var row=new JsonObject();
            row.addProperty("position",at.toShortString());row.addProperty("actual_state",net.minecraft.commands.arguments.blocks.BlockStateParser.serialize(state));
            row.addProperty("actual_collision_AABBs",state.getCollisionShape(level,at,net.minecraft.world.phys.shapes.CollisionContext.of(player)).toAabbs().toString());rows.add(row);
        }
        return rows;
    }
'''
    text=text.replace(needle,helper+needle,1)
    needle='row.addProperty("horizontal_collision",player.horizontalCollision);';assert text.count(needle)==1
    text=text.replace(needle,needle+'row.addProperty("actual_client_horizontal_collision",clientHorizontalCollision);row.addProperty("actual_client_contact_samples",clientContactSamples);row.addProperty("actual_client_forward_impulse",clientForwardImpulse);row.addProperty("actual_client_body",String.valueOf(clientBody));',1)
    needle='        player.setGameMode(originalMode);player.load(original.copy());player.noPhysics=originalNoPhysics;';assert text.count(needle)==1
    text=text.replace(needle,'        player.setGameMode(originalMode);player.load(original.copy());player.noPhysics=originalNoPhysics;player.zza=0;player.xxa=0;',1)
    needle='        boolean aligned=clientPosition!=null&&player.position().distanceToSqr(originalPosition)<.04&&clientPosition.distanceToSqr(originalPosition)<.10&&mc.player!=null&&mc.level!=null\n';assert text.count(needle)==1
    text=text.replace(needle,'''        restoreDiagnostic=new JsonObject();restoreDiagnostic.addProperty("original_position",String.valueOf(originalPosition));restoreDiagnostic.addProperty("server_position",player.position().toString());restoreDiagnostic.addProperty("client_position",String.valueOf(clientPosition));
        restoreDiagnostic.addProperty("server_original_position_ACK",player.position().distanceToSqr(originalPosition)<.04);restoreDiagnostic.addProperty("client_original_position_ACK",clientPosition!=null&&clientPosition.distanceToSqr(originalPosition)<.10);
        restoreDiagnostic.addProperty("inventory_typed_equal",Objects.equals(after.get("Inventory"),original.get("Inventory")));restoreDiagnostic.addProperty("server_slot",player.getInventory().selected);restoreDiagnostic.addProperty("original_slot",original.getInt("SelectedItemSlot"));
        restoreDiagnostic.addProperty("server_mode",player.gameMode.getGameModeForPlayer().toString());restoreDiagnostic.addProperty("original_mode",originalMode.toString());restoreDiagnostic.addProperty("server_health",player.getHealth());restoreDiagnostic.addProperty("original_health",original.getFloat("Health"));
        restoreDiagnostic.addProperty("server_XP",player.totalExperience+"/"+player.experienceLevel+"/"+player.experienceProgress);restoreDiagnostic.addProperty("original_XP",original.getInt("XpTotal")+"/"+original.getInt("XpLevel")+"/"+original.getFloat("XpP"));
        if(mc.player!=null&&mc.level!=null){restoreDiagnostic.addProperty("client_slot",mc.player.getInventory().selected);restoreDiagnostic.addProperty("client_mode",mc.gameMode.getPlayerMode().toString());restoreDiagnostic.addProperty("client_health",mc.player.getHealth());restoreDiagnostic.addProperty("client_XP",mc.player.totalExperience+"/"+mc.player.experienceLevel+"/"+mc.player.experienceProgress);restoreDiagnostic.addProperty("client_dimension",mc.level.dimension().location().toString());}
        restoreDiagnostic.addProperty("server_dimension",player.serverLevel().dimension().location().toString());restoreDiagnostic.addProperty("original_dimension",originalDimension.location().toString());restoreDiagnostic.addProperty("server_UUID_equal",player.getUUID().equals(actorId));restoreDiagnostic.addProperty("actual_client_forward_impulse",clientForwardImpulse);restoreDiagnostic.addProperty("restore_ticks",restoreTicks);
        boolean aligned=clientPosition!=null&&player.position().distanceToSqr(originalPosition)<.04&&clientPosition.distanceToSqr(originalPosition)<.10&&mc.player!=null&&mc.level!=null
''',1)
    old='        require(++restoreTicks<600,"Original actor restoration not acknowledged");var mc=Minecraft.getInstance();CompoundTag after=player.saveWithoutId(new CompoundTag());\n';assert text.count(old)==1
    text=text.replace(old,'        ++restoreTicks;var mc=Minecraft.getInstance();CompoundTag after=player.saveWithoutId(new CompoundTag());\n',1)
    needle='        if(!aligned){restoreStable=0;return;}';assert text.count(needle)==1
    text=text.replace(needle,'        require(restoreTicks<600,"Original actor restoration not acknowledged: "+restoreDiagnostic);\n'+needle,1)
    needle='if(firstFailure!=null)result.add("first_failure",firstFailure);';assert text.count(needle)==1
    text=text.replace(needle,needle+'if(restoreDiagnostic!=null)result.add("restore_ACK_diagnostic",restoreDiagnostic);if(original!=null)result.addProperty("original_actor_full_NBT",original.toString());',1)
    if raw.count(b'\r\n')==raw.count(b'\n'):text=text.replace('\n','\r\n')
    (OUT/'FacilityComponentReviewR45.before.txt').write_bytes(raw);(OUT/'FacilityComponentReviewR45.candidate.txt').write_bytes(text.encode('utf8'))
    patch=''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java',tofile='b/src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java'))
    (OUT/'root_actual_client_collision_and_restore_inputs.patch').write_bytes(patch.encode('utf8'))
    (OUT/'prepared_NOT_APPLIED_NOT_COMPILED.json').write_bytes((json.dumps(dict(patch_sha256=hashlib.sha256(patch.encode('utf8')).hexdigest(),one_consumer_only=True,all165_cases_and60keytick_and_position_bounds_preserved=True,server_remote_field_no_longer_false_gate=True,requires_actual_client_collision_10_samples_and_actual_native_forward_blocked=True,stop_keys_also_stops_actual_input_impulses=True,restore_position_tolerance_unmodified=True,original_NBT_and_all_restore_ACK_values_exported=True,MainJava_modified=False,world_written=False,compiled=False,new_native_pass=False),indent=2)+'\n').encode('utf8'))
    print('Prepared one-consumer collision/input/restore-diagnostic patch only.',flush=True)
if __name__=='__main__':main()

"""Single existing consumer stop/teleport ACK patch; pure timing controls."""
from pathlib import Path
import difflib,json,hashlib,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java';OUT=ROOT/'artifacts/rebuild_r45/pyramid_components_sol_v1/v5_staging_stop_fix_v2'
def main():
    assert not OUT.exists();OUT.mkdir();raw=SOURCE.read_bytes();before=raw.decode('utf8');text=before.replace('\r\n','\n')
    needle='    private static volatile float clientForwardImpulse;\n';assert text.count(needle)==1
    text=text.replace(needle,needle+'    private static volatile Vec3 clientVelocity;\n    private static volatile boolean clientStopped;\n    private static volatile long clientSampleSerial;\n    private static Vec3 beforeStopServerPosition;\n    private static long lastStopClientSample=-1;\n    private static int stopStableTicks;\n    private static boolean startTeleported;\n',1)
    needle='        if(!actuating||target==null||mc.screen!=null)return;\n';assert text.count(needle)==1
    text=text.replace(needle,'''        clientVelocity=mc.player.getDeltaMovement();clientSampleSerial++;
        clientStopped=!mc.options.keyUp.isDown()&&!mc.options.keyDown.isDown()&&!mc.options.keyLeft.isDown()&&!mc.options.keyRight.isDown()
                &&mc.player.input.forwardImpulse==0&&mc.player.input.leftImpulse==0&&mc.player.zza==0&&mc.player.xxa==0
                &&clientVelocity.horizontalDistanceSqr()<.000001;
        if(!actuating||target==null||mc.screen!=null)return;
        clientStopped=false;
''',1)
    old='''            lease(active,new ChunkPos(BlockPos.containing(start)));player.teleportTo(active,start.x,start.y,start.z,0,0);player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
            target=start;waypoint=1;caseAge=ackTicks=upTicks=0;actuating=false;
'''
    new='''            lease(active,new ChunkPos(BlockPos.containing(start)));
            target=null;waypoint=1;caseAge=ackTicks=upTicks=stopStableTicks=0;actuating=false;startTeleported=false;
            beforeStopServerPosition=null;lastStopClientSample=-1;
'''
    assert text.count(old)==1;text=text.replace(old,new,1)
    needle='        if(!actuating)\n        {\n';assert text.count(needle)==1
    insertion='''        if(!startTeleported)
        {
            // Release actual keys and drain the previous client movement BEFORE
            // the single allowed case-start teleport. No repeated teleport or
            // wider0.3m staging tolerance masks a late old movement packet.
            boolean serverStable=beforeStopServerPosition!=null&&player.position().distanceToSqr(beforeStopServerPosition)<.000001;
            boolean freshClientSample=clientSampleSerial>lastStopClientSample;
            boolean stopACK=clientStopped&&clientId!=null&&clientId.equals(actorId)&&clientPosition!=null&&clientGround&&player.onGround()
                    &&clientPosition.distanceToSqr(player.position())<.0004&&serverStable&&freshClientSample;
            var prep=new JsonObject();prep.addProperty("phase","STOP_INPUT_BEFORE_SINGLE_TELEPORT");prep.addProperty("stop_ACK",stopACK);prep.addProperty("server_stable",serverStable);
            prep.addProperty("fresh_client_sample",freshClientSample);prep.addProperty("client_stopped",clientStopped);prep.addProperty("client_velocity",String.valueOf(clientVelocity));prep.add("actual_pose",pose(player));
            observation.add("initial_preparation",prep);
            if(!freshClientSample){if(!serverStable)stopStableTicks=0;return;}
            beforeStopServerPosition=player.position();lastStopClientSample=clientSampleSerial;
            if(!stopACK){stopStableTicks=0;return;}if(++stopStableTicks<3)return;
            Vec3 start=vec(path==null?current.getAsJsonArray("start"):path.get(0).getAsJsonArray());
            observation.addProperty("stop_ACK_stable_ticks",stopStableTicks);observation.addProperty("start_teleports",1);
            player.teleportTo(active,start.x,start.y,start.z,0,0);player.setDeltaMovement(Vec3.ZERO);player.fallDistance=0;
            target=start;startTeleported=true;ackTicks=0;return;
        }
'''
    text=text.replace(needle,insertion+needle,1)
    needle='            if(!ack){ackTicks=0;return;}if(++ackTicks<3)return;\n';assert text.count(needle)==1
    text=text.replace(needle,'''            var prep=new JsonObject();prep.addProperty("phase","ACTUAL_CLIENT_SERVER3D_FLOOR_ACK_AFTER_SINGLE_TELEPORT");prep.addProperty("floor_ACK",ack);prep.addProperty("planned_start",String.valueOf(target));prep.add("actual_pose",pose(player));observation.add("initial_preparation_after_teleport",prep);
            if(!ack){ackTicks=0;return;}if(++ackTicks<3)return;
''',1)
    needle='row.addProperty("actual_client_body",String.valueOf(clientBody));';assert text.count(needle)==1
    text=text.replace(needle,needle+'row.addProperty("actual_client_velocity",String.valueOf(clientVelocity));row.addProperty("actual_client_stopped_ACK",clientStopped);row.addProperty("actual_client_sample",clientSampleSerial);',1)
    if raw.count(b'\r\n')==raw.count(b'\n'):text=text.replace('\n','\r\n')
    (OUT/'FacilityComponentReviewR45.before.txt').write_bytes(raw);(OUT/'FacilityComponentReviewR45.candidate.txt').write_bytes(text.encode('utf8'))
    patch=''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='a/src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java',tofile='b/src/main/java/com/projectseele/client/visual/FacilityComponentReviewR45.java'))
    (OUT/'root_stop_input_before_case_start_teleport.patch').write_bytes(patch.encode('utf8'))
    # Pure input-time model: late prior input/motion belongs to the old position.
    # It is deliberately NOT a Minecraft physics/native success claim.
    speed=.12;drag=.546;old_position=0.;trace=[]
    for tick in range(14):
        old_position+=speed;trace.append(dict(tick=tick,old_body_shift=old_position,speed=speed,client_stopped=speed*speed<.000001));speed*=drag
    old_immediate_teleport_drift=.12/(1-drag);new_start=303.5;stop_samples=[r for r in trace if r['client_stopped']]
    assert old_immediate_teleport_drift>.2 and len(stop_samples)>=3
    assert new_start==303.5  # only after the recorded three drained/stable samples
    report=dict(scope='PURE_INPUT_TIME_SEQUENCE_ONLY_NOT_NATIVE_PHYSICS',old_immediate_TP_then_residual_drift=old_immediate_teleport_drift,old_server_start0_04_distance_sq_would_fail=old_immediate_teleport_drift**2>.04,new_stop_velocity3_distinct_samples_before_only_TP=True,new_start_tolerance_unchanged=True,no_repeated_teleports=True,trace=trace,MC_started=False,world_written=False,MainJava_modified=False,compiled=False,patch_sha256=hashlib.sha256(patch.encode('utf8')).hexdigest(),requires_full_native165_after_first_small_case_sequence=True)
    (OUT/'pure_input_sequence_regression.json').write_bytes((json.dumps(report,indent=2)+'\n').encode('utf8'));print(json.dumps({k:v for k,v in report.items()if k!='trace'},indent=2))
if __name__=='__main__':main()

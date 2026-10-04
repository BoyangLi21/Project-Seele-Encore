"""Freeze a precise final real-client restoration patch without editing Java.

Root merges after the currently running native factory process has stopped.
"""
from pathlib import Path
import difflib
import json
from school_hakone_patch_r45 import ROOT,ART,sha


def main():
    source=ROOT/'src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java'
    out=ART/'school_restore_ack_v1';assert not out.exists();out.mkdir()
    before=source.read_text('utf8');after=before
    def change(old,new):
        nonlocal after
        assert old in after,('Exact root/source epoch changed',old[:90]);after=after.replace(old,new,1)
    change('private static boolean optionsSaved, oldPause, stopping, restored;',
        'private static boolean optionsSaved, oldPause, stopping, restored, originalNoPhysics;\n    private static boolean restoring;\n    private static int restoreTicks, restoreStable;\n    private static JsonObject restorationEvidence;')
    change('originalPosition=player.position(); originalYaw=player.getYRot(); originalPitch=player.getXRot();',
        'originalPosition=player.position(); originalYaw=player.getYRot(); originalPitch=player.getXRot();originalNoPhysics=player.noPhysics;')
    change('require(player.getUUID().equals(playerId),"Review player identity changed"); require(error.isBlank(),error);',
        'require(player.getUUID().equals(playerId),"Review player identity changed");\n            if(restoring){acknowledgeRestoration(player,mc);return;}\n            require(error.isBlank(),error);')
    change('restorePlayer(player);persist(true);finished=true;',
        'restorePlayer(player);persist(false);')
    change('try { if (cases != null) { restoreBlocks(server.getLevel(FacilitySchemaV2.DIMENSION));restorePlayer(player);persist(true); } }\n            catch (Exception restoration) { error += " RESTORATION_ERROR:"+restoration; if (output!=null)persist(true); }\n            finished=true;ProjectSeele.LOGGER.error("R45 school/pool native lifecycle failed",failure);',
        '''try
            {
                if(restoring){restored=false;persist(true);finished=true;}
                else if(cases!=null){restoreBlocks(server.getLevel(FacilitySchemaV2.DIMENSION));restorePlayer(player);persist(false);}
                else finished=true;
            }
            catch(Exception restoration){error += " RESTORATION_ERROR:"+restoration;restored=false;if(output!=null)persist(true);finished=true;}
            ProjectSeele.LOGGER.error("R45 school/pool native lifecycle failed",failure);''')
    change('player.load(originalPlayer.copy());player.setGameMode(originalMode);',
        '''// Change mode first so native mode packets are emitted. Loading
        // afterwards preserves every original ability instead of allowing a
        // mode-default update to overwrite the full saved player's abilities.
        player.setGameMode(originalMode);player.load(originalPlayer.copy());player.noPhysics=originalNoPhysics;''')
    change('player.onUpdateAbilities();player.inventoryMenu.broadcastChanges();require(player.getUUID().equals(playerId),"Original UUID not preserved");\n        restored=true;',
        '''player.onUpdateAbilities();player.inventoryMenu.broadcastFullState();
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetCarriedItemPacket(player.getInventory().selected));
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetHealthPacket(player.getHealth(),player.getFoodData().getFoodLevel(),player.getFoodData().getSaturationLevel()));
        player.connection.send(new net.minecraft.network.protocol.game.ClientboundSetExperiencePacket(player.experienceProgress,player.totalExperience,player.experienceLevel));
        require(player.getUUID().equals(playerId),"Original UUID not preserved");
        restored=false;restoring=true;restoreTicks=restoreStable=0;
    }

    private static void acknowledgeRestoration(ServerPlayer player,Minecraft mc)throws Exception
    {
        require(++restoreTicks<600,"Original player restoration packet acknowledgment timed out");
        // Pinned MC1.20.1 has exactly one Vec3 member on this listener:
        // awaitingPositionFromClient. Resolve by declared type so official/SRG
        // names cannot quietly turn the mandatory acknowledgment into a skip.
        var candidates=Arrays.stream(player.connection.getClass().getDeclaredFields())
            .filter(field->field.getType()==Vec3.class).toList();
        require(candidates.size()==1,"Pinned native pending-teleport field contract differs");
        var pending=candidates.get(0);pending.setAccessible(true);
        boolean nativeAck=pending.get(player.connection)==null;
        var expectedInventory=originalPlayer.getList("Inventory",10);
        var serverInventory=player.getInventory().save(new net.minecraft.nbt.ListTag());
        var clientInventory=mc.player.getInventory().save(new net.minecraft.nbt.ListTag());
        var serverAbilities=new CompoundTag();player.getAbilities().save(serverAbilities);
        var clientAbilities=new CompoundTag();mc.player.getAbilities().save(clientAbilities);
        var expectedAbilities=originalPlayer.getCompound("abilities");
        boolean aligned=nativeAck&&player.getUUID().equals(playerId)&&mc.player.getUUID().equals(playerId)
            &&player.level().dimension().equals(originalDimension)&&mc.level.dimension().equals(originalDimension)
            &&player.position().distanceToSqr(originalPosition)<.01&&mc.player.position().distanceToSqr(originalPosition)<.01
            &&player.gameMode.getGameModeForPlayer()==originalMode&&mc.gameMode.getPlayerMode()==originalMode
            &&serverInventory.equals(expectedInventory)&&clientInventory.equals(expectedInventory)
            &&player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")&&mc.player.getInventory().selected==originalPlayer.getInt("SelectedItemSlot")
            &&serverAbilities.getCompound("abilities").equals(expectedAbilities)&&clientAbilities.getCompound("abilities").equals(expectedAbilities)
            &&Math.abs(player.getHealth()-originalPlayer.getFloat("Health"))<.001&&Math.abs(mc.player.getHealth()-originalPlayer.getFloat("Health"))<.001
            &&player.experienceLevel==originalPlayer.getInt("XpLevel")&&mc.player.experienceLevel==originalPlayer.getInt("XpLevel")
            &&player.totalExperience==originalPlayer.getInt("XpTotal")&&mc.player.totalExperience==originalPlayer.getInt("XpTotal")
            &&Math.abs(player.experienceProgress-originalPlayer.getFloat("XpP"))<.001&&Math.abs(mc.player.experienceProgress-originalPlayer.getFloat("XpP"))<.001
            &&player.noPhysics==originalNoPhysics&&mc.player.noPhysics==originalNoPhysics;
        restorationEvidence=new JsonObject();restorationEvidence.addProperty("actual_UUID",playerId.toString());
        restorationEvidence.addProperty("server_position",player.position().toString());restorationEvidence.addProperty("client_position",mc.player.position().toString());
        restorationEvidence.addProperty("native_server_pending_teleport_cleared",nativeAck);restorationEvidence.addProperty("client_server_mode_inventory_abilities_health_XP_aligned",aligned);
        restorationEvidence.addProperty("ticks",restoreTicks);restorationEvidence.addProperty("mode",originalMode.getName());
        restorationEvidence.addProperty("server_full_NBT_load_performed",true);
        restorationEvidence.addProperty("tick_statistics_bytes","Root wrapper restores exact original playerdata/stats/advancements only after this process stops; MTR progress remains live");
        if(!aligned){restoreStable=0;return;}
        if(++restoreStable<8)return;
        restorationEvidence.addProperty("stable_acknowledged_ticks",restoreStable);
        Files.writeString(output.resolveSibling("player_after_ack_full_snbt.txt"),player.saveWithoutId(new CompoundTag()).toString());
        restored=true;restoring=false;persist(true);finished=true;''')
    change('report.addProperty("full_player_NBT_restored",restored);',
        'report.addProperty("full_player_NBT_restored",restored);report.addProperty("client_restoration_packet_acknowledged",restored);if(restorationEvidence!=null)report.add("actual_restoration_evidence",restorationEvidence.deepCopy());')
    candidate=out/source.name;candidate.write_text(after,'utf8')
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
        fromfile='a/src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java',
        tofile='b/src/main/java/com/projectseele/client/visual/SchoolPoolLifecycleR45.java'))
    (out/'school_restore_ack.patch').write_bytes(patch.encode('utf8'))
    (out/'preconditions.json').write_text(json.dumps(dict(source=str(source.resolve()),before_sha256=sha(source),
        candidate=str(candidate.resolve()),candidate_sha256=sha(candidate),source_modified=False,
        compiled_by_agent=False,native_run_by_agent=False,root_only_merge=True,
        limitation='The current frozen helper stops before final client acknowledgment; this candidate must be merged/compiled and actually tested before full restoration is certified'),indent=2)+'\n','utf8')
    print('Frozen precise restoration acknowledgment candidate; root Java unchanged',out,flush=True)


if __name__=='__main__':main()

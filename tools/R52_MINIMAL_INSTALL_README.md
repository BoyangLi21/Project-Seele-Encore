本轮使用显式 `--scope 124`。Root 先生成最终 installed-intent bundle，再运行 `prepare_r52_runtime_deployment_candidate.py`，只把那份精确部署清单复制到 `D:/eva/artifacts/map_complete_20261013/WORLD`。工具不复制世界、不导入 QA 进度、不重置玩家或交通，也不替代发射／回库／空运完整验收。

本轮新增必填参数：`--baseline`、`--baseline-sha256`、`--root-plan`、`--root-plan-sha256`、`--original-identities`、`--original-identities-sha256`、`--server-release-sha256`、`--observer-dir`。原身份文件为 `{ "world": "当前世界绝对路径", "managed_geofront": { "原 UUID": { "type": "原实体类型", "dimension": "dimensions/projectseele/geofront" } } }`；本轮实际 678 项由这份明确 SHA 的完整表提供，不复用旧 680 项文件。41 门加原三组机构共 50 个控制器必须从最终 owner 和 directory 得到；有无炮库不能只改数量。

先运行 `compile_root_lifecycle_observers_r53.py --out <独立观察器目录>`，再把该目录传给 `--observer-dir`。编译只读反射观察器不启动或连接游戏。新观察器接受明确候选路径，仍拒绝写进任何原生世界，并按实际源哈希、原 UUID、完整设备 Spec／时钟 NBT 检查。

下面旧完整模式示例只说明调用方式。当前 124 应替换其世界／部署／输出路径，并加上上述显式授权参数和 `--scope 124`；不要重用旧实例路径或历史成功收据。

The existing successful dedicated template is `D:/eva/artifacts/rebuild_r49/native_session/original_npc_01/launch.json`. Its Forge 47.4.10 libraries are already absolute paths under the retained runtime-r25 library cache. The isolated small host reuses the existing dedicated mods/configuration and existing `eula=true`; only its Project SEELE JAR and portable runtime are the explicitly selected final inputs. Third-party JARs are hard-linked where possible, never modified. The host binds only loopback at an ephemeral port.

Run from `C:/Users/liboy/.codex/worktrees/r51-nonmap/eva`. Root supplies the final immutable JAR and both actual SHA256 values:

```powershell
python tools/run_r52_minimal_install_restart.py `
  --jar <final-immutable-jar-path> `
  --jar-sha256 <actual-final-jar-sha256> `
  --deployment D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate/DEPLOYMENT_PREPARATION.json `
  --deployment-sha256 <actual-final-deployment-json-sha256> `
  --world D:/eva/artifacts/r52_fresh_from_r51_20261009/WORLD_R52 `
  --runtime <final-selected-projectseele-local-maps-directory> `
  --out D:/eva/artifacts/r52_fresh_from_r51_20261009/runtime_directory/candidate/native_install_<unique-attempt> `
  --run
```

Omitting `--run` only prepares a fresh small host and an input receipt; it does not start Java or change World. Each invocation requires a new attempt directory so failure evidence is preserved. Stop other Java/build/game processes before the sole heavy server.

The only installation input is stdin console:

`execute in projectseele:geofront run nerv r52 install ROOT_ASSEMBLY_BUNDLE.json`

The executor waits for normal startup and reasonably retries while ticket loading/commissioning remains held. It requires the real accepted success text and exact selected directory fingerprint, then the existing read-only native lifecycle snapshot. Only after acceptance does it issue `save-all flush` and `stop`. After disk identity readback it cold starts the same World and same inputs once; automatic restoration must prove the same 64 UUIDs and persisted bundle authority. It compares all 42 doors' complete source/spec/raw/target/clock NBT, plus the fixed cannon geometry/cradle/aim/load/readiness and physical position. Native region readback must retain the managed GeoFront original 680 UUID/type/dimension identities and all 64 declared GeoFront controllers. The initial all-dimension inventory is retained separately; other-dimension identities and any differences are recorded, never treated as extra actors to remove or reset. Root measured 919 initially: GeoFront 680 plus overworld 239.

`INPUTS.json`, separate install/cold logs, submitted `COMMANDS.jsonl`, native lifecycle snapshots, persisted identity inventory, and `RESULT.json` remain under the candidate attempt. A missing success marker, state mismatch, source change, or incomplete normal stop is a failure. A still-live failed process is reported by PID and left for Root inspection; the executor never kills it, resets the World, or starts a second process to conceal failure. Full play acceptance remains `USER_TEST_PENDING`; two deferred battles are not promoted to PASS.

"""Prepare a private, read-only delivery plan from the actual R53 client.

This deliberately does not promote ready-client, copy a world, or execute the
old ready-to-client installer. Regenerate after the final normal Save and Quit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


CLIENT_TREES = (
    'mods', 'projectseele-local-maps', 'config', 'defaultconfigs',
    'resourcepacks', 'shaderpacks', 'licenses',
)
STATE_TREES = ('playerdata', 'advancements', 'stats', 'mtr')
WORLD_TREES = ('tables', 'r52', 'datapacks', 'serverconfig')
STATIC_REGIONS = ('r.-1.0.mca', 'r.0.0.mca', 'r.-1.-1.mca', 'r.0.-1.mca')
NAVIGATION = (
    'r53_personnel_walking_graph.json.gz', 'quality_walk_cases.json',
    'regional_plan.json', 'regional_states.json', 'regional_wayfinding.json',
    'local_lift_routes_r45.json.gz', 'local_nearest_lift_paths_r45.json.gz',
    'nearest_lift_paths_r44.json.gz', 'nerv_routes_r24.json.gz',
    'r45_school_hakone_navigation.json', 'ROOT_RUNTIME_DIRECTORY.json',
)


def bounded_files(root: Path):
    """Only used for explicitly selected small client trees, never the world."""
    if root.exists():
        for path in sorted(root.rglob('*')):
            if path.is_symlink():
                raise ValueError(f'Unexpected linked delivery input: {path}')
            if path.is_file():
                yield path


def file_record(path: Path, root: Path):
    stat = path.stat()
    return {'path': path.relative_to(root).as_posix(), 'bytes': stat.st_size}


def dimensions(world: Path):
    yield world
    for name in ('DIM-1', 'DIM1'):
        if (world / name).is_dir():
            yield world / name
    custom = world / 'dimensions'
    if custom.exists():
        for namespace in sorted(custom.iterdir()):
            if namespace.is_dir():
                yield from (p for p in sorted(namespace.iterdir()) if p.is_dir())


def write_launcher(output: Path, base: Path, java: Path, args: Path,
                   background_agent: Path):
    def ps(value):
        return "'" + str(value).replace("'", "''") + "'"

    # A local review launcher: its existing private @args is not republished.
    text = "\n".join((
        '# Local actual-client launcher. No ready-to-client synchronization.',
        "param([ValidateSet('Visible', 'BackgroundReview')][string]$Mode = 'Visible')",
        "$ErrorActionPreference = 'Stop'",
        f'$taskBase = {ps(base)}',
        f'$taskJava = {ps(java)}',
        f'$taskArgs = {ps(args)}',
        f'$taskAgent = {ps(background_agent)}',
        "$taskClient = Join-Path $taskBase 'client'",
        "$taskJar = Join-Path $taskClient 'mods/projectseele-0.1.0-all.jar'",
        'foreach ($taskInput in @($taskJava, $taskArgs, $taskJar)) {',
        "    if (-not (Test-Path -LiteralPath $taskInput -PathType Leaf)) { throw ('Missing actual input: ' + $taskInput) }",
        '}',
        '# Temporary exclusions for the two methods named by local native-crash reports.',
        "$taskArguments = @('-XX:CompileCommand=exclude,net/minecraft/world/level/BlockCollisions.m_186411_', '-XX:CompileCommand=exclude,com/google/gson/stream/JsonReader.peekNumber')",
        "$taskWindow = 'Normal'",
        "if ($Mode -eq 'BackgroundReview') {",
        "    if (-not (Test-Path -LiteralPath $taskAgent -PathType Leaf)) { throw 'Missing background review agent' }",
        "    $taskArguments += '-javaagent:' + $taskAgent + '=no-focus'",
        "    $taskWindow = 'Hidden'",
        '}',
        "$taskArguments += '@' + $taskArgs",
        '# Quote the actual paths for the Windows process command line.',
        '$taskQuoted = $taskArguments | ForEach-Object { \'"\' + $_ + \'"\' }',
        'Start-Process -FilePath $taskJava -ArgumentList $taskQuoted -WorkingDirectory $taskClient -WindowStyle $taskWindow -PassThru',
        '',
    ))
    output.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--generation-updates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--java', type=Path, required=True)
    parser.add_argument('--background-agent', type=Path, required=True)
    parser.add_argument('--args', type=Path)
    a = parser.parse_args()
    base = a.base.resolve()
    client = base / 'client'
    world = client / 'saves/SEELE_R53_WORLD'
    output = a.output.resolve()
    # The only writes are a new private plan directory outside actual/ready.
    for protected in (client, base / 'ready-client', base / 'ready-world'):
        if output == protected or protected in output.parents:
            raise ValueError('Plan output must not be inside actual or ready')
    if output.exists():
        raise FileExistsError(output)
    args = (a.args or base / 'r53-java17-native.args').resolve()
    required = [world / 'level.dat', client / 'mods/projectseele-0.1.0-all.jar',
                args, a.java, a.background_agent, a.generation_updates]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    generation = json.loads(a.generation_updates.read_text(encoding='utf-8'))
    recipes = [row['target_world_relative'] for row in generation['files']]
    if len(recipes) != 8 or len(set(recipes)) != 8:
        raise ValueError('The current apron installation declares exactly eight recipes')
    for relative in recipes:
        path = (world / relative).resolve()
        if world.resolve() not in path.parents or not path.is_file():
            raise ValueError(f'Invalid actual generation recipe: {relative}')

    client_files = [file_record(p, client) for name in CLIENT_TREES
                    for p in bounded_files(client / name)]
    for name in ('options.txt', 'patchouli_data.json'):
        if (client / name).is_file():
            client_files.append(file_record(client / name, client))
    world_root = [file_record(p, world) for p in sorted(world.iterdir())
                  if p.is_file() and p.name != 'session.lock']
    state_trees = [name for name in STATE_TREES if (world / name).exists()]
    saved_data_files = []
    journal_trees = []
    all_region_trees = []
    for dimension in dimensions(world):
        for name in ('entities', 'poi'):
            if (dimension / name).exists():
                state_trees.append((dimension / name).relative_to(world).as_posix())
        if (dimension / 'region').exists():
            all_region_trees.append((dimension / 'region').relative_to(world).as_posix())
        data = dimension / 'data'
        if not data.exists():
            continue
        for path in sorted(data.iterdir()):
            if path.is_file() and not path.name.startswith('DistantHorizons.sqlite'):
                saved_data_files.append(file_record(path, world))
            elif path.is_dir() and path.name != 'city_rigid_generation_r45':
                journal_trees.append(path.relative_to(world).as_posix())
    static_files = ['dimensions/projectseele/geofront/region/' + name for name in STATIC_REGIONS]
    for relative in static_files:
        if not (world / relative).is_file():
            raise FileNotFoundError(world / relative)
    nav = [name for name in NAVIGATION if (world / name).is_file()]
    receipts = [base / 'integration1023' / name / 'installation.json' for name in (
        'tray-backup-installed', 'upright-backup-installed', 'console-floor-backup-installed',
        'bank-front-backup-installed', 'bank-horizontal-backup-installed',
        'bank-curb-backup-installed', 'bank-curb-v2-backup-installed',
        'retired-bank23-seals-backup-installed', 'retired-underground-fronts-backup-installed')]
    receipts.append(base / 'integration1023/bank-curb-v3-install-receipt.json')
    receipts.append(base / 'integration1024/upper-carrier-installed/INSTALLED.json')
    plan = {
        'status': 'PREPARATION_ONLY_NOT_PROMOTED',
        'actual_client': str(client), 'actual_world': str(world),
        'source_checkout': str(Path(__file__).resolve().parents[1]),
        'source_policy': 'Regenerate this plan after final normal Save and Quit; all payload bytes come from this actual client, never build/libs or an old ready snapshot.',
        'client': {
            'replace_whole_trees': list(CLIENT_TREES), 'files': client_files,
            'flat_ready_mappings': {
                'mods/projectseele-0.1.0-all.jar': 'ready-client/projectseele-0.1.0-all.jar',
                'shaderpacks/SEELE_Local_Cavern_R53_Private_v1.zip': 'ready-client/SEELE_Local_Cavern_R53_Private_v1.zip',
            },
            'structured_payload_required': 'The flat ready directory is insufficient: preserve all listed client trees in the final package overrides.',
        },
        'launch': {
            'java': str(a.java), 'private_args_file': str(args),
            'extra_jvm_args': ['-XX:CompileCommand=exclude,net/minecraft/world/level/BlockCollisions.m_186411_',
                               '-XX:CompileCommand=exclude,com/google/gson/stream/JsonReader.peekNumber',
                               '-javaagent:' + str(a.background_agent) + '=no-focus'],
            'background_agent': str(a.background_agent),
            'candidate_launcher': 'start_R53_actual_candidate.ps1',
            'launcher_modes': {'Visible': 'Default human-visible client, no review agent.',
                               'BackgroundReview': 'Explicit automatic review, hidden/no-focus agent.'},
            'rule': 'Never call install_ready_client.ps1 from the actual-client launcher. Keep account/session arguments private; no args contents are emitted here.',
        },
        'static_delta': {
            'whole_current_region_files': static_files,
            'installation_receipts': [str(p) for p in receipts if p.is_file()],
            'generation_recipe_files': recipes,
            'recipe_declaration': str(a.generation_updates.resolve()),
            'rule': 'Copy current complete region files and current complete eight recipes only after the final installation; never copy their pre-install backups or reapply old patches.',
        },
        'current_navigation': {'files': nav, 'complete_table_tree': 'tables',
                               'rule': 'Use actual current world files; preserve all companion metadata and tables together.'},
        'cold_progress_snapshot': {
            'replace_complete_trees': state_trees,
            'dimension_saved_data_files': saved_data_files,
            'replace_complete_journal_trees': journal_trees,
            'whole_world_root_files': world_root,
            'world_support_trees': [name for name in WORLD_TREES if (world / name).exists()],
            'rule': 'One stopped-world session only. Include level.dat RootVehicle, all recursive entity passengers, playerdata, every dimension SavedData, current metadata/tables and the whole mtr tree. Replace old tree contents, including deletions; do not merge historic identity snapshots.',
        },
        'final_world_delivery': {
            'source': str(world), 'mode': 'ONE_COLD_ACTUAL_WORLD_STREAM_TO_FINAL_ARCHIVE',
            'all_region_trees': all_region_trees,
            'required_generation_tree': 'dimensions/projectseele/geofront/data/city_rigid_generation_r45',
            'rule': 'Static delta and progress lists alone are NOT a standalone save. Final server world must include every current terrain region and the complete generation library once, directly from the same cold actual world. Do not copy that library into intermediate ready snapshots. Do not splice old archive world entries with a new progress snapshot.',
            'exclude': ['session.lock', '**/DistantHorizons.sqlite', '**/DistantHorizons.sqlite-wal', '**/DistantHorizons.sqlite-shm', '**/*.tmp'],
            'preconditions': ['All requested native flows finished or explicitly described as pending.',
                              'Normal Save and Quit completed; no process has this world open.',
                              'Hold the existing world/session.lock throughout inventory and streaming.',
                              'Read back delivered changed entries and state file inventory without digest reports.'],
        },
        'never_copy': ['client/assets', 'client/libraries', 'client/.minecraft', 'client/logs',
                       'client/crash-reports', 'client/debug', 'client/PCL', 'client/pose-captures',
                       'client/screenshots', 'client/modernfix', 'client/saves/*/data/DistantHorizons.sqlite',
                       '.Codex', 'integration1023 diagnostics and backup snapshots'],
        'existing_tool_reuse': {
            'zip_update': 'tools/patch_zip_entries.py:replace_entries (existing established PCL/server format)',
            'packager': 'tools/package_r53_current_review.py',
            'implemented_source_boundary': [
                'Mod comes from actual client/mods, with complete current PCL override trees.',
                'Existing server mod selection is retained and refreshed from actual; missing old mod aborts.',
                'DistantHorizons SQLite caches are pruned; required generation data stays complete.',
                'One existing session.lock is held across source collection and archive readback.',
                'Stale archive entries from replaced trees are removed; changed entries get byte readback.',
            ],
            'required_before_execution': ['Finish the requested native flow and normally stop the actual world.',
                                          'Regenerate this plan and confirm the final installation set.',
                                          'Root selects the final delivery date/build and executes packaging; this plan does not promote anything.'],
        },
    }
    output.mkdir(parents=True)
    (output / 'READY_SYNC_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_launcher(output / 'start_R53_actual_candidate.ps1', base, a.java, args, a.background_agent)
    print(json.dumps({'plan': str(output / 'READY_SYNC_PLAN.json'),
                      'client_files': len(client_files), 'static_regions': len(static_files),
                      'generation_recipes': len(recipes), 'copied_payload_files': 0,
                      'ready_modified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()

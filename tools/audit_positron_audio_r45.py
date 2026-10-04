"""Read-only installed audio audit. Private auditions are never project resources."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/rebuild_r45/positron_audio_sol_followup'
JAR = ROOT / '.Codex/local-mods/superbwarfare-0.8.9.1-hotfix-mc1.20.1-993063bed-all.jar'
EVENTS = ['annihilator_fire_1p', 'annihilator_fire_3p', 'annihilator_far',
          'annihilator_veryfar', 'annihilator_reload']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def duration(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                             'format=duration', '-of', 'json', str(path)],
                            check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)['format']['duration'])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    private = OUT / 'private_auditions_not_for_distribution'
    private.mkdir(exist_ok=True)
    (private / '.gitignore').write_text('*\n', encoding='utf-8')
    rows = []
    with zipfile.ZipFile(JAR) as archive:
        sounds = json.loads(archive.read('assets/superbwarfare/sounds.json'))
        vehicle = json.loads(archive.read('data/superbwarfare/sbw/vehicles/annihilator.json'))
        language = json.loads(archive.read('assets/superbwarfare/lang/zh_cn.json'))
        identity = {key: value for key, value in language.items()
                    if 'annihilator' in key and not key.startswith('item.')}
        for event in EVENTS:
            definition = sounds[event]
            for sample in definition['sounds']:
                name = sample if isinstance(sample, str) else sample['name']
                namespace, relative = name.split(':', 1)
                member = f'assets/{namespace}/sounds/{relative}.ogg'
                data = archive.read(member)
                path = private / (event + '.ogg')
                path.write_bytes(data)
                rows.append({'event': f'superbwarfare:{event}', 'jar_member': member,
                             'definition': definition, 'sha256': sha(data), 'bytes': len(data),
                             'seconds': duration(path), 'audition': str(path),
                             'subjective_listen_passed': False, 'license': 'Assets: All Rights Reserved',
                             'project_resource_copy': False, 'redistribution_authorized': False})
    overrides = []
    options = (ROOT / 'run/options.txt').read_text(encoding='utf-8')
    enabled = json.loads(next(line.split(':', 1)[1] for line in options.splitlines()
                             if line.startswith('resourcePacks:')))
    for entry in enabled:
        if not entry.startswith('file/'):
            continue
        pack = ROOT / 'run/resourcepacks' / entry[5:]
        if pack.is_dir():
            matches = [str(p.relative_to(pack)) for p in pack.rglob('sounds.json')]
            raw_overrides = [str(p.relative_to(pack)) for p in pack.rglob('*.ogg')]
        elif pack.is_file():
            with zipfile.ZipFile(pack) as archive:
                matches = [p for p in archive.namelist() if p.endswith('/sounds.json')]
                raw_overrides = [p for p in archive.namelist() if '/sounds/' in p and p.endswith('.ogg')]
        else:
            matches = ['PACK_NOT_FOUND']
            raw_overrides = []
        overrides.append({'pack': str(pack), 'sound_definition_files': matches, 'raw_audio_overrides': raw_overrides,
                          'missing': not pack.exists()})
    project_definitions = json.loads((ROOT / 'src/main/resources/assets/projectseele/sounds.json').read_text(encoding='utf-8'))
    provenance = []
    for relative in ['artifacts/first_battle_world_r10/audio/manifest.json',
                     'artifacts/world_repair_r21/audio/sources.json',
                     'artifacts/combat_direction_r36/audio/manifest.json']:
        receipt = ROOT / relative
        data = json.loads(receipt.read_text(encoding='utf-8'))
        rows_for_receipt = data if isinstance(data, list) else data['outputs']
        for row in rows_for_receipt:
            provenance.append(dict(receipt=str(receipt), **row))
    project_events = []
    for name in ['beam_charge', 'beam_fire', 'eva_rifle_fire', 'eva_foot_concrete', 'eva_foot_soil',
                 'eva_land', 'eva_servo', 'eva_drive_loop', 'eva_cockpit_warning', 'eva_joint_load',
                 'eva_swing', 'eva_impact', 'eva_impact_heavy', 'eva_armor_impact', 'eva_knife_cut',
                 'eva_core_break', 'eva_at_pressure', 'eva_at_tear', 'eva_berserk_roar',
                 'facility_rail_motion', 'facility_hydraulic', 'facility_hydraulic_launch',
                 'facility_lock', 'facility_catapult', 'facility_siren']:
        definition = project_definitions[name]
        clips = []
        for sample in definition['sounds']:
            resource = sample if isinstance(sample, str) else sample['name']
            namespace, relative = resource.split(':', 1)
            path = ROOT / 'src/main/resources/assets' / namespace / 'sounds' / (relative + '.ogg')
            digest = sha(path.read_bytes()) if path.exists() else None
            clips.append({'resource': resource, 'path': str(path), 'exists': path.exists(),
                          'sha256': digest,
                          'matching_provenance_receipts': [row for row in provenance if row.get('sha256') == digest],
                          'seconds': duration(path) if path.exists() else None})
        project_events.append({'event': name, 'definition': definition, 'clips': clips,
                               'subjective_listen_passed': False})
    installed = json.loads((ROOT / 'artifacts/rebuild_r45/audio/installation/installed.json').read_text(encoding='utf-8'))
    voices = json.loads((ROOT / 'src/main/resources/assets/projectseele/audio/facility_voice_r45.json').read_text(encoding='utf-8'))
    voice_rows = []
    for voice in voices:
        path = ROOT / 'src/main/resources/assets/projectseele/sounds' / (voice['name'] + '.ogg')
        recorded = next(row for row in installed['files'] if row['name'] == path.name)
        digest = sha(path.read_bytes())
        voice_rows.append({'name': voice['name'], 'path': str(path), 'text': voice['text'],
                           'subtitle_cn': voice['subtitle_cn'], 'sha256': digest,
                           'seconds': duration(path), 'receipt_hash_matches': recorded['sha256'] == digest,
                           'metadata_installed_flag': voice.get('installed'),
                           'subjective_listen_passed': False})
    report = {'world_written': False, 'project_assets_written': False,
              'jar': str(JAR), 'jar_sha256': sha(JAR.read_bytes()),
              'identity_from_installed_lang': identity, 'weapon_definition': vehicle,
              'annihilator_events': rows, 'active_resourcepack_sound_overrides': overrides,
              'facility_current_recordings': voice_rows, 'project_current_events': project_events,
              'reference_commit': '993063bed60ac4d0a8d75ca9972765f4557172c8',
              'primary_license_url': 'https://github.com/Mercurows/SuperbWarfare/blob/993063bed60ac4d0a8d75ca9972765f4557172c8/README-en.md',
              'private_audition_distribution': 'Excluded. Event references require installed SBW on clients.'}
    (OUT / 'installed_audio_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'events': len(rows), 'voices': len(voice_rows),
                      'receipt_matches': sum(row['receipt_hash_matches'] for row in voice_rows),
                      'output': str(OUT / 'installed_audio_audit.json')}))


if __name__ == '__main__':
    main()

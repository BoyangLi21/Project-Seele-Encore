"""Read the compiled ground function against independently composed map deltas."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/rebuild_r44'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--delta', type=Path, action='append', default=[])
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a fresh evidence directory'
    args.output.mkdir(parents=True)
    contract_path = ART / 'city_expansion/tv_geofront_continuous_range_v1/frozen_whole_geometry_v2/terrain_contract.json'
    contract = json.loads(contract_path.read_text('utf8'))
    surface = {}
    provenance = []
    sources = [(Path(s['forward']), s['forward_sha256']) for s in contract['sectors']]
    sources += [(p, None) for p in args.delta]
    for path, expected_hash in sources:
        actual_hash = digest(path)
        if expected_hash:
            assert actual_hash == expected_hash, ('Construction source changed', path)
        tops = {}
        with gzip.open(path, 'rt', encoding='utf8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['after'].split('[')[0] != 'minecraft:grass_block':
                    continue
                x, y, z = row['pos']
                tops[x, z] = max(y, tops.get((x, z), y))
        surface.update(tops)
        provenance.append(dict(path=str(path.resolve()), sha256=actual_hash,
                               authored_surface_columns=len(tops)))
    assert surface, 'No independent authored surface cells'
    tsv = args.output / 'patch_surface_expectations.tsv'
    tsv.write_text(''.join(f'{x} {z} {y}\n' for (x, z), y in sorted(surface.items())), 'utf8')
    source = args.output / 'GroundPatchReadbackR44.java'
    source.write_text('''import java.io.*;
import com.projectseele.world.TvWorldPreviewTerrain;
public final class GroundPatchReadbackR44 {
 public static void main(String[] args) throws Exception {
  int checked=0, failures=0;
  try(var r=new BufferedReader(new InputStreamReader(System.in))) {
   String line; while((line=r.readLine())!=null) {
    var a=line.split(" ");
    int x=Integer.parseInt(a[0]),z=Integer.parseInt(a[1]),want=Integer.parseInt(a[2]);
    int got=TvWorldPreviewTerrain.ground(x,z); checked++;
    if(got!=want){if(failures<20)System.out.println("MISMATCH "+line+" actual="+got);failures++;}
   }
  }
  System.out.println("checked="+checked+" failures="+failures);
  if(failures>0 || checked!=Integer.parseInt(args[0]))
   throw new IllegalStateException("Compiled generator differs from exact construction patches");
 }
}
''', 'utf8')
    launch = json.loads((ART / 'space_photos/actual_geofront_whole_ranges_v1/20261001_144531/launch.json').read_text('utf8'))
    command = launch['command']
    classpath = command[command.index('-cp') + 1]
    java = Path(command[0])
    build = subprocess.run([str(java.with_name('javac.exe')), '-cp', classpath,
                            '-d', str(args.output.resolve()), str(source.resolve())],
                           capture_output=True, text=True, cwd=ROOT)
    (args.output / 'compile.log').write_text(build.stdout + build.stderr, 'utf8')
    assert build.returncode == 0, 'Readback helper compile failed; see compile.log'
    with tsv.open('rb') as stream:
        run = subprocess.run([str(java), '-Xmx768m', '-cp', str(args.output.resolve()) + ';' + classpath,
                              'GroundPatchReadbackR44', str(len(surface))], stdin=stream,
                             capture_output=True, text=True, cwd=ROOT)
    (args.output / 'native_java_stdout.log').write_text(run.stdout, 'utf8')
    (args.output / 'native_java_stderr.log').write_text(run.stderr, 'utf8')
    resource = ROOT / 'build/resources/main/data/projectseele/worldgen/authored/geofront_east_ranges_r44.json.gz'
    compiled = ROOT / 'build/classes/java/main/com/projectseele/world/TvWorldPreviewTerrain.class'
    result = dict(passed=run.returncode == 0, columns=len(surface), source_deltas=provenance,
                  input_sha256=digest(tsv), compiled_class_sha256=digest(compiled),
                  shipped_heightfield_sha256=digest(resource), java_only=True,
                  actual_chunk_generation=False, world_blocks_written=False, visual_passed=False,
                  scope='Compiled production ground method versus surface cells composed from exact forward patches, not heightfield compared with itself.')
    (args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf8')
    print('Compiled ground readback', len(surface), 'passed', result['passed'], args.output, flush=True)
    assert result['passed'], run.stdout


if __name__ == '__main__':
    main()

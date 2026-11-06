"""Configuration-driven offline checks for frozen station candidates."""
import json
import subprocess
import sys
from pathlib import Path
import numpy as np
from map_pipeline.delivery_check import read


def local_file(root, name):
    root = Path(root).resolve()
    path = (root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Check file is missing or outside its package: '+name)
    return path


def verify(args):
    spec = read(args.checks)
    values = dict(python=sys.executable, tools=str(Path(__file__).resolve().parents[1]),
                  candidate=str(args.candidate), authority=str(args.authority),
                  models=str(args.models), review=str(args.review))
    logs = args.candidate/'release-check-logs'
    logs.mkdir(exist_ok=True)
    for i, row in enumerate(spec.get('commands', [])):
        command = [part.format(**values) for part in row['argv']]
        with (logs/f'{i:02}.log').open('w', encoding='utf8') as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
        if result.returncode:
            raise ValueError(f"Offline check failed: {row['name']}; see {logs/f'{i:02}.log'}")
    if not spec.get('candidate_error_reports'):
        raise ValueError('No candidate checks declared')
    for name in spec['candidate_error_reports']:
        report = read(local_file(args.candidate, name))
        if 'errors' not in report or report['errors']:
            raise ValueError('Candidate check is incomplete or failed: '+name)
    for name in spec['review_error_reports']:
        report = read(local_file(args.review, name))
        if 'errors' not in report or report['errors']:
            raise ValueError('Independent review failed: '+name)
    for item in spec.get('report_values', []):
        roots = dict(candidate=args.candidate, review=args.review)
        report = read(local_file(roots[item['root']], item['file']))
        for key, expected in item['equals'].items():
            if key not in report or report[key] != expected:
                raise ValueError('Required evidence differs: '+item['file']+'/'+key)
    for pair in spec.get('exact_model_arrays', []):
        with np.load(local_file(args.candidate, pair['candidate'])) as actual, np.load(local_file(args.models, pair['reference'])) as reference:
            for key in pair['keys']:
                if not np.array_equal(actual[key], reference[key]):
                    raise ValueError('Independently decoded vehicle model differs: '+key)
    for name in spec['reviewed_views']:
        local_file(args.review, name)
    if not spec.get('views_reviewed_by_root'):
        raise ValueError('Independent view review has not been recorded')
    return spec

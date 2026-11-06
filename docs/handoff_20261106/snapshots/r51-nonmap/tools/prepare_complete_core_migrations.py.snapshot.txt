"""Run the reviewed core migrations against one explicit current construction.

Legacy modules provide measured runs and typed NBT migration. Their historical
WORLD defaults are never used by this entry point. This does not activate runtime
builders or declare a partially constructed map playable.
"""
from pathlib import Path
import argparse
import importlib
import json
import sys


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('terminal','pyramid','hangar','hq_station'))
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    base=args.base.resolve()
    world=(base/'WORLD').resolve()
    assert world.parent==base and world.name=='WORLD'
    assert (base/'BASELINE.json').is_file()
    depth=json.loads((base/'depth_extension/APPLIED.json').read_text('utf8'))
    assert depth, 'Depth migration receipt must exist'
    import survey_r52_original_complex as survey
    import extend_world_depth_r52 as extension
    survey.BASE=extension.BASE=base
    survey.WORLD=extension.WORLD=world
    survey.OUT=base/'survey'
    module=importlib.import_module('prepare_'+args.stage+'_move_r52')
    module.BASE=base
    module.WORLD=world
    module.OUT=base/(args.stage+'_move')
    sys.argv=[module.__name__]+(['--apply'] if args.apply else [])
    module.main()


if __name__=='__main__':
    main()

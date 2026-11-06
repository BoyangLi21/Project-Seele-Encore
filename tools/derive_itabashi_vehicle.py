"""Offline e44 mini model derivation, recording uninstantiated definitions.

The installed mini position file omits full-size window instances. The shared
strict mainline parser is unchanged; this adapter explicitly records those
uninstantiated definitions while using the same cube transformation maths.
"""
import argparse, inspect
from pathlib import Path
import derive_mtr_station_vehicle_envelopes as parser


def derive(jar, vehicles, out):
    source = inspect.getsource(parser.derive)
    source = source.replace('parts=[];all_cubes=[];visible_cubes=[];',
                            'parts=[];inactive=[];all_cubes=[];visible_cubes=[];')
    old = "if definition not in definitions:raise ValueError('Missing selected position definition')"
    new = ("if definition not in definitions:\n"
           "                                inactive.append(dict(resource=model['positionDefinitionsResource'], "
           "definition=definition, names=part['names'], reason='No instantiated position in selected mini definition'));continue")
    if old not in source:
        # The primary parser now follows native getPositionDefinition and
        # records missing, hence uninstantiated, position names itself.
        if 'inactive.append' not in source:
            raise ValueError('Shared parser changed; inspect before adapting')
        return parser.derive(jar, vehicles, out)
    source = source.replace(old, new)
    source = source.replace('result=dict(vehicle=ident,',
                            'result=dict(inactive_position_definitions=inactive,vehicle=ident,')
    scope = dict(vars(parser))
    exec(compile(source, __file__, 'exec'), scope)
    scope['derive'](jar, vehicles, out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--jar', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--vehicles', nargs='+', default=['e44_mini_cab_3'])
    a = p.parse_args()
    derive(a.jar, a.vehicles, a.out)

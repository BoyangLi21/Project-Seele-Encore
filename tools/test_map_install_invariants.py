"""Regression cases for destructive ambiguity and protected unknown NBT."""
import copy
import tempfile
import unittest
from pathlib import Path
import nbtlib as n
import numpy as np
from install_hakone_array_patch import Palette, compose
from map_pipeline.install.invariants import assert_chunk_preserved, require_nbt_equal
from apply_s20_approved_semantic_repairs import chunk_blob
from transplant_s22_authority import parse_chunk


def fixture():
    def section(y):
        return n.Compound({'Y':n.Byte(y), 'block_states':n.Compound({'palette':n.List[n.Compound]([n.Compound({'Name':n.String('minecraft:stone')})])}),
            'biomes':n.Compound({'palette':n.List[n.String]([n.String('minecraft:plains')])}), 'FutureModFlag':n.Byte(1)})
    return n.File({'Status':n.String('minecraft:full'), 'xPos':n.Int(-1), 'zPos':n.Int(32),
        'sections':n.List[n.Compound]([section(-84), section(5)]),
        'block_entities':n.List[n.Compound]([n.Compound({'id':n.String('unknown:device'), 'x':n.Int(-1), 'y':n.Int(81), 'z':n.Int(512),
            'UnknownInventory':n.Compound({'revision':n.Long(7), 'slots':n.LongArray([1,2,3])})})]),
        'UnknownRoot':n.Compound({'tag':n.Short(9)}), 'block_ticks':n.List[n.Compound](), 'Heightmaps':n.Compound()})


class InstallInvariants(unittest.TestCase):
    def test_serialized_edit_preserves_deep_underground_and_unknown_nbt(self):
        before=fixture();after=copy.deepcopy(before)
        after['sections'][1]['block_states']['palette'][0]['Name']=n.String('minecraft:air')
        del after['Heightmaps']
        assert_chunk_preserved(before,parse_chunk(chunk_blob(after)),{5},{})

    def test_equal_numeric_value_with_different_nbt_type_fails(self):
        with self.assertRaisesRegex(ValueError,'type changed'):
            require_nbt_equal(n.Compound({'mod':n.Byte(1)}),n.Compound({'mod':n.Int(1)}))

    def test_deep_section_change_is_rejected(self):
        before=fixture();after=copy.deepcopy(before)
        after['sections'][0]['block_states']['palette'][0]['Name']=n.String('minecraft:air')
        with self.assertRaisesRegex(ValueError,'sections/-84'):
            assert_chunk_preserved(before,after,{5},{})

    def test_unknown_device_inventory_change_is_rejected(self):
        before=fixture();after=copy.deepcopy(before)
        after['block_entities'][0]['UnknownInventory']['slots'][1]=999
        with self.assertRaisesRegex(ValueError,'block_entities'):
            assert_chunk_preserved(before,after,{5},{})

    def test_only_explicit_device_migration_is_allowed(self):
        before=fixture();after=copy.deepcopy(before)
        after['block_entities'][0]['UnknownInventory']['revision']=n.Long(8)
        change={(-1,81,512):{'Before':before['block_entities'][0], 'After':after['block_entities'][0]}}
        assert_chunk_preserved(before,parse_chunk(chunk_blob(after)),{5},change)

    def test_conflicting_after_cannot_depend_on_candidate_order(self):
        with tempfile.TemporaryDirectory()as temp:
            files=[]
            for i,after in enumerate([1,2,1]):
                file=Path(temp)/f'{i}.npz'
                np.savez(file,coordinates=[[-1,32]],ranges=[0,1],indices=[0],before=[0],after=[after],
                    palette=['minecraft:stone','minecraft:air','minecraft:dirt'])
                files.append(file)
            for pair in [files[:2],files[1::-1]]:
                with self.assertRaisesRegex(ValueError,'Conflicting final states at'):
                    compose(pair,Palette())
            forward=compose([files[0],files[2]],Palette())
            reverse=compose([files[2],files[0]],Palette())
            for a,b in zip(forward[-1,32],reverse[-1,32]):np.testing.assert_array_equal(a,b)


if __name__=='__main__': unittest.main()

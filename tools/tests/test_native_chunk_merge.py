"""Failure-oriented checks for cold native chunk publication."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import nbtlib
import merge_hakone_missing_chunks as merger


def chunk(x=0, z=0, status='carvers'):
    return nbtlib.File({'xPos':nbtlib.Int(x),'zPos':nbtlib.Int(z),'yPos':nbtlib.Int(-84),
        'Status':nbtlib.String('minecraft:'+status),'DataVersion':nbtlib.Int(3465),
        'LastUpdate':nbtlib.Long(400),'InhabitedTime':nbtlib.Long(7)})


class NativeChunkMergeTests(unittest.TestCase):
    def test_original_payload_change_rejected(self):
        old=merger.chunk_blob(chunk())
        changed=chunk();changed['LastUpdate']=nbtlib.Long(401)
        with self.assertRaisesRegex(ValueError,'changed since capture'):
            merger.prepare_slot(old,merger.chunk_blob(changed),merger.chunk_blob(chunk(status='full')),(0,0),900)

    def test_missing_became_existing_rejected(self):
        with self.assertRaisesRegex(ValueError,'changed since capture'):
            merger.prepare_slot(None,merger.chunk_blob(chunk()),merger.chunk_blob(chunk(status='full')),(0,0),900)

    def test_existing_full_rejected(self):
        full=merger.chunk_blob(chunk(status='full'))
        with self.assertRaisesRegex(ValueError,'Already FULL'):
            merger.prepare_slot(full,full,full,(0,0),900)

    def test_persistent_ticks_and_unknown_metadata_rejected(self):
        old=merger.chunk_blob(chunk())
        for field in ('block_ticks','block_entities'):
            new=chunk(status='full');new[field]=nbtlib.List[nbtlib.Compound]([nbtlib.Compound()])
            with self.assertRaisesRegex(ValueError,'explicit migration'):
                merger.prepare_slot(old,old,merger.chunk_blob(new),(0,0),900)
        new=chunk(status='full');new['UnreviewedIdentity']=nbtlib.String('keep me')
        with self.assertRaisesRegex(ValueError,'Protected NBT fields'):
            merger.prepare_slot(old,old,merger.chunk_blob(new),(0,0),900)

    def test_native_time_normalized_without_importing_inhabited_time(self):
        old=merger.chunk_blob(chunk());new=chunk(status='full');new['InhabitedTime']=nbtlib.Long(999)
        encoded,status=merger.prepare_slot(old,old,merger.chunk_blob(new),(0,0),900)
        result=merger.parse_chunk(encoded)
        self.assertEqual(status,'carvers');self.assertEqual(int(result['LastUpdate']),900)
        self.assertEqual(int(result['InhabitedTime']),7)

    def test_second_publication_failure_restores_original_regions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);world=root/'actual';source=root/'cache-server/world';plan_dir=root/'plan'
            actual_files=[];original_bytes=[]
            for cx in (0,32):
                name=f'r.{cx//32}.0.mca';slots=[None]*1024
                slots[0]=merger.chunk_blob(chunk(cx,0))
                slots[1]=merger.chunk_blob(chunk(cx+1,0,status='full'))
                raw=merger.build_region(bytes(range(256))*16,slots)
                for parent in (world,plan_dir/'actual-before'):
                    f=parent/merger.DIM/'region'/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(raw)
                actual_files.append(world/merger.DIM/'region'/name);original_bytes.append(raw)
                slots[0]=merger.chunk_blob(chunk(cx,0,status='full'))
                f=source/merger.DIM/'region'/name;f.parent.mkdir(parents=True,exist_ok=True)
                f.write_bytes(merger.build_region(bytes(4096),slots))
            args=SimpleNamespace(world=world,source=source,list=plan_dir/'chunks.json',out=root/'install')
            guard=SimpleNamespace(by_chunk={},report={})
            real_replace=merger.atomic_replace
            def fail_second(path,data):
                if path==actual_files[1]:raise OSError('simulated publication failure')
                return real_replace(path,data)
            with patch.object(merger,'preflight',return_value=({'chunks':[[0,0],[32,0]]},900)),patch.object(merger,'launch_protection',return_value=guard),patch.object(merger,'atomic_replace',side_effect=fail_second):
                with self.assertRaisesRegex(OSError,'simulated publication failure'):merger.merge(args)
            for f,raw in zip(actual_files,original_bytes):self.assertEqual(f.read_bytes(),raw)
            self.assertEqual(json.loads((args.out/'installation.json').read_text())['status'],'rolled_back')


if __name__=='__main__':unittest.main()

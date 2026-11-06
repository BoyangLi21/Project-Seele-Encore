import tempfile,unittest
from pathlib import Path
from native_transit_additions import prepare,assert_preserved


class NativeAdditionPreservation(unittest.TestCase):
    def test_addition_retains_existing_runtime_bytes(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);world=root/'world';candidate=root/'candidate'
            old=Path('projectseele/geofront/sidings/11/1111')
            for folder in (world/'mtr',candidate/'preserved-native'):
                p=folder/old;p.parent.mkdir(parents=True);p.write_bytes(b'original vehicles and inventories')
            new='mtr/projectseele/geofront/sidings/22/2222';p=candidate/'after'/new;p.parent.mkdir(parents=True);p.write_bytes(b'new boat')
            pairs,baseline,added=prepare(candidate,world,[new])
            for target,source in pairs:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            assert_preserved(world,baseline,added)
            (world/'mtr'/old).write_bytes(b'advanced old vehicle')
            with self.assertRaisesRegex(ValueError,'Existing native member changed'):assert_preserved(world,baseline,added)

    def test_existing_identity_and_undeclared_member_are_rejected(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);world=root/'world';candidate=root/'candidate'
            relative='projectseele/geofront/routes/11/1111'
            for folder in(world/'mtr',candidate/'preserved-native'):
                p=folder/relative;p.parent.mkdir(parents=True);p.write_bytes(b'original route')
            with self.assertRaisesRegex(ValueError,'already exists'):prepare(candidate,world,['mtr/'+relative])
            p=world/'mtr/projectseele/geofront/settings/00/0000';p.parent.mkdir(parents=True);p.write_bytes(b'changed settings')
            with self.assertRaisesRegex(ValueError,'member set changed'):prepare(candidate,world,['mtr/projectseele/geofront/routes/22/2222'])


if __name__=='__main__':unittest.main()

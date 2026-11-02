import multiprocessing
import unittest
from concurrent.futures import ProcessPoolExecutor
import nbtlib
from install_hakone_array_patch import encode_device_changes,decode_device_changes


def spawned_roundtrip(payload):
    return encode_device_changes(decode_device_changes(payload))


class DeviceTransportTest(unittest.TestCase):
    def test_nested_sign_inventory_and_identity_survive_spawn(self):
        tag=nbtlib.Compound({'id':nbtlib.String('minecraft:sign'),'x':nbtlib.Int(-17),'y':nbtlib.Int(104),'z':nbtlib.Int(2050),
            'front_text':nbtlib.Compound({'messages':nbtlib.List[nbtlib.String]([nbtlib.String('{"text":"元箱根港"}')])}),
            'identity':nbtlib.Long(-3816295015381828007),
            'Items':nbtlib.List[nbtlib.Compound]([nbtlib.Compound({'Slot':nbtlib.Byte(4),'Count':nbtlib.Byte(63),
                'tag':nbtlib.Compound({'Damage':nbtlib.Int(19),'Flags':nbtlib.LongArray([-1,2**60+3])})})])})
        before=nbtlib.Compound({'Before':tag});after=nbtlib.Compound({'After':tag})
        source={(-2,128):{(-17,104,2050):before,(-18,104,2050):after}}
        payload=encode_device_changes(source)
        with ProcessPoolExecutor(max_workers=1,mp_context=multiprocessing.get_context('spawn'))as pool:
            received=pool.submit(spawned_roundtrip,payload).result(timeout=30)
        self.assertEqual(received,payload)
        self.assertEqual(decode_device_changes(received),source)

    def test_empty_changes(self):
        self.assertEqual(decode_device_changes(encode_device_changes({})),{})


if __name__=='__main__':unittest.main()

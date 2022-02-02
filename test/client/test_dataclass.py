from octoprint_psucontrol_meross.meross_client import MerossDeviceHandle

def test_asdict():
    assert MerossDeviceHandle(name="hello", dev_id="world").asdict() == {"name": "hello", "dev_id": "world"}
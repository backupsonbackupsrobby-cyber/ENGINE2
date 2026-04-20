import asyncio

from engine_core.chinese_device_database import (
    ChineseSmartDeviceDatabase,
    MultiPlatformController,
)


def run(coro):
    return asyncio.run(coro)


def test_device_database_lookup_known_and_unknown_models():
    known = ChineseSmartDeviceDatabase.get_device_info("tuya_light")
    unknown = ChineseSmartDeviceDatabase.get_device_info("does_not_exist")

    assert known["manufacturer"] == "Tuya"
    assert known["protocol"] == "WiFi"
    assert "switch_led" in known["commands"]
    assert unknown == {"error": "Model does_not_exist not found"}


def test_all_supported_devices_contains_expected_models():
    devices = ChineseSmartDeviceDatabase.get_all_supported_devices()

    assert "tuya_light" in devices
    assert "aqara_sensor_temp_humidity" in devices
    assert len(devices) == len(set(devices))


def test_sync_all_platforms_successfully_collects_devices():
    controller = MultiPlatformController()

    result = run(controller.sync_all_platforms())

    assert result["tuya"] == {"count": 2, "status": "success"}
    assert result["aqara"] == {"count": 2, "status": "success"}
    assert result["mi_home"] == {"count": 2, "status": "success"}
    assert result["total_devices"] == 6
    assert len(controller.all_devices) == 6


def test_sync_all_platforms_handles_single_platform_failure():
    controller = MultiPlatformController()

    async def broken_tuya():
        raise RuntimeError("tuya unavailable")

    controller.tuya.get_device_list = broken_tuya

    result = run(controller.sync_all_platforms())

    assert result["tuya"]["status"] == "failed"
    assert "tuya unavailable" in result["tuya"]["error"]
    assert result["aqara"]["status"] == "success"
    assert result["mi_home"]["status"] == "success"
    assert result["total_devices"] == 4


def test_execute_unified_scene_for_known_and_unknown_scene_names():
    controller = MultiPlatformController()

    morning = run(controller.execute_unified_scene("morning"))
    unknown = run(controller.execute_unified_scene("weekend"))

    assert morning == {
        "scene": "morning",
        "actions_executed": 2,
        "status": "success",
    }
    assert unknown == {
        "scene": "weekend",
        "actions_executed": 0,
        "status": "success",
    }


def test_platform_status_and_count_devices_by_platform():
    controller = MultiPlatformController()
    controller.all_devices = {
        "1": {"platform": "tuya"},
        "2": {"platform": "aqara"},
        "3": {"platform": "mi_home"},
        "4": {"platform": "other_vendor"},
    }

    counts = controller._count_devices_by_platform()
    status = controller.get_platform_status()

    assert counts == {
        "tuya": 1,
        "aqara": 1,
        "mi_home": 1,
        "other": 0,
        "other_vendor": 1,
    }
    assert status["total_devices"] == 4
    assert status["platforms"] == controller.platform_status
    assert status["devices_by_platform"] == counts

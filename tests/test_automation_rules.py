import asyncio

from engine_core.automation_rules import (
    AutomationAction,
    AutomationRule,
    AutomationRulesEngine,
    Condition,
    setup_example_automations,
)


def test_rule_condition_operators_cover_all_paths():
    rule = AutomationRule("rule_1", "Rule One")
    state = {
        "temperature": 21,
        "mode": "heat",
        "humidity": 40,
        "label": "living_room_sensor",
    }

    assert rule._evaluate_condition({"entity": "mode", "condition": "equals", "value": "heat"}, state)
    assert rule._evaluate_condition({"entity": "mode", "condition": "not_equals", "value": "cool"}, state)
    assert rule._evaluate_condition({"entity": "temperature", "condition": "gt", "value": 20}, state)
    assert rule._evaluate_condition({"entity": "temperature", "condition": "lt", "value": 22}, state)
    assert rule._evaluate_condition({"entity": "temperature", "condition": "gte", "value": 21}, state)
    assert rule._evaluate_condition({"entity": "temperature", "condition": "lte", "value": 21}, state)
    assert rule._evaluate_condition({"entity": "humidity", "condition": "in_range", "value": (35, 45)}, state)
    assert rule._evaluate_condition({"entity": "label", "condition": "contains", "value": "room"}, state)


def test_should_execute_respects_enabled_and_conditions():
    rule = AutomationRule("rule_2", "Rule Two")
    rule.add_condition({"entity": "state", "condition": "equals", "value": "armed"})

    assert rule.should_execute({"state": "armed"})
    assert not rule.should_execute({"state": "disarmed"})

    rule.enabled = False
    assert not rule.should_execute({"state": "armed"})


def test_execute_respects_cooldown_and_tracks_metadata():
    rule = AutomationRule("rule_3", "Rule Three")
    rule.cooldown = 60

    first = asyncio.run(rule.execute())
    assert first["rule_id"] == "rule_3"
    assert first["execution_count"] == 1
    assert first["actions"] == 0

    second = asyncio.run(rule.execute())
    assert second["success"] is False
    assert "Cooldown" in second["reason"]


class FakeZHA:
    def __init__(self):
        self.calls = []

    async def set_device_state(self, device_id, state, sync_cycle=None):
        self.calls.append({"device_id": device_id, "state": state, "sync_cycle": sync_cycle})
        return True


def test_engine_evaluate_execute_and_status_tracking():
    zha = FakeZHA()
    engine = AutomationRulesEngine(zha_integration=zha)

    rule = engine.create_rule("motion", "Motion Rule")
    rule.add_condition({"entity": "motion", "condition": Condition.EQUALS.value, "value": True})
    rule.add_action(AutomationAction(device_id="light_1", service="turn_on", data={"state": "on"}))

    matched = asyncio.run(engine.evaluate_triggers({"motion": True}))
    assert matched == ["motion"]
    assert engine.total_triggers == 1

    result = asyncio.run(engine.execute_rules(matched, sync_cycle=7))
    assert result["rules_executed"] == 1
    assert result["actions"] == 1
    assert result["results"][0]["success"] is True
    assert zha.calls == [{"device_id": "light_1", "state": "on", "sync_cycle": 7}]

    status = engine.get_engine_status()
    assert status["total_rules"] == 1
    assert status["enabled_rules"] == 1
    assert status["disabled_rules"] == 0
    assert status["total_automations"] == 1
    assert status["total_actions"] == 1
    assert status["execution_history"] == 1


def test_setup_example_automations_creates_expected_rules_and_actions():
    engine = AutomationRulesEngine()

    asyncio.run(setup_example_automations(engine, None))

    assert set(engine.rules.keys()) == {
        "morning_routine",
        "motion_lights",
        "night_mode",
        "temperature_control",
    }
    assert len(engine.rules["morning_routine"].actions) == 3
    assert engine.rules["motion_lights"].cooldown == 30
    assert engine.rules["temperature_control"].cooldown == 300

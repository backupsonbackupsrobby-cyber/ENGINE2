import asyncio
from datetime import datetime

from engine_core.automation_rules import (
    AutomationAction,
    AutomationRule,
    AutomationRulesEngine,
    AutomationTrigger,
    TriggerType,
    setup_example_automations,
)


def run(coro):
    return asyncio.run(coro)


def test_rule_builder_helpers_append_and_return_self():
    rule = AutomationRule("rule_1", "Rule 1")
    trigger = AutomationTrigger(
        trigger_type=TriggerType.TIME,
        entity_id="clock",
    )
    action = AutomationAction(
        device_id="light_1", service="turn_on", data={"state": "on"}
    )

    assert rule.add_trigger(trigger) is rule
    condition = {"entity": "temp", "condition": "gt", "value": 20}
    assert rule.add_condition(condition) is rule
    assert rule.add_action(action) is rule

    assert rule.triggers == [trigger]
    assert rule.conditions == [condition]
    assert rule.actions == [action]


def test_can_execute_respects_enabled_and_cooldown():
    rule = AutomationRule("rule_2", "Rule 2")
    assert rule.can_execute() is True

    rule.enabled = False
    assert rule.can_execute() is False

    rule.enabled = True
    rule.cooldown = 60
    rule.last_trigger_time = datetime.now().timestamp()
    assert rule.can_execute() is False


def test_evaluate_condition_supported_operators():
    rule = AutomationRule("rule_3", "Rule 3")
    state = {"x": 10, "label": "engine2"}

    assert rule._evaluate_condition(
        {"entity": "x", "condition": "equals", "value": 10}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "not_equals", "value": 9}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "gt", "value": 9}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "lt", "value": 11}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "gte", "value": 10}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "lte", "value": 10}, state
    )
    assert rule._evaluate_condition(
        {"entity": "x", "condition": "in_range", "value": [5, 15]}, state
    )
    assert rule._evaluate_condition(
        {"entity": "label", "condition": "contains", "value": "gin"}, state
    )


def test_should_execute_returns_false_when_any_condition_fails():
    rule = AutomationRule("rule_4", "Rule 4")
    rule.add_condition({"entity": "temp", "condition": "gt", "value": 20})
    motion_condition = {
        "entity": "motion",
        "condition": "equals",
        "value": "on",
    }
    rule.add_condition(motion_condition)

    assert rule.should_execute({"temp": 22, "motion": "on"}) is True
    assert rule.should_execute({"temp": 19, "motion": "on"}) is False


def test_execute_updates_metadata_and_returns_result():
    rule = AutomationRule("rule_5", "Rule 5")
    rule.add_action(AutomationAction(device_id="plug_1", service="turn_on"))

    result = run(rule.execute())

    assert result["rule_id"] == "rule_5"
    assert result["rule_name"] == "Rule 5"
    assert result["execution_count"] == 1
    assert result["actions"] == 1
    assert rule.execution_count == 1
    assert rule.last_execution is not None


def test_execute_returns_failure_when_cooldown_active():
    rule = AutomationRule("rule_6", "Rule 6")
    rule.cooldown = 300
    rule.last_trigger_time = datetime.now().timestamp()

    result = run(rule.execute())

    assert result == {
        "success": False,
        "reason": "Cooldown active or rule disabled",
    }


class DummyZHA:
    def __init__(self):
        self.calls = []

    async def set_device_state(self, device_id, state, sync_cycle=None):
        self.calls.append((device_id, state, sync_cycle))
        return state != "fail"


def test_engine_create_evaluate_execute_and_status():
    zha = DummyZHA()
    engine = AutomationRulesEngine(zha_integration=zha)

    rule_a = engine.create_rule("a", "Rule A")
    home_mode_condition = {
        "entity": "mode",
        "condition": "equals",
        "value": "home",
    }
    rule_a.add_condition(home_mode_condition)
    rule_a.add_action(
        AutomationAction(
            device_id="light_1",
            service="turn_on",
            data={"state": "on"},
        )
    )

    rule_b = engine.create_rule("b", "Rule B")
    rule_b.enabled = False

    matching = run(engine.evaluate_triggers({"mode": "home"}))
    assert matching == ["a"]

    execution = run(engine.execute_rules(["a", "missing"], sync_cycle=7))
    assert execution["rules_executed"] == 2
    assert execution["actions"] == 1
    assert len(execution["results"]) == 1
    assert all(item["rule_id"] == "a" for item in execution["results"])

    assert zha.calls == [("light_1", "on", 7)]

    status = engine.get_engine_status()
    assert status["total_rules"] == 2
    assert status["enabled_rules"] == 1
    assert status["disabled_rules"] == 1
    assert status["total_triggers"] == 1
    assert status["total_automations"] == 1
    assert status["total_actions"] == 1
    assert status["automations_executed"] == {"a": 1}
    assert status["execution_history"] == 1


def test_setup_example_automations_creates_expected_rules():
    engine = AutomationRulesEngine()
    updated = run(setup_example_automations(engine, None))

    assert updated is engine
    assert set(engine.rules.keys()) == {
        "morning_routine",
        "motion_lights",
        "night_mode",
        "temperature_control",
    }
    assert len(engine.rules["morning_routine"].actions) == 3
    assert engine.rules["motion_lights"].cooldown == 30
    assert engine.rules["temperature_control"].cooldown == 300

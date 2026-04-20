import asyncio

from engine_core.tron_rhythm import TRONPhase, TRONRhythmEngine


def test_register_and_unregister_entities_and_status():
    engine = TRONRhythmEngine(node_id="node_a", grid_frequency=2)

    engine.register_node("node_b")
    engine.register_zha_device("lamp_1")
    engine.unregister_zha_device("lamp_1")

    status = engine.get_grid_status()
    assert status["node_id"] == "node_a"
    assert status["nodes"] == 2
    assert status["zha_devices"] == 0
    assert status["state_ledger_entries"] == 0


def test_heartbeat_and_commitment_update_energy_and_ledger():
    engine = TRONRhythmEngine(node_id="node_a")
    engine.register_zha_device("device_1")
    engine.register_zha_device("device_2")

    start_energy = engine.energy_balance
    asyncio.run(engine.heartbeat_phase())
    assert engine.energy_balance == max(0, start_energy - 1.0)
    assert engine.phase_timestamps[TRONPhase.HEARTBEAT] > 0

    asyncio.run(engine.commitment_phase({"k": "v"}))
    assert len(engine.state_ledger) == 1
    assert engine.state_ledger[0]["state_hash"]
    assert engine.phase_timestamps[TRONPhase.COMMITMENT] > 0


def test_consensus_phase_handles_pending_and_achieved_states():
    engine = TRONRhythmEngine(node_id="node_a")
    engine.register_node("node_b")
    engine.register_node("node_c")

    before = engine.consensus_efficiency
    asyncio.run(engine.consensus_phase())
    assert engine.consensus_efficiency < before

    key = f"cycle_{engine.current_cycle}"
    engine.consensus_votes[key] = {"node_a", "node_b", "node_c"}
    prior = engine.consensus_efficiency
    asyncio.run(engine.consensus_phase())
    assert engine.consensus_efficiency >= prior
    assert engine.phase_timestamps[TRONPhase.CONSENSUS] > 0


def test_execution_phase_mutates_actions_with_cycle_and_timestamp():
    engine = TRONRhythmEngine(node_id="node_a")
    actions = [{"device": "light_1", "command": "turn_on"}]

    asyncio.run(engine.execution_phase(actions))

    assert "executed_at" in actions[0]
    assert actions[0]["cycle"] == engine.current_cycle
    assert engine.phase_timestamps[TRONPhase.EXECUTION] > 0


def test_run_tron_cycle_advances_cycle_and_nonce():
    engine = TRONRhythmEngine(node_id="node_a", grid_frequency=10)
    engine.phase_allocations = {phase: 0 for phase in TRONPhase}
    actions = [{"device": "light_1", "command": "sync"}]

    asyncio.run(engine.run_tron_cycle(zha_state={"state": "ok"}, actions=actions))

    assert engine.current_cycle == 1
    assert engine.grid_nonce == 1
    assert engine.sync_accuracy >= 0
    assert len(engine.state_ledger) == 1
    assert "executed_at" in actions[0]

# Tau source audit — 29 September 2026

This is a read-only research audit, not an implementation or benchmark result. The upstream repository was cloned into `research-sources/tau2-bench`. No dependencies were installed and no model evaluations were run.

Repository: https://github.com/sierra-research/tau2-bench

Inspected commit: `5bfa7e37b36656b37dc6d022156be6563c1007f3`

Package version: `1.0.1`. The README calls the current benchmark tau-three; the repository and CLI retain the `tau2` name. Python requirement: `>=3.12,<3.14`.

## Counts obtained directly from task JSON and split JSON

| Domain | All task records | Base evaluation split | Active reward bases in base split |
|---|---:|---:|---|
| Airline | 50 | 50 | 50: DB + COMMUNICATE |
| Retail | 114 | 114 | 112: DB + NL_ASSERTION; 2: DB |
| Telecom | 2,285 | 114 | 94: ENV_ASSERTION; 20: ENV_ASSERTION + ACTION |

An activated check can be vacuous if its associated criteria are empty. These counts describe configuration, not the number of substantive checks or how often agents pass.

`docs/evaluation.md` says the default across these domains is DB + COMMUNICATE and claims ACTION is absent from telecom. The checked-in task files disagree. For this snapshot, use actual task `evaluation_criteria.reward_basis` and evaluator implementation as the authority. Do not carry these counts into another revision without recomputing them.

## Source map

- Agent instructions and policy composition: `src/tau2/agent/llm_agent.py`.
- User prompt composition: `src/tau2/user/user_simulator.py`.
- User state/protocol: `src/tau2/user/user_simulator_base.py`.
- Global user rules: `data/tau2/user_simulator/simulation_guidelines.md` and `simulation_guidelines_tools.md`.
- Runtime persona fields: `src/tau2/data_model/persona.py`.
- Task facts, goals, personas, initial conditions and evaluation criteria: `data/tau2/domains/<domain>/tasks.json`.
- Domain rules: `data/tau2/domains/<domain>/policy.md`.
- Simulator registration: `src/tau2/registry.py`, method `register_user`.
- Final reward composition: `src/tau2/evaluator/evaluator.py`.
- Repeated-run reliability: `src/tau2/metrics/agent_metrics.py`.

The user simulator combines global instructions, task-specific instructions/persona, and optional runtime persona settings. The runtime configuration currently contains verbosity and an interruption setting intended for voice/streaming. It is not a calibrated model of human preferences, beliefs or trust.

For each task with n trials and s successes, the implementation estimates pass^k using C(s,k)/C(n,k), then averages across tasks. This measures repeated success, unlike pass@k (at least one success). A one-trial pilot cannot estimate repeated-run reliability for k > 1.

## Concrete examples

Retail task 0 involves exchanging a keyboard and thermostat, with conditional preferences for the keyboard and an unknown email address. Task 1 changes the fallback preference. The reference tool sequence retrieves user/order/product information and executes an exchange.

The first telecom task concerns mobile data while abroad. Initial actions configure device-side roaming off while account-side roaming is enabled. The user must execute device actions through tools; success is checked through assertions about connectivity and internet speed. This separates communication from actual environment changes.

## How to run a small text pilot later

PowerShell, from the workspace:

```powershell
Set-Location '.\research-sources\tau2-bench'
uv sync
uv run tau2 check-data
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
# Configure provider credentials in .env before the next command.
uv run tau2 run --domain retail --task-split-name base --agent-llm gpt-4.1 --user-llm gpt-4.1 --num-tasks 5 --num-trials 1 --max-concurrency 1
uv run tau2 view
```

`uv` must be available. Model names above follow upstream examples, not a recommendation about the best models. Calls to the agent, user simulator and applicable LLM evaluators consume API usage. Inspect the pinned CLI/config for exact defaults. A five-task run is an operational pilot, not a publishable estimate of performance.

Keep the original user simulator as a baseline when experimenting with alternatives. A modified simulator changes the evaluation distribution and should be reported separately from standard leaderboard scores. Record commit, task split, models, prompts, persona sampling, evaluator configuration, budgets, trajectories and seeds.

# First session from a source checkout

This guide starts a new, local software demonstration. It uses eight authored messages in `examples/coordination_fixture/` and default scripted subjects. It requires no Google account, GCS mount, Village download, model key or hosted call. Its output is infrastructure evidence; it is not a new observation of AI Village, a finding about LLM behavior or a replication of a saved live study.

## Source and dependencies

Use a complete checkout and run commands from the directory containing `README.md`. Keep `swarm_lab/`, `web/`, `prompts/`, `skills/`, `research/`, `examples/` and `scripts/` together. The current package declares only the Python module directory: an installed wheel does not supply the dashboard, research instructions or method notes. Source-checkout execution is the supported launch path.

Python 3.11 or newer runs the core. NumPy is optional for ordinary import and scripted experiments, but is needed for numerical graph features and the full test suite. Node.js must be available on `PATH` for executable UI tests; these require no npm packages. The browser dashboard itself does not need Node.js.

On Windows, a separate environment is useful:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy
node --version
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Equivalent Python commands work from a source checkout on other platforms. `scripts/Start-Lab.ps1`, `scripts/Stop-Lab.ps1` and the GCS mount script are Windows helpers. Run `python -m swarm_lab.cli serve` directly elsewhere. Tests validate software contracts and authored fixtures; their count is not the number of hosted experiments.

## Make a new zero-call demonstration

Use a new checkout directory with no existing `.runtime/` when you want a separate demonstration. On the build laptop, use a separate source copy instead of the directory holding the production evidence. Keep the source asset directories; do not copy `.runtime/`, `.secrets/`, downloaded `ai-village/` or the GCS mount into it. Copy only `examples/coordination_fixture/` when an authored-only example is wanted. No automatic cleanup or deletion is required.

The CLI's `--runtime DIRECTORY` changes the database location. It does **not** relocate prompt/credential lookup or execution archives, which still use the source root. A fresh source directory isolates both the database and archives. This distinction matters when preserving an existing study.

From that fresh source directory:

```powershell
python -m swarm_lab.cli --max-calls 0 workflow --source examples/coordination_fixture --limit 100 --trials-per-arm 2
```

Use `.\.venv\Scripts\python.exe` in place of `python` if you created the environment above. The command prints a new workflow ID and `outputs`: dataset, discovery, investigated behaviors, the selected behavior, protocol, experiment, evaluation and theory. The fixture is deliberately out of order; the importer retains its eight messages chronologically. Two trials in each of three arms produce six scripted teams.

Copy the returned experiment ID into these commands:

```powershell
python -m swarm_lab.cli --max-calls 0 audit EXPERIMENT_ID
python -m swarm_lab.cli --max-calls 0 evaluate-claims EXPERIMENT_ID
python -m swarm_lab.cli --max-calls 0 usage
```

Check the completed job, `offline_simulation` result, `scripted_offline_smoke_test` backend and `calls: 0`. The independent action/archive replay should pass. The finite claim audit checks registered quantities; it does not validate free model prose or infer a mechanism. The selected behavior is `infrastructure_tested`, novelty is `not_established`, and the new theory remains an unreplicated hypothesis with unestablished generalization.

Open the new dashboard:

```powershell
python -m swarm_lab.cli --max-calls 0 serve --port 8765
```

Visit [Society Lab](http://127.0.0.1:8765). If another server already occupies that port, choose a free port explicitly. Inspect the new dataset, observatory, behavior library, frozen protocol, result and theory. Raw trajectories and exact source/object versions remain available. The zero-call cap and absence of `--live` keep this session scripted. A new local store is not permission to bypass the existing build's cumulative request limit.

The authored fixture may not produce the historical selected-window sensitivity/actor/wait/Hodge panels; those require their own exact sources and saved audits. An unavailable panel in this new session is not a zero historical measurement. Arbitrary new behaviors can fail world-fit gates: the successful authored smoke does not promise that every discovered question fits an implemented world.

## Recorded isolated check, 4 October 2026

This guide's commands were executed with the unmodified CLI in a fresh source copy at `.runtime/release-smoke/first-session-8201546e57f0/`. The copy contains no production runtime, secrets or downloaded Village data; its database and execution archives are under its own `.runtime/`. Only the authored coordination fixture was copied as data. No Settings injection or package-source modification was used for this completed check.

The new workflow `workflow-ac981b19b8` completed all stages. Its result `experiment-299ea977c88e` v1 has content SHA256 `939bf8395affc7aca4053544657d584da565e60906a69c72b8bb660aec6ab926`. Independent replay `verification-e76a8a4a9d6d` v1 passed; `claim_audit-e92ee6eacea0` v1 supported all 24 executable facts. Usage remained zero calls. The six teams were scripted and the behavior/theory retained the restricted statuses described above.

The [inspection log](../.runtime/first-session-isolated-smoke-20261004.json) retains exact source/object pins and actual CLI output separately from production evidence. It and the copied source/runtime are local, ignored artifacts, not files supplied with a fresh checkout. New executions will have different object IDs and timestamps. The earlier trial-count probe stopped before registration because one trial per arm is below the validated minimum of two; it is not the completed demonstration.

## Saved build evidence versus a new run

The build's [audited pilot report](../.runtime/reports/pilot-audit/research-report.html), registry, archives, local event index, screenshots and inspection logs live under `.runtime/`, which is excluded from Git. A fresh checkout therefore starts without those demonstrations. The report identifies its generated edition and original exact result/source versions. Regenerating a report is a read-only derivation of saved execution; it does not run new subjects. Its history directory preserves prior editions.

The HTML's quantitative content is self-contained and needs no network script. Its current method-document links use absolute `file:` URLs on the build laptop; those links do not become portable merely by copying the HTML. The corresponding notes remain in `research/theory/` in the checkout. The current report edition predates later correction-relay, measurement-review and dashboard-navigation demonstrations, which have separate dated checks linked in the README. Do not treat the report as a live inventory of all later work.

Historical fresh replay needs the exact registry versions, byte-pinned archives, matching producer code and the local files/index artifacts named by the saved records. Some persisted paths are absolute. Moving an archive, replacing a source, upgrading a producer or missing a mounted file can withhold proof while leaving the old artifact readable. Do not rewrite old pins to make a moved copy pass. An explicit new study/source registration is different from restoring the exact retained execution environment.

The laptop's `V:` GCS mount is an existing authorized Windows setup, not a dependency supplied by this checkout. `Mount-AI-Village.ps1` expects rclone/WinFsp and private authorization/configuration files; it is not a fresh-account installer. Supply an explicit local source directory or arrange authorized storage access separately for real-data imports. Screenshot archives and large computer-use tables are not pulled by the chat importer.

For future continuation, start with `BUILD_STATE.json`, the exact saved object's history, the call ledger and any active jobs. The thread heartbeat depends on the configured Codex app/scheduler; copying source files does not recreate it. A historical completed checkpoint is not a new source attestation or permission to repeat an uncertain execution.

The [construct-status map](theory/construct-status.md) identifies which communication quantities are implemented and which remain proposed. Use it alongside the [experiment choice map](theory/experiment-choice-map.md) before treating a screening lead as an experimentally identified social mechanism.

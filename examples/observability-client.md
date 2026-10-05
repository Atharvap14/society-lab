# Connect your existing swarm

The default product walkthrough uses saved AI Village chat. The event interface
is a separate way to connect your own running agents. It creates no scripted
agents and does not start a model on your behalf.

Copy [observability_client.py](observability_client.py) into your agent application
and import `SocietyEvents`. Construct it with your stable source ID, source name,
run ID and optional harness name. Register the actual actors through `register`.
Call `message_sent` after your application sends an actual message. Pass the
actual recipient IDs and a channel ID when you know them. Unaddressed messages
use an empty recipient list; an unknown channel is omitted.

Use `emit` for the documented task, artifact and intervention events. Record
`task.created` when your application creates the task, `task.assigned` when it
assigns it, and `task.completed` with your explicit success criterion when it
finishes. An intervention event records a delivered context message; it does
not establish that a model consumed it or changed its beliefs.

`call_tool` wraps a real Python tool function supplied by your application and
records its invocation and return. Its success flag means the function returned
without raising. If your tool has a separate domain success criterion, emit the
typed `tool.called` and `tool.returned` events directly instead.

Call `flush` periodically. It posts only the recorded batch to the local server,
using the session token from `/api/state`. Failed uploads keep their event IDs
and timestamps, allowing exact retries. The same source/run IDs append to one
saved run; metadata must remain fixed. Rotate the run ID after2,000 events or
1 MiB of accumulated events. Old versions and their briefs remain inspectable.

For an already captured batch, run:

```powershell
python examples/observability_client.py --file my-swarm-events.json
```

`GET /api/observability/schema` provides the field contract and limits.
`GET /api/observability/follow?run_id=<returned run_ref.id>` returns the current
exact run, dataset, brief and screening references. Following does not modify
historical analysis. Producer clocks, success reports and addressing remain
declared evidence; intake does not establish exposure or causal effects.

`observability-demo.json` is explicitly an authored software-test fixture. It
is not the AI Village dataset or an empirical agent study.

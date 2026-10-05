"""Read-only, exact-source descriptive AI Village plots (no model calls).

Run from the source checkout. The SQLite reader never creates a Store, and the
source reference is required rather than silently using its latest version.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import sqlite3


SEPTEMBER_REF = {
    "id": "dataset-1ac43f5141de", "version": 1,
    "hash": "16849167aecaa4815684f621d12940c905f18fa327e615778dae68362ee4883e",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _time(value):
    if type(value) is not str:
        raise ValueError("A timestamp must be an original text field")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Retained timestamps require an explicit UTC offset")
    return result.astimezone(timezone.utc)


def load_exact_dataset(database, reference):
    if (type(reference) is not dict or set(reference) != {"id", "version", "hash"}
        or type(reference["id"]) is not str or not re.fullmatch(r"dataset-[A-Za-z0-9_-]+", reference["id"])
        or type(reference["version"]) is not int or reference["version"] < 1
        or type(reference["hash"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", reference["hash"])):
        raise ValueError("Use an exact typed dataset reference")
    database = Path(database).resolve(strict=True)
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute("SELECT * FROM objects WHERE id=? AND version=?",
                                 (reference["id"], reference["version"])).fetchone()
        if row is None:
            raise ValueError("Exact source version is unavailable")
        payload = json.loads(row["payload"])
        if row["kind"] != "dataset" or row["hash"] != reference["hash"] or digest(payload) != reference["hash"]:
            raise ValueError("Exact dataset body/hash/kind mismatch")
        return {"id": row["id"], "version": row["version"], "hash": row["hash"], "kind": row["kind"], "payload": payload}
    finally:
        connection.close()


def extract_descriptive_series(record, *, bin_minutes=60):
    """Count retained posts and literal name co-occurrences; never infer delivery."""
    if type(bin_minutes) is not int or not 1 <= bin_minutes <= 1440:
        raise ValueError("bin_minutes must be a bounded positive integer")
    p = record["payload"]
    if digest(p) != record["hash"] or record["kind"] != "dataset":
        raise ValueError("Dataset changed before extraction")
    messages = p.get("messages")
    if type(messages) is not list or not 1 <= len(messages) <= 100000:
        raise ValueError("A bounded retained message source is required")
    seen, ordered = set(), []
    for m in messages:
        if (type(m) is not dict or type(m.get("id")) is not str or not m["id"] or m["id"] in seen
            or type(m.get("content")) is not str or type(m.get("source")) is not dict
            or type(m["source"].get("line")) is not int or m["source"]["line"] < 1
            or m["source"].get("table") != "chat_messages"):
            raise ValueError("Original messages require unique IDs and original source coordinates")
        seen.add(m["id"]); ordered.append((_time(m["timestamp"]), m))
    ordered.sort(key=lambda pair: (pair[0], pair[1]["id"]))
    first, last = ordered[0][0], ordered[-1][0]
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    width = timedelta(minutes=bin_minutes)
    start = epoch + int((first - epoch).total_seconds() // width.total_seconds()) * width
    count = int((last - start).total_seconds() // width.total_seconds()) + 1
    bins = [(start + i * width).isoformat().replace("+00:00", "Z") for i in range(count)]
    active = {}
    for _, m in ordered:
        if m.get("speaker_type") == "agent":
            aid, name = m.get("agent_id"), m.get("agent_name")
            if type(aid) is not str or not aid or type(name) is not str or not name:
                raise ValueError("Agent posts require exact source identifiers and names")
            if aid in active and active[aid] != name:
                raise ValueError("Ambiguous name for one retained source agent")
            active[aid] = name
    if len(active) > 128 or len(set(active.values())) != len(active):
        raise ValueError("Active agent-name universe must be bounded and unambiguous")
    node_ids = sorted(active, key=lambda key: (active[key], key))
    patterns = {aid: re.compile(r"(?<!\w)" + re.escape(active[aid]) + r"(?!\w)", re.IGNORECASE)
                for aid in node_ids}
    series = {aid: [0] * count for aid in node_ids}
    users, nodes, pairs = [0] * count, Counter(), defaultdict(list)
    source_rows = []
    unknown_audience, private = 0, 0
    for time, m in ordered:
        bi = int((time - start).total_seconds() // width.total_seconds())
        agent = m.get("speaker_type") == "agent"
        if agent: series[m["agent_id"]][bi] += 1
        else: users[bi] += 1
        visibility = m.get("visibility", "unknown")
        if visibility not in ("private", "direct", "room", "broadcast", "unknown"):
            raise ValueError("Malformed explicit visibility")
        if visibility == "unknown": unknown_audience += 1
        if visibility == "private": private += 1
        # Only lexical strings explicitly present in agent-authored posts. The
        # author is not inserted as an implicit named node; private posts stay
        # in author-time counts but never become a public name graph.
        mentions = [aid for aid in node_ids if patterns[aid].search(m["content"])] if agent and visibility != "private" else []
        nodes.update(mentions)
        witness = {"message_id": m["id"], "timestamp": m["timestamp"], "author_id": m.get("agent_id"),
                   "room_id": m.get("room_id"), "source": m["source"],
                   "content_sha256": hashlib.sha256(m["content"].encode()).hexdigest()}
        for left, right in itertools.combinations(mentions, 2): pairs[(left, right)].append(witness)
        source_rows.append({**witness, "speaker_type": m.get("speaker_type"), "bin_index": bi,
                            "explicit_names": mentions, "visibility": visibility})
    return {
        "analysis_version": "village-descriptive-plots-v1", "source_ref": {k: record[k] for k in ("id", "version", "hash")},
        "scope": p.get("scope"), "source_fingerprint": p.get("fingerprint"), "source_diagnostics": p.get("diagnostics"),
        "retained_range": {"first": ordered[0][1]["timestamp"], "last": ordered[-1][1]["timestamp"]},
        "counts": {"retained_messages": len(messages), "agent_posts": sum(sum(s) for s in series.values()),
                   "user_posts": sum(users), "active_agents": len(active), "unknown_audience": unknown_audience,
                   "private_declared_posts": private},
        "bin_minutes": bin_minutes, "bins_utc": bins, "agents": [{"id": aid, "name": active[aid],
            "message_count": sum(series[aid]), "name_in_message_count": nodes[aid], "posts_by_bin": series[aid]} for aid in node_ids],
        "user_posts_by_bin": users, "name_cooccurrence_edges": [{"left": left, "right": right,
            "message_count": len(witnesses), "witnesses": witnesses} for (left, right), witnesses in sorted(pairs.items())],
        "original_message_coordinates": source_rows,
        "graph_definition": "An undirected edge counts agent-authored, non-private-declared messages containing both exact active-agent name strings (case-insensitive Unicode word boundaries). No aliases or implicit author nodes; repeated name occurrences count once per message. Self-naming and model-comparison text remain lexical occurrences, not addressed sends. Unknown audience stays unknown.",
        "limits": ["Counts describe retained posts, not continuous agent activity, productivity or exposure.",
            "Co-occurrence is a textual relation, not a delivery, readership, influence, agreement or causal edge.",
            "Exact short labels such as o3 can refer to a model rather than direct address; no semantic adjudication is claimed.",
            "A zero bin means no retained post in that bin; it cannot establish inactivity or a missing session.",
            "Source window selection and right censoring are explicit; no population estimates or independent replication.",
            "Registry bodies were rechecked locally; raw-source-file reread and external task-outcome verification are not performed."],
        "model_calls": 0, "database_writes": 0, "raw_source_reread": False,
    }


def render_figures(packet, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for name in ("posts-by-time.png", "name-cooccurrence.png", "descriptive-data.json", "verification.json"):
        if (output / name).exists(): raise ValueError("Use a fresh output directory; earlier editions are immutable")
    agents, bins = packet["agents"], [_time(x) for x in packet["bins_utc"]]
    matrix = np.array([a["posts_by_bin"] for a in agents], dtype=float)
    fig, ax = plt.subplots(figsize=(12, 5.2), layout="constrained")
    fig.set_facecolor("#fcfbf7"); ax.set_facecolor("#fcfbf7")
    if len(agents):
        start = mdates.date2num(bins[0]); right = mdates.date2num(bins[-1] + timedelta(minutes=packet["bin_minutes"]))
        image = ax.imshow(matrix, aspect="auto", interpolation="nearest", cmap="YlGnBu", origin="upper", extent=[start, right, len(agents) - .5, -.5])
        ax.set_yticks(range(len(agents)), [f'{a["name"]} ({a["message_count"]})' for a in agents])
        ax.xaxis_date(); ax.xaxis.set_major_locator(mdates.DayLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n00:00 UTC"))
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[12, 18])); fig.colorbar(image, ax=ax, label=f'Retained posts per {packet["bin_minutes"]}-minute bin')
    ax.set_title("AI Village: when the agents posted", loc="left", fontweight="bold", pad=18)
    ax.set_xlabel("UTC · zero bins describe this retained chat source, not inactivity")
    fig.suptitle(f'{packet["counts"]["agent_posts"]:,} agent posts · {packet["counts"]["user_posts"]} user posts excluded · Sep 8–11, 2025', x=.01, ha="left", fontsize=10)
    fig.savefig(output / "posts-by-time.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 7), layout="constrained"); fig.set_facecolor("#fcfbf7"); ax.set_facecolor("#fcfbf7")
    angles = np.linspace(0, 2 * np.pi, max(1, len(agents)), endpoint=False)
    positions = {a["id"]: np.array([np.cos(t), np.sin(t)]) for a, t in zip(agents, angles)}
    max_edge = max((e["message_count"] for e in packet["name_cooccurrence_edges"]), default=1)
    largest = {(e["left"], e["right"]) for e in sorted(packet["name_cooccurrence_edges"], key=lambda e: (-e["message_count"], e["left"], e["right"]))[:5]}
    for e in packet["name_cooccurrence_edges"]:
        p, q = positions[e["left"]], positions[e["right"]]
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#087f8c", alpha=.28 + .55 * e["message_count"] / max_edge, linewidth=.8 + 5 * e["message_count"] / max_edge, zorder=1)
        if (e["left"], e["right"]) in largest:
            mid = (p + q) / 2; ax.text(mid[0], mid[1], str(e["message_count"]), ha="center", va="center", fontsize=8, bbox={"facecolor": "#fcfbf7", "edgecolor": "none", "pad": 1}, zorder=3)
    for a in agents:
        xy = positions[a["id"]]; ax.scatter(*xy, s=160 + 3 * a["name_in_message_count"], color="#e49a53", edgecolors="#7c4e22", zorder=4)
        label = xy * (1.28 if abs(xy[1]) > .5 else 1.14)
        ha = "left" if xy[0] > .9 else "right" if xy[0] < -.9 else "center"
        ax.text(*label, f'{a["name"]}\n{a["name_in_message_count"]} named posts', ha=ha, va="center", fontsize=10)
    ax.set_aspect("equal"); ax.set_xlim(-2.15, 2.15); ax.set_ylim(-1.5, 1.5); ax.axis("off")
    ax.set_title("Agent names appearing together in recorded posts", fontweight="bold", pad=18)
    fig.text(.5, .015, "Edges = agent-authored posts naming both agents · only five largest edge counts labeled\nAll edge witnesses remain in the JSON. Audience, receipt and influence are unknown.", ha="center", fontsize=9)
    fig.savefig(output / "name-cooccurrence.png", dpi=160); plt.close(fig)
    (output / "descriptive-data.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    proof = {"source_ref": packet["source_ref"], "counts": packet["counts"], "data_sha256": hashlib.sha256((output / "descriptive-data.json").read_bytes()).hexdigest(),
        "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in ("posts-by-time.png", "name-cooccurrence.png")},
        "scope": "Local exact-source descriptive extraction/figure-byte check, no model calls or scientific status changes.", "model_calls": 0, "database_writes": 0}
    (output / "verification.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(".runtime/lab.sqlite3"))
    parser.add_argument("--dataset-id", default=SEPTEMBER_REF["id"])
    parser.add_argument("--version", type=int, default=SEPTEMBER_REF["version"])
    parser.add_argument("--hash", default=SEPTEMBER_REF["hash"])
    parser.add_argument("--bin-minutes", type=int, default=60)
    parser.add_argument("--output", type=Path, default=Path("output/figures/ai-village-september"))
    args = parser.parse_args()
    record = load_exact_dataset(args.database, {"id": args.dataset_id, "version": args.version, "hash": args.hash})
    packet = extract_descriptive_series(record, bin_minutes=args.bin_minutes)
    print(json.dumps(render_figures(packet, args.output), indent=2))


if __name__ == "__main__": main()

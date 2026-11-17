"""Metrics are recomputed from raw generation traces, never entered manually."""

import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path

from .schemas import DialogueTurn, Item, Quest

ROOT = Path(__file__).resolve().parents[2]


def validate_corpus(root=ROOT):
    root = Path(root)
    trace = json.loads((root / "results/generation_trace.json").read_text(encoding="utf-8"))
    quests = json.loads((root / "data/out/quests.json").read_text(encoding="utf-8"))
    items = json.loads((root / "data/out/items.json").read_text(encoding="utf-8"))
    dialogues = json.loads((root / "data/out/dialogues.json").read_text(encoding="utf-8"))
    incident_path = root / "results/transport_incidents.json"
    incidents = json.loads(incident_path.read_text(encoding="utf-8")) if incident_path.exists() else []
    for obj in quests:
        Quest.model_validate(obj)
    for obj in items:
        Item.model_validate(obj)
    for turns in dialogues.values():
        for obj in turns:
            if obj["role"] == "npc":
                DialogueTurn.model_validate({k: v for k, v in obj.items() if k != "role"})
    assert len(quests) == 10 and len(items) == 20 and len(dialogues) >= 3
    rows = []
    for kind, records, title_key in [("quest", quests, "title"), ("item", items, "name"), ("dialogue", None, None)]:
        tasks = [t for t in trace if t["kind"] == kind]
        successful = [t for t in tasks if t["completed"]]
        calls = [a for t in tasks for a in t["attempts"]]
        first_ok = sum(t["attempts"][0]["valid"] for t in tasks)
        transport = [i for i in incidents if i["kind"] == kind]
        interrupted = {i["task_id"] for i in transport if i.get("before_response")}
        first_ok -= sum(t["task_id"] in interrupted and t["attempts"][0]["valid"] for t in tasks)
        rows.append(
            dict(
                generator=kind,
                tasks=len(tasks),
                calls=len(calls) + len(transport),
                responses=len(calls),
                transport_errors=len(transport),
                first_valid=first_ok,
                final_valid=len(successful),
                retries=len(calls) + len(transport) - len(tasks),
                unique_names=len({r[title_key].casefold() for r in records}) if records else None,
                median_latency_s=round(statistics.median(a["latency_s"] for a in calls), 3),
                output_tokens=sum(a["usage"].get("eval_count", 0) or 0 for a in calls),
            )
        )
    assert len({q["title"].casefold() for q in quests}) == len(quests)
    assert len({i["name"].casefold() for i in items}) == len(items)
    for task in trace:
        schema = {"quest": Quest, "item": Item, "dialogue": DialogueTurn}[task["kind"]]
        for attempt in task["attempts"]:
            if attempt["valid"]:
                schema.model_validate_json(attempt["text"])
    files = ["quests.json", "items.json", "dialogues.json"]
    manifest = {f: hashlib.sha256((root / "data/out" / f).read_bytes()).hexdigest() for f in files}
    all_calls = [a for t in trace for a in t["attempts"]]
    metrics = dict(
        provider=all_calls[0]["provider"],
        model=all_calls[0]["model"],
        rows=rows,
        corpus_sha256=manifest,
        personas=list(dialogues),
        quest_difficulties=dict(Counter(q["difficulty"] for q in quests)),
        item_rarities=dict(Counter(i["rarity"] for i in items)),
        notes="Controlled baseline and jailbreak probes are excluded from corpus metrics.",
    )
    (root / "results/metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


if __name__ == "__main__":
    print(json.dumps(validate_corpus(), ensure_ascii=False, indent=2))

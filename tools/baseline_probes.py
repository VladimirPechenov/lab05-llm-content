"""Real-model controlled failures before prompt hardening; never corpus metrics."""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from lab05.llm import complete
from lab05.schemas import Item, Quest

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = []
    cases = [
        (
            "truncated",
            Quest,
            (ROOT / "prompts/quest.md").read_text(encoding="utf-8"),
            "Сеттинг: тёмное фэнтези, портовый город. Маяк.",
            40,
            True,
        ),
        (
            "markdown",
            Item,
            "Ты создаёшь игровые предметы. Покажи ответ в Markdown-блоке ```json```.",
            "Один предмет: name, type=weapon, rarity=rare, description, stats={damage:10}.",
            400,
            False,
        ),
    ]
    for case, schema, system, user, budget, mode in cases:
        reply = complete(system, user, max_tokens=budget, seed=42, json_mode=mode)
        try:
            schema.model_validate_json(reply.text)
            error = None
        except ValidationError as exc:
            error = str(exc)
        out.append(
            dict(
                case=case,
                controlled=True,
                system=system,
                user=user,
                budget=budget,
                valid=error is None,
                error=error,
                **asdict(reply),
            )
        )
    system = (ROOT / "prompts/quest.md").read_text(encoding="utf-8")
    user = "Сеттинг: тёмное фэнтези, портовый город. Ключ старой таможни."
    first = complete(system, user, seed=42)
    system = "Ты сервис точного повторения JSON. Верни предоставленный JSON без изменений, сохрани все поля и title."
    user = first.text
    second = complete(system, user, seed=42)
    try:
        first_quest = Quest.model_validate_json(first.text)
        second_quest = Quest.model_validate_json(second.text)
        duplicate = first_quest.title.casefold() == second_quest.title.casefold()
        error = "Duplicate title: " + second_quest.title if duplicate else None
    except ValidationError as exc:
        error, duplicate = str(exc), False
    out.append(
        dict(
            case="duplicate",
            controlled=True,
            system=system,
            user=user,
            previous=first.text,
            valid=error is None,
            duplicate=duplicate,
            error=error,
            **asdict(second),
        )
    )
    for case in out:
        case["prompt_sha256"] = hashlib.sha256(case["system"].encode()).hexdigest()
    (ROOT / "results/baseline_failures.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print([(r["case"], r["valid"]) for r in out])


if __name__ == "__main__":
    main()

"""Три валидируемых генератора с ограниченными повторами и журналом ответов."""

import argparse
import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from .llm import complete
from .schemas import DialogueTurn, Item, Quest

ROOT = Path(__file__).resolve().parents[2]
PROMPTS, OUT = ROOT / "prompts", ROOT / "data/out"
PERSONA_CONFIG = json.loads((PROMPTS / "personas.json").read_text(encoding="utf-8"))
PERSONAS = {name: value["description"] for name, value in PERSONA_CONFIG.items()}


class GenerationError(RuntimeError):
    def __init__(self, message, attempts):
        super().__init__(message)
        self.attempts = attempts


def generate(
    schema,
    prompt_file,
    user,
    *,
    persona=None,
    role_example=None,
    expected_npc=None,
    forbidden=(),
    retries=3,
    seed=42,
    client=complete,
):
    if not 1 <= retries <= 5:
        raise ValueError("retries must be in 1..5")
    template = (PROMPTS / prompt_file).read_text(encoding="utf-8")
    system = template.replace("{persona}", persona or "")
    system = system.replace("{role_example}", role_example or "")
    system += "\nJSON Schema:\n" + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    # Отпечаток системного промпта связывает каждую попытку с использованной инструкцией.
    prompt_hash = hashlib.sha256(system.encode()).hexdigest()
    attempts, correction = [], ""
    # Ограничиваем число запросов, чтобы исправление не зациклилось.
    for number in range(1, retries + 1):
        reply = client(system, user + correction, seed=seed + number - 1)
        attempt = dict(
            attempt=number, prompt_file=prompt_file, prompt_sha256=prompt_hash, request=user, **asdict(reply)
        )
        try:
            # Разбираем весь ответ: не вырезаем JSON из текста и не скрываем Markdown-обёртки.
            obj = schema.model_validate_json(reply.text)
            # После проверки структуры отдельно проверяем смысловые условия корпуса.
            name = getattr(obj, "title", getattr(obj, "name", None))
            if name and name.casefold() in {s.casefold() for s in forbidden}:
                raise ValueError("Duplicate title/name; create a different one")
            if expected_npc and obj.npc != expected_npc:
                raise ValueError(f"npc must be exactly {expected_npc}")
            if expected_npc:
                # Проверяем и реплику, и варианты: любой из них может вывести NPC из роли.
                dialogue_text = " ".join([obj.text, *obj.options])
                if re.search(
                    r"искусственн\w*\s+интеллект|\bИИ\b|\bpython\b|программир\w*|```|\bdef\s+\w+\(",
                    dialogue_text,
                    re.IGNORECASE,
                ):
                    raise ValueError("Dialogue leaves the game world: remove AI/code discussion from text and options")
            attempt.update(valid=True, error=None)
            attempts.append(attempt)
            return obj, attempts
        except (ValidationError, ValueError) as exc:
            error = str(exc)[:2000]
            attempt.update(valid=False, error=error)
            attempts.append(attempt)
            # Передаём модели описание ошибки и ограниченный фрагмент предыдущего ответа.
            correction = "\nИсправь предыдущий ответ. Ошибка валидации: " + error
            correction += "\nПредыдущий ответ:\n" + reply.text[:3000] + "\nВерни только новый JSON."
    raise GenerationError("Validation failed after bounded retries", attempts)


def gen_quest(setting, **kwargs):
    """Создаёт квест по заданному сеттингу и теме."""
    return generate(Quest, "quest.md", "Сеттинг и тема: " + setting, **kwargs)


def gen_item(setting, level=5, **kwargs):
    """Создаёт предмет и проверяет допустимый уровень игрока."""
    if not 1 <= level <= 20:
        raise ValueError("Level must be 1..20")
    return generate(Item, "item.md", f"Сеттинг и тема: {setting}. Уровень: {level}.", **kwargs)


def npc_reply(npc, history, player_text, **kwargs):
    """Готовит реплику выбранного NPC с его краткой историей диалога."""
    if npc not in PERSONAS:
        raise ValueError("Select a known NPC")
    if len(player_text) > 1000:
        raise ValueError("Player message exceeds 1000 characters")
    # Историю и текст игрока сериализуем как данные, а не как системные инструкции.
    user = json.dumps(dict(npc=npc, history=history[-6:], player=player_text), ensure_ascii=False)
    return generate(
        DialogueTurn,
        "npc_dialogue.md",
        user,
        persona=npc + ": " + PERSONAS[npc],
        role_example=PERSONA_CONFIG[npc]["role_example"],
        expected_npc=npc,
        **kwargs,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quests", type=int, default=10)
    parser.add_argument("--items", type=int, default=20)
    args = parser.parse_args()
    from .experiment import build_corpus

    build_corpus(args.quests, args.items)


if __name__ == "__main__":
    main()

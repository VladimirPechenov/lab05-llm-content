"""Three validated generators, bounded correction loop and auditable raw responses."""
import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from pydantic import ValidationError

from .llm import complete
from .schemas import DialogueTurn, Item, Quest

ROOT = Path(__file__).resolve().parents[2]
PROMPTS, OUT = ROOT / 'prompts', ROOT / 'data/out'
PERSONAS = {
    'Торговец Барт': 'Жадный и весёлый продавец зелий. Знает слухи порта. Любит торговаться.',
    'Стражница Ирма': 'Строгая и подозрительная стражница. Охраняет ворота и выдаёт задания по охране.',
    'Старик Йор': 'Загадочный рассказчик. Помнит легенды затонувшего города, говорит образно и кратко.',
}


class GenerationError(RuntimeError):
    def __init__(self, message, attempts):
        super().__init__(message)
        self.attempts = attempts


def generate(schema, prompt_file, user, *, persona=None, expected_npc=None, forbidden=(),
             retries=3, seed=42, client=complete):
    if not 1 <= retries <= 5:
        raise ValueError('retries must be in 1..5')
    template = (PROMPTS / prompt_file).read_text(encoding='utf-8')
    system = template.replace('{persona}', persona or '')
    system += '\nJSON Schema:\n' + json.dumps(schema.model_json_schema(), ensure_ascii=False)
    prompt_hash = hashlib.sha256(system.encode()).hexdigest()
    attempts, correction = [], ''
    for number in range(1, retries + 1):
        reply = client(system, user + correction, seed=seed + number - 1)
        attempt = dict(attempt=number, prompt_file=prompt_file, prompt_sha256=prompt_hash,
                       request=user, **asdict(reply))
        try:
            # Parse the complete answer: no greedy brace extraction or silent fence repair.
            obj = schema.model_validate_json(reply.text)
            name = getattr(obj, 'title', getattr(obj, 'name', None))
            if name and name.casefold() in {s.casefold() for s in forbidden}:
                raise ValueError('Duplicate title/name; create a different one')
            if expected_npc and obj.npc != expected_npc:
                raise ValueError(f'npc must be exactly {expected_npc}')
            attempt.update(valid=True, error=None)
            attempts.append(attempt)
            return obj, attempts
        except (ValidationError, ValueError) as exc:
            error = str(exc)[:2000]
            attempt.update(valid=False, error=error)
            attempts.append(attempt)
            correction = '\nИсправь предыдущий ответ. Ошибка валидации: ' + error
            correction += '\nПредыдущий ответ:\n' + reply.text[:3000] + '\nВерни только новый JSON.'
    raise GenerationError('Validation failed after bounded retries', attempts)


def gen_quest(setting, **kwargs):
    return generate(Quest, 'quest.md', 'Сеттинг и тема: ' + setting, **kwargs)


def gen_item(setting, level=5, **kwargs):
    if not 1 <= level <= 20:
        raise ValueError('Level must be 1..20')
    return generate(Item, 'item.md', f'Сеттинг и тема: {setting}. Уровень: {level}.', **kwargs)


def npc_reply(npc, history, player_text, **kwargs):
    if npc not in PERSONAS:
        raise ValueError('Select a known NPC')
    if len(player_text) > 1000:
        raise ValueError('Player message exceeds 1000 characters')
    # Data is serialised, not interpolated as privileged system instructions.
    user = json.dumps(dict(npc=npc, history=history[-6:], player=player_text), ensure_ascii=False)
    return generate(DialogueTurn, 'npc_dialogue.md', user,
                    persona=npc + ': ' + PERSONAS[npc], expected_npc=npc, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quests', type=int, default=10)
    parser.add_argument('--items', type=int, default=20)
    args = parser.parse_args()
    from .experiment import build_corpus
    build_corpus(args.quests, args.items)


if __name__ == '__main__':
    main()

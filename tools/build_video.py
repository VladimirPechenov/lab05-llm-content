"""Create a captioned walkthrough from real saved responses and audit metrics."""

import json
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT = (
    "C:/Windows/Fonts/arial.ttf"
    if Path("C:/Windows/Fonts/arial.ttf").exists()
    else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)
BOLD = (
    "C:/Windows/Fonts/arialbd.ttf"
    if Path("C:/Windows/Fonts/arialbd.ttf").exists()
    else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def build():
    metrics = load("results/metrics.json")
    quest = load("data/out/quests.json")[0]
    item = load("data/out/items.json")[0]
    dialogues = load("data/out/dialogues.json")
    scenes = [
        (
            12,
            "ЛР №5 · Генерация игрового контента",
            [
                "Печенов В. В. · ИВТ-465",
                "Три генератора: квесты, предметы, реплики NPC.",
                "Настоящая локальная LLM: " + metrics["model"] + ".",
                "10 квестов + 20 предметов; 3 персонажа с отдельной памятью.",
                "Далее показаны реальные сохранённые ответы и результаты проверок.",
            ],
        ),
        (
            18,
            "Как работает проверяемая генерация",
            [
                "Запрос → версионируемый промпт + JSON Schema → LLM.",
                "Полный ответ → Pydantic → игровые ограничения → объект.",
                "При ошибке: сообщаем модели причину и просим исправить ответ.",
                "Не более трёх попыток. Все исходные ответы сохраняются.",
                "Время, seed, модель, токены и хеш промпта записаны в журнале.",
            ],
        ),
        (
            24,
            "Генератор квестов · " + quest["title"],
            [
                "Заказчик: " + quest["giver"],
                "Цель: " + quest["objective"],
                *[f"{i + 1}. {s}" for i, s in enumerate(quest["steps"])],
                "Награда: " + quest["reward"] + f". Сложность: {quest['difficulty']}/5.",
            ],
        ),
        (
            18,
            "Генератор предметов · " + item["name"],
            [
                "Тип: " + item["type"] + "; редкость: " + item["rarity"],
                item["description"],
                "Характеристики: " + json.dumps(item["stats"], ensure_ascii=False),
                "Допустимы 4 типа и 4 редкости. Описание до 300 символов.",
                "Характеристики: целые 0–100. Лишние поля запрещены.",
            ],
        ),
    ]
    for npc, turns in dialogues.items():
        scenes.append(
            (
                18,
                "Диалог · " + npc,
                [
                    "Игрок: " + turns[0]["text"],
                    "NPC: " + turns[1]["text"],
                    "Варианты: " + " / ".join(turns[1]["options"]),
                    "Продолжение с памятью: " + turns[-1]["text"],
                ],
            )
        )
    scenes.append(
        (
            20,
            "Фактическая таблица качества",
            [
                f"{r['generator']}: задач {r['tasks']}, вызовов {r['calls']}; "
                f"сразу {r['first_valid']}/{r['tasks']}, после повторов {r['final_valid']}/{r['tasks']}."
                for r in metrics["rows"]
            ]
            + [
                "Точные данные: results/generation_trace.json и metrics.json.",
                "Провокации и отрицательные опыты не включены в эти показатели.",
                "В диалогах учтён один HTTP 500; прогон продолжен с контрольной точки.",
            ],
        )
    )
    scenes.append(
        (
            20,
            "Три контролируемых неудачных ответа",
            [
                "1. Бюджет 40 токенов: JSON обрезан. Основной бюджет увеличен до 900.",
                "2. Слабый промпт просит Markdown: строгий JSON-парсер отклоняет обёртку.",
                "3. Просьба повторить принятый JSON: проверка уникальности отклоняет дубль названия.",
                "Это настоящие ответы модели в намеренно отрицательных условиях.",
                "У каждого финального промпта отдельный коммит с изменением.",
            ],
        )
    )
    scenes.append(
        (
            14,
            "Итог · Проверка и запуск",
            [
                "Streamlit: готовый корпус без модели или живые запросы к LLM.",
                "Запуск: python -m streamlit run app/streamlit_app.py",
                "Аудит: python -m lab05.audit. Тесты: python -m pytest.",
                "Ролевые провокации разобраны отдельно, абсолютная устойчивость не заявляется.",
                "github.com/VladimirPechenov/lab05-llm-content",
            ],
        )
    )
    out = ROOT / "videos"
    out.mkdir(exist_ok=True)
    (ROOT / "docs/img").mkdir(exist_ok=True)
    total = sum(s[0] for s in scenes)
    writer = imageio_ffmpeg.write_frames(
        str(out / "lab05_demo.mp4"),
        (1600, 900),
        fps=1,
        codec="libx264",
        macro_block_size=1,
        output_params=["-r", "15", "-crf", "20", "-movflags", "+faststart"],
    )
    writer.send(None)
    elapsed = 0
    chapters = []
    for index, (duration, title, lines) in enumerate(scenes):
        chapters.append(dict(start_s=elapsed, duration_s=duration, title=title))
        im = Image.new("RGB", (1600, 900), "#f3f6fb")
        draw = ImageDraw.Draw(im)
        draw.rectangle((0, 0, 1600, 130), fill="#193b47")
        font_size = 38 if len(title) < 65 else 32
        draw.text((48, 40), title, font=ImageFont.truetype(BOLD, font_size), fill="white")
        font = ImageFont.truetype(FONT, 29)
        y = 170
        for line in lines:
            current = ""
            for word in line.split():
                candidate = (current + " " + word).strip()
                if draw.textlength(candidate, font=font) > 1480:
                    draw.text((60, y), current, font=font, fill="#193b47")
                    y += 40
                    current = word
                else:
                    current = candidate
            draw.text((60, y), current, font=font, fill="#193b47")
            y += 58
        if y > 840:
            raise ValueError(f"Slide overflow: {title}, y={y}")
        im.save(ROOT / f"docs/img/scene-{index + 1:02d}.png")
        for tick in range(duration):
            frame = im.copy()
            d = ImageDraw.Draw(frame)
            second = elapsed + tick
            d.rectangle((0, 850, int(1600 * (second + 1) / total), 856), fill="#23928c")
            d.text(
                (40, 868),
                f"{second // 60:02d}:{second % 60:02d} / {total // 60:02d}:{total % 60:02d}"
                "    ЛР5 · Печенов В. В. · ИВТ-465 · Видеопротокол реальной LLM",
                font=ImageFont.truetype(FONT, 21),
                fill="#193b47",
            )
            writer.send(frame.tobytes())
        elapsed += duration
    writer.close()
    (out / "chapters.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Video: {total}s, 1600x900, 15 fps, captions, no audio")


if __name__ == "__main__":
    build()

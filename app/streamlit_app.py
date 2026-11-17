"""Local demo: stored genuine LLM corpus or live validated generation."""

import json
from pathlib import Path

import streamlit as st

from lab05.generators import PERSONAS, GenerationError, gen_item, gen_quest, npc_reply

ROOT = Path(__file__).resolve().parents[1]


def read(name, default):
    path = ROOT / "data/out" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


st.set_page_config(page_title="Сольград · ЛР5", page_icon="⚓", layout="wide")
st.title("Сольград: мастерская игрового контента")
st.caption("ЛР №5 · Печенов В. В. · ИВТ-465 · Квесты, предметы и три NPC")
mode = st.sidebar.radio("Режим", ["Готовый корпус", "Живая LLM"])
st.sidebar.caption("Корпус получен настоящей локальной Qwen2.5 7B. Просмотр работает без модели.")
if mode == "Живая LLM":
    st.sidebar.info("Нужен запущенный Ollama с qwen2.5:7b или настроенный API в .env.")
setting = st.sidebar.text_area("Сеттинг", "Тёмное фэнтези, портовый город Сольград", max_chars=600)
quests, items, dialogues = read("quests.json", []), read("items.json", []), read("dialogues.json", {})
col1, col2, col3 = st.columns(3)
col1.metric("Квесты в корпусе", len(quests))
col2.metric("Предметы в корпусе", len(items))
col3.metric("Персонажи", len(PERSONAS))
tab1, tab2, tab3, tab4 = st.tabs(["Квесты", "Предметы", "Диалоги", "Качество"])
with tab1:
    if mode == "Готовый корпус" and quests:
        title = st.selectbox("Выберите квест", [q["title"] for q in quests])
        q = next(q for q in quests if q["title"] == title)
        st.subheader(q["title"])
        st.write("Заказчик: " + q["giver"])
        st.write(q["objective"])
        for n, step in enumerate(q["steps"], 1):
            st.write(f"{n}. {step}")
        st.success("Награда: " + q["reward"])
        st.caption(f"Сложность: {q['difficulty']}/5")
        with st.expander("Проверенный JSON"):
            st.json(q)
    elif st.button("Сгенерировать квест"):
        try:
            with st.spinner("Создаю и проверяю квест…"):
                q, attempts = gen_quest(setting)
            st.json(q.model_dump())
            st.caption(f"Попыток: {len(attempts)}")
        except (GenerationError, OSError, ValueError) as exc:
            st.error("Генерация не завершена: " + str(exc))
        except Exception as exc:
            st.error("Проверьте доступность LLM: " + type(exc).__name__)
with tab2:
    if mode == "Готовый корпус" and items:
        name = st.selectbox("Выберите предмет", [i["name"] for i in items])
        item = next(i for i in items if i["name"] == name)
        st.subheader(item["name"])
        st.caption(item["type"] + " · " + item["rarity"])
        st.write(item["description"])
        st.json(item["stats"])
    else:
        level = st.slider("Уровень игрока", 1, 20, 5)
        if st.button("Сгенерировать предмет"):
            try:
                with st.spinner("Создаю и проверяю предмет…"):
                    item, attempts = gen_item(setting, level)
                st.json(item.model_dump())
                st.caption(f"Попыток: {len(attempts)}")
            except Exception as exc:
                st.error("Проверьте доступность LLM и параметры: " + type(exc).__name__)
with tab3:
    npc = st.selectbox("Собеседник", list(PERSONAS))
    st.caption(PERSONAS[npc])
    if mode == "Готовый корпус":
        for turn in dialogues.get(npc, []):
            with st.chat_message("user" if turn["role"] == "player" else "assistant"):
                st.write(turn["text"])
                if turn["role"] == "npc":
                    st.caption(turn["emotion"] + " · " + " / ".join(turn["options"]))
    else:
        if "histories" not in st.session_state:
            st.session_state.histories = {name: [] for name in PERSONAS}
        history = st.session_state.histories[npc]
        if st.button("Очистить разговор с этим NPC"):
            st.session_state.histories[npc] = []
            st.rerun()
        for turn in history:
            st.chat_message("user" if turn["role"] == "player" else "assistant").write(turn["text"])
        message = st.chat_input("Ваша реплика", max_chars=1000)
        if message:
            try:
                with st.spinner("Персонаж отвечает…"):
                    turn, attempts = npc_reply(npc, history, message)
                history += [dict(role="player", text=message), dict(role="npc", text=turn.text)]
                st.rerun()
            except Exception as exc:
                st.error("Ответ не получен: " + type(exc).__name__)
with tab4:
    path = ROOT / "results/metrics.json"
    if path.exists():
        metrics = json.loads(path.read_text(encoding="utf-8"))
        st.write("Модель: " + metrics["model"])
        st.dataframe(metrics["rows"], width="stretch")
        st.caption("Управляемые отрицательные эксперименты и проверки выхода из роли считаются отдельно.")
        st.download_button(
            "Скачать корпус квестов",
            json.dumps(quests, ensure_ascii=False, indent=2),
            "quests.json",
            "application/json",
        )
    else:
        st.info("Сначала выполните генерацию корпуса и аудит.")

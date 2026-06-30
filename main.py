from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    msg = "BOT_TOKEN is not provided"
    raise RuntimeError(msg)

BASE_DIR = Path()
QUESTIONS_PATH = BASE_DIR / "questions.json"
if not QUESTIONS_PATH.exists():
    msg = "Questions file is not provided"
    raise RuntimeError(msg)

QUESTIONS = json.loads(QUESTIONS_PATH.read_bytes())
QUESTIONS_BY_ID = {q["id"]: q for q in QUESTIONS}
TOTAL = len(QUESTIONS)

router = Router()

user_state: dict[int, dict] = {}


def format_question_text(q: dict) -> str:
    lines = [f"<b>Вопрос {q['id']}/{TOTAL}</b>\n", q["question"]]
    if q["options"]:
        lines.append("")
        lines.append("\n".join(q["options"]))

    return "\n".join(lines)


def question_keyboard(q_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Показать ответ", callback_data=f"answer:{q_id}")],
        ],
    )


def after_answer_keyboard(q_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Следующий", callback_data="next"),
                InlineKeyboardButton(text="🎲 Случайный", callback_data="random"),
            ],
            [InlineKeyboardButton(text="📋 Список вопросов", callback_data="list:0")],
        ],
    )


def get_or_init_state(user_id: int) -> dict:
    if user_id not in user_state:
        order = list(range(1, TOTAL + 1))
        random.shuffle(order)
        user_state[user_id] = {"order": order, "pos": 0}

    return user_state[user_id]


async def send_question(message: Message, q_id: int) -> None:
    q = QUESTIONS_BY_ID[q_id]
    await message.answer(format_question_text(q), reply_markup=question_keyboard(q_id))


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    get_or_init_state(message.from_user.id)
    text = (
        "Привет! Это бот-тренажёр по базе вопросов "
        "«Проектирование информационных систем».\n\n"
        f"Всего вопросов в базе: {TOTAL}\n\n"
        "Команды:\n"
        "/quiz — начать проходить вопросы по порядку (в случайном перемешанном порядке)\n"
        "/random — случайный вопрос\n"
        "/list — список всех вопросов\n"
        "/reset — начать заново (перемешать порядок)\n"
    )
    await message.answer(text)


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    order = list(range(1, TOTAL + 1))
    random.shuffle(order)
    user_state[message.from_user.id] = {"order": order, "pos": 0}
    await message.answer("Прогресс сброшен, порядок вопросов перемешан заново. Жми /quiz")


@router.message(Command("quiz"))
async def cmd_quiz(message: Message) -> None:
    state = get_or_init_state(message.from_user.id)
    q_id = state["order"][state["pos"]]
    await send_question(message, q_id)


@router.message(Command("random"))
async def cmd_random(message: Message) -> None:
    q_id = random.choice(list(QUESTIONS_BY_ID.keys()))
    await send_question(message, q_id)


def list_keyboard(page: int) -> InlineKeyboardMarkup:
    per_page = 10
    start = page * per_page
    end = min(start + per_page, TOTAL)
    rows = []
    row = []
    for i in range(start + 1, end + 1):
        row.append(InlineKeyboardButton(text=str(i), callback_data=f"go:{i}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"list:{page - 1}"))
    if end < TOTAL:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"list:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await message.answer(
        f"Выберите номер вопроса (всего {TOTAL}):",
        reply_markup=list_keyboard(0),
    )


@router.callback_query(F.data.startswith("list:"))
async def cb_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        f"Выберите номер вопроса (всего {TOTAL}):",
        reply_markup=list_keyboard(page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("go:"))
async def cb_go(callback: CallbackQuery) -> None:
    q_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        format_question_text(QUESTIONS_BY_ID[q_id]),
        reply_markup=question_keyboard(q_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("answer:"))
async def cb_answer(callback: CallbackQuery) -> None:
    q_id = int(callback.data.split(":")[1])
    q = QUESTIONS_BY_ID[q_id]
    text = format_question_text(q) + f"\n\n✅ <b>Ответ:</b>\n{q['answer']}"
    await callback.message.edit_text(text, reply_markup=after_answer_keyboard(q_id))
    await callback.answer()


@router.callback_query(F.data == "next")
async def cb_next(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    state = get_or_init_state(user_id)
    state["pos"] += 1
    if state["pos"] >= TOTAL:
        order = list(range(1, TOTAL + 1))
        random.shuffle(order)
        state["order"] = order
        state["pos"] = 0
        await callback.message.answer("🎉 Вы прошли все вопросы! Начинаем новый круг.")
    q_id = state["order"][state["pos"]]
    await callback.message.answer(
        format_question_text(QUESTIONS_BY_ID[q_id]),
        reply_markup=question_keyboard(q_id),
    )
    await callback.answer()


@router.callback_query(F.data == "random")
async def cb_random(callback: CallbackQuery) -> None:
    q_id = random.choice(list(QUESTIONS_BY_ID.keys()))
    await callback.message.answer(
        format_question_text(QUESTIONS_BY_ID[q_id]),
        reply_markup=question_keyboard(q_id),
    )
    await callback.answer()


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

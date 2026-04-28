import logging
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot import wb_parser, sheets
from bot.scheduler import QUERY, format_prices_message

logger = logging.getLogger(__name__)
router = Router()


def refresh_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить цены", callback_data="refresh")],
        [InlineKeyboardButton(text="🔔 Мой алерт", callback_data="my_alert")],
    ])


# ── /start ─────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        "👋 Привет! Я слежу за ценами на *Royal Canin Anallergenic* на Wildberries.\n\n"
        "📋 *Команды:*\n"
        "/prices — показать топ-5 цен прямо сейчас\n"
        "/setalert 1500 — уведомить, когда цена опустится ниже 1500₽\n"
        "/myalert — посмотреть мой текущий алерт\n"
        "/stopalert — отключить уведомления\n\n"
        "Цены обновляются автоматически каждый час."
    )
    await message.answer(text, parse_mode="Markdown")


# ── /prices ────────────────────────────────────────────────────────────────────

@router.message(Command("prices"))
async def cmd_prices(message: Message):
    wait_msg = await message.answer("⏳ Запрашиваю актуальные цены...")

    try:
        products = await wb_parser.fetch_top_prices(QUERY, top_n=5)
        text = format_prices_message(products)
        await wait_msg.edit_text(
            text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=refresh_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error in /prices: {e}")
        await wait_msg.edit_text("❌ Не удалось получить цены. Попробуйте позже.")


# ── Callback: refresh button ───────────────────────────────────────────────────

@router.callback_query(F.data == "refresh")
async def callback_refresh(callback: CallbackQuery):
    await callback.answer("Обновляю...")
    try:
        products = await wb_parser.fetch_top_prices(QUERY, top_n=5)
        text = format_prices_message(products)
        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=refresh_keyboard(),
        )
    except Exception as e:
        logger.error(f"Error in refresh callback: {e}")
        await callback.message.edit_text("❌ Не удалось обновить цены. Попробуйте позже.")


# ── /setalert <price> ──────────────────────────────────────────────────────────

@router.message(Command("setalert"))
async def cmd_setalert(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip().isdigit():
        await message.answer(
            "⚠️ Укажите порог цены в рублях.\n"
            "Пример: `/setalert 1500`",
            parse_mode="Markdown",
        )
        return

    threshold = int(args[1].strip())
    if threshold < 100 or threshold > 100_000:
        await message.answer("⚠️ Введите цену от 100 до 100 000 ₽.")
        return

    try:
        sheets.set_subscription(message.from_user.id, threshold, direction="below")
        await message.answer(
            f"✅ Алерт установлен: я напишу вам, когда цена опустится ниже *{threshold:,}₽*.\n\n"
            f"Отключить: /stopalert",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Error setting subscription: {e}")
        await message.answer("❌ Не удалось сохранить алерт. Попробуйте позже.")


# ── /myalert ───────────────────────────────────────────────────────────────────

@router.message(Command("myalert"))
@router.callback_query(F.data == "my_alert")
async def cmd_myalert(event: Message | CallbackQuery):
    message = event if isinstance(event, Message) else event.message
    user_id = event.from_user.id

    if isinstance(event, CallbackQuery):
        await event.answer()

    try:
        sub = sheets.get_subscription(user_id)
    except Exception as e:
        logger.error(f"Error getting subscription: {e}")
        await message.answer("❌ Не удалось загрузить данные.")
        return

    if not sub or str(sub.get("active")).lower() not in ("true", "1"):
        await message.answer(
            "У вас нет активного алерта.\n"
            "Установить: `/setalert 1500`",
            parse_mode="Markdown",
        )
    else:
        threshold = sub["threshold"]
        await message.answer(
            f"🔔 Активный алерт: цена ниже *{int(threshold):,}₽*\n\n"
            f"Отключить: /stopalert",
            parse_mode="Markdown",
        )


# ── /stopalert ─────────────────────────────────────────────────────────────────

@router.message(Command("stopalert"))
async def cmd_stopalert(message: Message):
    try:
        sheets.remove_subscription(message.from_user.id)
        await message.answer("🔕 Уведомления отключены.")
    except Exception as e:
        logger.error(f"Error removing subscription: {e}")
        await message.answer("❌ Не удалось отключить алерт.")

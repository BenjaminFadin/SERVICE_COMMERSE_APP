from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

from config import config
from database import (
    get_or_create_user,
    update_user_language,
    get_user_language,
)
from keyboards import (
    language_keyboard,
    main_menu_keyboard,
    website_inline_keyboard,
)
from locales import get_text, TEXTS

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    # Save / update user in database
    user = await get_or_create_user(message.from_user)

    # Show language selection
    await message.answer(
        get_text("uz", "choose_language"),
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.split("_")[1]  # uz or ru

    # Update language in database
    await update_user_language(callback.from_user.id, lang)

    # Confirm language selection
    await callback.message.edit_text(get_text(lang, "language_selected"))

    # Send welcome message with main menu
    name = callback.from_user.first_name or "Foydalanuvchi"
    await callback.message.answer(
        get_text(lang, "welcome", name=name),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


@router.message(F.text.in_([
    TEXTS["uz"]["services_button"],
    TEXTS["ru"]["services_button"],
]))
async def services_handler(message: Message):
    lang = await get_user_language(message.from_user.id)
    await message.answer(
        get_text(lang, "services_message"),
        reply_markup=website_inline_keyboard(lang, config.website_url),
    )


@router.message(F.text.in_([
    TEXTS["uz"]["change_language_button"],
    TEXTS["ru"]["change_language_button"],
]))
async def change_language_handler(message: Message):
    await message.answer(
        get_text("uz", "choose_language"),
        reply_markup=language_keyboard(),
    )
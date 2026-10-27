from collections.abc import Callable, Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton as Button
from aiogram.types import InlineKeyboardMarkup as Markup
from aiogram.utils.keyboard import InlineKeyboardBuilder as Builder

from app.bot.utils import buy_url
from app.storage import ChatData, TokenData
from app.texts import SUPPORTED_LANGUAGES, TextButton


class LanguageCallback(CallbackData, prefix="language"):
    code: str


class PageCallback(CallbackData, prefix="page"):
    number: int


class ChatCallback(CallbackData, prefix="chat"):
    id: int


class TokenCallback(CallbackData, prefix="token"):
    address: str


class AdminCallback(CallbackData, prefix="admin"):
    user_id: int


class TopCallback(CallbackData, prefix="top"):
    address: str


def back(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [Button(text=text_button.get("back"), callback_data="back")],
        ]
    )


def main(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [Button(text=text_button.get("back"), callback_data="main")],
        ]
    )


def select_language() -> Markup:
    builder = Builder()
    builder.row(
        *[
            Button(text=text, callback_data=LanguageCallback(code=code).pack())
            for code, text in SUPPORTED_LANGUAGES.items()
        ],
        width=3,
    )
    return builder.as_markup()


def main_menu(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [Button(text=text_button.get("get_access"), callback_data="get_access")],
            [
                Button(text=text_button.get("change_language"), callback_data="change_language"),
                Button(text=text_button.get("disconnect_wallet"), callback_data="disconnect_wallet"),
            ],
        ]
    )


def allow_access(text_button: TextButton, chats: Sequence[ChatData]) -> Markup:
    inline_keyboard = [[Button(text=chat.name, url=chat.invite_link)] for chat in chats]
    inline_keyboard.append([Button(text=text_button.get("back"), callback_data="main")])
    return Markup(inline_keyboard=inline_keyboard)


def deny_access(text_button: TextButton, tokens: Sequence[TokenData], dex_name: str) -> Markup:
    inline_keyboard = [[Button(text=token.name, url=buy_url(token, dex_name))] for token in tokens]
    inline_keyboard.append([Button(text=text_button.get("back"), callback_data="main")])
    return Markup(inline_keyboard=inline_keyboard)


def select_tokens(tokens: Sequence[TokenData]) -> Markup:
    builder = Builder()
    for token in tokens:
        builder.row(Button(text=token.name, callback_data=TopCallback(address=token.address).pack()))
    return builder.as_markup()


def page_labels(page: int, total_pages: int) -> list[tuple[int, str]]:
    if total_pages <= 5:
        labels = {number: str(number) for number in range(1, total_pages + 1)}
    elif page <= 3:
        labels = {1: "1", 2: "2", 3: "3", 4: "4 ›", total_pages: f"{total_pages} »"}
    elif page > total_pages - 3:
        labels = {1: "« 1", total_pages - 3: f"‹ {total_pages - 3}"}
        labels |= {number: str(number) for number in range(total_pages - 2, total_pages + 1)}
    else:
        labels = {1: "« 1", page - 1: f"‹ {page - 1}", page + 1: f"{page + 1} ›", total_pages: f"{total_pages} »"}
    labels[page] = f"· {page} ·"
    return sorted(labels.items())


def paginated(
    items: Sequence[tuple[str, CallbackData]],
    page: int,
    total_pages: int,
    page_callback: Callable[[int], CallbackData],
    footer: Markup | None = None,
) -> Markup:
    builder = Builder()
    for text, callback_data in items:
        builder.row(Button(text=text, callback_data=callback_data.pack()))
    if total_pages > 1:
        builder.row(
            *[
                Button(text=label, callback_data=page_callback(number).pack())
                for number, label in page_labels(page, total_pages)
            ]
        )
    if footer is not None:
        builder.attach(Builder(markup=footer.inline_keyboard))
    return builder.as_markup()


def back_add(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [
                Button(text=text_button.get("back"), callback_data="back"),
                Button(text=text_button.get("add"), callback_data="add"),
            ],
        ]
    )


def back_delete(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [
                Button(text=text_button.get("back"), callback_data="back"),
                Button(text=text_button.get("delete"), callback_data="delete"),
            ],
        ]
    )


def back_confirm(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [
                Button(text=text_button.get("back"), callback_data="back"),
                Button(text=text_button.get("confirm"), callback_data="confirm"),
            ],
        ]
    )


def admin_menu(text_button: TextButton) -> Markup:
    return Markup(
        inline_keyboard=[
            [Button(text=text_button.get("admins_menu"), callback_data="admins_menu")],
            [
                Button(text=text_button.get("chats_menu"), callback_data="chats_menu"),
                Button(text=text_button.get("tokens_menu"), callback_data="tokens_menu"),
            ],
            [Button(text=text_button.get("back"), callback_data="main")],
        ]
    )


def token_info(text_button: TextButton) -> Markup:
    inline_keyboard = [[Button(text=text_button.get("edit_min_amount"), callback_data="edit_min_amount")]]
    return Markup(inline_keyboard=inline_keyboard + back_delete(text_button).inline_keyboard)

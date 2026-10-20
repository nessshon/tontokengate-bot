from aiogram import html
from aiogram.utils.markdown import hbold, hcode

from app.bot import keyboards
from app.bot.keyboards import AdminCallback, ChatCallback, PageCallback, TokenCallback
from app.bot.manager import Manager, SendMode
from app.bot.states import AdminState
from app.bot.utils import date_string, paginate, token_amount, tonviewer_link
from app.storage import AdminData, ChatData, TokenData

PAGE_SIZE = 5


async def current_page(manager: Manager, page: int | None) -> int:
    if page is None:
        return int((await manager.state.get_data()).get("page", 1))
    await manager.state.update_data(page=page)
    return page


async def selected_chat(manager: Manager) -> ChatData | None:
    chat_id = (await manager.state.get_data()).get("chat_id")
    return None if chat_id is None else await manager.storage.get_chat(chat_id)


async def selected_token(manager: Manager) -> TokenData | None:
    address = (await manager.state.get_data()).get("token_address")
    return None if address is None else await manager.storage.get_token(address)


async def selected_admin(manager: Manager) -> AdminData | None:
    user_id = (await manager.state.get_data()).get("admin_id")
    return None if user_id is None else await manager.storage.get_admin(user_id)


def with_note(text: str, note: str | None) -> str:
    return f"{text}\n\n{note}" if note else text


async def admin_menu(manager: Manager, send_mode: SendMode = SendMode.EDIT) -> None:
    text = manager.text_message.get("admin_menu")
    await manager.send_message(text, reply_markup=keyboards.admin_menu(manager.text_button), send_mode=send_mode)
    await manager.state.set_state(AdminState.ADMIN_MENU)


async def chats_menu(manager: Manager, page: int | None = None) -> None:
    page = await current_page(manager, page)
    chats, total_pages = paginate(await manager.storage.chats(), page, PAGE_SIZE)
    reply_markup = keyboards.paginated(
        [(chat.name, ChatCallback(id=chat.id)) for chat in chats],
        page,
        total_pages,
        lambda number: PageCallback(number=number),
        footer=keyboards.back(manager.text_button),
    )
    await manager.send_message(manager.text_message.get("chats_menu"), reply_markup=reply_markup)
    await manager.state.set_state(AdminState.CHATS_MENU)


async def chat_info(manager: Manager) -> None:
    chat = await selected_chat(manager)
    if chat is None:
        await chats_menu(manager)
        return
    text = manager.text_message.get("chat_info").format(
        chat_id=hcode(chat.id),
        chat_type=chat.type,
        chat_name=hbold(chat.name),
        chat_invite_link=chat.invite_link,
        chat_created_at=hcode(date_string(chat.created_at)),
    )
    await manager.send_message(text, reply_markup=keyboards.back_delete(manager.text_button))
    await manager.state.set_state(AdminState.CHAT_INFO)


async def chat_confirm_delete(manager: Manager) -> None:
    chat = await selected_chat(manager)
    if chat is None:
        await chats_menu(manager)
        return
    text = manager.text_message.get("confirm_item_delete").format(item=html.quote(chat.name))
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button))
    await manager.state.set_state(AdminState.CHAT_CONFIRM_DELETE)


async def chat_confirm_add(manager: Manager, send_mode: SendMode = SendMode.EDIT) -> None:
    chat = (await manager.state.get_data()).get("chat")
    if chat is None:
        await chats_menu(manager)
        return
    text = manager.text_message.get("confirm_item_add").format(item=html.quote(chat["name"]))
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button), send_mode=send_mode)
    await manager.state.set_state(AdminState.CHAT_CONFIRM_ADD)


async def tokens_menu(manager: Manager, page: int | None = None) -> None:
    page = await current_page(manager, page)
    tokens, total_pages = paginate(await manager.storage.tokens(), page, PAGE_SIZE)
    reply_markup = keyboards.paginated(
        [(token.name, TokenCallback(address=token.address)) for token in tokens],
        page,
        total_pages,
        lambda number: PageCallback(number=number),
        footer=keyboards.back_add(manager.text_button),
    )
    await manager.send_message(manager.text_message.get("tokens_menu"), reply_markup=reply_markup)
    await manager.state.set_state(AdminState.TOKENS_MENU)


async def token_info(manager: Manager) -> None:
    token = await selected_token(manager)
    if token is None:
        await tokens_menu(manager)
        return
    text = manager.text_message.get("token_info").format(
        token_name=html.quote(token.name),
        token_type=token.type,
        token_min_amount=token_amount(token, token.min_amount),
        token_address=tonviewer_link(token.address),
        token_created_at=date_string(token.created_at),
    )
    await manager.send_message(text, reply_markup=keyboards.token_info(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_INFO)


async def token_confirm_delete(manager: Manager) -> None:
    token = await selected_token(manager)
    if token is None:
        await tokens_menu(manager)
        return
    text = manager.text_message.get("confirm_item_delete").format(item=html.quote(token.name))
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_CONFIRM_DELETE)


async def token_send_address(manager: Manager, note: str | None = None) -> None:
    text = with_note(manager.text_message.get("token_send_address"), note)
    await manager.send_message(text, reply_markup=keyboards.back(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_SEND_ADDRESS)


async def token_send_amount(manager: Manager, note: str | None = None) -> None:
    token = (await manager.state.get_data()).get("token")
    if token is None:
        await token_send_address(manager)
        return
    text = manager.text_message.get("token_send_amount").format(
        token_name=tonviewer_link(token["address"], token["name"]),
        token_type=token["type"],
    )
    await manager.send_message(with_note(text, note), reply_markup=keyboards.back(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_SEND_AMOUNT)


async def token_confirm_add(manager: Manager) -> None:
    token = (await manager.state.get_data()).get("token")
    if token is None:
        await token_send_address(manager)
        return
    item = tonviewer_link(token["address"], token["name"])
    text = manager.text_message.get("confirm_item_add").format(item=item)
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_CONFIRM_ADD)


async def token_edit_amount(manager: Manager, note: str | None = None) -> None:
    text = with_note(manager.text_message.get("token_edit_amount"), note)
    await manager.send_message(text, reply_markup=keyboards.back(manager.text_button))
    await manager.state.set_state(AdminState.TOKEN_EDIT_AMOUNT)


async def admins_menu(manager: Manager, page: int | None = None) -> None:
    page = await current_page(manager, page)
    admins, total_pages = paginate(await manager.storage.admins(), page, PAGE_SIZE)
    reply_markup = keyboards.paginated(
        [(admin.full_name, AdminCallback(user_id=admin.user_id)) for admin in admins],
        page,
        total_pages,
        lambda number: PageCallback(number=number),
        footer=keyboards.back_add(manager.text_button),
    )
    await manager.send_message(manager.text_message.get("admins_menu"), reply_markup=reply_markup)
    await manager.state.set_state(AdminState.ADMINS_MENU)


async def admin_info(manager: Manager) -> None:
    admin = await selected_admin(manager)
    if admin is None:
        await admins_menu(manager)
        return
    text = manager.text_message.get("admin_info").format(
        admin_id=hcode(admin.user_id),
        admin_username=admin.username or "N/A",
        admin_full_name=hbold(admin.full_name),
        admin_created_at=hcode(date_string(admin.created_at)),
    )
    await manager.send_message(text, reply_markup=keyboards.back_delete(manager.text_button))
    await manager.state.set_state(AdminState.ADMIN_INFO)


async def admin_confirm_delete(manager: Manager) -> None:
    admin = await selected_admin(manager)
    if admin is None:
        await admins_menu(manager)
        return
    text = manager.text_message.get("confirm_item_delete").format(item=html.quote(admin.full_name))
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button))
    await manager.state.set_state(AdminState.ADMIN_CONFIRM_DELETE)


async def admin_send_id(manager: Manager, note: str | None = None) -> None:
    text = with_note(manager.text_message.get("admin_send_id"), note)
    await manager.send_message(text, reply_markup=keyboards.back(manager.text_button))
    await manager.state.set_state(AdminState.ADMIN_SEND_ID)


async def admin_confirm_add(manager: Manager) -> None:
    admin = (await manager.state.get_data()).get("admin")
    if admin is None:
        await admin_send_id(manager)
        return
    text = manager.text_message.get("confirm_item_add").format(item=html.quote(admin["full_name"]))
    await manager.send_message(text, reply_markup=keyboards.back_confirm(manager.text_button))
    await manager.state.set_state(AdminState.ADMIN_CONFIRM_ADD)

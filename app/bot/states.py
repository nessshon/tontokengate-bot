from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    SELECT_LANGUAGE = State()
    CHANGE_LANGUAGE = State()
    CONNECT_WALLET = State()

    MAIN_MENU = State()


class AdminState(StatesGroup):
    ADMIN_MENU = State()

    CHATS_MENU = State()
    CHAT_INFO = State()
    CHAT_CONFIRM_DELETE = State()
    CHAT_CONFIRM_ADD = State()

    TOKENS_MENU = State()
    TOKEN_INFO = State()
    TOKEN_CONFIRM_DELETE = State()

    TOKEN_SEND_ADDRESS = State()
    TOKEN_SEND_AMOUNT = State()
    TOKEN_CONFIRM_ADD = State()
    TOKEN_EDIT_AMOUNT = State()

    ADMINS_MENU = State()
    ADMIN_INFO = State()
    ADMIN_CONFIRM_DELETE = State()

    ADMIN_SEND_ID = State()
    ADMIN_CONFIRM_ADD = State()

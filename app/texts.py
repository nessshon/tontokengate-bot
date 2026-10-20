import tomllib
from pathlib import Path
from string import Formatter
from typing import Any

from aiogram.utils.markdown import hide_link

LOCALES_DIR = Path(__file__).parents[1] / "locales"
TABLES = ("buttons", "messages", "pictures")

PLACEHOLDERS: dict[str, dict[str, set[str]]] = {
    "buttons": {
        "connect_wallet": {"wallet_name"},
    },
    "messages": {
        "main_menu": {"chats", "tokens", "wallet"},
        "user_kicked": {"user"},
        "welcome_to_chat": {"user_full_name", "balances"},
        "welcome_to_chat_no_tokens": {"user_full_name"},
        "top_holders": {"top_holders"},
        "balance_command": {"user_full_name", "balances"},
        "balance_command_no_tokens": {"user_full_name"},
        "connect_wallet": {"wallet_name"},
        "chat_info": {"chat_id", "chat_type", "chat_name", "chat_invite_link", "chat_created_at"},
        "token_info": {"token_type", "token_name", "token_address", "token_min_amount", "token_created_at"},
        "token_send_amount": {"token_type", "token_name"},
        "admin_info": {"admin_id", "admin_full_name", "admin_username", "admin_created_at"},
        "admin_send_id_error": {"error"},
        "confirm_item_add": {"item"},
        "item_added": {"item"},
        "confirm_item_delete": {"item"},
        "item_deleted": {"item"},
        "chat_add_rights": {"rights"},
        "chat_bot_removed": {"chat"},
        "chat_rights_missing": {"chat", "rights"},
        "chat_rights_restored": {"chat"},
        "chat_check_failed": {"chat", "error"},
    },
}


def placeholders(text: str) -> set[str]:
    return {field for _, field, _, _ in Formatter().parse(text) if field is not None}


def problems(language: dict[str, Any], keys: dict[str, set[str]]) -> list[str]:
    if missing := {"language", *TABLES} - language.keys():
        return [f"no {', '.join(sorted(missing))}"]
    found = [f"no {table}.{key}" for table in TABLES for key in sorted(keys[table] - language[table].keys())]
    for key, url in sorted(language["pictures"].items()):
        if key not in language["messages"]:
            found.append(f"pictures.{key} is for no message")
        if not url.startswith("https://"):
            found.append(f"pictures.{key} is not a link")
    for table in ("buttons", "messages"):
        for key, text in language[table].items():
            try:
                unknown = placeholders(text) - PLACEHOLDERS[table].get(key, set())
            except ValueError as ex:
                found.append(f"{table}.{key}: {ex}")
                continue
            if unknown:
                fields = ", ".join("{" + field + "}" for field in sorted(unknown))
                found.append(f"{table}.{key} has unsupported {fields}")
    return found


def load(directory: Path) -> dict[str, dict[str, Any]]:
    texts = {path.stem: tomllib.loads(path.read_text(encoding="utf-8")) for path in sorted(directory.glob("*.toml"))}
    if not texts:
        raise ValueError(f"No language files in {directory}")
    keys = {table: set().union(*(language.get(table, {}) for language in texts.values())) for table in TABLES}
    for code, language in texts.items():
        if found := problems(language, keys):
            raise ValueError(f"{code}.toml: " + "; ".join(found))
    return texts


TEXTS = load(LOCALES_DIR)
SUPPORTED_LANGUAGES = {code: language["language"] for code, language in TEXTS.items()}
DEFAULT_LANGUAGE = "en" if "en" in SUPPORTED_LANGUAGES else next(iter(SUPPORTED_LANGUAGES))


def language_or_default(language_code: str | None) -> str:
    return language_code if language_code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


class TextButton:
    def __init__(self, language_code: str | None) -> None:
        self.language_code = language_or_default(language_code)

    def get(self, code: str) -> str:
        return TEXTS[self.language_code]["buttons"][code]


class TextMessage:
    def __init__(self, language_code: str | None) -> None:
        self.language_code = language_or_default(language_code)

    def get(self, code: str) -> str:
        language = TEXTS[self.language_code]
        text = language["messages"][code]
        if picture := language["pictures"].get(code):
            return hide_link(picture) + text
        return text

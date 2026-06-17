#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# токены и каналы такие же, как в твоём большом скрипте
BOT_TOKEN_PUBLIC = os.environ.get("TELEGRAM_BOT_TOKEN_PUBLIC")
BOT_TOKEN_PRIVATE = os.environ.get("TELEGRAM_BOT_TOKEN")
PRIVATE_CHANNEL = os.environ.get("TELEGRAM_PRIVATE_CHANNEL")

PUBLIC_CHANNEL = "@vlesstrojan"

SUBSCRIPTIONS_LIST_PATH = Path("out/subscriptions_list.txt")
MAX_BUTTONS_PER_POST = 10   # 10 кнопок = 10 подписок


def load_ready_sub_links() -> list[str]:
    """
    Читает ГОТОВЫЕ короткие ссылки-подписки из out/subscriptions_list.txt.
    Каждая непустая строка = отдельная подписка (URL или короткий sub).
    """
    if not SUBSCRIPTIONS_LIST_PATH.exists():
        print(f"⚠️ {SUBSCRIPTIONS_LIST_PATH} не существует, запусти pipeline.py + build_eu_subscriptions_list.py")
        return []

    content = SUBSCRIPTIONS_LIST_PATH.read_text(encoding="utf-8", errors="ignore").strip()
    if not content:
        print(f"⚠️ {SUBSCRIPTIONS_LIST_PATH} пустой")
        return []

    subs: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        subs.append(line)

    print(f"🔗 Готовых коротких ссылок-подписок: {len(subs)}")
    return subs


def build_keyboard_for_subs(subs: list[str]) -> list[list[dict]]:
    """Строит inline_keyboard: по одной кнопке в строке, каждая с copy_text = короткая ссылка."""
    keyboard: list[list[dict]] = []
    for idx, sub in enumerate(subs, start=1):
        btn_text = f"📥 EU подписка #{idx}"
        keyboard.append(
            [
                {
                    "text": btn_text,
                    "copy_text": {"text": sub},
                    # можно добавить "url": sub, если хочешь открытие по клику
                }
            ]
        )
    return keyboard


def send_buttons_post(
    bot_token: str,
    channel: str,
    subs: list[str],
    for_private: bool = False,
) -> None:
    """Отправляет один пост с кнопками (по одной готовой ссылке-подписке на кнопку)."""
    if not subs:
        print(f"⚠️ Нет подписок для отправки в {channel}")
        return

    subs = subs[:MAX_BUTTONS_PER_POST]
    keyboard = build_keyboard_for_subs(subs)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if not for_private:
        # текст для публичного
        text = (
            "👋 Привет! Свежие EU подписки.\n\n"
            "Каждая кнопка — отдельная подписная ссылка.\n"
            "Нажми на кнопку — строка скопируется в буфер,\n"
            "потом вставь её в Hiddify, v2rayNG, Clash и т.п.\n\n"
            f"🕒 Обновление: <code>{now_str}</code>\n"
            "⚠️ Конфиги из открытых источников, только для ознакомления."
        )
    else:
        # текст для приватного
        text = (
            "🔐 Приватные EU подписки.\n\n"
            "Каждая кнопка — отдельная подписная ссылка.\n"
            "Скопируй и вставь в свой клиент.\n\n"
            f"🕒 Обновление: <code>{now_str}</code>\n"
            "⚠️ Не делись этими ссылками публично."
        )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": channel,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": {"inline_keyboard": keyboard},
            },
            timeout=20,
        )
        data = resp.json()
        if data.get("ok"):
            print(f"✅ Пост с {len(subs)} кнопками отправлен в {channel}")
        else:
            print(f"❌ Ошибка Telegram ({channel}): {data.get('description')}")
    except Exception as e:
        print(f"❌ Ошибка отправки в {channel}: {e}")


def main() -> int:
    if not BOT_TOKEN_PUBLIC:
        print("❌ TELEGRAM_BOT_TOKEN_PUBLIC не установлен")
        return 1

    print("=== EU SUBSCRIPTIONS BUTTON POSTER (from subscriptions_list.txt) ===")

    subs = load_ready_sub_links()
    if not subs:
        print("❌ Нет коротких ссылок-подписок, ничего не отправляем")
        return 1

    # Публичный канал
    send_buttons_post(
        bot_token=BOT_TOKEN_PUBLIC,
        channel=PUBLIC_CHANNEL,
        subs=subs,
        for_private=False,
    )

    # Приватный (если задан)
    if BOT_TOKEN_PRIVATE and PRIVATE_CHANNEL:
        remaining = subs[MAX_BUTTONS_PER_POST:]
        if not remaining:
            remaining = subs
        send_buttons_post(
            bot_token=BOT_TOKEN_PRIVATE,
            channel=PRIVATE_CHANNEL,
            subs=remaining,
            for_private=True,
        )
    else:
        print("ℹ️ Приватный канал или токен не заданы — отправляем только в паблик")

    return 0


if __name__ == "__main__":
    sys.exit(main())

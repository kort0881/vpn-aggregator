#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import random
from pathlib import Path
from datetime import datetime

import requests

# токены и каналы такие же, как в твоём большом скрипте
BOT_TOKEN_PUBLIC = os.environ.get("TELEGRAM_BOT_TOKEN_PUBLIC")
BOT_TOKEN_PRIVATE = os.environ.get("TELEGRAM_BOT_TOKEN")
PRIVATE_CHANNEL = os.environ.get("TELEGRAM_PRIVATE_CHANNEL")

PUBLIC_CHANNEL = "@vlesstrojan"

BASE_OUT = Path("out/by_country")

EU_COUNTRIES = [
    "DE", "NL", "FR", "FI", "SE", "PL", "CZ", "AT", "BE",
    "DK", "IE", "ES", "IT", "PT", "NO", "CH", "LU", "EE",
    "LV", "LT",
]

KEYS_PER_SUB = 100          # 100 ключей = 1 подписка
MAX_BUTTONS_PER_POST = 10   # 10 кнопок = 10 подписок


def load_eu_keys() -> list[str]:
    """Читает URI из out/by_country/*.txt только для EU-стран."""
    keys: list[str] = []
    if not BASE_OUT.exists():
        print(f"⚠️ {BASE_OUT} не существует, запусти pipeline.py")
        return keys

    for cc in EU_COUNTRIES:
        path = BASE_OUT / f"{cc}.txt"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if "://" not in line:
                continue
            keys.append(line)

    print(f"🌍 Найдено EU-ключей: {len(keys)}")
    return keys


def chunk_keys(keys: list[str], per_sub: int) -> list[list[str]]:
    """Режет список ключей на чанки по per_sub штук (1 чанк = 1 подписка)."""
    random.shuffle(keys)
    chunks: list[list[str]] = []
    for i in range(0, len(keys), per_sub):
        part = keys[i:i + per_sub]
        if part:
            chunks.append(part)
    return chunks


def make_subscription_payload(keys: list[str]) -> str:
    """
    Содержимое подписки: текст, который юзер скопирует и вставит в клиент.
    Сейчас это просто список URI построчно.
    Если захочешь — тут можно упаковать в base64/одну ссылку.
    """
    return "\n".join(keys) + "\n"


def build_keyboard_for_subs(subs_payloads: list[str]) -> list[list[dict]]:
    """Строит inline_keyboard: по одной кнопке в строке, каждая с copy_text."""
    keyboard: list[list[dict]] = []
    for idx, payload in enumerate(subs_payloads, start=1):
        btn_text = f"📥 EU подписка #{idx}"
        keyboard.append(
            [
                {
                    "text": btn_text,
                    "copy_text": {"text": payload},
                }
            ]
        )
    return keyboard


def send_buttons_post(
    bot_token: str,
    channel: str,
    subs_payloads: list[str],
    for_private: bool = False,
) -> None:
    """Отправляет один пост с кнопками (по одной подписке на кнопку)."""
    if not subs_payloads:
        print(f"⚠️ Нет подписок для отправки в {channel}")
        return

    subs_payloads = subs_payloads[:MAX_BUTTONS_PER_POST]
    keyboard = build_keyboard_for_subs(subs_payloads)

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if not for_private:
        # текст для публичного
        text = (
            "👋 Привет! Свежие EU подписки.\n\n"
            "Каждая кнопка — отдельная подписка (~100 ключей).\n"
            "Нажми на кнопку — текст скопируется в буфер,\n"
            "потом вставь его в Hiddify, v2rayNG, Clash и т.п.\n\n"
            f"🕒 Обновление: <code>{now_str}</code>\n"
            "⚠️ Конфиги из открытых источников, только для ознакомления."
        )
    else:
        # текст для приватного (можно сделать чуть «более VIP»)
        text = (
            "🔐 Приватные EU подписки.\n\n"
            "Каждая кнопка — отдельная подписка (~100 ключей).\n"
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
            print(f"✅ Пост с {len(subs_payloads)} кнопками отправлен в {channel}")
        else:
            print(f"❌ Ошибка Telegram ({channel}): {data.get('description')}")
    except Exception as e:
        print(f"❌ Ошибка отправки в {channel}: {e}")


def main() -> int:
    if not BOT_TOKEN_PUBLIC:
        print("❌ TELEGRAM_BOT_TOKEN_PUBLIC не установлен")
        return 1

    print("=== EU SUBSCRIPTIONS BUTTON POSTER (2 channels) ===")

    keys = load_eu_keys()
    if not keys:
        print("❌ Нет EU-ключей, ничего не отправляем")
        return 1

    chunks = chunk_keys(keys, KEYS_PER_SUB)
    print(f"📦 Подписок всего: {len(chunks)}")

    subs_payloads = [make_subscription_payload(chunk) for chunk in chunks]

    # Публичный канал
    send_buttons_post(
        bot_token=BOT_TOKEN_PUBLIC,
        channel=PUBLIC_CHANNEL,
        subs_payloads=subs_payloads,
        for_private=False,
    )

    # Приватный (если задан)
    if BOT_TOKEN_PRIVATE and PRIVATE_CHANNEL:
        # можно взять следующие 10 подписок, чтобы не дублировать с пабликом
        remaining_subs = subs_payloads[MAX_BUTTONS_PER_POST:]
        if not remaining_subs:
            # если мало подписок, просто переиспользуем те же
            remaining_subs = subs_payloads
        send_buttons_post(
            bot_token=BOT_TOKEN_PRIVATE,
            channel=PRIVATE_CHANNEL,
            subs_payloads=remaining_subs,
            for_private=True,
        )
    else:
        print("ℹ️ Приватный канал или токен не заданы — отправляем только в паблик")

    return 0


if __name__ == "__main__":
    sys.exit(main())

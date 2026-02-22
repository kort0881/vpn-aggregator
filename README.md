# VPN Aggregator & Repacker

Технический конвейер агрегации, фильтрации и переупаковки VPN-конфигов 
(VLESS/VMess/Shadowsocks) из открытых источников с фокусом на 
европейские серверы.

## 🎯 Функциональность

- **Загрузка сырья**: GitHub, Telegram, сайты-генераторы
- **Фильтрация**: Только EU сервера (по IP/ASN/стране), без России
- **Профилирование источников**: Качество (ping, alive_ratio), ASN/страна распределение
- **Автоматический whitelist/blacklist**: На основе профилей
- **Переупаковка**: Трансформация конфигов с сохранением IP/UUID/портов
- **Ребрендирование**: Смена имён узлов, комментариев, тегов

## 📊 Структура Репозитория

```
sources_raw/      → Сырые конфиги
sources_clean/    → После фильтрации по EU
sources_meta/     → Профили источников (JSON)
out/              → Финальные конфиги
scripts/          → Python-модули конвейера
```

## 🚀 Быстрый старт

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск полного конвейера
python pipeline.py

# Или запуск отдельных шагов
python -m scripts.fetch_sources
python -m scripts.filter_and_classify
python -m scripts.collect_providers
python -m scripts.repack_configs
```

## 📋 Конфигурация

Настройки находятся в `config.yaml`:

```yaml
filters:
  eu_countries: true
  exclude_countries: ["RU", "BY", "KZ"]
  min_alive_ratio: 0.7

output:
  brand_name: "@мойканал"
  format_template: "{country} {ping}ms AS{asn} {protocol}"
```

## 🔧 Основные модули

### Парсинг конфигов
```python
from scripts.parser import ConfigParser

parser = ConfigParser()
node = parser.parse_vless("vless://uuid@host:port?params#remark")
```

### Фильтрация по GEO
```python
from scripts.filter_and_classify import GeoFilter

filter = GeoFilter()
eu_nodes = filter.filter_by_region(nodes, "EU")
```

### Профилирование источников
```python
from scripts.collect_providers import ProviderProfiler

profiler = ProviderProfiler()
profile = profiler.build_profile(source_id, nodes)
```

## 📦 Зависимости

- `requests` — HTTP запросы
- `pydantic` — Валидация данных
- `pyyaml` — Конфиги
- `geoip2` / `maxminddb` — Определение страны по IP
- `aiohttp` — Асинхронные запросы

## 📝 Структура JSON-профиля

```json
{
  "id": "github_repo1",
  "total_nodes": 150,
  "unique_ips": 120,
  "alive_ratio": 0.75,
  "avg_ping_ms": 85,
  "eu_share": 0.85,
  "bad_country_share": 0.02,
  "asn_stats": {"16509": 45, "13335": 30},
  "country_stats": {"DE": 50, "NL": 40, "FR": 30}
}
```

## 🔐 Безопасность

- Никакие пароли/ключи не хранятся в репозитории
- Используйте `.env` для секретов
- Все конфиги в `sources_raw/` в .gitignore

## 📜 Лицензия

MIT License

## 🤝 Контрибьюция

Pull requests welcome!

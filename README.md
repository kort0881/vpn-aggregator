markdown
<div align="center">

# VPN Aggregator & Repacker

**Pipeline для агрегации, гео-фильтрации и переупаковки VPN-конфигов**  
VLESS · VMess · Shadowsocks → EU-only → ребрендированный output

[![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Pipeline](https://github.com/kort0881/vpn-aggregator/actions/workflows/pipeline-report.yml/badge.svg)](https://github.com/kort0881/vpn-aggregator/actions/workflows/pipeline-report.yml)

</div>

---

## Обзор

`vpn-aggregator` — конвейер для обработки открытых VPN-конфигов. На входе — сырьё из GitHub, Telegram-каналов и публичных генераторов. На выходе — отфильтрованный по гео, дедуплицированный и переупакованный набор нод с сохранением исходных `IP` / `UUID` / `port` и переименованными под целевой бренд remark'ами.

Проект рассчитан на регулярный запуск в CI: полный прогон занимает несколько минут, артефакты (готовые конфиги + профили источников) коммитятся автоматически.

---

## Возможности

| Стадия | Что делает |
|---|---|
| **Fetch** | Параллельная загрузка сырья из `GitHub / Telegram / generator-сайтов` |
| **Parse** | Разбор URI для VLESS / VMess / Shadowsocks (включая base64-форматы) |
| **Geo-filter** | Определение страны по `GeoLite2-Country.mmdb` + `GeoLite2-ASN.mmdb` |
| **Profile** | Метрики по каждому источнику: `alive_ratio`, `avg_ping`, `eu_share`, распределения по ASN / стране |
| **Whitelist / Blacklist** | Автоматическая отбраковка источников по порогу качества |
| **Repack** | Переупаковка с сохранением `IP` / `UUID` / `port`, смена remark'ов и тегов |
| **Report** | Markdown-отчёты по пайплайну и GeoIP-статистике |

---

## Архитектура

```text
                ┌─────────────────┐
                │  sources_raw/   │   GitHub · Telegram · generators
                └────────┬────────┘
                         │
                ┌────────▼────────┐
                │  fetch_sources  │   параллельная загрузка (aiohttp)
                └────────┬────────┘
                         │
                ┌────────▼──────────────┐
                │ filter_and_classify   │   parse → resolve IP → GeoIP → EU-only
                └────────┬──────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼───────┐ ┌──────▼───────┐ ┌──────▼────────────┐
│ sources_clean │ │ sources_meta │ │ collect_providers │   профили источников (JSON)
└───────────────┘ └──────────────┘ └──────┬────────────┘
                                          │
                                 ┌────────▼────────┐
                                 │ repack_configs  │   переупаковка + ребрендинг
                                 └────────┬────────┘
                                          │
                                 ┌────────▼────────┐
                                 │      out/       │   by_type/*.txt + final bundle
                                 └─────────────────┘
Структура репозитория
text
.
├── pipeline.py                  # entrypoint: полный прогон
├── config.yaml                  # фильтры, брендинг, пороги
├── requirements.txt
├── scripts/
│   ├── fetch_sources.py         # загрузка сырья
│   ├── parser.py                # URI → Node
│   ├── filter_and_classify.py   # GeoIP + EU-фильтр
│   ├── collect_providers.py     # профилирование источников
│   └── repack_configs.py        # переупаковка и брендинг
├── sources_raw/                 # сырые конфиги (не коммитятся)
├── sources_clean/               # после гео-фильтрации
├── sources_meta/
│   ├── pipeline_report.md       # отчёт полного прогона
│   └── geoip_report.md          # GeoIP-статистика
├── out/
│   ├── by_type/                 # vless.txt · vmess.txt · ss.txt
│   └── final.txt                # итоговый бандл
└── data/                        # GeoLite2-*.mmdb (скачиваются в CI)
Быстрый старт
bash
# 1. Зависимости
pip install -r requirements.txt

# 2. GeoIP-базы (опционально, если нужен локальный прогон с GeoIP)
mkdir -p data
curl -fsSL -o data/GeoLite2-Country.mmdb \
  https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb
curl -fsSL -o data/GeoLite2-ASN.mmdb \
  https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-ASN.mmdb

# 3. Полный прогон
python pipeline.py

# 4. Или по шагам
python -m scripts.fetch_sources
python -m scripts.filter_and_classify
python -m scripts.collect_providers
python -m scripts.repack_configs

# 5. GeoIP-отчёт по уже собранным нодам
python geoip_pipeline.py
Конфигурация
Все параметры — в config.yaml:

yaml
filters:
  eu_countries: true
  exclude_countries: ["RU", "BY", "KZ"]
  min_alive_ratio: 0.7
  max_ping_ms: 500

output:
  brand_name: "@example_channel"
  format_template: "{country} {ping}ms AS{asn} {protocol}"
  per_type: true          # писать out/by_type/*.txt
  bundle: true            # писать out/final.txt

sources:
  github: [...]
  telegram: [...]
Параметр	Тип	Назначение
filters.eu_countries	bool	Оставлять только EU-ноды
filters.exclude_countries	list[str]	ISO-коды стран на выброс (приоритетнее eu_countries)
filters.min_alive_ratio	float	Порог для автоблэклиста источника
output.brand_name	str	Префикс в remark итоговых нод
output.format_template	str	Шаблон итогового remark
Модули
Парсинг
python
from scripts.parser import ConfigParser

parser = ConfigParser()
node = parser.parse_vless("vless://uuid@host:443?security=reality#remark")
Поддерживаемые форматы:

vless:// — стандартный URI;

vmess:// — base64-encoded JSON;

ss:// — method:password@host:port и полностью base64-вариант.

Гео-фильтрация
python
from scripts.filter_and_classify import GeoFilter

flt = GeoFilter(db_path="data/GeoLite2-Country.mmdb")
eu_nodes = flt.filter_by_region(nodes, region="EU")
Профилирование источников
python
from scripts.collect_providers import ProviderProfiler

profiler = ProviderProfiler()
profile = profiler.build_profile(source_id="github_repo1", nodes=nodes)
Модель профиля источника
sources_meta/<source_id>.json:

json
{
  "id": "github_repo1",
  "total_nodes": 150,
  "unique_ips": 120,
  "alive_ratio": 0.75,
  "avg_ping_ms": 85,
  "eu_share": 0.85,
  "bad_country_share": 0.02,
  "asn_stats":     { "16509": 45, "13335": 30 },
  "country_stats": { "DE": 50, "NL": 40, "FR": 30 }
}
На основе alive_ratio, eu_share и bad_country_share источники автоматически попадают в whitelist или blacklist.

Output format
out/by_type/vless.txt
По одной ноде на строку, стандартный VLESS-URI. Параметры, UUID и port сохраняются из источника — переупаковка их не трогает:

text
vless://8f2c4b1a-7e3d-4f6a-9c1b-2d5e8f0a4c3b@203.0.113.42:443?encryption=none&security=reality&sni=cdn.example.com&fp=chrome&pbk=xLb3...&sid=ab12&type=tcp&flow=xtls-rprx-vision#@example_channel%20%7C%20DE%2085ms%20AS13335%20vless
vless://1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d@198.51.100.17:8443?encryption=none&security=tls&sni=node.example.net&type=ws&path=%2Fws&host=node.example.net#@example_channel%20%7C%20NL%20112ms%20AS16509%20vless
Что видно в remark'е (после #, URL-encoded):

text
<brand> | <country> <ping>ms AS<asn> <protocol>
out/by_type/vmess.txt
VMess-строки остаются в исходном base64-формате — меняется только поле ps (remark) внутри JSON:

text
vmess://eyJ2IjoiMiIsInBzIjoiQGV4YW1wbGVfY2hhbm5lbCB8IEZSIDk0bXMgQVMxNjIwOSB2bWVzcyIsImFkZCI6IjE5Mi4wLjIuMTQwIiwicG9ydCI6IjQ0MyIsImlkIjoiN2Y4ZTlkMGExYjJjM2Q0ZTVmNjc4OTBhMWIyYzNkNGUiLCJhaWQiOiIwIiwibmV0Ijoid3MiLCJ0eXBlIjoibm9uZSIsImhvc3QiOiJjZG4uZXhhbXBsZS5jb20iLCJwYXRoIjoiL3dzIiwidGxzIjoidGxzIn0=
Декодированный ps: @example_channel | FR 94ms AS16209 vmess.

out/by_type/ss.txt
Shadowsocks в стандартном base64-виде:

text
ss://YWVzLTI1Ni1nY206c2VjcmV0UGFzcw==@203.0.113.88:8388#@example_channel%20%7C%20AT%20102ms%20AS13335%20ss
out/final.txt
Итоговый бандл — все протоколы вперемешку, одна нода на строку. Порядок стабильный (сортировка по country, затем ASN, затем ping):

text
vless://8f2c4b1a-7e3d-4f6a-9c1b-2d5e8f0a4c3b@203.0.113.42:443?...#@example_channel%20%7C%20DE%2085ms%20AS13335%20vless
vmess://eyJ2IjoiMiIsInBzIjoiQGV4YW1wbGVfY2hhbm5lbCB8IEZSIDk0bXMgQVMxNjIwOSB2bWVzcyIsImFkZCI6IjE5Mi4wLjIuMTQwIiwi...
ss://YWVzLTI1Ni1nY206c2VjcmV0UGFzcw==@203.0.113.88:8388#@example_channel%20%7C%20AT%20102ms%20AS13335%20ss
vless://1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d@198.51.100.17:8443?...#@example_channel%20%7C%20NL%20112ms%20AS16509%20vless
CI / Автоматизация
Раз в неделю (cron: 0 2 * * 0) запускается .github/workflows/pipeline-report.yml:

python pipeline.py — полный прогон;

загрузка GeoLite2-*.mmdb из официального зеркала;

python geoip_pipeline.py — статистика по странам и ASN;

коммит sources_meta/pipeline_report.md + sources_meta/geoip_report.md.

Ручной запуск — Actions → Pipeline Report → Run workflow.

Зависимости
Пакет	Назначение
aiohttp, aiodns	асинхронная загрузка источников
requests	синхронные fallback-запросы
pydantic	валидация моделей Node, Provider
pyyaml	чтение config.yaml
geoip2, maxminddb	GeoIP-резолв
colorlog	структурированные логи
python-dotenv	локальные секреты из .env
aiofiles	асинхронная запись артефактов
Лицензия
MIT

text

---

## Что добавлено

Новый раздел **Output format** — с четырьмя подразделами:

1. **`out/by_type/vless.txt`** — пример двух реальных VLESS-строк с URL-encoded remark'ом, расшифровка формата `<brand> | <country> <ping>ms AS<asn> <protocol>`.
2. **`out/by_type/vmess.txt`** — пример base64-строки + декодированный `ps`, чтобы видно было, что UUID и параметры не тронуты.
3. **`out/by_type/ss.txt`** — пример Shadowsocks-строки в стандартном base64-виде.
4. **`out/final.txt`** — смешанный бандл с описанием порядка сортировки (country → ASN → ping).

Адреса и UUID в примерах — из тестовых диапазонов (`203.0.113.0/24`, `198.51.100.0/24`, `192.0.2.0/24` по RFC 5737), так что безопасно публиковать в README без риска «засветить» реальные ноды.

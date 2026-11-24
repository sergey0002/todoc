---
id: doc:after-search-vector
title: AFTER: поиск, эмбеддинги и векторный слой
doc_type: after-plan
lang: ru
source: .doc/plan/search-embeddings-vector.after.md
copied: true
---

# Перспектива (НЕ сейчас): Embeddings, vector search, hybrid fusion, reranking

**Статус:** FUTURE — не реализуется в MVP. Этот файл описывает, **как** перспектива вставится в архитектуру MVP без переписывания ядра.
**Дата:** 24 ноября 2026 года.
**Связанные документы:** [`implementation-plan.md`](../implementation-plan.md) §2 (порты E4/E5), §4 Этап 5 (lexical backend); [`constitution.md`](../constitution.md) §5.3, §6.6, FR-5.9, C11–C12; [`competitive-analysis.md`](../competitive-analysis.md) §4.2 (QMD, Basic Memory, Khoj), §6 C11–C12, §7 таблицы.

---

## 1. Что это и зачем

- **Embeddings + vector search:** семантический поиск по смыслу (синонимы, перефразирования), а не только по точным словам.
- **Hybrid fusion:** BM25/lexical + vector + graph traversal, объединённые через RRF/score fusion.
- **Reranking:** переранжирование top-k кандидатов моделью (локальной или облачной) для повышения точности.
- **External adapters:** QMD bridge, external vector DB (LanceDB/Chroma/Qdrant/Weaviate/Milvus), graph stores (Neo4j/FalkorDB) — как опциональные провайдеры.

**Ценность:** лучше recall на концептуальных запросах («как проверить пользователей» → «authentication middleware»). **Цена:** модель/инфраструктура, latency, приватность (egress), стоимость, сложность.

**Конкуренты-референсы:** QMD (`search` BM25 → `vsearch` vector → `query` hybrid+rerank), Basic Memory (FTS5 + semantic chunks + graph, score-fused), Khoj/AnythingLLM/Open Notebook (RAG с embeddings+rerank), Mem0/Zep (vector/graph memory). Все показывают: vector/hybrid — зрелая технология, но не moat отдельно; важна независимость от поставщика.

## 2. Почему НЕ сейчас

1. **MVP закрывается lexical.** Offline lexical/path/metadata + deterministic rank достаточно для source-native QA и typed query (конституция P5, P12). Vector без benchmark — спекуляция.
2. **Нужен gate:** доказать на frozen queries, что lexical недостаточен (recall/rank ниже baseline), и что hybrid реально выигрывает при заданном бюджете/латентности.
3. **Privacy/egress:** embeddings/rerank могут отправлять документы в облако или требовать локальную модель (RAM/GPU). Без review — нельзя по умолчанию.
4. **Портабельность:** vector DB как истина противоречит P1/P2. Vector — только derived cache, пересобираемый из файлов.

## 3. Архитектурные хуки в MVP (уже заложены)

| Хук | Что уже есть в MVP | Как переиспользуется |
|---|---|---|
| **E4 `CandidateRetriever`** | Одна реализация: offline lexical/path/metadata | Добавить `VectorRetriever`, `GraphRetriever`, `QmdBridgeRetriever` как новые реализации; `SearchHit` contract не меняется |
| **E5 `Ranker`/`Reranker`/`Renderer`** | Deterministic rank + bounded projection renderer | Добавить `HybridFusionRanker` (RRF), `ModelReranker` (opt-in); fallback на lexical при недоступности |
| **E6 `GenerationStore` / cache** | Atomic generations + per-doc JSON shards; cache key включает parser/schema/query digest | Добавить `cache/search/` shards для embeddings/vector representations; инвалидация по content hash + model version + chunking policy |
| **E10 `OutputSerializer`** | JSON envelope + `truncated`/cursor/provenance | Добавить `retrieval_mode`, `scores`, `model_id` как optional поля; envelope не ломается |
| **Config** | `dataset.json` с `limits`, `enabled_formats`, trusted workflows | Добавить `search` секцию: `mode: lexical\|hybrid`, `embedding_model`, `vector_store`, `reranker`, `egress: local\|cloud\|off`, `budget` |

**Инвариант:** lexical остаётся default и fallback. Любой vector/rerank провайдер — opt-in, с явным consent и видимым `retrieval_mode` в отчёте (NFR-4).

## 4. Пошаговый план внедрения (когда gate пройден)

### Шаг 1 — Benchmark gate (до кода)

1. Зафиксировать frozen corpus + held-out queries (из Этапа 0) + baseline lexical (Recall@k/MRR/nDCG, latency, bytes/tokens).
2. Прогнать QMD (`search` vs `vsearch` vs `query`) и, при необходимости, Basic Memory hybrid на тех же задачах. Отделять self-reported метрики авторов от собственного теста.
3. **Go/no-go:** hybrid выигрывает на выбранных задачах при заданном бюджете/латентности и privacy-ограничениях. Иначе — не внедрять, остаться на lexical.

### Шаг 2 — Локальный vector retriever (без облака)

1. Выбрать embedding-модель (локальную, например `nomic-embed-text` через Ollama, как в mdkb; или ONNX, как в mcp-memory-service). Зафиксировать модель + chunking policy + tokenizer в cache key.
2. Реализовать `VectorRetriever` (E4): чанкинг Markdown/CSV/JSON → embeddings → локальный индекс (SQLite + vector extension или файловая структура) в `.todoc/cache/search/`. Индекс — derived, удаляемый, пересобираемый.
3. Реализовать `HybridFusionRanker` (E5): RRF (k=60, как в QMD) для lexical+vector; top-rank bonus — только если доказан benchmark-ом.
4. Добавить CLI-флаги: `docs search --mode lexical|vector|hybrid` (default `lexical`); `--mode hybrid` требует явного opt-in в конфиге.
5. Тесты: contract tests для нового retriever (тот же `SearchHit` contract); cold-rebuild (удалить vector cache → пересборка); offline (без сети); fallback (отключить модель → lexical).

### Шаг 3 — Reranker (opt-in)

1. Выбрать reranker (локальный LLM или облачной — только с egress review). Зафиксировать модель + лимиты (top-k, timeout, budget).
2. Реализовать `ModelReranker` (E5): переранжирование top-k после fusion; fallback на fusion при недоступности/таймауте.
3. Добавить `--rerank` флаг (default off) + `retrieval_mode`/`model_id` в отчёт.
4. Тесты: latency/budget; fallback; privacy (что отправляется в модель).

### Шаг 4 — External adapters (QMD bridge, vector DB, graph DB)

1. Реализовать `QmdBridgeRetriever` (E4): тонкий adapter поверх QMD CLI/library (`qmd search/vsearch/query --json`); `todoc` остаётся authority для типов/валидации, QMD — только retrieval.
2. Реализовать external vector/graph adapters (LanceDB/Chroma/Qdrant/Weaviate/Milvus/Neo4j/FalkorDB) — только по подтверждённой боли (масштаб/латентность, которую локальный индекс не закрывает). Каждый — отдельный adapter + privacy review + benchmark.
3. Graph traversal retrieval: `relations graph` уже есть в MVP как derived index; добавить graph-aware retrieval (neighbours как кандидаты) только после benchmark.

### Шаг 5 — Eval и CI

1. Добавить `eval` для hybrid/rerank (референс Open Knowledge: MRR/Recall@k/nDCG@k + embedding-uplift gate).
2. Зафиксировать regression gate: hybrid не должен регрессировать lexical на exact-term задачах.

## 5. Данные и миграции

- **Schema:** добавить `search` секцию в `dataset.json` (`schema_version` bump + migrate/check). Старые конфиги без секции → `mode: lexical` по умолчанию.
- **Cache:** новые shards в `.todoc/cache/search/` с cache key (content hash + model version + chunking policy + query schema digest). Старые generations остаются валидны; новые — с новым `generation_id`.
- **Миграция:** `todoc index rebuild --search hybrid` пересобирает vector cache из файлов. Удаление vector cache не теряет истину (P1).

## 6. Безопасность / приватность / производительность

- **Privacy:** default `egress: off` (только локальные модели). Cloud embeddings/rerank — только с явным consent + documented data flow (что отправляется, куда, retention). Валидность схемы не даёт права читать файл (NFR-1).
- **Безопасность:** embedding-модель и reranker — только из установленного окружения (allowlist), не из DATA_ROOT (P10). Query — только allowlisted AST, без `eval`/SQL.
- **Производительность:** измерять cold start (загрузка модели), latency per mode, RAM/GPU. `search` (BM25) — ~0.2s; `vsearch` — секунды; `query` (hybrid+rerank) — дороже. Документировать для каждого режима.

## 7. Benchmark / gate критерии

- Hybrid Recall@k/MRR/nDCG > lexical на held-out концептуальных запросах при заданном бюджете.
- Lexical не регрессирует на exact-term задачах (code identifiers, names, phrases).
- Latency/budget в пределах заявленных лимитов; fallback работает при недоступности модели.
- Privacy review пройден (data flow задокументирован, consent явный).
- Cold-rebuild + offline тесты пройдены.

## 8. Что НЕ делать

- НЕ делать vector DB истиной (P1). Vector — derived cache.
- НЕ делать embeddings/rerank default без gate (P5, P12).
- НЕ отправлять документы в облако без consent (NFR-7).
- НЕ менять `SearchHit`/`Diagnostic` контракты ради нового провайдера (E4/E5 инвариант).
- НЕ конкурировать «ещё одним общим поиском» без benchmark против QMD/Basic Memory.
- НЕ копировать QMD processors (доверенный код в индексе) — противоречит P10.

## 9. Связи

- Зависит от: Этап 5 MVP (lexical backend + порты E4/E5 + benchmark).
- Блокирует: ничего в MVP. Веб (`web-ui.after.md`) может использовать hybrid поиск, но не требует его.
- Связано с: `plugins-formats-import.after.md` (importers для PDF/DOCX/XLSX — источники для embeddings), `memory-llm-wiki.after.md` (semantic memory — отдельный профиль).

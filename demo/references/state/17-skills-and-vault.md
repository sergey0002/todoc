---
created: 2026-11-26
updated: 2026-11-28
id: doc:state-skills-vault
title: "Состояние: скилы — vault и жизненный цикл"
doc_type: reference
lang: ru
source: docs/state/17-skills-and-vault.md
copied: true
---

# 17. Скилы и хранилище

По умолчанию движок сканирует `skills/` внутри DATA_ROOT. `--vault` указывает другое хранилище внутри корня. Скил определяется наличием `SKILL.md`. Front matter содержит `name` и `description`, рядом могут быть каталоги `references/`, `scripts/` и `assets/`. Разделы могут задавать заголовок, описание, порядок и алиасы в `.config.json`.

| Команда | Контракт |
|---|---|
| `skills tree` | Живой обход без индекса. `--query`, `--within`, `--depth`, `--limit`, `--cursor` и проекции. Доступны `tree` и `flat`, неизвестный вид даёт fallback к дереву |
| `skills read --path P` | Проверенное содержимое `data.result.content`. Поддерживает `--line-range` и Unicode-бюджет |
| `skills attach --to DIR` | Предпросмотр установки диспетчера во внешнюю цель. `--apply` выполняет план, `--force` разрешает обновить существующую цель |
| `skills import --src PATH --into SECTION` | Предпросмотр импорта. `--apply` копирует выбранный скил, `--adopt` управляет принятием существующего назначения согласно справке |

Папка с префиксом `!` скрывает скил и потомков до передачи `--all`. Оглавление сохраняет структурные `id` и `path` при проекции. Для подключения агента устанавливается диспетчер, а навигация по хранилищу происходит через CLI.

[Полные опции](https://github.com/sergey0002/todoc/blob/master/docs/state/cli.md) · [Контракт агента](../../notes/agent-contract.md)

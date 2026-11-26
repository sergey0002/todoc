---
id: doc:export-rasa-glossary
title: "Экспорт Rasa NLU: глоссарий"
doc_type: export
lang: ru
created: 2026-11-26
updated: 2026-11-26
derived_from: ["records/terms/data-root.json#/definition@sha256:4431876e91a5dd56a31a3268fff2349873358c3a137f08e06ea6e3bbe130485d", "records/terms/diagnostic.json#/definition@sha256:ea627394e4d7694920417b3315608e54526a40511a29db9bfd8d917407e3fb39", "records/terms/dir-type.json#/definition@sha256:f14afc6c3f1ebfbab24d5ccae4166070f994908c7dcb81e1ad08bba180a2c432", "records/terms/doc-type.json#/definition@sha256:00be7d85493b5f0a6d89fec4d9451800fab7559d6a19896313eb0628e972f83b", "records/terms/entity-type.json#/definition@sha256:00f97720d78c0c57ff9f9b86b3ae91ee4846a03772a9991546741ddcf9aabdb2", "records/terms/envelope.json#/definition@sha256:3d77cacae00dd7003dfc33133a68161c4049ae78c7725699c174535b4f4653e5", "records/terms/generation.json#/definition@sha256:ad8a3a8ab550134aa41d1c9254e384b2c64724808eecd9492ef8e67cbcfc7010", "records/terms/relation-type.json#/definition@sha256:803c68b15c92cfaf3ecaea805e6b1bf2b7dc24c9cb2a441f45f111331346fd6c", "records/terms/reserved-basename.json#/definition@sha256:cd4de19baf6d9228cba858167485d2c91d74a0ba4d05e4fbcdf761a0639a6b16", "records/terms/write-plan.json#/definition@sha256:180318fa95801c8634b38127c34c0d722952fcaea6ed9a35e13b6cfc7fe31107"]
tags: [export, interop, rasa]
---

# Экспорт Rasa NLU: глоссарий

Derived-артефакт: сгенерирован `todoc interop export --kind rasa` из записи-источника
(см. `derived_from`). Правка записи-источника сделает этот файл stale (`todoc stale`).
Перегенерация: та же команда с тем же `--write` — цель перезаписывается поверх CAS-хэша,
ручные файлы (без `derived_from`) не трогаются. Записи датасета экспорт не меняет.

```yaml
version: "3.1"
nlu:
- intent: term_data-root
  examples: |
    - Корень переносимой папки данных: обычные файлы + .todoc/.
    - Всё производное (индекс, кэш) пересобирается из него.
    - Не путать с каталогом Skill (SKILL.md + references/).
- intent: term_diagnostic
  examples: |
    - Найденная проблема: code, severity, path, location (line/column), evidence, suggested_fixes.
    - Идентификатор diag_* стабилен только внутри одного запуска.
- intent: term_dir-type
  examples: |
    - Тип папки.
    - Присваивается правилами directory-rules.json по basename или маске, затем зарезервированными именами.
    - Влияет на маршрутизацию и валидацию, но не перемещает файлы.
- intent: term_doc-type
  examples: |
    - Тип документа.
    - Присваивается правилами document-rules.json: явное объявление в front matter (приоритет 200) важнее маски папки (приоритет 100).
    - Не равен формату и не равен dir_type.
- intent: term_entity-type
  examples: |
    - Тип записи (сущности) JSON: описатель с required_fields, path_template, views, единицами измерения.
    - Записи создаются create-only и валидируются по JSON Schema из .todoc/entity_types/<entity_type>/schema.json.
- intent: term_envelope
  examples: |
    - Единая форма вывода: schema_version, ok, data, diagnostics, next_actions.
    - В stdout — ровно один JSON-текст; человекочитаемые режимы table/markdown рендерят те же факты.
- intent: term_generation
  examples: |
    - Атомарно публикуемый снимок .todoc/index/generations/<id>/: folders, documents, records, relations, diagnostics.
    - CURRENT.json переключается только после успешной записи.
- intent: term_relation-type
  examples: |
    - Тип направленного ребра графа между записями.
    - type_id обязан существовать в реестре, target.id обязан указывать на существующую запись.
- intent: term_reserved-basename
  examples: |
    - Имя папки с закреплённым dir_type: .research, architecture, constitution, harness, glossary, plan.
    - Срабатывает, когда правила не дали результата.
- intent: term_write-plan
  examples: |
    - План записи до применения: target_path, new_content, expected_hash, new_hash, conflict.
    - Пишется только после review-first подтверждения (--preview → --apply).
```


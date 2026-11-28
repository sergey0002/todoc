---
created: 2026-11-25
updated: 2026-11-28
id: doc:state-benchmark
title: "Состояние: бенчмарк качества и сравнение с конкурентами"
doc_type: reference
lang: ru
source: docs/state/15-benchmark.md
copied: true
---

# 15. Бенчмарк качества

На выпуске единого CLI K1–K30 получили `pass`, итоговая оценка 29,9 из 30.
K19 ограничивает полезный текст 500 символами Unicode. Размер конверта с
метаданными измеряется отдельно. [Результаты выпуска](../../notes/unified-cli-release.md)

На интеграционном демо K22 дал Recall@3 и Precision@3 0,86 и MRR 0,96 для
12 запросов. K27 уложился во все шесть бюджетов. Обзор 20 идей по четырём
полям дал 3654 байта UTF-8 и 1077 токенов `o200k_base`.

## Воспроизведение

```bash
results="$(mktemp -d)"
PYTHONPATH=src .venv/bin/python bench/run_benchmark.py --skip-competitors --results-dir "$results"
```

Сценарий создаёт изолированные копии демо, вносит размеченные дефекты в одну
копию, измеряет время и пишет `benchmark.json` и `benchmark.md`. `--quick`
уменьшает число повторов латентности. Частичный результат может завершиться
с кодом 0, поэтому проверяйте статусы всех критериев. Проверки используют
PyYAML для K8 и coverage для K29.

[Критерии K1–K30](https://github.com/sergey0002/todoc/blob/master/bench/criteria.md) · [Исторический отчёт](https://github.com/sergey0002/todoc/blob/master/bench/results/benchmark.md) · [Тестовый гейт](10-testing-and-quality.md)

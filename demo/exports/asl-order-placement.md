---
id: doc:export-asl-order-placement
title: "Экспорт ASL: flow:order-placement"
doc_type: export
lang: ru
created: 2026-11-26
updated: 2026-11-26
derived_from: ["records/flows/order-placement.json#/tree@sha256:d81ace2f3a6b77c8eeaeaee9063bc4e7195ba5eeec39b949430a8da4a6829a41"]
tags: [export, interop, asl]
---

# Экспорт ASL: flow:order-placement

Derived-артефакт: сгенерирован `todoc interop export --kind asl` из записи-источника
(см. `derived_from`). Правка записи-источника сделает этот файл stale (`todoc stale`).
Перегенерация: та же команда с тем же `--write` — цель перезаписывается поверх CAS-хэша,
ручные файлы (без `derived_from`) не трогаются. Записи датасета экспорт не меняет.

```json
{
  "Comment": "flow:order-placement: Оформление заказа",
  "StartAt": "start",
  "States": {
    "start": {
      "Type": "Task",
      "Resource": "todoc:start",
      "Next": "q-account"
    },
    "q-account": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.q-account",
          "StringEquals": "да",
          "Next": "out-acc-blocked"
        },
        {
          "Variable": "$.q-account",
          "StringEquals": "нет",
          "Next": "q-funds"
        }
      ]
    },
    "out-acc-blocked": {
      "Type": "Fail",
      "Error": "ACC_BLOCKED",
      "Cause": "Заказ отклоняется"
    },
    "q-funds": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.q-funds",
          "StringEquals": "нет",
          "Next": "out-no-funds"
        },
        {
          "Variable": "$.q-funds",
          "StringEquals": "да",
          "Next": "q-gateway"
        }
      ]
    },
    "out-no-funds": {
      "Type": "Fail",
      "Error": "INSUFFICIENT_FUNDS",
      "Cause": "Отказ оплаты"
    },
    "q-gateway": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.q-gateway",
          "StringEquals": "нет",
          "Next": "out-retry"
        },
        {
          "Variable": "$.q-gateway",
          "StringEquals": "да",
          "Next": "out-paid"
        }
      ]
    },
    "out-retry": {
      "Type": "Task",
      "Resource": "todoc:out-retry",
      "Next": "q-gateway"
    },
    "out-paid": {
      "Type": "Succeed"
    }
  }
}
```


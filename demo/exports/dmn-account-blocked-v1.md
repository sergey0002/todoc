---
id: doc:export-dmn-account-blocked-v1
title: "Экспорт DMN: rule:account-blocked-v1"
doc_type: export
lang: ru
created: 2026-11-26
updated: 2026-11-26
derived_from: ["records/rules/account-blocked-v1.json#/statement@sha256:fb9ab7ce60fa7dcc6e53911c5489a671b48ea248b472053cbad7d3a1108c71c5", "records/rules/account-blocked-v1.json#/examples@sha256:3f2942b5a11d94d46724479b5b57a5e19d62f021d3d1626a3070373d7bbec072", "records/flows/order-placement.json#/tree@sha256:d81ace2f3a6b77c8eeaeaee9063bc4e7195ba5eeec39b949430a8da4a6829a41"]
tags: [export, interop, dmn]
---

# Экспорт DMN: rule:account-blocked-v1

Derived-артефакт: сгенерирован `todoc interop export --kind dmn` из записи-источника
(см. `derived_from`). Правка записи-источника сделает этот файл stale (`todoc stale`).
Перегенерация: та же команда с тем же `--write` — цель перезаписывается поверх CAS-хэша,
ручные файлы (без `derived_from`) не трогаются. Записи датасета экспорт не меняет.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" id="definitions-account-blocked-v1" name="Блокировка аккаунта останавливает оплату" namespace="todoc">
  <decision id="decision-account-blocked-v1" name="Блокировка аккаунта останавливает оплату">
    <decisionTable hitPolicy="UNIQUE">
      <input id="input-given" label="Ситуация"><inputExpression id="input-given-expr" typeRef="string"><text>given</text></inputExpression></input>
      <input id="input-when" label="Условие"><inputExpression id="input-when-expr" typeRef="string"><text>when</text></inputExpression></input>
      <input id="input-mode" label="Режим"><inputExpression id="input-mode-expr" typeRef="string"><text>mode</text></inputExpression></input>
      <output id="output-outcome" label="Исход" name="outcome" typeRef="string"/>
    <rule id="rule-1">
      <inputEntry id="rule-1-inputEntry-9"><text>аккаунт покупателя заблокирован</text></inputEntry>
      <inputEntry id="rule-1-inputEntry-10"><text>покупатель оформляет заказ</text></inputEntry>
      <inputEntry id="rule-1-inputEntry-11"><text>auto</text></inputEntry>
      <outputEntry id="rule-1-output"><text>ACC_BLOCKED</text></outputEntry>
    </rule>
    <rule id="rule-2">
      <inputEntry id="rule-da-input-1"><text></text></inputEntry>
      <inputEntry id="rule-da-input-2"><text>да</text></inputEntry>
      <inputEntry id="rule-da-input-3"><text>auto</text></inputEntry>
      <outputEntry id="rule-da-output"><text>ACC_BLOCKED</text></outputEntry>
    </rule>
    </decisionTable>
  </decision>
</definitions>
```


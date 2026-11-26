# Правка: `agent-skill`

Правка скила — review-first: patch + предпросмотр + hash. `name` и папка не меняются
(идентичность скила); `description` правится, если сменился охват «что + когда».

## Как

```bash
todoc docs read --root KB --path skill/<имя>/SKILL.md --output json   # hash
todoc docs edit --root KB --path skill/<имя>/SKILL.md --patch-file patch.txt --preview
todoc docs edit --root KB --path skill/<имя>/SKILL.md --patch-file patch.txt --apply --if-hash <hash>
```

После — `todoc validate --root KB --all` — 0 диагностик; поиск находит по новым словам.

"""Pure, byte-preserving Markdown metadata and link transformations for moves."""
from __future__ import annotations
import json
from todoc.adapters.formats.markdown import parse_markdown


def set_metadata(text: str, key: str, value: object) -> str:
    """Set one YAML-lite field; preserve body and every other line verbatim."""
    bom = '\ufeff' if text.startswith('\ufeff') else ''
    lines = text.removeprefix(bom).splitlines(keepends=True)
    nl = '\r\n' if '\r\n' in text else '\n'
    encoded = key + ': ' + json.dumps(value, ensure_ascii=False)
    if lines and lines[0].strip() == '---':
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
        if close is not None:
            indexes = [i for i in range(1, close) if lines[i].partition(':')[0].strip() == key]
            if indexes:
                for i in indexes:
                    lines[i] = encoded + nl
            else:
                lines.insert(close, encoded + nl)
            return bom + ''.join(lines)
    return bom + '---' + nl + encoded + nl + '---' + nl + text.removeprefix(bom)


def rewrite_identity(text: str, doc: dict, target: str, keep_id: bool, pin_type: bool) -> tuple[str, str]:
    fm = parse_markdown(text).front_matter
    old = doc['document_id']
    new = old if keep_id or old != 'doc:' + doc['path'] else 'doc:' + target
    if (new != old and 'id' in fm) or (keep_id and 'id' not in fm):
        text = set_metadata(text, 'id', new)
    if pin_type and 'doc_type' not in fm and doc['doc_type'] != 'unknown':
        text = set_metadata(text, 'doc_type', doc['doc_type'])
    return text, new


import copy
import posixpath
import re
from pathlib import PurePosixPath
from urllib.parse import quote
from todoc.adapters.formats.markdown import editable_link_spans, resolve_link_target
from todoc.adapters.formats.metadata import get_attributes
from todoc.application.validator import _basename_index, _wikilink_candidates
from todoc.application.staleness import parse_anchor, format_anchor, fragment_hash_text, dependencies_of
from todoc.application.write import bump_front_matter_updated
from todoc.errors import ValidationError, ConflictError


def warning(code: str, path: str) -> dict:
    return {'code': code, 'severity': 'warning', 'path': path, 'message': code,
            'location': {}, 'evidence': '', 'suggested_fixes': []}


def rewrite_links(text: str, path: str, source: str, target: str, paths: set[str], records: set[str]) -> tuple[str, int]:
    old_index = _basename_index(paths)[0]
    new_index = _basename_index((paths - {source}) | {target})[0]
    new_path = target if path == source else path
    edits = []
    for span in editable_link_spans(text):
        link = span.link
        if link.target in records:
            continue
        if link.is_wikilink:
            candidates = _wikilink_candidates(link.target, old_index)
            if source not in candidates:
                continue
            name = PurePosixPath(target).name if link.target.endswith(PurePosixPath(source).suffix) else PurePosixPath(target).stem
            if len(candidates) != 1 or _wikilink_candidates(name, new_index) != [target]:
                raise ValidationError('Ambiguous wikilink.', 'move.wikilink_ambiguous')
            replacement = name
            original = link.target
        else:
            resolved = resolve_link_target(path, link.target, parsed=True)
            if resolved is None or (path != source and resolved != source):
                continue
            resolved = target if resolved == source else resolved
            replacement = quote(posixpath.relpath(resolved, posixpath.dirname(new_path) or '.'), safe='/.-_~')
            if link.fragment:
                replacement += '#' + quote(link.fragment, safe='/-_~:')
            original = quote(link.target, safe='/.-_~') + ('#' + quote(link.fragment, safe='/-_~:') if link.fragment else '')
        if replacement == original:
            continue
        if span.destination_start is None:
            raise ValidationError('Affected link has no proven edit span.', 'move.link_unsupported')
        edits.append((span.destination_start, span.destination_end, replacement))
    for a, b, replacement in sorted(edits, reverse=True):
        text = text[:a] + replacement + text[b:]
    return text, len(edits)


def rewrite_attributes(attrs: dict, *, source: str, target: str, old_id: str, new_id: str,
                       paths: set[str], record_ids: set[str]) -> dict:
    value = copy.deepcopy(attrs)
    for key in ('source_path', 'source', 'sources', 'artifacts'):
        field = value.get(key)
        if field == source:
            value[key] = target
        elif isinstance(field, list):
            value[key] = [target if x == source else x for x in field]
    baseline = value.get('baseline')
    if isinstance(baseline, dict) and isinstance(baseline.get('artifacts'), dict) and source in baseline['artifacts']:
        artifacts = baseline['artifacts']
        if target in artifacts:
            raise ConflictError('Baseline path key collision.', 'move.metadata_collision')
        artifacts[target] = artifacts.pop(source)
    if isinstance(value.get('covers'), list):
        value['covers'] = [new_id if x == old_id else x for x in value['covers']]
    if isinstance(value.get('related'), list):
        result = []
        for item in value['related']:
            if isinstance(item, str):
                item = rewrite_links(item, '.', source, target, paths, record_ids)[0]
            result.append(item)
        value['related'] = result
    return value


def rewrite_dependencies(attrs: dict, before: str, after: str, source: str, target: str,
                         owner_path: str) -> tuple[dict, list[dict]]:
    value = copy.deepcopy(attrs)
    warnings = []
    deps = value.get('derived_from')
    if not isinstance(deps, list):
        return value, warnings
    changed = []
    ack_mapping: dict[str, set[str]] = {}
    for item in deps:
        dep = parse_anchor(item) if isinstance(item, str) else copy.deepcopy(item)
        if not isinstance(dep, dict) or dep.get('path') != source:
            changed.append(item)
            continue
        old_actual, _ = fragment_hash_text(before, dep)
        new_actual, status = fragment_hash_text(after, dep)
        dep['path'] = target
        if dep.get('hash') == old_actual and status == 'ok':
            dep['hash'] = new_actual
        else:
            warnings.append(warning('move.preexisting_stale', owner_path))
        if old_actual and new_actual:
            ack_mapping.setdefault(old_actual, set()).add(new_actual)
        changed.append(format_anchor(dep) if isinstance(item, str) else dep)
    value['derived_from'] = changed
    ack = value.get('stale_ack_hashes')
    if ack and ack_mapping:
        ack = [ack] if isinstance(ack, str) else ack
        # A hash may acknowledge several different dependencies. Do not global-replace.
        affected = set(ack_mapping) & set(ack)
        if affected:
            value['stale_ack_hashes'] = [h for h in ack if h not in affected]
            warnings.append(warning('move.ack_invalidated', owner_path))
    return value, warnings


def write_attributes(text: str, old: dict, new: dict) -> str:
    for key, value in new.items():
        if old.get(key) != value:
            text = set_metadata(text, key, value)
    return text


def rewrite_corpus(ctx, payload: dict, source: str, target: str, old_id: str,
                   new_id: str, initial: bytes) -> tuple[tuple, dict, tuple]:
    from todoc.application.move import MoveFile, read_bytes
    paths = {d['path'] for d in payload['documents']}
    record_ids = {r['record_id'] for r in payload['records']}
    originals, texts, attrs, json_values = {}, {}, {}, {}
    counts = {'links': 0, 'records': 0, 'derived_from': 0}
    warnings = []
    for doc in payload['documents']:
        path = doc['path']
        if doc['format'] not in ('markdown', 'json'):
            continue
        raw = read_bytes(ctx, doc)
        originals[path] = raw
        if doc['format'] == 'markdown':
            text = initial.decode('utf-8') if path == source else raw.decode('utf-8')
            text, count = rewrite_links(text, path, source, target, paths, record_ids)
            counts['links'] += count
            attributes = parse_markdown(text).front_matter
            attrs[path] = attributes
            new = rewrite_attributes(attributes, source=source, target=target, old_id=old_id,
                                     new_id=new_id, paths=paths, record_ids=record_ids)
            texts[path] = write_attributes(text, attributes, new)
        else:
            data = json.loads(raw)
            attributes = get_attributes('json', data)[0]
            attrs[path] = attributes
            new = rewrite_attributes(attributes, source=source, target=target, old_id=old_id,
                                     new_id=new_id, paths=paths, record_ids=record_ids)
            if isinstance(data, dict):
                data = {**data, 'meta': new} if 'meta' in data and 'record_id' not in data else new
            json_values[path] = data
    # Bump bodies before hashing dependencies against the final moved text.
    for path, text in texts.items():
        if path == source or text.encode('utf-8') != originals[path]:
            texts[path] = bump_front_matter_updated(text)[0]
    moved_text = texts[source]
    # Cycles involving the moved source cannot be re-anchored to a fixed point.
    graph = {p: [d['path'] for d in dependencies_of(a)] for p, a in attrs.items()}
    def reaches(node, seen):
        if node == source:
            return True
        if node in seen:
            return False
        return any(reaches(n, seen | {node}) for n in graph.get(node, []))
    if any(reaches(n, set()) for n in graph.get(source, [])):
        raise ValidationError('Cyclic dependency includes source.', 'move.dependency_cycle')
    for path, old in attrs.items():
        if path in texts:
            current = parse_markdown(texts[path]).front_matter
        else:
            current = get_attributes('json', json_values[path])[0]
        new, findings = rewrite_dependencies(current, originals[source].decode('utf-8'), moved_text, source, target, path)
        warnings.extend(findings)
        if current.get('derived_from') != new.get('derived_from'):
            counts['derived_from'] += 1
        if path in texts:
            texts[path] = write_attributes(texts[path], current, new)
            if texts[path].encode('utf-8') != originals[path]:
                texts[path] = bump_front_matter_updated(texts[path])[0]
        elif isinstance(json_values[path], dict):
            if 'meta' in json_values[path] and 'record_id' not in json_values[path]:
                json_values[path]['meta'] = new
            else:
                json_values[path] = new
    files = [MoveFile(target, None, texts[source].encode('utf-8')), MoveFile(source, originals[source], None)]
    for path in sorted(originals.keys() - {source}):
        if path in texts:
            after = texts[path].encode('utf-8')
        else:
            value = json_values[path]
            if value == json.loads(originals[path]):
                continue
            after = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
            counts['records'] += 1
        if after != originals[path]:
            if '/deltas/' in path:
                raise ConflictError('Historical delta would change.', 'move.active_change_conflict')
            files.append(MoveFile(path, originals[path], after))
    affected = {f.path for f in files}
    from todoc.application.changes import parse_delta, contained_delta_target
    for path in texts:
        if '/deltas/' in path:
            delta = parse_delta(originals[path].decode('utf-8'))
            resolved = contained_delta_target(ctx.root, delta['target'])
            if resolved is not None and resolved.resolve().relative_to(ctx.root.resolve()).as_posix() in affected:
                raise ConflictError('An active or historical delta targets an affected path.', 'move.active_change_conflict')
    return tuple(files), counts, tuple(warnings)

# Changelog entries

Project configuration and mapping updates write entries to
`.fmu/logs/changelog.json`. Each entry contains a short `change` description and
an optional `structured_diff` list. New descriptions do not embed old and new
values. The structured field contains that data once.

For example, changing a model name produces a description such as
`Updated field 'model.name'.` and this diff:

```json
[
  {"field_path": "model.name", "before": "old", "after": "new"}
]
```

A missing or null `structured_diff` means the entry has no structured comparison.
This includes historical entries and events such as initialization, copying, and
restoring. Consumers can parse historical `change` strings when necessary.
An empty list means the comparison ran and found no value changes. Consumers
must not fall back to the string parser for an empty list.

Updates retain the current per-key logging behavior, including repeated writes
of identical values. A parent-key entry can contain several nested field diffs.
Overlapping parent and child updates assign each diff once to the most specific
matching key. Comparisons use the validated saved resource and ignore the
project metadata fields configured in `diff_ignore_fields`.

## Mapping differences

List diffs contain `added`, `removed`, and `updated` items. Updated items contain
complete before and after values for the affected item. Unchanged items do not
appear in the payload.

Mappings use the composite identity `mapping_type`, `source_system`,
`target_system`, and `source_id`. This follows the mapping collection's uniqueness
rules. Editing a target identifier, UUID, or relationship keeps the identity and
produces an updated item. Changing a source identifier or system produces removed
and added items. JSON represents the composite identity as an array.

Mapping list order does not affect these differences. The helper rejects
duplicate composite identities instead of silently dropping items. Other lists
use their configured `diff_list_keys`. Lists without a configured key remain
whole before and after values. A transition between null and a nested object
can also contain the whole changed subtree.

## Compatibility and rollout

Existing entries load without migration. Appending, filtering, and merging retain
their descriptions and any structured values already present. The existing
scalar log filters do not support filtering on the nested `structured_diff` field.

The API imports `ChangeInfo` from this library, so upgrading its library dependency
exposes the field in responses and OpenAPI. GUI clients need regenerated types
and must render the structured field when it is non-null. Older clients can still
show the short descriptions, but cannot show the new detailed differences.

Upgrade all writers that share a project directory. Older library versions ignore
unknown fields and can discard `structured_diff` when rewriting the log. This
change does not provide lossless writes from those older versions.

A successful resource save precedes its changelog write. These writes are not
transactional. This change does not alter that failure behavior or set a log
retention limit.

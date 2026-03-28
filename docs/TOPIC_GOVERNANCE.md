# Topic Governance

Topic governance keeps the graph understandable as the platform grows. A topic list that expands without review becomes harder to search, harder to maintain, and more likely to accumulate duplicate concepts that split relevance across multiple nodes.

## Why topic caps matter

`agentic-brain` now uses a **soft topic cap of 100** with a **warning threshold at 75**.

The cap is intentionally soft rather than hard:

- it protects graph quality without blocking legitimate growth
- it creates early visibility before topic sprawl becomes expensive to fix
- it encourages consolidation of overlapping concepts instead of endlessly minting new labels
- it keeps quarterly governance work small, predictable, and reviewable

### What the audit checks

The quarterly audit focuses on four governance signals:

1. **Topic count** — whether the graph is healthy, nearing the cap, or over it
2. **Orphan topics** — topic nodes with no relationships
3. **Orphan nodes** — any disconnected nodes that cannot be reached through normal traversal
4. **Duplicate or similar topics** — candidates for consolidation into a canonical topic

## Running the audit

### CLI

```bash
agentic-brain topics audit
```

Useful options:

```bash
agentic-brain topics audit --format json
agentic-brain topics audit --limit 20
agentic-brain topics audit --output reports/topic-audit.md
agentic-brain topics audit --uri bolt://localhost:7687 --database neo4j
```

### Standalone script

```bash
python3 scripts/quarterly-audit.py
```

Useful options:

```bash
python3 scripts/quarterly-audit.py --format markdown --output reports/topic-audit.md
python3 scripts/quarterly-audit.py --format json
```

Neo4j connection settings default from:

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `NEO4J_DATABASE`

## Health status meanings

| Status | Meaning | Action |
| --- | --- | --- |
| `healthy` | Fewer than 75 topics | Continue normal monitoring |
| `warning` | 75-99 topics | Schedule consolidation this quarter |
| `soft-cap-exceeded` | 100 or more topics | Pause new topic creation until cleanup is complete |

## Merge procedure

When the audit suggests a merge:

1. **Pick a canonical topic**
   - prefer the topic with the strongest relationship count
   - prefer the clearer, shorter, more stable name
2. **Review relationships**
   - verify the candidate topics represent the same business concept
   - confirm there is no domain-specific reason to keep them separate
3. **Move references**
   - reconnect downstream nodes to the canonical topic
   - preserve identifiers and traceability if external systems reference the old node
4. **Archive or delete the duplicate**
   - archive first if your governance process requires a review trail
   - delete only after confirming the duplicate is no longer referenced
5. **Re-run the audit**
   - confirm the duplicate is gone
   - confirm orphan counts did not increase

## Recommended quarterly workflow

1. Run `agentic-brain topics audit`
2. Save the report to versioned output
3. Review merge suggestions with a maintainer
4. Fix orphan topics and duplicate topics
5. Re-run the audit and keep the post-cleanup report

## Governance policy summary

- keep topic creation intentional
- prefer reuse over synonyms
- audit every quarter
- treat duplicate topics as a relevance bug, not a cosmetic issue
- keep the graph below the soft cap whenever possible

# OMG Compliance Review for agentic-brain

## Executive summary

**Assessment:** Partially compliant with OMG-style modelling practices.  
**Overall status:** **Needs remediation before claiming strong OMG/JDL-style model-driven compliance.**

| Area | Status | Summary |
| --- | --- | --- |
| UML | Partial | Sequence/component views exist in the repo, but ADL-specific class and state diagrams were missing before this review. |
| MOF | Partial | `parser.py` defines a useful abstract syntax model, but `entity_parser.py` introduces a second incompatible metamodel. |
| OCL | Low | Constraints exist as imperative Python checks, not as formal invariants, preconditions, or postconditions. |
| MDA | Partial | ADL config generation is implemented, but entity-generation transformations are not traceable end-to-end and the advertised 7-layer flow is not wired into the main pipeline. |

## Scope reviewed

- `src/agentic_brain/adl/parser.py`
- `src/agentic_brain/adl/entity_parser.py`
- `src/agentic_brain/adl/entity_generator.py`
- `src/agentic_brain/adl/generator.py`
- `src/agentic_brain/cli/__init__.py`
- `src/agentic_brain/cli/commands.py`
- `src/agentic_brain/business/base.py`
- `src/agentic_brain/business/retail.py`
- `src/agentic_brain/orchestration/workflow.py`
- `docs/ADL.md`
- `docs/ADL_ENTITIES.md`
- `tests/test_adl.py`
- `tests/adl/test_adl_parser.py`
- `tests/adl/test_adl_cli.py`

## What is already good

1. **Clear ADL metamodel foundation**
   - `parser.py` defines explicit modelling types such as `Annotation`, `Block`, `FieldDef`, `EntityDef`, `RelationshipDef`, `PaginationDef`, `DtoDef`, `ServiceDef`, and `ADLConfig` (`src/agentic_brain/adl/parser.py:471-575`).
   - This is a solid MOF-style starting point because the abstract syntax is explicit and typed.

2. **Platform-specific config generation exists**
   - `generate_from_adl()` materialises `.env`, `docker-compose.yml`, `adl_api.py`, and `adl_config.py` from ADL (`src/agentic_brain/adl/generator.py:562-641`).
   - That is a valid PIM-to-PSM pattern for runtime configuration.

3. **Good class design examples exist outside ADL**
   - `BusinessEntity` and `Repository` use abstraction and dependency inversion well (`src/agentic_brain/business/base.py:28-220`).
   - `HealthIndicator` is a clean abstract interface (`src/agentic_brain/health/__init__.py:96-130`).

4. **State logic exists in code**
   - Order transitions are explicitly modelled (`src/agentic_brain/business/retail.py:288-332`).
   - Workflow transitions are explicitly modelled (`src/agentic_brain/orchestration/workflow.py:37-105`).

## Violations found

### 1. Dual, incompatible ADL metamodels

**Severity:** Critical

`parser.py` models ADL entities as typed dataclasses (`FieldDef`, `EntityDef`, `RelationshipDef`) (`src/agentic_brain/adl/parser.py:490-575`), but `entity_parser.py` parses entities into dictionaries inside a different `EntityDefinition` shape (`src/agentic_brain/adl/entity_parser.py:47-83,137-179,227-343`).

`entity_generator.py` expects dataclass-like field/relationship objects with attributes such as `field.field_type`, `field.max_length`, `rel.name`, and `rel.target_entity` (`src/agentic_brain/adl/entity_generator.py:170-220`), but `entity_parser.py` returns dictionaries instead (`src/agentic_brain/adl/entity_parser.py:265-341`).

**OMG impact:** This breaks MOF-style conformance because there is no single canonical metamodel for the language.

### 2. Advertised 7-layer entity generation is not integrated end-to-end

**Severity:** Critical

The docs claim 7 generated layers per entity (`docs/ADL_ENTITIES.md:94-107`), and `EntityGenerator` declares those layers (`src/agentic_brain/adl/entity_generator.py:48-55`), but the main ADL pipeline only generates configuration artefacts (`src/agentic_brain/adl/generator.py:562-641`).

The CLI exposes `agentic adl init|validate|generate|import`, but no real entity lifecycle commands are wired into the production CLI (`src/agentic_brain/cli/__init__.py:492-598`). The entity CLI tests use a mock Typer app and explicitly note missing real implementation (`tests/adl/test_adl_cli.py:13-15,30-72,119`).

**Observed verification:** a direct parser→entity-generator run failed with:

```text
AttributeError: 'dict' object has no attribute 'name'
```

**OMG impact:** MDA transformation rules are incomplete and not executable across the advertised model chain.

### 3. No formal OCL layer

**Severity:** High

Constraints are implemented as imperative Python validation, for example:

- `validate_config()` in `parser.py` (`src/agentic_brain/adl/parser.py:197-259`)
- entity `__post_init__()` checks in business classes (`src/agentic_brain/business/retail.py:65-99,153-166,191-197,231-243`)

These are useful, but there are no formal invariants, preconditions, or postconditions expressed in an OCL-like form in code or docs.

**OMG impact:** Business rules are not model-level constraints; they are implementation rules only.

### 4. UML coverage was incomplete for OMG review scope

**Severity:** Medium

The repository already had general architecture and sequence diagrams, but no ADL-focused class diagram and no state diagram for reviewed stateful components were present. Existing docs mostly use general Mermaid flow charts (`docs/architecture.md`, `docs/diagrams/component-diagram.md`).

**Resolution in this review:** added `docs/diagrams/OMG_ADL_MODELING.md` with class, sequence, state, and component views.

### 5. PIM/PSM separation is implicit, not explicit

**Severity:** High

ADL is described as generator-friendly (`docs/ADL.md:9-12`), but the project does not explicitly document:

- what constitutes the **PIM**
- what constitutes the **PSM**
- which transformation rules map one to the other
- how traceability is preserved

`generate_from_adl()` performs the transformation, but the transformation contract is not documented as an MDA mapping (`src/agentic_brain/adl/generator.py:596-641`).

### 6. JDL-inspired documentation is ahead of implementation

**Severity:** Medium

`docs/ADL.md` and `docs/ADL_ENTITIES.md` present ADL as a JDL-like modelling language with entities, relationships, directives, and generation (`docs/ADL.md:88-98,223-245`; `docs/ADL_ENTITIES.md:94-138`), but the executable toolchain does not yet give a fully consistent JDL-style model compiler for entities.

**OMG impact:** The language story is stronger in documentation than in the actual model tooling.

## Recommended fixes

### Priority 1 — unify the metamodel

Adopt **one** canonical ADL metamodel.

Recommended direction:

- keep `parser.py` as the canonical MOF-like abstract syntax
- either remove `entity_parser.py` or refactor it to emit `FieldDef`, `EntityDef`, and `RelationshipDef`
- refactor `entity_generator.py` to consume the canonical model only

### Priority 2 — make MDA transformations explicit

Document and implement the chain:

1. **PIM:** ADL source + canonical `ADLConfig`
2. **PSM-Config:** `.env`, `adl_config.py`, `docker-compose.yml`, `adl_api.py`
3. **PSM-Entity:** model, DAO, service, business, API, React, CLI artefacts

Add a traceability table per target artefact, e.g.:

| PIM element | PSM target | Rule |
| --- | --- | --- |
| `entity Foo` | `foo_model.py` | one entity → one persistence model |
| `field name String required` | model field + API schema | required scalar mapping |
| `relationship OneToMany` | DAO/service/API relation code | relation projection |

### Priority 3 — add formal OCL-style constraints

At minimum, document constraints like:

```ocl
context ADLConfig
inv AtLeastOneLLM: self.llms->size() >= 1

context EntityDef
inv UniqueFieldNames: self.fields.name->isUnique(n | n)

context RelationshipDef
inv ValidEndpoints:
  self.from_end.entity <> '' and self.to_end.entity <> ''

context EntityGenerator::generate(entity : EntityDef)
pre CanonicalEntity: entity.fields->forAll(f | f.type <> '')
post SevenLayersOrExplainedFailure:
  result->size() = 7 or result->exists(r | r.layer = 'error')
```

Then align those documented constraints with executable validators.

### Priority 4 — align CLI and tests with real implementation

- Replace `tests/adl/test_adl_cli.py` mock app with tests against the production CLI.
- Add an integration test for parser → generator → emitted files.
- Fail CI if the 7-layer generation pipeline drifts from the documented contract.

### Priority 5 — keep UML artefacts source-aligned

Maintain the new diagrams in `docs/diagrams/OMG_ADL_MODELING.md` as part of ADL changes.  
Any metamodel change should update:

- class diagram
- sequence diagram
- state diagram for affected stateful components
- component diagram

## UML diagrams added by this review

Created:

- `docs/diagrams/OMG_ADL_MODELING.md`

Contents:

- ADL metamodel class diagram
- ADL generation sequence diagram
- Order lifecycle state diagram
- ADL component diagram

## Compliance verdict

**Verdict:** `agentic-brain` has a promising OMG-aligned foundation, but it is **not yet fully OMG-compliant** in the ADL/entity-generation area.

The largest gaps are:

1. **single-source metamodel conformance**
2. **formal constraints**
3. **traceable PIM→PSM transformations**
4. **implementation parity with documented 7-layer generation**

## Validation performed

- `python3 -m pytest tests/test_adl.py tests/adl/test_adl_parser.py -q` ✅
- manual parser→entity generator verification ❌ (`AttributeError: 'dict' object has no attribute 'name'`)

# Step 1 — Analyze & Design

Runs before any Python code is written. For each Java module it produces a
trustworthy architecture blueprint that Steps 2 and 3 build on.

---

## Agents

### 1-A: `UnderstandAgent`

Reads the raw Java source and asks Claude to extract a structured JSON analysis.

**Output (`AnalysisResult`):**

| Field | Description |
|---|---|
| `business_logic` | Plain-English description of each method |
| `data_structures` | All classes, interfaces, enums, and records with their fields |
| `external_api_calls` | External calls (e.g. `jdbcTemplate.query(...)`, `restTemplate.getForObject(...)`) |
| `control_flow` | `methods` list (signatures), `loops`, and `exception_handlers` |
| `complexity_score` | 0.0 (trivial POJO/DTO) → 1.0 (deep concurrency, reflection, many checked exceptions) |
| `raw_summary` | 2–3 sentence human summary |

**Validator A: `ASTChecker`** (runs immediately after)

Uses regex to independently scan the Java source for all class, interface, and method
definitions and compares them against what the LLM captured. Flags any method or type
that was silently dropped.

Method name comparison: the LLM returns full Java signatures such as
`"public BigDecimal calcSubtotal(Invoice invoice)"`. The checker extracts the last
whitespace-delimited token before `(` as the bare method name before comparing, so
modifiers and return types in the signature do not cause false mismatches.

Also warns about Java idioms that need special migration attention:

| Warning trigger | Concern |
|---|---|
| `return null` | Verify `Optional[T]` handling in architecture |
| `instanceof` | Verify type-dispatch is modelled correctly |
| `synchronized` | Verify thread-safety model maps to asyncio |
| Raw collection types (`ArrayList`, `HashMap`, …) | Ensure generic equivalents are typed in Python |

---

### 1-B: `DocumentAgent`

Takes the `AnalysisResult` JSON and turns it into a human-readable Markdown spec
saved to disk as `<ModuleName>_spec.md`.

**The Markdown spec always contains:**
1. Overview paragraph
2. Inputs & Outputs table
3. Business Rules — numbered invariants the Python code must honour
4. Data Structures tables
5. Error Conditions
6. Migration Notes — Java idioms needing special attention

---

### 1-C: `ArchitectAgent`

Takes both the analysis JSON and the Markdown spec, then designs the Python
architecture blueprint saved as `<ModuleName>_architecture.json`.

**Output (`ArchitectureDesign`):**

| Field | Description |
|---|---|
| `dataclasses` | Python dataclass definitions replacing Java classes/records |
| `type_hints` | PEP 484 type annotations for all identifiers |
| `module_boundaries` | Top-level Python module names to create |
| `dependency_injection` | Interfaces/protocols for external deps (e.g. JDBC → injected repository) |
| `public_api` | Function signatures + docstrings for every public function |
| `design_notes` | Paragraph on key architectural decisions |

Note: in the architecture JSON, `"default": null` on a dataclass field means *required —
no default value*. It does not represent a Python `None` default.

**Validator B: `ArchAuditor`** (runs immediately after)

An LLM audit of the design against these criteria:
1. No global mutable state (module-level mutable variables, class-level mutable defaults)
2. All public APIs have complete type annotations
3. No Java-isms carried over (null return types in signatures, checked-exception signatures,
   Hungarian notation, get/set prefix methods, raw collections, instanceof chains)
4. External dependencies replaced by injected abstractions (protocols/ABCs)
5. Proper Python OOP (dataclasses/Pydantic, not ad-hoc dicts)
6. Module boundaries are sensible (no god-modules)

---

## Human Gate

Always triggered at the end of Step 1 regardless of audit outcome. The panel shows:
- Complexity score
- Any AST issues (methods/classes/interfaces found in source but not captured)
- Architecture audit status (PASS/FAIL) with individual issues listed

The pipeline pauses and prompts the user to approve or reject the design before
Step 2 begins.

---

## Flow

```
Java source file
     │
     ▼
[UnderstandAgent] ──→ AnalysisResult
     │
     ▼
[ASTChecker] ── warns if methods/classes/interfaces were missed
     │
     ▼
[DocumentAgent] ──→ <ModuleName>_spec.md
     │
     ▼
[ArchitectAgent] ──→ <ModuleName>_architecture.json
     │
     ▼
[ArchAuditor] ── flags Java-isms, missing types, bad structure
     │
     ▼
[Human Gate] ── always pauses for approval before Step 2
     │
     ▼
  → Step 2 (generate_tests)
```

---

## Files

| File | Role |
|---|---|
| `understand_agent.py` | 1-A — extracts structured analysis from Java source |
| `document_agent.py` | 1-B — writes Markdown functional spec |
| `architect_agent.py` | 1-C — designs Python architecture blueprint |
| `ast_checker.py` | Validator A — regex cross-check of captured methods and types |
| `arch_auditor.py` | Validator B — LLM audit of the architecture design |

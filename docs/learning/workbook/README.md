# AEGIS Hands-On Workbook (Phase 0 to Phase 5)

You already have the **handbook** (`../aegis-handbook-phase-0-to-5.md`). It explains
*what* each phase is. This workbook makes you **learn the code by working on it
yourself**: reading with a purpose, predicting, running, breaking, fixing and
building small pieces.

Rule of the workbook: **you do the tasks, not an AI.** Every task tells you where to
look and how to check yourself. There is an answer key (`07-answer-key.md`) but you
open it only *after* you wrote your own answer.

---

## Files in this workbook

| File | Covers | Tasks |
| --- | --- | --- |
| `README.md` (this file) | how to work, lab setup, tracker, schedule, cheat sheet | - |
| `01-phase-0-1-foundation-and-core.md` | app skeleton, settings, layers, incident domain, API, auth, DB | P0-1 .. P1-11 |
| `02-phase-2-simulator.md` | fake production, scenarios, signals, webhook, dedupe | P2-1 .. P2-10 |
| `03-phase-3-rag.md` | allowlist, chunking, embeddings, hybrid search, eval | P3-1 .. P3-10 |
| `04-phase-4-investigation.md` | worker, LangGraph, commander, specialists, RCA | P4-1 .. P4-13 |
| `05-phase-5-guardrail.md` | the gateway, policy, audit, limits, kill switch, MCP | P5-1 .. P5-14 |
| `06-capstones-and-exam.md` | cross-phase projects, failure drills, final exam | C-1 .. C-6, exam |
| `07-answer-key.md` | verified answers (open last) | K-xx |
| `08-change-the-code-tasks.md` | **11 real code changes** you make yourself, test first (bug fixes, hardening, refactor, features) | CH-1 .. CH-11 |
| `../aegis-code-walkthrough.md` | annotated tour of the real code, 13 sections, with a 20-point design-review list | read alongside |

**Where the code-change tasks fit.** Everything in files 01 to 06 teaches you to read,
run and break the code. File 08 is where you **change it for real**. Read the matching
section of the walkthrough, then do the CH task. Good moments: CH-1 to CH-4 after
Phase 2, CH-7 after Phase 3, CH-6 after Phase 4, CH-2, CH-5, CH-8 to CH-11 after Phase 5.

---

## 1. How to learn from this (the loop)

For every task use the same six steps. Write each step in your notebook.

1. **Read.** Open the files the task names. Read slowly. Do not run anything yet.
2. **Predict.** Write down what you think will happen (a value, a status code, a
   test name). A wrong prediction is the most valuable result you can get.
3. **Run.** Run the command. Compare with your prediction.
4. **Break.** Change one thing on purpose (a constant, a condition, a rule). Predict
   which tests fail. Run them.
5. **Fix / restore.** Undo the change with git (see lab safety below).
6. **Explain.** In 3 sentences, out loud or in writing, as if to a new teammate:
   *what does this code do, why is it built this way, what would go wrong without it?*

If you cannot do step 6, you have not learned it yet. Re-read.

### Task tags

| Tag | Meaning | Needs Docker? |
| --- | --- | --- |
| `[READ]` | read code and answer questions | no |
| `[RUN]` | run something and observe | mostly no (marked when yes) |
| `[BREAK]` | change code to see what fails, then undo | no |
| `[MODIFY]` | make a small real change with tests | no |
| `[BUILD]` | build a new piece (usually test first) | no |
| `[THINK]` | design or trade-off question, no code | no |

Each task that needs Docker says **(Docker)** in its title. Everything else works on a
laptop with only `uv`.

---

## 2. Lab safety (read this once)

Your working tree may contain files that are not committed yet (for example the
handbook, `scripts/learning/`, `docs/releases/v0.6.md`). Experiments use
`git restore`, which **throws away uncommitted edits to the file you name**. So:

```bash
cd /home/ali/Videos/aegis-ai-engineering-platform

# 1. See what is uncommitted. Save anything you care about first.
git status --short

# 2. Do all experiments on a branch (uncommitted files come along safely).
git switch -c learn/workbook

# 3. Optional but wise: commit YOUR OWN work first, so a restore can never eat it.
#    (Only you decide when to commit. Nothing in this workbook commits for you.)
```

Rules of thumb:

- **Mutate / break only files you did not edit yourself that day.** Then
  `git restore <that file>` is always safe.
- Check what you changed before restoring: `git diff <file>`.
- Put your own tests in a scratch folder so they never mix with project tests:

```bash
mkdir -p tests/learning && touch tests/learning/__init__.py
# your tests: tests/learning/test_my_<topic>.py
uv run pytest tests/learning -q
```

- Use a throwaway database only. Never run destructive SQL against anything you care
  about. The local Docker Postgres from `scripts/docker-up.sh` is disposable.
- Every Python command in this workbook assumes `AEGIS_SKIP_DOTENV=1`
  (do not read `.env`). Put it in your shell once:

```bash
export AEGIS_SKIP_DOTENV=1
```

---

## 3. Setup check (10 minutes, no Docker)

```bash
uv sync --group dev
uv run pytest tests/unit -q          # expect: 383 passed, 1 skipped
uv run pytest tests/unit tests/security/test_prompt_injection_tools.py \
              tests/security/test_tool_abuse.py -q   # expect: 438 passed, 1 skipped
uv run python scripts/learning/guardrail_demo.py   # prints decisions and audit rows
uv run python scripts/learning/graph_demo.py latency_spike --no-mermaid
```

If these pass, you can do every task that is not marked **(Docker)**.

For **(Docker)** tasks follow handbook section 3 (`bash scripts/docker-up.sh`,
`uv run alembic upgrade head`, `uv run aegis-ingest`, then the API, simulator, worker
and MCP in separate terminals).

---

## 4. Cheat sheet

```bash
# one test, one file, by keyword
uv run pytest tests/unit/domain/incidents/test_transitions.py -q
uv run pytest tests/unit -q -k "kill_switch"
uv run pytest -x -q                      # stop at first failure
uv run pytest --lf -q                    # only what failed last time
uv run pytest -s -q path::test_name      # show print() output

# stop inside a test or function and look around
#   put   breakpoint()   in the code, then run pytest with -s

# a Python prompt with the project importable
uv run python -i -c "from aegis.domain.incidents import Incident"

# search the code (ripgrep)
rg -n "def next_action" src
rg -n "denied:" src | head -50           # every deny reason in the code
rg -l "list_deploys" --glob '!docs/**' . # every file that mentions a tool

# quality gates
uv run ruff check src tests
uv run mypy src                          # has some old findings; compare before/after

# undo
git diff                  # what did I change?
git restore path/to/file  # throw away my edit to one file
git status --short
```

Import tip: if a demo or your script imports `aegis.application.gateway...` first and
hits a circular import, import
`from aegis.application.investigation.collect import SpecialistPorts` **first**
(that is why the demo scripts start with it).

---

## 5. Progress tracker

Tick as you finish. `[ ]` means not done.

**Phase 0 and 1**
- [ ] P0-1 health route  - [ ] P0-2 composition root  - [ ] P0-3 settings fail fast
- [ ] P0-4 layer rule  - [ ] P0-5 quality gates  - [ ] P0-6 read the ADRs  - [ ] P0-7 build `/version`
- [ ] P1-1 state machine  - [ ] P1-2 entity REPL  - [ ] P1-3 break transitions
- [ ] P1-4 entity invariants  - [ ] P1-5 one field through layers  - [ ] P1-6 role matrix (Docker)
- [ ] P1-7 JWT by hand  - [ ] P1-8 error envelope  - [ ] P1-9 events and the dual write
- [ ] P1-10 Alembic tour (Docker)  - [ ] P1-11 build incident stats

**Phase 2**
- [ ] P2-1 scenario map  - [ ] P2-2 run the simulator  - [ ] P2-3 simulator in Python
- [ ] P2-4 memory-leak ramp  - [ ] P2-5 fingerprint  - [ ] P2-6 where dedupe happens
- [ ] P2-7 HMAC by hand  - [ ] P2-8 independence check  - [ ] P2-9 end to end emit (Docker)
- [ ] P2-10 build `disk_full` (simulator side)

**Phase 3**
- [ ] P3-1 allowlist  - [ ] P3-2 chunk one runbook  - [ ] P3-3 corpus numbers
- [ ] P3-4 fake embedder  - [ ] P3-5 RRF by hand  - [ ] P3-6 retrieve with a fake store
- [ ] P3-7 inspect the index (Docker)  - [ ] P3-8 RAG eval  - [ ] P3-9 build a new runbook
- [ ] P3-10 poisoning (think)

**Phase 4**
- [ ] P4-1 commander table  - [ ] P4-2 six scenarios  - [ ] P4-3 move the constants
- [ ] P4-4 reducers  - [ ] P4-5 interrupt and resume  - [ ] P4-6 specialists trace
- [ ] P4-7 policy meets commander  - [ ] P4-8 RCA outcomes  - [ ] P4-9 consumer tests
- [ ] P4-10 queue semantics (Docker)  - [ ] P4-11 the Postgres trail (Docker)
- [ ] P4-12 RCA review API (Docker)  - [ ] P4-13 build a commander rule

**Phase 5**
- [ ] P5-1 decision order  - [ ] P5-2 policy puzzles  - [ ] P5-3 grants matrix
- [ ] P5-4 mutation lab  - [ ] P5-5 beat the regex  - [ ] P5-6 circuit breaker
- [ ] P5-7 URL validator  - [ ] P5-8 build a chain verifier  - [ ] P5-9 immutable audit (Docker)
- [ ] P5-10 kill switch  - [ ] P5-11 policy version  - [ ] P5-12 MCP tour
- [ ] P5-13 threat map  - [ ] P5-14 build a fifth tool

**Change the code (file 08)**
- [ ] CH-1 cap duplicate notes  - [ ] CH-2 IPv6 loopback  - [ ] CH-3 reopen resolved
- [ ] CH-4 severity into the spec  - [ ] CH-5 Unicode vs neutralizer  - [ ] CH-6 resume guard
- [ ] CH-7 per-source cap in RRF  - [ ] CH-8 partial kill switch  - [ ] CH-9 verify and re-chain audit
- [ ] CH-10 audit read API (Docker for last step)  - [ ] CH-11 fifth tool end to end

**Capstones and exam**
- [ ] C-1 trace an incident  - [ ] C-2 new scenario across all phases
- [ ] C-3 in-memory end-to-end test  - [ ] C-4 failure drills (Docker)
- [ ] C-5 draw the platform from memory  - [ ] C-6 teach it  - [ ] Final exam

---

## 6. Suggested schedule (14 days, about 1.5 to 2.5 hours a day)

| Day | Do | Goal at the end of the day |
| --- | --- | --- |
| 1 | Setup check, P0-1 .. P0-5 | you can explain how the app starts and why layers exist |
| 2 | P0-6, P0-7, P1-1 .. P1-3 | you know the state machine by heart |
| 3 | P1-4, P1-5, P1-7, P1-8 | you can follow one field through all layers |
| 4 | P1-6, P1-9, P1-10 (Docker), P1-11 | you built a vertical slice |
| 5 | P2-1 .. P2-6 | you understand the simulator and dedupe |
| 6 | P2-7 .. P2-10 | you understand webhook trust and added a scenario |
| 7 | P3-1 .. P3-5 | you understand chunking, embeddings, RRF |
| 8 | P3-6 .. P3-10 | you understand retrieval end to end |
| 9 | P4-1 .. P4-5 | you understand the commander and LangGraph |
| 10 | P4-6 .. P4-9 | you understand specialists, RCA, idempotency |
| 11 | P4-10 .. P4-13 | you understand the worker and built a commander rule |
| 12 | P5-1 .. P5-4 | you can predict every guardrail decision |
| 13 | P5-5 .. P5-11 | you understand each hardening layer |
| 14 | P5-12 .. P5-14, C-1 .. C-6, exam | you can teach the whole platform |

**Extending to 21 days with code changes** (recommended if you want to learn the code,
not just the ideas): after day 14 add: day 15 walkthrough sections 1 to 5 + CH-1, CH-3;
day 16 CH-2, CH-4; day 17 walkthrough 6 to 8 + CH-6, CH-7; day 18 walkthrough 9 to 11 +
CH-5, CH-8; day 19 walkthrough 12 to 13 + CH-9; day 20 CH-10 (Docker); day 21 CH-11 and
the self-review at the end of file 08.

If you only have a weekend: do P0-3, P1-1, P1-2, P2-5, P3-5, P4-1, P4-2, P4-7, P5-1,
P5-2, P5-4, then C-1.

---

## 7. Keep a learning log

Create `~/aegis-notes.md` (outside the repo, or in `tests/learning/` if you like).
After each task write:

```text
P4-7  (date)
Predicted: ...
Happened: ...
Surprise: ...
One-line explanation: ...
```

Review the "Surprise" lines before the exam. They are your real gaps.

---

## 8. What each phase is *for* (one line each, so you never lose the thread)

| Phase | One line | You will be able to say |
| --- | --- | --- |
| 0 | a runnable, testable skeleton | "Everything hangs off `create_app` and `Settings`." |
| 1 | the system of record for incidents | "Incidents are an aggregate with a strict state machine behind JWT roles." |
| 2 | a fake production that fails on demand | "No input, no investigation. The simulator is a separate product, signed webhooks, dedupe by fingerprint." |
| 3 | grounded knowledge | "Chunk, embed, hybrid search, cite. Only allowlisted text, treated as data." |
| 4 | automatic investigation | "An event wakes a worker; a deterministic commander routes specialists; an LLM only writes the RCA; a human accepts it." |
| 5 | one deterministic gate for every tool call | "The model proposes, the gateway decides, everything is audited, and untrusted text never becomes an action." |

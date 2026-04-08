Extract learnings from this session and propose additions to compound-rules.md.

## Process

### Step 1: Review Session
Scan the conversation for:
- **Bugs fixed** - What caused them? How to prevent next time?
- **Failed approaches** - What didn't work? Why?
- **Successful patterns** - What worked well? Why?
- **New insights** - What did we learn that's generalizable?

### Step 2: Filter Candidates
For each potential learning, assess:
- **Generalizable?** - Will this apply to future tasks? (not one-off)
- **Non-obvious?** - Is this already in CLAUDE.md or compound-rules.md?
- **Actionable?** - Is it specific enough to apply? (not vague advice)

Only proceed with learnings that pass all three filters.

### Step 3: Draft Rules
For each qualified learning, use this format:

```markdown
#### {CATEGORY}-{NUMBER}: {Short description}
**Added:** {today's date YYYY-MM-DD}
**Context:** {What problem/task prompted this}
**Rule:** {The actionable guidance - specific and clear}
**Evidence:** {File path, conversation reference, or "this session"}
**Applies when:** {Trigger condition - when should Claude apply this?}
```

**Category codes:**
- FO = File Operations
- TR = Translation
- CW = Content/Writing
- GC = Git/Commit
- PY = Python/Scripts
- SI = Search/Index
- CM = Communication
- (Propose new category if needed)

### Step 4: Output

Provide in this format:

---

## Session Summary
- **Task accomplished:** {1-2 sentence description}
- **Key challenge:** {What was hard}
- **Resolution:** {How solved}

## Proposed Compound Rules

{List each rule in template format, numbered}

## Existing Rules to Update

{If any existing rules need refinement based on this session}

## Recommended Actions
- [ ] Add rule(s) to `.claude/docs/compound-rules.md`
- [ ] Update existing rule {ID} with {change}
- [ ] Update Quick Index table with new counts
- [ ] {Other actions if needed}

---

## When to Use This Command

Invoke `/compound` when:
- End of significant sessions (30+ minutes of work)
- After solving a novel problem
- When user says "what did we learn?" or "extract learnings"
- After debugging tricky issues
- When a pattern emerged that should be remembered

**Skip** when:
- Simple Q&A session
- Routine commits/translations with no new learnings
- Single-step tasks
- Nothing novel happened

$ARGUMENTS

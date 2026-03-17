---
name: create-plan
description: |
  Reasoning loop that reads a task or goal, breaks it into ordered steps, and writes
  a structured Plan.md file to AI_Employee_Vault/Plans/. Use this for any task with
  3 or more steps, multi-day work, or whenever a clear execution roadmap is needed
  before acting. Also use when the user says "make a plan for..." or "plan out...".
---

# Create Plan Skill

Break down a complex task into a structured, executable Plan.md file.

## Vault Location

The vault is at: `./AI_Employee_Vault`

## When to Use

- Any task with 3 or more distinct steps
- Multi-day or multi-session work
- Tasks touching external systems (email, LinkedIn, payments)
- When vault-triage encounters a complex item in /Needs_Action

## Planning Workflow

### Step 1: Read Context

```bash
# Read the task source
cat AI_Employee_Vault/Needs_Action/<task_file>.md

# Read the handbook for constraints
cat AI_Employee_Vault/Company_Handbook.md

# Check existing plans to avoid duplication
ls AI_Employee_Vault/Plans/
```

### Step 2: Reason Through the Task

Before writing, think through:

1. **Objective** — What is the desired outcome?
2. **Dependencies** — What must happen before what?
3. **Approval gates** — Which steps require human approval per handbook?
4. **Risks** — What could go wrong? What's irreversible?
5. **Success criteria** — How do we know it's done?

### Step 3: Write the Plan File

```bash
cat > AI_Employee_Vault/Plans/PLAN_<task_slug>_<timestamp>.md << 'EOF'
---
created: <ISO timestamp>
task_source: <source file name>
objective: <one-line goal>
priority: high|medium|low
estimated_steps: <N>
approval_required: true|false
status: in_progress
---

## Objective

<Clear statement of what needs to be accomplished and why>

## Context

<Relevant background — what triggered this task, any constraints>

## Steps

- [ ] **Step 1:** <Action> — *autonomous / requires approval*
- [ ] **Step 2:** <Action> — *autonomous / requires approval*
- [ ] **Step 3:** <Action> — *autonomous / requires approval*
...

## Approval Gates

List any steps that require human approval before proceeding:
- Step N: <reason approval is needed>

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| <risk> | <how to handle it> |

## Completion Criteria

<What "done" looks like — specific, measurable>

## Notes

<Any additional context, links, or references>
EOF
```

### Step 4: Execute Step by Step

Work through each step in order:

1. Mark step as in-progress: change `- [ ]` to `- [~]`
2. Perform the action (or create approval request if needed)
3. Mark step complete: change `- [~]` to `- [x]`
4. Log the action to `Logs/YYYY-MM-DD.jsonl`

### Step 5: Mark Plan Complete

When all steps are done, update the plan frontmatter:

```bash
# Update status in the plan file
sed -i 's/^status: in_progress/status: completed/' AI_Employee_Vault/Plans/PLAN_<task_slug>_<timestamp>.md

# Move to Done
mv "AI_Employee_Vault/Plans/PLAN_<task_slug>_<timestamp>.md" \
   "AI_Employee_Vault/Done/DONE_$(date +%Y%m%d_%H%M%S)_PLAN_<task_slug>.md"
```

### Step 6: Log and Update Dashboard

```bash
echo '{"timestamp":"<ISO>","action":"plan_completed","plan":"<task_slug>","steps_completed":<N>}' \
  >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).jsonl
```

Run `update-dashboard` skill.

## Rules

- Always write the plan **before** taking any action on multi-step tasks
- Mark approval gates explicitly — never skip them
- Keep steps atomic (one action per step)
- If a step fails, update the plan with the failure reason and stop
- Never delete a plan file — archive it to /Done when complete

# CLAUDE.md — working rules for this repo

Team MediBora, Terumo BCT Africa Hackathon 2026. Product working name: **Providus**.
Read `docs/BUILD_PLAN.md` and `docs/DESIGN.md` before writing any code. Follow the plan step by step.

## Hard rules (never break these)

1. **Git, depending on where you are running.**
   - *In Linet's own terminal (local session):* never run `git commit`, `git push`, `git merge`,
     `git rebase`, `git reset`, or change git config. You may run `git status`, `git diff`, `git add`.
     At the end of each step, stage the changes and print the exact `git commit -m "..."` and
     `git push` commands for Linet to run herself.
   - *In a cloud session (Linet has no terminal in your environment):* do not commit or push on your
     own. At each checkpoint show her the commit message and the list of files, and wait. Commit and
     push only after she replies "commit", to the working branch only, never by force, never to `main`
     unless she says so. One commit per step.
2. **Commit messages:** short, imperative, plain. No "Co-Authored-By", no "Generated with", no links,
   no mention of any AI tool. (AI tool use is declared in the README instead, as the hackathon rules require.)
3. **Never deploy, publish, or create cloud resources.** Deployment happens only in Step 11, and only
   after Linet says "deploy" in chat.
4. **Never read, print, store or ask for secrets.** No GitHub token, no Oracle password, no wallet contents
   in code, logs, commits or chat. Secrets live in `.env` and `wallet/`, both gitignored. If you need a
   value, tell Linet which variable to set.
5. **Never load `donors.csv`.** It is deliberately not in this repo. The product uses no donor or patient
   identities. A test enforces this. Do not download or recreate it.
6. **All code is written fresh in this repo.** Do not copy code from Linet's earlier projects or from
   outside sources beyond normal open-source library use. This is a hackathon rule.
7. **Stop and ask** when: a requirement is ambiguous, the data contradicts the plan, a step will take
   more than double its time budget, you want to add a dependency not listed in the plan, or you are
   about to delete or rewrite a file you did not create in this session.
8. **Every number shown in the UI comes from code that computed it from the data.** No hard-coded
   metrics, no placeholder results presented as real. If something is mocked, label it "Demo" in the UI
   and list it in the README under "What is mocked or not finished".
9. **The AI never acts.** It suggests. Orders, transfers and drives are requests that a signed-in person
   accepts, changes or rejects. Nothing auto-substitutes blood groups.

## How to work

- Work through one step of `docs/BUILD_PLAN.md` at a time. Inside a step, work without asking for
  permission on routine choices. Make the simplest choice that satisfies the step.
- At the end of each step, post a **checkpoint**:
  1. What now works (2 to 4 lines).
  2. Exact commands for Linet to run to see it working locally.
  3. Anything that is mocked, skipped, or different from the plan, and why.
  4. Changed files (`git status --short`) and the proposed commit message. Local session: the commit
     and push commands in one code block. Cloud session: wait for "commit".
  5. Wait for Linet to say "next" before starting the next step.
- If a step is running long, say so at the halfway mark and offer the cut line listed in the plan.
- Run the tests before every checkpoint. Do not hand over a step with failing tests.
- Keep `README.md` current as you go. It follows the organisers' template in `docs/README_TEMPLATE.md`.
- Plain language everywhere a user reads: UI copy, README, error messages. No jargon without a
  one-line explanation. British/Kenyan English spelling (haemoglobin, centre).
- Commands you give Linet must work on both Windows PowerShell and Linux bash, or give both.

## Stack (do not change without asking)

- Backend: Python 3.11+, FastAPI, pandas, numpy, scikit-learn, SQLite (stdlib `sqlite3`), pytest.
  Optional: `oracledb` for the cloud sync only.
- Frontend: React + Vite + TypeScript + Tailwind CSS, Framer Motion for small transitions,
  hand-built SVG for charts (Recharts allowed for the one forecast chart if faster).
  Fonts self-hosted via `@fontsource` so the app works offline.
- No LLM in the core path. Reasons are written by templates from computed numbers.

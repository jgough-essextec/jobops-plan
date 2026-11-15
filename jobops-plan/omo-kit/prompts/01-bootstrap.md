ulw

Bootstrap the JobOps repo in this directory.

1. Confirm the OmO commands available in this build: run `/help` and note in `plan/DOC-INBOX.md` whether `/goal`, `/ulw-plan`, `/ulw-execute` and `mass ulw` exist here.
2. `git init` if needed, create `main`, add a `.gitignore` (Python, Node, `profile/`, `.env*` except `*.sops.*`, `output/`).
3. Run `python plan/tools/build_state.py report` and read `AGENTS.md`, `plan/PLAN.md` and `plan/00-INDEX.md` fully.
4. Run the AGENTS.md build loop for **S00.1 only** (monorepo scaffold and CI), including its Red tests first.
5. Also add `plan/tools/build_state.py`'s tests (`plan/tools/tests/`) to `make test` so the build tool itself stays covered.
6. Stop after S00.1 is done. Print the report.

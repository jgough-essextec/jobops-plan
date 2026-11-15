# JobOps guardrails (always on)
- JobOps never sends email, never submits applications, never requests gmail.send. Do not write code that could.
- Only actor `doc` may set APPROVED or APPLIED. Do not add shortcuts.
- No real personal data (CV, inbox, Notion, Telegram) in repo, fixtures, logs or prompts. Synthetic only.
- Live network calls only inside spikes, after their checkpoint is cleared. CI uses fixtures and fakes.
- Never run `build_state.py clear` — that is Doc's command.

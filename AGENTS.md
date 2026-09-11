# Local Issue Tracker

## Commit and push — always update release notes

Whenever the user asks to **commit and push** (to GitHub):

1. Update **`release-notes.html`** in the project root **before** committing. Include that file in the same commit.
2. Prepend a changelog entry at the top of the **Latest** highlights (if the change is user-facing) and at the top of the **Changelog** day list.
3. Use today’s date, a kind badge (`Feature`, `UI`, `Fix`, `Docs`, `Chore`, `CI`), and a short plain-language summary of what landed — not only the git subject.
4. Keep newest entries first. Match the existing page style (dark theme, chips, day headings).
5. After the commit exists, refresh the embedded git log:

   ```powershell
   uv run python scripts/update-release-notes.py
   ```

   If that changes the file, amend the commit (`git add release-notes.html` then `git commit --amend --no-edit`) **only if it has not been pushed yet**. If it is already pushed, include the refresh in the same push by amending before `git push`.
6. Do not skip the notes for “small” UI work. Dist-only rebuilds can stay in the git log; they do not need a new highlight card.

The page is `release-notes.html`. Open it locally with the default browser when the user asks to view notes.

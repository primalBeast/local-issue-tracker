# Completing the GitHub push

The private repo was created at:
https://github.com/primalBeast/local-issue-tracker

Local commits are ready on `main`. HTTPS/SSH push from this environment
needs your credentials once:

```bash
cd /Users/bradleyarthur/Documents/dev/projectTracker

# Option A: GitHub CLI
gh auth login
git remote set-url origin https://github.com/primalBeast/local-issue-tracker.git
git push -u origin main

# Option B: SSH (after adding a key to GitHub)
git remote set-url origin git@github.com:primalBeast/local-issue-tracker.git
git push -u origin main
```

After the first successful push, clone-and-run works:

```bash
git clone https://github.com/primalBeast/local-issue-tracker.git
cd local-issue-tracker
uv sync
uv run lit serve --open
```

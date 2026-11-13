# Git Gym

A small terminal trainer for remembering Git commands **and when to use them**.
Twenty scenarios cover staging, Conventional Commits, branches, worktrees,
rebase, conflicts, leases, squash, stacked PRs, and reflog recovery.

Requires Python 3.9+ and Git 2.28+ for the lab. No Python dependencies or install
step are needed. From a terminal:

```sh
git clone https://github.com/Pablomm12/git-gym.git
cd git-gym
python3 -m git_gym practice --count 5
```

Already in the project directory? Run the last command. `python` works in
place of `python3` if that is how Python 3 is installed on your system.

```sh
python3 -m git_gym practice --count 3 --topic worktrees
python3 -m git_gym stats
python3 -m git_gym reference
python3 -m git_gym lab /tmp/git-gym-lab
```

Read [the guided lab missions](labs/README.md) after creating the lab. It uses a
local bare remote, linked worktrees, and a teammate clone. Creation refuses an
existing destination. It never needs to touch another work repository or send
anything to GitHub. Local Git identity is configured inside the lab.

During practice, type your command or explanation. `?` gives a hint, Enter
reveals the solution and records a miss, and `q` quits. Each solution explains
why it fits and how to verify it. Full commands come first. Listed reference
answers are recognized despite whitespace and quoting differences. Equivalent
commands or explanations can be marked correct with `y`; judge the reasoning
as well as the syntax. **Quiz answers are never executed**, including shell
operators and pasted commands.

Progress is saved after each graded answer to
`~/.local/share/git-gym/progress.json`. Set `GIT_GYM_DATA_DIR` to choose another
folder. Completed answers survive quitting; an unfinished question is not
recorded. Misses are due immediately and prioritized next session. Successful
recalls are scheduled in 1, 3, 7, 14, then 30 days. Due questions come first,
then unseen questions, then early review if you requested more. Questions do
not repeat within one session. Keep sessions short and return the next day.
A corrupt progress file produces an error and is preserved for recovery.
Use one practice process at a time; concurrent sessions can overwrite progress.

Commands in scenarios use illustrative branch names and placeholders such as
`OLD_SHA`; adapt them only after inspecting the repository. Rebase, amend,
and squash rewrite commit IDs. Use private practice branches, keep a backup
branch, and coordinate before rewriting shared history. Aliases are optional
and require your own configuration. The lab does not install any aliases.

Run the checks (standard library only):

```sh
python3 -m unittest discover -s tests -v
```

Tests use real disposable repositories in temporary directories, including
conflicts, restacking, and lease rejection. CI runs on Python 3.9 and 3.13.

For a first version this intentionally stays local: no AI, backend, or frontend.
A good next exercise on a real hosting service is a small documentation branch,
a Conventional Commit, and a PR. Practice dependent branches in the lab first;
you do not need stacked PR tooling to learn the underlying Git graph.

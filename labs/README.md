# Disposable local missions

Create a fresh lab from the Git Gym project directory:

```sh
python3 -m git_gym lab /tmp/git-gym-lab
cd /tmp/git-gym-lab
```

Use a new path each time. `origin.git` is a local bare remote; `main` and
`report-api` are linked worktrees; `teammate` is an independent clone.
These missions use only this lab. Run commands from the stated directory.
No GitHub account or network is involved. Replace `/tmp/git-gym-lab` if needed.

## 1. Inspect, stage, commit

In `report-api`, edit `reports.txt`: change `Filters: none` to `Filters: api`.

```sh
cd /tmp/git-gym-lab/report-api
git status
git diff
git add --patch reports.txt
git diff --staged
git commit -m "feat: add API filters"
git log -1 --stat
git worktree list
```

Why: review working files, select changes, review the index, then record intent.
Verify the commit contains only your intended edit and `git status` is clean.

## 2. Rebase, resolve, or abort

Simulate a teammate changing the same line:

```sh
cd /tmp/git-gym-lab/teammate
```

Edit `reports.txt` to say `Filters: shared`. Then:

```sh
git add reports.txt
git commit -m "feat: add shared filters"
git push origin main
cd /tmp/git-gym-lab/report-api
git fetch origin
git branch backup/api-before-rebase
git rebase origin/main
```

Expect a conflict. Read `git status` and the file. To try again later, run
`git rebase --abort`; verify your branch equals `backup/api-before-rebase`,
then run `git rebase origin/main` again.
Resolve the file to `Filters: shared, api`, removing every conflict marker.

```sh
git add reports.txt
git -c core.editor=true rebase --continue
git status
git log --graph --oneline --all
```

Verify the resolved content and that your feature commit follows origin/main.

## 3. Squash a private branch

In `report-api`, append `Sorting: enabled` to `reports.txt`, stage and commit
with `git commit -m "feat: add sorting"`. Append `Export: enabled`, stage and
commit with `git commit -m "feat: add export"`.

```sh
git branch backup/api-before-squash
git rebase --interactive HEAD~3
```

Keep the first `pick`; change the next two to `squash`. Save the todo file and
choose `feat: add report options` as the combined message. Verify:

```sh
git log --oneline origin/main..HEAD
git diff backup/api-before-squash HEAD
```

Expect one commit and no file differences. Squash changes history, not content.

## 4. Build and restack a dependent feature

```sh
cd /tmp/git-gym-lab/report-api
git worktree add -b feat/report-ui ../report-ui
cd ../report-ui
```

Create `ui.txt` with `Report controls`, then:

```sh
git add ui.txt
git commit -m "feat: add report controls"
git diff feat/report-api...feat/report-ui
```

This is a stack: a real UI PR would target `feat/report-api`. Simulate merging
the parent with squash (keep `feat/report-api` at its original tip):

```sh
cd ../main
git merge --ff-only origin/main
git merge --squash feat/report-api
git commit -m "feat: add report options"
git push origin main
cd ../report-ui
git fetch origin
git branch backup/ui-before-restack
git rebase --onto origin/main feat/report-api feat/report-ui
git log --oneline origin/main..HEAD
git diff origin/main...HEAD
```

Expect only the UI commit and `ui.txt` in the diff. A real UI PR now targets
main. Git branches and worktrees are local concepts; PR targets belong to the
hosting service. These missions simulate the graph without opening PRs.

## 5. Publish a rewrite with a lease

In `report-ui`:

```sh
git push -u origin feat/report-ui
git rev-parse origin/feat/report-ui
```

Copy that exact hash as `OLD_SHA`. Amend your private practice commit:

```sh
git commit --amend -m "feat: add accessible report controls"
git push --force-with-lease=refs/heads/feat/report-ui:OLD_SHA origin feat/report-ui
```

Replace `OLD_SHA` with the recorded hash. Verify with `git fetch origin` and
`git rev-parse HEAD origin/feat/report-ui`: both hashes should match.
A lease rejects an unexpected remote tip. Investigate a rejection; don't
replace it with `--force`.

## 6. Recover and clean up

```sh
git reflog
git show HEAD@{1}
git branch rescue HEAD@{1}
git show rescue
cd ../main
git worktree remove ../report-ui
git worktree list
```

Inspect before recovering: reflog entries depend on your actual operations.
Removal refuses dirty worktrees; keep or commit work you need. Branches remain.
When finished, the whole `/tmp/git-gym-lab` directory is disposable. Remove only
that verified lab path using your file manager. No command here needs your
other repositories.

import argparse
import contextlib
import datetime as dt
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from git_gym import cli


class PracticeTests(unittest.TestCase):
    def test_bank(self):
        bank = cli.scenarios()
        self.assertEqual(len(bank), 20)
        self.assertEqual(len({q['id'] for q in bank}), len(bank))
        for q in bank:
            for key in ('prompt', 'hint', 'why', 'verify'):
                self.assertTrue(q[key])
            self.assertTrue(q['answers'][0].startswith('git '))

    def test_schedule_and_reset(self):
        now = dt.datetime(2026, 1, 1, tzinfo=cli.UTC)
        progress = {}
        for days in (1, 3, 7, 14, 30, 30):
            cli.record(progress, 'a', True, now)
            self.assertEqual(progress['a']['due'], (now + dt.timedelta(days=days)).isoformat())
        cli.record(progress, 'a', False, now)
        self.assertEqual(progress['a']['level'], 0)
        self.assertEqual(progress['a']['attempts'], 7)
        self.assertEqual(progress['a']['correct'], 6)
        bank = [{'id': x, 'topic': 't'} for x in ('future', 'new', 'a')]
        progress['future'] = dict(progress['a'], due=(now + dt.timedelta(days=1)).isoformat())
        self.assertEqual([q['id'] for q in cli.select_questions(bank, progress, 3, now=now)], ['a', 'new', 'future'])
        self.assertEqual(cli.select_questions(bank, progress, 3, topic='other'), [])

    def test_progress_roundtrip_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'nested/progress.json'
            self.assertEqual(cli.load_progress(path), {})
            progress = {}
            cli.record(progress, 'a', False)
            cli.save_progress(path, progress)
            self.assertEqual(cli.load_progress(path), progress)
            for bad in ('{', '[]', '{"a": {}}'):
                path.write_text(bad)
                with self.assertRaises(ValueError):
                    cli.load_progress(path)
                self.assertEqual(path.read_text(), bad)

    def test_hints_equivalence_miss_and_quit(self):
        question = cli.scenarios()[0]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, GIT_GYM_DATA_DIR=tmp):
            with patch.object(cli, 'scenarios', return_value=[question]), patch('builtins.input', side_effect=['?', 'my equivalent explanation', 'y']), contextlib.redirect_stdout(io.StringIO()) as out:
                cli.practice(argparse.Namespace(count=1, topic=None))
            self.assertIn('Hint:', out.getvalue())
            self.assertIn('Verify:', out.getvalue())
            self.assertEqual(cli.load_progress(cli.data_path())[question['id']]['correct'], 1)
            with patch.object(cli, 'scenarios', return_value=[question]), patch('builtins.input', side_effect=['']), contextlib.redirect_stdout(io.StringIO()):
                cli.practice(argparse.Namespace(count=1, topic=None))
            saved = cli.load_progress(cli.data_path())
            self.assertEqual(saved[question['id']]['level'], 0)
            with patch.object(cli, 'scenarios', return_value=[question]), patch('builtins.input', side_effect=['q']), contextlib.redirect_stdout(io.StringIO()):
                cli.practice(argparse.Namespace(count=1, topic=None))
            self.assertEqual(cli.load_progress(cli.data_path()), saved)

    def test_answers_never_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'executed'
            env = dict(os.environ, GIT_GYM_DATA_DIR=tmp)
            result = subprocess.run(['python3', '-m', 'git_gym', 'practice', '--count', '1'], input='touch ' + str(marker) + '\nn\n', text=True, capture_output=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            self.assertIn('0/1', result.stdout)

    def test_normalization(self):
        self.assertTrue(cli.matches(' $ git commit -m \'feat: add report filters\' ', cli.scenarios()[5]))
        self.assertFalse(cli.matches('git status; touch x', cli.scenarios()[0]))


class LabTests(unittest.TestCase):
    def test_real_missions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / 'lab'
            with contextlib.redirect_stdout(io.StringIO()):
                cli.lab(argparse.Namespace(path=str(root)))
            with self.assertRaises(ValueError):
                cli.lab(argparse.Namespace(path=str(root)))
            env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
            env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1', GIT_EDITOR='true')
            def git(where, *args, ok=True):
                result = subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull, *args], cwd=root / where, env=env, text=True, capture_output=True)
                if ok:
                    self.assertEqual(result.returncode, 0, result.stderr)
                else:
                    self.assertNotEqual(result.returncode, 0)
                return result.stdout.strip()
            def commit(where, content, message):
                (root / where / 'reports.txt').write_text(content)
                git(where, 'add', 'reports.txt')
                git(where, 'commit', '-m', message)
            self.assertEqual(git('main', 'remote', 'get-url', 'origin'), str(root / 'origin.git'))
            original = git('report-api', 'rev-parse', 'HEAD')
            commit('report-api', 'Report table\nFilters: api\n', 'feat: add API filters')
            api_tip = git('report-api', 'rev-parse', 'HEAD')
            commit('teammate', 'Report table\nFilters: shared\n', 'feat: add shared filters')
            git('teammate', 'push', 'origin', 'main')
            git('report-api', 'fetch', 'origin')
            git('report-api', 'rebase', 'origin/main', ok=False)
            git('report-api', 'rebase', '--abort')
            self.assertEqual(git('report-api', 'rev-parse', 'HEAD'), api_tip)
            git('report-api', 'rebase', 'origin/main', ok=False)
            (root / 'report-api/reports.txt').write_text('Report table\nFilters: shared, api\n')
            git('report-api', 'add', 'reports.txt')
            git('report-api', 'rebase', '--continue')
            self.assertEqual(git('report-api', 'status', '--porcelain'), '')
            # Squash two extra commits together with the rebased feature.
            commit('report-api', 'Report table\nFilters: shared, api\nSorting: enabled\n', 'feat: add sorting')
            commit('report-api', 'Report table\nFilters: shared, api\nSorting: enabled\nExport: enabled\n', 'feat: add export')
            git('report-api', 'branch', 'backup/api')
            editor = Path(tmp) / 'squash.py'
            editor.write_text('import pathlib,sys\np=pathlib.Path(sys.argv[1])\ns=p.read_text().splitlines(True)\nn=0\nfor i,line in enumerate(s):\n if line.startswith("pick "):\n  n+=1\n  if n>1: s[i]="fixup "+line[5:]\np.write_text("".join(s))\n')
            env['GIT_SEQUENCE_EDITOR'] = 'python3 ' + str(editor)
            git('report-api', 'rebase', '-i', 'HEAD~3')
            self.assertEqual(git('report-api', 'diff', 'backup/api', 'HEAD'), '')
            self.assertEqual(git('report-api', 'rev-list', '--count', 'origin/main..HEAD'), '1')
            git('report-api', 'worktree', 'add', '-b', 'feat/report-ui', '../report-ui')
            (root / 'report-ui/ui.txt').write_text('Report controls\n')
            git('report-ui', 'add', 'ui.txt')
            git('report-ui', 'commit', '-m', 'feat: add report controls')
            git('main', 'merge', '--ff-only', 'origin/main')
            git('main', 'merge', '--squash', 'feat/report-api')
            git('main', 'commit', '-m', 'feat: add report options')
            git('main', 'push', 'origin', 'main')
            git('report-ui', 'fetch', 'origin')
            git('report-ui', 'rebase', '--onto', 'origin/main', 'feat/report-api', 'feat/report-ui')
            self.assertEqual(git('report-ui', 'diff', '--name-only', 'origin/main...HEAD'), 'ui.txt')
            self.assertEqual(git('report-ui', 'rev-list', '--count', 'origin/main..HEAD'), '1')
            git('report-ui', 'push', '-u', 'origin', 'feat/report-ui')
            old = git('report-ui', 'rev-parse', 'HEAD')
            git('report-ui', 'commit', '--amend', '-m', 'feat: improve report controls')
            lease = '--force-with-lease=refs/heads/feat/report-ui:'
            git('report-ui', 'push', lease + original, 'origin', 'feat/report-ui', ok=False)
            git('report-ui', 'push', lease + old, 'origin', 'feat/report-ui')
            git('report-ui', 'branch', 'rescue', old)
            self.assertEqual(git('report-ui', 'rev-parse', 'rescue'), old)
            self.assertIn(old[:7], git('report-ui', 'reflog'))
            git('main', 'worktree', 'remove', '../report-ui')
            self.assertNotIn(str(root / 'report-ui'), git('main', 'worktree', 'list'))


if __name__ == '__main__':
    unittest.main()

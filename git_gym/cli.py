"""Standard-library CLI. Quiz answers are compared as text and never executed."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import sys
import tempfile

UTC = dt.timezone.utc
INTERVALS = [0, 1, 3, 7, 14, 30]


def scenarios():
    return json.loads(Path(__file__).with_name('scenarios.json').read_text(encoding='utf-8'))


def data_path():
    explicit = os.environ.get('GIT_GYM_DATA_DIR')
    root = Path(explicit) if explicit else Path.home() / '.local/share/git-gym'
    return root / 'progress.json'


def load_progress(path):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('expected an object')
        for entry in value.values():
            if not isinstance(entry, dict):
                raise ValueError('invalid progress entry')
            for field in ('level', 'attempts', 'correct'):
                if type(entry.get(field)) is not int or entry[field] < 0:
                    raise ValueError('invalid progress counters')
            dt.datetime.fromisoformat(entry['due'])
        return value
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError(f'Cannot read {path}: {error}. File preserved; use a different GIT_GYM_DATA_DIR to start fresh.') from error


def save_progress(path, progress):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.progress-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(progress, handle, indent=2)
            handle.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def normalize(answer):
    text = answer.strip()
    if text.startswith('$ '):
        text = text[2:]
    try:
        return shlex.split(text)
    except ValueError:
        return [text]


def matches(answer, question):
    return any(normalize(answer) == normalize(candidate) for candidate in question['answers'])


def select_questions(bank, progress, count, topic=None, now=None):
    now = now or dt.datetime.now(UTC)
    pool = [q for q in bank if topic is None or q['topic'] == topic]
    random.shuffle(pool)
    def priority(question):
        entry = progress.get(question['id'])
        if entry is None:
            return (1, 0)
        due = dt.datetime.fromisoformat(entry['due'])
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        return (0 if due <= now else 2, due.timestamp())
    pool.sort(key=priority)
    return pool[:count]


def record(progress, question_id, correct, now=None):
    now = now or dt.datetime.now(UTC)
    entry = progress.setdefault(question_id, {'level': 0, 'attempts': 0, 'correct': 0})
    entry['attempts'] += 1
    entry['correct'] += int(correct)
    entry['level'] = min(entry['level'] + 1, len(INTERVALS) - 1) if correct else 0
    # Missed questions return next session; successes return in 1/3/7/14/30 days.
    entry['due'] = (now + dt.timedelta(days=INTERVALS[entry['level']])).isoformat()


def ask(prompt):
    value = input(prompt).strip()
    if value.lower() in ('q', ':q', 'quit'):
        raise EOFError
    return value


def practice(args):
    bank = scenarios()
    path = data_path()
    progress = load_progress(path)
    picked = select_questions(bank, progress, args.count, args.topic)
    print('\nGIT GYM  /  Learn the command. Understand the situation.')
    print('Type a command or explanation. Enter = reveal; ? = hint; q = quit.')
    print('Answers are text only. Equivalent answers can be self-assessed.\n')
    completed = correct_count = 0
    for index, question in enumerate(picked, 1):
        try:
            print(f'[{index}/{len(picked)}] {question["topic"].upper()} · {question["title"]}')
            print(question['prompt'])
            answer = ask('\nYour answer > ')
            while answer == '?':
                print('Hint:', question['hint'])
                answer = ask('Your answer > ')
            matched = question['kind'] == 'command' and matches(answer, question)
            if matched:
                print('\nMatches a reference answer.')
            print('\nReference:', question['answers'][0])
            if question.get('aliases'):
                print('Optional alias:', ', '.join(question['aliases']))
            print('Why:', question['why'])
            print('Verify:', question['verify'])
            if question.get('caution'):
                print('Watch for:', question['caution'])
            if not answer:
                correct = False
                print('Revealed without an answer — marked for practice again.')
            else:
                default = '[Y/n]' if matched else '[y/N]'
                while True:
                    grade = ask(f'Did you get the command AND reasoning right? {default} ').lower()
                    if grade in ('', 'y', 'yes', 'n', 'no'):
                        break
                    print('Enter y or n (or q to quit).')
                correct = grade in ('y', 'yes') or (grade == '' and matched)
            record(progress, question['id'], correct)
            save_progress(path, progress)
            completed += 1
            correct_count += int(correct)
            print('Recorded:', 'got it' if correct else 'practice again', '\n')
        except (EOFError, KeyboardInterrupt):
            print('\nSession stopped; completed answers are saved.')
            break
    print(f'Session: {correct_count}/{completed} self-assessed correct. Run `python3 -m git_gym stats` to see progress.')


def stats(_args):
    bank = scenarios()
    progress = load_progress(data_path())
    entries = [progress[q['id']] for q in bank if q['id'] in progress]
    attempts = sum(e['attempts'] for e in entries)
    correct = sum(e['correct'] for e in entries)
    print(f'Explored: {len(entries)}/{len(bank)} scenarios')
    print(f'Attempts: {attempts} · Self-assessed correct: {correct}')
    print('Level 3+ (repeated successful recalls):', sum(e['level'] >= 3 for e in entries))
    for topic in sorted({q['topic'] for q in bank}):
        ids = [q['id'] for q in bank if q['topic'] == topic]
        print(f'  {topic}: {sum(i in progress for i in ids)}/{len(ids)} explored')
    print('Progress:', data_path())


def reference(_args):
    for question in scenarios():
        print(f'\n{question["title"]} [{question["topic"]}]')
        print(' ', question['answers'][0])
        print('  Why:', question['why'])
        print('  Verify:', question['verify'])
        if question.get('caution'):
            print('  Watch for:', question['caution'])


def lab(args):
    root = Path(args.path).expanduser().resolve()
    if root.exists():
        raise ValueError(f'Lab destination already exists; choose a new directory: {root}')
    git = shutil.which('git')
    if not git:
        raise ValueError('Git is required to create the lab.')
    root.mkdir(parents=True)
    # Ignore inherited repository routing and user hooks/config inside the lab.
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
               GIT_TERMINAL_PROMPT='0')
    def g(*command, cwd=None):
        subprocess.run([git, '-c', 'core.hooksPath=' + os.devnull, *command], cwd=cwd, env=env, check=True, capture_output=True, text=True)
    try:
        g('init', '--bare', '--initial-branch=main', str(root / 'origin.git'))
        g('clone', str(root / 'origin.git'), str(root / 'main'))
        main = root / 'main'
        g('config', 'user.name', 'Git Gym Learner', cwd=main)
        g('config', 'user.email', 'learner@example.invalid', cwd=main)
        (main / 'README.md').write_text('# Git Gym lab\n\nA tiny reports project for practicing Git.\n')
        (main / 'reports.txt').write_text('Report table\nFilters: none\n')
        g('add', 'README.md', 'reports.txt', cwd=main)
        g('-c', 'commit.gpgsign=false', 'commit', '-m', 'chore: initialize practice project', cwd=main)
        g('push', '-u', 'origin', 'main', cwd=main)
        g('worktree', 'add', '-b', 'feat/report-api', str(root / 'report-api'), cwd=main)
        g('clone', str(root / 'origin.git'), str(root / 'teammate'))
        g('config', 'user.name', 'Git Gym Teammate', cwd=root / 'teammate')
        g('config', 'user.email', 'teammate@example.invalid', cwd=root / 'teammate')
    except subprocess.CalledProcessError as error:
        raise ValueError(f'Lab setup stopped: {error.stderr.strip()}. Partial lab kept at {root}.') from error
    print(f'\nLab created: {root}')
    print('origin.git = local bare remote; main + report-api = worktrees; teammate = second clone.')
    print('All remotes point to local folders; nothing was sent to GitHub.')
    print('Start here:', shlex.join(['cd', str(root / 'report-api')]))
    print('Then: git status; git worktree list; edit reports.txt and review git diff.')
    print('See labs/README.md in the project for missions, including a dependent branch.')


def positive_int(value):
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError('must be at least 1')
    return result


def main():
    parser = argparse.ArgumentParser(description='Scenario-based Git practice, no dependencies.')
    sub = parser.add_subparsers(dest='command')
    training = sub.add_parser('practice', help='Short recall session (default: 5 scenarios)')
    training.add_argument('--count', type=positive_int, default=5)
    training.add_argument('--topic', choices=sorted({q['topic'] for q in scenarios()}))
    training.set_defaults(func=practice)
    sub.add_parser('stats', help='Show local progress').set_defaults(func=stats)
    sub.add_parser('reference', help='Read all scenario solutions').set_defaults(func=reference)
    sandbox = sub.add_parser('lab', help='Create a disposable local Git practice repository')
    sandbox.add_argument('path', help='A new, unused directory')
    sandbox.set_defaults(func=lab)
    args = parser.parse_args()
    if args.command is None:
        args = parser.parse_args(['practice'])
    try:
        args.func(args)
    except (ValueError, OSError) as error:
        print(f'git-gym: {error}', file=sys.stderr)
        raise SystemExit(1)

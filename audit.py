#!/usr/bin/env python3
"""titan-ui audit - what has changed in everyone's apps since the last run?

    py -3 audit.py <all_apps folder> [--state <folder>] [--no-save]

Runs the rules of check.py over every Anvil app in
    <all_apps>/current_anvil_code/*    group "mine"
    <all_apps>/team_anvil_code/*       group "team" (the read-only mirror of the share)
compares the result with the snapshot the previous run saved, and reports only what
changed. It reads the apps and never changes them. It writes only in the state folder
(default <all_apps>/titan-ui-audit):
    baseline.json    the snapshot the next run compares against
    last_report.md   the report of the latest run
    reports/         one dated copy of every report that had something new
    log.md           one line per run
    accepted.txt     optional; one finding key per line that the owner has accepted

What a run can report
  DRIFT  a rule is broken: a new error from check.py; a new form or a new app that is not
         titan-ui; a titan-ui form that went back to Material Design 3; an app that
         marked itself exempt.
  WATCH  a person should look: the layout of a Material Design 3 form changed (if that was
         a rework the form should have moved to titan-ui); more hand-set colours in a
         Material Design 3 form or in shared modules; theme.css changed.
  GOOD   a form moved to titan-ui; an error was cleared; an app adopted the block.
DRIFT findings stay listed under STILL OPEN on every later run until they are fixed or
their key is added to accepted.txt.

The first line printed is a one-line summary, for whoever runs this on a schedule.
The team mirror only holds what each developer has published to the share: a change that
was never published cannot be seen here.
"""
import datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check  # noqa: E402

GROUPS = (('mine', 'current_anvil_code'), ('team', 'team_anvil_code'))
SKIP_DIRS = ('.git', '__pycache__', '.titan-ui')


def sha(*paths):
    h = hashlib.sha256()
    for p in paths:
        h.update(((check.read(p) if p else None) or '').encode('utf-8', 'replace'))
        h.update(b'\0')
    return h.hexdigest()[:10]


def newest_file(app):
    best = 0
    for d, dirs, files in os.walk(app):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            try:
                best = max(best, os.path.getmtime(os.path.join(d, f)))
            except OSError:
                pass
    return datetime.datetime.utcfromtimestamp(best).strftime('%Y-%m-%d') if best else None


def group_errors(errors):
    """check.py errors carry line numbers, which move; group them by rule + file."""
    count, text = {}, {}
    for e in errors:
        m = re.match(r'(R\d) (.+?):\d+ ', e)
        k = f'{m.group(1)} {m.group(2)}' if m else e.split(' ', 1)[0]
        count[k] = count.get(k, 0) + 1
        text.setdefault(k, e)
    return count, text


def snapshot(path, canon, with_newest):
    r = check.check_app(path, canon)
    if 'skipped' in r:
        return None
    s = {'state': 'm3', 'block': None, 'errors': {}, 'error_text': {}, 'forms': {},
         'theme_sha': None, 'theme_colours': 0, 'module_colours': 0}
    if with_newest:
        s['newest'] = newest_file(path)
    if 'exempt' in r:
        s['state'], s['exempt_reason'] = 'exempt', r['exempt']
        return s
    i = r['info']
    s['block'] = i.get('block_version')
    s['errors'], s['error_text'] = group_errors(r['errors'])
    s['theme_sha'] = i.get('stock_base_sha')
    s['theme_colours'] = i.get('custom_css_colours', 0)
    s['module_colours'] = i.get('module_colour_codes', 0)
    forms, _ = check.forms_of(path)
    conv = set(r['converted'])
    for k, f in forms.items():
        s['forms'][k] = {'look': 'tui' if k in conv else 'm3',
                         'layout': sha(f['yaml'], f['html']),
                         'colours': r['legacy'].get(k, 0)}
    if conv or s['block']:
        s['state'] = 'tui'
    return s


def scan(root):
    canon = check.canonical_block()
    apps, skipped, missing = {}, [], []
    for group, folder in GROUPS:
        base = os.path.join(root, folder)
        if not os.path.isdir(base):
            missing.append(folder)
            continue
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name)
            if not os.path.isdir(p):
                continue
            s = snapshot(p, canon, group == 'team')
            if s is None:
                skipped.append(f'{group}/{name}')
            else:
                apps[f'{group}/{name}'] = s
    return apps, skipped, missing


def m3_forms(s):
    return sorted(f for f, v in s['forms'].items() if v['look'] == 'm3')


def error_line(key, s, g):
    n = s['errors'][g]
    return f"{key}: {s['error_text'].get(g, g)}" + (f' (and {n - 1} more in the same file)' if n > 1 else '')


def compare(old, new):
    """Returns drift [(key, text)], watch [text], good [text], info [text]."""
    drift, watch, good, info = [], [], [], []
    for key, n in sorted(new.items()):
        o = old.get(key)
        if o is None:
            if n['state'] == 'exempt':
                drift.append((f'{key}|exempt', f"{key}: new app that marks itself exempt (\"{n.get('exempt_reason')}\"). "
                              'Exemptions come from the decision, not from the app.'))
                continue
            left = m3_forms(n)
            if left:
                drift.append((f'{key}|new-app', f"{key}: new app with {len(left)} of {len(n['forms'])} forms "
                              'not on titan-ui (new apps are built on titan-ui)'))
            else:
                good.append(f"{key}: new app, every form on titan-ui")
            for g in sorted(n['errors']):
                drift.append((f'{key}|err|{g}', error_line(key, n, g)))
            continue
        if n['state'] == 'exempt' and o['state'] != 'exempt':
            drift.append((f'{key}|exempt', f"{key}: now marks itself exempt (\"{n.get('exempt_reason')}\"). "
                          'Exemptions come from the decision, not from the app.'))
        if o['state'] == 'exempt' and n['state'] != 'exempt':
            info.append(f'{key}: no longer exempt; its forms are tracked from this run')
        if n['block'] and not o['block']:
            good.append(f"{key}: adopted the titan-ui block ({n['block']})")
        if o['block'] and not n['block'] and n['state'] != 'exempt':
            drift.append((f'{key}|block-removed', f"{key}: the titan-ui block ({o['block']}) was removed from theme.css"))
        for g in sorted(n['errors']):
            if n['errors'][g] > o['errors'].get(g, 0):
                drift.append((f'{key}|err|{g}', error_line(key, n, g)))
        for g in sorted(o['errors']):
            if g not in n['errors']:
                good.append(f'{key}: cleared - {g}')
        if 'exempt' in (o['state'], n['state']):
            continue
        gone = {f: v for f, v in o['forms'].items() if f not in n['forms']}
        gone_layouts = {v['layout']: f for f, v in gone.items()}
        renamed = set()
        for f in sorted(n['forms']):
            v, ov = n['forms'][f], o['forms'].get(f)
            if ov is None:
                was = gone_layouts.get(v['layout'])
                if was:
                    renamed.add(was)
                    info.append(f'{key}: form {was} renamed to {f}')
                elif v['look'] == 'm3':
                    drift.append((f'{key}|new-form|{f}', f'{key}: new form {f} is not on titan-ui (new forms are built on titan-ui)'))
                else:
                    good.append(f'{key}: new form {f}, built on titan-ui')
            elif ov['look'] == 'm3' and v['look'] == 'tui':
                good.append(f'{key}: form {f} moved to titan-ui')
            elif ov['look'] == 'tui' and v['look'] == 'm3':
                drift.append((f'{key}|reverted|{f}', f'{key}: form {f} went from titan-ui back to Material Design 3 (the move is one-way)'))
            elif v['look'] == 'm3':
                if v['layout'] != ov['layout']:
                    watch.append(f'{key}: layout of Material Design 3 form {f} changed. If this was a rework, the form should have moved to titan-ui.')
                if v['colours'] > ov['colours']:
                    watch.append(f"{key}: hand-set colours in Material Design 3 form {f} rose from {ov['colours']} to {v['colours']}")
        for f in sorted(gone):
            if f not in renamed:
                info.append(f'{key}: form {f} removed')
        if n['theme_sha'] != o['theme_sha'] and n['theme_sha'] and o['theme_sha']:
            extra = ''
            if not n['block'] and n['theme_colours'] != o['theme_colours']:
                extra = f" (colour codes in it: {o['theme_colours']} -> {n['theme_colours']})"
            watch.append(f'{key}: theme.css changed outside the titan-ui block{extra}')
        if n['module_colours'] > o['module_colours']:
            watch.append(f"{key}: colour codes in shared client modules rose from {o['module_colours']} to {n['module_colours']}")
    for key in sorted(old):
        if key not in new:
            info.append(f'{key}: no longer present')
    return drift, watch, good, info


def still_valid(key, new):
    """Is a finding carried over from an earlier run still true?"""
    parts = key.split('|')
    s = new.get(parts[0])
    if s is None:
        return False
    kind = parts[1]
    if kind == 'err':
        return parts[2] in s['errors']
    if kind == 'exempt':
        return s['state'] == 'exempt'
    if kind == 'new-app':
        return bool(m3_forms(s))
    if kind in ('new-form', 'reverted'):
        return s['forms'].get(parts[2], {}).get('look') == 'm3'
    if kind == 'block-removed':
        return not s['block'] and s['state'] != 'exempt'
    return False


def read_accepted(state):
    t = check.read(os.path.join(state, 'accepted.txt')) or ''
    return {line.split('#')[0].strip() for line in t.split('\n') if line.split('#')[0].strip()}


def table(new):
    rows = ['app | look | forms titan-ui / Material | errors | newest file']
    for key, s in sorted(new.items()):
        if s['state'] == 'exempt':
            why = s.get('exempt_reason') or ''
            why = why if len(why) <= 60 else why[:57] + '...'
            rows.append(f"{key} | exempt: {why} | - | - | {s.get('newest') or '-'}")
            continue
        look = f"titan-ui {s['block'] or '(no block)'}" if s['state'] == 'tui' else 'Material Design 3'
        tui = sum(1 for v in s['forms'].values() if v['look'] == 'tui')
        rows.append(f"{key} | {look} | {tui} / {len(s['forms']) - tui} | {sum(s['errors'].values())} | {s.get('newest') or '-'}")
    return rows


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    save = '--no-save' not in argv
    state = argv[argv.index('--state') + 1] if '--state' in argv else None
    if state in args:
        args.remove(state)
    if len(args) != 1:
        sys.exit(__doc__)
    root = args[0]
    state = state or os.path.join(root, 'titan-ui-audit')
    now = datetime.datetime.utcnow()
    stamp, today = now.strftime('%Y-%m-%d %H:%M UTC'), now.strftime('%Y-%m-%d')

    new, skipped, missing = scan(root)
    if not new:
        print(f'AUDIT {stamp} | FAILED: no Anvil apps found under {root} (missing: {", ".join(missing) or "none"})')
        return 1
    try:
        with open(os.path.join(state, 'baseline.json'), encoding='utf-8') as f:
            base = json.load(f)
    except (OSError, ValueError):
        base = None
    accepted = read_accepted(state)
    if missing and base:
        # a folder could not be read this run: carry its last known state forward
        # unchanged, so nothing in it is reported as removed or as fixed
        groups = tuple(g for g, folder in GROUPS if folder in missing)
        for k, v in base['apps'].items():
            if k.split('/')[0] in groups:
                new.setdefault(k, v)

    if base is None:
        drift, watch, good, info = [], [], [], []
        carried = {}
        current = [(f'{k}|err|{g}', error_line(k, s, g)) for k, s in sorted(new.items()) for g in sorted(s['errors'])]
    else:
        drift, watch, good, info = compare(base['apps'], new)
        carried = {k: v for k, v in base.get('open', {}).items() if still_valid(k, new)}
        current = []
    drift = [(k, t) for k, t in drift if k not in accepted]
    new_keys = {k for k, _ in drift}
    open_now = {}
    for k, t in current + drift:
        open_now[k] = {'text': t, 'first_seen': carried.get(k, {}).get('first_seen', today)}
    for k, v in carried.items():
        open_now.setdefault(k, v)
    open_now = {k: v for k, v in open_now.items() if k not in accepted}
    older = {k: v for k, v in open_now.items() if k not in new_keys}

    exempt = sum(1 for s in new.values() if s['state'] == 'exempt')
    head = (f'AUDIT {stamp} | NEW: {len(drift)} drift, {len(watch)} watch, {len(good)} good | '
            f'STILL OPEN: {len(older)} | apps: {len(new)} ({exempt} exempt) | previous run: '
            + (base['run'] if base else 'none - baseline created'))
    out = [head, '']
    if missing:
        out += ['NOT REACHABLE: ' + ', '.join(missing) + ' (those apps were not audited this run; '
                'they are shown as last seen)', '']
    for title, items in (('DRIFT - a rule is broken', [f'{t}   [{k}]' for k, t in drift]),
                         ('WATCH - worth a look', watch), ('GOOD', good), ('OTHER CHANGES', info)):
        if items:
            out += [title] + ['  - ' + x for x in items] + ['']
    if older:
        out += ['STILL OPEN - reported on an earlier run, not fixed yet']
        out += [f"  - {v['text']}   (since {v['first_seen']})   [{k}]" for k, v in sorted(older.items())] + ['']
    team_dates = sorted((s['newest'], k) for k, s in new.items() if s.get('newest'))
    if team_dates:
        out += [f'MIRROR: the newest file in team_anvil_code is dated {team_dates[-1][0]} ({team_dates[-1][1]}). '
                'Only what a developer has published to the share can be seen here.', '']
    out += ['APPS'] + ['  ' + r for r in table(new)]
    if skipped:
        out += ['', 'Not Anvil apps (skipped): ' + ', '.join(skipped)]
    report = '\n'.join(out) + '\n'
    print(report, end='')

    if save:
        os.makedirs(os.path.join(state, 'reports'), exist_ok=True)
        with open(os.path.join(state, 'baseline.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'version': 1, 'run': stamp, 'apps': new, 'open': open_now}, f, indent=1, sort_keys=True)
        with open(os.path.join(state, 'last_report.md'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(report)
        if base is None or drift or watch or good:
            with open(os.path.join(state, 'reports', now.strftime('%Y-%m-%d_%H%M') + '.md'), 'w',
                      encoding='utf-8', newline='\n') as f:
                f.write(report)
        with open(os.path.join(state, 'log.md'), 'a', encoding='utf-8', newline='\n') as f:
            f.write(head + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

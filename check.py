#!/usr/bin/env python3
"""titan-ui check - does an Anvil app follow the Titan house style?

    py -3 check.py <app folder> [<app folder> ...] [--json out.json] [--strict]

Reads only; changes nothing. Standard library only. Exit code 1 when an app has an
ERROR (a broken rule in the shared block, or in a form that has opted in), else 0.
With --strict, legacy findings (forms not converted yet) also fail.

A form may be in one of two looks only: stock Material Design 3, or the Titan house style
(titan-ui). An app with no titan-ui form and no block passes (the Material Design 3 rules apply to it; this check does
not verify that its theme is stock); its forms are listed as LEGACY until they move over.

Rules
  R1  an app with any titan-ui form carries the TITAN-UI block in theme/assets/theme.css
  R2  the block is byte-identical to titan-ui.css next to this script
  R3  theme/parameters.yaml registers every tui role
  R4  no colour codes in theme.css after the block (app CSS uses tokens)
  R5  no font-family / font-size literals in theme.css after the block
  R6  no colour properties in a form's designer file (foreground / background / border)
  R7  no colour codes in a form's Python
  R8  every form opts in (role `tui` on its content panel, or class anvil-role-tui in
      its HTML template) - forms that have not are listed as LEGACY
R6-R8 are ERRORS for forms that opted in and LEGACY counts for the rest: the house
policy is "new forms now, existing forms when they are next touched".
An app is exempt when its root holds a file `.titan-ui-exempt` (first line = the reason).
"""
import hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HEX = re.compile(r'#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b')
ROLES = ['tui', 'tui-toolbar', 'tui-primary', 'tui-danger', 'tui-chip', 'tui-on', 'tui-pill',
         'tui-neutral', 'tui-info', 'tui-ok', 'tui-warn', 'tui-special', 'tui-void', 'tui-meta',
         'tui-late', 'tui-text-warn', 'tui-text-danger', 'tui-text-muted', 'tui-text-ok',
         'tui-text-info', 'tui-text-special', 'tui-row-plan', 'tui-row-stale']


def read(path):
    try:
        with open(path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace').replace('\r\n', '\n')
    except OSError:
        return None


def strip_css_comments(css):
    return re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), css, flags=re.S)


def line_hits(text, pattern, keep=None):
    """[(line number, matched text)] for pattern, optionally filtered."""
    out = []
    for n, line in enumerate(text.split('\n'), 1):
        for m in pattern.finditer(line):
            if keep is None or keep(line, m):
                out.append((n, m.group(0)))
    return out


def canonical_block():
    t = read(os.path.join(HERE, 'titan-ui.css'))
    if t is None:
        sys.exit('titan-ui.css is missing next to check.py')
    return t.rstrip('\n') + '\n'


def extract_block(css):
    a = css.find('/* ==== TITAN-UI BEGIN')
    e = css.find('/* ==== TITAN-UI END')
    if a < 0 or e < 0:
        return None, None, css
    b = css.find('*/', e) + 2
    return css[a:b] + '\n', css[:a], css[b:]


def check_theme(app, canon):
    """R1-R5. Returns (errors, info)."""
    errors, info = [], {}
    css = read(os.path.join(app, 'theme', 'assets', 'theme.css'))
    if css is None:
        return ['R1 theme/assets/theme.css not found'], info
    block, before, after = extract_block(css)
    info['stock_base_sha'] = hashlib.sha256((before if block else css).encode()).hexdigest()[:10]
    if block is None:
        errors.append('R1 no TITAN-UI block in theme.css')
        info['custom_css_colours'] = len(HEX.findall(strip_css_comments(css)))
        return errors, info
    m = re.search(r'TITAN-UI BEGIN (v[\d.]+)', block)
    info['block_version'] = m.group(1) if m else '?'
    cm = re.search(r'TITAN-UI BEGIN (v[\d.]+)', canon)
    if block != canon:
        errors.append(f"R2 TITAN-UI block differs from the canonical {cm.group(1) if cm else ''} "
                      f"(app has {info['block_version']}; sha {hashlib.sha256(block.encode()).hexdigest()[:10]} "
                      f"vs {hashlib.sha256(canon.encode()).hexdigest()[:10]})")
    params = read(os.path.join(app, 'theme', 'parameters.yaml')) or ''
    missing = [r for r in ROLES if not re.search(r'name:\s*' + re.escape(r) + r'\s*$', params, re.M)]
    if missing:
        errors.append('R3 roles not registered in theme/parameters.yaml: ' + ', '.join(missing))
    offset = (before + block).count('\n')
    app_css = strip_css_comments(after)
    for n, h in line_hits(app_css, HEX):
        errors.append(f'R4 theme.css:{n + offset} colour code {h} in app CSS (use a --tui token)')
    fam = line_hits(app_css, re.compile(r'font-family\s*:\s*(?!var\()[^;}]+'))
    size = line_hits(app_css, re.compile(r'font-size\s*:\s*(?!var\(|inherit)[^;}]+'))
    info['app_css_font_family_literals'] = len(fam)
    info['app_css_font_size_literals'] = len(size)
    info['app_css_font_sizes'] = sorted({s.split(':')[1].replace('!important', '').strip() for _, s in size})
    info['app_css_lines'] = after.count('\n')
    info['app_css_important'] = app_css.count('!important')
    return errors, info


def forms_of(app):
    """{form path relative to client_code: {'py','yaml','html'}} + loose modules."""
    root = os.path.join(app, 'client_code')
    forms, modules = {}, []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != '__pycache__']
        rel = os.path.relpath(d, root).replace(os.sep, '/')
        if '__init__.py' in files and ('form_template.yaml' in files or 'form_template.html' in files):
            forms[rel] = {'py': os.path.join(d, '__init__.py'),
                          'yaml': os.path.join(d, 'form_template.yaml') if 'form_template.yaml' in files else None,
                          'html': os.path.join(d, 'form_template.html') if 'form_template.html' in files else None}
        elif rel == '.':
            modules += [os.path.join(d, f) for f in files if f.endswith('.py')]
    return forms, modules


def form_opted_in(app, f):
    """True when the form uses the house style: any `tui...` role in its designer file
    or code (the root role `tui`, or a row template using tui-pill and friends), or an
    HTML page template whose root carries class anvil-role-tui."""
    texts = [read(p) or '' for p in (f['py'], f['yaml'], f['html']) if p]
    blob = '\n'.join(texts)
    if re.search(r"role\s*[:=]\s*\[?\s*['\"]?tui\b", blob) or re.search(r"['\"\[ ]tui-[a-z-]+", blob):
        return True
    for name in re.findall(r'@theme:([\w.-]+\.html)', blob):
        page = read(os.path.join(app, 'theme', 'assets', name)) or ''
        if 'anvil-role-tui' in page:
            return True
    return False


def form_findings(f):
    out = []
    y = read(f['yaml']) if f['yaml'] else None
    if y:
        pat = re.compile(r"\b(foreground|background|border)\s*:\s*['\"]?[^,}\n]*#[0-9A-Fa-f]{3,6}")
        out += [f"R6 {os.path.basename(f['yaml'])}:{n} designer colour ({s.split(':')[0]})" for n, s in line_hits(y, pat)]
    h = read(f['html']) if f['html'] else None
    if h:
        out += [f"R6 {os.path.basename(f['html'])}:{n} colour code {s}" for n, s in line_hits(h, HEX)]
    p = read(f['py']) or ''
    out += [f"R7 __init__.py:{n} colour code {s}" for n, s in
            line_hits(p, HEX, keep=lambda line, m: not line.lstrip().startswith('#'))]
    return out


def check_app(app, canon):
    name = os.path.basename(os.path.normpath(app))
    res = {'app': name, 'errors': [], 'legacy': {}, 'converted': [], 'info': {}}
    if not os.path.isfile(os.path.join(app, 'anvil.yaml')):
        res['skipped'] = 'not an Anvil app (no anvil.yaml)'
        return res
    ex = read(os.path.join(app, '.titan-ui-exempt'))
    if ex is not None:
        res['exempt'] = ex.strip().split('\n')[0] or 'no reason given'
        return res
    res['errors'], res['info'] = check_theme(app, canon)
    forms, modules = forms_of(app)
    opted = {k for k, f in forms.items() if form_opted_in(app, f)}
    if not opted and res['errors'] == ['R1 no TITAN-UI block in theme.css']:
        # nothing has moved to titan-ui yet: a Material Design 3 app, which is permitted
        res['errors'] = []
        res['info']['look'] = ('no titan-ui form yet - the Material Design 3 rules apply '
                               '(this check does not verify that the theme is stock)')
    for k in sorted(forms):
        finds = form_findings(forms[k])
        if k in opted:
            res['converted'].append(k)
            res['errors'] += [f'{x.split(" ", 1)[0]} {k}/{x.split(" ", 1)[1]}' for x in finds]
        else:
            res['legacy'][k] = len(finds)
    mod = 0
    for m in modules:
        p = read(m) or ''
        mod += len(line_hits(p, HEX, keep=lambda line, mm: not line.lstrip().startswith('#')))
    res['info']['module_colour_codes'] = mod
    return res


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    strict = '--strict' in argv
    jout = argv[argv.index('--json') + 1] if '--json' in argv else None
    if jout in args:
        args.remove(jout)
    if not args:
        sys.exit(__doc__)
    canon = canonical_block()
    results, bad = [], False
    for app in args:
        r = check_app(app, canon)
        results.append(r)
        print(f"\n== {r['app']}")
        if 'exempt' in r or 'skipped' in r:
            print('   EXEMPT: ' + r['exempt'] if 'exempt' in r else '   SKIPPED: ' + r['skipped'])
            continue
        i = r['info']
        if i.get('look'):
            print('   ' + i['look'])
        print(f"   block {i.get('block_version', 'none')} | stock base {i.get('stock_base_sha')} | "
              f"forms: {len(r['converted'])} converted, {len(r['legacy'])} legacy "
              f"({sum(r['legacy'].values())} colour findings in legacy forms) | "
              f"colour codes in shared modules: {i.get('module_colour_codes', 0)}")
        if 'app_css_lines' in i:
            print(f"   app CSS after the block: {i['app_css_lines']} lines, "
                  f"{i['app_css_font_size_literals']} font-size literals {i['app_css_font_sizes']}, "
                  f"{i['app_css_font_family_literals']} font-family literals, {i['app_css_important']} !important")
        for e in r['errors'][:40]:
            print('   ERROR ' + e)
        if len(r['errors']) > 40:
            print(f"   ... and {len(r['errors']) - 40} more errors")
        for k, n in sorted(r['legacy'].items(), key=lambda x: -x[1])[:12]:
            print(f'   legacy {k}: {n} colour findings')
        if r['errors'] or (strict and r['legacy']):
            bad = True
    if jout:
        with open(jout, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=1)
    print('\nSUMMARY  app | block | forms converted / legacy | errors | legacy colour findings')
    for r in results:
        if 'exempt' in r or 'skipped' in r:
            print(f"  {r['app']} | " + ('exempt' if 'exempt' in r else 'skipped'))
            continue
        print(f"  {r['app']} | {r['info'].get('block_version') or 'none (M3 rules)'} | {len(r['converted'])} / {len(r['legacy'])} | "
              f"{len(r['errors'])} | {sum(r['legacy'].values())}")
    print('\nRESULT: ' + ('FAIL' if bad else 'PASS'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

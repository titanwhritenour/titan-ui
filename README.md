# titan-ui - the Titan house style

One look for every Titan app. This repository is the single source.

| File | What it is |
|---|---|
| `titan-ui.css` | The canonical TITAN-UI block. It is copied, unchanged, into every app's `theme/assets/theme.css`. Its first line carries the version. |
| `check.py` | The checker. Reads an app and reports every breach with file and line. Read-only, standard library only. |
| `for-app-repos/titan-ui.yml` | The GitHub workflow each app repository carries so the check runs on every push. |
| `audit.py` | The audit. Runs the same rules over every app folder at once and reports only what changed since its last run. |

## How a form uses the style
1. Give the form's top content panel the role `tui` (a custom-HTML form puts the class
   `anvil-role-tui` on its root element).
2. Build with normal Anvil components. Buttons, text boxes, dropdowns, date pickers, check
   boxes, links and data grids take the house look automatically.
3. For a special look, use a role from the list below. Never set a colour, font or size in
   the designer or in code.

| Role | Use |
|---|---|
| `tui` | the form's root panel |
| `tui-toolbar` | a strip of controls above the content (FlowPanel) |
| `tui-primary`, `tui-danger` | the one loud button; a destructive button |
| `tui-chip` + `tui-on` | a filter chip (Link); the active one |
| `tui-pill` + `tui-neutral` / `tui-info` / `tui-ok` / `tui-warn` / `tui-danger` / `tui-special` / `tui-void` | a state pill; the word is always on it |
| `tui-text-warn` / `-danger` / `-ok` / `-info` / `-special` / `-muted` | one word or value in a tone (works in popups) |
| `tui-late` | a past-due value (bold + dark red) |
| `tui-meta` | small grey supporting text |
| `tui-row-plan`, `tui-row-stale` | tinted data-grid rows |

State is never colour alone: a pill, chip or late value always carries its word.

## Run the check by hand
    py -3 check.py "D:\cowork\projects\all_apps\current_anvil_code\dw_Production Control v3.0"
    py -3 check.py <app folder> <app folder> ... --json findings.json
Exit code 1 when an app has an ERROR. `--strict` also fails on legacy (unconverted) forms.

## What it checks
A form may be in one of two looks only: stock Material Design 3, or titan-ui. An app with no
titan-ui form and no block passes: the Material Design 3 rules apply to it (the check does not
verify that its theme is stock), and its forms are listed as LEGACY until they move over.

- R1 an app with any titan-ui form carries the TITAN-UI block in its `theme.css`
- R2 the block is byte-identical to `titan-ui.css` here
- R3 `theme/parameters.yaml` registers every `tui` role
- R4 no colour codes in `theme.css` after the block
- R5 font-family / font-size literals after the block (reported, not yet an error)
- R6 no colour properties in a form's designer file
- R7 no colour codes in a form's Python
- R8 forms that have not opted in are listed as LEGACY

A form has opted in once it uses any `tui` role. R6 and R7 are errors for those forms and
legacy counts for the rest: new forms follow the style now, existing forms when they are
next touched.

An app is exempt only when its root holds a file `.titan-ui-exempt` whose first line gives
the reason.

## Audit every app at once
    py -3 audit.py "D:\cowork\projects\all_apps"
Reads every Anvil app under `current_anvil_code` and `team_anvil_code` (the mirror of the
share), compares with the snapshot of the previous run, and reports only what changed. It
never changes an app. It writes its snapshot and reports to `all_apps\titan-ui-audit`.

- DRIFT, a rule is broken: a new error from the check; a new form or a new app that is not
  titan-ui; a titan-ui form that went back to Material Design 3; an app that marked itself
  exempt. A DRIFT finding stays listed as STILL OPEN on every run until it is fixed, or the
  owner accepts it by adding its key to `titan-ui-audit\accepted.txt`.
- WATCH, a person should look: the layout of a Material Design 3 form changed (if that was a
  rework, the form should have moved to titan-ui); more hand-set colours; `theme.css` changed.
- GOOD: a form moved to titan-ui; an error was cleared; an app adopted the block.

The mirror only holds what each developer has published to the share, so a change that was
never published cannot be seen. `--no-save` reports without updating the snapshot.

## Changing the style
Only here, and only with the owner's approval (Dave Whritenour).
1. Edit `titan-ui.css`; raise the version on its first line.
2. Copy the whole block into each app that carries it, replacing the old block.
3. The check fails any app whose block differs from this one, so a private variant cannot
   pass.

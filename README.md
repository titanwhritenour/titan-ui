# titan-ui - the Titan house style

One look for every Titan app. This repository is the single source.

| File | What it is |
|---|---|
| `titan-ui.css` | The canonical TITAN-UI block. It is copied, unchanged, into every app's `theme/assets/theme.css`. Its first line carries the version. |
| `check.py` | The checker. Reads an app and reports every breach with file and line. Read-only, standard library only. |
| `for-app-repos/titan-ui.yml` | The GitHub workflow each app repository carries so the check runs on every push. |

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
- R1 the app's `theme.css` contains the TITAN-UI block
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

## Changing the style
Only here, and only with the owner's approval (Dave Whritenour).
1. Edit `titan-ui.css`; raise the version on its first line.
2. Copy the whole block into each app that carries it, replacing the old block.
3. The check fails any app whose block differs from this one, so a private variant cannot
   pass.

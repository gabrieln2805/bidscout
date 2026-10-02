# The published page

`index.html` is the page at
<https://gabrieln2805.github.io/bidscout/>. It is one static file: no build
step, no framework, no dependency. It reads `data.json` and renders it.

## Why there is a data file at all

GitHub Pages serves files and runs nothing. The page cannot query SQLite and
cannot call SEAP — the portal sends no CORS headers, so a browser could not
reach it even if we wanted that. So the database is exported first:

```bash
make site          # rebuilds data/demo.sqlite3, then writes docs/data.json
make serve         # http://localhost:8000 — look at it before you push
```

`make site` is the whole pipeline: fixtures → store → extract → decide →
`docs/data.json` → the page. Nothing on the page is typed by hand.

## Turning Pages on

GitHub → **Settings → Pages → Build and deployment → Deploy from a branch**,
branch `main`, folder **`/docs`**. No Action, no workflow file. The page is live
a minute after the push.

## Publishing your own numbers

`make site` exports from `profile.example.yaml`, so the published page shows
*Example SRL*, not you. `bidscout export` prints which profile it read, because
committing an export made from your real `profile.yaml` publishes your turnover,
your past contracts and your guarantee to anyone with the link. That is a fine
thing to do on purpose and a bad thing to do by accident.

To look at your own tenders without publishing them, export somewhere outside
`docs/` and serve that folder:

```bash
bidscout export --out /tmp/mine/data.json
cp docs/index.html /tmp/mine/
python -m http.server 8000 --directory /tmp/mine
```

## What the page may and may not do

- It marks each gate from the `outcome` the engine computed. It never infers a
  verdict by reading the English in `text`.
- It writes every string from the data with `textContent`. Titles and quotes
  come from a public portal and are never treated as markup. Two tests in
  `tests/test_the_export_is_exact_and_self_describing.py` hold both of these.
- It shows the notices nobody has read in full, instead of quietly leaving them
  out of the count.

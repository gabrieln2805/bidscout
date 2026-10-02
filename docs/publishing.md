# Publishing the page

`site/index.html` is the page at <https://gabrieln2805.github.io/bidscout/>.
It is one static file: no build step, no framework, no dependency. It reads
`site/data.json` and renders it.

## Why there is a data file at all

GitHub Pages serves files and runs nothing. The page cannot query a database
and cannot call SEAP — the portal sends no CORS headers, so a browser could not
reach it even if we wanted that. So the app marts are exported first:

```bash
make ingest        # watch + fetch: land new notices from the portal (needs it)
make site          # score → dbt build → site/data.json from the app marts
make serve         # http://localhost:8000 — look at it before you push
```

`make demo-site` does the same from the captured fixtures, on a machine with no
portal. The whole road from the portal to the page is in `docs/data-model.md`.
Nothing on the page is typed by hand.

## Turning Pages on

The page lives in `site/`, and GitHub's "deploy from a branch" only serves the
repository root or `/docs`, so `.github/workflows/pages.yml` publishes `site/`
on every push to `main` that touches it.

**Once:** GitHub → **Settings → Pages → Build and deployment → Source:
GitHub Actions.** Until that is switched, Pages keeps serving the old `/docs`
setting, which no longer holds a page.

## Publishing your own numbers

`make site` exports with `config/profile.example.yaml`, so the published page
shows *Example SRL*, not you. `bidscout export` prints which profile it read,
because committing an export made from your real `config/profile.yaml`
publishes your turnover, your past contracts and your guarantee to anyone with
the link. That is a fine thing to do on purpose and a bad thing to do by
accident.

To look at your own tenders without publishing them, export somewhere outside
`site/` and serve that folder:

```bash
bidscout --profile config/profile.yaml export --out /tmp/mine/data.json
cp site/index.html /tmp/mine/
python -m http.server 8000 --directory /tmp/mine
```

## What the page may and may not do

- It marks each gate from the `outcome` the engine computed. It never infers a
  verdict by reading the English in `text`.
- It writes every string from the data with `textContent`. Titles and quotes
  come from a public portal and are never treated as markup. Two tests in
  `tests/test_the_export_is_exact_and_self_describing.py` hold both of these.
- It lists the notices nobody has read in full, grouped by why, instead of
  quietly leaving them out of the count.

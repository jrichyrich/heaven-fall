# Heaven Fall Card Library

Static PDF-backed card library for Heaven Fall.

## Build

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-build.txt
python scripts/build_heaven_fall_catalog.py
```

This reads canonical datasheets from `data/`, renders the linked PDF pages into `docs/assets/source-cards/`, and regenerates:

- `docs/data/manifest.json`
- `docs/data/catalog.json`
- `docs/data/verification-report.json`

The canonical source PDF lives at `assets/pdf/datasheets-for-heavenfall.pdf`.
The core rules PDF lives at `assets/pdf/heaven-fall-rules.pdf`.
The faction rules PDF lives at `assets/pdf/faction-rules.pdf`.
Archived handwritten captures live under `archive/handwritten-v1/` and are not emitted into the live catalog.

## Test

```bash
python3 -m unittest tests/test_build_heaven_fall_catalog.py
node --test tests/test_card_renderer.js
```

## Serve

```bash
cd docs
python3 -m http.server 8123
```

Then open [http://127.0.0.1:8123/](http://127.0.0.1:8123/).

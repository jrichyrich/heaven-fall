# Heaven Fall Card Library

Static v1 card library for Heaven Fall.

## Build

```bash
python3 scripts/build_heaven_fall_catalog.py
```

This reads raw source data from `data/`, copies the original photographed cards into `docs/assets/source-cards/`, and regenerates:

- `docs/data/manifest.json`
- `docs/data/catalog.json`

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

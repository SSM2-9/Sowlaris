# Sowlaris interface (Sakina) on top of the Field Shift engine (Ekram)

Sowlaris is the only interface. Ekram's earlier Streamlit page and its colours were replaced; the backend was not touched.

    pip3 install -r requirements.txt
    streamlit run app/streamlit_app.py      # or: make app

## Layout of `app/`
    app/streamlit_app.py   entry point: hero screen or dashboard
    app/core/auth.py       accounts, sessions, password reset, profile, delete account (SQLite: app/sowlaris.db)
    app/core/styles.py     palette, fonts, CSS, icons, tooltips
    app/core/engine.py     BRIDGE: calls fieldshift only; the interface never computes a score or ranking
    app/core/data.py       BRIDGE: pipeline numbers -> plain-language cards
    app/views/login.py     hero video + Continue as guest
    app/views/dashboard.py banner, farm setup, field health, rotation options, what-if, guide
    app/views/charts.py    all charts (Sowlaris palette)
    app/assets/, app/static/   images and hero video
    .streamlit/config.toml     Sowlaris theme

## Not edited by the interface (Ekram, Aisanat, Aarya)
`fieldshift/`, `scripts/`, `data/`, `reports/`, and every test except the removed `tests/test_app.py`
(it tested the old interface; its engine-level checks now live in `tests/test_sowlaris_bridge.py`).

## Screen -> engine output
| Section | Source |
|---|---|
| Farm setup: 4 sliders (0-5), 4 situation checkboxes | `recommend(priorities, constraints)` |
| Map circles | `config.FARM`, satellite footprints |
| Field health | `farm` summary, master table, bare soil, regimes, trends, risk heatmaps |
| Rotation options | `strategies`, `ranking`, `notices`, `known_limitations`, `ranking_sensitivity.json` |
| Climate what-if | `what_if()`, `yield_model_results.json` |

## Limits carried into the interface
Data cover one demonstration farm (Riley County, Kansas); a pin elsewhere shows a notice. "Market potential" is not income.

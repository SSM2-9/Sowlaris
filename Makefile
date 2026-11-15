PY ?= python3

.PHONY: all pipeline test app clean

all: pipeline test

pipeline:
	$(PY) scripts/run_pipeline.py

test:
	$(PY) -m pytest -q

app:
	streamlit run app/streamlit_app.py

clean:
	rm -rf data/processed/*.csv reports/*.json .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +

validate:
	$(PY) scripts/validate_water_balance.py

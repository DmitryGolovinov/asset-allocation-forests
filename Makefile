PY ?= python
.PHONY: test demo data-public reproduce-public value-gap benchmark data-private \
	reproduce-private data smoke-real reproduce report check
PUBLIC_RUNS := transfer_french5_dev transfer_french5_dev_relaxed transfer_french5_final \
	transfer_french5_final_relaxed
PRIVATE_RUNS := archival_hw3_dev archival_hw3_dev_relaxed

test:               ## offline solver, proposition, forest and accounting checks
	$(PY) -m pytest -q
demo:               ## synthetic two-regime fixture, no network, writes results/demo/
	$(PY) scripts/demo.py
data-public:        ## PUBLIC input: Kenneth French library download (compared with the snapshot)
	$(PY) -c "import sys; sys.path.insert(0,'src'); from aaf.data import download_french; download_french('data')"
reproduce-public:   ## French transfer (development), both leaf formulations, three seeds
	$(PY) scripts/run_study.py --dataset transfer_french5
	$(PY) scripts/run_study.py --dataset transfer_french5 --leaf relaxed
	$(PY) scripts/run_study.py --dataset transfer_french5 --compare-formulations
	$(PY) scripts/make_report.py transfer_french5_dev transfer_french5_dev_relaxed
value-gap:          ## paired value-gap count on development node problems (10-15 min, one core)
	$(PY) scripts/paired_value_gap.py
	$(PY) scripts/make_report.py transfer_french5_dev
benchmark:          ## leaf-solver benchmark (minutes)
	$(PY) scripts/leaf_benchmark.py
data-private:       ## PRIVATE supplied workbook (not redistributed; see docs/data.md)
	@test -f data/HW3_dataset.xlsx || (echo "The archival reproduction needs the course-supplied \
	HW3_dataset.xlsx in data/. It is not redistributed. The French study does not need it: \
	make data-public reproduce-public." && exit 1)
reproduce-private: data-private  ## archival reproduction, both formulations
	$(PY) scripts/run_study.py --dataset archival_hw3
	$(PY) scripts/run_study.py --dataset archival_hw3 --leaf relaxed
	$(PY) scripts/run_study.py --dataset archival_hw3 --compare-formulations
	$(PY) scripts/make_report.py archival_hw3_dev archival_hw3_dev_relaxed
data: data-public
smoke-real:         ## French transfer (development), one seed
	$(PY) scripts/run_study.py --dataset transfer_french5 --seeds 0
reproduce: reproduce-public
report:             ## rebuild tables and figures from whichever run artifacts exist
	$(PY) scripts/evaluation_diagnostics.py
	@for r in $(PUBLIC_RUNS) $(PRIVATE_RUNS); do if [ -f results/$$r/manifest.json ]; then \
	$(PY) scripts/make_report.py $$r || exit 1; fi; done
check: test
	$(PY) -m ruff check src tests scripts
	$(PY) scripts/check_claims.py

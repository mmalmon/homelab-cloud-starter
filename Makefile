.PHONY: test lint compose-check check

test:
	python3 -m unittest discover -s tests
	cd containers/updater && python3 -m unittest discover -s tests

lint:
	python3 -m py_compile wizard/*.py containers/updater/updater.py containers/updater/web/web.py
	bash -n homelab

compose-check:
	@for f in containers/*/compose.yaml; do \
	  d=$$(dirname $$f); \
	  if [ -f $$d/.env.example ]; then docker compose --env-file $$d/.env.example -f $$f config -q || exit 1; \
	  else docker compose -f $$f config -q || exit 1; fi; \
	done

check: lint test compose-check

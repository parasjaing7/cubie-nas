.PHONY: help deploy-safe deploy-safe-dry

help:
	@echo "Targets:"
	@echo "  deploy-safe      Run safe deployment with restart verification"
	@echo "  deploy-safe-dry  Preview safe deployment without changes"

deploy-safe:
	bash scripts/deploy-safe.sh

deploy-safe-dry:
	bash scripts/deploy-safe.sh --dry-run

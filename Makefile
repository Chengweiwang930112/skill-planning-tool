# Every target is a single command that runs the same in cmd, PowerShell and bash;
# the logic lives in scripts/dev.ps1 (Windows) and scripts/dev.sh (Linux, macOS).
ifeq ($(OS),Windows_NT)
DEV := powershell -NoProfile -ExecutionPolicy Bypass -File scripts/dev.ps1
else
DEV := bash scripts/dev.sh
endif

.DEFAULT_GOAL := help
.PHONY: help start stop restart clean

help start stop restart clean:
	@$(DEV) $@

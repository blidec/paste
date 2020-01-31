all:
	@echo "make <target>"
	@echo ""
	@echo "targets:"
	@echo "  build           - build binaries in the build/ directory"
	@echo "  test            - runs tests"
	@echo "  dockerimage     - build a dockerimage of the service and add to docker engine"
	@echo "  clean           - remove intermediate files"

lint:
    flake8 --exclude=.tox

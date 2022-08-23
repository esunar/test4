help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make clean - remove unneeded files"
	@echo " make dev-environment - setup the development environment"
	@echo " make build - build the snap"
	@echo " make lint - run flake8, black --check and isort --check-only"
	@echo " make reformat - run black and isort and reformat files"
	@echo " make unittests - run the tests defined in the unittest subdirectory"
	@echo " make functional - run the tests defined in the functional subdirectory"
	@echo " make test - run lint, proof, unittests and functional targets"
	@echo " make pre-commit - run pre-commit checks on all the files"
	@echo ""


lint:
	@echo "Running lint checks"
	@tox -e lint

unittests:
	@echo "Running unit tests"
	@tox -e unit


test: lint unittests functional
	@echo "Tests completed for the snap."


reformat:
	@echo "Reformat files with black and isort"
	tox -e reformat

build:
	@echo "Building the snap"
	@snapcraft --use-lxd

clean:
	@echo "Cleaning snap"
	@snapcraft clean --use-lxd
	@echo "Cleaning existing snap builds"
	@find . -name "*.snap" -delete

dev-environment:
	@echo "Creating virtualenv and installing pre-commit"
	@virtualenv -p python3 .venv
	@.venv/bin/pip install -r tests/requirements.txt
	@.venv/bin/pre-commit install

functional: build
	@echo "Executing functional tests using built snap"
	@tox -e func

pre-commit:
	@tox -e pre-commit

# The targets below don't depend on a file
.PHONY: help clean dev-environment build lint reformat unittests functional test pre-commit

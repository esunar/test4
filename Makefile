lint:
	tox -e lintverbose

test:
	tox -e unit

format-code:
	tox -e format-code

build:
	snapcraft --use-lxd --debug

clean:
	snapcraft clean --use-lxd


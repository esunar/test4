lint:
	tox -e lintverbose

dch:
	if ! which gbp > /dev/null; then sudo apt-get install -y git-buildpackage; fi
	gbp dch --debian-tag='%(version)s' -D xenial --git-log --first-parent

deb-src:
	debuild -S -sa -I.git -I.tox

test:
	tox -e unit

format-code:
	tox -e format-code

build:
	snapcraft --use-lxd --debug

clean:
	snapcraft clean --use-lxd


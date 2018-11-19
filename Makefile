lint:
	tox -e lint

dch:
	if ! which gbp > /dev/null; then sudo apt-get install -y git-buildpackage; fi
	gbp dch --debian-tag='%(version)s' -D xenial --git-log --first-parent

deb-src:
	debuild -S -sa -I.git -I.tox

test:
	python3 -m unittest discover tests

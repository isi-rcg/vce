PACKAGE := vce
SHELL := /bin/bash

# .ONESHELL:
.PHONY: init test coverage style docs package upload clean libs-debian influxdb-debian libs-macos pyz s3

init:
	python3.7 -m pip install pipenv --user --upgrade
	PIP_NO_BINARY=shapely pipenv install --dev

libs-debian: influxdb-debian
	sudo apt-get install libproj-dev libgeos-dev

influxdb-debian:
	wget https://dl.influxdata.com/influxdb/releases/influxdb_1.7.4_amd64.deb
	sudo dpkg -i influxdb_1.7.4_amd64.deb
	rm influxdb_1.7.4_amd64.deb
	sudo service influxdb start
	sleep 3
	HOSTALIASES=hosts LOGLEVEL=info pipenv run python -m vce db reset demo/demo.yml

libs-macos:
	brew install pyqt proj geos influxdb

test:
	pipenv run pytest tests

coverage:
	pipenv run py.test --verbose --cov-report term --cov-report xml --cov=requests tests

style:
	pipenv run flake8 ${PACKAGE}

docs:
	cd docs && pipenv run sphinx-apidoc -o api/ ../${PACKAGE} && pipenv run make html

pyz:
	mkdir -p build
	pipenv run shiv -o build/vce --compressed -p '/usr/bin/env python3.7' --site-packages `pipenv --venv`/lib/python3.7/site-packages --no-deps . -e vce.__main__:main
	chmod +x build/vce

tar:
	mkdir -p build
	cd ..; tar cvf vce/build/vce.tar --exclude='*~' --exclude='.git*' --exclude='docs/_build/*' --exclude='build' --exclude='__pycache__*' vce

s3:
	aws s3 cp build/vce.tar s3://vce-framework/vce.tar

package:
	@pipenv run python setup.py check --restructuredtext --strict && ([ $$? -eq 0 ] && echo "README.rst ok") || echo "Invalid markup in README.rst!"
	pipenv run python setup.py sdist bdist_wheel
	@echo "Install the package with:"
	@echo "  python3.7 -m pip install --user --upgrade --force-reinstall `ls dist/*whl`"

upload:
#	pipenv run twine upload dist/*

clean:
	rm -rf Leap_Second.dat deltat* *pdf *gif
	rm -rf htmlcov .coverage
	rm -rf docs/_build docs/api
	rm -fr build dist ${PACKAGE}.egg-info
	find . \( -name "*.pyc" -o -name "*.pyo" -o -name __pycache__ -o -name "*~" \) -delete

clean:
	-rm -rf build
	-rm -rf dist
	-rm -rf *.egg-info
	-rm -f tests/.coverage
	-docker rm `docker ps -a -q`
	-docker rmi `docker images -q --filter "dangling=true"`

build: clean
	python setup.py bdist_wheel

uninstall:
	-pip uninstall -y vlab-ipam-api

install: uninstall build
	pip install -U dist/*.whl

test: uninstall install
	cd tests && nosetests -v --with-coverage --cover-package=vlab_ipam_api

images: build
	docker build -f DevDockerfile -t devipam .

up:
	docker-compose -p vlabIpamDev up --abort-on-container-exit

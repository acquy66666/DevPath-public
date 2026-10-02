# The Docker API proxy between the grading worker and the daemon (server.py).
#
# Standard library only: the image is a Python and three files. It is the one
# container on the host that holds the Docker socket, so it is kept small
# enough to read in full.
FROM python:3.12-alpine

WORKDIR /opt/devpath
COPY __init__.py policy.py server.py proxy/

# Production runs it as 10001 with the host's docker group added
# (docker-compose.prod.yml) -- enough to reach the socket and to read the
# grading workspace the worker, also 10001, writes. Never needs root there.
USER 10001:10001
EXPOSE 2375

CMD ["python", "-m", "proxy.server"]

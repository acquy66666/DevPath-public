# The backup service: the database's own image, plus the glue.
#
# Same base as the `postgres` service, so pg_dump and pg_restore are the
# server's exact major version. A pg_dump older than the server refuses to run,
# and one newer writes archives an older server may not load -- either way the
# failure would surface on the night a restore is needed. Bump this tag with
# the postgres service's, never separately.
FROM pgvector/pgvector:pg16

# Debian's own boto3, not PyPI's: no pip in the image, nothing resolved at
# build time, and the version is whatever bookworm ships (1.26), which is
# plenty for list / upload / download / delete.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-boto3 \
    && rm -rf /var/lib/apt/lists/*

COPY devpath_backup.py /usr/local/lib/devpath-backup/devpath_backup.py

# Not root: the tools connect over the network and write only to /tmp.
USER postgres
WORKDIR /tmp

# The base image stops with SIGINT, which is Postgres's "fast shutdown". To
# Python it is a KeyboardInterrupt: every `docker stop` ended in a traceback
# and exit 130. SIGTERM goes to the handler devpath_backup.py installs.
STOPSIGNAL SIGTERM

ENTRYPOINT ["python3", "/usr/local/lib/devpath-backup/devpath_backup.py"]
CMD ["serve"]

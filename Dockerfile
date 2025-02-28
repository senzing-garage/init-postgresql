ARG BASE_IMAGE=senzing/senzingapi-runtime:3.12.5
FROM ${BASE_IMAGE}

ENV REFRESHED_AT=2025-02-05

LABEL Name="senzing/init-postgresql" \
  Maintainer="support@senzing.com" \
  Version="1.1.17"

# Define health check.

HEALTHCHECK CMD ["/app/healthcheck.sh"]

# Run as "root" for system installation.

USER root

# Install packages via apt.

RUN apt-get update \
  && apt-get -y install \
  gnupg2 \
  libaio1 \
  libodbc1 \
  odbc-postgresql \
  python3 \
  python3-pip \
  python3-venv \
  wget \
  && rm -rf /var/lib/apt/lists/*

# Install packages via PIP.

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY requirements.txt .
RUN pip3 install --upgrade pip \
  && pip3 install -r requirements.txt \
  && rm /requirements.txt

# Copy files from repository.

COPY ./rootfs /
COPY ./init-postgresql.py /app/

# Set environment variables.

ENV LD_LIBRARY_PATH=/opt/senzing/er/lib:/opt/senzing/er/lib/debian
ENV PATH=${PATH}:/opt/senzing/er/python
ENV PYTHONPATH=/opt/senzing/er/sdk/python
ENV SENZING_DOCKER_LAUNCHED=true

# Make non-root container.

USER 1001:1001

# Runtime execution.

WORKDIR /app
ENTRYPOINT ["/app/init-postgresql.py"]

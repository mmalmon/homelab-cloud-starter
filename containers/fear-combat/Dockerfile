FROM ubuntu:24.04

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        libc6:i386 \
        libgcc-s1:i386 \
        libstdc++5:i386 \
        glibc-tools:i386 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /server/FEAR
COPY --chmod=755 start-server.sh /usr/local/bin/start-server
ENV FEAR_SERVER_BIN=FEAR/fearserver.bin
ENTRYPOINT ["/usr/local/bin/start-server"]

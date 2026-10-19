#!/bin/sh
# Creates the platform topics once the broker is up. Safe to re-run.
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
TOPICS="goods.changed publications.changed user.events orders.changed"

echo "[kafka-init] waiting for ${BOOTSTRAP}"
until /opt/kafka/bin/kafka-topics.sh --bootstrap-server "${BOOTSTRAP}" --list >/dev/null 2>&1; do
    sleep 2
done

for topic in ${TOPICS}; do
    echo "[kafka-init] ensuring topic ${topic}"
    /opt/kafka/bin/kafka-topics.sh \
        --bootstrap-server "${BOOTSTRAP}" \
        --create --if-not-exists \
        --topic "${topic}" \
        --partitions 3 \
        --replication-factor 1
done

echo "[kafka-init] done"

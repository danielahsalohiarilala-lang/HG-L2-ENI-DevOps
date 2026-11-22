#!/bin/bash
cd /home/tantara/HG-L2-ENI-DevOps/tantara-db || exit 1
OLD=$(docker inspect -f '{{.Image}}' tantara-app 2>/dev/null)
docker compose pull -q app
docker compose up -d app
NEW=$(docker inspect -f '{{.Image}}' tantara-app 2>/dev/null)
if [ "$OLD" != "$NEW" ]; then
  echo "[$(date)] nouvelle image deployee" >> deploy.log
fi
docker image prune -f > /dev/null


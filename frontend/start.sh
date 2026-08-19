#!/bin/sh

set -e

sed -i "s|http://backend:8000|${BACKEND_URL}|g" \
  /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
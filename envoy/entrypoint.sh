#!/bin/sh
envsubst '${FRONTEND_URL} ${GRPC_HOST} ${GRPC_PORT}' < /etc/envoy/envoy.template.yaml > /etc/envoy/envoy.yaml
exec envoy -c /etc/envoy/envoy.yaml
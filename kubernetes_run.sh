#!/bin/bash
set -e

# Build Docker image
docker build -t otel-span-log:latest .

# Push to registry (uncomment and edit if using a remote registry)
# docker tag otel-span-log:latest <your-registry>/otel-span-log:latest
# docker push <your-registry>/otel-span-log:latest

echo "Docker image built."

echo "Apply Kubernetes pod manifest..."
kubectl apply -f kubernetes/otel-span-log-pod.yaml

echo "Pod created. Check logs with: kubectl logs -l app=otel-span-log"


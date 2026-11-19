#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  (
    umask 077
    set -o noclobber
    cat > .env <<EOF
COMPOSE_PROJECT_NAME=university-student-demo
ENVIRONMENT=production
DEBUG=false
POSTGRES_USER=uni
POSTGRES_DB=uni_service
POSTGRES_PASSWORD=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)
BACKEND_PORT=18001
NVIDIA_API_KEY=
EOF
  )
fi
docker_cli=(docker)
if ! docker info >/dev/null 2>&1; then
  docker_cli=(sudo docker)
fi
"${docker_cli[@]}" compose config --quiet
"${docker_cli[@]}" compose up -d --build --wait
"${docker_cli[@]}" compose exec -T backend alembic upgrade head
"${docker_cli[@]}" compose exec -T backend python -m scripts.prepare_demo
echo "Студенческая площадка: http://$( "${docker_cli[@]}" compose port backend 8000)/"

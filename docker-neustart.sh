# Laufende Container stoppen
docker stop $(docker ps -q)

# Alte Container entfernen (optional)
docker rm $(docker ps -aq)

# Neues Image bauen
docker-compose build --no-cache

# Container starten
docker-compose up
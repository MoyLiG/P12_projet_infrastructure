# Image Kestra custom : dépendances Python RUNTIME du pipeline pré-installées.
#
# Pourquoi : sans ça, chaque recreate du conteneur Kestra perd les paquets pip,
# obligeant le flow à réinstaller great-expectations & co à chaque run (lent +
# logs verbeux + allers-retours de debug). En les figeant dans l'image, les
# tâches Process runner démarrent instantanément et le flow n'a plus besoin de
# `beforeCommands: pip install`.
#
# On n'embarque que le runtime (pas pytest/bandit/python-docx, qui sont dev).
FROM kestra/kestra:v0.19.0

USER root

RUN pip install --quiet --no-cache-dir \
      pandas==2.1.4 numpy==1.26.4 openpyxl==3.1.5 \
      SQLAlchemy==2.0.36 "psycopg[binary]==3.2.3" \
      pydantic==2.9.2 pydantic-settings==2.6.1 \
      Faker==30.8.2 great-expectations==1.2.4 \
      googlemaps==4.10.0 geopy==2.4.1 \
      requests==2.33.0 tenacity==9.0.0

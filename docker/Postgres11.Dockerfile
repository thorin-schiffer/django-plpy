FROM postgres:11-buster

RUN apt-get update && apt-get -y install postgresql-plpython3-11

RUN  apt-get clean && \
     rm -rf /var/cache/apt/* /var/lib/apt/lists/*

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 5432
CMD ["postgres"]

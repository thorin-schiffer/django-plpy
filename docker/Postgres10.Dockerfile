FROM postgres:10-buster

RUN apt-get update && apt-get -y install postgresql-plpython3-10

RUN  apt-get clean && \
     rm -rf /var/cache/apt/* /var/lib/apt/lists/*

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5432
CMD ["postgres"]

FROM postgres:10

RUN apt-get update
RUN apt-get -y install python3 postgresql-plpython3-10

RUN  apt-get clean && \
     rm -rf /var/cache/apt/* /var/lib/apt/lists/*

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5432
CMD ["postgres"]

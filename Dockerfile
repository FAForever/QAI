FROM python:3.6

RUN pip install --upgrade pip==18.0 pipenv==2018.7.1
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD . /code/
WORKDIR /code/

RUN pipenv run pip install --upgrade pip==18.0
RUN pipenv install

VOLUME /config

# irc3 searches for the plugin files in the folder of the configuration file
CMD cp /config/config.ini ./config.ini && pipenv run irc3 config.ini

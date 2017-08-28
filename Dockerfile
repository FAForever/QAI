FROM python:3.5

RUN pip install --upgrade pip
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.txt /tmp/requirements.txt

RUN pip install --upgrade --trusted-host content.dev.faforever.com -r /tmp/requirements.txt

ADD . /code/
WORKDIR /code/

VOLUME /config

# irc3 searches for the plugin files in the folder of the configuration file
CMD cp /config/config.ini ./config.ini && irc3 config.ini
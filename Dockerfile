FROM python:3.5

RUN pip install --upgrade pip
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

COPY requirements.txt /tmp/requirements.txt

RUN pip install --upgrade --trusted-host content.dev.faforever.com -r /tmp/requirements.txt

RUN cat /config/config.ini

CMD irc3 /config/config.ini
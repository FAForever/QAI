# FA Forever - IRC bot

[![Build Status](https://travis-ci.org/FAForever/QAI.svg?branch=master)](https://travis-ci.org/FAForever/QAI)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/FAForever/QAI/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/FAForever/QAI/?branch=master)

This is the source code for the [Forged Alliance Forever](http://www.faforever.com/) IRC bot.

## Installation

Install Python 3.6 or a later 3.x version.

Latest pip version (18.1) at the moment of writing this document breaks pipenv - https://github.com/pypa/pipenv/issues/2924, 
so we will need to install version 18.0

Install pip version 18.0:

    windows:    pip install --upgrade pip==18.0
                pip --version

    linux:      pip3 install --upgrade pip==18.0
                pip3 --version


Install the package dependencies:

    windows:    pip install -r requirements.txt
                pipenv run pip install --upgrade pip==18.0
                pipenv install

    linux:      pip3 install -r requirements.txt
                pipenv run pip3 install --upgrade pip==18.0
                pipenv install


Create the config file and modify the settings as appropriate:

    cp config.ini.example config.ini

Create the `passwords.py` file. You can create of copy of the `passwords.py.example` file
in [the server repo](https://github.com/FAForever/server).

## Usage

    pipenv shell
    python3 -m irc3 config.ini

## Running the tests

    pipenv shell
    py.test tests/

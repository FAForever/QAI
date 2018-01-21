# FA Forever - IRC bot

[![Build Status](https://travis-ci.org/FAForever/QAI.svg?branch=master)](https://travis-ci.org/FAForever/QAI)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/FAForever/QAI/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/FAForever/QAI/?branch=master)

This is the source code for the [Forged Alliance Forever](http://www.faforever.com/) IRC bot.

## Installation

Install Python 3.4 or a later 3.x version.

Install the package dependencies:

    windows:	pip install -r requirements.txt
    linux:		pip3 install -r requirements.txt

Create the config file and modify the settings as appropriate:

    cp config.ini.example config.ini

Create the `passwords.py` file. You can create of copy of the `passwords.py.example` file
in [the server repo](https://github.com/FAForever/server).

## Usage

    python3 -m irc3 ../config.ini

## Running the tests

    py.test tests/

# FA Forever - IRC bot

[![Build Status](https://travis-ci.org/FAForever/fafbot.svg?branch=master)](https://travis-ci.org/FAForever/fafbot)
[![Scrutinizer Code Quality](https://scrutinizer-ci.com/g/FAForever/fafbot/badges/quality-score.png?b=master)](https://scrutinizer-ci.com/g/FAForever/fafbot/?branch=master)

This is the source code for the [Forged Alliance Forever](http://www.faforever.com/) IRC bot.

## Installation

Install Python 2.7 or a later 2.x version.

Install the package dependencies:

    pip install -r requirements.txt

Create the config file and modify the settings as appropriate:

    cp fafbot.conf.example fafbot.conf

Create the `passwords.py` file. You can create of copy of the `passwords.py.example` file
in [the server repo](https://github.com/FAForever/server).

## Usage

    python fafbot.py

## Running the tests

    py.test tests/

"""bidscout — read a Romanian public tender and say whether it is worth bidding.

The package is split so that one concern lives in one place:

* ``sicap``   talks to the portal. It is the only place that knows a URL.
* ``extract`` turns portal text into facts. Every fact keeps its quote.
* ``decide``  applies the rules. The rules live in YAML, not in code.
* ``store``   keeps the raw data for ever, so a parser fix can be replayed.
* ``warehouse`` builds the dbt models over the store and reads the app marts.
* ``export``  writes the app marts to the JSON file the page reads.
"""

__version__ = "0.4.0"

# CS172 Search Engine

## Requirements

- PyLucene
- Flask
- PRAW Reddit Data

## Deployment

Run `./indexer.sh <data-dir>` to build the index and run the web app

Alternatively, you can build the index directly with `python index.py <data-dir>` and then perform CLI searches by running `python search.py`

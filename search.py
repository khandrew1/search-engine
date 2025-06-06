#!/usr/bin/env python

INDEX_DIR = "index/IndexFiles.index"

import sys, os, lucene

from java.nio.file import Paths
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.index import DirectoryReader
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import NIOFSDirectory
from org.apache.lucene.search import IndexSearcher

"""
This script is loosely based on the Lucene (java implementation) demo class
org.apache.lucene.demo.SearchFiles.  It will prompt for a search query, then it
will search the Lucene index in the current directory called 'index' for the
search query entered against the 'contents' field.  It will then display the
'path' and 'name' fields for each of the hits it finds in the index.  Note that
search.close() is currently commented out because it causes a stack overflow in
some cases.
"""


def documentToJSON(doc):
    return {
        "title": doc.get("title"),
        "text": doc.get("text"),
        "author": doc.get("author"),
        "subreddit": doc.get("subreddit"),
        "linked_page_title": doc.get("linked_page_title"),
        "post_id": doc.get("post_id"),
        "type": doc.get("type"),
        "post_url": doc.get("post_url"),
        "timestamp": doc.get("timestamp"),
        "score": doc.get("score"),
        "num_comments": doc.get("num_comments"),
    }


def run(searcher, analyzer):
    while True:
        print()
        print("Hit enter with no input to quit.")
        command = input("Query:")
        if command == "":
            return

        print()
        print("Searching for:", command)
        query = QueryParser("title", analyzer).parse(command)
        scoreDocs = searcher.search(query, 50).scoreDocs
        print("%s total matching documents." % len(scoreDocs))

        for scoreDoc in scoreDocs:
            doc = searcher.storedFields().document(scoreDoc.doc)

            print(documentToJSON(doc))


if __name__ == "__main__":
    lucene.initVM(vmargs=["-Djava.awt.headless=true"])
    print("lucene", lucene.VERSION)
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    directory = NIOFSDirectory(Paths.get(os.path.join(base_dir, INDEX_DIR)))
    searcher = IndexSearcher(DirectoryReader.open(directory))
    analyzer = StandardAnalyzer()
    run(searcher, analyzer)
    del searcher

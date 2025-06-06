INDEX_DIR = "index/IndexFiles.index"

import sys
import os
import lucene
import threading
import time
import json

from datetime import datetime

from java.nio.file import Paths
from org.apache.lucene.analysis.miscellaneous import LimitTokenCountAnalyzer
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.util import BytesRef
from org.apache.lucene.document import (
    Document,
    Field,
    TextField,
    StringField,
    IntPoint,
    StoredField,
    NumericDocValuesField,
    SortedDocValuesField,
)
from org.apache.lucene.index import (
    IndexWriter,
    IndexWriterConfig,
)
from org.apache.lucene.store import NIOFSDirectory


class Ticker(object):
    def __init__(self):
        self.tick = True

    def run(self):
        while self.tick:
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(1.0)


class IndexFiles:
    def __init__(self, root, storeDir, analyzer):
        if not os.path.exists(storeDir):
            os.makedirs(storeDir)

        store = NIOFSDirectory(Paths.get(storeDir))
        analyzer = LimitTokenCountAnalyzer(analyzer, 1000000)
        config = IndexWriterConfig(analyzer)
        config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
        writer = IndexWriter(store, config)

        self._initialize_field_handlers()

        self.indexDocs(root, writer)
        ticker = Ticker()
        print("commit index", end=" ")
        threading.Thread(target=ticker.run).start()
        writer.commit()
        writer.close()
        ticker.tick = False
        print("done")

    def _parseJSON(self, file):
        return [json.loads(line) for line in file if line.strip()]

    def _handle_text_field(self, doc, key, value):
        if str(value):
            doc.add(TextField(key, str(value), Field.Store.YES))

    def _handle_string_field(self, doc, key, value):
        doc.add(StringField(key, str(value), Field.Store.YES))

    def _handle_integer_field(self, doc, key, value):
        try:
            val_int = int(value)
            doc.add(IntPoint(key, val_int))
            doc.add(StoredField(key, val_int))
            doc.add(NumericDocValuesField(key, val_int))
        except (ValueError, TypeError):
            print(f"Invalid integer value for {key}: {value}")

    def _handle_timestamp_iso_field(self, doc, key, value):
        ts_str = str(value)
        doc.add(StoredField(key, ts_str))
        doc.add(SortedDocValuesField(key, BytesRef(ts_str)))

    def _initialize_field_handlers(self):
        self.field_handlers = {
            "title": self._handle_text_field,
            "text": self._handle_text_field,
            "author": self._handle_text_field,
            "subreddit": self._handle_text_field,
            "linked_page_title": self._handle_text_field,
            "post_id": self._handle_string_field,
            "type": self._handle_string_field,
            "post_url": self._handle_string_field,
            "timestamp": self._handle_timestamp_iso_field,
            "score": self._handle_integer_field,
            "num_comments": self._handle_integer_field,
        }

    def indexDocs(self, root, writer):
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue
                print("adding", filename)
                try:
                    path = os.path.join(dirpath, filename)
                    with open(path, "r") as file:
                        data = self._parseJSON(file)
                        for json_obj in data:
                            doc = Document()
                            doc.add(StringField("filename", filename, Field.Store.YES))
                            doc.add(StringField("filepath", dirpath, Field.Store.YES))

                            for key, value in json_obj.items():
                                if value is None:
                                    continue

                                handler = self.field_handlers.get(key)
                                if handler:
                                    handler(doc, key, value)
                                else:
                                    print(
                                        f"Warning to specific handler for JSON field '{key}'. Applying generic TextField"
                                    )
                                    self._handle_text_field(doc, key, value)

                            writer.addDocument(doc)
                except Exception as e:
                    print("Failed in indexDocs:", e)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(IndexFiles.__doc__)
        sys.exit(1)
    env = lucene.initVM(vmargs=["-Djava.awt.headless=true"])
    print("lucene", lucene.VERSION)

    def fn():
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        env.attachCurrentThread()
        start = datetime.now()
        IndexFiles(sys.argv[1], os.path.join(base_dir, INDEX_DIR), StandardAnalyzer())
        end = datetime.now()
        print(end - start)

    threading.Thread(target=fn).start()

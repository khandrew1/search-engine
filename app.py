import os
import lucene

from flask import Flask, render_template, request

from java.nio.file import Paths
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.index import DirectoryReader, Term
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.store import NIOFSDirectory
from org.apache.lucene.search import (
    IndexSearcher,
    BooleanQuery,
    BooleanClause,
    TermQuery,
    Sort,
    SortField,
)

INDEX_DIR = "index/IndexFiles.index"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LUCENE_INDEX_PATH = os.path.join(BASE_DIR, INDEX_DIR)

app = Flask(__name__)

# --- Global Lucene Objects ---
searcher = None
analyzer = None
vm_env = None


def initialize_lucene():
    global searcher, analyzer, vm_env
    try:
        try:
            vm_env = lucene.getVMEnv()
            if vm_env:
                vm_env.attachCurrentThread()
            else:
                vm_env = lucene.initVM(vmargs=["-Djava.awt.headless=true"])
                vm_env.attachCurrentThread()
        except lucene.JavaError:
            vm_env = lucene.initVM(vmargs=["-Djava.awt.headless=true"])
            vm_env.attachCurrentThread()
        print(f"Lucene version: {lucene.VERSION}")

        if not os.path.exists(LUCENE_INDEX_PATH):
            print(
                f"Index directory not found at {LUCENE_INDEX_PATH}. Please run index.py first."
            )
            return

        directory = NIOFSDirectory(Paths.get(LUCENE_INDEX_PATH))
        searcher = IndexSearcher(DirectoryReader.open(directory))
        analyzer = StandardAnalyzer()
        print("Lucene Searcher and Analyzer initialized.")

    except Exception as e:
        print(f"Error initializing Lucene: {e}")
        raise


def document_to_json_serializable(doc):
    data = {
        "title": doc.get("title"),
        "text": doc.get("text"),
        "author": doc.get("author"),
        "subreddit": doc.get("subreddit"),
        "linked_page_title": doc.get("linked_page_title"),
        "post_id": doc.get("post_id"),
        "type": doc.get("type"),
        "post_url": doc.get("post_url"),
        "timestamp": doc.get("timestamp"),
        "score": None,
        "num_comments": None,
    }
    score_val = doc.get("score")
    if score_val is not None:
        try:
            data["score"] = int(score_val)
        except ValueError:
            data["score"] = score_val

    num_comments_val = doc.get("num_comments")
    if num_comments_val is not None:
        try:
            data["num_comments"] = int(num_comments_val)
        except ValueError:
            alt_comments_val = doc.get("comments")
            if alt_comments_val is not None:
                try:
                    data["num_comments"] = int(alt_comments_val)
                except ValueError:
                    data["num_comments"] = alt_comments_val
            else:
                data["num_comments"] = num_comments_val
    return data


@app.route("/")
def home():
    sort_field = request.args.get("sort_field", "relevance")
    sort_order = request.args.get("sort_order", "desc")
    type_field = request.args.get("type_field", "posts")
    reddit_field = request.args.get("reddit_field", "ucr")
    return render_template(
        "index.html",
        sort_field=sort_field,
        sort_order=sort_order,
        type_field=type_field,
        reddit_field=reddit_field,
    )


@app.route("/search", methods=["POST"])
def search_results_view():
    global searcher, analyzer, vm_env
    if not searcher or not analyzer:
        return "Lucene not initialized. Please check server logs.", 500
    if vm_env and not vm_env.isCurrentThreadAttached():
        vm_env.attachCurrentThread()

    query_string = request.form.get("query", "")
    sort_field_form = request.form.get("sort_field", "relevance")
    sort_order_form = request.form.get("sort_order", "desc")
    type_field_form = request.form.get("type_field", "posts")
    reddit_field_form = request.form.get("reddit_field", "ucr")

    if not query_string:
        return render_template(
            "results.html",
            query=query_string,
            results=[],
            count=0,
            error="Please enter a search query.",
            sort_field=sort_field_form,
            sort_order=sort_order_form,
            type_field=type_field_form,
            reddit_field=reddit_field_form,
        )

    results = []
    count = 0
    error_message = None
    lucene_sort = None

    try:
        print(
            f"Searching {reddit_field_form} for {type_field_form} with: {query_string}, sort: {sort_field_form} {sort_order_form}"
        )

        escaped_query_string = QueryParser.escape(query_string)
        if type_field_form == "posts":
            main_query = QueryParser("text", analyzer).parse(escaped_query_string)
            type_filter_query = TermQuery(Term("type", "post"))
        else:
            main_query = QueryParser("text", analyzer).parse(escaped_query_string)
            type_filter_query = TermQuery(Term("type", "comment"))

        boolean_query_builder = BooleanQuery.Builder()
        boolean_query_builder.add(main_query, BooleanClause.Occur.MUST)
        boolean_query_builder.add(type_filter_query, BooleanClause.Occur.MUST)
        if reddit_field_form != "all":
            reddit_filter_query = TermQuery(Term("subreddit", reddit_field_form))
            boolean_query_builder.add(reddit_filter_query, BooleanClause.Occur.MUST)
        final_query = boolean_query_builder.build()

        is_reverse = sort_order_form == "desc"

        if sort_field_form == "timestamp":
            sf = SortField("timestamp", SortField.Type.STRING, is_reverse)
            lucene_sort = Sort(sf)
        elif sort_field_form == "score":
            sf = SortField("score", SortField.Type.INT, is_reverse)
            lucene_sort = Sort(sf)
        elif sort_field_form == "num_comments":
            sf = SortField("num_comments", SortField.Type.INT, is_reverse)
            lucene_sort = Sort(sf)
        elif sort_field_form == "relevance":
            lucene_sort = Sort.RELEVANCE
        else:
            lucene_sort = Sort.RELEVANCE

        if lucene_sort:
            print(f"Applying sort: {lucene_sort}")
            score_docs = searcher.search(final_query, 10, lucene_sort).scoreDocs
        else:
            score_docs = searcher.search(final_query, 10).scoreDocs

        count = len(score_docs)
        print(f"{count} total matching posts found.")

        for score_doc in score_docs:
            doc = searcher.storedFields().document(score_doc.doc)
            results.append(document_to_json_serializable(doc))

    except Exception as e:
        print(f"Search error: {e}")
        import traceback

        traceback.print_exc()
        error_message = f"An error occurred during the search: {e}"

    return render_template(
        "results.html",
        query=query_string,
        results=results,
        count=count,
        error=error_message,
        sort_field=sort_field_form,
        sort_order=sort_order_form,
        type_field=type_field_form,
    )


@app.route("/post/<post_id>")
def post_detail_view(post_id):
    global searcher, analyzer, vm_env
    if not searcher or not analyzer:
        return "Lucene not initialized.", 500
    if vm_env and not vm_env.isCurrentThreadAttached():
        vm_env.attachCurrentThread()

    post_data = None
    comments_data = []
    error_message = None

    try:
        post_id_term = Term("post_id", post_id)
        type_post_term = Term("type", "post")

        post_query_builder = BooleanQuery.Builder()
        post_query_builder.add(TermQuery(post_id_term), BooleanClause.Occur.MUST)
        post_query_builder.add(TermQuery(type_post_term), BooleanClause.Occur.MUST)
        post_query = post_query_builder.build()

        top_docs_post = searcher.search(post_query, 1)
        if top_docs_post.scoreDocs:
            doc = searcher.storedFields().document(top_docs_post.scoreDocs[0].doc)
            post_data = document_to_json_serializable(doc)
        else:
            error_message = f"Post with ID '{post_id}' not found."
            return render_template(
                "post_detail.html", post=None, comments=[], error=error_message
            )

        type_comment_term = Term("type", "comment")
        comments_query_builder = BooleanQuery.Builder()
        comments_query_builder.add(TermQuery(post_id_term), BooleanClause.Occur.MUST)
        comments_query_builder.add(
            TermQuery(type_comment_term), BooleanClause.Occur.MUST
        )
        comments_query = comments_query_builder.build()

        comment_sort = Sort(
            SortField("timestamp", SortField.Type.STRING, False)
        )  # False for asc (oldest first)
        top_docs_comments = searcher.search(comments_query, 100, comment_sort)

        for score_doc in top_docs_comments.scoreDocs:
            comment_doc = searcher.storedFields().document(score_doc.doc)
            comments_data.append(document_to_json_serializable(comment_doc))

    except Exception as e:
        print(f"Error fetching post/comments for {post_id}: {e}")
        error_message = f"An error occurred while fetching post details: {e}"

    return render_template(
        "post_detail.html", post=post_data, comments=comments_data, error=error_message
    )


if __name__ == "__main__":
    initialize_lucene()
    if searcher and analyzer:
        app.run(debug=True)
        del searcher
    else:
        print("Failed to initialize Lucene. Flask app will not start.")

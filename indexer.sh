#!/bin/bash

if [ -z "$1" ]; then
  echo "Error: No input data directory provided."
  echo "Usage: ./indexer.sh <path-to-your-data-directory>"
  exit 1
fi

DATA_DIR="$1"

echo "--- Step 1: Running the indexer on directory: '$DATA_DIR' ---"
echo ""

python index.py "$DATA_DIR"

if [ $? -ne 0 ]; then
  echo ""
  echo "--- Indexing failed. Please check the output above. Aborting. ---"
  exit 1
fi

echo ""
echo "--- Indexing complete. ---"
echo ""
echo "--- Step 2: Starting the Flask web application ---"
echo "You can access the application at http://127.0.0.1:5000"
echo "Press CTRL+C to stop the server."
echo ""

# --- Run the Flask app ---
python3 app.py

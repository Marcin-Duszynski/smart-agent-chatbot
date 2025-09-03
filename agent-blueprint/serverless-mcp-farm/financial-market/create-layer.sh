#!/bin/bash

LAYER_NAME="pandas-yfinance-layer"
REGION="us-west-2"

echo "Creating pandas + yfinance Lambda Layer..."

# Create temporary directory
mkdir -p layer-build/python
cd layer-build

# Install dependencies to python/ directory (Lambda Layer structure)
pip install pandas yfinance numpy -t python/ --platform linux --python-version 3.13 --only-binary=:all:

# Create layer zip
zip -r ../pandas-yfinance-layer.zip python/

cd ..
rm -rf layer-build

# Upload to AWS Lambda Layer
aws lambda publish-layer-version \
    --layer-name $LAYER_NAME \
    --zip-file fileb://pandas-yfinance-layer.zip \
    --compatible-runtimes python3.13 \
    --region $REGION

echo "Layer created. Check AWS Console for ARN."
rm pandas-yfinance-layer.zip
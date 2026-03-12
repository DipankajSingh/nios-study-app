#!/bin/bash
# Upload NIOS PDF extraction notebook to Kaggle
# Make sure you have regenerated your API key with full permissions first

cd /home/dipankaj/Desktop/nios-study-app/pipeline/02_extract
source /home/dipankaj/Desktop/nios-study-app/.venv/bin/activate

echo "Uploading notebook to Kaggle..."
kaggle kernels push

if [ $? -eq 0 ]; then
    echo "✅ Successfully uploaded to Kaggle!"
    echo "🔗 View at: https://www.kaggle.com/code/dipankaj/nios-pdf-extraction"
else
    echo "❌ Upload failed. Check your API key permissions."
fi
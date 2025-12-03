#!/bin/bash
# GCS Test Configuration
export GCS_BUCKET="your-test-bucket"
export GCS_OBJECT_PATH="orgdata/comprehensive_index_dump.json"
export GCS_PROJECT_ID="your-project-id"

# Option 1: Use service account file
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account.json"

# Option 2: Use service account JSON directly (alternative to above)
# export GCS_CREDENTIALS_JSON='{"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}'

echo "GCS environment variables set for testing"
echo "GCS_BUCKET: $GCS_BUCKET"
echo "GCS_OBJECT_PATH: $GCS_OBJECT_PATH"
echo "GCS_PROJECT_ID: $GCS_PROJECT_ID"
echo "GOOGLE_APPLICATION_CREDENTIALS: $GOOGLE_APPLICATION_CREDENTIALS"



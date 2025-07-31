######THIS IS AN EXAMPLE - I DO NOT HAVE MY GCP PROJECT ID'S HERE 

# Fantasy Football Neuron - GCP Setup Script
# This script sets up all required GCP resources

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_ACCOUNT_NAME="ffn-service-account"
BUCKET_NAME="${PROJECT_ID}-ffn-audio-cache"

echo "🚀 Setting up Fantasy Football Neuron on GCP"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "📡 Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  storage.googleapis.com \
  redis.googleapis.com

# Create service account
echo "👤 Creating service account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="Fantasy Football Neuron Service Account" \
  --description="Service account for FFN application" \
  || echo "Service account already exists"

# Grant necessary permissions
echo "🔐 Granting IAM permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# Create Artifact Registry repository
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create ffn-docker \
  --repository-format=docker \
  --location=$REGION \
  --description="Docker images for Fantasy Football Neuron" \
  || echo "Repository already exists"

# Create Cloud Storage bucket for audio cache
echo "🗄️ Creating Cloud Storage bucket..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$BUCKET_NAME/ \
  || echo "Bucket already exists"

# Set bucket lifecycle rules for cost optimization
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 30,
          "matchesPrefix": ["audio-cache/"]
        }
      },
      {
        "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
        "condition": {
          "age": 7,
          "matchesPrefix": ["audio-cache/"]
        }
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://$BUCKET_NAME/
rm lifecycle.json

# Create secrets in Secret Manager
echo "🔑 Setting up Secret Manager..."
echo "Please enter your API keys:"

read -p "ElevenLabs API Key: " ELEVENLABS_KEY
echo -n "$ELEVENLABS_KEY" | gcloud secrets create elevenlabs-api-key \
  --data-file=- \
  --replication-policy="automatic" \
  || echo "Secret already exists"

read -p "OpenAI API Key: " OPENAI_KEY
echo -n "$OPENAI_KEY" | gcloud secrets create openai-api-key \
  --data-file=- \
  --replication-policy="automatic" \
  || echo "Secret already exists"

read -p "Upstash Redis URL: " UPSTASH_URL
echo -n "$UPSTASH_URL" | gcloud secrets create upstash-redis-url \
  --data-file=- \
  --replication-policy="automatic" \
  || echo "Secret already exists"

read -p "Upstash Redis Token: " UPSTASH_TOKEN
echo -n "$UPSTASH_TOKEN" | gcloud secrets create upstash-redis-token \
  --data-file=- \
  --replication-policy="automatic" \
  || echo "Secret already exists"

# Build and deploy the application
echo "🔨 Building Docker image..."
gcloud builds submit --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/ffn-docker/fantasy-football-neuron-api:latest .

echo "🚀 Deploying to Cloud Run..."
gcloud run deploy fantasy-football-neuron-api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/ffn-docker/fantasy-football-neuron-api:latest \
  --platform managed \
  --region $REGION \
  --service-account ${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 100 \
  --memory 4Gi \
  --cpu 2 \
  --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},VERTEX_AI_LOCATION=${REGION},GCS_BUCKET_NAME=${BUCKET_NAME}" \
  --set-secrets "ELEVENLABS_API_KEY=elevenlabs-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,UPSTASH_REDIS_URL=upstash-redis-url:latest,UPSTASH_REDIS_TOKEN=upstash-redis-token:latest"

# Get the service URL
SERVICE_URL=$(gcloud run services describe fantasy-football-neuron-api --region $REGION --format 'value(status.url)')

echo "✅ Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "1. Update your frontend to use the service URL: $SERVICE_URL"
echo "2. Set up Cloud CDN for the frontend"
echo "3. Configure a custom domain"
echo "4. Set up monitoring and alerts"

# Optional: Set up budget alert
echo ""
read -p "Would you like to set up a budget alert? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
  echo "Creating budget alert for $250/month..."
  # This would require additional setup with Cloud Billing API
  echo "Please set up budget alerts manually in the Cloud Console:"
  echo "https://console.cloud.google.com/billing/budgets"
fi

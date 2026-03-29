# Deployment Guide

Deploy Agentic Brain to production with one click or one command.

<div align="center">

## 🚀 One-Click Deploy

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/agentic-brain-project/agentic-brain)
[![Deploy to Railway](https://railway.app/button.svg)](https://railway.app/template/agentic-brain?referralCode=agentic)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/agentic-brain-project/agentic-brain)
[![Deploy to Fly.io](https://img.shields.io/badge/Deploy%20to-Fly.io-7B3F00?style=for-the-badge&logo=fly.io&logoColor=white)](https://fly.io/launch?repo=https://github.com/agentic-brain-project/agentic-brain)
[![Deploy to DigitalOcean](https://img.shields.io/badge/Deploy%20to-DigitalOcean-0080FF?style=for-the-badge&logo=digitalocean&logoColor=white)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/agentic-brain-project/agentic-brain)

</div>

---

## ☁️ Cloud Platforms

| Platform | Method | Deploy Time | Difficulty |
|----------|--------|-------------|------------|
| [Heroku](#heroku) | One-click | 3 min | ⭐ Easy |
| [Railway](#railway) | One-click | 2 min | ⭐ Easy |
| [Render](#render) | One-click | 5 min | ⭐ Easy |
| [Fly.io](#flyio) | CLI | 5 min | ⭐⭐ Medium |
| [DigitalOcean](#digitalocean-app-platform) | Template | 10 min | ⭐⭐ Medium |
| [Azure](#microsoft-azure) | Container Apps/AKS | 15 min | ⭐⭐⭐ Advanced |
| [Google Cloud](#google-cloud) | Cloud Run/GKE | 10 min | ⭐⭐⭐ Advanced |
| [AWS](#amazon-web-services) | ECS/EKS/Lambda | 20 min | ⭐⭐⭐ Advanced |

---

## 💰 Cost Estimates (2026)

Approximate entry-level costs for a small always-on deployment (see provider pricing for up-to-date details):

| Platform | Free Tier / Credits | Typical Small Paid Tier (USD/mo) |
|----------|---------------------|-----------------------------------|
| AWS Fargate | No always-free compute | ~30+/vCPU + RAM |
| Google Cloud Run | Generous free requests | ~50+/vCPU + RAM |
| Azure Container Apps | Generous free requests | ~60+/vCPU + RAM |
| Heroku | Eco/limited dynos | $5+ |
| Railway | $5 credit/month | $5–25+ |
| Render | Free sleeping tier | $7–19+ |
| Fly.io | Small free VMs | $2–7+ |
| DigitalOcean App Platform | $100/60 day credit | $5–7+ |

These are indicative only; always confirm in each provider's calculator.

---

## Quick Start (Docker)

```bash
# Clone and deploy
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain

# Set password
export NEO4J_PASSWORD=your_secure_password

# Deploy
docker-compose up -d
```

API available at `http://localhost:8000`

---

## 🟣 Heroku

### One-Click Deploy

Click the button above or:

```bash
# Using Heroku CLI
heroku create my-agentic-brain
heroku addons:create heroku-redis:mini
heroku addons:create graphenedb:dev-free  # Neo4j addon

git push heroku main
```

### app.json (included)

```json
{
  "name": "Agentic Brain",
  "description": "AI Agent Framework with GraphRAG",
  "repository": "https://github.com/agentic-brain-project/agentic-brain",
  "logo": "https://raw.githubusercontent.com/agentic-brain-project/agentic-brain/main/docs/assets/brain-logo.png",
  "keywords": ["ai", "agents", "graphrag", "python"],
  "addons": [
    "heroku-redis:mini"
  ],
  "env": {
    "NEO4J_PASSWORD": {
      "description": "Neo4j database password",
      "generator": "secret"
    },
    "JWT_SECRET": {
      "description": "Secret for JWT tokens",
      "generator": "secret"
    },
    "AUTH_ENABLED": {
      "description": "Enable authentication",
      "value": "true"
    }
  },
  "buildpacks": [
    {"url": "heroku/python"}
  ]
}
```

### Procfile

```
web: uvicorn agentic_brain.server:app --host 0.0.0.0 --port $PORT
worker: python -m agentic_brain.worker
```

---

## 🚂 Railway

### One-Click Deploy

Click the Railway button above, or:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### railway.json

```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "./Dockerfile"
  },
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  },
  "services": [
    {
      "name": "agentic-brain",
      "internalPort": 8000
    },
    {
      "name": "neo4j",
      "image": "neo4j:5-community",
      "internalPort": 7687,
      "volumes": ["/var/lib/neo4j/data"]
    },
    {
      "name": "redis",
      "image": "redis:7-alpine",
      "internalPort": 6379
    }
  ]
}
```

---

## 🎨 Render

### One-Click Deploy

Click the Render button above, or use:

### render.yaml (Blueprint)

```yaml
services:
  - type: web
    name: agentic-brain
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerContext: .
    healthCheckPath: /health
    envVars:
      - key: NEO4J_URI
        fromService:
          type: pserv
          name: neo4j
          property: connectionString
      - key: NEO4J_PASSWORD
        generateValue: true
      - key: REDIS_URL
        fromService:
          type: redis
          name: redis
          property: connectionString
      - key: JWT_SECRET
        generateValue: true
    autoDeploy: true

  - type: pserv
    name: neo4j
    runtime: docker
    dockerCommand: neo4j
    disk:
      name: neo4j-data
      mountPath: /var/lib/neo4j/data
      sizeGB: 10

  - type: redis
    name: redis
    ipAllowList: []
    plan: starter
```

---

## 🦋 Fly.io

### Quick Deploy

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Launch (creates fly.toml automatically)
fly launch --name my-agentic-brain

# Deploy
fly deploy
```

### fly.toml

```toml
app = "agentic-brain"
primary_region = "syd"  # Sydney for Australia

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1
  processes = ["app"]

[[services]]
  internal_port = 8000
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

  [[services.http_checks]]
    interval = "15s"
    timeout = "5s"
    path = "/health"
    method = "GET"

[env]
  SESSION_BACKEND = "redis"
  LOG_LEVEL = "INFO"

[[vm]]
  cpu_kind = "shared"
  cpus = 2
  memory_mb = 1024
```

### Attach Services

```bash
# Create Redis
fly redis create --name agentic-brain-redis

# Create volume for Neo4j
fly volumes create neo4j_data --size 10 --region syd

# Set secrets
fly secrets set NEO4J_PASSWORD=your_secure_password
fly secrets set JWT_SECRET=$(openssl rand -hex 32)
```

---

## 🔷 DigitalOcean App Platform

### Deploy via Dashboard

1. Go to [DigitalOcean App Platform](https://cloud.digitalocean.com/apps)
2. Click "Create App" → "GitHub"
3. Select the repository
4. Configure resources

### app.yaml (Spec)

```yaml
name: agentic-brain
region: syd  # Sydney

services:
  - name: api
    dockerfile_path: Dockerfile
    github:
      repo: agentic-brain-project/agentic-brain
      branch: main
      deploy_on_push: true
    http_port: 8000
    instance_count: 2
    instance_size_slug: basic-s
    health_check:
      http_path: /health
    envs:
      - key: NEO4J_URI
        scope: RUN_TIME
        value: ${neo4j.DATABASE_URL}
      - key: REDIS_URL
        scope: RUN_TIME
        value: ${redis.DATABASE_URL}
      - key: JWT_SECRET
        scope: RUN_TIME
        type: SECRET

databases:
  - name: redis
    engine: REDIS
    production: true
    cluster_name: agentic-brain-redis

  - name: neo4j
    engine: MONGODB  # Use managed graph or external Neo4j
    production: true
```

### CLI Deployment

```bash
# Install doctl
brew install doctl

# Authenticate
doctl auth init

# Deploy
doctl apps create --spec .do/app.yaml
```

---

## 🔵 Microsoft Azure

### Option 1: Azure Container Apps (Recommended)

```bash
# Login
az login

# Create resource group
az group create --name agentic-brain-rg --location australiaeast

# Create Container Apps environment
az containerapp env create \
  --name agentic-brain-env \
  --resource-group agentic-brain-rg \
  --location australiaeast

# Deploy
az containerapp create \
  --name agentic-brain \
  --resource-group agentic-brain-rg \
  --environment agentic-brain-env \
  --image ghcr.io/agentic-brain-project/agentic-brain:latest \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 10 \
  --env-vars \
    NEO4J_URI=bolt://neo4j:7687 \
    NEO4J_PASSWORD=secretref:neo4j-password \
    SESSION_BACKEND=redis
```

### Option 2: Azure Kubernetes Service (AKS)

```bash
# Create AKS cluster
az aks create \
  --resource-group agentic-brain-rg \
  --name agentic-brain-aks \
  --node-count 3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group agentic-brain-rg --name agentic-brain-aks

# Deploy with Helm
helm install agentic-brain ./helm/agentic-brain \
  --namespace agentic-brain --create-namespace
```

### Option 3: Azure App Service

```bash
# Create App Service plan
az appservice plan create \
  --name agentic-brain-plan \
  --resource-group agentic-brain-rg \
  --sku B2 \
  --is-linux

# Create web app
az webapp create \
  --name agentic-brain \
  --resource-group agentic-brain-rg \
  --plan agentic-brain-plan \
  --deployment-container-image-name ghcr.io/agentic-brain-project/agentic-brain:latest

# Configure
az webapp config appsettings set \
  --name agentic-brain \
  --resource-group agentic-brain-rg \
  --settings NEO4J_URI=bolt://neo4j:7687
```

### Azure Bicep Template

```bicep
// main.bicep
param location string = 'australiaeast'
param appName string = 'agentic-brain'

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: appName
  location: location
  properties: {
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
    }
    template: {
      containers: [
        {
          name: appName
          image: 'ghcr.io/agentic-brain-project/agentic-brain:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 10
      }
    }
  }
}
```

---

## 🟡 Google Cloud

### Option 1: Cloud Run (Recommended)

```bash
# Login
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable services
gcloud services enable run.googleapis.com containerregistry.googleapis.com

# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/agentic-brain

# Deploy
gcloud run deploy agentic-brain \
  --image gcr.io/YOUR_PROJECT_ID/agentic-brain \
  --platform managed \
  --region australia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars "NEO4J_URI=bolt://neo4j:7687" \
  --min-instances 1 \
  --max-instances 10 \
  --memory 1Gi \
  --cpu 2
```

### Option 2: Google Kubernetes Engine (GKE)

```bash
# Create cluster
gcloud container clusters create agentic-brain-cluster \
  --zone australia-southeast1-a \
  --num-nodes 3 \
  --machine-type e2-medium \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials agentic-brain-cluster \
  --zone australia-southeast1-a

# Deploy
kubectl apply -k k8s/overlays/prod
```

### Option 3: Compute Engine (VM)

```bash
# Create VM
gcloud compute instances create agentic-brain-vm \
  --zone australia-southeast1-a \
  --machine-type e2-medium \
  --image-family ubuntu-2204-lts \
  --image-project ubuntu-os-cloud \
  --tags http-server,https-server

# SSH and install
gcloud compute ssh agentic-brain-vm --zone australia-southeast1-a

# On the VM:
curl -fsSL https://get.docker.com | sh
git clone https://github.com/agentic-brain-project/agentic-brain.git
cd agentic-brain
docker-compose up -d
```

### cloudbuild.yaml

```yaml
steps:
  # Build
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/agentic-brain:$COMMIT_SHA', '.']
  
  # Push
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/agentic-brain:$COMMIT_SHA']
  
  # Deploy
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'agentic-brain'
      - '--image'
      - 'gcr.io/$PROJECT_ID/agentic-brain:$COMMIT_SHA'
      - '--region'
      - 'australia-southeast1'

images:
  - 'gcr.io/$PROJECT_ID/agentic-brain:$COMMIT_SHA'
```

---

## 🟠 Amazon Web Services

### Option 1: ECS Fargate (Recommended)

```bash
# Create cluster
aws ecs create-cluster --cluster-name agentic-brain-cluster

# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
  --cluster agentic-brain-cluster \
  --service-name agentic-brain-service \
  --task-definition agentic-brain \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### ecs-task-definition.json

```json
{
  "family": "agentic-brain",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "agentic-brain",
      "image": "ghcr.io/agentic-brain-project/agentic-brain:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "NEO4J_URI", "value": "bolt://neo4j:7687"},
        {"name": "SESSION_BACKEND", "value": "redis"}
      ],
      "secrets": [
        {
          "name": "NEO4J_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:neo4j-password"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agentic-brain",
          "awslogs-region": "ap-southeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

### Option 2: EKS (Kubernetes)

```bash
# Create cluster with eksctl
eksctl create cluster \
  --name agentic-brain \
  --region ap-southeast-2 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 1 \
  --nodes-max 5

# Deploy
kubectl apply -k k8s/overlays/prod
```

### Option 3: Lambda (Serverless)

```python
# lambda_handler.py
from mangum import Mangum
from agentic_brain.server import app

handler = Mangum(app)
```

```yaml
# serverless.yml
service: agentic-brain

provider:
  name: aws
  runtime: python3.11
  region: ap-southeast-2
  memorySize: 1024
  timeout: 30

functions:
  api:
    handler: lambda_handler.handler
    events:
      - http:
          path: /{proxy+}
          method: ANY
    environment:
      NEO4J_URI: ${env:NEO4J_URI}
      NEO4J_PASSWORD: ${env:NEO4J_PASSWORD}

plugins:
  - serverless-python-requirements
```

### CloudFormation Template

```yaml
# cloudformation.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Agentic Brain on AWS

Parameters:
  Neo4jPassword:
    Type: String
    NoEcho: true

Resources:
  ECSCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: agentic-brain-cluster

  TaskDefinition:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: agentic-brain
      Cpu: '512'
      Memory: '1024'
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      ContainerDefinitions:
        - Name: agentic-brain
          Image: ghcr.io/agentic-brain-project/agentic-brain:latest
          PortMappings:
            - ContainerPort: 8000

  Service:
    Type: AWS::ECS::Service
    Properties:
      Cluster: !Ref ECSCluster
      DesiredCount: 2
      LaunchType: FARGATE
      TaskDefinition: !Ref TaskDefinition

Outputs:
  ClusterArn:
    Value: !GetAtt ECSCluster.Arn
```

---

## 📦 Infrastructure as Code Templates

### Terraform

```hcl
# main.tf
terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    google = { source = "hashicorp/google", version = "~> 5.0" }
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
  }
}

# AWS ECS
module "aws_ecs" {
  source = "./modules/aws-ecs"
  count  = var.cloud_provider == "aws" ? 1 : 0
  
  app_name       = "agentic-brain"
  image          = "ghcr.io/agentic-brain-project/agentic-brain:latest"
  cpu            = 512
  memory         = 1024
  desired_count  = 2
  neo4j_password = var.neo4j_password
}

# Google Cloud Run
module "gcp_cloudrun" {
  source = "./modules/gcp-cloudrun"
  count  = var.cloud_provider == "gcp" ? 1 : 0
  
  app_name       = "agentic-brain"
  image          = "gcr.io/${var.gcp_project}/agentic-brain:latest"
  region         = "australia-southeast1"
  min_instances  = 1
  max_instances  = 10
}

# Azure Container Apps
module "azure_aca" {
  source = "./modules/azure-aca"
  count  = var.cloud_provider == "azure" ? 1 : 0
  
  app_name       = "agentic-brain"
  image          = "ghcr.io/agentic-brain-project/agentic-brain:latest"
  location       = "australiaeast"
  min_replicas   = 1
  max_replicas   = 10
}

variable "cloud_provider" {
  description = "Cloud provider: aws, gcp, or azure"
  type        = string
}

variable "neo4j_password" {
  description = "Neo4j password"
  type        = string
  sensitive   = true
}
```

### JHipster-Style Deployment Layout

Terraform and Kubernetes templates are provided in the repository:

- `deployment/aws/` – AWS ECS/Fargate Terraform
- `deployment/gcp/` – Google Cloud Run Terraform
- `deployment/azure/` – Azure Container Apps Terraform
- `deployment/kubernetes/` – K8s Deployment/Service/Ingress
- `deployment/helm/agentic-brain/` – Helm chart (also available via `./helm/agentic-brain` symlink)

### Pulumi (TypeScript)

```typescript
// index.ts
import * as pulumi from "@pulumi/pulumi";
import * as gcp from "@pulumi/gcp";
import * as docker from "@pulumi/docker";

const config = new pulumi.Config();

// Build and push image
const image = new docker.Image("agentic-brain", {
    imageName: pulumi.interpolate`gcr.io/${gcp.config.project}/agentic-brain:latest`,
    build: {
        context: "../",
        dockerfile: "../Dockerfile",
    },
});

// Deploy to Cloud Run
const service = new gcp.cloudrun.Service("agentic-brain", {
    location: "australia-southeast1",
    template: {
        spec: {
            containers: [{
                image: image.imageName,
                ports: [{ containerPort: 8000 }],
                envs: [
                    { name: "NEO4J_URI", value: config.require("neo4jUri") },
                    { name: "NEO4J_PASSWORD", value: config.requireSecret("neo4jPassword") },
                ],
                resources: {
                    limits: { memory: "1Gi", cpu: "2" },
                },
            }],
        },
        metadata: {
            annotations: {
                "autoscaling.knative.dev/minScale": "1",
                "autoscaling.knative.dev/maxScale": "10",
            },
        },
    },
});

// Make publicly accessible
const iamMember = new gcp.cloudrun.IamMember("public", {
    service: service.name,
    location: service.location,
    role: "roles/run.invoker",
    member: "allUsers",
});

export const url = service.statuses[0].url;
```

---

## 🐳 Docker Compose Templates

### Production Template

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.le.acme.tlschallenge=true"
      - "--certificatesresolvers.le.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.le.acme.storage=/letsencrypt/acme.json"
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    networks:
      - agentic-network

  agentic-brain:
    image: ghcr.io/agentic-brain-project/agentic-brain:${VERSION:-latest}
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: '1'
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`${DOMAIN}`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=le"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - REDIS_URL=redis://redis:6379
      - SESSION_BACKEND=redis
      - AUTH_ENABLED=true
      - JWT_SECRET=${JWT_SECRET}
    depends_on:
      - neo4j
      - redis
    networks:
      - agentic-network

  neo4j:
    image: neo4j:5-enterprise
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
    volumes:
      - neo4j_data:/var/lib/neo4j/data
    networks:
      - agentic-network

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - agentic-network

volumes:
  neo4j_data:
  redis_data:
  letsencrypt:

networks:
  agentic-network:
    driver: overlay
```

### Development Template

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  agentic-brain:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/.venv  # Exclude venv
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_PASSWORD=devpassword
      - DEBUG=true
      - LOG_LEVEL=DEBUG
    command: uvicorn agentic_brain.server:app --host 0.0.0.0 --port 8000 --reload

  neo4j:
    image: neo4j:5-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/devpassword
```

---

## Docker Deployment

### Single Container

```bash
# Build image
docker build -t agentic-brain .

# Run with Neo4j
docker run -d \
  --name neo4j \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:5-community

docker run -d \
  --name agentic-brain \
  -p 8000:8000 \
  -e NEO4J_URI=bolt://host.docker.internal:7687 \
  -e NEO4J_PASSWORD=password \
  agentic-brain
```

### Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5-community
    container_name: agentic-brain-neo4j
    restart: unless-stopped
    ports:
      - "7687:7687"
      - "7474:7474"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeme}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_server_memory_heap_initial_size=512m
      - NEO4J_server_memory_heap_max_size=1g
    volumes:
      - neo4j_data:/var/lib/neo4j/data
    networks:
      - agentic-network
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD:-changeme}", "RETURN 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  redis:
    image: redis:7-alpine
    container_name: agentic-brain-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - agentic-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  agentic-brain:
    build: .
    container_name: agentic-brain-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-changeme}
      - SESSION_BACKEND=redis
      - REDIS_URL=redis://redis:6379
      - AUTH_ENABLED=${AUTH_ENABLED:-false}
      - API_KEYS=${API_KEYS:-}
      - JWT_SECRET=${JWT_SECRET:-}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    networks:
      - agentic-network
    depends_on:
      neo4j:
        condition: service_healthy
      redis:
        condition: service_healthy
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  neo4j_data:
  redis_data:

networks:
  agentic-network:
    driver: bridge
```

**Deploy:**

```bash
# Create .env file
cat > .env << EOF
NEO4J_PASSWORD=your_secure_password_here
AUTH_ENABLED=true
API_KEYS=your-api-key-1,your-api-key-2
JWT_SECRET=$(openssl rand -hex 32)
LOG_LEVEL=INFO
EOF

# Deploy
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f agentic-brain
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEO4J_URI` | Yes | - | Neo4j connection URI |
| `NEO4J_USER` | Yes | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | Yes | - | Neo4j password |
| `SESSION_BACKEND` | No | `memory` | `memory` or `redis` |
| `REDIS_URL` | If redis | - | Redis connection URL |
| `AUTH_ENABLED` | No | `false` | Enable authentication |
| `API_KEYS` | If auth | - | Comma-separated API keys |
| `JWT_SECRET` | If JWT | - | JWT signing secret |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `API_HOST` | No | `0.0.0.0` | Bind address |
| `API_PORT` | No | `8000` | Bind port |

See [configuration.md](./configuration.md) for all options.

---

## Health Checks

### API Health

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-20T10:30:45+00:00",
  "sessions_active": 5
}
```

### Docker Health Check

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Kubernetes Probes

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

---

## Redis Setup

For multi-instance deployments, use Redis for session storage:

```bash
# Enable Redis backend
SESSION_BACKEND=redis
REDIS_URL=redis://localhost:6379
```

### Redis Configuration

```yaml
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
appendonly yes
```

### Redis Cluster

For high availability:

```bash
REDIS_URL=redis://redis-master:6379,redis-slave-1:6379,redis-slave-2:6379
```

---

## Scaling

### Horizontal Scaling

With Redis session backend, run multiple API instances:

```yaml
# docker-compose.yml
services:
  agentic-brain:
    deploy:
      replicas: 3
```

### Load Balancer

Use nginx or Traefik:

```nginx
upstream agentic_brain {
    least_conn;
    server agentic-brain-1:8000;
    server agentic-brain-2:8000;
    server agentic-brain-3:8000;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://agentic_brain;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### WebSocket Scaling

For WebSocket, ensure sticky sessions or use Redis pub/sub:

```nginx
upstream agentic_brain_ws {
    ip_hash;  # Sticky sessions
    server agentic-brain-1:8000;
    server agentic-brain-2:8000;
}
```

---

## SSL/TLS

### With Reverse Proxy (Recommended)

Use nginx or Traefik for TLS termination:

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://agentic-brain:8000;
    }
}
```

### With Docker + Traefik

```yaml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.le.acme.tlschallenge=true"
      - "--certificatesresolvers.le.acme.email=admin@example.com"
      - "--certificatesresolvers.le.acme.storage=/letsencrypt/acme.json"
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - letsencrypt:/letsencrypt

  agentic-brain:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.example.com`)"
      - "traefik.http.routers.api.entrypoints=websecure"
      - "traefik.http.routers.api.tls.certresolver=le"
```

---

## Logging

### Container Logs

```bash
# View logs
docker-compose logs -f agentic-brain

# Tail last 100 lines
docker-compose logs --tail=100 agentic-brain
```

### Log Aggregation

For production, ship logs to a central system:

```yaml
services:
  agentic-brain:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Or use Fluentd/Logstash:

```yaml
logging:
  driver: fluentd
  options:
    fluentd-address: localhost:24224
    tag: agentic-brain
```

---

## Monitoring

### Prometheus Metrics

Expose metrics endpoint:

```python
# Custom metrics (future feature)
from prometheus_client import Counter, Histogram

CHAT_REQUESTS = Counter('chat_requests_total', 'Total chat requests')
CHAT_LATENCY = Histogram('chat_latency_seconds', 'Chat request latency')
```

### Grafana Dashboard

Monitor:
- Request rate
- Response latency
- Error rate
- Active sessions
- Neo4j query times

---

## Backup & Recovery

### Neo4j Backup

```bash
# Stop Neo4j
docker-compose stop neo4j

# Backup data volume
docker run --rm \
  -v agentic_brain_neo4j_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/neo4j-backup-$(date +%Y%m%d).tar.gz /data

# Start Neo4j
docker-compose start neo4j
```

### Automated Backups

```bash
# crontab -e
0 2 * * * /opt/agentic-brain/scripts/backup.sh
```

---

## Production Checklist

- [ ] **Security**
  - [ ] `AUTH_ENABLED=true`
  - [ ] Strong passwords and API keys
  - [ ] TLS enabled
  - [ ] Firewall configured

- [ ] **Reliability**
  - [ ] Health checks configured
  - [ ] Restart policies set
  - [ ] Backups automated
  - [ ] Monitoring enabled

- [ ] **Performance**
  - [ ] Redis session backend
  - [ ] Multiple replicas
  - [ ] Load balancer configured
  - [ ] Resource limits set

- [ ] **Observability**
  - [ ] Log aggregation
  - [ ] Metrics collection
  - [ ] Alerting configured
  - [ ] Audit logging enabled

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs agentic-brain

# Check Neo4j is healthy
docker-compose exec neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

### Connection Refused

```bash
# Check network
docker-compose exec agentic-brain ping neo4j

# Check ports
docker-compose port agentic-brain 8000
```

### Out of Memory

```yaml
services:
  agentic-brain:
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

---

## Kubernetes Deployment

For production Kubernetes deployments, we provide both Kustomize and Helm options.

### Quick Start with Helm

```bash
# Install with Helm
helm install agentic-brain ./helm/agentic-brain \
  --namespace agentic-brain \
  --create-namespace \
  --set neo4j.password=your_secure_password \
  --set auth.jwtSecret=$(openssl rand -hex 32)

# Check status
kubectl get pods -n agentic-brain

# Upgrade
helm upgrade agentic-brain ./helm/agentic-brain \
  --set image.tag=v1.1.0
```

### Quick Start with Kustomize

```bash
# Development
kubectl apply -k k8s/overlays/dev

# Production
kubectl apply -k k8s/overlays/prod
```

### What's Included

| Component | Description |
|-----------|-------------|
| **Deployment** | 3 replicas, rolling updates, resource limits |
| **Service** | ClusterIP on port 8000 |
| **Ingress** | Nginx ingress with TLS |
| **HPA** | Autoscale 3-10 replicas at 70% CPU |
| **PDB** | Minimum 2 pods available |
| **ConfigMap** | Non-sensitive configuration |
| **Secrets** | Template for sensitive data |

### Scaling

```bash
# Manual scaling
kubectl scale deployment agentic-brain --replicas=5

# HPA handles automatic scaling based on CPU/memory
kubectl get hpa agentic-brain
```

### Resource Guidelines

| Environment | Replicas | Memory | CPU |
|-------------|----------|--------|-----|
| Development | 1 | 128-256Mi | 50-250m |
| Staging | 2 | 256-512Mi | 100-500m |
| Production | 3-10 | 512Mi-1Gi | 250m-1000m |

### Cloud-Agnostic

Works on any Kubernetes cluster:
- **GKE** (Google Kubernetes Engine)
- **EKS** (Amazon Elastic Kubernetes Service)
- **AKS** (Azure Kubernetes Service)
- **k3s** (Lightweight Kubernetes)
- **minikube** (Local development)

See [k8s/README.md](../k8s/README.md) for full documentation.

---

## See Also

- [k8s/README.md](../k8s/README.md) — Full Kubernetes deployment guide
- [configuration.md](./configuration.md) — All configuration options
- [SECURITY.md](./SECURITY.md) — Security best practices
- [AUTHENTICATION.md](./AUTHENTICATION.md) — Auth setup

---

**Last Updated**: 2026-03-20

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

variable "project" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "australia-southeast1"
}

variable "app_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "agentic-brain"
}

variable "image" {
  description = "Container image to deploy (gcr.io/... or artifact registry)"
  type        = string
}

resource "google_cloud_run_service" "this" {
  name     = var.app_name
  location = var.region

  template {
    spec {
      containers {
        image = var.image
        ports {
          container_port = 8000
        }
        env {
          name  = "NEO4J_URI"
          value = "bolt://neo4j:7687"
        }
        env {
          name  = "SESSION_BACKEND"
          value = "redis"
        }
      }
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "10"
      }
    }
  }

  traffic {
    percent         = 100
    latest_revision = true
  }
}

resource "google_cloud_run_service_iam_member" "public" {
  location = google_cloud_run_service.this.location
  project  = var.project
  service  = google_cloud_run_service.this.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "url" {
  description = "Public URL of the Cloud Run service"
  value       = google_cloud_run_service.this.status[0].url
}

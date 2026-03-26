terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "location" {
  description = "Azure location"
  type        = string
  default     = "australiaeast"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = "agentic-brain-rg"
}

variable "app_name" {
  description = "Container App name"
  type        = string
  default     = "agentic-brain"
}

variable "image" {
  description = "Container image (e.g. ghcr.io/joseph-webber/agentic-brain:latest)"
  type        = string
}

variable "min_replicas" {
  description = "Minimum replicas"
  type        = number
  default     = 1
}

variable "max_replicas" {
  description = "Maximum replicas"
  type        = number
  default     = 10
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "${var.app_name}-law"
  location            = var.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_container_app_environment" "this" {
  name                       = "${var.app_name}-env"
  location                   = var.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id
}

resource "azurerm_container_app" "this" {
  name                         = var.app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"

  template {
    container {
      name   = var.app_name
      image  = var.image
      cpu    = 0.5
      memory = "1Gi"
      env {
        name  = "NEO4J_URI"
        value = "bolt://neo4j:7687"
      }
      env {
        name  = "SESSION_BACKEND"
        value = "redis"
      }
    }

    scale {
      min_replicas = var.min_replicas
      max_replicas = var.max_replicas
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8000
  }
}

output "url" {
  description = "FQDN of the Container App"
  value       = azurerm_container_app.this.latest_revision_fqdn
}

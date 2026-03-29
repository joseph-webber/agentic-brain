# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for new RAG loaders."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import yaml

from agentic_brain.rag.loaders.ansible_loader import AnsibleLoader
from agentic_brain.rag.loaders.docker_compose_loader import DockerComposeLoader
from agentic_brain.rag.loaders.github_actions_loader import GitHubActionsLoader
from agentic_brain.rag.loaders.graphql_schema_loader import GraphQLSchemaLoader
from agentic_brain.rag.loaders.jira_loader import JiraLoader
from agentic_brain.rag.loaders.kubernetes_loader import KubernetesLoader
from agentic_brain.rag.loaders.openapi_loader import OpenAPILoader
from agentic_brain.rag.loaders.protobuf_loader import ProtobufLoader
from agentic_brain.rag.loaders.sso_saml_loader import SsoSamlLoader
from agentic_brain.rag.loaders.terraform_loader import TerraformLoader


class TestNewLoaders(unittest.TestCase):

    def setUp(self):
        self.base_path = "/tmp/test"

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_file")
    def test_kubernetes_loader(self, mock_is_file, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_read.return_value = """
apiVersion: v1
kind: Service
metadata:
  name: my-service
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-deployment
"""
        loader = KubernetesLoader(self.base_path)
        doc = loader.load_document("k8s.yaml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["count"], 2)
        self.assertIn("Service", doc.metadata["kinds"])
        self.assertIn("my-deployment", doc.metadata["names"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_ansible_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
- hosts: webservers
  tasks:
    - name: Ensure apache is at the latest version
      yum:
        name: httpd
        state: latest
"""
        loader = AnsibleLoader(self.base_path)
        doc = loader.load_document("playbook.yml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["task_count"], 1)
        self.assertIn("webservers", doc.metadata["hosts"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_docker_compose_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
version: '3'
services:
  web:
    build: .
  redis:
    image: redis
"""
        loader = DockerComposeLoader(self.base_path)
        doc = loader.load_document("docker-compose.yml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["service_count"], 2)
        self.assertIn("web", doc.metadata["services"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_github_actions_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
"""
        loader = GitHubActionsLoader(self.base_path)
        doc = loader.load_document("ci.yml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["workflow_name"], "CI")
        self.assertIn("build", doc.metadata["jobs"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_openapi_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
openapi: 3.0.0
info:
  title: Sample API
  version: 0.1.9
paths:
  /users:
    get:
      summary: Returns a list of users.
"""
        loader = OpenAPILoader(self.base_path)
        doc = loader.load_document("api.yaml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["title"], "Sample API")
        self.assertEqual(doc.metadata["endpoint_count"], 1)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_terraform_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
resource "aws_instance" "web" {
  ami = "ami-12345678"
}
variable "region" {
  default = "us-east-1"
}
"""
        loader = TerraformLoader(self.base_path)
        doc = loader.load_document("main.tf")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["resource_count"], 1)
        self.assertEqual(doc.metadata["variable_count"], 1)
        self.assertIn("aws_instance.web", doc.metadata["resources"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_graphql_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
type User {
  id: ID!
  name: String
}
type Query {
  me: User
}
"""
        loader = GraphQLSchemaLoader(self.base_path)
        doc = loader.load_document("schema.graphql")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["type_count"], 2)
        self.assertIn("User", doc.metadata["types"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_protobuf_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
syntax = "proto3";
package tutorial;

message Person {
  string name = 1;
  int32 id = 2;
}
"""
        loader = ProtobufLoader(self.base_path)
        doc = loader.load_document("person.proto")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["package"], "tutorial")
        self.assertIn("Person", doc.metadata["messages"])

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.exists")
    def test_saml_loader(self, mock_exists, mock_read):
        mock_exists.return_value = True
        mock_read.return_value = """
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="https://idp.example.com">
  <md:IDPSSODescriptor>
  </md:IDPSSODescriptor>
</md:EntityDescriptor>
"""
        loader = SsoSamlLoader(self.base_path)
        doc = loader.load_document("metadata.xml")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["entity_id"], "https://idp.example.com")
        self.assertTrue(doc.metadata["is_idp"])

    @patch("agentic_brain.rag.loaders.jira_loader.Jira")
    def test_jira_loader(self, mock_jira_cls):
        mock_client = MagicMock()
        mock_jira_cls.return_value = mock_client

        mock_client.issue.return_value = {
            "key": "TEST-1",
            "fields": {
                "summary": "Test Issue",
                "description": "Description",
                "status": {"name": "Open"},
                "project": {"key": "TEST"},
                "created": "2023-01-01T12:00:00.000+0000",
                "updated": "2023-01-02T12:00:00.000+0000",
            },
        }

        loader = JiraLoader("https://jira.example.com", "user", "pass")
        # Mock authenticated
        loader._authenticated = True
        loader._client = mock_client

        doc = loader.load_document("TEST-1")

        self.assertIsNotNone(doc)
        self.assertEqual(doc.metadata["key"], "TEST-1")
        self.assertEqual(doc.metadata["summary"], "Test Issue")


if __name__ == "__main__":
    unittest.main()

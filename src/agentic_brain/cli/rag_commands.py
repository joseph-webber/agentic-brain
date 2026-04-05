# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
RAG (Retrieval-Augmented Generation) CLI Commands
==================================================

Commands for indexing documents, querying RAG system, evaluating results,
and managing RAG configuration.

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentic_brain.core.neo4j_pool import get_session as get_shared_neo4j_session
from agentic_brain.rag.system import RAGSystem

from .commands import Colors, print_header, print_info, print_success, print_warning


def cmd_query(args: argparse.Namespace) -> int:
    """Execute a RAG query and return results.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        0 on success, 1 on error
    """
    try:
        question = args.question
        if not question:
            if args.json:
                print(json.dumps({"error": "No question provided"}))
            else:
                print_warning("No question provided")
            return 1
        
        if not args.json:
            print_header("RAG Query")
            print_info(f"Querying: {question}")
        
        # Initialize RAG system
        rag = RAGSystem()
        
        # Execute query with timing
        start_time = time.time()
        
        result = rag.query(
            question=question,
            top_k=args.top_k,
            filters=args.filters,
        )
        
        elapsed = time.time() - start_time
        
        if args.json:
            output = {
                "question": question,
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "relevance_score": result.get("relevance_score", 0.0),
                "elapsed_ms": elapsed * 1000,
            }
            print(json.dumps(output, indent=2))
        else:
            print_success(f"Query completed in {elapsed:.2f}s")
            print(f"\n{Colors.BOLD}Answer:{Colors.RESET}")
            print(result.get("answer", "No answer found"))
            
            sources = result.get("sources", [])
            if sources:
                print(f"\n{Colors.BOLD}Sources:{Colors.RESET}")
                for i, source in enumerate(sources, 1):
                    print(f"  {i}. {source}")
            
            score = result.get("relevance_score", 0.0)
            print(f"\n{Colors.BOLD}Relevance Score:{Colors.RESET} {score:.2%}")
        
        return 0
    
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print_warning(f"Query failed: {e}")
        return 1


def cmd_index(args: argparse.Namespace) -> int:
    """Index documents from specified path.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        0 on success, 1 on error
    """
    try:
        path = Path(args.path)
        if not path.exists():
            if args.json:
                print(json.dumps({"error": f"Path does not exist: {path}"}))
            else:
                print_warning(f"Path does not exist: {path}")
            return 1
        
        if not args.json:
            print_header("Document Indexing")
            print_info(f"Indexing documents from: {path}")
        
        # Initialize RAG system
        rag = RAGSystem()
        
        # Index documents
        start_time = time.time()
        
        result = rag.index(
            path=str(path),
            recursive=args.recursive,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
        
        elapsed = time.time() - start_time
        
        if args.json:
            output = {
                "path": str(path),
                "documents_indexed": result.get("count", 0),
                "chunks_created": result.get("chunks", 0),
                "elapsed_ms": elapsed * 1000,
            }
            print(json.dumps(output, indent=2))
        else:
            count = result.get("count", 0)
            chunks = result.get("chunks", 0)
            print_success(f"Indexed {count} documents ({chunks} chunks) in {elapsed:.2f}s")
        
        return 0
    
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print_warning(f"Indexing failed: {e}")
        return 1


def cmd_eval(args: argparse.Namespace) -> int:
    """Evaluate RAG results from results file.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        0 on success, 1 on error
    """
    try:
        results_path = Path(args.results)
        if not results_path.exists():
            if args.json:
                print(json.dumps({"error": f"Results file not found: {results_path}"}))
            else:
                print_warning(f"Results file not found: {results_path}")
            return 1
        
        # Load results
        with open(results_path) as f:
            results_data = json.load(f)
        
        if not args.json:
            print_header("Results Evaluation")
            print_info(f"Evaluating {len(results_data)} results")
        
        # Initialize RAG system
        rag = RAGSystem()
        
        # Evaluate results
        start_time = time.time()
        evaluation = rag.evaluate(results_data)
        elapsed = time.time() - start_time
        
        if args.json:
            output = {
                "total_results": len(results_data),
                "metrics": evaluation.get("metrics", {}),
                "elapsed_ms": elapsed * 1000,
            }
            print(json.dumps(output, indent=2))
        else:
            print_success(f"Evaluation completed in {elapsed:.2f}s")
            
            metrics = evaluation.get("metrics", {})
            print(f"\n{Colors.BOLD}Metrics:{Colors.RESET}")
            for key, value in metrics.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2%}")
                else:
                    print(f"  {key}: {value}")
        
        return 0
    
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print_warning(f"Evaluation failed: {e}")
        return 1


def cmd_health(args: argparse.Namespace) -> int:
    """Check system health status.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        0 on success, 1 on error
    """
    try:
        if not args.json:
            print_header("System Health Check")
        
        # Initialize RAG system
        rag = RAGSystem()
        
        # Get health status
        start_time = time.time()
        health = rag.health()
        elapsed = time.time() - start_time
        
        if args.json:
            output = {
                "status": health.get("status", "unknown"),
                "components": health.get("components", {}),
                "elapsed_ms": elapsed * 1000,
            }
            print(json.dumps(output, indent=2))
        else:
            status = health.get("status", "unknown")
            status_color = Colors.GREEN if status == "healthy" else Colors.YELLOW
            print_success(f"System status: {status_color}{status}{Colors.RESET}")
            
            components = health.get("components", {})
            if components:
                print(f"\n{Colors.BOLD}Components:{Colors.RESET}")
                for name, info in components.items():
                    comp_status = info.get("status", "unknown")
                    comp_color = Colors.GREEN if comp_status == "ok" else Colors.RED
                    print(f"  {name}: {comp_color}{comp_status}{Colors.RESET}")
        
        return 0
    
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print_warning(f"Health check failed: {e}")
        return 1


def cmd_config(args: argparse.Namespace) -> int:
    """Show or set configuration.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        0 on success, 1 on error
    """
    try:
        # Initialize RAG system
        rag = RAGSystem()
        
        if not args.json and (args.get is None and args.set is None):
            print_header("Configuration")
        
        if args.get:
            # Get specific config value
            value = rag.config(args.get)
            if args.json:
                print(json.dumps({args.get: value}, indent=2))
            else:
                print(f"{args.get}: {value}")
        elif args.set:
            # Set config value (key=value format)
            key, value = args.set.split("=", 1)
            rag.config(key, value)
            if args.json:
                print(json.dumps({"status": "success", "key": key, "value": value}))
            else:
                print_success(f"Set {key} = {value}")
        else:
            # Show all config
            config = rag.config()
            if args.json:
                print(json.dumps(config, indent=2))
            else:
                print(f"\n{Colors.BOLD}Configuration:{Colors.RESET}")
                for key, value in config.items():
                    print(f"  {key}: {value}")
        
        return 0
    
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print_warning(f"Config operation failed: {e}")
        return 1


def register_rag_commands(subparsers: argparse._SubParsersAction) -> None:
    """Register RAG commands with the argument parser.
    
    Args:
        subparsers: The subparsers action from argparse
    """
    # Query command
    query_parser = subparsers.add_parser(
        "query",
        help="Run a RAG query",
        description="Execute a retrieval-augmented generation query",
    )
    query_parser.add_argument("question", help="Question to ask")
    query_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top results to return (default: 5)",
    )
    query_parser.add_argument(
        "--filters",
        type=json.loads,
        default={},
        help="JSON filters for document selection",
    )
    query_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    query_parser.set_defaults(func=cmd_query)
    
    # Index command
    index_parser = subparsers.add_parser(
        "index",
        help="Index documents",
        description="Index documents from specified path for RAG",
    )
    index_parser.add_argument("path", help="Path to documents")
    index_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively index subdirectories",
    )
    index_parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Size of document chunks (default: 512)",
    )
    index_parser.add_argument(
        "--overlap",
        type=int,
        default=50,
        help="Overlap between chunks (default: 50)",
    )
    index_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    index_parser.set_defaults(func=cmd_index)
    
    # Eval command
    eval_parser = subparsers.add_parser(
        "eval",
        help="Evaluate results",
        description="Evaluate RAG results from results file",
    )
    eval_parser.add_argument("results", help="Path to results file (JSON)")
    eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Output metrics as JSON",
    )
    eval_parser.set_defaults(func=cmd_eval)
    
    # Health command
    health_parser = subparsers.add_parser(
        "health",
        help="Check system health",
        description="Check health status of RAG system and components",
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        help="Output health status as JSON",
    )
    health_parser.set_defaults(func=cmd_health)
    
    # Config command
    config_parser = subparsers.add_parser(
        "config",
        help="Manage configuration",
        description="Show or set RAG system configuration",
    )
    config_parser.add_argument(
        "--get",
        help="Get specific config value",
    )
    config_parser.add_argument(
        "--set",
        help="Set config value (format: key=value)",
    )
    config_parser.add_argument(
        "--json",
        action="store_true",
        help="Output configuration as JSON",
    )
    config_parser.set_defaults(func=cmd_config)

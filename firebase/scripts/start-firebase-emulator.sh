#!/bin/bash
set -e

# Start Firebase Emulators
firebase emulators:start --only auth,firestore,database --project agentic-brain-local

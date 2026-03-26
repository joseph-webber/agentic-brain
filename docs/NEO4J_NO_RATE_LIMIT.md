# Preventing Neo4j Rate Limit Issues

## Quick Fix: Restart Neo4j
```bash
neo4j stop && sleep 3 && neo4j start
```

## Permanent Fix: Increase Rate Limit
Add to neo4j.conf:
```
dbms.security.auth_max_failed_attempts=100
```

## For Local Dev Only: Disable Auth
```
dbms.security.auth_enabled=false
```

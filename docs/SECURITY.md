# Security

## What's Protected ✓

### Input Validation
- Message length: 1-32,000 characters (Pydantic)
- Session ID format: alphanumeric + hyphen/underscore only
- User ID format: alphanumeric + hyphen/underscore only

### Rate Limiting
- 60 requests per minute per IP address
- Automatic cleanup of old request counts

### Data Isolation
- Sessions are isolated by session_id
- No cross-session data leakage

## What's NOT Protected ✗

### Authentication
- **No authentication required** - anyone can use any session_id
- For production, add API key or JWT authentication

### Encryption at Rest
- Neo4j data is not encrypted by default
- Configure Neo4j Enterprise for encryption

### Audit Logging
- No audit trail of who accessed what
- Add logging middleware for production

## Deployment Recommendations

1. **Use environment variables** for all secrets
2. **Enable TLS** for all connections
3. **Add authentication** before exposing publicly
4. **Set up rate limiting** at load balancer level too
5. **Monitor** for unusual patterns

## Security Test Coverage

Run security tests with:
```bash
python -m pytest tests/test_security.py -v
```

### Test Categories

- **Rate Limiting Tests**: Verify per-IP rate limit enforcement
- **Input Validation Tests**: Check message/session ID validation
- **Prompt Injection Tests**: Verify resistance to prompt manipulation
- **SQL Injection Tests**: Check Neo4j query parameterization
- **Concurrency Tests**: Ensure session isolation
- **Data Sanitization Tests**: Verify no information leakage
- **Authentication Tests**: Document missing auth layer

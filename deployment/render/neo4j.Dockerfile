FROM neo4j:5.17.0-community

# Enable APOC which Agentic Brain relies on.
ENV NEO4J_PLUGINS='["apoc"]'

CMD ["neo4j"]

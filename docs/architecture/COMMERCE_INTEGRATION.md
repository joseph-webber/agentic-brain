# Commerce Integration Architecture

This document outlines how the Commerce module integrates with the core Agentic Brain systems.

```mermaid
graph TD
    %% Core Inputs
    User[User (Chat/Web)] -->|Message| Chatbot[WooCommerceChatbot]
    Store[WooCommerce Store] -->|Webhook| Handler[WebhookHandler]

    %% Brain Core Systems
    subgraph Brain Core
        Router[LLM Router]
        RAG[RAG Pipeline]
        EventBus[Event Bus (Redpanda)]
        Redis[Redis Session Store]
    end

    %% Commerce Module
    subgraph Commerce Module
        Chatbot -->|Classify Intent| Router
        Chatbot -->|Product Search| RAG
        Chatbot -->|Session Data| Redis
        
        Handler -->|Publish Event| EventBus
        
        Agent[WooCommerceAgent] -->|Sync Data| RAG
        Agent -->|CRUD| Store
        
        Hub[CommerceHub] -->|Orchestrate| Agent
    end

    %% Flows
    EventBus -->|Notify| Chatbot
    RAG -->|Context| Chatbot
    Router -->|Route| Chatbot
```

## Integration Points

1.  **RAG Pipeline**:
    - **Product Indexing**: `WooCommerceAgent.sync_products()` fetches products. A separate ingestion job pushes these to the Vector DB.
    - **Retrieval**: `WooCommerceChatbot` queries the RAG pipeline for product recommendations.

2.  **LLM Router**:
    - **Intent Classification**: The chatbot uses the Router to classify user intent (support, purchase, return).
    - **Response Generation**: Complex queries are routed to the appropriate LLM (e.g., GPT-4 for nuanced support).

3.  **Event Bus**:
    - **Webhooks**: `WooCommerceWebhookHandler` receives HMAC-signed payloads and emits standardized events to Redpanda (e.g., `commerce.order.created`).
    - **Reactivity**: Other agents subscribe to these events (e.g., to trigger a "Thank you" email).

4.  **Redis**:
    - **Session Management**: Chat state (cart context, user identity) is stored in Redis.
    - **Caching**: Product data and frequent API responses are cached to reduce latency.

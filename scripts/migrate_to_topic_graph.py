#!/usr/bin/env python3
"""
Migrate existing Neo4j data to use the arraz2000 topic-centric graph pattern.

This script:
1. Creates core Topic nodes
2. Links existing Sessions to Topics based on content
3. Links existing Memories/Learnings to Topics
4. Creates zone labels for existing nodes
5. Reports migration stats
"""

import os

from neo4j import GraphDatabase

# Neo4j connection
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Brain2026")

# Core topics from arraz2000 pattern
CORE_TOPICS = [
    # Brain/AI topics
    "voice",
    "memory",
    "learning",
    "automation",
    "agents",
    "llm",
    "embeddings",
    "rag",
    # Work topics
    "jira",
    "bitbucket",
    "code_review",
    "testing",
    "deployment",
    "ci_cd",
    "github",
    # Communication
    "teams",
    "email",
    "notifications",
    "calendar",
    "slack",
    # Data
    "neo4j",
    "redis",
    "backup",
    "sync",
    "analytics",
    "graph",
    # Accessibility
    "voiceover",
    "accessibility",
    "audio",
    "speech",
    "tts",
    # Personal
    "health",
    "trading",
    "family",
    "travel",
    "dooby",
    # Technical
    "python",
    "swift",
    "java",
    "javascript",
    "api",
    "mcp",
]


def run_migration():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    stats = {
        "topics_created": 0,
        "sessions_linked": 0,
        "memories_linked": 0,
        "constraints_created": 0,
    }

    with driver.session() as session:
        print("🚀 Starting topic-centric graph migration...")

        # 1. Create Topic nodes
        print("\n📌 Creating core Topic nodes...")
        result = session.run(
            """
            UNWIND $topics AS topic_name
            MERGE (t:Topic {name: topic_name})
            ON CREATE SET t.created_at = datetime(), t.source = 'core_migration'
            RETURN count(t) as count
        """,
            topics=CORE_TOPICS,
        )
        stats["topics_created"] = result.single()["count"]
        print(f"   Created/verified {stats['topics_created']} Topic nodes")

        # 2. Create constraints
        print("\n🔒 Creating constraints...")
        constraints = [
            "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE INDEX topic_created IF NOT EXISTS FOR (t:Topic) ON (t.created_at)",
        ]
        for c in constraints:
            try:
                session.run(c)
                stats["constraints_created"] += 1
            except:
                pass
        print(f"   Created {stats['constraints_created']} constraints/indexes")

        # 3. Link Sessions to Topics based on content keywords
        print("\n🔗 Linking Sessions to Topics...")
        for topic in CORE_TOPICS:
            result = session.run(
                """
                MATCH (s:Session)
                WHERE toLower(s.title) CONTAINS toLower($topic)
                   OR toLower(s.summary) CONTAINS toLower($topic)
                   OR toLower(s.content) CONTAINS toLower($topic)
                MATCH (t:Topic {name: $topic})
                MERGE (s)-[r:DISCUSSES]->(t)
                ON CREATE SET r.created_at = datetime(), r.source = 'migration'
                RETURN count(r) as linked
            """,
                topic=topic,
            )
            count = result.single()["linked"]
            if count > 0:
                stats["sessions_linked"] += count
                print(f"   Linked {count} sessions to '{topic}'")

        # 4. Link Memories to Topics
        print("\n🧠 Linking Memories to Topics...")
        for topic in CORE_TOPICS:
            result = session.run(
                """
                MATCH (m:Memory)
                WHERE toLower(m.content) CONTAINS toLower($topic)
                   OR toLower(m.title) CONTAINS toLower($topic)
                MATCH (t:Topic {name: $topic})
                MERGE (m)-[r:TAGGED]->(t)
                ON CREATE SET r.created_at = datetime(), r.source = 'migration'
                RETURN count(r) as linked
            """,
                topic=topic,
            )
            count = result.single()["linked"]
            if count > 0:
                stats["memories_linked"] += count
        print(f"   Linked {stats['memories_linked']} memories to topics")

        # 5. Link Learnings to Topics
        print("\n📚 Linking Learnings to Topics...")
        learnings_linked = 0
        for topic in CORE_TOPICS:
            result = session.run(
                """
                MATCH (l:Learning)
                WHERE toLower(l.content) CONTAINS toLower($topic)
                   OR toLower(l.insight) CONTAINS toLower($topic)
                MATCH (t:Topic {name: $topic})
                MERGE (l)-[r:TAGGED]->(t)
                ON CREATE SET r.created_at = datetime(), r.source = 'migration'
                RETURN count(r) as linked
            """,
                topic=topic,
            )
            count = result.single()["linked"]
            if count > 0:
                learnings_linked += count
        print(f"   Linked {learnings_linked} learnings to topics")

        # 6. Link HookEvents to Sessions (Zone 1 -> Zone 2)
        print("\n⚡ Ensuring HookEvents link to Sessions (Zone boundary)...")
        result = session.run(
            """
            MATCH (h:HookEvent)
            WHERE NOT (h)-[:PART_OF]->(:Session)
            WITH h LIMIT 1000
            MATCH (s:Session)
            WHERE s.id = h.session_id OR s.timestamp = h.session_timestamp
            MERGE (h)-[r:PART_OF]->(s)
            RETURN count(r) as linked
        """
        )
        hook_links = result.single()["linked"]
        print(f"   Linked {hook_links} HookEvents to Sessions")

        # 7. Get final stats
        print("\n📊 Final graph stats:")
        result = session.run(
            """
            MATCH (t:Topic)<-[r]-()
            WITH t.name AS topic, count(r) AS links
            RETURN sum(links) AS total_topic_links,
                   count(topic) AS topics_with_links
        """
        )
        record = result.single()
        print(f"   Total topic links: {record['total_topic_links']}")
        print(f"   Topics with links: {record['topics_with_links']}/{len(CORE_TOPICS)}")

        # Node counts by zone
        result = session.run(
            """
            MATCH (n)
            WITH labels(n)[0] AS label, count(n) AS cnt
            RETURN label, cnt ORDER BY cnt DESC LIMIT 15
        """
        )
        print("\n   Top node labels:")
        for r in result:
            print(f"      {r['label']}: {r['cnt']}")

    driver.close()

    print("\n✅ Migration complete!")
    print(f"   Topics: {stats['topics_created']}")
    print(f"   Sessions linked: {stats['sessions_linked']}")
    print(f"   Memories linked: {stats['memories_linked']}")

    return stats


if __name__ == "__main__":
    run_migration()

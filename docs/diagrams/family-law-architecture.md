# Family Law Legal Aid Architecture

**Visual map of the Australian Family Law Legal Aid chatbot case study.**

---

## System Overview

```mermaid
graph TB
    subgraph "User Interface"
        User[👤 User]
        Location[📍 Location Services]
        Auth[🔐 Identity Verification]
    end

    subgraph "Core Chatbots"
        Main[🤖 Main Family Law Bot]
        DV[🏠 DV Support Bot]
        Child[👶 Children's Matters Bot]
        Finance[💰 Financial Bot]
    end

    subgraph "Intelligence Layer"
        KB[📚 Knowledge Base]
        Router[🔀 Role Router]
        Templates[📝 Response Templates]
    end

    subgraph "External Services"
        Directory[📖 Service Directory]
        LawFirms[⚖️ Law Firm Finder]
        SupportServices[🤝 Support Services]
        CMMs[📊 CMMS Adapters]
    end

    subgraph "Plugins"
        Address[📮 Address Validation]
        Geo[🌍 Geolocation]
    end

    User --> Main
    Main --> Location
    Main --> Auth
    Main --> KB
    Main --> Router

    Router --> DV
    Router --> Child
    Router --> Finance

    KB --> Templates
    Main --> Directory
    Directory --> LawFirms
    Directory --> SupportServices

    Main --> Address
    Location --> Geo

    Main --> CMMs

    classDef user fill:#e3f2fd
    classDef bot fill:#e8f5e9
    classDef intel fill:#fff3e0
    classDef ext fill:#fce4ec
    classDef plugin fill:#f3e5f5

    class User,Location,Auth user
    class Main,DV,Child,Finance bot
    class KB,Router,Templates intel
    class Directory,LawFirms,SupportServices,CMMs ext
    class Address,Geo plugin
```

---

## Bot-to-Bot Handoff Flow

```mermaid
sequenceDiagram
    participant U as User
    participant M as Main Bot
    participant A as Auth Service
    participant S as Specialist Bot
    participant D as Directory

    U->>M: Initial query
    M->>M: Classify intent

    alt Sensitive Matter
        M->>A: Request identity verification
        A->>U: MFA challenge
        U->>A: Verify identity
        A->>M: Identity confirmed
    end

    M->>M: Route to specialist

    alt DV/Safety Concern
        M->>S: Handoff to DV Bot
        S->>D: Find local DV services
        D->>S: Service list
        S->>U: Safety resources + next steps
    else Children Matters
        M->>S: Handoff to Children's Bot
        S->>D: Find family courts
        D->>S: Court locations
        S->>U: Custody guidance
    else Financial
        M->>S: Handoff to Financial Bot
        S->>U: Property/support guidance
    end
```

---

## Location Services Flow

```mermaid
flowchart LR
    subgraph "User Input"
        State[State Code]
        Postcode[Postcode]
        GPS[GPS Coords]
    end

    subgraph "Location Service"
        LS[LocationService]
        TZ[Timezone Detection]
        Dist[Distance Calculator]
    end

    subgraph "Output"
        LocalTime[Local Time]
        NearbyServices[Nearby Services]
        Courts[Local Courts]
    end

    State --> LS
    Postcode --> LS
    GPS --> LS

    LS --> TZ
    LS --> Dist

    TZ --> LocalTime
    Dist --> NearbyServices
    Dist --> Courts
```

---

## Address Validation Plugin

```mermaid
flowchart TB
    Input["Input: '301/10 Bloduras Wya ADELAID SA 5000'"]

    subgraph "Address Parser"
        Parse[Parse Components]
        Normalize[Normalize State/Street]
        Typo[Fix Typos]
        Validate[Validate Postcode]
    end

    subgraph "Confidence Scoring"
        Score[Calculate Confidence]
        Corrections[List Corrections]
    end

    Output["Output: 'Unit 301/10 Bloduras Way, Adelaide SA 5000'<br>Confidence: 85%"]

    Input --> Parse
    Parse --> Normalize
    Normalize --> Typo
    Typo --> Validate
    Validate --> Score
    Score --> Corrections
    Corrections --> Output
```

---

## Service Directory Structure

```mermaid
graph TB
    subgraph "Service Locator"
        SL[SupportServiceLocator]
    end

    subgraph "Service Categories"
        DV[Domestic Violence]
        Legal[Legal Aid]
        Mental[Mental Health]
        Child[Children's Services]
        Housing[Housing Services]
        Financial[Financial Counselling]
        ATSI[Aboriginal Services]
        CALD[CALD Services]
        LGBTIQ[LGBTIQ+ Services]
        Disability[Disability Advocacy]
        Mens[Men's Services]
    end

    subgraph "Law Firms"
        LFF[FamilyLawFirmFinder]
        Regional[Regional Firms]
        Metro[Metro Firms]
        LegalAid[Legal Aid Providers]
        ICL[ICL Panel]
    end

    SL --> DV
    SL --> Legal
    SL --> Mental
    SL --> Child
    SL --> Housing
    SL --> Financial
    SL --> ATSI
    SL --> CALD
    SL --> LGBTIQ
    SL --> Disability
    SL --> Mens

    LFF --> Regional
    LFF --> Metro
    LFF --> LegalAid
    LFF --> ICL

    classDef locator fill:#e8f5e9
    classDef service fill:#e3f2fd
    classDef firm fill:#fff3e0

    class SL,LFF locator
    class DV,Legal,Mental,Child,Housing,Financial,ATSI,CALD,LGBTIQ,Disability,Mens service
    class Regional,Metro,LegalAid,ICL firm
```

---

## User Roles

```mermaid
mindmap
  root((Family Law Users))
    Parents
      Separated Parent
      Single Parent
      Grandparent
      Step-parent
    Professionals
      Legal Professional
      Social Worker
      Mediator
      ICL
    Support Persons
      Support Worker
      Advocate
      Family Friend
    Vulnerable Users
      DV Survivor
      At-risk Child
      Aboriginal/TSI
      CALD Person
      Disability
```

---

## 24/7 Crisis Support Flow

```mermaid
flowchart TB
    Crisis[User in Crisis]

    Crisis --> Assessment{Assess Type}

    Assessment -->|DV Emergency| DV[1800 737 732<br>1800RESPECT]
    Assessment -->|Suicidal| Life[13 11 14<br>Lifeline]
    Assessment -->|Child at Risk| Child[1800 070 120<br>Child Protection]
    Assessment -->|Legal Emergency| Legal[1300 354 244<br>LawAccess]

    DV --> Police[Call 000<br>if immediate danger]
    Life --> Police
    Child --> Police

    Legal --> Online[Federal Circuit<br>Court Website]

    style Crisis fill:#ffcdd2
    style Police fill:#ff8a80
    style DV fill:#f8bbd9
    style Life fill:#c5cae9
    style Child fill:#b2dfdb
    style Legal fill:#fff9c4
```

---

## File Structure

```
examples/case-studies/family-law-legal-aid/
│
├── README.md                 # Case study overview
├── LICENSE                   # Apache-2.0
│
├── family_law_bot.py         # 🤖 Main chatbot
├── knowledge_base.py         # 📚 Legal knowledge
├── templates.py              # 📝 Response templates
├── case_manager.py           # 📋 Case management
│
├── user_roles.py             # 👥 Role definitions
├── architecture.py           # 🏗️ Multi-domain setup
├── cmms_adapters.py          # 📊 CMMS integration
│
├── support_services.py       # 🤝 Service directory
├── law_firms.py              # ⚖️ Law firm finder
│
└── tests/
    ├── test_bot.py
    ├── test_services.py
    └── test_law_firms.py
```

---

## Integration Points

| Integration | Purpose | Module |
|-------------|---------|--------|
| Location Services | User timezone/location | `agentic_brain.location` |
| Address Validation | Format addresses | `agentic_brain.plugins.address_validation` |
| Neo4j Memory | Conversation history | `agentic_brain.neo4j` |
| Bot-to-Bot Handoff | Specialist routing | `agentic_brain.bots.handoff` |
| Identity Verification | Sensitive matter access | `agentic_brain.auth` |

---

## Compliance Requirements

- **Apache-2.0 License**: Permissive open source license
- **WCAG 2.1 AA**: Accessibility for blind users
- **Australian Privacy Act**: Data handling requirements
- **Family Law Act 1975**: Legal accuracy requirements
- **National DV Framework**: Safety-first approach

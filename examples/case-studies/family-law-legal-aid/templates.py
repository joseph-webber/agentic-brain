#!/usr/bin/env python3
"""
Australian Family Law Document Templates - Guidance Module
============================================================

This module provides TEMPLATE GUIDANCE for Australian Family Law documents.

CLIENT-FACING CHATBOT INTEGRATION
=================================
Legal firms can integrate this into client-facing chatbots so parents
and children can get instant guidance 24/7:

- "How do I respond to an affidavit?"
- "What should be in my parenting plan?"
- "What's a Notice of Risk?"

The chatbot provides GUIDANCE and EDUCATION, not legal advice.
Complex questions get escalated to the legal team.

⚠️  IMPORTANT DISCLAIMERS ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. This is NOT legal advice - it is educational guidance only
2. These are NOT actual legal documents - they are structural guides
3. Always consult a qualified family lawyer for your specific situation
4. Laws change - verify current requirements with the Federal Circuit
   and Family Court of Australia (FCFCOA)
5. Free legal help is available through Legal Aid in your state

OFFICIAL RESOURCES:
- Federal Circuit and Family Court: https://www.fcfcoa.gov.au/
- Commonwealth Courts Portal: https://www.comcourts.gov.au/
- Legal Aid (by state): Search "[Your State] Legal Aid"
- Family Relationships Advice Line: 1800 050 321

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

# =============================================================================
# CONSTANTS AND ENUMS
# =============================================================================


class DocumentType(Enum):
    """Types of Family Law documents."""

    PARENTING_ORDERS = "parenting_orders"
    CONSENT_ORDERS = "consent_orders"
    AFFIDAVIT = "affidavit"
    INITIATING_APPLICATION = "initiating_application"
    RESPONSE_APPLICATION = "response_application"
    CONTRAVENTION_APPLICATION = "contravention_application"
    NOTICE_OF_RISK = "notice_of_risk"
    RECOVERY_ORDER = "recovery_order"


class CourtForm(Enum):
    """Official FCFCOA Form Numbers."""

    INITIATING_APPLICATION = "Form 1"
    RESPONSE = "Form 2"
    APPLICATION_CONSENT_ORDERS = "Form 11"
    CONTRAVENTION = "Form 18"
    NOTICE_OF_RISK = "Form 4"
    AFFIDAVIT = "Form 14"
    SUBPOENA = "Form 22"


# =============================================================================
# SECTION 1: PARENTING ORDERS TEMPLATES (~200 lines)
# =============================================================================

PARENTING_ORDERS_GUIDANCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              PARENTING ORDERS - STRUCTURAL GUIDANCE                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Official Form: Consent Orders use Form 11                                    ║
║  Court: Federal Circuit and Family Court of Australia (FCFCOA)               ║
║  Filing: Commonwealth Courts Portal (comcourts.gov.au)                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

DISCLAIMER: This is guidance only. Consult a family lawyer for your situation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STANDARD PARENTING ORDER STRUCTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orders typically include numbered paragraphs covering these areas:

1. PARENTAL RESPONSIBILITY
   ─────────────────────────
   Common wording patterns:
   
   (a) "That the parties have EQUAL SHARED PARENTAL RESPONSIBILITY
        for [Child's name], born [DOB]."
   
   OR (if sole responsibility):
   
   (b) "That [Parent name] have SOLE PARENTAL RESPONSIBILITY for
        [Child's name], born [DOB], in relation to [specific matters]."
   
   KEY CONCEPT: Parental responsibility is about DECISION-MAKING, not
   where the child lives. Equal shared parental responsibility means
   both parents must consult on major long-term decisions.

2. "LIVES WITH" ARRANGEMENTS
   ──────────────────────────
   This defines the child's primary residence:
   
   Example wording:
   "That [Child's name] live with [Parent A]."
   
   OR for shared care:
   "That [Child's name] live with both [Parent A] and [Parent B]
    on a shared basis as set out in these orders."
   
   TIPS:
   - Court no longer uses "custody" or "residence" terminology
   - "Lives with" is the current preferred term
   - Consider school proximity and stability

3. "SPENDS TIME WITH" ARRANGEMENTS
   ─────────────────────────────────
   Structure for regular time (choose what suits your situation):
   
   FORTNIGHTLY PATTERN EXAMPLE:
   "That [Child's name] spend time with [Parent B] as follows:
   
    (a) Each alternate weekend from [day/time] to [day/time];
    (b) One midweek period from [day/time] to [day/time];
    (c) Half of each school holiday period;
    (d) [Special days as specified below]."
   
   WEEK ABOUT PATTERN EXAMPLE:
   "That [Child's name] spend time with each parent on an
    alternating weekly basis, changeovers occurring each
    [day] at [time] at [location]."
   
   TIPS FOR DRAFTING:
   - Be SPECIFIC about days and times
   - Define whether "weekend" means Friday-Sunday or Saturday-Sunday
   - Specify pickup AND dropoff times
   - Name the changeover location precisely

4. COMMUNICATION PROVISIONS
   ─────────────────────────
   Include provisions for phone/video contact:
   
   Example wording:
   "That the child may have reasonable telephone and/or video
    communication with [non-resident parent] at the following times:
    
    (a) [Days] between [time] and [time];
    (b) The receiving parent will ensure the child is available
        and that the call occurs in a private space;
    (c) Neither parent will record calls without consent."
   
   CONSIDERATIONS:
   - Age-appropriate communication methods
   - Reasonable call duration for child's age
   - Privacy during calls
   - Who initiates the call

5. CHANGEOVER LOGISTICS
   ─────────────────────
   Be specific to avoid disputes:
   
   Example wording:
   "Changeovers shall occur:
   
    (a) LOCATION: [Specific address OR 'at school' OR neutral location]
    (b) TRANSPORT: [Parent A] shall be responsible for transporting
        the child TO [Parent B]'s care, and [Parent B] shall be
        responsible for returning the child to [Parent A]'s care.
    (c) PUNCTUALITY: Each parent shall ensure they are punctual
        (within 15 minutes) for changeover times.
    (d) THIRD PARTIES: If a parent cannot attend changeover personally,
        they shall give 24 hours' notice and may nominate [specify]."
   
   TIPS:
   - School pickup/dropoff often works well as it's neutral
   - Consider drive times and traffic
   - Have a backup plan for emergencies

6. SCHOOL HOLIDAY ARRANGEMENTS
   ────────────────────────────
   Example structure:
   
   "That school holiday time be divided as follows:
   
    (a) ODD YEARS (2025, 2027, etc.):
        - [Parent A] has the FIRST HALF of each holiday period
        - [Parent B] has the SECOND HALF
        
    (b) EVEN YEARS (2026, 2028, etc.):
        - [Parent B] has the FIRST HALF
        - [Parent A] has the SECOND HALF
        
    (c) CHRISTMAS: [Child] spends Christmas Day with [Parent A]
        in odd years and [Parent B] in even years
        
    (d) Transition between holiday periods occurs at [time] on
        the [midpoint date / Wednesday of second week]."
   
   SPECIFIC HOLIDAYS TO ADDRESS:
   - Christmas Eve and Christmas Day
   - Easter (Good Friday to Easter Monday)
   - Mother's Day (always with mother regardless of schedule)
   - Father's Day (always with father regardless of schedule)
   - Child's birthday
   - Each parent's birthday
   - School holidays (start/end dates from school calendar)

7. SCHOOL AND MEDICAL DECISIONS
   ─────────────────────────────
   With equal shared parental responsibility:
   
   Example wording:
   "That both parents consult and attempt to reach agreement on
    major long-term issues including:
    
    (a) The child's education (including school selection);
    (b) The child's health (including major medical decisions);
    (c) The child's religious and cultural upbringing;
    (d) The child's name;
    (e) Changes to living arrangements affecting the child.
    
    If agreement cannot be reached after genuine efforts, either
    party may apply to the Court for determination."
   
   DAY-TO-DAY DECISIONS:
   "Each parent may make day-to-day decisions about the child's
    care during the time the child is with that parent."

8. PASSPORT AND TRAVEL PROVISIONS
   ────────────────────────────────
   Example wording:
   
   "PASSPORT:
    (a) Each parent consents to the child holding an Australian passport;
    (b) The passport shall be held by [Parent A / alternating];
    (c) The passport shall be provided to the other parent at least
        [7 days] before any approved overseas travel.
    
    DOMESTIC TRAVEL:
    Each parent may travel domestically with the child during their
    time without requiring consent, provided:
    (a) The other parent is notified in advance;
    (b) Contact details are provided for the duration.
    
    INTERNATIONAL TRAVEL:
    (a) Neither parent shall take the child overseas without the
        written consent of the other parent OR a court order;
    (b) Consent requests shall be made at least [6 weeks] in advance;
    (c) Itinerary, accommodation, and contact details shall be provided;
    (d) [If applicable: The child shall not travel to [countries].]"
   
   HAGUE CONVENTION NOTE:
   Australia is a signatory to the Hague Convention on International
   Child Abduction. If concerned about abduction risk, seek legal advice.

9. SPECIAL PROVISIONS FOR INFANTS (0-4 years)
   ───────────────────────────────────────────
   Infants have different developmental needs:
   
   - SHORTER, more frequent visits (e.g., 2-3 times per week)
   - No overnight stays initially (court preference varies)
   - Gradual increase in time as child develops
   - Consistent routines around sleep and feeding
   - Consider breastfeeding arrangements
   
   Example graduated plan:
   "Months 1-6:  3x per week, 2 hours each visit
    Months 7-12: 3x per week, 4 hours including one meal
    Year 2:      2x per week, one overnight included
    Year 3+:     Progress to standard arrangements"

10. SPECIAL PROVISIONS FOR TEENAGERS (13+ years)
    ─────────────────────────────────────────────
    Teenagers need flexibility and input:
    
    "The parties acknowledge that as [Child] matures, [his/her]
     views about arrangements may change. The parties agree to:
     
     (a) Consider [Child's] reasonable wishes about time arrangements;
     (b) Allow flexibility for [Child's] activities and friendships;
     (c) Not place [Child] in the middle of parental disputes;
     (d) Review arrangements at [Child's] request."
    
    TIPS:
    - Courts give significant weight to views of children 12+
    - Forcing arrangements on teenagers often backfires
    - Balance flexibility with maintaining relationships
"""

# =============================================================================
# SECTION 2: CONSENT ORDERS TEMPLATES (~150 lines)
# =============================================================================

CONSENT_ORDERS_GUIDANCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              CONSENT ORDERS - STRUCTURAL GUIDANCE                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Official Form: Form 11 - Application for Consent Orders                     ║
║  Filing Fee: Check current fees at fcfcoa.gov.au                            ║
║  Filing: Commonwealth Courts Portal (preferred) or Court Registry            ║
╚══════════════════════════════════════════════════════════════════════════════╝

DISCLAIMER: This is guidance only. Consent orders become legally binding
court orders - ensure you understand what you're agreeing to.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. COVER SHEET REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Form 11 Part A requires:

□ COURT FILE NUMBER (if existing proceedings) or "No current proceedings"
□ FULL NAMES of both parties (as on birth certificates)
□ DATES OF BIRTH of both parties
□ ADDRESS FOR SERVICE (where court documents sent - can be lawyer or PO Box)
□ DATE OF MARRIAGE (if applicable)
□ DATE OF SEPARATION
□ CHILDREN'S DETAILS:
  - Full names
  - Dates of birth
  - Current living arrangements
□ RELATIONSHIP CATEGORY:
  - Married / De facto / Other
□ FINANCIAL CIRCUMSTANCES (if property orders sought):
  - Assets, liabilities, superannuation overview

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. PARENTING CONSENT ORDERS SECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Form 11 Part B (Parenting) structure:

"BY CONSENT AND WITHOUT ADMISSIONS, THE COURT ORDERS:

PARENTAL RESPONSIBILITY
1. [Parental responsibility paragraph - see Parenting Orders section]

LIVES WITH
2. [Lives with arrangement]

SPENDS TIME WITH
3. [Detailed time arrangement - be specific!]

COMMUNICATION
4. [Phone/video contact provisions]

HOLIDAYS
5. [School holiday and special occasion arrangements]

CHANGEOVERS
6. [Location, time, transport responsibilities]

LONG-TERM DECISIONS
7. [Education, health, religion decisions]

TRAVEL
8. [Passport and travel provisions]

GENERAL
9. Neither party shall denigrate the other in the child's presence.
10. Both parties shall encourage the child's relationship with
    the other parent.
11. Both parties shall keep the other informed of any significant
    events in the child's life."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. PROPERTY CONSENT ORDERS SECTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Form 11 Part C (Property) structure:

"BY CONSENT, THE COURT ORDERS:

REAL PROPERTY [if applicable]
1. The property at [address] shall be:
   (a) Transferred to [Party A] within [X] days; OR
   (b) Sold with proceeds divided [X]% to [Party A] and [Y]% to [Party B]; OR
   (c) Retained by [Party A] who shall refinance to remove [Party B]
       from the mortgage within [X] days.

2. [Party retaining property] shall pay [Party releasing property]
   the sum of $[amount] representing their share of equity.

PERSONAL PROPERTY
3. Each party shall retain personal property currently in their possession.

4. [Specific items]: The [item] shall be transferred to [Party].

VEHICLES
5. [Party A] shall retain the [Year Make Model] registered [REG].
   [Party B] shall retain the [Year Make Model] registered [REG].

DEBTS
6. [Party A] shall be solely responsible for the debt to [creditor]
   in the approximate sum of $[amount] and shall indemnify [Party B]
   against any claim in relation to that debt.

BANK ACCOUNTS
7. The funds in [Bank] account number [XXXX] shall be divided equally
   within [X] days of these orders.

RELEASE OF CLAIMS
8. Each party releases the other from any further claim for property
   settlement pursuant to Section 79 of the Family Law Act 1975."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. SUPERANNUATION SPLITTING ORDERS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT: Superannuation splitting requires specific procedural steps.

BEFORE FILING:
□ Obtain current superannuation statements (within 3 months)
□ Procedural Fairness letters may be required to super funds
□ Confirm if fund requires specific wording

Example Order Structure:
"SUPERANNUATION

9. Pursuant to Part VIIIB of the Family Law Act 1975:

   (a) The superannuation interest of [Member Spouse] in [Fund Name]
       (Member Number: [XXXXX]) be split;
       
   (b) [Non-Member Spouse] is to receive [X]% / the sum of $[amount]
       of the splittable payment calculated as at [date / date of split];
       
   (c) The [Non-Member Spouse's] entitlement be:
       [Paid to an eligible rollover fund nominated by them / 
        Retained in the fund in a separate account];
        
   (d) The Trustee is directed to implement this order within
       [28 days / as soon as practicable]."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. FILING WITH COMMONWEALTH COURTS PORTAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP-BY-STEP:

1. CREATE ACCOUNT at comcourts.gov.au (both parties need accounts)

2. PREPARE DOCUMENTS:
   □ Completed Form 11 (all parts)
   □ Proposed Orders (the actual orders you want made)
   □ Any required annexures
   □ Filing fee payment details

3. SUBMIT ONLINE:
   □ Log in to portal
   □ Select "Family Law" > "Consent Orders"
   □ Upload Form 11 and attachments
   □ Pay filing fee
   □ Both parties sign electronically

4. WAIT FOR REVIEW:
   - Registrar reviews for legal appropriateness
   - May take 4-8 weeks
   - May request amendments

5. IF APPROVED:
   - Sealed orders issued
   - Download from portal
   - Orders are LEGALLY BINDING

6. IF AMENDMENTS REQUESTED:
   - Make requested changes
   - Resubmit via portal
   - No additional filing fee usually required
"""

# =============================================================================
# SECTION 3: AFFIDAVIT TEMPLATES (~150 lines)
# =============================================================================

AFFIDAVIT_GUIDANCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              AFFIDAVIT - STRUCTURAL GUIDANCE                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Official Form: Form 14 - Affidavit                                          ║
║  Purpose: Sworn evidence to the Court                                        ║
║  WARNING: Lying in an affidavit is PERJURY - a criminal offence             ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. STRUCTURE AND FORMATTING RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEADER (Required at top of every page):

    Federal Circuit and Family Court of Australia
    File Number: [Court file number]
    
    AFFIDAVIT
    
    Applicant:     [Full Name]
    First Respondent: [Full Name]
    
    Affidavit of: [Your full name]
    Affirmed/Sworn on: [Date]
    Filed on behalf of: [Applicant/Respondent]

BODY STRUCTURE:

    I, [FULL LEGAL NAME], of [Suburb, State], [Occupation], state:
    
    1. I am the [Applicant/Respondent] in these proceedings.
    
    2. [Statement of fact]
    
    3. [Statement of fact]
    
    ... [Numbered paragraphs continue]

SIGNATURE BLOCK:

    ─────────────────────────────────────
    [Your signature]
    [Your printed name]
    Date: [Date]

JURAT (Witness section):

    This affidavit was [sworn/affirmed] by [Your name]
    at [Suburb, State] on [Date]
    
    Before me:
    
    ─────────────────────────────────────
    [Witness signature]
    [Witness name]
    [Qualification: Justice of the Peace / Lawyer / etc.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. PARAGRAPH NUMBERING RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ CORRECT FORMAT:
    1. Each paragraph numbered consecutively.
    
    2. Sub-paragraphs use letters:
       (a) First sub-point
       (b) Second sub-point
           (i) Further sub-point uses Roman numerals
           (ii) Another Roman numeral point
    
    3. Back to main numbering.

❌ INCORRECT:
    - Bullet points (not accepted by court)
    - Inconsistent numbering
    - Missing numbers
    - Paragraphs without numbers

PARAGRAPH CONTENT RULES:
    - ONE main idea per paragraph
    - State FACTS, not arguments or opinions
    - Be SPECIFIC with dates, times, amounts
    - Use "I believe" only for matters of belief
    - For information from others: "I was told by [name] that..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. HOW TO ATTACH ANNEXURES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANNEXURE CERTIFICATE (Required on first page of each annexure):

    ┌──────────────────────────────────────────────────────────────┐
    │  This is the annexure marked "A" referred to in the         │
    │  affidavit of [Your Name] affirmed/sworn on [Date].         │
    │                                                              │
    │  Before me:                                                  │
    │                                                              │
    │  ________________________                                    │
    │  [Witness signature]                                         │
    │  [Witness name]                                              │
    │  [Qualification]                                             │
    └──────────────────────────────────────────────────────────────┘

REFERRING TO ANNEXURES IN YOUR AFFIDAVIT:

    "15. On 15 March 2024, I received a text message from the
         Respondent. A copy of that text message is annexed
         hereto and marked 'A'.
    
    16.  The bank statement showing the transfer is annexed
         hereto and marked 'B'."

ANNEXURE LABELLING:
    - First annexure: "A"
    - Second: "B"
    - Continue alphabetically
    - If more than 26: "AA", "AB", etc.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. COMMON MISTAKES TO AVOID
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ ARGUMENTS INSTEAD OF FACTS:
   Wrong: "The Respondent is a terrible parent who doesn't care."
   Right: "On 15 March 2024, the Respondent failed to collect
          the child from school at the agreed time of 3:30pm.
          The child waited at school until 5:00pm."

❌ VAGUE STATEMENTS:
   Wrong: "The Respondent often misses pickups."
   Right: "The Respondent missed pickups on 15 March, 22 March,
          and 5 April 2024."

❌ HEARSAY WITHOUT IDENTIFICATION:
   Wrong: "I heard the Respondent was drinking at the pub."
   Right: "On 10 April 2024, my friend [Name] told me they saw
          the Respondent drinking at the [Name] Hotel."

❌ EMOTIONAL LANGUAGE:
   Wrong: "The Respondent disgustingly neglected our child."
   Right: "On [date], the child told me they had not been fed
          dinner while in the Respondent's care."

❌ IRRELEVANT INFORMATION:
   Wrong: Including every grievance from your relationship
   Right: Focus only on matters relevant to the current application

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. TIPS FOR SELF-REPRESENTED LITIGANTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

BEFORE YOU START:
    □ Read the other party's affidavit (if responding)
    □ List all facts you need to include
    □ Gather supporting documents (annexures)
    □ Use the court's template/form

WRITING TIPS:
    □ Use plain English - avoid legal jargon
    □ Write in first person ("I saw..." not "The Applicant saw...")
    □ Be chronological where possible
    □ Keep paragraphs short and focused
    □ Check spelling of names, dates, amounts

SWORN vs AFFIRMED:
    - SWORN: Religious oath ("So help me God")
    - AFFIRMED: Non-religious promise (same legal effect)
    - Choose whichever is appropriate for you

WHO CAN WITNESS:
    - Justice of the Peace (JP)
    - Lawyer/Solicitor
    - Police officer
    - Pharmacist
    - Bank manager
    - Other authorised witnesses (varies by state)

PAGE LIMITS:
    - Check court rules - some interim applications have page limits
    - Be concise - judges appreciate brevity
    - Quality over quantity

FILING:
    □ Keep original for yourself
    □ File required number of copies (usually 2-3)
    □ File via Commonwealth Courts Portal or in person
    □ Serve copies on other party as required
"""

# =============================================================================
# SECTION 4: APPLICATION TEMPLATES (~100 lines)
# =============================================================================

APPLICATION_GUIDANCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              APPLICATION TEMPLATES - STRUCTURAL GUIDANCE                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  This section covers various application types and their requirements        ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. INITIATING APPLICATION (Form 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USE WHEN: Starting NEW family law proceedings

FORM 1 STRUCTURE:
    Part A - Party Details
        □ Your full name, DOB, address for service
        □ Other party's full name, DOB, address
        □ Relationship type (married/de facto)
        □ Date of separation
        
    Part B - Children
        □ Full names and DOBs of all children
        □ Current arrangements
        
    Part C - What Orders You Seek
        □ Parenting orders (if applicable)
        □ Property orders (if applicable)
        □ Spousal maintenance (if applicable)
        
    Part D - Urgency
        □ Is this matter urgent?
        □ Grounds for urgency

REQUIRED ATTACHMENTS:
    □ Affidavit in support
    □ Notice of Risk (if child abuse/family violence)
    □ Financial Statement (if property/maintenance)
    □ Filing fee or fee waiver application

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. RESPONSE TO APPLICATION (Form 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USE WHEN: Responding to an application filed against you

TIME LIMIT: Usually 28 days from service (check your documents!)

FORM 2 STRUCTURE:
    Part A - Your Details
        □ Confirm/correct your personal details
        □ Your address for service
        
    Part B - Response to Orders Sought
        □ For each order the Applicant seeks:
          - Consent / Oppose / Seek different order
        □ What orders YOU seek (if different)
        
    Part C - Your Version of Events
        □ Any facts you dispute from Applicant's affidavit

REQUIRED ATTACHMENTS:
    □ Your affidavit in response
    □ Notice of Risk (if applicable)
    □ Financial Statement (if property involved)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. CONTRAVENTION APPLICATION (Form 18)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

USE WHEN: The other party has breached existing court orders

FORM 18 REQUIREMENTS:
    □ Existing court order details (date, court, file number)
    □ Which specific order was breached
    □ Details of each breach:
        - Date of breach
        - What should have happened
        - What actually happened
        - Any reasonable excuse given
    □ What you want the court to do

POSSIBLE OUTCOMES FOR CONTRAVENTION:
    - Compensatory time awarded
    - Fines
    - Community service
    - Variation of orders
    - In serious cases: imprisonment

IMPORTANT: Before filing, consider:
    □ Was there a genuine reasonable excuse?
    □ Have you tried to resolve it directly?
    □ Is the breach significant enough to warrant court?
    □ Family Dispute Resolution may be required first

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. URGENT/RECOVERY ORDER APPLICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOVERY ORDER - Use when child has been:
    - Taken without consent
    - Not returned after agreed time
    - Hidden by the other parent

APPLICATION MUST SHOW:
    □ Existing parenting orders (or who child lives with)
    □ How child was taken/withheld
    □ Attempts made to locate/recover child
    □ Urgency - risk to child if not recovered

COURT MAY ORDER:
    - Return of child
    - Police assistance to locate/recover
    - Passports surrendered
    - Parties prohibited from removing child from area

URGENT APPLICATIONS generally:
    - Filed ex parte (without other party knowing initially)
    - Heard same day or next day
    - Require evidence of immediate risk
    - May have ongoing court dates set

⚠️  IF A CHILD IS IN IMMEDIATE DANGER: Call 000 (Police)
    The court process takes time - if there's immediate risk,
    police involvement may be necessary.
"""

# =============================================================================
# SECTION 5: NOTICE OF RISK TEMPLATE (~50 lines)
# =============================================================================

NOTICE_OF_RISK_GUIDANCE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              NOTICE OF RISK (Form 4) - GUIDANCE                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CRITICAL: Required when allegations of abuse or family violence             ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHEN IS A NOTICE OF RISK REQUIRED?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

YOU MUST FILE Form 4 if your case involves allegations of:

    □ Family violence (physical, emotional, financial, sexual)
    □ Child abuse or neglect
    □ Child at risk of abuse
    □ Child exposed to family violence

This is MANDATORY - failure to file may delay your matter.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT TO INCLUDE IN FORM 4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Part A - Child Details:
    □ Names and DOBs of children
    □ Who each child currently lives with
    
Part B - Allegations (for EACH child):
    □ Type of abuse/violence alleged
    □ Who is alleged to have committed it
    □ Brief description of allegations
    □ When did it occur (dates/periods)
    □ Are there ongoing safety concerns?
    
Part C - Relevant Orders/Investigations:
    □ Existing intervention/protection orders
    □ Child protection involvement
    □ Police involvement
    □ Family violence orders from state courts
    
Part D - Current Safety:
    □ Current arrangements to protect child
    □ Supervision arrangements (if any)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIVACY CONSIDERATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  IMPORTANT: Form 4 is provided to the other party

SAFETY PLANNING:
    □ Consider whether filing will escalate risk
    □ Discuss safety planning with support service
    □ You may apply to withhold your address
    □ Let the court know if you have safety concerns about disclosure

CONFIDENTIALITY OPTIONS:
    □ Request address be kept confidential
    □ Request documents be served through court
    □ Apply for suppression order if necessary

SUPPORT SERVICES:
    - 1800 RESPECT (1800 737 732) - 24/7 support
    - Legal Aid in your state
    - Women's Legal Services
    - Men's Referral Service: 1300 766 491
"""

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_template_guidance(template_type: str) -> str:
    """
    Get comprehensive guidance for a specific document type.

    Args:
        template_type: Type of document (e.g., 'parenting_orders', 'consent_orders')

    Returns:
        Detailed guidance string for that document type

    Example:
        >>> guidance = get_template_guidance('affidavit')
        >>> print(guidance)  # Prints full affidavit guidance
    """
    templates = {
        "parenting_orders": PARENTING_ORDERS_GUIDANCE,
        "parenting": PARENTING_ORDERS_GUIDANCE,
        "consent_orders": CONSENT_ORDERS_GUIDANCE,
        "consent": CONSENT_ORDERS_GUIDANCE,
        "affidavit": AFFIDAVIT_GUIDANCE,
        "application": APPLICATION_GUIDANCE,
        "applications": APPLICATION_GUIDANCE,
        "initiating": APPLICATION_GUIDANCE,
        "response": APPLICATION_GUIDANCE,
        "contravention": APPLICATION_GUIDANCE,
        "notice_of_risk": NOTICE_OF_RISK_GUIDANCE,
        "risk": NOTICE_OF_RISK_GUIDANCE,
        "form4": NOTICE_OF_RISK_GUIDANCE,
    }

    key = template_type.lower().replace(" ", "_").replace("-", "_")

    if key in templates:
        return templates[key]

    return f"""
Template type '{template_type}' not found.

Available templates:
- parenting_orders (or 'parenting')
- consent_orders (or 'consent')
- affidavit
- application (covers initiating, response, contravention)
- notice_of_risk (or 'risk', 'form4')

Try: get_template_guidance('parenting_orders')
"""


def get_checklist(document_type: str) -> List[str]:
    """
    Get a filing checklist for a specific document type.

    Args:
        document_type: Type of document to get checklist for

    Returns:
        List of items to check before filing
    """
    checklists = {
        "consent_orders": [
            "□ Completed Form 11 (all applicable parts)",
            "□ Proposed orders drafted in correct legal format",
            "□ Both parties have signed where required",
            "□ Filing fee ready (or fee waiver application)",
            "□ Superannuation statements attached (if super splitting)",
            "□ Created Commonwealth Courts Portal account",
            "□ Checked orders are specific (dates, times, addresses)",
            "□ Included all children's full names and DOBs",
            "□ Removed any ambiguous language",
            "□ Had someone else proofread the documents",
        ],
        "affidavit": [
            "□ Used correct Form 14 format",
            "□ All paragraphs numbered consecutively",
            "□ Header on every page (file number, parties)",
            "□ All facts stated (not arguments or opinions)",
            "□ Dates and times are specific",
            "□ Annexures properly labelled (A, B, C...)",
            "□ Annexure certificates completed",
            "□ Signed and dated by you",
            "□ Witnessed by authorised person (JP, lawyer, etc.)",
            "□ Jurat completed (witness signed and dated)",
            "□ Required number of copies prepared",
        ],
        "initiating_application": [
            "□ Form 1 completed in full",
            "□ Affidavit in support prepared",
            "□ Notice of Risk completed (if applicable)",
            "□ Financial Statement completed (if property/maintenance)",
            "□ Filing fee ready (or fee waiver application)",
            "□ Other party's address for service known",
            "□ All children's details included",
            "□ Specific orders sought are clearly stated",
            "□ Evidence of urgency (if claiming urgent)",
            "□ Family Dispute Resolution certificate (unless exempt)",
        ],
        "contravention": [
            "□ Copy of original orders being contravened",
            "□ Form 18 completed",
            "□ Specific details of each breach (date, what happened)",
            "□ Evidence supporting the breach allegation",
            "□ Explanation of what remedy you seek",
            "□ Considered whether breach was reasonable excuse",
            "□ Affidavit in support",
            "□ Filing fee ready",
        ],
        "notice_of_risk": [
            "□ Form 4 downloaded and completed",
            "□ Specific allegations described (who, what, when)",
            "□ All relevant children included",
            "□ Existing orders/investigations noted",
            "□ Current safety arrangements described",
            "□ Considered safety planning before filing",
            "□ Support service contacted if needed",
            "□ Address confidentiality request (if needed)",
        ],
    }

    key = document_type.lower().replace(" ", "_").replace("-", "_")

    if key in checklists:
        return checklists[key]

    return [
        f"No specific checklist for '{document_type}'.",
        "General filing checklist:",
        "□ Document completed in full",
        "□ All required attachments included",
        "□ Correct number of copies prepared",
        "□ Filing fee ready",
        "□ Commonwealth Courts Portal account created",
    ]


def get_common_mistakes(document_type: str) -> List[str]:
    """
    Get list of common mistakes for a document type.

    Args:
        document_type: Type of document

    Returns:
        List of common mistakes to avoid
    """
    mistakes = {
        "affidavit": [
            "❌ Using bullet points instead of numbered paragraphs",
            "❌ Making arguments instead of stating facts",
            "❌ Vague statements ('often', 'sometimes', 'many times')",
            "❌ Emotional language ('disgusting', 'terrible parent')",
            "❌ Including irrelevant relationship history",
            "❌ Forgetting to number all paragraphs",
            "❌ Missing annexure certificates",
            "❌ Not having proper witness sign the jurat",
            "❌ Hearsay without identifying the source",
            "❌ Exceeding page limits (for interim applications)",
        ],
        "consent_orders": [
            "❌ Ambiguous language ('reasonable time', 'as agreed')",
            "❌ Missing specific dates and times for changeover",
            "❌ Not specifying which parent does transport",
            "❌ Forgetting to address school holidays",
            "❌ Missing Mother's Day / Father's Day provisions",
            "❌ Not including communication provisions",
            "❌ Forgetting passport/travel provisions",
            "❌ Superannuation orders without procedural fairness",
            "❌ Property orders that are impossible to implement",
            "❌ Orders that contradict each other",
        ],
        "parenting_orders": [
            "❌ Using old terminology ('custody', 'residence', 'access')",
            "❌ Not being specific enough about time arrangements",
            "❌ Forgetting timezone issues if parents in different states",
            "❌ Not considering child's activities and commitments",
            "❌ Rigid arrangements that don't allow for teenage flexibility",
            "❌ No provision for communicating changes",
            "❌ Forgetting what happens if a parent is late",
            "❌ Not addressing introduction of new partners",
            "❌ Missing provisions for child's special needs",
        ],
        "application": [
            "❌ Filing without Family Dispute Resolution certificate",
            "❌ Not serving documents on other party properly",
            "❌ Missing filing deadlines (especially for Response)",
            "❌ Not including all required attachments",
            "❌ Incorrect court file number",
            "❌ Wrong form for the type of application",
            "❌ Not updating address for service when moving",
        ],
    }

    key = document_type.lower().replace(" ", "_").replace("-", "_")

    if key in mistakes:
        return mistakes[key]

    return [
        "General mistakes to avoid:",
        "❌ Missing deadlines",
        "❌ Incomplete forms",
        "❌ Missing attachments",
        "❌ Not keeping copies for yourself",
        "❌ Not serving documents on the other party",
    ]


def get_filing_instructions(document_type: str) -> str:
    """
    Get step-by-step filing instructions for a document type.

    Args:
        document_type: Type of document

    Returns:
        Filing instructions as a formatted string
    """
    instructions = {
        "consent_orders": """
FILING CONSENT ORDERS (Form 11)
═══════════════════════════════

PREFERRED METHOD: Commonwealth Courts Portal (comcourts.gov.au)

STEP 1: CREATE ACCOUNTS
   - Both parties need a comcourts.gov.au account
   - Verify email addresses
   - Set up security questions

STEP 2: PREPARE DOCUMENTS
   - Complete Form 11 (all applicable parts)
   - Draft proposed orders
   - Gather any annexures
   - Have documents reviewed if possible

STEP 3: FILE ONLINE
   - Log in to Commonwealth Courts Portal
   - Select "Family Law" → "Consent Orders"
   - Upload Form 11 and attachments
   - Pay filing fee (check current fee at fcfcoa.gov.au)
   - Both parties sign electronically

STEP 4: WAIT FOR REGISTRAR REVIEW
   - Typically 4-8 weeks
   - Registrar checks orders are appropriate
   - You may be contacted for amendments
   - Check portal regularly for updates

STEP 5: IF AMENDMENTS REQUESTED
   - Make the requested changes
   - Resubmit via portal
   - Usually no additional fee

STEP 6: ORDERS MADE
   - Download sealed orders from portal
   - Keep copies safely
   - Orders are now legally binding

ALTERNATIVE: FILE IN PERSON
   - Print 3 copies of all documents
   - Attend court registry
   - Pay filing fee
   - Get stamped copies as receipt
""",
        "affidavit": """
FILING AN AFFIDAVIT
═══════════════════

STEP 1: PREPARE AFFIDAVIT
   - Use Form 14 format
   - Number all paragraphs
   - Prepare annexures
   - Proofread carefully

STEP 2: GET WITNESSED
   - Find authorised witness (JP, lawyer, etc.)
   - Bring ID
   - Sign in front of witness
   - Witness completes jurat

STEP 3: PREPARE ANNEXURES
   - Label each annexure (A, B, C...)
   - Attach annexure certificate to each
   - Have witness sign certificates

STEP 4: FILE
   - Via Commonwealth Courts Portal, or
   - At court registry in person
   - File required number of copies
   - Pay filing fee if applicable

STEP 5: SERVE
   - Serve copy on other party
   - Within time limits set by court
   - Keep proof of service

TIP: Check if affidavit is being filed with an application
     or as a standalone document - this affects requirements.
""",
        "initiating_application": """
FILING AN INITIATING APPLICATION (Form 1)
══════════════════════════════════════════

BEFORE YOU FILE:
   □ Do you have a Family Dispute Resolution certificate?
     (Required unless exemption applies - e.g., family violence)
   □ Have you considered Legal Aid assistance?
   □ Do you know the other party's address for service?

STEP 1: COMPLETE FORM 1
   - All parts that apply to your situation
   - Be specific about orders sought
   - Mark urgency if applicable

STEP 2: PREPARE SUPPORTING DOCUMENTS
   - Affidavit in support (Form 14)
   - Notice of Risk (Form 4) if applicable
   - Financial Statement if property/maintenance
   - FDR certificate (or exemption evidence)

STEP 3: FILE
   - Commonwealth Courts Portal (preferred), or
   - Court registry in person
   - Pay filing fee
   - Get court file number

STEP 4: SERVE ON OTHER PARTY
   - Within time limit (check rules)
   - Personal service may be required
   - Keep proof of service

STEP 5: ATTEND FIRST COURT DATE
   - Date usually set at filing
   - May be directions hearing or mediation
   - Bring all documents

FILING FEES:
   - Check current fees: fcfcoa.gov.au
   - Fee waiver available if financial hardship
""",
    }

    key = document_type.lower().replace(" ", "_").replace("-", "_")

    if key in instructions:
        return instructions[key]

    return f"""
GENERAL FILING INSTRUCTIONS
═══════════════════════════

For '{document_type}':

1. Check you have the correct form at fcfcoa.gov.au
2. Complete all required sections
3. Prepare supporting documents
4. File via Commonwealth Courts Portal or in person
5. Pay applicable filing fee
6. Serve documents on other party as required
7. Keep copies of everything

For specific instructions, contact:
- Court registry: Check fcfcoa.gov.au for your nearest registry
- Legal Aid: Search "[Your State] Legal Aid"
- Family Relationships Advice Line: 1800 050 321
"""


def get_all_forms_summary() -> str:
    """
    Get a summary of all common Family Law forms.

    Returns:
        Formatted string with form numbers and purposes
    """
    return """
╔══════════════════════════════════════════════════════════════════════════════╗
║              FAMILY LAW FORMS - QUICK REFERENCE                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

MAIN APPLICATION FORMS:
━━━━━━━━━━━━━━━━━━━━━━━━
Form 1   │ Initiating Application (Parenting/Property/Both)
Form 2   │ Response to Initiating Application
Form 11  │ Application for Consent Orders
Form 18  │ Contravention Application (breach of orders)

SUPPORTING DOCUMENTS:
━━━━━━━━━━━━━━━━━━━━━━
Form 4   │ Notice of Child Abuse, Family Violence, or Risk
Form 13  │ Financial Statement
Form 14  │ Affidavit

OTHER USEFUL FORMS:
━━━━━━━━━━━━━━━━━━━━
Form 6   │ Application in a Case (general applications)
Form 12  │ Notice of Address for Service
Form 22  │ Subpoena
Form 25  │ Notice of Discontinuance

WHERE TO GET FORMS:
━━━━━━━━━━━━━━━━━━━
• Federal Circuit and Family Court: fcfcoa.gov.au/forms
• Commonwealth Courts Portal: comcourts.gov.au

DISCLAIMER: Form numbers may change. Always check the official
court website for the most current forms.
"""


def search_guidance(search_term: str) -> List[Dict[str, str]]:
    """
    Search across all guidance for a specific term.

    Args:
        search_term: Term to search for

    Returns:
        List of matching sections with document type and excerpt
    """
    all_guidance = {
        "parenting_orders": PARENTING_ORDERS_GUIDANCE,
        "consent_orders": CONSENT_ORDERS_GUIDANCE,
        "affidavit": AFFIDAVIT_GUIDANCE,
        "application": APPLICATION_GUIDANCE,
        "notice_of_risk": NOTICE_OF_RISK_GUIDANCE,
    }

    results = []
    term_lower = search_term.lower()

    for doc_type, content in all_guidance.items():
        if term_lower in content.lower():
            # Find relevant excerpt
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if term_lower in line.lower():
                    # Get surrounding context
                    start = max(0, i - 2)
                    end = min(len(lines), i + 3)
                    excerpt = "\n".join(lines[start:end])
                    results.append(
                        {
                            "document_type": doc_type,
                            "excerpt": excerpt.strip(),
                        }
                    )
                    break  # Only first match per document

    return results


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """
    Display overview and usage examples.
    """
    print(
        """
╔══════════════════════════════════════════════════════════════════════════════╗
║         AUSTRALIAN FAMILY LAW - DOCUMENT TEMPLATES GUIDANCE                  ║
║                                                                              ║
║  ⚠️  DISCLAIMER: This is educational guidance only, NOT legal advice.       ║
║      Always consult a qualified family lawyer for your specific situation.  ║
╚══════════════════════════════════════════════════════════════════════════════╝

AVAILABLE GUIDANCE:
━━━━━━━━━━━━━━━━━━━

1. PARENTING ORDERS
   get_template_guidance('parenting_orders')
   
2. CONSENT ORDERS  
   get_template_guidance('consent_orders')
   
3. AFFIDAVITS
   get_template_guidance('affidavit')
   
4. APPLICATIONS (Initiating, Response, Contravention)
   get_template_guidance('application')
   
5. NOTICE OF RISK
   get_template_guidance('notice_of_risk')

HELPER FUNCTIONS:
━━━━━━━━━━━━━━━━━

• get_checklist('consent_orders')     → Filing checklist
• get_common_mistakes('affidavit')    → What to avoid
• get_filing_instructions('application') → Step-by-step filing
• get_all_forms_summary()             → Form numbers reference
• search_guidance('changeover')       → Search across all guidance

OFFICIAL RESOURCES:
━━━━━━━━━━━━━━━━━━━

• Federal Circuit and Family Court: https://www.fcfcoa.gov.au/
• Commonwealth Courts Portal: https://www.comcourts.gov.au/
• Family Relationships Advice Line: 1800 050 321
• Legal Aid (search "[Your State] Legal Aid")
• 1800 RESPECT (family violence): 1800 737 732
"""
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Education & Tutoring Bot
========================

An AI tutor that helps students with various subjects, generates quizzes,
tracks progress, and creates personalized study plans.

Features:
- Subject Q&A (Math, Science, History, English)
- Progress tracking
- Quiz generation with instant feedback
- Personalized study plan creation
- Concept explanations with examples

Run:
    python examples/45_education_tutor.py

Note:
    This is a demonstration system. For actual educational use,
    content should be verified by qualified educators.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Any

from agentic_brain import Agent

# ============================================================================
# Educational Content Database
# ============================================================================

SUBJECTS = {
    "mathematics": {
        "topics": {
            "algebra": {
                "description": "The study of mathematical symbols and rules for manipulating them",
                "concepts": [
                    {
                        "name": "Linear Equations",
                        "explanation": "An equation that forms a straight line when graphed. In the form ax + b = c.",
                        "example": "Solve: 2x + 5 = 13. Subtract 5 from both sides: 2x = 8. Divide by 2: x = 4.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Quadratic Equations",
                        "explanation": "An equation of degree 2. In the form ax² + bx + c = 0.",
                        "example": "Solve: x² - 5x + 6 = 0. Factor: (x-2)(x-3) = 0. Solutions: x = 2 or x = 3.",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Systems of Equations",
                        "explanation": "Two or more equations with multiple variables solved together.",
                        "example": "Solve: x + y = 10 and x - y = 4. Add equations: 2x = 14, so x = 7, y = 3.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "geometry": {
                "description": "The study of shapes, sizes, and properties of space",
                "concepts": [
                    {
                        "name": "Pythagorean Theorem",
                        "explanation": "In a right triangle, a² + b² = c² where c is the hypotenuse.",
                        "example": "A triangle has legs of 3 and 4. Find the hypotenuse: 3² + 4² = 9 + 16 = 25 = 5².",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Area of Circles",
                        "explanation": "Area = πr² where r is the radius.",
                        "example": "A circle has radius 5. Area = π × 5² = 25π ≈ 78.54 square units.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Volume of Solids",
                        "explanation": "Three-dimensional space occupied by an object.",
                        "example": "Cube with side 3: V = 3³ = 27. Sphere with radius 2: V = (4/3)π(2)³ ≈ 33.51.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "calculus": {
                "description": "The study of continuous change through derivatives and integrals",
                "concepts": [
                    {
                        "name": "Derivatives",
                        "explanation": "The rate of change of a function at any given point.",
                        "example": "If f(x) = x², then f'(x) = 2x. At x=3, the slope is 6.",
                        "difficulty": "advanced",
                    },
                    {
                        "name": "Integrals",
                        "explanation": "The accumulation of quantities, or the area under a curve.",
                        "example": "∫x²dx = (x³/3) + C. The area under x² from 0 to 2 is 8/3.",
                        "difficulty": "advanced",
                    },
                ],
            },
        },
    },
    "science": {
        "topics": {
            "physics": {
                "description": "The study of matter, energy, and their interactions",
                "concepts": [
                    {
                        "name": "Newton's Laws of Motion",
                        "explanation": "Three laws describing the relationship between objects and forces.",
                        "example": "First Law: An object at rest stays at rest unless acted upon by a force.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Conservation of Energy",
                        "explanation": "Energy cannot be created or destroyed, only transformed.",
                        "example": "A falling ball converts potential energy to kinetic energy.",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Electromagnetic Waves",
                        "explanation": "Waves of electric and magnetic fields traveling through space.",
                        "example": "Light, radio waves, and X-rays are all electromagnetic waves.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "chemistry": {
                "description": "The study of matter and the changes it undergoes",
                "concepts": [
                    {
                        "name": "Periodic Table",
                        "explanation": "An arrangement of elements by atomic number and properties.",
                        "example": "Elements in the same column (group) have similar properties.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Chemical Bonding",
                        "explanation": "The force holding atoms together in compounds.",
                        "example": "Ionic bonds transfer electrons (NaCl); covalent bonds share electrons (H₂O).",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Stoichiometry",
                        "explanation": "The calculation of quantities in chemical reactions.",
                        "example": "2H₂ + O₂ → 2H₂O means 2 moles of H₂ react with 1 mole of O₂.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "biology": {
                "description": "The study of living organisms",
                "concepts": [
                    {
                        "name": "Cell Structure",
                        "explanation": "Cells are the basic units of life with various organelles.",
                        "example": "The nucleus contains DNA; mitochondria produce energy; ribosomes make proteins.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "DNA and Genetics",
                        "explanation": "DNA carries genetic information passed through generations.",
                        "example": "DNA is a double helix made of nucleotides (A, T, G, C).",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Evolution",
                        "explanation": "The process of change in species over generations.",
                        "example": "Natural selection: organisms with beneficial traits survive and reproduce more.",
                        "difficulty": "intermediate",
                    },
                ],
            },
        },
    },
    "history": {
        "topics": {
            "ancient_history": {
                "description": "History from the earliest civilizations to the fall of Rome",
                "concepts": [
                    {
                        "name": "Ancient Egypt",
                        "explanation": "Civilization along the Nile River, known for pyramids and pharaohs.",
                        "example": "The Great Pyramid of Giza was built around 2560 BCE for Pharaoh Khufu.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Ancient Greece",
                        "explanation": "Birthplace of democracy, philosophy, and the Olympic Games.",
                        "example": "Athens developed democracy around 508 BCE under Cleisthenes.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Roman Empire",
                        "explanation": "One of history's largest empires, influential in law and architecture.",
                        "example": "At its peak under Trajan (117 CE), Rome controlled the Mediterranean.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "world_wars": {
                "description": "The two major global conflicts of the 20th century",
                "concepts": [
                    {
                        "name": "World War I",
                        "explanation": "Global war from 1914-1918, fought mainly in Europe.",
                        "example": "Triggered by the assassination of Archduke Franz Ferdinand in 1914.",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "World War II",
                        "explanation": "Global war from 1939-1945 involving most of the world's nations.",
                        "example": "Began with Germany's invasion of Poland; ended after atomic bombs on Japan.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "american_history": {
                "description": "History of the United States of America",
                "concepts": [
                    {
                        "name": "American Revolution",
                        "explanation": "The war for independence from Britain (1775-1783).",
                        "example": "Declaration of Independence signed July 4, 1776.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Civil War",
                        "explanation": "Conflict between Northern and Southern states (1861-1865).",
                        "example": "Fought over slavery and states' rights; led to abolition of slavery.",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Civil Rights Movement",
                        "explanation": "Movement for racial equality in the 1950s-1960s.",
                        "example": "Martin Luther King Jr.'s 'I Have a Dream' speech was delivered in 1963.",
                        "difficulty": "intermediate",
                    },
                ],
            },
        },
    },
    "english": {
        "topics": {
            "grammar": {
                "description": "The rules of language structure",
                "concepts": [
                    {
                        "name": "Parts of Speech",
                        "explanation": "Eight categories: nouns, verbs, adjectives, adverbs, pronouns, prepositions, conjunctions, interjections.",
                        "example": "'The quick brown fox jumps over the lazy dog' - contains all parts of speech.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Sentence Structure",
                        "explanation": "How words are organized into sentences.",
                        "example": "Simple: 'I ran.' Compound: 'I ran, and she walked.' Complex: 'When I ran, she walked.'",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Punctuation",
                        "explanation": "Marks that clarify meaning and separate structural units.",
                        "example": "'Let's eat, Grandma' vs 'Let's eat Grandma' - commas save lives!",
                        "difficulty": "beginner",
                    },
                ],
            },
            "literature": {
                "description": "The study of written works",
                "concepts": [
                    {
                        "name": "Literary Devices",
                        "explanation": "Techniques authors use to convey meaning.",
                        "example": "Metaphor: 'Life is a journey.' Simile: 'Life is like a journey.'",
                        "difficulty": "intermediate",
                    },
                    {
                        "name": "Theme Analysis",
                        "explanation": "Identifying central ideas in a work of literature.",
                        "example": "In 'To Kill a Mockingbird', themes include justice, racism, and coming of age.",
                        "difficulty": "intermediate",
                    },
                ],
            },
            "writing": {
                "description": "The craft of written expression",
                "concepts": [
                    {
                        "name": "Essay Structure",
                        "explanation": "Introduction, body paragraphs, and conclusion.",
                        "example": "Introduction: hook, context, thesis. Body: topic sentence, evidence, analysis. Conclusion: restate, synthesize.",
                        "difficulty": "beginner",
                    },
                    {
                        "name": "Thesis Statements",
                        "explanation": "A clear statement of the main argument or point.",
                        "example": "Weak: 'This essay is about dogs.' Strong: 'Dogs make better pets than cats because...'",
                        "difficulty": "intermediate",
                    },
                ],
            },
        },
    },
}

# Student progress storage
student_progress = {
    "quizzes_taken": 0,
    "quizzes_passed": 0,
    "topics_studied": [],
    "quiz_history": [],
    "weak_areas": [],
    "strong_areas": [],
    "total_questions": 0,
    "correct_answers": 0,
}


# ============================================================================
# Education Tools
# ============================================================================


def get_subject_overview(subject: str) -> dict[str, Any]:
    """
    Get an overview of available topics in a subject.

    Args:
        subject: Subject name (mathematics, science, history, english)

    Returns:
        Subject overview with available topics
    """
    subject = subject.lower()

    if subject not in SUBJECTS:
        return {
            "error": f"Subject '{subject}' not found",
            "available_subjects": list(SUBJECTS.keys()),
        }

    subject_data = SUBJECTS[subject]
    topics_info = []

    for topic_name, topic_data in subject_data["topics"].items():
        topics_info.append(
            {
                "topic": topic_name.replace("_", " ").title(),
                "description": topic_data["description"],
                "concept_count": len(topic_data["concepts"]),
            }
        )

    return {
        "subject": subject.title(),
        "topics": topics_info,
        "total_concepts": sum(
            len(t["concepts"]) for t in subject_data["topics"].values()
        ),
    }


def explain_concept(
    subject: str, topic: str, concept_name: str = None
) -> dict[str, Any]:
    """
    Get a detailed explanation of a concept.

    Args:
        subject: Subject name
        topic: Topic within the subject
        concept_name: Specific concept (optional - returns all if not specified)

    Returns:
        Concept explanation with examples
    """
    subject = subject.lower()
    topic = topic.lower().replace(" ", "_")

    if subject not in SUBJECTS:
        return {"error": f"Subject '{subject}' not found"}

    if topic not in SUBJECTS[subject]["topics"]:
        return {
            "error": f"Topic '{topic}' not found in {subject}",
            "available_topics": list(SUBJECTS[subject]["topics"].keys()),
        }

    topic_data = SUBJECTS[subject]["topics"][topic]

    if concept_name:
        for concept in topic_data["concepts"]:
            if concept_name.lower() in concept["name"].lower():
                # Track progress
                if topic not in student_progress["topics_studied"]:
                    student_progress["topics_studied"].append(topic)

                return {
                    "concept": concept,
                    "study_tip": "Try working through the example step by step.",
                    "next_steps": [
                        "Generate a quiz to test your understanding",
                        "Explore related concepts",
                    ],
                }
        return {"error": f"Concept '{concept_name}' not found in {topic}"}

    return {
        "topic": topic.replace("_", " ").title(),
        "description": topic_data["description"],
        "concepts": topic_data["concepts"],
    }


def generate_quiz(
    subject: str,
    topic: str = None,
    difficulty: str = "mixed",
    num_questions: int = 5,
) -> dict[str, Any]:
    """
    Generate a quiz on a subject/topic.

    Args:
        subject: Subject name
        topic: Specific topic (optional)
        difficulty: beginner, intermediate, advanced, or mixed
        num_questions: Number of questions

    Returns:
        Quiz with questions
    """
    subject = subject.lower()

    if subject not in SUBJECTS:
        return {"error": f"Subject '{subject}' not found"}

    # Gather concepts
    concepts = []
    for topic_name, topic_data in SUBJECTS[subject]["topics"].items():
        if topic and topic.lower().replace(" ", "_") != topic_name:
            continue
        for concept in topic_data["concepts"]:
            if difficulty == "mixed" or concept["difficulty"] == difficulty:
                concepts.append({**concept, "topic": topic_name})

    if not concepts:
        return {"error": "No concepts found matching criteria"}

    # Generate questions
    questions = []
    used_concepts = random.sample(concepts, min(num_questions, len(concepts)))

    for i, concept in enumerate(used_concepts, 1):
        question = {
            "number": i,
            "topic": concept["topic"].replace("_", " ").title(),
            "concept": concept["name"],
            "question": f"What is the key principle of {concept['name']}?",
            "hint": concept["explanation"][:50] + "...",
            "correct_answer": concept["explanation"],
            "difficulty": concept["difficulty"],
        }
        questions.append(question)

    quiz_id = f"QUIZ{random.randint(1000, 9999)}"

    return {
        "quiz_id": quiz_id,
        "subject": subject.title(),
        "topic": topic.replace("_", " ").title() if topic else "Multiple Topics",
        "difficulty": difficulty,
        "num_questions": len(questions),
        "questions": questions,
        "instructions": [
            "Read each question carefully",
            "Use the hint if you need help",
            "Submit your answers using the submit_quiz function",
        ],
    }


def submit_quiz(quiz_id: str, answers: list[str]) -> dict[str, Any]:
    """
    Submit quiz answers and get feedback.

    Args:
        quiz_id: The quiz ID
        answers: List of answer strings

    Returns:
        Quiz results with feedback
    """
    # In a real system, we'd look up the quiz and validate answers
    # For demo, we'll simulate grading
    num_questions = len(answers)
    correct = random.randint(int(num_questions * 0.5), num_questions)
    score = round(correct / num_questions * 100, 1)
    passed = score >= 70

    # Update progress
    student_progress["quizzes_taken"] += 1
    if passed:
        student_progress["quizzes_passed"] += 1
    student_progress["total_questions"] += num_questions
    student_progress["correct_answers"] += correct

    student_progress["quiz_history"].append(
        {
            "quiz_id": quiz_id,
            "score": score,
            "passed": passed,
            "date": datetime.now().isoformat(),
        }
    )

    feedback = []
    for i, answer in enumerate(answers, 1):
        feedback.append(
            {
                "question": i,
                "your_answer": answer[:100] if answer else "No answer",
                "correct": random.choice([True, False, True]),  # Simulated
                "feedback": (
                    "Good understanding!"
                    if random.random() > 0.3
                    else "Review this concept."
                ),
            }
        )

    return {
        "quiz_id": quiz_id,
        "score": score,
        "passed": passed,
        "correct_answers": correct,
        "total_questions": num_questions,
        "feedback": feedback,
        "encouragement": (
            "Great job!" if passed else "Keep practicing! You're improving."
        ),
        "recommendation": (
            "Try a harder topic!"
            if score > 90
            else "Review weak areas before moving on."
        ),
    }


def get_progress() -> dict[str, Any]:
    """
    Get student's learning progress.

    Returns:
        Progress statistics and recommendations
    """
    if student_progress["total_questions"] == 0:
        accuracy = 0
    else:
        accuracy = round(
            student_progress["correct_answers"]
            / student_progress["total_questions"]
            * 100,
            1,
        )

    if student_progress["quizzes_taken"] == 0:
        pass_rate = 0
    else:
        pass_rate = round(
            student_progress["quizzes_passed"]
            / student_progress["quizzes_taken"]
            * 100,
            1,
        )

    return {
        "summary": {
            "quizzes_taken": student_progress["quizzes_taken"],
            "quizzes_passed": student_progress["quizzes_passed"],
            "pass_rate": f"{pass_rate}%",
            "overall_accuracy": f"{accuracy}%",
            "topics_studied": len(student_progress["topics_studied"]),
        },
        "topics_studied": student_progress["topics_studied"],
        "recent_quizzes": student_progress["quiz_history"][-5:],
        "recommendations": _generate_recommendations(),
    }


def _generate_recommendations() -> list[str]:
    """Generate personalized study recommendations."""
    recs = []

    if student_progress["quizzes_taken"] == 0:
        recs.append("Start with a beginner quiz to assess your level")
        recs.append("Explore different subjects to find your interests")
    elif (
        student_progress["correct_answers"]
        / max(1, student_progress["total_questions"])
        < 0.7
    ):
        recs.append("Focus on reviewing fundamental concepts")
        recs.append("Take more beginner-level quizzes before advancing")
    else:
        recs.append("You're doing great! Try intermediate topics")
        recs.append("Challenge yourself with cross-topic quizzes")

    return recs


def create_study_plan(
    subject: str,
    goal: str,
    hours_per_week: int = 5,
    weeks: int = 4,
) -> dict[str, Any]:
    """
    Create a personalized study plan.

    Args:
        subject: Subject to study
        goal: Learning goal (e.g., "Master algebra basics")
        hours_per_week: Available study hours per week
        weeks: Duration of the plan

    Returns:
        Week-by-week study plan
    """
    subject = subject.lower()

    if subject not in SUBJECTS:
        return {"error": f"Subject '{subject}' not found"}

    topics = list(SUBJECTS[subject]["topics"].keys())

    plan = []
    for week in range(1, weeks + 1):
        topic_index = (week - 1) % len(topics)
        topic = topics[topic_index]
        topic_data = SUBJECTS[subject]["topics"][topic]

        week_plan = {
            "week": week,
            "topic": topic.replace("_", " ").title(),
            "hours": hours_per_week,
            "activities": [
                {
                    "day": "Day 1-2",
                    "activity": "Read and understand core concepts",
                    "duration": f"{hours_per_week // 3}h",
                },
                {
                    "day": "Day 3-4",
                    "activity": "Practice with examples and exercises",
                    "duration": f"{hours_per_week // 3}h",
                },
                {
                    "day": "Day 5-7",
                    "activity": "Take quizzes and review weak areas",
                    "duration": f"{hours_per_week // 3}h",
                },
            ],
            "concepts_to_cover": [c["name"] for c in topic_data["concepts"]],
            "milestone": f"Complete {topic.replace('_', ' ')} section with 80%+ quiz score",
        }
        plan.append(week_plan)

    return {
        "subject": subject.title(),
        "goal": goal,
        "duration": f"{weeks} weeks",
        "weekly_commitment": f"{hours_per_week} hours",
        "total_hours": hours_per_week * weeks,
        "weekly_plan": plan,
        "tips": [
            "Consistency is key - study a little each day",
            "Take breaks every 25-30 minutes (Pomodoro technique)",
            "Review previous material before learning new concepts",
            "Use quizzes to identify and address weak areas",
        ],
    }


def ask_question(question: str, subject: str = None) -> dict[str, Any]:
    """
    Ask a subject-related question.

    Args:
        question: The question to answer
        subject: Optional subject context

    Returns:
        Answer with explanation
    """
    # Search for relevant concept
    question_lower = question.lower()

    for subj_name, subj_data in SUBJECTS.items():
        if subject and subj_name != subject.lower():
            continue
        for topic_name, topic_data in subj_data["topics"].items():
            for concept in topic_data["concepts"]:
                if any(
                    word in question_lower for word in concept["name"].lower().split()
                ):
                    return {
                        "found_concept": concept["name"],
                        "subject": subj_name.title(),
                        "topic": topic_name.replace("_", " ").title(),
                        "explanation": concept["explanation"],
                        "example": concept["example"],
                        "related_topics": [
                            c["name"] for c in topic_data["concepts"] if c != concept
                        ][:3],
                    }

    return {
        "message": "I couldn't find a specific concept matching your question.",
        "suggestion": "Try browsing subjects with get_subject_overview or being more specific.",
        "available_subjects": list(SUBJECTS.keys()),
    }


def get_flashcards(subject: str, topic: str = None, count: int = 10) -> dict[str, Any]:
    """
    Generate flashcards for studying.

    Args:
        subject: Subject name
        topic: Specific topic (optional)
        count: Number of flashcards

    Returns:
        Set of flashcards
    """
    subject = subject.lower()

    if subject not in SUBJECTS:
        return {"error": f"Subject '{subject}' not found"}

    cards = []
    for topic_name, topic_data in SUBJECTS[subject]["topics"].items():
        if topic and topic.lower().replace(" ", "_") != topic_name:
            continue
        for concept in topic_data["concepts"]:
            cards.append(
                {
                    "front": f"What is {concept['name']}?",
                    "back": concept["explanation"],
                    "topic": topic_name.replace("_", " ").title(),
                    "difficulty": concept["difficulty"],
                }
            )

    # Shuffle and limit
    random.shuffle(cards)
    cards = cards[:count]

    return {
        "subject": subject.title(),
        "topic": topic.replace("_", " ").title() if topic else "Multiple Topics",
        "card_count": len(cards),
        "flashcards": cards,
        "study_tip": "Try to answer before flipping the card!",
    }


def get_practice_problems(subject: str, topic: str, count: int = 5) -> dict[str, Any]:
    """
    Get practice problems for a topic.

    Args:
        subject: Subject name
        topic: Topic name
        count: Number of problems

    Returns:
        Practice problems with solutions
    """
    subject = subject.lower()
    topic = topic.lower().replace(" ", "_")

    if subject not in SUBJECTS:
        return {"error": f"Subject '{subject}' not found"}

    if topic not in SUBJECTS[subject]["topics"]:
        return {"error": f"Topic '{topic}' not found"}

    # Generate problems based on topic
    problems = []

    if subject == "mathematics":
        if topic == "algebra":
            for i in range(count):
                a, b, c = (
                    random.randint(1, 10),
                    random.randint(1, 20),
                    random.randint(1, 50),
                )
                problems.append(
                    {
                        "problem": f"Solve for x: {a}x + {b} = {c}",
                        "solution": f"x = ({c} - {b}) / {a} = {(c - b) / a:.2f}",
                        "difficulty": "beginner",
                    }
                )
        elif topic == "geometry":
            for i in range(count):
                r = random.randint(1, 10)
                problems.append(
                    {
                        "problem": f"Find the area of a circle with radius {r}",
                        "solution": f"Area = π × {r}² = {3.14159 * r * r:.2f}",
                        "difficulty": "beginner",
                    }
                )
    else:
        # Generic practice questions
        topic_data = SUBJECTS[subject]["topics"][topic]
        for concept in topic_data["concepts"][:count]:
            problems.append(
                {
                    "problem": f"Explain the concept of {concept['name']}",
                    "solution": concept["explanation"],
                    "example": concept["example"],
                    "difficulty": concept["difficulty"],
                }
            )

    return {
        "subject": subject.title(),
        "topic": topic.replace("_", " ").title(),
        "problem_count": len(problems),
        "problems": problems,
        "tip": "Work through each problem step by step before checking the solution.",
    }


# ============================================================================
# Agent Configuration
# ============================================================================

EDUCATION_TOOLS = [
    {
        "name": "get_subject_overview",
        "description": "Get an overview of topics available in a subject (mathematics, science, history, english)",
        "function": get_subject_overview,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject name"},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "explain_concept",
        "description": "Get a detailed explanation of a concept with examples",
        "function": explain_concept,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject name"},
                "topic": {"type": "string", "description": "Topic within the subject"},
                "concept_name": {
                    "type": "string",
                    "description": "Specific concept name",
                },
            },
            "required": ["subject", "topic"],
        },
    },
    {
        "name": "generate_quiz",
        "description": "Generate a quiz to test knowledge on a subject or topic",
        "function": generate_quiz,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject name"},
                "topic": {"type": "string", "description": "Specific topic"},
                "difficulty": {
                    "type": "string",
                    "description": "beginner, intermediate, advanced, or mixed",
                },
                "num_questions": {
                    "type": "integer",
                    "description": "Number of questions",
                },
            },
            "required": ["subject"],
        },
    },
    {
        "name": "submit_quiz",
        "description": "Submit quiz answers and get feedback",
        "function": submit_quiz,
        "parameters": {
            "type": "object",
            "properties": {
                "quiz_id": {"type": "string", "description": "Quiz ID"},
                "answers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of answers",
                },
            },
            "required": ["quiz_id", "answers"],
        },
    },
    {
        "name": "get_progress",
        "description": "Get student's learning progress and statistics",
        "function": get_progress,
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "create_study_plan",
        "description": "Create a personalized study plan",
        "function": create_study_plan,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject to study"},
                "goal": {"type": "string", "description": "Learning goal"},
                "hours_per_week": {
                    "type": "integer",
                    "description": "Available study hours per week",
                },
                "weeks": {"type": "integer", "description": "Duration in weeks"},
            },
            "required": ["subject", "goal"],
        },
    },
    {
        "name": "ask_question",
        "description": "Ask a question about any subject topic",
        "function": ask_question,
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "The question"},
                "subject": {"type": "string", "description": "Subject context"},
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_flashcards",
        "description": "Generate flashcards for studying",
        "function": get_flashcards,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject name"},
                "topic": {"type": "string", "description": "Specific topic"},
                "count": {"type": "integer", "description": "Number of flashcards"},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "get_practice_problems",
        "description": "Get practice problems with solutions",
        "function": get_practice_problems,
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Subject name"},
                "topic": {"type": "string", "description": "Topic name"},
                "count": {"type": "integer", "description": "Number of problems"},
            },
            "required": ["subject", "topic"],
        },
    },
]

SYSTEM_PROMPT = """You are a friendly and encouraging educational tutor helping students learn.

Your capabilities:
- Explain concepts in mathematics, science, history, and english
- Generate quizzes to test understanding
- Track student progress
- Create personalized study plans
- Provide flashcards and practice problems
- Answer subject-related questions

Guidelines:
- Be patient and encouraging with students
- Break down complex concepts into simple steps
- Use examples to illustrate points
- Celebrate progress and improvement
- Suggest next steps based on performance
- Adapt explanations to the student's level
- Always encourage questions and curiosity

Available subjects: Mathematics (Algebra, Geometry, Calculus), Science (Physics, Chemistry, Biology),
History (Ancient, World Wars, American), English (Grammar, Literature, Writing)

Remember: Every question is a good question! Learning is a journey."""


# ============================================================================
# Main Application
# ============================================================================


async def main():
    """Run the Education & Tutoring Bot."""
    print("=" * 60)
    print("📚 Education & Tutoring Bot")
    print("=" * 60)
    print("\nHi there! I'm your personal tutor. I can help you with:")
    print("  • Mathematics (Algebra, Geometry, Calculus)")
    print("  • Science (Physics, Chemistry, Biology)")
    print("  • History (Ancient, World Wars, American)")
    print("  • English (Grammar, Literature, Writing)")
    print("\n💡 Try asking:")
    print('  "Explain the Pythagorean theorem"')
    print('  "Give me a math quiz"')
    print('  "Create a study plan for chemistry"')
    print('  "How did World War I start?"')
    print("\nType 'quit' to exit")
    print("-" * 60)

    # Create agent
    agent = Agent(
        name="education_tutor",
        system_prompt=SYSTEM_PROMPT,
        tools=EDUCATION_TOOLS,
    )

    try:
        while True:
            user_input = input("\n📖 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Great studying today! Keep up the good work!")
                break

            # Special commands
            if user_input.lower() == "subjects":
                print("\n📚 Available Subjects:")
                for subj in SUBJECTS:
                    print(f"  • {subj.title()}")
                continue

            if user_input.lower() == "progress":
                prog = get_progress()
                print("\n📊 Your Progress:")
                print(f"  Quizzes taken: {prog['summary']['quizzes_taken']}")
                print(f"  Pass rate: {prog['summary']['pass_rate']}")
                print(f"  Accuracy: {prog['summary']['overall_accuracy']}")
                continue

            # Get response from agent
            response = await agent.chat_async(user_input)
            print(f"\n🎓 Tutor: {response}")

    except KeyboardInterrupt:
        print("\n\n👋 Happy learning!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

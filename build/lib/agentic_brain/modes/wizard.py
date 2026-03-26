# Copyright 2026 Joseph Webber
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
Mode Wizard - Interactive mode recommendation system.

Asks 3-5 questions to determine the best mode for a user's needs,
considering use case, industry, security requirements, and scale.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .base import Mode, ModeCategory, SecurityLevel
from .registry import MODE_REGISTRY, list_modes, MODES_BY_CATEGORY
from .manager import ModeManager, get_manager


class WizardStep(Enum):
    """Wizard question steps."""
    USE_CASE = "use_case"
    INDUSTRY = "industry"
    SECURITY = "security"
    SCALE = "scale"
    FEATURES = "features"


@dataclass
class WizardQuestion:
    """A wizard question with options."""
    step: WizardStep
    question: str
    options: List[Tuple[str, str, int]]  # (code, label, score_weight)
    required: bool = True


@dataclass
class WizardAnswer:
    """User's answer to a wizard question."""
    step: WizardStep
    selected_code: str
    selected_label: str


@dataclass
class ModeRecommendation:
    """Wizard's mode recommendation."""
    mode: Mode
    score: float  # 0-100 confidence score
    reasons: List[str]
    alternatives: List[Tuple[Mode, float]]  # (mode, score) pairs


class ModeWizard:
    """
    Interactive wizard that recommends the best mode.
    
    Asks 3-5 strategic questions to understand user needs
    and recommends the optimal mode configuration.
    
    Example (interactive):
        wizard = ModeWizard()
        wizard.start()
        # User answers questions...
        recommendation = wizard.recommend()
        
    Example (programmatic):
        wizard = ModeWizard()
        wizard.answer(WizardStep.USE_CASE, "development")
        wizard.answer(WizardStep.SCALE, "team")
        recommendation = wizard.recommend()
    """
    
    QUESTIONS: List[WizardQuestion] = [
        WizardQuestion(
            step=WizardStep.USE_CASE,
            question="What's your primary use case?",
            options=[
                ("personal", "🏠 Personal/Home use", 1),
                ("development", "👨‍💻 Software development", 2),
                ("business", "💼 Business operations", 3),
                ("research", "🔬 Research/Academic", 4),
                ("creative", "🎨 Content creation", 5),
                ("enterprise", "🏢 Enterprise deployment", 6),
            ],
        ),
        WizardQuestion(
            step=WizardStep.INDUSTRY,
            question="Which industry are you in?",
            options=[
                ("general", "🌐 General / Not specific", 0),
                ("healthcare", "🏥 Healthcare / Medical", 1),
                ("finance", "🏦 Banking / Finance", 2),
                ("legal", "⚖️ Legal", 3),
                ("education", "🎓 Education", 4),
                ("government", "🏛️ Government", 5),
                ("retail", "🛍️ Retail / E-commerce", 6),
                ("tech", "💻 Technology", 7),
                ("manufacturing", "🏭 Manufacturing", 8),
                ("media", "🎬 Media / Entertainment", 9),
            ],
            required=False,
        ),
        WizardQuestion(
            step=WizardStep.SECURITY,
            question="What level of security do you need?",
            options=[
                ("basic", "🟢 Basic - Standard security", 1),
                ("moderate", "🟡 Moderate - Some compliance needs", 2),
                ("high", "🟠 High - Regulatory compliance (HIPAA, GDPR)", 3),
                ("maximum", "🔴 Maximum - Air-gapped / Military-grade", 4),
            ],
        ),
        WizardQuestion(
            step=WizardStep.SCALE,
            question="What scale are you operating at?",
            options=[
                ("individual", "👤 Individual / Personal", 1),
                ("team", "👥 Small team (2-10 people)", 2),
                ("department", "🏬 Department (10-50 people)", 3),
                ("organization", "🏢 Organization (50-500 people)", 4),
                ("enterprise", "🌐 Enterprise (500+ people)", 5),
            ],
        ),
        WizardQuestion(
            step=WizardStep.FEATURES,
            question="What features are most important?",
            options=[
                ("speed", "⚡ Speed and performance", 1),
                ("accuracy", "🎯 Accuracy and reliability", 2),
                ("compliance", "📋 Compliance and audit", 3),
                ("integration", "🔗 Integration capabilities", 4),
                ("multiagent", "🤖 Multi-agent orchestration", 5),
                ("everything", "🚀 Everything - Maximum capability", 6),
            ],
            required=False,
        ),
    ]
    
    # Scoring matrix: (answer_code, mode_name) -> score boost
    SCORING_MATRIX: Dict[Tuple[str, str], int] = {
        # Use case -> Mode mappings
        ("personal", "home"): 50,
        ("personal", "free"): 40,
        ("development", "developer"): 50,
        ("development", "startup"): 30,
        ("business", "business"): 50,
        ("business", "enterprise"): 30,
        ("research", "research"): 50,
        ("creative", "creator"): 50,
        ("enterprise", "enterprise"): 50,
        ("enterprise", "cluster"): 30,
        
        # Industry -> Mode mappings
        ("healthcare", "medical"): 60,
        ("healthcare", "hipaa"): 40,
        ("finance", "banking"): 60,
        ("finance", "sox"): 40,
        ("legal", "legal"): 60,
        ("education", "education"): 60,
        ("government", "government"): 60,
        ("retail", "retail"): 60,
        ("tech", "developer"): 30,
        ("tech", "startup"): 30,
        ("manufacturing", "manufacturing"): 60,
        ("media", "media"): 60,
        ("media", "creator"): 30,
        
        # Security -> Mode mappings
        ("basic", "free"): 20,
        ("basic", "home"): 20,
        ("moderate", "business"): 20,
        ("moderate", "enterprise"): 20,
        ("high", "hipaa"): 40,
        ("high", "gdpr"): 40,
        ("high", "sox"): 40,
        ("maximum", "military"): 50,
        ("maximum", "airlock"): 50,
        
        # Scale -> Mode mappings
        ("individual", "free"): 20,
        ("individual", "home"): 20,
        ("individual", "developer"): 20,
        ("team", "startup"): 20,
        ("team", "developer"): 20,
        ("department", "business"): 20,
        ("organization", "enterprise"): 30,
        ("enterprise", "enterprise"): 40,
        ("enterprise", "cluster"): 30,
        ("enterprise", "microservices"): 30,
        
        # Features -> Mode mappings
        ("speed", "ludicrous"): 40,
        ("speed", "plaid"): 30,
        ("accuracy", "research"): 30,
        ("accuracy", "legal"): 30,
        ("compliance", "hipaa"): 30,
        ("compliance", "gdpr"): 30,
        ("compliance", "sox"): 30,
        ("compliance", "apra"): 30,
        ("integration", "microservices"): 30,
        ("integration", "hybrid"): 30,
        ("multiagent", "swarm"): 40,
        ("multiagent", "ludicrous"): 30,
        ("everything", "ludicrous"): 50,
        ("everything", "plaid"): 60,
    }
    
    def __init__(self):
        """Initialize the wizard."""
        self._answers: Dict[WizardStep, WizardAnswer] = {}
        self._current_step = 0
        self._completed = False
    
    def start(self) -> WizardQuestion:
        """Start the wizard and return the first question."""
        self._answers.clear()
        self._current_step = 0
        self._completed = False
        return self.QUESTIONS[0]
    
    def current_question(self) -> Optional[WizardQuestion]:
        """Get the current question."""
        if self._current_step < len(self.QUESTIONS):
            return self.QUESTIONS[self._current_step]
        return None
    
    def answer(self, step: WizardStep, selected_code: str) -> Optional[WizardQuestion]:
        """
        Record an answer and return the next question.
        
        Args:
            step: Which step this answer is for
            selected_code: The selected option code
            
        Returns:
            Next question, or None if wizard is complete
        """
        # Find the question
        question = None
        for q in self.QUESTIONS:
            if q.step == step:
                question = q
                break
        
        if not question:
            raise ValueError(f"Unknown step: {step}")
        
        # Find the selected option
        selected_label = None
        for code, label, _ in question.options:
            if code == selected_code:
                selected_label = label
                break
        
        if not selected_label:
            raise ValueError(f"Unknown option: {selected_code}")
        
        # Record the answer
        self._answers[step] = WizardAnswer(
            step=step,
            selected_code=selected_code,
            selected_label=selected_label,
        )
        
        # Move to next step
        self._current_step += 1
        
        # Check if we have enough to recommend
        required_answered = all(
            q.step in self._answers
            for q in self.QUESTIONS
            if q.required
        )
        
        if required_answered and self._current_step >= 3:
            # Can recommend after 3 required questions
            self._completed = True
        
        # Return next question or None
        if self._current_step < len(self.QUESTIONS):
            return self.QUESTIONS[self._current_step]
        
        self._completed = True
        return None
    
    def answer_quick(self, **kwargs) -> 'ModeWizard':
        """
        Quick answer multiple questions at once.
        
        Example:
            wizard.answer_quick(
                use_case="development",
                security="moderate",
                scale="team"
            )
        """
        step_mapping = {
            "use_case": WizardStep.USE_CASE,
            "industry": WizardStep.INDUSTRY,
            "security": WizardStep.SECURITY,
            "scale": WizardStep.SCALE,
            "features": WizardStep.FEATURES,
        }
        
        for key, value in kwargs.items():
            if key in step_mapping:
                try:
                    self.answer(step_mapping[key], value)
                except ValueError:
                    pass  # Skip invalid answers
        
        return self
    
    def can_recommend(self) -> bool:
        """Check if we have enough answers to make a recommendation."""
        required_answered = sum(
            1 for q in self.QUESTIONS
            if q.required and q.step in self._answers
        )
        return required_answered >= 3
    
    def recommend(self) -> ModeRecommendation:
        """
        Generate a mode recommendation based on answers.
        
        Returns:
            ModeRecommendation with best mode and alternatives
        """
        if not self.can_recommend():
            raise ValueError("Not enough answers to make a recommendation")
        
        # Score each mode
        scores: Dict[str, float] = {}
        
        for mode_name, mode in MODE_REGISTRY.items():
            score = 10.0  # Base score
            
            # Apply scoring matrix
            for answer in self._answers.values():
                key = (answer.selected_code, mode_name)
                if key in self.SCORING_MATRIX:
                    score += self.SCORING_MATRIX[key]
            
            scores[mode_name] = score
        
        # Sort by score
        sorted_modes = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Best mode
        best_name, best_score = sorted_modes[0]
        best_mode = MODE_REGISTRY[best_name]
        
        # Normalize score to 0-100
        max_possible = 200  # Rough maximum
        normalized_score = min(100.0, (best_score / max_possible) * 100)
        
        # Generate reasons
        reasons = self._generate_reasons(best_mode)
        
        # Get alternatives
        alternatives = [
            (MODE_REGISTRY[name], min(100.0, (score / max_possible) * 100))
            for name, score in sorted_modes[1:4]
        ]
        
        return ModeRecommendation(
            mode=best_mode,
            score=round(normalized_score, 1),
            reasons=reasons,
            alternatives=alternatives,
        )
    
    def _generate_reasons(self, mode: Mode) -> List[str]:
        """Generate human-readable reasons for the recommendation."""
        reasons = []
        
        # Based on answers
        if WizardStep.USE_CASE in self._answers:
            answer = self._answers[WizardStep.USE_CASE]
            reasons.append(f"Optimized for {answer.selected_label.split(' ', 1)[-1]}")
        
        if WizardStep.INDUSTRY in self._answers:
            answer = self._answers[WizardStep.INDUSTRY]
            if answer.selected_code != "general":
                reasons.append(f"Industry-specific features for {answer.selected_label.split(' ', 1)[-1]}")
        
        if WizardStep.SECURITY in self._answers:
            answer = self._answers[WizardStep.SECURITY]
            if answer.selected_code in ("high", "maximum"):
                reasons.append(f"Enhanced security: {mode.config.security.level.value}")
        
        # Based on mode features
        if mode.config.rag.rag_type.value == "graphrag":
            reasons.append("GraphRAG knowledge retrieval enabled")
        
        if mode.config.llm.reasoning_enabled:
            reasons.append("Advanced reasoning capabilities")
        
        if mode.config.compliance.frameworks:
            reasons.append(f"Compliance: {', '.join(mode.config.compliance.frameworks)}")
        
        return reasons[:5]  # Max 5 reasons
    
    def skip(self) -> Optional[WizardQuestion]:
        """Skip the current question and move to next."""
        if self._current_step < len(self.QUESTIONS):
            self._current_step += 1
        
        if self._current_step < len(self.QUESTIONS):
            return self.QUESTIONS[self._current_step]
        
        self._completed = True
        return None
    
    def reset(self) -> None:
        """Reset the wizard to start over."""
        self._answers.clear()
        self._current_step = 0
        self._completed = False
    
    @property
    def is_completed(self) -> bool:
        """Check if wizard has completed all questions."""
        return self._completed
    
    @property
    def progress(self) -> Tuple[int, int]:
        """Get progress as (current, total)."""
        return (len(self._answers), len(self.QUESTIONS))
    
    def get_answers(self) -> Dict[str, str]:
        """Get all answers as a simple dict."""
        return {
            answer.step.value: answer.selected_code
            for answer in self._answers.values()
        }


def quick_recommend(
    use_case: str = "development",
    industry: str = "general",
    security: str = "moderate",
    scale: str = "team",
    features: str = "speed",
) -> ModeRecommendation:
    """
    Quick recommendation without interactive wizard.
    
    Args:
        use_case: personal, development, business, research, creative, enterprise
        industry: general, healthcare, finance, legal, education, etc.
        security: basic, moderate, high, maximum
        scale: individual, team, department, organization, enterprise
        features: speed, accuracy, compliance, integration, multiagent, everything
        
    Returns:
        ModeRecommendation
    """
    wizard = ModeWizard()
    wizard.answer_quick(
        use_case=use_case,
        industry=industry,
        security=security,
        scale=scale,
        features=features,
    )
    return wizard.recommend()


def interactive_wizard() -> Optional[Mode]:
    """
    Run interactive wizard in the terminal.
    
    Returns:
        Selected Mode, or None if cancelled
    """
    wizard = ModeWizard()
    print("\n🧙 Agentic Brain Mode Wizard")
    print("=" * 40)
    print("I'll ask a few questions to find the perfect mode for you.\n")
    
    question = wizard.start()
    
    while question:
        print(f"\n📋 {question.question}")
        print("-" * 40)
        
        for i, (code, label, _) in enumerate(question.options, 1):
            print(f"  {i}. {label}")
        
        if not question.required:
            print(f"  0. Skip this question")
        
        try:
            choice = input("\nEnter number: ").strip()
            
            if choice == "0" and not question.required:
                question = wizard.skip()
                continue
            
            idx = int(choice) - 1
            if 0 <= idx < len(question.options):
                selected_code = question.options[idx][0]
                question = wizard.answer(question.step, selected_code)
            else:
                print("❌ Invalid choice, try again.")
                
        except (ValueError, KeyboardInterrupt):
            print("\n\n❌ Wizard cancelled.")
            return None
    
    # Generate recommendation
    print("\n" + "=" * 40)
    print("🎯 RECOMMENDATION")
    print("=" * 40)
    
    rec = wizard.recommend()
    
    print(f"\n{rec.mode.icon} **{rec.mode.name}** (Code: {rec.mode.code})")
    print(f"   Confidence: {rec.score}%")
    print(f"   {rec.mode.description}\n")
    
    print("✅ Why this mode:")
    for reason in rec.reasons:
        print(f"   • {reason}")
    
    if rec.alternatives:
        print("\n🔄 Alternatives:")
        for alt_mode, alt_score in rec.alternatives:
            print(f"   • {alt_mode.name} [{alt_mode.code}] ({alt_score}%)")
    
    # Apply mode
    apply = input("\n\n👉 Apply this mode? (y/n): ").strip().lower()
    if apply == "y":
        manager = get_manager()
        manager.switch(rec.mode.name)
        print(f"\n✅ Switched to {rec.mode.name} mode!")
        return rec.mode
    
    return None


if __name__ == "__main__":
    interactive_wizard()

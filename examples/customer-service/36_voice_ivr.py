#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Voice/IVR Support System
========================

Voice and IVR (Interactive Voice Response) support with:
- Text-to-speech output formatting
- Speech-to-text input handling
- DTMF menu navigation
- Call routing logic
- Hold music and wait time estimates
- Call analytics and metrics

Demo: Phone support for tech products (monitors, keyboards, cables)
"""

import asyncio
import json
import random
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional


class CallState(Enum):
    """Call states in IVR flow."""

    INITIATED = "initiated"
    GREETING = "greeting"
    MAIN_MENU = "main_menu"
    SUB_MENU = "sub_menu"
    SPEECH_INPUT = "speech_input"
    PROCESSING = "processing"
    AGENT_QUEUE = "agent_queue"
    ON_HOLD = "on_hold"
    WITH_AGENT = "with_agent"
    SURVEY = "survey"
    ENDED = "ended"


class InputType(Enum):
    """Types of caller input."""

    DTMF = "dtmf"  # Touch-tone keypad
    SPEECH = "speech"
    TIMEOUT = "timeout"
    HANGUP = "hangup"


class CallPriority(Enum):
    """Call queue priority."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    VIP = 4
    EMERGENCY = 5


class AgentSkill(Enum):
    """Agent skill categories."""

    GENERAL = "general"
    TECHNICAL = "technical"
    BILLING = "billing"
    RETURNS = "returns"
    SALES = "sales"
    SPANISH = "spanish"


@dataclass
class TTSConfig:
    """Text-to-speech configuration."""

    voice: str = "en-US-Standard-C"
    speaking_rate: float = 0.95
    pitch: float = 0.0
    pause_between_sentences: float = 0.5
    emphasis_words: list = field(default_factory=list)

    def format_for_speech(self, text: str) -> str:
        """Format text for natural TTS output."""
        # Add pauses after punctuation
        text = re.sub(r"\.", '.<break time="0.5s"/>', text)
        text = re.sub(r"\?", '?<break time="0.3s"/>', text)
        text = re.sub(r"\!", '!<break time="0.3s"/>', text)

        # Emphasize numbers for clarity
        text = re.sub(r"(\d)", r'<say-as interpret-as="characters">\1</say-as>', text)

        # Format phone numbers
        text = re.sub(
            r"1-(\d{3})-(\d{3})-(\d{4})",
            r'<say-as interpret-as="telephone">1 \1 \2 \3</say-as>',
            text,
        )

        return text


@dataclass
class STTResult:
    """Speech-to-text result."""

    transcript: str
    confidence: float
    is_final: bool
    alternatives: list = field(default_factory=list)
    intent: Optional[str] = None
    entities: dict = field(default_factory=dict)


@dataclass
class MenuItem:
    """IVR menu item."""

    key: str  # DTMF key (0-9, *, #)
    label: str
    speech_triggers: list[str]
    action: str  # transfer, submenu, info, repeat, agent
    target: Optional[str] = None  # Submenu name or agent skill

    def get_prompt(self) -> str:
        """Get TTS prompt for this option."""
        return f"Press {self.key} for {self.label}."


@dataclass
class IVRMenu:
    """IVR menu definition."""

    name: str
    greeting: str
    items: list[MenuItem]
    timeout_seconds: int = 10
    max_retries: int = 3
    parent: Optional[str] = None

    def get_full_prompt(self) -> str:
        """Get full menu prompt."""
        parts = [self.greeting]
        for item in self.items:
            parts.append(item.get_prompt())
        return " ".join(parts)

    def find_by_key(self, key: str) -> Optional[MenuItem]:
        """Find menu item by DTMF key."""
        for item in self.items:
            if item.key == key:
                return item
        return None

    def find_by_speech(self, transcript: str) -> Optional[MenuItem]:
        """Find menu item by speech input."""
        transcript_lower = transcript.lower()
        for item in self.items:
            for trigger in item.speech_triggers:
                if trigger.lower() in transcript_lower:
                    return item
        return None


@dataclass
class Agent:
    """Support agent."""

    id: str
    name: str
    skills: list[AgentSkill]
    extension: str
    available: bool = True
    current_call: Optional[str] = None
    avg_handle_time: float = 300.0  # seconds
    calls_today: int = 0


@dataclass
class Call:
    """Phone call session."""

    id: str
    caller_id: str
    caller_name: Optional[str]
    state: CallState
    priority: CallPriority
    language: str = "en"
    started_at: datetime = field(default_factory=datetime.now)
    menu_history: list = field(default_factory=list)
    input_history: list = field(default_factory=list)
    assigned_agent: Optional[str] = None
    wait_time_seconds: float = 0.0
    hold_time_seconds: float = 0.0
    talk_time_seconds: float = 0.0
    survey_score: Optional[int] = None
    ended_at: Optional[datetime] = None
    resolution: Optional[str] = None

    @property
    def total_duration(self) -> float:
        """Get total call duration."""
        end = self.ended_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "caller_id": self.caller_id,
            "state": self.state.value,
            "priority": self.priority.name,
            "duration_seconds": self.total_duration,
            "wait_time": self.wait_time_seconds,
            "assigned_agent": self.assigned_agent,
        }


class SpeechRecognizer:
    """Simulated speech recognition."""

    def __init__(self):
        self.intent_patterns = {
            "order_status": ["order", "track", "where is", "status", "shipped"],
            "returns": ["return", "refund", "exchange", "send back"],
            "technical": ["help", "problem", "not working", "broken", "issue"],
            "billing": ["bill", "charge", "payment", "invoice", "price"],
            "sales": ["buy", "purchase", "recommend", "new", "product"],
            "agent": ["human", "person", "agent", "representative", "speak to"],
            "main_menu": ["main menu", "start over", "menu"],
            "repeat": ["repeat", "again", "what", "sorry"],
        }

    def recognize(self, audio_input: str) -> STTResult:
        """Recognize speech from audio (simulated with text in demo)."""
        # In production, this would call a speech recognition API
        transcript = audio_input.strip()
        confidence = 0.85 + random.uniform(0, 0.10)

        # Detect intent
        intent = self._detect_intent(transcript)

        return STTResult(
            transcript=transcript, confidence=confidence, is_final=True, intent=intent
        )

    def _detect_intent(self, transcript: str) -> Optional[str]:
        """Detect intent from transcript."""
        transcript_lower = transcript.lower()

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern in transcript_lower:
                    return intent

        return None


class HoldMusicManager:
    """Manages hold music and announcements."""

    def __init__(self):
        self.music_tracks = [
            {"id": "jazz_1", "name": "Smooth Jazz", "duration": 180},
            {"id": "classical_1", "name": "Classical Piano", "duration": 240},
            {"id": "ambient_1", "name": "Ambient Calm", "duration": 200},
        ]

        self.position_announcements = [
            "You are currently number {position} in the queue. Estimated wait time is {wait} minutes.",
            "Thank you for holding. Your call is important to us. You are {position} in line.",
            "We appreciate your patience. A representative will be with you shortly. Position: {position}.",
        ]

        self.tips = [
            "Did you know? You can check your order status online at techworld.com/orders.",
            "For faster service, have your order number ready when the agent answers.",
            "Visit our FAQ page for answers to common questions at techworld.com/faq.",
        ]

    def get_hold_audio(self, position: int, wait_minutes: int) -> list[dict]:
        """Get hold audio sequence."""
        sequence = []

        # Position announcement
        announcement = random.choice(self.position_announcements).format(
            position=position, wait=wait_minutes
        )
        sequence.append({"type": "speech", "content": announcement})

        # Music segment
        track = random.choice(self.music_tracks)
        sequence.append({"type": "music", "track_id": track["id"], "duration": 30})

        # Tip (occasionally)
        if random.random() < 0.3:
            tip = random.choice(self.tips)
            sequence.append({"type": "speech", "content": tip})

        return sequence


class CallRouter:
    """Routes calls to appropriate agents."""

    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.queue: list[Call] = []

        self._init_demo_agents()

    def _init_demo_agents(self):
        """Initialize demo agents."""
        agents = [
            Agent(
                id="agent_1",
                name="Sarah",
                skills=[AgentSkill.GENERAL, AgentSkill.RETURNS],
                extension="1001",
            ),
            Agent(
                id="agent_2",
                name="Mike",
                skills=[AgentSkill.TECHNICAL],
                extension="1002",
            ),
            Agent(
                id="agent_3",
                name="Lisa",
                skills=[AgentSkill.BILLING, AgentSkill.SALES],
                extension="1003",
            ),
            Agent(
                id="agent_4",
                name="Carlos",
                skills=[AgentSkill.GENERAL, AgentSkill.SPANISH],
                extension="1004",
            ),
        ]
        for agent in agents:
            self.agents[agent.id] = agent

    def add_to_queue(self, call: Call, skill: AgentSkill = AgentSkill.GENERAL):
        """Add call to queue."""
        call.state = CallState.AGENT_QUEUE

        # Insert by priority
        inserted = False
        for i, queued_call in enumerate(self.queue):
            if call.priority.value > queued_call.priority.value:
                self.queue.insert(i, call)
                inserted = True
                break

        if not inserted:
            self.queue.append(call)

        return self.get_queue_position(call.id)

    def get_queue_position(self, call_id: str) -> int:
        """Get position in queue (1-indexed)."""
        for i, call in enumerate(self.queue):
            if call.id == call_id:
                return i + 1
        return -1

    def estimate_wait_time(self, position: int, skill: AgentSkill = None) -> int:
        """Estimate wait time in minutes."""
        # Find available agents with skill
        available = [a for a in self.agents.values() if a.available]
        if skill:
            available = [a for a in available if skill in a.skills]

        if available:
            avg_handle = sum(a.avg_handle_time for a in available) / len(available)
            return max(1, int((position * avg_handle) / (len(available) * 60)))

        # No agents available - estimate based on current handle times
        avg_handle = sum(a.avg_handle_time for a in self.agents.values()) / len(
            self.agents
        )
        return max(5, int((position * avg_handle) / 60))

    def find_available_agent(self, skill: AgentSkill = None) -> Optional[Agent]:
        """Find available agent with required skill."""
        for agent in self.agents.values():
            if agent.available:
                if skill is None or skill in agent.skills:
                    return agent
        return None

    def assign_call(self, call: Call, agent: Agent):
        """Assign call to agent."""
        agent.available = False
        agent.current_call = call.id
        agent.calls_today += 1

        call.assigned_agent = agent.id
        call.state = CallState.WITH_AGENT

        # Remove from queue
        self.queue = [c for c in self.queue if c.id != call.id]

    def release_agent(self, agent_id: str):
        """Release agent after call."""
        agent = self.agents.get(agent_id)
        if agent:
            agent.available = True
            agent.current_call = None

    def get_queue_stats(self) -> dict:
        """Get current queue statistics."""
        return {
            "queue_length": len(self.queue),
            "available_agents": sum(1 for a in self.agents.values() if a.available),
            "total_agents": len(self.agents),
            "avg_wait_estimate": (
                self.estimate_wait_time(len(self.queue)) if self.queue else 0
            ),
        }


class VoiceIVRBot:
    """Voice IVR support system."""

    def __init__(self, company_name: str = "TechWorld"):
        self.company_name = company_name
        self.tts_config = TTSConfig()
        self.speech_recognizer = SpeechRecognizer()
        self.hold_music = HoldMusicManager()
        self.router = CallRouter()

        self.calls: dict[str, Call] = {}
        self.menus: dict[str, IVRMenu] = {}

        self.call_counter = 0

        # Metrics
        self.metrics = {
            "total_calls": 0,
            "calls_completed": 0,
            "calls_abandoned": 0,
            "avg_wait_time": 0.0,
            "avg_handle_time": 0.0,
            "avg_survey_score": 0.0,
            "survey_responses": 0,
            "ivr_containment": 0,  # Resolved without agent
            "menu_selections": defaultdict(int),
        }

        # Callbacks
        self.on_speech: Optional[Callable] = None
        self.on_dtmf: Optional[Callable] = None
        self.on_state_change: Optional[Callable] = None

        self._build_menus()

    def _build_menus(self):
        """Build IVR menu structure."""
        # Main menu
        self.menus["main"] = IVRMenu(
            name="main",
            greeting=f"Thank you for calling {self.company_name}. For English, press 1. Para español, oprima 2.",
            items=[
                MenuItem("1", "English", ["english", "one"], "submenu", "main_english"),
                MenuItem(
                    "2",
                    "Spanish",
                    ["spanish", "español", "dos"],
                    "submenu",
                    "main_spanish",
                ),
                MenuItem(
                    "0",
                    "operator",
                    ["operator", "help"],
                    "agent",
                    AgentSkill.GENERAL.value,
                ),
            ],
        )

        # English main menu
        self.menus["main_english"] = IVRMenu(
            name="main_english",
            greeting="Main menu.",
            items=[
                MenuItem(
                    "1",
                    "order status",
                    ["order", "track", "status"],
                    "info",
                    "order_status",
                ),
                MenuItem(
                    "2",
                    "returns and exchanges",
                    ["return", "exchange", "refund"],
                    "submenu",
                    "returns",
                ),
                MenuItem(
                    "3",
                    "technical support",
                    ["technical", "help", "problem"],
                    "agent",
                    AgentSkill.TECHNICAL.value,
                ),
                MenuItem(
                    "4",
                    "billing questions",
                    ["billing", "payment", "charge"],
                    "agent",
                    AgentSkill.BILLING.value,
                ),
                MenuItem(
                    "5",
                    "sales",
                    ["buy", "purchase", "product"],
                    "agent",
                    AgentSkill.SALES.value,
                ),
                MenuItem("9", "repeat these options", ["repeat"], "repeat"),
                MenuItem(
                    "0",
                    "speak to a representative",
                    ["representative", "agent", "person"],
                    "agent",
                    AgentSkill.GENERAL.value,
                ),
            ],
            parent="main",
        )

        # Spanish main menu
        self.menus["main_spanish"] = IVRMenu(
            name="main_spanish",
            greeting="Menú principal.",
            items=[
                MenuItem(
                    "1",
                    "estado del pedido",
                    ["pedido", "orden"],
                    "info",
                    "order_status_es",
                ),
                MenuItem(
                    "2", "devoluciones", ["devolver", "cambio"], "submenu", "returns_es"
                ),
                MenuItem(
                    "0",
                    "hablar con un representante",
                    ["representante", "agente"],
                    "agent",
                    AgentSkill.SPANISH.value,
                ),
            ],
            parent="main",
        )

        # Returns submenu
        self.menus["returns"] = IVRMenu(
            name="returns",
            greeting="Returns and exchanges.",
            items=[
                MenuItem(
                    "1", "start a new return", ["new", "start"], "info", "return_start"
                ),
                MenuItem(
                    "2",
                    "check return status",
                    ["status", "check"],
                    "info",
                    "return_status",
                ),
                MenuItem(
                    "3",
                    "return policy information",
                    ["policy", "information"],
                    "info",
                    "return_policy",
                ),
                MenuItem(
                    "0",
                    "speak with returns specialist",
                    ["specialist", "agent"],
                    "agent",
                    AgentSkill.RETURNS.value,
                ),
                MenuItem(
                    "*",
                    "return to main menu",
                    ["main", "back"],
                    "submenu",
                    "main_english",
                ),
            ],
            parent="main_english",
        )

    async def start_call(
        self,
        caller_id: str,
        caller_name: Optional[str] = None,
        priority: CallPriority = CallPriority.NORMAL,
    ) -> Call:
        """Start a new inbound call."""
        self.call_counter += 1
        call_id = f"call_{int(time.time())}_{self.call_counter}"

        call = Call(
            id=call_id,
            caller_id=caller_id,
            caller_name=caller_name,
            state=CallState.INITIATED,
            priority=priority,
        )

        self.calls[call_id] = call
        self.metrics["total_calls"] += 1

        # Transition to greeting
        await self._change_state(call, CallState.GREETING)

        # Play greeting
        greeting = await self._get_greeting(call)
        await self._speak(call, greeting)

        # Transition to main menu
        await self._change_state(call, CallState.MAIN_MENU)
        call.menu_history.append("main")

        # Play main menu
        menu = self.menus["main"]
        await self._speak(call, menu.get_full_prompt())

        return call

    async def _get_greeting(self, call: Call) -> str:
        """Get call greeting based on context."""
        greeting_parts = [f"Thank you for calling {self.company_name}."]

        # Time-based greeting
        hour = datetime.now().hour
        if 5 <= hour < 12:
            greeting_parts.insert(0, "Good morning!")
        elif 12 <= hour < 17:
            greeting_parts.insert(0, "Good afternoon!")
        else:
            greeting_parts.insert(0, "Good evening!")

        # VIP greeting
        if call.priority == CallPriority.VIP:
            greeting_parts.append("We value your VIP membership.")

        return " ".join(greeting_parts)

    async def handle_dtmf(self, call_id: str, digit: str) -> dict:
        """Handle DTMF (keypad) input."""
        call = self.calls.get(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")

        call.input_history.append(
            {
                "type": InputType.DTMF.value,
                "value": digit,
                "timestamp": datetime.now().isoformat(),
            }
        )

        self.metrics["menu_selections"][digit] += 1

        # Get current menu
        current_menu_name = call.menu_history[-1] if call.menu_history else "main"
        menu = self.menus.get(current_menu_name)

        if not menu:
            return await self._handle_invalid_input(call)

        # Find matching menu item
        item = menu.find_by_key(digit)

        if not item:
            return await self._handle_invalid_input(call)

        return await self._execute_menu_action(call, item)

    async def handle_speech(self, call_id: str, audio_or_text: str) -> dict:
        """Handle speech input."""
        call = self.calls.get(call_id)
        if not call:
            raise ValueError(f"Call {call_id} not found")

        # Recognize speech
        result = self.speech_recognizer.recognize(audio_or_text)

        call.input_history.append(
            {
                "type": InputType.SPEECH.value,
                "value": result.transcript,
                "confidence": result.confidence,
                "intent": result.intent,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Get current menu
        current_menu_name = call.menu_history[-1] if call.menu_history else "main"
        menu = self.menus.get(current_menu_name)

        if not menu:
            return await self._handle_invalid_input(call)

        # Try to match speech to menu item
        item = menu.find_by_speech(result.transcript)

        if item:
            return await self._execute_menu_action(call, item)

        # Try intent-based routing
        if result.intent:
            return await self._route_by_intent(call, result.intent)

        return await self._handle_invalid_input(call)

    async def _execute_menu_action(self, call: Call, item: MenuItem) -> dict:
        """Execute menu item action."""
        response = {"action": item.action, "target": item.target}

        if item.action == "submenu":
            # Navigate to submenu
            call.menu_history.append(item.target)
            menu = self.menus.get(item.target)

            if menu:
                await self._speak(call, menu.get_full_prompt())
                response["prompt"] = menu.get_full_prompt()
            else:
                return await self._handle_invalid_input(call)

        elif item.action == "agent":
            # Transfer to agent
            skill = AgentSkill(item.target) if item.target else AgentSkill.GENERAL
            response = await self._transfer_to_agent(call, skill)

        elif item.action == "info":
            # Play information
            info = await self._get_info_content(item.target)
            await self._speak(call, info)
            response["info"] = info

            # Return to menu
            menu = self.menus.get(call.menu_history[-1])
            if menu:
                await self._speak(call, "Returning to menu. " + menu.get_full_prompt())

        elif item.action == "repeat":
            # Repeat current menu
            menu = self.menus.get(call.menu_history[-1])
            if menu:
                await self._speak(call, menu.get_full_prompt())
                response["prompt"] = menu.get_full_prompt()

        return response

    async def _route_by_intent(self, call: Call, intent: str) -> dict:
        """Route call based on detected intent."""
        intent_to_skill = {
            "order_status": None,  # Self-service
            "returns": AgentSkill.RETURNS,
            "technical": AgentSkill.TECHNICAL,
            "billing": AgentSkill.BILLING,
            "sales": AgentSkill.SALES,
            "agent": AgentSkill.GENERAL,
        }

        if intent == "main_menu":
            # Return to main menu
            call.menu_history = ["main"]
            menu = self.menus["main"]
            await self._speak(call, menu.get_full_prompt())
            return {"action": "main_menu"}

        if intent == "repeat":
            menu = self.menus.get(call.menu_history[-1])
            if menu:
                await self._speak(call, menu.get_full_prompt())
            return {"action": "repeat"}

        if intent == "order_status":
            # Self-service order status
            info = await self._get_info_content("order_status")
            await self._speak(call, info)
            self.metrics["ivr_containment"] += 1
            return {"action": "info", "info": info}

        skill = intent_to_skill.get(intent)
        if skill:
            return await self._transfer_to_agent(call, skill)

        return await self._handle_invalid_input(call)

    async def _transfer_to_agent(self, call: Call, skill: AgentSkill) -> dict:
        """Transfer call to agent queue."""
        # Check for available agent
        agent = self.router.find_available_agent(skill)

        if agent:
            # Direct transfer
            self.router.assign_call(call, agent)
            await self._speak(call, f"Connecting you with {agent.name}. Please hold.")

            return {
                "action": "connected",
                "agent": agent.name,
                "extension": agent.extension,
            }

        # Add to queue
        position = self.router.add_to_queue(call, skill)
        wait_time = self.router.estimate_wait_time(position, skill)

        await self._change_state(call, CallState.ON_HOLD)

        message = f"All representatives are currently busy. You are number {position} in the queue. Your estimated wait time is {wait_time} minutes. Please hold."
        await self._speak(call, message)

        return {
            "action": "queued",
            "position": position,
            "estimated_wait_minutes": wait_time,
        }

    async def _get_info_content(self, info_key: str) -> str:
        """Get informational content."""
        info_content = {
            "order_status": "To check your order status, please visit techworld.com/orders and enter your order number. You can also find tracking information in your order confirmation email. If you need further assistance, press 0 to speak with a representative.",
            "return_start": "To start a return, visit techworld.com/returns or press 0 to speak with our returns team. You'll need your order number and the items you wish to return.",
            "return_status": "To check your return status, visit techworld.com/returns and enter your return authorization number. Returns typically process within 5-7 business days.",
            "return_policy": "Our return policy allows returns within 30 days of purchase for unused items in original packaging. Electronics must be returned within 15 days. Restocking fees may apply to opened items. For complete policy details, visit techworld.com/returns.",
            "order_status_es": "Para verificar el estado de su pedido, visite techworld.com/orders e ingrese su número de pedido. Si necesita más ayuda, presione 0.",
        }

        return info_content.get(
            info_key, "I'm sorry, that information is not available."
        )

    async def _handle_invalid_input(self, call: Call) -> dict:
        """Handle invalid or unrecognized input."""
        await self._speak(
            call, "I'm sorry, I didn't understand that. Let me repeat your options."
        )

        menu = self.menus.get(call.menu_history[-1] if call.menu_history else "main")
        if menu:
            await self._speak(call, menu.get_full_prompt())

        return {"action": "invalid", "prompt": "repeated_menu"}

    async def process_hold_queue(self):
        """Process calls in hold queue (background task)."""
        while True:
            for call in list(self.router.queue):
                # Check for available agent
                agent = self.router.find_available_agent()

                if agent:
                    self.router.assign_call(call, agent)
                    await self._change_state(call, CallState.WITH_AGENT)
                    await self._speak(
                        call,
                        f"Thank you for holding. You are now connected with {agent.name}.",
                    )
                else:
                    # Update wait time
                    call.wait_time_seconds += 30

                    # Play hold sequence
                    position = self.router.get_queue_position(call.id)
                    wait_mins = self.router.estimate_wait_time(position)

                    # Every 2 minutes, announce position
                    if int(call.wait_time_seconds) % 120 == 0:
                        sequence = self.hold_music.get_hold_audio(position, wait_mins)
                        for item in sequence:
                            if item["type"] == "speech":
                                await self._speak(call, item["content"])

            await asyncio.sleep(30)

    async def end_call(
        self, call_id: str, resolution: Optional[str] = None, offer_survey: bool = True
    ) -> dict:
        """End a call."""
        call = self.calls.get(call_id)
        if not call:
            return {}

        # Offer survey
        if offer_survey:
            await self._change_state(call, CallState.SURVEY)
            await self._speak(
                call,
                "Before you go, please rate your experience. Press 1 for poor, 2 for fair, 3 for good, 4 for very good, or 5 for excellent.",
            )
            # In real implementation, wait for input

        # Release agent if assigned
        if call.assigned_agent:
            self.router.release_agent(call.assigned_agent)

        call.state = CallState.ENDED
        call.ended_at = datetime.now()
        call.resolution = resolution

        self.metrics["calls_completed"] += 1
        self._update_avg_metrics(call)

        # Goodbye
        await self._speak(call, f"Thank you for calling {self.company_name}. Goodbye!")

        return call.to_dict()

    async def submit_survey(self, call_id: str, score: int):
        """Submit survey score."""
        call = self.calls.get(call_id)
        if not call:
            return

        call.survey_score = score

        # Update metrics
        self.metrics["survey_responses"] += 1
        current_avg = self.metrics["avg_survey_score"]
        self.metrics["avg_survey_score"] = (
            current_avg * (self.metrics["survey_responses"] - 1) + score
        ) / self.metrics["survey_responses"]

        await self._speak(call, "Thank you for your feedback!")

    def _update_avg_metrics(self, call: Call):
        """Update average metrics."""
        completed = self.metrics["calls_completed"]

        # Average wait time
        current_wait = self.metrics["avg_wait_time"]
        self.metrics["avg_wait_time"] = (
            current_wait * (completed - 1) + call.wait_time_seconds
        ) / completed

        # Average handle time
        current_handle = self.metrics["avg_handle_time"]
        self.metrics["avg_handle_time"] = (
            current_handle * (completed - 1) + call.total_duration
        ) / completed

    async def _speak(self, call: Call, text: str):
        """Output TTS speech."""
        # Format for TTS
        formatted = self.tts_config.format_for_speech(text)

        if self.on_speech:
            await self.on_speech(call, text, formatted)

    async def _change_state(self, call: Call, new_state: CallState):
        """Change call state."""
        old_state = call.state
        call.state = new_state

        if self.on_state_change:
            await self.on_state_change(call, old_state, new_state)

    def get_call(self, call_id: str) -> Optional[Call]:
        """Get call by ID."""
        return self.calls.get(call_id)

    def get_metrics(self) -> dict:
        """Get IVR metrics."""
        queue_stats = self.router.get_queue_stats()

        return {
            **self.metrics,
            "menu_selections": dict(self.metrics["menu_selections"]),
            "containment_rate": (
                self.metrics["ivr_containment"]
                / max(self.metrics["total_calls"], 1)
                * 100
            ),
            **queue_stats,
        }


class IVRConsole:
    """Console interface for IVR demo."""

    def __init__(self, bot: VoiceIVRBot):
        self.bot = bot
        self.current_call: Optional[Call] = None

        # Wire callbacks
        self.bot.on_speech = self._on_speech
        self.bot.on_state_change = self._on_state_change

    async def _on_speech(self, call: Call, text: str, formatted: str):
        """Handle TTS output."""
        print(f"\n  🔊 IVR: {text}")

    async def _on_state_change(
        self, call: Call, old_state: CallState, new_state: CallState
    ):
        """Handle state change."""
        state_icons = {
            CallState.INITIATED: "📞",
            CallState.GREETING: "👋",
            CallState.MAIN_MENU: "📋",
            CallState.SUB_MENU: "📁",
            CallState.PROCESSING: "⚙️",
            CallState.AGENT_QUEUE: "⏳",
            CallState.ON_HOLD: "🎵",
            CallState.WITH_AGENT: "👤",
            CallState.SURVEY: "⭐",
            CallState.ENDED: "📴",
        }
        icon = state_icons.get(new_state, "•")
        print(f"\n  {icon} State: {new_state.value}")

    def print_header(self):
        """Print console header."""
        print("\n" + "=" * 60)
        print(f"  📞 {self.bot.company_name} Voice IVR Demo")
        print("=" * 60)
        print("  Enter DTMF digits (0-9, *, #) or speak naturally")
        print("  Commands: /status /metrics /end /quit")
        print("-" * 60)

    async def run(self, caller_id: str = "555-123-4567"):
        """Run IVR console demo."""
        self.print_header()

        # Start call
        self.current_call = await self.bot.start_call(
            caller_id=caller_id, caller_name="Demo Caller"
        )

        while self.current_call.state != CallState.ENDED:
            try:
                user_input = input("\n  Your input: ").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    result = await self._handle_command(user_input)
                    if result == "quit":
                        break
                    continue

                # Check if DTMF or speech
                if len(user_input) == 1 and user_input in "0123456789*#":
                    result = await self.bot.handle_dtmf(
                        self.current_call.id, user_input
                    )
                else:
                    result = await self.bot.handle_speech(
                        self.current_call.id, user_input
                    )

                # Display result
                if result.get("action") == "connected":
                    print(
                        f"\n  ✅ Connected to {result['agent']} (ext: {result['extension']})"
                    )
                elif result.get("action") == "queued":
                    print(
                        f"\n  ⏳ Queued: Position {result['position']}, ~{result['estimated_wait_minutes']} min wait"
                    )
                elif result.get("action") == "info":
                    pass  # Already spoken

            except KeyboardInterrupt:
                print("\n\n  Call ended by user.")
                await self.bot.end_call(self.current_call.id, "user_hangup", False)
                break
            except Exception as e:
                print(f"\n  ❌ Error: {e}")

        # Show final metrics
        print("\n" + "-" * 60)
        print("  📊 Call Summary")
        print("-" * 60)
        call = self.current_call
        print(f"  Duration: {call.total_duration:.0f} seconds")
        print(f"  Wait time: {call.wait_time_seconds:.0f} seconds")
        print(f"  Agent: {call.assigned_agent or 'Self-service'}")
        print(f"  Inputs: {len(call.input_history)}")

    async def _handle_command(self, command: str) -> Optional[str]:
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/quit":
            await self.bot.end_call(self.current_call.id, "quit", False)
            return "quit"

        if cmd == "/end":
            await self.bot.end_call(self.current_call.id, "completed")
            return None

        if cmd == "/status":
            call = self.current_call
            print("\n  📞 Call Status")
            print(f"     ID: {call.id}")
            print(f"     State: {call.state.value}")
            print(f"     Duration: {call.total_duration:.0f}s")
            print(f"     Menu path: {' > '.join(call.menu_history)}")
            return None

        if cmd == "/metrics":
            metrics = self.bot.get_metrics()
            print("\n  📊 IVR Metrics")
            print(f"     Total calls: {metrics['total_calls']}")
            print(f"     Completed: {metrics['calls_completed']}")
            print(f"     Avg wait: {metrics['avg_wait_time']:.0f}s")
            print(f"     Containment: {metrics['containment_rate']:.1f}%")
            print(f"     Avg survey: {metrics['avg_survey_score']:.2f}/5")
            return None

        print(f"  Unknown command: {command}")
        return None


async def demo():
    """Run interactive IVR demo."""
    bot = VoiceIVRBot(company_name="TechWorld Support")
    console = IVRConsole(bot)
    await console.run()


async def automated_demo():
    """Run automated IVR demo."""
    print("\n" + "=" * 60)
    print("  Voice IVR - Automated Demo")
    print("=" * 60)

    bot = VoiceIVRBot(company_name="TechWorld Support")

    # Track speech for display
    async def on_speech(call, text, formatted):
        print(f"  🔊 {text[:60]}{'...' if len(text) > 60 else ''}")

    bot.on_speech = on_speech

    # Simulate a call
    print("\n--- Simulating Customer Call ---\n")

    call = await bot.start_call("555-123-4567", "John Smith")
    print(f"  📞 Call started: {call.id}")

    # Navigate menus
    print("\n  [Pressing 1 for English]")
    await bot.handle_dtmf(call.id, "1")

    print("\n  [Pressing 1 for order status]")
    await bot.handle_dtmf(call.id, "1")

    print("\n  [Speaking: 'I want to talk to someone']")
    result = await bot.handle_speech(
        call.id, "I want to talk to someone about my order"
    )

    if result.get("action") == "connected":
        print(f"\n  ✅ Connected to agent: {result['agent']}")
    elif result.get("action") == "queued":
        print(f"\n  ⏳ In queue: Position {result['position']}")

    # End call
    await bot.end_call(call.id, "demo_complete", False)

    # Show metrics
    print("\n--- IVR Metrics ---\n")
    metrics = bot.get_metrics()
    print(f"  Total Calls: {metrics['total_calls']}")
    print(f"  Containment Rate: {metrics['containment_rate']:.1f}%")
    print(f"  Menu Selections: {dict(metrics['menu_selections'])}")
    print(f"  Queue Length: {metrics['queue_length']}")
    print(
        f"  Available Agents: {metrics['available_agents']}/{metrics['total_agents']}"
    )


if __name__ == "__main__":
    import sys

    if "--auto" in sys.argv:
        asyncio.run(automated_demo())
    else:
        asyncio.run(demo())

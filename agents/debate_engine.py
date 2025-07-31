"""
Debate Engine for Fantasy Football Neuron
Orchestrates multi-agent debates with voice synthesis
"""

import asyncio
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json

from .personas import AgentPersona, get_agent_by_name, get_debate_matchup
from .voice_config import VoiceSettings, get_cache_key
from .agent_responses import ResponseGenerator

@dataclass
class DebateTurn:
    """Represents a single turn in the debate"""
    agent: AgentPersona
    text: str
    emotion: str
    responding_to: Optional[str] = None
    timestamp: datetime = None
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

@dataclass
class DebateContext:
    """Context for the ongoing debate"""
    topic: str
    user_context: Dict[str, any]
    agents: List[AgentPersona]
    turns: List[DebateTurn]
    max_turns: int = 15
    time_limit_seconds: int = 300
    
    def get_last_speaker(self) -> Optional[AgentPersona]:
        """Get the agent who spoke last"""
        return self.turns[-1].agent if self.turns else None
    
    def get_turn_count(self, agent: AgentPersona) -> int:
        """Count how many times an agent has spoken"""
        return sum(1 for turn in self.turns if turn.agent == agent)
    
    def get_total_duration_ms(self) -> int:
        """Get total audio duration of debate"""
        return sum(turn.duration_ms or 0 for turn in self.turns)

class DebateOrchestrator:
    """Orchestrates multi-agent debates"""
    
    def __init__(self, response_generator: ResponseGenerator):
        self.response_generator = response_generator
        self.active_debates: Dict[str, DebateContext] = {}
    
    async def start_debate(
        self,
        topic: str,
        user_context: Optional[Dict] = None,
        agents: Optional[List[str]] = None,
        debate_id: Optional[str] = None
    ) -> DebateContext:
        """Initialize a new debate"""
        
        # Select agents if not specified
        if agents:
            agent_personas = [get_agent_by_name(name) for name in agents]
        else:
            agent_personas = get_debate_matchup(topic)
        
        # Create debate context
        context = DebateContext(
            topic=topic,
            user_context=user_context or {},
            agents=agent_personas,
            turns=[]
        )
        
        # Store debate
        if debate_id:
            self.active_debates[debate_id] = context
        
        # Generate opening statements
        await self._generate_opening_statements(context)
        
        return context
    
    async def _generate_opening_statements(self, context: DebateContext):
        """Generate opening statements for each agent"""
        for agent in context.agents:
            response = await self.response_generator.generate_response(
                agent=agent,
                topic=context.topic,
                context=context.user_context,
                previous_turns=[]
            )
            
            turn = DebateTurn(
                agent=agent,
                text=response.text,
                emotion=response.emotion
            )
            context.turns.append(turn)
    
    async def continue_debate(
        self,
        context: DebateContext,
        num_turns: int = 3
    ) -> List[DebateTurn]:
        """Continue an ongoing debate"""
        new_turns = []
        
        for _ in range(num_turns):
            if len(context.turns) >= context.max_turns:
                break
            
            # Select next speaker
            next_agent = self._select_next_speaker(context)
            if not next_agent:
                break
            
            # Generate response
            response = await self.response_generator.generate_response(
                agent=next_agent,
                topic=context.topic,
                context=context.user_context,
                previous_turns=context.turns[-5:]  # Last 5 turns for context
            )
            
            # Determine if this is a rebuttal
            responding_to = None
            if context.turns and random.random() < 0.7:  # 70% chance of direct response
                responding_to = context.get_last_speaker().name
            
            turn = DebateTurn(
                agent=next_agent,
                text=response.text,
                emotion=response.emotion,
                responding_to=responding_to
            )
            
            context.turns.append(turn)
            new_turns.append(turn)
        
        return new_turns
    
    def _select_next_speaker(self, context: DebateContext) -> Optional[AgentPersona]:
        """Select the next agent to speak"""
        if not context.agents:
            return None
        
        # Don't let the same agent speak twice in a row
        last_speaker = context.get_last_speaker()
        available_agents = [a for a in context.agents if a != last_speaker]
        
        if not available_agents:
            return None
        
        # Weighted selection based on personality and turn count
        weights = []
        for agent in available_agents:
            # Base weight
            weight = 1.0
            
            # Agents with higher contrarian tendency interrupt more
            weight += agent.get_personality_score("contrarian_tendency") * 0.5
            
            # Agents who haven't spoken much get higher weight
            turn_count = context.get_turn_count(agent)
            avg_turns = len(context.turns) / len(context.agents)
            if turn_count < avg_turns:
                weight += 0.3
            
            # Emotional agents respond more to emotional statements
            if context.turns and context.turns[-1].emotion in ["angry", "excited"]:
                weight += agent.get_personality_score("emotional_weight") * 0.4
            
            weights.append(weight)
        
        # Select based on weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        return random.choices(available_agents, weights=weights)[0]
    
    async def conclude_debate(self, context: DebateContext) -> DebateTurn:
        """Generate a concluding summary from The Architect"""
        architect = get_agent_by_name("architect")
        
        # Generate meta-analysis
        response = await self.response_generator.generate_conclusion(
            agent=architect,
            context=context
        )
        
        conclusion = DebateTurn(
            agent=architect,
            text=response.text,
            emotion="thoughtful"
        )
        
        context.turns.append(conclusion)
        return conclusion

class DebateFlowController:
    """Controls the flow and pacing of debates"""
    
    @staticmethod
    def should_interrupt(
        speaker: AgentPersona,
        listener: AgentPersona,
        current_text: str
    ) -> bool:
        """Determine if an agent should interrupt"""
        
        # High contrarian agents interrupt more
        interrupt_chance = listener.get_personality_score("contrarian_tendency") * 0.3
        
        # Emotional agents interrupt emotional statements
        if any(trigger in current_text.lower() for trigger in ["never", "always", "ridiculous"]):
            interrupt_chance += listener.get_personality_score("emotional_weight") * 0.2
        
        # Specific agent dynamics
        if speaker.name == "Marcus" and listener.name == "Big Mike":
            # Big Mike loves to interrupt Marcus's data dumps
            interrupt_chance += 0.2
        
        return random.random() < interrupt_chance
    
    @staticmethod
    def get_interaction_type(
        speaker: AgentPersona,
        listener: AgentPersona,
        context: DebateContext
    ) -> str:
        """Determine the type of interaction between agents"""
        
        # Check personality compatibility
        personality_diff = sum(
            abs(s - l) for s, l in 
            zip(speaker.personality_vector, listener.personality_vector)
        )
        
        if personality_diff > 3.5:
            return "confrontational"
        elif personality_diff < 2.0:
            return "agreeable"
        else:
            return "analytical"
    
    @staticmethod
    def estimate_debate_cost(
        context: DebateContext,
        include_voice: bool = True
    ) -> Dict[str, float]:
        """Estimate the cost of a debate"""
        
        costs = {
            "llm_tokens": 0,
            "voice_generation": 0,
            "total": 0
        }
        
        # Estimate tokens (rough approximation)
        total_text = " ".join(turn.text for turn in context.turns)
        token_count = len(total_text.split()) * 1.3  # Rough token estimate
        costs["llm_tokens"] = token_count * 0.00001  # Example rate
        
        if include_voice:
            # Voice costs vary by provider
            for turn in context.turns:
                char_count = len(turn.text)
                if turn.agent.name in ["Marcus", "Big Mike", "Sam", "Leo"]:
                    # ElevenLabs premium
                    costs["voice_generation"] += (char_count / 1000) * 0.030
                else:
                    # OpenAI TTS
                    costs["voice_generation"] += (char_count / 1000) * 0.015
        
        costs["total"] = costs["llm_tokens"] + costs["voice_generation"]
        return costs

# Debate templates for common scenarios
DEBATE_TEMPLATES = {
    "injury_news": {
        "opening_prompts": {
            "marcus": "Let me pull up the historical data on {player} injury impact...",
            "big_mike": "Injuries are part of the game, but {player} is a warrior...",
            "sam": "I've seen this story before with {player} type injuries..."
        },
        "key_points": ["backup value", "injury severity", "game script impact"],
        "max_turns": 9
    },
    
    "start_sit": {
        "opening_prompts": {
            "marcus": "The projections clearly favor {player1} by {margin} points...",
            "zareena": "Everyone will start {player1}, which is exactly why you shouldn't...",
            "leo": "{player1} has the ceiling, but {player2} has the floor..."
        },
        "key_points": ["matchup", "volume", "game script", "weather"],
        "max_turns": 12
    },
    
    "lineup_review": {
        "opening_prompts": {
            "architect": "Your lineup construction reveals interesting psychological patterns...",
            "sam": "I see you're chasing last week's points again...",
            "big_mike": "This lineup has no soul! Where's the upside?"
        },
        "key_points": ["correlation", "ownership", "ceiling", "floor"],
        "max_turns": 15
    }
}

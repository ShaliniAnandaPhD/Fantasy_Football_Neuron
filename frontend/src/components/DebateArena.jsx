import React, { useState, useEffect, useRef } from 'react';
import { useDebate } from '../hooks/useDebate';
import { useVoicePlayback } from '../hooks/useVoicePlayback';
import AgentAvatar from './AgentAvatar';
import VoiceControls from './VoiceControls';
import CostDashboard from './CostDashboard';

const DebateArena = ({ topic, userContext }) => {
  const [debateState, setDebateState] = useState('idle');
  const [selectedAgents, setSelectedAgents] = useState(['marcus', 'big_mike', 'zareena']);
  const [turns, setTurns] = useState([]);
  const [currentSpeaker, setCurrentSpeaker] = useState(null);
  const [totalCost, setTotalCost] = useState(0);
  const [showTranscript, setShowTranscript] = useState(true);
  
  const { 
    startDebate, 
    continueDebate, 
    concludeDebate,
    estimateCost,
    isConnected 
  } = useDebate();
  
  const { 
    playAudio, 
    pauseAudio, 
    isPlaying, 
    playbackSpeed, 
    setPlaybackSpeed 
  } = useVoicePlayback();
  
  const transcriptRef = useRef(null);

  // Agent personalities and colors
  const agentProfiles = {
    marcus: {
      name: 'Marcus Chen',
      title: 'The Quant',
      color: '#3B82F6',
      avatar: '📊'
    },
    big_mike: {
      name: 'Big Mike Sullivan',
      title: 'The Gut Player',
      color: '#EF4444',
      avatar: '🏈'
    },
    zareena: {
      name: 'Zareena Volkov',
      title: 'The Contrarian',
      color: '#8B5CF6',
      avatar: '♟️'
    },
    sam: {
      name: 'Sam Rodriguez',
      title: 'The Veteran',
      color: '#F59E0B',
      avatar: '🎯'
    },
    leo: {
      name: 'Leo Kim',
      title: 'The Rookie',
      color: '#10B981',
      avatar: '🚀'
    },
    architect: {
      name: 'The Architect',
      title: 'Game Theorist',
      color: '#6B7280',
      avatar: '🧩'
    }
  };

  // Start the debate
  const handleStartDebate = async () => {
    setDebateState('starting');
    try {
      const debate = await startDebate(topic, userContext, selectedAgents);
      setTurns(debate.turns);
      setDebateState('active');
      
      // Play first audio
      if (debate.turns.length > 0) {
        await playTurnAudio(debate.turns[0]);
      }
    } catch (error) {
      console.error('Failed to start debate:', error);
      setDebateState('error');
    }
  };

  // Continue the debate
  const handleContinue = async () => {
    if (debateState !== 'active') return;
    
    try {
      const newTurns = await continueDebate(3);
      setTurns(prev => [...prev, ...newTurns]);
      
      // Play new turns sequentially
      for (const turn of newTurns) {
        await playTurnAudio(turn);
      }
    } catch (error) {
      console.error('Failed to continue debate:', error);
    }
  };

  // Play audio for a turn
  const playTurnAudio = async (turn) => {
    setCurrentSpeaker(turn.agent);
    
    if (turn.audio_url) {
      await playAudio(turn.audio_url);
    }
    
    // Update cost
    setTotalCost(prev => prev + (turn.cost || 0.005));
    
    // Scroll transcript
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
    
    setCurrentSpeaker(null);
  };

  // Estimate debate cost
  useEffect(() => {
    const fetchEstimate = async () => {
      if (selectedAgents.length > 0) {
        const estimate = await estimateCost(selectedAgents, 15);
        console.log('Estimated cost:', estimate);
      }
    };
    fetchEstimate();
  }, [selectedAgents, estimateCost]);

  return (
    <div className="debate-arena">
      {/* Header */}
      <div className="arena-header">
        <h1>The Fantasy Football Huddle</h1>
        <p className="topic">{topic}</p>
        
        {/* Connection Status */}
        <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
          {isConnected ? '🟢 Live' : '🔴 Disconnected'}
        </div>
      </div>

      {/* Agent Selection (before debate starts) */}
      {debateState === 'idle' && (
        <div className="agent-selection">
          <h3>Select Your Debate Panel</h3>
          <div className="agent-grid">
            {Object.entries(agentProfiles).map(([key, agent]) => (
              <div
                key={key}
                className={`agent-card ${selectedAgents.includes(key) ? 'selected' : ''}`}
                onClick={() => {
                  if (selectedAgents.includes(key)) {
                    setSelectedAgents(prev => prev.filter(a => a !== key));
                  } else if (selectedAgents.length < 4) {
                    setSelectedAgents(prev => [...prev, key]);
                  }
                }}
              >
                <div className="agent-avatar">{agent.avatar}</div>
                <div className="agent-name">{agent.name}</div>
                <div className="agent-title">{agent.title}</div>
              </div>
            ))}
          </div>
          
          <button 
            className="start-button"
            onClick={handleStartDebate}
            disabled={selectedAgents.length < 2}
          >
            Start the Debate ({selectedAgents.length} agents)
          </button>
        </div>
      )}

      {/* Active Debate */}
      {(debateState === 'active' || debateState === 'starting') && (
        <div className="debate-content">
          {/* Agent Avatars */}
          <div className="agents-row">
            {selectedAgents.map(agentKey => (
              <AgentAvatar
                key={agentKey}
                agent={agentProfiles[agentKey]}
                isActive={currentSpeaker === agentKey}
                turnCount={turns.filter(t => t.agent === agentKey).length}
              />
            ))}
          </div>

          {/* Debate Transcript */}
          <div className="transcript-container">
            <div className="transcript-header">
              <h3>Debate Transcript</h3>
              <button onClick={() => setShowTranscript(!showTranscript)}>
                {showTranscript ? 'Hide' : 'Show'}
              </button>
            </div>
            
            {showTranscript && (
              <div className="transcript" ref={transcriptRef}>
                {turns.map((turn, index) => (
                  <div 
                    key={index} 
                    className={`turn ${turn.agent === currentSpeaker ? 'speaking' : ''}`}
                  >
                    <div 
                      className="speaker-name"
                      style={{ color: agentProfiles[turn.agent]?.color }}
                    >
                      {agentProfiles[turn.agent]?.name}
                      {turn.responding_to && (
                        <span className="responding-to">
                          → {agentProfiles[turn.responding_to]?.name}
                        </span>
                      )}
                    </div>
                    <div className="turn-text">{turn.text}</div>
                    <div className="turn-meta">
                      <span className="emotion">{turn.emotion}</span>
                      <span className="cost">${(turn.cost || 0.005).toFixed(3)}</span>
                    </div>
                  </div>
                ))}
                
                {debateState === 'starting' && (
                  <div className="loading-turn">
                    <div className="spinner"></div>
                    <span>Agents are thinking...</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Controls */}
          <VoiceControls
            isPlaying={isPlaying}
            onPlay={() => playAudio()}
            onPause={pauseAudio}
            playbackSpeed={playbackSpeed}
            onSpeedChange={setPlaybackSpeed}
            onContinue={handleContinue}
            onConclude={() => concludeDebate()}
            debateActive={debateState === 'active'}
          />

          {/* Cost Dashboard */}
          <CostDashboard
            totalCost={totalCost}
            turnCount={turns.length}
            cacheHits={Math.floor(turns.length * 0.4)}
            estimatedSavings={totalCost * 0.4}
          />
        </div>
      )}

      <style jsx>{`
        .debate-arena {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
        }

        .arena-header {
          text-align: center;
          margin-bottom: 30px;
        }

        .arena-header h1 {
          font-size: 2.5rem;
          margin-bottom: 10px;
        }

        .topic {
          font-size: 1.2rem;
          color: #666;
        }

        .connection-status {
          display: inline-block;
          padding: 5px 15px;
          border-radius: 20px;
          font-size: 0.9rem;
          margin-top: 10px;
        }

        .connection-status.connected {
          background: #10B981;
          color: white;
        }

        .connection-status.disconnected {
          background: #EF4444;
          color: white;
        }

        .agent-selection {
          background: #f9fafb;
          padding: 30px;
          border-radius: 12px;
          margin-bottom: 30px;
        }

        .agent-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 20px;
          margin: 20px 0;
        }

        .agent-card {
          background: white;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          padding: 20px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
        }

        .agent-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }

        .agent-card.selected {
          border-color: #3B82F6;
          background: #EFF6FF;
        }

        .agent-avatar {
          font-size: 2rem;
          margin-bottom: 10px;
        }

        .agent-name {
          font-weight: 600;
          margin-bottom: 5px;
        }

        .agent-title {
          font-size: 0.875rem;
          color: #6B7280;
        }

        .start-button {
          background: #3B82F6;
          color: white;
          border: none;
          padding: 12px 30px;
          border-radius: 8px;
          font-size: 1.1rem;
          cursor: pointer;
          transition: background 0.2s;
        }

        .start-button:hover:not(:disabled) {
          background: #2563EB;
        }

        .start-button:disabled {
          background: #9CA3AF;
          cursor: not-allowed;
        }

        .debate-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .agents-row {
          display: flex;
          justify-content: center;
          gap: 30px;
          margin-bottom: 20px;
        }

        .transcript-container {
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          overflow: hidden;
        }

        .transcript-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 15px 20px;
          border-bottom: 1px solid #e5e7eb;
        }

        .transcript {
          max-height: 500px;
          overflow-y: auto;
          padding: 20px;
        }

        .turn {
          margin-bottom: 20px;
          padding: 15px;
          background: #f9fafb;
          border-radius: 8px;
          transition: all 0.2s;
        }

        .turn.speaking {
          background: #FEF3C7;
          transform: scale(1.02);
        }

        .speaker-name {
          font-weight: 600;
          margin-bottom: 8px;
        }

        .responding-to {
          font-weight: 400;
          font-size: 0.875rem;
          opacity: 0.7;
        }

        .turn-text {
          line-height: 1.6;
          margin-bottom: 8px;
        }

        .turn-meta {
          display: flex;
          justify-content: space-between;
          font-size: 0.875rem;
          color: #6B7280;
        }

        .emotion {
          font-style: italic;
        }

        .loading-turn {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 20px;
          color: #6B7280;
        }

        .spinner {
          width: 20px;
          height: 20px;
          border: 2px solid #e5e7eb;
          border-top-color: #3B82F6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default DebateArena;

# Fantasy Football Neuron 🏈🤖

An AI-powered fantasy football debate platform featuring six unique AI agents with distinct personalities, voice synthesis, and real-time debates about your lineup decisions.

## 🌟 Features

- **AI Agent Debates**: Six unique AI personalities debate your fantasy football decisions
- **Voice Synthesis**: Each agent has their own voice powered by ElevenLabs and OpenAI TTS
- **Real-time Analysis**: Breaking news and injury updates trigger instant debates
- **Cost-Optimized**: Smart caching and routing reduce voice generation costs by 70%
- **GCP-Powered**: Fine-tuned models deployed on Google Cloud Platform

## 🎭 Meet The Agents

1. **Marcus Chen (The Quant)** - Data-obsessed analyst who trusts only the numbers
2. **Big Mike Sullivan (The Gut Player)** - Old-school instinct-driven veteran
3. **Zareena Volkov (The Contrarian)** - Always fades the chalk, loves to challenge consensus
4. **Sam Rodriguez (The Veteran)** - Seen it all, plays the long game
5. **Leo Kim (The Rookie)** - Enthusiastic newcomer with fresh perspectives
6. **The Architect (Game Theorist)** - Strategic mastermind playing 4D chess

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+
- Google Cloud Platform account
- ElevenLabs API key
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/fantasy-football-neuron.git
cd fantasy-football-neuron

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

```bash
# Start the backend
python api/main.py

# In another terminal, start the frontend
cd frontend
npm start

# Access at http://localhost:3000
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   User Interface                     │
│              (React + Voice Controls)                │
└────────────────────────┬────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────┐
│                   API Gateway                        │
│              (Cloud Run + FastAPI)                   │
└────────────────────────┬────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Voice Engine │ │ Debate Engine│ │ Cost Tracker │
│ (ElevenLabs) │ │ (Vertex AI)  │ │  (Redis)     │
└──────────────┘ └──────────────┘ └──────────────┘
```

## 💰 Cost Optimization

Our hybrid architecture reduces voice generation costs by 70%:

- **L1 Cache**: Upstash Redis for common phrases (40% hit rate)
- **L2 Cache**: Cloud Storage for all generated audio
- **Smart Routing**: Premium voices only for emotional content
- **Format Optimization**: 3-agent debates instead of 6 when appropriate

## 🚀 Deployment

### Google Cloud Platform

```bash
# Deploy to Cloud Run
cd cloud/gcp
./setup.sh

# Deploy the frontend to Cloud CDN
gcloud app deploy frontend/app.yaml
```

### Environment Variables

```env
# Voice APIs
ELEVENLABS_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# GCP
GCP_PROJECT_ID=your_project
VERTEX_AI_LOCATION=us-central1

# Redis Cache
UPSTASH_REDIS_URL=your_redis_url
UPSTASH_REDIS_TOKEN=your_token

# Feature Flags
ENABLE_VOICE_CACHE=true
ENABLE_SMART_ROUTING=true
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Test specific components
pytest tests/test_agents.py
pytest tests/test_voice_generation.py

# Run with coverage
pytest --cov=agents --cov=api
```

## 📊 Performance Metrics

- **Response Time**: < 1.5 seconds per voice generation
- **Cache Hit Rate**: 40% for common phrases
- **Cost Reduction**: 70% vs. baseline implementation
- **Uptime**: 99.9% with auto-failover

## 🛠️ Development

### Adding New Agents

1. Define personality vector in `agents/personas.py`
2. Add voice configuration in `agents/voice_config.py`
3. Create backstory and signature phrases
4. Test with validation suite

### Voice Tuning

Each agent's voice can be customized:

```python
VOICE_CONFIG = {
    "marcus_chen": {
        "provider": "elevenlabs",
        "voice_id": "adam",
        "settings": {
            "stability": 0.8,
            "similarity_boost": 0.7,
            "speed": 0.9
        }
    }
}
```

## 📱 API Examples

### Start a Debate

```bash
POST /api/debates/start
{
  "topic": "Should I start CMC despite the injury?",
  "agents": ["marcus", "big_mike", "zareena"],
  "user_context": {
    "league_type": "PPR",
    "team_needs": "must-win"
  }
}
```

### Get Voice Audio

```bash
GET /api/voice/generate
{
  "agent": "marcus",
  "text": "The regression model shows a 23.4% decrease in target share.",
  "emotion": "confident"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Built for the Pond Google Cloud Agents Hackathon
- Voice synthesis powered by ElevenLabs and OpenAI
- Deployed on Google Cloud Platform
- Special thanks to the fantasy football community for inspiration

## 📞 Contact

- Project Link: [https://github.com/yourusername/fantasy-football-neuron](https://github.com/yourusername/fantasy-football-neuron)
- Click on Discussions here at the Link


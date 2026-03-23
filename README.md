# 🏡 Atrio – AI Real Estate Assistant

> An intelligent virtual agent designed to transform real estate customer service.  
> Automate property listings, lead qualification, payment generation, and more — powered by generative AI, WhatsApp integration, and financial APIs.

---

## ✨ Overview

**Atrio** is an AI-powered virtual assistant that acts as a digital real estate agent.

It is capable of:

- Qualifying leads
- Recommending properties
- Classifying customer intent
- Generating payment requests (boletos)
- Integrating directly with WhatsApp

Built with a focus on **sales efficiency and scalability**, Atrio enables real estate businesses to automate high-volume interactions while maintaining personalized service.

---

## 🧠 Core Capabilities

- 🤖 AI-driven lead qualification
- 🏡 Smart property recommendation engine
- 📊 Lead scoring (hot / warm / cold)
- 💬 WhatsApp automation (via Waha API)
- 💳 Payment generation via Asaas API
- 🧾 AI-generated property descriptions (marketing copy)
- 🔀 Intelligent conversation routing based on user profile

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|--------|
| 🧠 LangGraph + LangChain | Agent orchestration and tool routing |
| 💬 OpenAI (GPT-4o-mini) | Natural language understanding & generation |
| 📦 MongoDB | Data storage (users, properties, leads, chat memory) |
| 💳 Asaas API | Payment processing and billing |
| 📱 Waha API | WhatsApp Business integration |
| ⚡ FastAPI | Backend services and API layer |
| 🐳 Docker | Containerized deployment |

---

## ⚙️ Features

### 👤 For Customers

- Search properties by:
  - Location
  - Price range
  - Property type
  - Number of bedrooms
- Receive personalized property recommendations
- Register interest (lead capture)
- Request payment slips (boletos)
- View previous charges

---

### 🧑‍💼 For Agents

- Register new clients and agents
- Add property listings with AI-generated descriptions
- Claim and manage leads
- Access lead history
- Generate payment requests
- Receive WhatsApp notifications for hot leads

---

### ⚡ Additional Features

- Automatic lead classification (hot, warm, cold)
- AI-generated real estate marketing copy
- Intelligent flow routing based on user intent
- Persistent chat memory per user (thread-based)

---

## 🔄 Example Flow

**User:**  
> "I'm looking for a house under R$2000 in Campos Elíseos"

**Atrio:**
- Understands intent and filters properties
- Returns matching listings
- Captures the user as a lead
- Classifies lead based on urgency and budget

➡️ If classified as a **hot lead**, a real estate agent is automatically notified via WhatsApp.

---

## 🏗️ Architecture Overview

- **Agent-based architecture** using LangGraph
- Modular tools for:
  - Property search
  - Lead management
  - Payment generation
- Persistent memory stored in MongoDB
- WhatsApp communication handled via Waha API
- External integrations (Asaas, MongoDB, OpenAI)

---

## 🛠️ Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/Vipires19/atrio_agent.git
cd atrio_agent
2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
3. Install dependencies
pip install -r requirements.txt
4. Configure environment variables

Create a .env file:

OPENAI_API_KEY=your_openai_key
MONGO_USER=your_mongo_user
MONGO_PASS=your_mongo_password
ASAAS_ACCESS_TOKEN=your_asaas_key
NGROK_AUTHTOKEN=your_ngrok_token

⚠️ Ngrok is used in development to expose HTTPS endpoints for webhook integration (Asaas).

5. Run the services

Run in two separate terminals:

Terminal 1:

docker-compose up --build waha

Terminal 2:

docker-compose up --build api

Running services separately improves debugging and observability.

📊 Data Structure
properties → available real estate listings
leads → qualified customer data
clients / agents → identified by phone number (thread_id)
chat_memory → persistent conversation history
📦 Example Interaction

User:

"Do you have 2-bedroom apartments under 2000 in downtown?"

Atrio:

Here are some options I found! 🏢✨

2-bedroom apartment, 65m² – Downtown – R$1,950
Available for visits ✅

Would you like to schedule a visit or talk to an agent?

⚠️ Notes
Atrio does not simulate financing, but can redirect users to specialists
Final negotiations and scheduling are handled by human agents
The system is designed to augment human productivity, not replace it
🔮 Future Improvements
Full RAG implementation with vector database
Advanced analytics dashboard for leads
Multi-agent orchestration
CRM integration
Multi-language support
Deployment on cloud infrastructure
👨‍💻 Author

Developed by Vinícius de Pires

📄 License

MIT License — feel free to use, modify and contribute.

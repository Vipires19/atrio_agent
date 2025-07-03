# 🏡 Átrio – Agente Virtual para Imobiliárias

> Um assistente digital inteligente para transformar o atendimento imobiliário.  
> Automatize o cadastro de imóveis, a qualificação de leads, a emissão de boletos e muito mais — tudo com IA generativa, WhatsApp e integração bancária.

---

## ✨ Visão Geral

O **Átrio** é um agente virtual que simula um corretor digital treinado para qualificar clientes, sugerir imóveis, classificar leads por potencial de compra e até mesmo emitir boletos via Asaas — tudo isso integrado ao WhatsApp por meio da API Waha.

Desenvolvido com foco em **eficiência comercial**, ele é ideal para imobiliárias que desejam escalar o atendimento com inteligência, agilidade e personalização.

---

## 🔧 Tecnologias Utilizadas

| Ferramenta | Finalidade |
|------------|------------|
| 🧠 LangGraph + LangChain | Criação do agente com roteamento e ferramentas |
| 💬 OpenAI GPT-4o-mini | Processamento de linguagem e geração de respostas |
| 🧾 API Asaas | Cadastro de clientes e geração de boletos |
| 📦 MongoDB | Armazenamento de usuários, imóveis, leads e histórico de conversas |
| 🤖 Waha API | Integração com WhatsApp Business |
| 🧭 Python + FastAPI | Backend do agente e interface com serviços externos |

---

## ⚙️ Funcionalidades

### Para clientes:
- Buscar imóveis por tipo, bairro, valor ou número de dormitórios
- Sugerir imóveis com base em preferências
- Registrar leads com orçamento e urgência
- Emitir 2ª via de boletos
- Consultar cobranças anteriores

### Para corretores:
- Cadastrar novos corretores e clientes
- Inserir novos imóveis com descrição automática via IA
- Assumir leads disponíveis
- Consultar histórico de leads
- Emitir boletos diretamente pela Asaas
- Receber notificações automáticas no WhatsApp

### Extras:
- Classificação de leads automática (quente, morno, frio)
- Descrição de imóveis gerada com IA (copy de marketing)
- Roteamento inteligente no fluxo com base no perfil do usuário

---

## 🧠 Exemplo de Fluxo

> 🧑 Cliente: "Gostaria de ver casas até R$2.000 no bairro Campos Elíseos"

→ O Átrio entende a intenção, aplica filtros, retorna imóveis compatíveis.  
→ Se houver interesse, registra como lead e classifica conforme urgência e orçamento.  
→ Caso classificado como lead quente, um corretor é notificado no WhatsApp.

---

## 🛠️ Como Rodar Localmente

1. **Clone o repositório**
   ```bash
   git clone https://github.com/seu-usuario/agent-imobiliario-atrio.git
   cd agent-imobiliario-atrio

2. **Crie e ative um ambiente virtual**
  ```bash
  python -m venv venv
  source venv/bin/activate  # Linux/Mac
  venv\Scripts\activate     # Windows
  ```

3. **Instale as dependências**
  ``` bash
  pip install -r requirements.txt
  ```

4. **Configure as variáveis de ambiente (.env)**
  ``` bash
  OPENAI_API_KEY= "SUA KEY DA OPENAI"
  MONGO_USER = "SEU USUÁRIO MONGODB"
  MONGO_PASS = "SUA SENHA MONGODB"
  ASSAS_ACCESS_TOKEN = "SUA KEY DO ASSAS"
  NGROK_AUTHTOKEN= "EM AMBIENTE DE DESENVOLVIMENTO UTILIZEI O NGROK PARA GERAR UM DOMÍNIO HTTPS PARA O WEBHOOK DO ASSAS ENTÃO É NECESSÁRIO O AUTHTOKEN DO NGROK"
  ```

5. **Execute o agente**

 Eu utilizo dois terminais:
  - Um com o comando:
     ``` bash
     docker-compose up --build waha
     ```
  - Outo com o comando:
     ``` bash
     docker-compose up --build api
     ```

Em minha humilde opinião torna mais fácil o DEBUG

## 📁 Estrutura dos Dados

**imoveis**: imóveis disponíveis com dados estruturados

**leads**: interessados com dados estratégicos para classificação

**clientes e corretores**: perfis identificados pelo número de telefone (thread_id)

**memoria_chat**: histórico da conversa persistente por thread

## 📦 Exemplos de Prompt e Resposta

**Usuário**: Tem apartamento de 2 quartos até 2000 reais no Centro?

**Átrio**: Aqui estão algumas opções que encontrei! 🏢✨
1. Apto com 2 dorm., 65m² – Bairro Centro – R$1.950
Disponível para visitação ✅

Deseja agendar uma visita ou falar com um corretor? 👨‍💼

## 💡 Algumas considerações

O Átrio não simula financiamento, mas pode sugerir contato com especialista
A disponibilidade final e agendamento são feitos por um corretor humano.
Em minha visão a proposta de toda IA é aumentar a produtividade e não substituir pessoas, por isso desenvolvi o fluxo do Átrio para gerar e classificar o interesse do usário e direcionar para um corretor, para que este assuma a "lead" e entre em contato com o interessado.

## 👨‍💻 Autor

Desenvolvido por Vinícius de Campos Pires
Policial militar, programador e entusiasta em IA aplicada a negócios reais.
📬 [LINKEDIN](https://www.linkedin.com/in/vin%C3%ADcius-de-campos-pires-544a88241/)

## 📄 Licença
MIT License - sinta-se livre para usar, adaptar e contribuir!


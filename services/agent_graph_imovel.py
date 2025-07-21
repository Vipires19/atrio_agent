import pandas as pd
import os
import uuid
import re
import json
import requests
from functools import wraps
from datetime import datetime
from pymongo import MongoClient
from dateutil.parser import parse
import urllib.parse
from io import BytesIO
from langchain_experimental.agents.agent_toolkits import create_python_agent
from langchain_experimental.tools.python.tool import PythonAstREPLTool
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.prebuilt import create_react_agent
from langchain_community.document_loaders import Docx2txtLoader
from langgraph.checkpoint.mongodb import MongoDBSaver
from langchain_openai import OpenAIEmbeddings
from langchain_mongodb.vectorstores import MongoDBAtlasVectorSearch
from langchain.agents.agent_types import AgentType
from langchain.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from typing_extensions import TypedDict
from services.waha import Waha
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig 
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import Annotated,Dict, Any
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from repositories.wbk_assas import Webhook


OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
MONGO_USER = urllib.parse.quote_plus(os.getenv('MONGO_USER'))
MONGO_PASS = urllib.parse.quote_plus(os.getenv('MONGO_PASS'))
embedding_model = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model="text-embedding-3-large")
client = MongoClient("mongodb+srv://%s:%s@cluster0.gjkin5a.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0" % (MONGO_USER, MONGO_PASS))
db = client.imobiliaria
coll_memoria = db.memoria_chat
coll_users = db.user
coll3 = db.imoveis
coll4 = db.leads
coll5 = db.corretores
coll6 = db.customers
coll7 = db.boletos
coll_vector = db.vetores
webhook_assas = Webhook()
access_token = os.getenv('ASSAS_ACCESS_TOKEN')
webhook_assas.create_webhook('imobi', access_token)
waha = Waha()

def carrega_txt(caminho):
    loader = Docx2txtLoader(caminho)
    lista_documentos = loader.load()
    documento = '\n\n'.join([doc.page_content for doc in lista_documentos])
    return documento

memory = MongoDBSaver(coll_memoria)

class State(TypedDict):
    messages: Annotated[list, add_messages]
    user_info: Dict[str, Any]

def check_user(state: dict, config: dict) -> dict:
    """
    Verifica se o usuário (cliente ou corretor) já está cadastrado no sistema, com base no telefone.
    Adiciona os dados como 'user_info' no estado do LangGraph.
    """
    try:
        thread_id = config["metadata"]["thread_id"]
        sem_sufixo = thread_id.replace("@c.us", "")
        telefone = sem_sufixo[2:]  # remove o 55

        usuario = coll5.find_one({"telefone": telefone})

        if not usuario:
            user_info = {"role": "cliente", "nome": "Não informado", "telefone": telefone}
        else:
            user_info = {
                "role": usuario.get("funcao", "cliente"),
                "nome": usuario.get("nome", "Não informado"),
                "telefone": telefone
            }

        # Retorna o estado original com user_info adicionado
        return {
            **state,
            "user_info": user_info
        }

    except Exception as e:
        print(f"[ERRO] check_user: {e}")
        # Em caso de erro, ainda retorna o estado sem quebrar o grafo
        return {
            **state,
            "user_info": {"role": "cliente", "nome": "Erro", "telefone": "indefinido"}
        }

SYSTEM_PROMPT = """
🏠 Backstory:
Você é o **Átrio**, assistente digital da imobiliária. Seu papel é **qualificar leads**, auxiliar os corretores e funcionários da imobiliária nas tarefas do dia a dia e responder dúvidas sobre imóveis com clareza e foco na conversão. Atua como um corretor virtual educado e objetivo.

📝 Registro e encaminhamento:
- Se o usuário demonstrar interesse em um imóvel, solicite os dados para utilizar a função `registrar_lead`.
- Quando perceber que o cliente deseja **agendar visita** ou **falar com corretor**, chame `encaminhar_para_corretor(id_lead)`.

🏡 Banco de dados:
Você pode consultar imóveis com os seguintes dados:
- título: Um breve resumo do imóvel
- tipo: Casa ou apartamento
- finalidade: aluguel ou compra
- endereço: Endereço físico do imóvel
- bairro: Bairro em que o imóvel está localizado
- cidade: Cidade em que o imóvel está localizado
- dormitórios: Número de quartos
- área útil: Área em m² do imóvel
- valor: Valor do imóvel
- condomínio: Valor do condomínio
- iptu: Valor do IPTU
- descrição: Descrição do imóvel
- disponível para visitação (sim ou não)

🛠️ Ações possíveis:
- Para corretores:
    - Cadastrar novos corretores e clientes, cadastrar novos imóveis
    - Buscar imóveis por tipo, bairro, valor, dormitórios ou finalidade
    - Enviar resumos comerciais com os principais dados do imóvel
    - Mostrar as leads disponíveis
    - Gerar boletos

- Para Clientes:
    - Buscar imóveis por tipo, bairro, valor, dormitórios ou finalidade
    - Coletar preferências e sugerir imóveis compatíveis
    - Registrar leads e encaminhar ao corretor quando apropriado
    - Enviar segunda via de boletos
    - Pesquisar cobranças/boletos gerados em seu nome

📋 Caso o cliente não saiba exatamente o que quer, pergunte:
- "Prefere casa ou apartamento?"
- "Tem algum bairro em mente?"
- "Qual o valor máximo que pretende investir ou pagar por mês?"
- "Precisa de quantos dormitórios ou vagas?"
- E com base nessas informações sugira um imóvel dentre os disponíveis

💬 Comunicação com o cliente:
- Seja educado, prestativo e direto ao ponto
- Use frases curtas, claras e amigáveis
- Não pressione o cliente, ajude com sugestões

🚫 Regras:
- Nunca solicite dados sensíveis
- Nunca divulgue dados de outros clientes
- Se não encontrar imóveis compatíveis, diga que o time comercial pode procurar alternativas
- Você terá acesso as informações como nome, telefone e função do usuário que está conversando com você, utilize essas informações nas funções que solicitem esses dados como parâmetro.

📈 Exemplos de perguntas:
- "Tem apartamento de 2 quartos até 2.000 no Centro?"
- "Quais casas estão disponíveis na zona sul pra alugar?"
- "Qual o valor de uma cobertura na Vila Tibério?"
- "Tem imóvel com 3 vagas e suíte?"

🔒 Limites:
- Não simula financiamento, mas pode sugerir contato com especialista
- A disponibilidade final e agendamento são feitos por um corretor humano

📤 Exemplo de saudação inicial:
"Olá! 👋 Sou o Átrio, assistente digital da nossa imobiliária. Me passa por favor, o que você está buscando! 🏡✨"
"""

@tool("consultar_material_de_apoio")
def consultar_material_de_apoio(pergunta: str) -> str:
    """
    Consulta o material de apoio técnico enviado pelos personal trainers para responder perguntas específicas.
    """
    vectorStore = MongoDBAtlasVectorSearch(coll_vector, embedding=embedding_model, index_name='default')
    docs = vectorStore.similarity_search(pergunta)
    if not docs:
        return "Nenhum conteúdo relevante encontrado no material de apoio."
    
    return "\n\n".join([doc.page_content[:400] for doc in docs])

# Função para gerar descrição de imóvel
def extrair_descricao_imovel(imovel: dict) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY, temperature=0)

    prompt = ChatPromptTemplate.from_template(
        """
        Sua tarefa é criar uma descrição com base nas características relevantes do imóvel.
        Pense que deve ser algo como um COPY para marketing, impactante, cativante e que realce o potencial do imóvel.
        Será usado para fazer divulgação do imóvel e até oferecê-lo para possíveis inquilinos ou compradores.

        Dados do imóvel:
        "{imovel}"

        A resposta deve ser uma string válida.
        """
    )
    
    messages = prompt.format_messages(imovel=imovel)
    resposta = llm(messages)
    return resposta.content

@tool("registra_imoveis_disponiveis")
def registra_imoveis_disponiveis(titulo: str,
                                tipo : str,
                                finalidade : str,
                                endereço : str,
                                bairro : str,
                                cidade : str,
                                dormitorios : float,
                                area : float,
                                valor : float,
                                condominio: float,
                                iptu: float,
                                disponivel: bool) -> str:
    """
    Cria a entrada de imóveis para o banco de dados. Apenas para corretores.
    """
    id_ref = str(uuid.uuid4())[:8]

    try:
        imovel = {'id_ref': id_ref,
                'título': titulo,
                'tipo': tipo,
                'finalidade': finalidade,
                'endereço': endereço,
                'bairro': bairro,
                'cidade': cidade,
                'dormitórios': dormitorios,
                'área útil': area,
                'valor': valor,
                'condomínio': condominio,
                'iptu': iptu,
                'disponível para visitação': disponivel}

        imovel['descricao'] = extrair_descricao_imovel(imovel)

        coll3.insert_one(imovel)  

        return f"Imóvel '{titulo}' cadastrado com sucesso!"

    except Exception as e:
        return f"Erro ao cadastrar imóvel: {str(e)}"

@tool("cria_novo_cliente")
def cria_novo_cliente(nome: str, cpf: str, email: str, celular: str, endereco: str, numero: str, bairro: str, cep: str) -> str:
    """
    Cria um cliente na API Asaas para permitir emissão de cobranças.
    Necessário fornecer: nome, CPF/CNPJ, email, celular, endereço, número, bairro e CEP.
    """
    url = "https://api-sandbox.asaas.com/v3/customers"

    payload = {
        "name": nome,
        "cpfCnpj": cpf,
        "email": email,
        "mobilePhone": celular,
        "address": endereco,
        "addressNumber": numero,
        "province": bairro,
        "postalCode": cep,
        "notificationDisabled": False
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "access_token": access_token
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        custumer_id = data.get("id")
        novo_cliente = {
            "nome": nome,
            "telefone": celular,
            "email": email,
            'id_asaas': custumer_id,
            "funcao" : 'cliente',
            "data_cadastro": datetime.now().isoformat()
        }

        coll6.insert_one(novo_cliente)

        if response.status_code == 200 or response.status_code == 201:
            return (
            f"✅ Novo cliente cadastrado com sucesso:\n"
            f"👤 Nome: {nome}\n"
            f"📞 Telefone: {celular}\n"
            f"📧 Email: {email}\n"
        )

        else:
            erro = data.get("errors") or data.get("message") or "Erro desconhecido"
            return f"❌ Falha ao cadastrar cliente: {erro}"

    except Exception as e:
        return f"Erro de exceção ao cadastrar cliente: {str(e)}"
    
@tool("criar_boleto_asaas")
def criar_boleto_asaas(
    customer_id: str,
    valor: float,
    vencimento: str,
    descricao: str,
    dias_pos_vencimento: int,
    dias_desconto: int,
    desconto: float = 0.0,
    multa: float = 0.0,
    juros: float = 0.0,
    referencia_interna: str = None
) -> str:
    """
    Cria um boleto bancário via Asaas para um cliente.

    Parâmetros:
    - customer_id: ID do cliente no Asaas
    - valor: valor total da cobrança
    - vencimento: data de vencimento no formato 'YYYY-MM-DD'
    - descricao: descrição da cobrança (opcional)
    - dias_pos_vencimento: Número de dias em que a cobrança é válida após o vencimento
    - desconto: percentual de desconto até o vencimento
    - dias_desconto: Número de dias antes do vencimento em que o desconto é válido
    - multa: percentual de multa após o vencimento (ex: 2.0 para 2%)
    - juros: percentual de juros ao mês após vencimento
    - referencia_interna: código de controle interno (opcional)

    Retorna link do boleto ou erro.
    """
    try:
        url = "https://api-sandbox.asaas.com/v3/payments"

        headers = {
            "Content-Type": "application/json",
            "access_token": access_token
        }

        payload = {
            "customer": customer_id,
            "billingType": "BOLETO",
            "value": valor,
            "dueDate": vencimento,
            "description": descricao,
            "daysAfterDueDateToRegistrationCancellation": dias_pos_vencimento,
            "discount": {
                "value": desconto,
                "dueDateLimitDays": dias_desconto,
                "type": "PERCENTAGE"
            },
            "interest": { "value": juros},
            "fine": {
                "value": multa,
                "type": "PERCENTAGE"
            },
        }

        if referencia_interna:
            payload["externalReference"] = referencia_interna

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code not in [200, 201]:
            return f"❌ Erro ao criar boleto: {response.status_code} - {response.text}"

        cobranca = response.json()
        link = cobranca.get("bankSlipUrl")

        retorno_cliente = (
            f"✅ *Novo boleto gerado para você!*\n"
            f"🧾 ID: {cobranca['id']}\n"
            f"💰 Valor: R$ {cobranca['value']:.2f}\n"
            f"📅 Vencimento: {cobranca['dueDate']}\n"
            f"🔗 Link do boleto: {link}"
        )

        url2 = f"https://api-sandbox.asaas.com/v3/customers/{customer_id}"
        response2 = requests.get(url2, headers=headers).json()
        telefone_cliente = response2.get('mobilePhone')
        chat_id= waha.verify_wid(telefone_cliente,'imobiliaria')
        waha.send_message(chat_id, retorno_cliente, 'imobiliaria')

        
        return (
            f"✅ *Boleto gerado com sucesso!*\n"
            f"🧾 ID: {cobranca['id']}\n"
            f"💰 Valor: R$ {cobranca['value']:.2f}\n"
            f"📅 Vencimento: {cobranca['dueDate']}\n"
            f"🔗 Link do boleto: {link}\n"
            f"O Boleto já foi enviado para {response2.get('name')}"
        )

    except Exception as e:
        return f"❌ Erro ao criar boleto: {str(e)}"

@tool('listar_cliente_pagamento')
def listar_cliente_pagamento(nome:str):
    """
    Lista os clientes cadastrados na API de pagamentos
    """
    try:
        url = "https://api-sandbox.asaas.com/v3/customers"

        headers = {
            "Content-Type": "application/json",
            "access_token": access_token
        }

        params = {"name": nome}
        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return f"Erro ao consultar clientes: {response.status_code} - {response.text}"

        data = response.json()
        items = data.get("data", [])

        if not items:
            return f"Nenhum cliente encontrado com o nome: {nome}"

        resposta = f"👤 Clientes encontrados com o nome *{nome}*:\n\n"
        for cliente in items[:5]:  # Limita para não exagerar
            resposta += (
                f"📌 ID: {cliente.get('id', '-')}\n"
                f"👤 Nome: {cliente.get('name', '-')}\n"
                f"📞 Telefone: {cliente.get('mobilePhone', '-')}\n"
                f"📧 Email: {cliente.get('email', '-')}\n"
                f"🔢 CPF/CNPJ: {cliente.get('cpfCnpj', '-')}\n"
                "--------------------------\n"
            )

        return resposta.strip()

    except Exception as e:
        return f"Erro ao listar cliente: {str(e)}"
    
@tool("pesquisar_cobrancas")
def pesquisar_cobrancas(nome: str = None, status: str = None) -> str:
    """
    Pesquisa cobranças no Asaas com base no ID do cliente e/ou status.
    Status pode ser: PENDING = Em aberto, RECEIVED = Paga, OVERDUE = Vencida, CONFIRMED = Confimada, etc.
    """
    try:
        url = "https://www.asaas.com/api/v3/payments"
        headers = {
            "Content-Type": "application/json",
            "access_token": access_token
        }

        params = {}
        if nome:
            params["customer"] = nome
        if status:
            params["status"] = status

        response = requests.get(url, headers=headers, params=params)

        if response.status_code != 200:
            return f"❌ Erro na requisição: {response.status_code} - {response.text}"

        dados = response.json()
        cobrancas = dados.get("data", [])

        if not cobrancas:
            return "🔎 Nenhuma cobrança encontrada com os filtros fornecidos."

        resultado = "📄 *Cobranças encontradas:*\n"
        for cobranca in cobrancas[:5]:  # limite de 5 para não poluir
            resultado += (
                f"\n🔹 *ID:* {cobranca['id']}\n"
                f"👤 Cliente: {cobranca.get('customer', 'N/A')}\n"
                f"💰 Valor: R$ {cobranca['value']:.2f}\n"
                f"📅 Vencimento: {cobranca.get('dueDate', 'N/A')}\n"
                f"📌 Status: {cobranca.get('status', 'N/A')}\n"
                f"🔗 Link: {cobranca.get('invoiceUrl', 'Sem link')}\n"
            )

        return resultado

    except Exception as e:
        return f"❌ Erro ao pesquisar cobranças: {str(e)}"

@tool("consultar_imovel")
def consultar_imovel(querries: list) -> str:
    """
    🔍 Consulta imóveis disponíveis no banco de dados com base em filtros personalizados.

    Parâmetros:
    - querries: lista de filtros para busca. Cada filtro deve ser um dict com:
        - key: nome do campo para filtrar
        - value: valor do filtro (pode ser string, número ou booleano)

    ⚠️ Use os nomes dos campos exatamente como estão no banco (com maiúsculas, acentos e espaços).
    """
    try:
        filtros = {}
        for querry in querries:
            chave = querry.get("key")
            valor = querry.get("value")
            if chave and valor != "":
                if isinstance(valor, str):
                    filtros[chave] = {"$regex": valor, "$options": "i"}
                else:
                    filtros[chave] = valor

        resultados = list(coll3.find(filtros, {'_id': 0}))

        if not resultados:
            return "Infelizmente, não localizei nenhum imóvel com essas características no momento. Deseja tentar com outros filtros ou deixar seu contato para ser avisado assim que houver novidade?"

        resposta_final = "🏡 *Imóveis encontrados com base na sua busca:*\n\n"

        for imovel in resultados[:5]:
            resposta_final += f"🔹 *{imovel.get('id_ref', '')}*\n"
            resposta_final += f"🔹 *{imovel.get('título', 'Imóvel')}*\n"
            resposta_final += f"{imovel.get('descricao', 'Descrição não disponível')}\n"
            resposta_final += f"📍 Bairro: {imovel.get('bairro', 'Bairro não informado')} - {imovel.get('cidade', 'Cidade não informada')}\n"
            resposta_final += f"🏠 Tipo: {imovel.get('tipo', 'N/A')} | Finalidade: {imovel.get('finalidade', 'N/A')}\n"
            resposta_final += f"🛏️ Dormitórios: {imovel.get('dormitórios', 'N/A')} | Área útil: {imovel.get('área útil', 'N/A')} m²\n"
            resposta_final += f"💰 Valor: R$ {imovel.get('valor', 0):,.2f} | Condomínio: R$ {imovel.get('condomínio', 0):,.2f} | IPTU: R$ {imovel.get('iptu', 0):,.2f}\n"
            resposta_final += f"📅 Disponível para visitação: {'Sim' if imovel.get('disponível para visitação') else 'Não'}\n"
            resposta_final += "-----------------------------------------------------\n\n"

        return resposta_final.strip()

    except Exception as e:
        return f"Erro ao consultar imóveis: {str(e)}"

@tool("gerar_lead_interessado")
def gerar_lead_interessado(nome:str,
                           telefone:str,
                           mensagem: str,
                           finalidade: str,
                           orcamento: float,
                           id_imovel: str,
                           urgencia: str) -> str:
    """
    Registra um lead com classificação estratégica baseada na finalidade, orçamento e urgência.
    Se faltar algum dado essencial, a função pede a informação ao cliente antes de seguir.

    Parametros:
    Nome: Nome do usuário
    Telefone: Telefone do usuário
    mensagem: Mensagem do usuário
    finalidade: Compra ou aluguel
    id_imovel: Id de referência do imóvel
    titulo: Título do imóvel
    bairro: Bairro do imóvel
    orcamento: Orçamento disponível do usuário
    urgencia: Urgência do usuário (alta, média ou baixa)
    """

    id_ref = str(uuid.uuid4())[:8]

    # 🔎 Validação prévia
    if not orcamento or orcamento <= 0:
        return (
            "💬 Para te ajudar da melhor forma, poderia me dizer qual o valor máximo que pretende investir ou pagar por mês? "
            "Essa informação é essencial para encontrar o imóvel ideal. 💰🏡"
        )

    if urgencia.strip().lower() not in ["alta", "média", "media", "baixa"]:
        return (
            "⚡ Só mais uma coisa: qual o seu nível de urgência? Alta, média ou baixa?\n"
            "Assim consigo priorizar seu atendimento da forma certa! 🔍"
        )

    imovel = coll3.find_one({"id_ref": id_imovel})

    try:
        lead = {
            "nome": nome,
            "telefone": telefone,
            "mensagem_original": mensagem,
            "finalidade": finalidade.lower(),
            "imovel": imovel["titulo"],
            "bairro_interesse": imovel["bairro"],
            "orçamento_aproximado": orcamento,
            "urgencia": urgencia.lower(),
            "status": "disponível",
            "id_ref": id_ref,
            "canal": "assistente_virtual",
            "data_criacao": datetime.now().isoformat()
        }

        corretores = list(coll5.find({'funcao': 'corretor'}))
        contatos = [c['telefone'] for c in corretores]

        if imovel:
            valor_imovel = imovel["valor"]
            relacao = orcamento / valor_imovel

            lead["imovel_relacionado"] = {
                "id": imovel["id_ref"],
                "Título": imovel["titulo"],
                "Valor": valor_imovel,
                "Bairro": imovel["bairro"]
            }

            # 🧠 Classificação de lead
            urg = urgencia.lower()
            if finalidade.lower() == "compra":
                if relacao >= 0.7:
                    lead["classificacao"] = "lead quente"
                elif relacao >= 0.5 and urg == 'alta':
                    lead["classificacao"] = "lead quente"
                elif relacao >= 0.5:
                    lead["classificacao"] = "lead morno"
                elif urg == 'alta':
                    lead["classificacao"] = "lead morno"
                else:
                    lead["classificacao"] = "lead frio"
            elif finalidade.lower() in ["locação", "aluguel"]:
                if relacao >= 0.7 and urg == "alta":
                    lead["classificacao"] = "lead quente"
                elif relacao >= 0.7:
                    lead["classificacao"] = "lead morno"
                else:
                    lead["classificacao"] = "lead frio"
            else:
                lead["classificacao"] = "em análise"
        else:
            lead["imovel_relacionado"] = "Não identificado automaticamente"
            lead["classificacao"] = "em análise"

        coll4.insert_one(lead)

        if lead["classificacao"] in ["lead quente", "lead morno"]:
            mensagem_corretor = (
                f"📢 *Novo Lead no Sistema*:\n"
                f"📌 ID: {lead['id_ref']}\n"
                f"👤 Cliente: {lead['nome']}\n"
                f"📞 Contato: {lead['telefone']}\n"
                f"🏡 Imóvel: {lead['imovel']} ({lead['finalidade']})\n"
                f"📍 Bairro: {lead['bairro_interesse']}\n"
                f"💰 Orçamento: R$ {lead['orçamento_aproximado']:,.2f}\n"
                f"⚡ Urgência: {lead['urgencia']}\n"
                f"🔥 Classificação: *{lead['classificacao'].upper()}*"
            )

            for contato in contatos:
                try:
                    chat_id = waha.verify_wid(contato, 'imobiliaria')
                    waha.send_message(chat_id, mensagem_corretor, 'imobiliaria')
                except Exception as e:
                    print(f"Erro ao notificar corretor {contato}: {e}")

        # 🎯 Resposta adaptada ao cliente
        respostas = {
            "lead quente": (
                "🚀 Obrigado pelo seu interesse!\n"
                "Seu perfil foi classificado como *lead quente*, e um de nossos corretores já está sendo acionado "
                "pra falar com você! 💬"
            ),
            "lead morno": (
                "🟡 Obrigado pelo interesse!\n"
                "Seu perfil está no radar e em breve um corretor pode entrar em contato pra entender melhor suas preferências."
            ),
            "lead frio": (
                "🔍 Lead registrado com sucesso!\n"
                "Se surgir mais alguma info sobre orçamento ou urgência, posso te ajudar a encontrar algo mais certeiro!"
            ),
            "em análise": (
                "✅ Lead registrado!\n"
                "Vamos avaliar sua solicitação e um de nossos especialistas pode te chamar em breve. TKS pelo contato!"
            )
        }

        return respostas.get(lead["classificacao"], "✅ Lead registrada!")

    except Exception as e:
        return f"❌ Erro ao registrar lead: {str(e)}"

@tool("consultar_leads_disponiveis")
def consultar_leads_disponiveis(nome: str = None,
                                 telefone: str = None,
                                 classificacao: str = None,
                                 finalidade: str = None) -> str:
    """
    Consulta leads cadastradas no banco de dados. Pode retornar:
    - Todas as leads
    - Uma lead específica pelo nome ou telefone
    - Leads filtradas por classificação (quente, morno, frio) ou finalidade (compra, locação)
    """

    try:
        filtro = {}

        if nome:
            filtro["nome"] = {"$regex": nome, "$options": "i"}

        if telefone:
            filtro["telefone"] = {"$regex": telefone, "$options": "i"}

        if classificacao:
            filtro["classificacao"] = {"$regex": classificacao, "$options": "i"}

        if finalidade:
            filtro["finalidade"] = {"$regex": finalidade, "$options": "i"}

        resultados = list(coll4.find(filtro).sort("data_criacao", -1))

        if not resultados:
            return "Nenhuma lead encontrada com os filtros informados. Verifique os dados e tente novamente."


        resposta = ""
        for lead in resultados[:10]:  # Limita a 10 leads mais recentes por segurança
            if lead.get('status') == 'disponível':
                resposta += (
                    f"📋 *ID - {lead.get('id_ref', 'ID não informado')}*\n"
                    f"📋 *Lead - {lead.get('nome', 'Nome não informado')}*\n"
                    f"📞 Telefone: {lead.get('telefone', '-')}\n"
                    f"🏷️ Finalidade: {lead.get('finalidade', '-').capitalize()} | Imóvel: {lead.get('imovel', '-')}\n"
                    f"📍 Bairro: {lead.get('bairro_interesse', '-')}\n"
                    f"💰 Orçamento: R$ {lead.get('orçamento_aproximado', 0):,.2f}\n"
                    f"⚡ Urgência: {lead.get('urgencia', '-').capitalize()}\n"
                    f"🔥 Classificação: *{lead.get('classificacao', '-').upper()}*\n"
                )
                data_criacao_str = lead.get("data_criacao")
                if data_criacao_str:
                    try:
                        data_fmt = parse(data_criacao_str).strftime('%d/%m/%Y às %Hh%M')
                    except:
                        data_fmt = data_criacao_str
                else:
                    data_fmt = "-"
                resposta += f"📅 Data de criação: {data_fmt}\n\n"

            return resposta

    except Exception as e:
        return f"Erro ao consultar leads: {str(e)}"

@tool("assumir_lead_por_id")
def assumir_lead_por_id(id_ref: str, nome: str, telefone: str, role: str) -> str:
    """
    Corretor assume o atendimento de uma lead informando o ID de referência.
    Atualiza status para 'em_atendimento' e registra quem assumiu.
    """
    
    try:
        lead = coll4.find_one({"id_ref": id_ref})

        if not lead:
            return f"❌ Nenhuma lead encontrada com o ID #{id_ref}."

        if lead.get("status") == "em_atendimento":
            return f"⚠️ Essa lead já foi assumida anteriormente."

        else:
            coll4.update_one(
                {"id_ref": id_ref},
                {"$set": {
                    "status": "em_atendimento",
                    "assumido_por": nome,
                    "telefone_corretor": telefone,
                    "data_assumido": datetime.now().isoformat()
                }}
            )

            return (
                f"✅ Lead #{id_ref} assumida com sucesso por {nome}.\n"
                f"A partir de agora, essa lead está *em atendimento*."
            )

    except Exception as e:
        return f"Erro ao assumir lead: {str(e)}"
        
@tool("cadastrar_novo_corretor")
def cadastrar_novo_corretor(nome_novo: str,
                            telefone_novo: str,
                            role: str,
                            email_novo: str = None,
                            status: str = "ativo") -> str:
    """
    Permite que um corretor autorizado cadastre um novo corretor no sistema.
    Campos obrigatórios: nome_novo, telefone_novo.
    Apenas corretores podem usar esta ferramenta.
    """

    
    try:
        # Verifica se já existe esse corretor
        existente = coll5.find_one({"telefone": telefone_novo})

        if existente:
            return f"⚠️ Já existe um corretor com esse telefone cadastrado: {existente.get('nome')}."

        novo_corretor = {
            "nome": nome_novo,
            "telefone": telefone_novo,
            "email": email_novo,
            "funcao": "corretor",
            "status": status.lower(),
            "data_cadastro": datetime.now().isoformat()
        }

        coll5.insert_one(novo_corretor)
        thread_id = f"55{telefone_novo}@c.us"
        memory.put(thread_id, {"nome": nome_novo, "telefone": telefone_novo, "role": "corretor"})

        return (
            f"✅ Novo corretor cadastrado com sucesso:\n"
            f"👤 Nome: {nome_novo}\n"
            f"📞 Telefone: {telefone_novo}\n"
            f"📧 Email: {email_novo if email_novo else 'não informado'}\n"
            f"🗂️ Status: {status.capitalize()}"
        )

    except Exception as e:
        return f"❌ Erro ao cadastrar corretor: {str(e)}"    
    
@tool("enviar_segunda_via_boleto")
def enviar_segunda_via_boleto(telefone: str) -> str:
    """
    Busca o boleto mais recente para o telefone informado e retorna o link para o usuário.
    Caso não encontre, avisa que o boleto não está disponível.
    Instrua o formato que o usuário deve passar o telefone. Ex: 16981394877.
    """

    try:
        customer_id = coll6.find_one({"telefone": telefone})["id_asaas"]

        url = f"https://api-sandbox.asaas.com/v3/payments?customer={customer_id}"

        headers = {
            "Content-Type": "application/json",
            "access_token": access_token
        }

        response = requests.get(url, headers=headers).json()
        boleto = response["data"][0]

        retorno = (
            f"✅ *2ª via do Boleto!*\n"
            f"🧾 ID: {boleto['id']}\n"
            f"💰 Valor: R$ {boleto['value']:.2f}\n"
            f"📅 Vencimento: {boleto['dueDate']}\n"
            f"🔗 Link do boleto: {boleto['bankSlipUrl']}"
        )

        if not response:
            return "❌ Não encontrei nenhum boleto cadastrado para este telefone."

        return retorno

    except Exception as e:
        return f"❌ Erro ao buscar boleto: {str(e)}"
    
tools_node = [cadastrar_novo_corretor,
         registra_imoveis_disponiveis,
         consultar_material_de_apoio,
         consultar_imovel,
         gerar_lead_interessado,
         consultar_leads_disponiveis,
         assumir_lead_por_id,
         enviar_segunda_via_boleto,
         cria_novo_cliente,
         pesquisar_cobrancas,
         criar_boleto_asaas,
         listar_cliente_pagamento]
  
class AgentMobi:
    def __init__(self):
        self.memory = self._init_memory()
        self.model = self._build_agent()

    def _init_memory(self):
        # 💥 Aqui usamos o método CORRETO pra sua versão (sem context manager!)
        memory = MongoDBSaver(coll_memoria)
        return memory
    
    def _build_agent(self):
        graph_builder = StateGraph(State)
        #tools =tools_node
        #llm = ChatOpenAI(model="gpt-4o-mini",openai_api_key=OPENAI_API_KEY, streaming=True)
        #llm_with_tools = llm.bind_tools(tools=tools)
        
        tool_vector_search = ToolNode(tools=[consultar_material_de_apoio])

        tools_corretor = [cadastrar_novo_corretor,
         registra_imoveis_disponiveis,
         consultar_imovel,
         gerar_lead_interessado,
         consultar_leads_disponiveis,
         assumir_lead_por_id,
         cria_novo_cliente,
         criar_boleto_asaas,
         listar_cliente_pagamento]
        
        tools_cliente = [consultar_imovel,
         gerar_lead_interessado,
         enviar_segunda_via_boleto,
         pesquisar_cobrancas]
        
        tools_node_corretor = ToolNode(tools=tools_corretor)
        tools_node_cliente = ToolNode(tools=tools_cliente)

        def chatbot(state: State, config: RunnableConfig) -> State:
            try:
                user_info = state.get("user_info", {})
                nome = user_info.get("nome", "usuário")
                role = user_info.get("role", "cliente")
                telefone = user_info.get("telefone", "indefinido")

                llm = ChatOpenAI(model="gpt-4o-mini",openai_api_key=OPENAI_API_KEY, streaming=True)
                if role == "corretor":
                    tools = tools_corretor
                else:
                    tools = tools_cliente

                llm_with_tools = llm.bind_tools(tools=tools)

                system_prompt = SystemMessage(content=SYSTEM_PROMPT + f"\n\nO nome do usuário é {nome}, e ele é um {role}. Telefone {telefone}")
                
                response = llm_with_tools.invoke([system_prompt] + state["messages"])

            except Exception as e:
                print(f"[ERRO chatbot]: {e}")
                raise

            return {
                "user_info": state["user_info"],
                "messages": state["messages"] + [response]
            }

        def routing_function(state: State):
            role = state.get("user_info", {}).get("role", "").lower()
            print(f"[ROUTING FUNCTION] Direcionando com base em role='{role}'")
            if role == "corretor":
                return "corretor"
            elif role == "cliente":
                return "cliente"
            else:
                return "cliente"

        # Adiciona os estados
        graph_builder.add_node("entrada_usuario", RunnableLambda(lambda state: {"messages": state["messages"], "user_info": {}}))  # só repassa o input
        graph_builder.add_node("check_user_role", RunnableLambda(check_user))
        graph_builder.add_node("chatbot", chatbot)
        graph_builder.add_node("corretor", tools_node_corretor)
        graph_builder.add_node("cliente", tools_node_cliente)
        graph_builder.add_node("consultar_vector", tool_vector_search)

        # Corrige a ordem de fluxo: chatbot antes de tool nodes
        graph_builder.set_entry_point("entrada_usuario")
        graph_builder.add_edge("entrada_usuario", "check_user_role")
        graph_builder.add_edge("check_user_role", "chatbot")
        graph_builder.add_conditional_edges("chatbot", routing_function, {
            'corretor': 'corretor',
            'cliente': 'cliente'
        })

        # Finalizações
        graph_builder.add_edge("corretor", END)
        graph_builder.add_edge("cliente", END)
        graph_builder.add_edge("consultar_vector", END)

        memory = MongoDBSaver(coll_memoria)
        graph = graph_builder.compile(checkpointer=memory)
        return graph

    def memory_agent(self):
        return self.model    
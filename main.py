# funcionando com envio de e-mail 17-06
# versão completa com todas as funcionalidades solicitadas
# versão liberada para usuário com correção de fuso horário e uso exclusivo de datas manuais
# envio de email atraves do gmail


import streamlit as st
st.set_page_config(page_title="Entregas - Tempo de Permanência", layout="wide")

import os
import re
import time as tm
import uuid
import html
import bcrypt
import socket
import smtplib
import requests
from datetime import datetime, timedelta, timezone, date, time
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

import pandas as pd
import pytz
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from streamlit_cookies_manager import EncryptedCookieManager

from supabase import create_client, Client as SupabaseClient

load_dotenv()
# --- CONFIGURAÇÕES DE E-MAIL DA KINGHOST ---
# Estas configurações podem ser movidas para um arquivo .env se preferir
EMAIL_REMETENTE = "ticketclicklogtransportes@gmail.com"
EMAIL_SENHA = "hlossktfkqlsxepo"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
# Configurar timeout para operações de socket
socket.setdefaulttimeout(10)  # 10 segundos de timeout

# --- DEFINIÇÃO DO FUSO HORÁRIO BRASILEIRO ---
# Usar este fuso horário em todas as operações de data/hora
FUSO_HORARIO_BRASIL = pytz.timezone("America/Sao_Paulo")

# --- SETUP DO COOKIE MANAGER ---
cookies = EncryptedCookieManager(
    prefix="meu_app_",  # Prefixo dos cookies
    password="chave-muito-secreta-para-cookies"  # Troque por uma senha forte
)
if not cookies.ready():
    st.stop()


# --- Função para verificar se o cookie expirou ---
def is_cookie_expired(expiry_time_str):
    try:
        expiry_time = datetime.strptime(expiry_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) > expiry_time





# --- Função de autenticação ---
def autenticar_usuario(nome_usuario, senha):
    try:
        dados_usuario = supabase.table("usuarios").select("*").eq("nome_usuario", nome_usuario).execute()

        if dados_usuario.data:
            usuario = dados_usuario.data[0]
            if verificar_senha(senha, usuario["senha_hash"]):
                return usuario
        return None
    except Exception:
        return None

# --- CONEXÃO COM O SUPABASE ---
url = "https://vismjxhlsctehpvgmata.supabase.co"  # ✅ sua URL real, já sem o '>' no meio
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpc21qeGhsc2N0ZWhwdmdtYXRhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY1NzA4NTIsImV4cCI6MjA2MjE0Njg1Mn0.zTjSWenfuVJTIixq2RThSUpqcHGfZWP2xkFDU3USPb0"  # ✅ sua chave real (evite expor em público!)
supabase = create_client = create_client(url, key)


# Função para hash de senha
def hash_senha(senha):
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

# Criar usuário via Supabase Auth e tabela `usuarios`
# Criar usuário direto na tabela 'usuarios' (sem Supabase Auth)

# Função para verificar se a senha fornecida corresponde ao hash
def verificar_senha(senha_fornecida, senha_hash):
    return bcrypt.checkpw(senha_fornecida.encode(), senha_hash.encode())
    
usuario_logado = "admin"  # Exemplo de nome de usuário do admin logado
dados_usuario = {
    "nome_usuario": "admin",
    "senha_hash": "$2b$12$OqjiW19Pjd9.eGnFfmJSrW.TqX/pq6RmPjbsHbuZ56MzeP3dNKuyq"  # Exemplo de senha já hashada (gerada com bcrypt)
}
    
# Função de autenticação simples com mensagens
def autenticar_usuario(nome_usuario, senha):
    try:
        dados = supabase.table("usuarios").select("*").eq("nome_usuario", nome_usuario).execute()

        if dados.data:
            usuario = dados.data[0]
            if verificar_senha(senha, usuario["senha_hash"]):
                st.success("✅ Logado com sucesso!")
                return usuario
        st.error("🛑 Usuário ou senha incorretos.")
        return None

    except Exception as e:
        st.error("Erro ao autenticar.")
        return None

# --- Interface de Login ---
def login():
    login_cookie = cookies.get("login")
    username_cookie = cookies.get("username")
    is_admin_cookie = cookies.get("is_admin")
    expiry_time_cookie = cookies.get("expiry_time")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>📝 Entregas - Tempo de Permanência </h1>", unsafe_allow_html=True)

    # Se o login já foi feito e o cookie não expirou, configura a sessão
    if login_cookie and username_cookie and not is_cookie_expired(expiry_time_cookie):
        # Buscar unidade do usuário logado
        try:
            usuario_data = supabase.table("usuarios").select("unidade").eq("nome_usuario", username_cookie).execute().data
            unidade_cookie = usuario_data[0]["unidade"] if usuario_data else "Não definida"
        except:
            unidade_cookie = "Não definida"

        # Preenche session_state
        st.session_state.login = True
        st.session_state.username = username_cookie
        st.session_state.is_admin = is_admin_cookie == "True"
        st.session_state.unidade = unidade_cookie

        st.markdown(f"👋 **Bem-vindo, {st.session_state.username}!**")

        # Botão de logout
        col1, col2, col3 = st.columns([6, 1, 1])
        with col3:
            if st.button("🔒 Sair", key="logout_button"):
                cookies["login"] = ""
                cookies["username"] = ""
                cookies["is_admin"] = ""
                cookies["expiry_time"] = ""
                cookies.save()
                st.session_state.login = False
                st.rerun()

    else:
        # Exibe formulário de login
        with col2:
            st.markdown("##### Login")
            username = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")

            if st.button("Entrar", key="login_button"):
                usuario = autenticar_usuario(username, senha)
                if usuario:
                    # Armazenar cookies
                    cookies["login"] = str(True)
                    cookies["username"] = usuario["nome_usuario"]
                    cookies["is_admin"] = str(usuario.get("is_admin", False))
                    expiry_time = datetime.now(timezone.utc) + timedelta(hours=24)
                    cookies["expiry_time"] = expiry_time.strftime("%Y-%m-%d %H:%M:%S")
                    cookies.save()

                    # Armazenar na sessão
                    st.session_state.login = True
                    st.session_state.username = usuario["nome_usuario"]
                    st.session_state.is_admin = usuario.get("is_admin", False)
                    st.session_state.unidade = usuario.get("unidade", "Não definida")

                    st.rerun()

        st.stop()
  # Impede que o código continue sendo executado após login falhar


# --- Chama login antes de qualquer coisa ---
login()


# --- SE CHEGOU AQUI, USUÁRIO ESTÁ AUTENTICADO ---
#--------------------------------------------------------------------------INICIO APP -------------------------------------------------------------


#- -- INICIALIZAÇÃO DE SESSÃO ---
if "ocorrencias_abertas" not in st.session_state:
    st.session_state.ocorrencias_abertas = []

if "ocorrencias_finalizadas" not in st.session_state:
    st.session_state.ocorrencias_finalizadas = []

if "historico_emails" not in st.session_state:
    st.session_state.historico_emails = []

if "focal_selecionado" not in st.session_state:
    st.session_state.focal_selecionado = None

# Inicialização da configuração de tempo de envio de e-mail
if "tempo_envio_email" not in st.session_state:
    st.session_state.tempo_envio_email = 30  # Valor padrão: 30 minutos

# =============================
# NAVEGAÇÃO ENTRE ABAS COM RADIO
# =============================

abas_admin = {
    "📝 Nova Ocorrência": "aba1",
    "📌 Ocorrências em Aberto": "aba2",
    "✅ Ocorrências Finalizadas": "aba3",
    "📊 Configurações": "aba4",
    "📧 Notificações por E-mail": "aba6",
    "🔄 Cadastros": "aba7",
    "📊 Estatística": "aba8"
}

abas_usuario = {
    "📝 Nova Ocorrência": "aba1",
    "📌 Ocorrências em Aberto": "aba2",
    "✅ Ocorrências Finalizadas": "aba3",
    "📊 Configurações": "aba4",
    "🔄 Cadastros": "aba7",
    "📊 Estatística": "aba8"
}

abas = abas_admin if st.session_state.is_admin else abas_usuario

# Exibe o menu lateral
aba_nome = st.sidebar.radio("📁 Menu", list(abas.keys()), key="menu_abas")

# Salva qual aba está ativa
st.session_state.aba_ativa = abas[aba_nome]



# Definindo a conexão com o banco de dados (ajuste com as suas credenciais)
def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname="nome_do_banco",
            user="usuario",
            password="senha",
            host="host_do_banco",
            port="porta"
        )
        return conn
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# --- FUNÇÕES DE DATA E HORA COM FUSO HORÁRIO ---

def obter_data_hora_atual_brasil():
    """Retorna a data e hora atual no fuso horário do Brasil."""
    return datetime.now(FUSO_HORARIO_BRASIL)

def converter_para_fuso_brasil(data_hora):
    """Converte uma data/hora para o fuso horário do Brasil."""
    if data_hora.tzinfo is None:
        # Se não tiver fuso, assume UTC
        data_hora = data_hora.replace(tzinfo=timezone.utc)
    return data_hora.astimezone(FUSO_HORARIO_BRASIL)

def calcular_diferenca_tempo(data_hora_inicial, data_hora_final=None):
    """Calcula a diferença entre duas datas/horas no mesmo fuso horário."""
    if data_hora_final is None:
        data_hora_final = obter_data_hora_atual_brasil()
    
    # Garantir que ambas as datas estão no mesmo fuso
    if data_hora_inicial.tzinfo is None:
        data_hora_inicial = FUSO_HORARIO_BRASIL.localize(data_hora_inicial)
    else:
        data_hora_inicial = data_hora_inicial.astimezone(FUSO_HORARIO_BRASIL)
    
    if data_hora_final.tzinfo is None:
        data_hora_final = FUSO_HORARIO_BRASIL.localize(data_hora_final)
    else:
        data_hora_final = data_hora_final.astimezone(FUSO_HORARIO_BRASIL)
    
    return data_hora_final - data_hora_inicial

def criar_datetime_manual(data_str, hora_str):
    """Cria um objeto datetime a partir de strings de data e hora, com fuso horário do Brasil."""
    try:
        data_hora_str = f"{data_str} {hora_str}"
        data_hora = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M:%S")
        return FUSO_HORARIO_BRASIL.localize(data_hora)
    except Exception as e:
        st.error(f"Erro ao criar datetime manual: {e}")
        return None

# Função de inserção no Supabase
def inserir_ocorrencia_supabase(dados):
    # Criar data_hora_abertura a partir dos campos manuais
    data_hora_manual = criar_datetime_manual(dados["data_abertura_manual"], dados["hora_abertura_manual"])
    
    if data_hora_manual:
        # Usar a data/hora manual para todos os campos de data/hora
        data_hora_str = data_hora_manual.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = data_hora_manual.isoformat()
        
        response = supabase.table("ocorrencias").insert([{
            "id": dados["id"],
            "nota_fiscal": dados["nota_fiscal"],
            "cliente": dados["cliente"],
            "focal": dados["focal"],
            "destinatario": dados["destinatario"],
            "cidade": dados["cidade"],
            "motorista": dados["motorista"],
            "tipo_de_ocorrencia": dados["tipo_de_ocorrencia"],
            "observacoes": dados["observacoes"],
            "responsavel": dados["responsavel"],
            "status": "Aberta",
            "data_hora_abertura": data_hora_str,  # Usar data/hora manual
            "abertura_timestamp": timestamp_iso,  # Usar data/hora manual
            "permanencia": dados["permanencia"],
            "complementar": dados["complementar"],
            "data_abertura_manual": dados["data_abertura_manual"],
            "hora_abertura_manual": dados["hora_abertura_manual"],
            "email_abertura_enviado": False,
            "email_finalizacao_enviado": False,
            "imagem_url": dados["imagem_url"],
            "ticket_unidade": dados["ticket_unidade"]

        }]).execute()
        return response
    else:
        st.error("Erro ao criar data/hora manual para inserção no banco")
        return None


# --- CARREGAMENTO DE DADOS Tabelas com nomes de motorista e clientes ---
def carregar_clientes_supabase():
    try:
        response = supabase.table("clientes").select("cliente, focal, enviar_para_email, email_copia").execute()
        if response.data:
            df_clientes = pd.DataFrame(response.data)
            df_clientes = df_clientes.dropna(subset=["cliente"])
            return df_clientes
        else:
            return pd.DataFrame(columns=["cliente", "focal", "enviar_para_email", "email_copia"])
    except Exception as e:
        st.error(f"Erro ao carregar clientes do banco: {e}")
        return pd.DataFrame(columns=["cliente", "focal", "enviar_para_email", "email_copia"])

# Carregar dados
df_clientes = carregar_clientes_supabase()

# Dicionários úteis
cliente_to_focal = dict(zip(df_clientes["cliente"], df_clientes["focal"]))
cliente_to_emails = {
    row["cliente"]: {
        "principal": row.get("enviar_para_email", ""),
        "copia": row.get("email_copia", "")
    }
    for _, row in df_clientes.iterrows()
}
clientes = df_clientes["cliente"].tolist()



# Buscar lista de cidades diretamente do Supabase
def carregar_cidades_supabase():
    try:
        response = supabase.table("cidades").select("cidade").execute()
        #st.write("✅ Cidades no banco:", response.data)  # para debug
        if response.data:
            cidades = [item["cidade"] for item in response.data if item.get("cidade")]
            return sorted(set(cidades))  # Ordena e remove duplicados
        else:
            return []
    except Exception as e:
        st.error(f"Erro ao carregar cidades do banco: {e}")
        return []

cidades = carregar_cidades_supabase()


# Buscar lista de motoristas diretamente do Supabase
def carregar_motoristas_supabase():
    try:
        motoristas = []
        pagina = 0
        pagina_tamanho = 1000  # Supabase retorna no máximo 1000 por requisição

        while True:
            resposta = supabase.table("motoristas") \
                .select("motorista") \
                .range(pagina * pagina_tamanho, (pagina + 1) * pagina_tamanho - 1) \
                .execute()

            dados = resposta.data
            if not dados:
                break

            motoristas.extend([item["motorista"].strip() for item in dados if item.get("motorista")])
            pagina += 1

        return sorted(set(motoristas))

    except Exception as e:
        st.error(f"Erro ao carregar motoristas do banco: {e}")
        return []



motoristas = carregar_motoristas_supabase()

try:
    resposta = supabase.table("motoristas").select("*").execute()
    
except Exception as e:
    st.error(f"Erro ao consultar a tabela motoristas: {e}")

# Buscar lista de focais diretamente do Supabase
def carregar_focal_supabase():
    try:
        response = supabase.table("clientes").select("focal").execute()
        if response.data:
            focais = [item["focal"] for item in response.data if item.get("focal")]
            return sorted(set(focais))
        else:
            return []
    except Exception as e:
        st.error(f"Erro ao carregar focais do banco: {e}")
        return []

# --- FUNÇÕES PARA A ABA CADASTROS ---

def validar_texto_maiusculo(texto):
    """Verifica se o texto está em letras maiúsculas."""
    return texto == texto.upper()

def validar_email(email):
    """Verifica se o e-mail tem um formato válido."""
    import re
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None

def validar_emails_multiplos(emails):
    """Verifica se múltiplos e-mails separados por ; têm formato válido."""
    if not emails:
        return True
    
    import re
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    for email in emails.split(';'):
        email = email.strip()
        if email and not re.match(padrao, email):
            return False
    
    return True

def inserir_motorista(motorista):
    """Insere um novo motorista no Supabase."""
    try:
        response = supabase.table("motoristas").insert({"motorista": motorista}).execute()
        return True, "Motorista cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar motorista: {e}"

def inserir_cidade(cidade):
    """Insere uma nova cidade no Supabase."""
    try:
        response = supabase.table("cidades").insert({"cidade": cidade}).execute()
        return True, "Cidade cadastrada com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar cidade: {e}"

def inserir_cliente(cliente, focal, enviar_email, email_principal, email_copia):
    """Insere um novo cliente no Supabase."""
    try:
        response = supabase.table("clientes").insert({
            "cliente": cliente,
            "focal": focal,
            "enviar_para_email": email_principal,
            "email_copia": email_copia,
            "receber_emails": enviar_email
        }).execute()
        return True, "Cliente cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar cliente: {e}"

def atualizar_tempo_envio_email(minutos):
    """Atualiza o tempo de envio de e-mail na configuração."""
    try:
        # Atualiza na sessão
        st.session_state.tempo_envio_email = minutos
        
        # Atualiza no banco de dados (supondo que exista uma tabela de configurações)
        response = supabase.table("configuracoes").upsert({
            "chave": "tempo_envio_email",
            "valor": str(minutos)
        }).execute()
        
        return True, f"Tempo de envio de e-mail atualizado para {minutos} minutos!"
    except Exception as e:
        return False, f"Erro ao atualizar tempo de envio de e-mail: {e}"

def carregar_tempo_envio_email():
    """Carrega o tempo de envio de e-mail da configuração."""
    try:
        response = supabase.table("configuracoes").select("valor").eq("chave", "tempo_envio_email").execute()
        if response.data:
            return int(response.data[0]["valor"])
        else:
            return 30  # Valor padrão
    except Exception as e:
        st.error(f"Erro ao carregar tempo de envio de e-mail: {e}")
        return 30  # Valor padrão em caso de erro

# --- FORMULÁRIO PARA NOVA OCORRÊNCIA ---

# =========================
#     ABA 1 - NOVA OCORRENCIA
# =========================
if st.session_state.aba_ativa == "aba1":
    st.header("Nova Ocorrência")

    # Definindo sessão focal_responsavel
    if "focal_responsavel" not in st.session_state:
        st.session_state["focal_responsavel"] = ""

    # Formulário para nova ocorrência
    with st.form("form_nova_ocorrencia", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            nf = st.text_input("Nota Fiscal", key="nf")
            nf_invalida = nf != "" and not nf.isdigit()
            if nf_invalida:
                st.error("Por favor, insira apenas números na Nota Fiscal.")

            destinatario = st.text_input("Destinatário", key="destinatario")

            cliente_opcao = st.selectbox("Cliente", options=clientes + ["Outro ()"], index=None, key="cliente_opcao")
            cliente = st.text_input("Digite o nome do cliente", key="cliente_manual") if cliente_opcao == "Outro ()" else cliente_opcao

            if cliente_opcao and cliente_opcao in cliente_to_focal:
                st.session_state["focal_responsavel"] = cliente_to_focal[cliente_opcao]
            elif cliente_opcao:
                st.session_state["focal_responsavel"] = ""

            cidade_opcao = st.selectbox("Cidade", options=cidades + ["Outro (digitar manualmente)"], index=None, key="cidade_opcao")
            cidade = st.text_input("Digite o nome da cidade", key="cidade_manual") if cidade_opcao == "Outro (digitar manualmente)" else cidade_opcao

            imagem = st.file_uploader("📎 Anexar imagem (opcional)", type=["png", "jpg", "jpeg"], key="imagem_ocorrencia")


        with col2:
            motoristas_brutos = supabase.table("motoristas").select("motorista").limit(40000).execute()

            if motoristas_brutos.data:
                motoristas = [item["motorista"].strip() for item in motoristas_brutos.data if item.get("motorista")]
                motoristas = sorted(set(motoristas))
                motoristas = carregar_motoristas_supabase()
            else:
                motoristas = []
                st.warning("⚠️ Nenhum motorista encontrado no banco.")

            opcoes_motoristas = motoristas + ["Outro (digitar manualmente)"]
            motorista_opcao = st.selectbox("Motorista", options=opcoes_motoristas, index=None, key="motorista_opcao")
            motorista = st.text_input("Digite o nome do motorista", key="motorista_manual") if motorista_opcao == "Outro (digitar manualmente)" else motorista_opcao

            tipo = st.multiselect(
                "Tipo de Ocorrência",
                options=["Chegada no Local", "Pedido Bloqueado", "Aguardando Descarga", "Divergência"],
                key="tipo_ocorrencia"
            )

            obs = st.text_area("Observações", key="observacoes")
            responsavel = st.session_state.username
            st.text_input("Quem está abrindo o ticket", value=responsavel, disabled=True)

            # Buscar unidade do usuário logado
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", responsavel).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else "N/A"
            st.text_input("Unidade", value=unidade_usuario, disabled=True)




            # Inicializa somente se o campo ainda não tiver sido preenchido durante o uso do formulário
            # Inicialização segura
            if "data_abertura_manual" not in st.session_state:
                st.session_state["data_abertura_manual"] = obter_data_hora_atual_brasil().date()
            if "hora_abertura_manual" not in st.session_state:
                st.session_state["hora_abertura_manual"] = obter_data_hora_atual_brasil().time()

            col_data, col_hora = st.columns(2)
            with col_data:
                st.date_input(
                    "Data de Abertura",
                    key="data_abertura_manual",
                    format="DD/MM/YYYY"
                )
            with col_hora:
                st.time_input(
                    "Hora de Abertura",
                    key="hora_abertura_manual"
                )

            data_abertura_manual = st.session_state["data_abertura_manual"]
            hora_abertura_manual = st.session_state["hora_abertura_manual"]



        enviar = st.form_submit_button("Adicionar Ocorrência")

        if enviar:
            campos_obrigatorios = {
                "Nota Fiscal": nf,
                "Cliente": cliente,
                "Focal Responsável": st.session_state["focal_responsavel"],
                "Destinatário": destinatario,
                "Cidade": cidade,
                "Motorista": motorista,
                "Tipo de Ocorrência": tipo,
                "Responsável": responsavel
            }

            faltando = [campo for campo, valor in campos_obrigatorios.items() if not valor]

            if nf_invalida:
                st.error("Ocorrência não adicionada: Nota Fiscal deve conter apenas números.")
            elif faltando:
                st.error(f"❌ Preencha todos os campos obrigatórios: {', '.join(faltando)}")
            elif not cliente:
                st.error("❌ O campo 'Cliente' é obrigatório.")
            else:
                numero_ticket = obter_data_hora_atual_brasil().strftime("%Y%m%d%H%M%S%f")
                data_abertura_manual_str = data_abertura_manual.strftime("%Y-%m-%d")
                hora_abertura_manual_str = hora_abertura_manual.strftime("%H:%M:%S")

                st.write("🧪 Será salvo:", data_abertura_manual_str, hora_abertura_manual_str)  # depuração

                nova_ocorrencia = {
                    "id": str(uuid.uuid4()),
                    "numero_ticket": numero_ticket,
                    "nota_fiscal": nf,
                    "cliente": cliente,
                    "focal": st.session_state["focal_responsavel"],
                    "destinatario": destinatario,
                    "cidade": cidade,
                    "motorista": motorista,
                    "tipo_de_ocorrencia": ", ".join(tipo),
                    "observacoes": obs,
                    "responsavel": responsavel,
                    "data_abertura_manual": data_abertura_manual_str,
                    "hora_abertura_manual": hora_abertura_manual_str,
                    "ticket_unidade": unidade_usuario,
                    "complementar": "",
                    "permanencia": "",
                    "imagem_url": "",
                }

                if imagem:
                    try:
                        nome_arquivo = f"{nova_ocorrencia['id']}_{imagem.name}"
                        supabase.storage.from_("imagem-ticket").upload(
                            nome_arquivo,
                            imagem.read(),
                            file_options={"content-type": imagem.type}
                        )
                        url_imagem = supabase.storage.from_("imagem-ticket").get_public_url(nome_arquivo)
                        nova_ocorrencia["imagem_url"] = url_imagem
                    except Exception as e:
                        st.warning(f"⚠️ Falha ao enviar imagem: {e}")

                response = inserir_ocorrencia_supabase(nova_ocorrencia)

                if response and response.data:
                    nova_ocorrencia_local = nova_ocorrencia.copy()
                    nova_ocorrencia_local["Data/Hora Finalização"] = ""
                    st.session_state.ocorrencias_abertas.append(nova_ocorrencia_local)

                    st.session_state["focal_responsavel"] = ""

                    sucesso = st.empty()
                    sucesso.success("✅ Ocorrência aberta com sucesso!")
                    tm.sleep(1.5)
                    sucesso.empty()

                    # 🧹 Limpa todos os campos após sucesso
                    campos_para_limpar = [
                        "nf", "destinatario", "cliente_opcao", "cliente_manual",
                        "cidade_opcao", "cidade_manual", "motorista_opcao", "motorista_manual",
                        "tipo_ocorrencia", "observacoes", "imagem_ocorrencia",
                        "data_abertura_manual", "hora_abertura_manual"
                    ]
                    for campo in campos_para_limpar:
                        if campo in st.session_state:
                            del st.session_state[campo]

                    st.rerun()  # opcional: recarrega a página com campos limpos

# =========================
#    FUNÇÃO CLASSIFICAÇÃO
# =========================
def classificar_ocorrencia_por_tempo(data_str, hora_str):
    try:
        # Criar datetime a partir das strings de data e hora
        data_hora = criar_datetime_manual(data_str, hora_str)
        if not data_hora:
            return "Erro", "gray"
        
        # Calcula a diferença de tempo com a hora atual do Brasil
        agora = obter_data_hora_atual_brasil()
        diferenca = calcular_diferenca_tempo(data_hora, agora)
        
        if diferenca <= timedelta(minutes=15):
            return "Até 15min", "#2ecc71"  # Verde
        elif diferenca <= timedelta(minutes=30):
            return "15-30min", "#f39c12"  # Laranja
        elif diferenca <= timedelta(minutes=45):
            return "30-45min", "#e74c3c"  # Vermelho
        elif diferenca <= timedelta(minutes=90):
            return "45-90min", "#800000"  # Vermelho escuro
        else:
            return "Acima de 90min", "#400A40"  # Roxo
    except Exception:
        return "Erro", "gray"
    



#####################################
#FUNÇÃO LIMPAR CARACTERES NOME FOTO
#####################################

def limpar_nome_arquivo(nome_original):
    nome_limpo = re.sub(r'[^a-zA-Z0-9_.-]', '_', nome_original)
    return nome_limpo


# =========================
#    FUNÇÕES DE E-MAIL
# =========================

def carregar_dados_clientes_email():
    try:
        response = supabase.table("clientes").select("cliente, enviar_para_email, email_copia").execute()
        if response.data:
            return {
                item["cliente"]: {
                    "principal": item.get("enviar_para_email", ""),
                    "copia": item.get("email_copia", "")
                }
                for item in response.data if item.get("enviar_para_email")
            }
        else:
            return {}
    except Exception as e:
        st.error(f"Erro ao carregar e-mails dos clientes: {e}")
        return {}


def obter_ocorrencias_abertas_30min():
    """Obtém ocorrências abertas há mais de 30 minutos que ainda não receberam e-mail."""
    try:
        # Obter todas as ocorrências abertas que ainda não receberam e-mail
        response = supabase.table("ocorrencias").select("*").eq("status", "Aberta").eq("email_abertura_enviado", False).execute()
        ocorrencias = response.data
        
        # Filtrar ocorrências abertas há mais de 30 minutos
        ocorrencias_30min = []
        agora = obter_data_hora_atual_brasil()
        
        for ocorr in ocorrencias:
            # Verificar se tem data e hora manual
            if ocorr.get("data_abertura_manual") and ocorr.get("hora_abertura_manual"):
                try:
                    # Criar datetime a partir das strings de data e hora manual
                    data_hora_abertura = criar_datetime_manual(
                        ocorr["data_abertura_manual"], 
                        ocorr["hora_abertura_manual"]
                    )
                    
                    if data_hora_abertura:
                        # Verificar se passou mais de 30 minutos
                        diferenca = calcular_diferenca_tempo(data_hora_abertura, agora)
                        if diferenca > timedelta(minutes=30):
                            ocorrencias_30min.append(ocorr)
                except Exception as e:
                    st.error(f"Erro ao processar data/hora da ocorrência {ocorr.get('nota_fiscal', '-')}: {e}")
        
        return ocorrencias_30min
    except Exception as e:
        st.error(f"Erro ao obter ocorrências abertas: {e}")
        return []

def obter_ocorrencias_abertas_90min():
    """Obtém ocorrências abertas há mais de 1h30 e que ainda não receberam o e-mail de 90 minutos."""
    try:
        response = supabase.table("ocorrencias") \
            .select("*") \
            .eq("status", "Aberta") \
            .or_("email_90min_enviado.is.null,email_90min_enviado.eq.false") \
            .execute()

        agora = obter_data_hora_atual_brasil()
        ocorrencias_validas = []

        for ocorr in response.data or []:
            if ocorr.get("data_abertura_manual") and ocorr.get("hora_abertura_manual"):
                data_hora = criar_datetime_manual(
                    ocorr["data_abertura_manual"],
                    ocorr["hora_abertura_manual"]
                )
                if data_hora and calcular_diferenca_tempo(data_hora, agora) > timedelta(minutes=90):
                    ocorrencias_validas.append(ocorr)

        return ocorrencias_validas

    except Exception as e:
        st.error(f"Erro ao obter ocorrências de 90min: {e}")
        return []







def marcar_email_como_enviado(ocorrencia_id, tipo="abertura"):
    """Marca a ocorrência como tendo recebido e-mail."""
    try:
        campo = "email_abertura_enviado" if tipo == "abertura" else "email_finalizacao_enviado"
        response = supabase.table("ocorrencias").update({
            campo: True
        }).eq("id", ocorrencia_id).execute()
        
        return response.data is not None
    except Exception as e:
        st.error(f"Erro ao atualizar status de e-mail enviado: {e}")
        return False


def verificar_e_enviar_email_90min(ocorrencia):
    """Envia e-mail após 1h30 de espera no local, apenas uma vez"""
    try:
        if ocorrencia.get("email_90min_enviado", False):
            return False, "E-mail 1h30 já enviado."

        agora = obter_data_hora_atual_brasil()

        if ocorrencia.get("data_abertura_manual") and ocorrencia.get("hora_abertura_manual"):
            data_hora_abertura = criar_datetime_manual(
                ocorrencia["data_abertura_manual"],
                ocorrencia["hora_abertura_manual"]
            )

            diferenca = calcular_diferenca_tempo(data_hora_abertura, agora)

            if diferenca <= timedelta(minutes=90):
                return False, "Ainda não passou 1h30."

            cliente = ocorrencia.get('cliente')
            emails = carregar_dados_clientes_email()
            if cliente not in emails:
                return False, "Cliente sem e-mail."

            email_principal = emails[cliente]['principal']
            email_copia = emails[cliente]['copia']
            imagem_url = ocorrencia.get("imagem_url", "")
            data_hora_str = f"{ocorrencia['data_abertura_manual']} {ocorrencia['hora_abertura_manual']}"

            if imagem_url:
                imagem_html = f"""
                <tr>
                    <th>Imagem Ticket</th>
                    <td><a href="{imagem_url}" target="_blank">Baixar Imagem</a></td>
                </tr>
                """
            else:
                imagem_html = "<tr><th>Imagem Ticket</th><td>Não Anexada</td></tr>"

            # Corpo do e-mail com layout em tabela
            corpo_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .header {{ background-color: #800080; color: white; padding: 10px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>Veículo Aguardando - 1h30</h2>
                </div>
                <p>Prezado cliente <strong>{cliente}</strong>,</p>
                <p>Informamos que o veículo referente à NF abaixo está no local aguardando descarga há 1:30h.</p>
                <p>Não havendo a liberação de saída, passará a incidir <strong>taxa de carro dedicado</strong> conforme tabela comercial.</p>
                <p>No aguardo das suas instruções.</p>
                <table>
                    <tr><th>Ticket</th><td>{ocorrencia.get('numero_ticket', '-')}</td></tr>
                    <tr><th>Nota Fiscal</th><td>{ocorrencia.get('nota_fiscal', '-')}</td></tr>
                    <tr><th>Destinatário</th><td>{ocorrencia.get('destinatario', '-')}</td></tr>
                    <tr><th>Cidade</th><td>{ocorrencia.get('cidade', '-')}</td></tr>
                    <tr><th>Motorista</th><td>{ocorrencia.get('motorista', '-')}</td></tr>
                    <tr><th>Tipo</th><td>{ocorrencia.get('tipo_de_ocorrencia', '-')}</td></tr>
                    <tr><th>Data/Hora Abertura</th><td>{data_hora_str}</td></tr>
                    {imagem_html}
                </table>
                <p>Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
                <p style="color:gray; font-size:12px;">⚠️ Este é um e-mail automático. Por favor, não responda.</p>
            </body>
            </html>
            """

            assunto = f"⚠️ Veículo aguardando há 1h30 - NF {ocorrencia.get('nota_fiscal', '-')}"
            sucesso, mensagem = enviar_email(email_principal, email_copia, assunto, corpo_html, imagem_url)

            if sucesso:
                supabase.table("ocorrencias").update({
                    "email_90min_enviado": True
                }).eq("id", ocorrencia["id"]).execute()

                supabase.table("emails_enviados").insert({
                    "data_hora": data_hora_abertura.strftime("%d-%m-%Y %H:%M:%S"),
                    "tipo": "1h30",
                    "cliente": cliente,
                    "email": email_principal,
                    "ticket": ocorrencia.get('numero_ticket', '-'),
                    "nota_fiscal": ocorrencia.get('nota_fiscal', '-'),
                    "status": "Enviado"
                }).execute()

                return True, "E-mail 1h30 enviado com sucesso."
            else:
                return False, mensagem

        return False, "Data/hora de abertura ausente."
    except Exception as e:
        return False, f"Erro: {e}"




def enviar_email(destinatario, copia, assunto, corpo, imagem_url=None):
    """Envia e-mail com corpo HTML e anexo de imagem (se fornecido)."""
    try:
        # Criar mensagem
        msg = MIMEMultipart()
        msg['From'] = EMAIL_REMETENTE
        msg['To'] = destinatario

        # CC (cópia)
        todos_destinatarios = [destinatario]
        if copia:
            emails_cc = [email.strip() for email in copia.split(';') if email.strip()]
            if emails_cc:
                msg['Cc'] = ', '.join(emails_cc)
                todos_destinatarios += emails_cc

        msg['Subject'] = assunto
        msg['Reply-To'] = "naoresponda@clicklog.com.br"  # ou outro email do tipo noreply

        msg.attach(MIMEText(corpo, 'html'))

        # 📎 Anexar imagem (se fornecida e válida)
        if imagem_url:
            try:
                print("URL da imagem:", imagem_url)  # 👈 Diagnóstico
                response = requests.get(imagem_url)
                print("Status da requisição:", response.status_code)
                response = requests.get(imagem_url)
                if response.status_code == 200:
                    img_data = response.content
                    image_mime = MIMEImage(img_data)
                    image_mime.add_header('Content-Disposition', 'attachment', filename="imagem_ocorrencia.jpg")
                    msg.attach(image_mime)
            except Exception as e:
                print(f"Erro ao anexar imagem: {e}")

        # Enviar via SMTP
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        server.sendmail(EMAIL_REMETENTE, todos_destinatarios, msg.as_string())
        server.quit()

        return True, "E-mail enviado com sucesso"
    except socket.timeout:
        return False, "Timeout ao conectar ao servidor SMTP. Possível bloqueio de firewall."
    except smtplib.SMTPAuthenticationError:
        return False, "Falha na autenticação. Verifique usuário e senha."
    except Exception as e:
        return False, f"Erro ao enviar e-mail: {e}"




def verificar_e_enviar_email_abertura(ocorrencia):
    """Verifica se a ocorrência precisa de e-mail e envia se necessário."""
    try:
        agora = obter_data_hora_atual_brasil()

        if ocorrencia.get("data_abertura_manual") and ocorrencia.get("hora_abertura_manual"):
            # Criar datetime
            data_hora_abertura = criar_datetime_manual(
                ocorrencia["data_abertura_manual"], 
                ocorrencia["hora_abertura_manual"]
            )

            if not data_hora_abertura:
                return False, "Erro ao criar datetime a partir de data/hora manual"

            # Verificar se passou 30 minutos
            diferenca = calcular_diferenca_tempo(data_hora_abertura, agora)
            if diferenca <= timedelta(minutes=30):
                return False, f"Ocorrência aberta há menos de 30 minutos (diferença: {diferenca})"

            # Obter e-mails do cliente
            clientes_emails = carregar_dados_clientes_email()
            cliente = ocorrencia.get('cliente')

            if cliente not in clientes_emails:
                return False, "Cliente não possui e-mail cadastrado"

            email_info = clientes_emails[cliente]
            email_principal = email_info['principal']
            email_copia = email_info['copia']

            # Obter imagem
            imagem_url = ocorrencia.get("imagem_url", "")
            if imagem_url:
                imagem_html = f"""
                <tr>
                    <th>Imagem Ticket</th>
                    <td><a href="{imagem_url}" target="_blank">Baixar Imagem</a></td>
                </tr>
                """
            else:
                imagem_html = """
                <tr>
                    <th>Imagem Ticket</th>
                    <td>Não Anexada</td>
                </tr>
                """

            # Corpo do e-mail
            data_hora_str = f"{ocorrencia['data_abertura_manual']} {ocorrencia['hora_abertura_manual']}"

            corpo_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .header {{ background-color: #f08104; color: white; padding: 10px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>Notificação de Ocorrência Aberta</h2>
                </div>
                <p>Prezado cliente <strong>{cliente}</strong>,</p>
                <p>O veículo com a entrega abaixo identificada encontra-se no ponto de descarga a 30min.</p>
                <p>Após 45 min de tempo de permanência haverá aplicação da TDE conforme especificado</p>
                <p>em tabela. Pedimos sua interferência no processo de descarga para evitar custos extras.</p>
                <table>
                    <tr><th>Ticket</th><td>{ocorrencia.get('numero_ticket', '-')}</td></tr>
                    <tr><th>Nota Fiscal</th><td>{ocorrencia.get('nota_fiscal', '-')}</td></tr>
                    <tr><th>Destinatário</th><td>{ocorrencia.get('destinatario', '-')}</td></tr>
                    <tr><th>Cidade</th><td>{ocorrencia.get('cidade', '-')}</td></tr>
                    <tr><th>Motorista</th><td>{ocorrencia.get('motorista', '-')}</td></tr>
                    <tr><th>Tipo</th><td>{ocorrencia.get('tipo_de_ocorrencia', '-')}</td></tr>
                    <tr><th>Data/Hora Abertura</th><td>{data_hora_str}</td></tr>
                    {imagem_html}
                </table>
                <p>Por favor, entre em contato conosco para mais informações.</p>
                <p>Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
                <p style="color:gray; font-size:12px;">
                ⚠️ Este é um e-mail automático. Por favor, não responda.
                </p>
            </body>
            </html>
            """

            # Enviar e-mail com imagem em anexo
            assunto = f"Notificação: Ocorrência Aberta - {cliente} - NF {ocorrencia.get('nota_fiscal', '-')}"
            sucesso, mensagem = enviar_email(
                destinatario=email_principal,
                copia=email_copia,
                assunto=assunto,
                corpo=corpo_html,
                imagem_url=imagem_url
            )

            if sucesso:
                marcar_email_como_enviado(ocorrencia["id"], "abertura")

                supabase.table("emails_enviados").insert({
                    "data": obter_data_hora_atual_brasil().strftime("%d-%m-%Y %H:%M:%S"),
                    "tipo": "Abertura",
                    "cliente": cliente,
                    "email": email_principal,
                    "ticket": ocorrencia.get('numero_ticket', '-'),
                    "nota_fiscal": ocorrencia.get('nota_fiscal', '-'),
                    "status": "Enviado"
                }).execute()

                return True, "E-mail enviado com sucesso"
            else:
                return False, mensagem

        else:
            return False, "Dados de data/hora de abertura ausentes"
    except Exception as e:
        return False, f"Erro ao verificar e enviar e-mail: {e}"


def enviar_email_finalizacao(ocorrencia):
    """Envia e-mail de finalização para o cliente, incluindo imagem se houver."""
    try:
        # Carregar dados do cliente
        clientes_emails = carregar_dados_clientes_email()
        cliente = ocorrencia.get('cliente')
        
        if cliente in clientes_emails:
            email_info = clientes_emails[cliente]
            email_principal = email_info['principal']
            email_copia = email_info['copia']
            
            # Obter dados de abertura e finalização
            data_abertura = f"{ocorrencia.get('data_abertura_manual', '-')} {ocorrencia.get('hora_abertura_manual', '-')}"
            data_finalizacao = f"{ocorrencia.get('data_finalizacao_manual', '-')} {ocorrencia.get('hora_finalizacao_manual', '-')}"
            
            # Obter imagem (se houver)
            imagem_url = ocorrencia.get("imagem_finalizacao_url", "")
            if imagem_url:
                imagem_html = f"""
                <tr>
                    <th>Imagem Ticket</th>
                    <td><a href="{imagem_url}" target="_blank">Baixar Imagem</a></td>
                </tr>
                """
            else:
                imagem_html = "<tr><th>Imagem Ticket</th><td>Não Anexada</td></tr>"
            
            # Criar corpo do e-mail
            corpo_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 10px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>Notificação de Ocorrência Finalizada</h2>
                </div>
                <p>Prezado cliente <strong>{cliente}</strong>,</p>
                <p>Informamos que a seguinte ocorrência foi finalizada:</p>
                <table>
                    <tr><th>Ticket</th><td>{ocorrencia.get('numero_ticket', '-')}</td></tr>
                    <tr><th>Nota Fiscal</th><td>{ocorrencia.get('nota_fiscal', '-')}</td></tr>
                    <tr><th>Destinatário</th><td>{ocorrencia.get('destinatario', '-')}</td></tr>
                    <tr><th>Cidade</th><td>{ocorrencia.get('cidade', '-')}</td></tr>
                    <tr><th>Motorista</th><td>{ocorrencia.get('motorista', '-')}</td></tr>
                    <tr><th>Tipo</th><td>{ocorrencia.get('tipo_de_ocorrencia', '-')}</td></tr>
                    <tr><th>Data/Hora Abertura</th><td>{data_abertura}</td></tr>
                    <tr><th>Data/Hora Finalização</th><td>{data_finalizacao}</td></tr>
                    <tr><th>Permanência</th><td>{ocorrencia.get('permanencia_manual', '-')}</td></tr>
                    {imagem_html}
                </table>
                <p><strong>Complemento:</strong> {ocorrencia.get('complementar', 'Sem complemento.')}</p>
                <p>Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
            </body>
            </html>
            """

            # Enviar e-mail (com imagem em anexo caso exista)
            assunto = f"Notificação: Ocorrência Finalizada - {cliente} - NF {ocorrencia.get('nota_fiscal', '-')}"
            sucesso, mensagem = enviar_email(email_principal, email_copia, assunto, corpo_html)
            
            if sucesso:
                marcar_email_como_enviado(ocorrencia["id"], "finalizacao")

                # Registrar no Supabase
                supabase.table("emails_enviados").insert({
                    "data_hora": obter_data_hora_atual_brasil().isoformat(),
                    "tipo": "Finalização",
                    "cliente": cliente,
                    "email": email_principal,
                    "ticket": ocorrencia.get('numero_ticket', '-'),
                    "nota_fiscal": ocorrencia.get('nota_fiscal', '-'),
                    "status": "Enviado"
                }).execute()

                return True, "E-mail de finalização enviado com sucesso"
            else:
                return False, mensagem
        else:
            return False, "Cliente não possui e-mail cadastrado"
    except Exception as e:
        return False, f"Erro ao enviar e-mail de finalização: {e}"


def notificar_ocorrencias_abertas():
    """Notifica clientes sobre ocorrências abertas há mais de 30 minutos e também aquelas com mais de 1h30."""
    resultados = []

    # 🔸 Etapa 1: e-mails de abertura (30min)
    ocorrencias_30min = obter_ocorrencias_abertas_30min()
    for ocorr in ocorrencias_30min:
        sucesso, mensagem = verificar_e_enviar_email_abertura(ocorr)
        resultados.append({
            "cliente": ocorr.get('cliente'),
            "ticket": ocorr.get('numero_ticket', '-'),
            "nota_fiscal": ocorr.get('nota_fiscal', '-'),
            "status": "sucesso" if sucesso else "erro",
            "mensagem": mensagem
        })

    # 🔹 Etapa 2: e-mails de 1h30
    ocorrencias_90min = obter_ocorrencias_abertas_90min()
    for ocorr in ocorrencias_90min:
        sucesso, mensagem = verificar_e_enviar_email_90min(ocorr)
        resultados.append({
            "cliente": ocorr.get('cliente'),
            "ticket": ocorr.get('numero_ticket', '-'),
            "nota_fiscal": ocorr.get('nota_fiscal', '-'),
            "status": "sucesso" if sucesso else "erro",
            "mensagem": f"E-mail 1h30: {mensagem}"
        })

    return resultados


def obter_ocorrencias_90min():
    """Obtém todas ocorrências abertas que ainda não receberam o e-mail de 90min e já passaram de 1h30."""
    try:
        response = supabase.table("ocorrencias") \
            .select("*") \
            .eq("status", "Aberta") \
            .eq("email_90min_enviado", False) \
            .execute()
        
        agora = obter_data_hora_atual_brasil()
        ocorrencias_validas = []
        
        for ocorr in response.data:
            if ocorr.get("data_abertura_manual") and ocorr.get("hora_abertura_manual"):
                dt = criar_datetime_manual(ocorr["data_abertura_manual"], ocorr["hora_abertura_manual"])
                if dt and calcular_diferenca_tempo(dt, agora) > timedelta(minutes=90):
                    ocorrencias_validas.append(ocorr)
        
        return ocorrencias_validas
    except Exception as e:
        st.error(f"Erro ao obter ocorrências de 90min: {e}")
        return []



def testar_conexao_smtp():
    """Testa apenas a conexão com o servidor SMTP."""
    try:
        # Tentar conectar ao servidor
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        
        # Tentar iniciar TLS
        server.starttls()
        
        # Tentar autenticar
        server.login(EMAIL_REMETENTE, EMAIL_SENHA)
        
        # Fechar conexão
        server.quit()
        return True, "Conexão SMTP testada com sucesso!"
    except socket.timeout:
        return False, "Timeout ao conectar ao servidor SMTP. Possível bloqueio de firewall."
    except smtplib.SMTPAuthenticationError:
        return False, "Falha na autenticação. Verifique usuário e senha."
    except smtplib.SMTPException as e:
        return False, f"Erro SMTP: {e}"
    except Exception as e:
        return False, f"Erro desconhecido: {e}"
    

# Função para carregar ocorrências abertas
def carregar_ocorrencias_abertas():
    try:
        if st.session_state.is_admin:
            response = supabase.table("ocorrencias").select("*").eq("status", "Aberta").order("data_hora_abertura", desc=True).execute()
        else:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            response = supabase.table("ocorrencias").select("*").eq("status", "Aberta").eq("ticket_unidade", unidade_usuario).order("data_hora_abertura", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências abertas: {e}")
        return []


# Função para carregar ocorrências por focal
def carregar_ocorrencias_por_focal(focal=None):
    try:
        if st.session_state.is_admin:
            response = supabase.table("ocorrencias").select("*").eq("status", "Aberta").eq("focal", focal).order("data_hora_abertura", desc=True).execute()
        else:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            response = supabase.table("ocorrencias").select("*").eq("status", "Aberta").eq("focal", focal).eq("ticket_unidade", unidade_usuario).order("data_hora_abertura", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências por focal: {e}")
        return []

    

# Função para obter lista de focais com contagem de tickets
def obter_focais_com_contagem():
    try:
        ocorrencias = carregar_ocorrencias_abertas()
        
        # Agrupar por focal e contar
        focais_contagem = {}
        for ocorr in ocorrencias:
            focal = ocorr.get('focal')
            if focal:
                if focal not in focais_contagem:
                    focais_contagem[focal] = 0
                focais_contagem[focal] += 1
        
        # Ordenar por contagem (decrescente)
        focais_ordenados = sorted(focais_contagem.items(), key=lambda x: x[1], reverse=True)
        
        return focais_ordenados
    except Exception as e:
        st.error(f"Erro ao obter focais com contagem: {e}")
        return []

# Função para finalizar ocorrência com suporte a imagem na finalização
def finalizar_ocorrencia(ocorr, complemento, data_finalizacao_manual, hora_finalizacao_manual, imagem_url_finalizacao="", observacao_final=""):
    try:
        data_abertura_manual = ocorr.get("data_abertura_manual")
        hora_abertura_manual = ocorr.get("hora_abertura_manual")
        
        if not data_abertura_manual or not hora_abertura_manual:
            return False, "Data/hora de abertura manual ausente. Não é possível calcular a permanência."
        
        try:
            # 🔧 Etapa 1: combinar data e hora inseridas pelo usuário
            data_finalizacao_obj = data_finalizacao_manual
            data_hora_finalizacao = datetime.combine(data_finalizacao_obj, hora_finalizacao_manual)

            # 🧪 Diagnóstico: antes do fuso
            st.write("💡 Data final manual (antes do fuso):", data_hora_finalizacao.strftime("%Y-%m-%d %H:%M:%S"))

            # 🔧 Etapa 2: garantir que o fuso horário brasileiro seja aplicado corretamente
            if data_hora_finalizacao.tzinfo is None:
                data_hora_finalizacao = FUSO_HORARIO_BRASIL.localize(data_hora_finalizacao)
            else:
                data_hora_finalizacao = data_hora_finalizacao.astimezone(FUSO_HORARIO_BRASIL)

            # 🧪 Diagnóstico: depois do fuso
            st.write("🕓 Data final (com fuso):", data_hora_finalizacao.strftime("%Y-%m-%d %H:%M:%S %Z"))
            
            # 🔧 Etapa 3: criar datetime de abertura
            data_hora_abertura = criar_datetime_manual(data_abertura_manual, hora_abertura_manual)
            if not data_hora_abertura:
                return False, "Erro ao criar datetime a partir de data/hora de abertura manual."
            
            # 🔒 Verificação de consistência
            if data_hora_finalizacao < data_hora_abertura:
                return False, "Data/hora de finalização não pode ser menor que a data/hora de abertura."
            
            # 🔢 Calcular permanência
            delta = calcular_diferenca_tempo(data_hora_abertura, data_hora_finalizacao)
            total_segundos = int(delta.total_seconds())
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            segundos = total_segundos % 60
            permanencia_manual = f"{horas:02d}:{minutos:02d}:{segundos:02d}"

            # 🔄 Preparar dados para o banco
            data_finalizacao_banco = data_hora_finalizacao.strftime("%Y-%m-%d")
            hora_finalizacao_banco = data_hora_finalizacao.strftime("%H:%M:%S")

            # 💾 Atualizar ocorrência no Supabase
            response = supabase.table("ocorrencias").update({
                "data_hora_finalizacao": data_hora_finalizacao.strftime("%Y-%m-%d %H:%M:%S"),
                "finalizado_por": st.session_state.username,
                "complementar": complemento,
                "status": "Finalizada",
                "permanencia_manual": permanencia_manual,
                "data_finalizacao_manual": data_finalizacao_banco,
                "hora_finalizacao_manual": hora_finalizacao_banco,
                "email_finalizacao_enviado": False,
                "observacao_final": observacao_final,
                "imagem_finalizacao_url": imagem_url_finalizacao
            }).eq("id", ocorr["id"]).execute()
            
            if response and response.data:
                # 📧 Enviar e-mail de finalização
                ocorr_atualizada = response.data[0]
                enviar_email_finalizacao(ocorr_atualizada)
                
                return True, "Ocorrência finalizada com sucesso!"
            else:
                return False, "Erro ao salvar a finalização no banco de dados."

        except ValueError:
            return False, "Formato inválido para data/hora de finalização. Use DD-MM-AAAA para a data e HH:MM para a hora."
        except Exception as e:
            return False, f"Erro ao calcular ou salvar permanência manual: {e}"

    except Exception as e:
        return False, f"Erro ao finalizar ocorrência: {e}"


# =========================
#     ABA 2 - EM ABERTO (COM FILTRO POR FOCAL)
# =========================
if st.session_state.aba_ativa == "aba2":
    col_titulo, col_botao = st.columns([5, 1])
    with col_titulo:
        st.header("Ocorrências em Aberto")
    with col_botao:
        atualizar_abertas = st.button("🔄 Atualizar", key="btn_atualizar_abertas", use_container_width=True)

    if atualizar_abertas or "ocorrencias_abertas" not in st.session_state:
        st.cache_data.clear()
        st.session_state.ocorrencias_abertas = carregar_ocorrencias_abertas()

    ocorrencias_abertas = st.session_state.get("ocorrencias_abertas", [])

    # ⏱️ Auto refresh a cada 7 minutos (420.000 ms)
    st_autorefresh(interval=7 * 60 * 1000, key="auto_refresh_abertas")

    # 🚫 Garantir que não envie múltiplos e-mails no mesmo ciclo
    
        # Executa a verificação de ocorrências a cada ciclo
    resultados_emails = notificar_ocorrencias_abertas()

    for resultado in resultados_emails:
        if resultado["status"] == "sucesso":
            st.toast(f"📧 {resultado['mensagem']}")
        else:
            st.warning(f"⚠️ Erro para {resultado.get('cliente', 'cliente desconhecido')}: {resultado['mensagem']}")




    # Filtro por Focal
    lista_focais = sorted(set(
        (ocorr.get('focal') or 'Sem Focal').strip()
        for ocorr in ocorrencias_abertas
    ))

    focal_selecionado = st.selectbox(
        "🔎 Filtrar por Focal:",
        options=["Todos"] + lista_focais,
        index=0
    )

    if focal_selecionado != "Todos":
        ocorrencias_filtradas = [
            ocorr for ocorr in ocorrencias_abertas
            if (ocorr.get('focal') or 'Sem Focal').strip() == focal_selecionado
        ]
    else:
        ocorrencias_filtradas = ocorrencias_abertas

    # ✅ EXIBIÇÃO DOS TICKETS (corretamente posicionado fora do filtro)
    if not ocorrencias_filtradas:
        st.info("ℹ️ Nenhuma ocorrência aberta no momento para esse filtro.")
    else:
        num_colunas = 4
        colunas = st.columns(num_colunas)

        for idx, ocorr in enumerate(ocorrencias_filtradas):
            status = "Data manual ausente"
            cor = "gray"
            abertura_manual_formatada = "Não informada"
            data_abertura_manual = ocorr.get("data_abertura_manual")
            hora_abertura_manual = ocorr.get("hora_abertura_manual")

            if data_abertura_manual and hora_abertura_manual:
                try:
                    dt_manual = criar_datetime_manual(data_abertura_manual, hora_abertura_manual)
                    if dt_manual:
                        abertura_manual_formatada = dt_manual.strftime("%d-%m-%Y %H:%M:%S")
                        status, cor = classificar_ocorrencia_por_tempo(data_abertura_manual, hora_abertura_manual)
                    else:
                        status = "Erro"
                except Exception as e:
                    st.error(f"Erro na data/hora manual da NF {ocorr.get('nota_fiscal', '-')}: {e}")
                    status = "Erro"

            with colunas[idx % num_colunas]:
                safe_idx = f"{idx}_{ocorr.get('nota_fiscal', '')}"
                email_enviado = ocorr.get('email_abertura_enviado', False)
                imagem_abertura_url = ocorr.get('imagem_url', '')
                imagem_finalizacao_url = ocorr.get('imagem_finalizacao_url', '')

                st.markdown(
                    f"""
                    <div style='background-color:{cor};padding:10px;border-radius:10px;color:white;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.3);margin-bottom:5px;min-height:250px;font-size:15px;'>
                    <strong>Ticket #:</strong> {str(ocorr.get('numero_ticket', 'N/A'))[-5:]}<br>
                    {f'📸 Abertura: <a href="{imagem_abertura_url}" target="_blank" style="text-decoration:underline;color:white;">Baixar</a><br>' if imagem_abertura_url else ''}
                    <strong>Status:</strong> {status}<br>
                    {'📧 E-mail enviado<br>' if email_enviado else ''}
                    <strong>NF:</strong> {ocorr.get('nota_fiscal', '-')}<br>
                    <strong>Cliente:</strong> {ocorr.get('cliente', '-')}<br>
                    <strong>Destinatário:</strong> {ocorr.get('destinatario', '-')}<br>
                    <strong>Focal:</strong> {ocorr.get('focal', '-')}<br>
                    <strong>Cidade:</strong> {ocorr.get('cidade', '-')}<br>
                    <strong>Motorista:</strong> {ocorr.get('motorista', '-')}<br>
                    <strong>Tipo:</strong> {ocorr.get('tipo_de_ocorrencia', '-')}<br>
                    <strong>Aberto por:</strong> {ocorr.get('responsavel', '-')}<br>
                    <strong>Data Abertura:</strong> {abertura_manual_formatada.split(" ")[0] if abertura_manual_formatada != "Não informada" else 'Não informada'}<br>
                    <strong>Hora Abertura:</strong> {hora_abertura_manual or 'Não informada'}<br>
                    <strong>Observações:</strong> {ocorr.get('observacoes', '')}<br>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # 🔥 Botão ou formulário de finalização
                if st.session_state.get("ticket_em_finalizacao") == safe_idx:
                    with st.form(f"form_{safe_idx}"):
                        chave_data = f"data_final_{safe_idx}"
                        chave_hora = f"hora_final_{safe_idx}"

                        if chave_data not in st.session_state or not isinstance(st.session_state[chave_data], date):
                            st.session_state[chave_data] = obter_data_hora_atual_brasil().date()

                        if chave_hora not in st.session_state or not isinstance(st.session_state[chave_hora], time):
                            st.session_state[chave_hora] = obter_data_hora_atual_brasil().time()

                        col_data, col_hora = st.columns(2)
                        with col_data:
                            st.date_input("Data Finalização", key=chave_data, format="DD/MM/YYYY")
                        with col_hora:
                            st.time_input("Hora Finalização", key=chave_hora)

                        data_finalizacao_manual = st.session_state[chave_data]
                        hora_finalizacao_manual = st.session_state[chave_hora]

                        complemento = st.text_area("Complementar não Fiscal", key=f"complemento_final_{safe_idx}")
                        observacao_final = st.text_area("Observação", key=f"observacao_final_{safe_idx}")

                        imagem_finalizacao = st.file_uploader(
                            "📎 Anexar imagem da finalização (opcional)",
                            type=["png", "jpg", "jpeg"],
                            key=f"imagem_finalizacao_{safe_idx}"
                        )

                        if st.form_submit_button("Finalizar"):
                            if not complemento.strip():
                                st.warning("❌ O campo 'Complementar' é obrigatório.")
                            else:
                                st.toast("📤 Enviando e-mail de finalização...")
                                st.toast("✅ Ticket sendo finalizado...")

                                imagem_url_finalizacao = ""
                                if imagem_finalizacao:
                                    try:
                                        nome_arquivo = f"{ocorr['id']}_finalizacao_{limpar_nome_arquivo(imagem_finalizacao.name)}"
                                        supabase.storage.from_("imagens-finalizacao").upload(
                                            nome_arquivo,
                                            imagem_finalizacao.read(),
                                            file_options={"content-type": imagem_finalizacao.type}
                                        )
                                        imagem_url_finalizacao = supabase.storage.from_("imagens-finalizacao").get_public_url(nome_arquivo)
                                    except Exception as e:
                                        st.warning(f"⚠️ Falha ao enviar imagem: {e}")

                                st.write("🧪 Será salvo:", data_finalizacao_manual.strftime("%d-%m-%Y"), hora_finalizacao_manual.strftime("%H:%M:%S"))

                                sucesso, mensagem = finalizar_ocorrencia(
                                    ocorr,
                                    complemento,
                                    data_finalizacao_manual,
                                    hora_finalizacao_manual,
                                    imagem_url_finalizacao,
                                    observacao_final
                                )

                                if sucesso:
                                    st.success("✅ Ticket finalizado com sucesso!")
                                    st.session_state.ticket_em_finalizacao = None
                                    tm.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.warning(f"⚠️ A finalização falhou: {mensagem}")
                else:
                    if st.button("Finalizar", key=f"btn_finalizar_{safe_idx}"):
                        st.session_state.ticket_em_finalizacao = safe_idx
                        st.rerun()




# =============================== 
#    FUNÇÃO CARREGAR FINALIZADAS 
# ===============================        
def carregar_ocorrencias_finalizadas():
    try:
        if st.session_state.is_admin:
            response = supabase.table("ocorrencias").select("*").eq("status", "Finalizada").order("data_hora_finalizacao", desc=True).execute()
        else:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            response = supabase.table("ocorrencias").select("*").eq("status", "Finalizada").eq("ticket_unidade", unidade_usuario).order("data_hora_finalizacao", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências finalizadas: {e}")
        return []
    
# =============================== 
#    ABA3 FINALIZADAS 
# ===============================   
def seguro(valor, padrao="-"):
    return html.escape(str(valor if valor is not None else padrao))

def auto_sanitizar_ocorrencia(ocorr):
    campos_texto = [
        'numero_ticket', 'nota_fiscal', 'cliente', 'destinatario', 'focal', 'cidade',
        'motorista', 'tipo_de_ocorrencia', 'responsavel', 'finalizado_por',
        'permanencia_manual', 'complementar', 'Status', 'Cor'
    ]
    for campo in campos_texto:
        if campo not in ocorr or ocorr[campo] is None:
            ocorr[campo] = "-"
    return ocorr

if st.session_state.aba_ativa == "aba3":
    col_titulo, col_botao = st.columns([6, 1])
    with col_titulo:
        st.header("Ocorrências Finalizadas")
    with col_botao:
        atualizar = st.button("🔄 Atualizar", key="btn_atualizar_finalizadas", use_container_width=True)

    if atualizar:
        st.cache_data.clear()
        try:
            st.session_state.ocorrencias_finalizadas = carregar_ocorrencias_finalizadas()
        except Exception as e:
            st.error(f"Erro ao carregar ocorrências finalizadas: {e}")
            st.stop()


    ocorrencias_finalizadas = st.session_state.get("ocorrencias_finalizadas", [])

    if not ocorrencias_finalizadas:
        st.info("ℹ️ Nenhuma ocorrência finalizada.")
    else:
        col1, col2 = st.columns([1, 2])
        with col1:
            filtro_nf = st.text_input("🔎 Pesquisar por NF:", "", max_chars=10)
        with col2:
            if st.button("📤 Exportar Excel"):
                try:
                    df = pd.DataFrame(ocorrencias_finalizadas)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Finalizadas')
                    st.download_button(
                        label="⬇️ Baixar Relatório Excel",
                        data=output.getvalue(),
                        file_name="ocorrencias_finalizadas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                except Exception as e:
                    st.error(f"Erro ao exportar para Excel: {e}")

        if filtro_nf:
            ocorrencias_filtradas = [
                ocorr for ocorr in ocorrencias_finalizadas
                if filtro_nf.lower() in str(ocorr.get("nota_fiscal", "")).lower()
            ]
        else:
            ocorrencias_filtradas = ocorrencias_finalizadas

        erros_detectados = []
        num_colunas = 4
        for i in range(0, len(ocorrencias_filtradas), num_colunas):
            linha = ocorrencias_filtradas[i:i+num_colunas]
            colunas = st.columns(num_colunas)

            for idx, ocorr in enumerate(linha):
                ocorr = auto_sanitizar_ocorrencia(ocorr)
                
                data_abertura_manual = hora_abertura_manual = "-"
                try:
                    if ocorr.get("data_abertura_manual") and ocorr.get("hora_abertura_manual"):
                        abertura_dt = criar_datetime_manual(
                            ocorr["data_abertura_manual"], ocorr["hora_abertura_manual"]
                        )
                        if abertura_dt:
                            data_abertura_manual = abertura_dt.strftime("%d-%m-%Y")
                            hora_abertura_manual = abertura_dt.strftime("%H:%M:%S")
                except Exception as e:
                    st.warning(f"Erro ao converter data/hora de abertura: {e}")

                data_finalizacao_manual = hora_finalizacao_manual = "-"
                try:
                    if ocorr.get("data_finalizacao_manual") and ocorr.get("hora_finalizacao_manual"):
                        finalizacao_dt = criar_datetime_manual(
                            ocorr["data_finalizacao_manual"], ocorr["hora_finalizacao_manual"]
                        )
                        if finalizacao_dt:
                            data_finalizacao_manual = finalizacao_dt.strftime("%d-%m-%Y")
                            hora_finalizacao_manual = finalizacao_dt.strftime("%H:%M:%S")
                except Exception as e:
                    st.warning(f"Erro ao converter data/hora de finalização: {e}")

                with colunas[idx]:
                    try:
                        email_abertura = "📧 E-mail abertura enviado" if ocorr.get('email_abertura_enviado', False) else ""
                        email_finalizacao = "📧 E-mail finalização enviado" if ocorr.get('email_finalizacao_enviado', False) else ""

                        imagem_abertura_url = html.escape(str(ocorr.get("imagem_url", "")), quote=True)
                        imagem_finalizacao_url = html.escape(str(ocorr.get("imagem_finalizacao_url", "")), quote=True)

                        html_card = f"""
                        <div style='background-color:{seguro(ocorr['Cor'])};padding:10px;border-radius:10px;color:white;
                        box-shadow: 0 4px 10px rgba(0,0,0,0.3);margin-bottom:5px;min-height:250px;font-size:15px;'>
                        <strong>Ticket #:</strong> {seguro(ocorr['numero_ticket'])}<br>
                        {'📸 Abertura: <a href="' + imagem_abertura_url + '" target="_blank" style="text-decoration:underline;color:white;">Baixar</a><br>' if imagem_abertura_url else ''}
                        {'📸 Finalização: <a href="' + imagem_finalizacao_url + '" target="_blank" style="text-decoration:underline;color:white;">Baixar</a><br>' if imagem_finalizacao_url else ''}
                        
                        {email_abertura}<br>
                        {email_finalizacao}<br>
                        <strong>NF:</strong> {seguro(ocorr['nota_fiscal'])}<br>
                        <strong>Cliente:</strong> {seguro(ocorr['cliente'])}<br>
                        <strong>Destinatário:</strong> {seguro(ocorr['destinatario'])}<br>
                        <strong>Focal:</strong> {seguro(ocorr['focal'])}<br>
                        <strong>Cidade:</strong> {seguro(ocorr['cidade'])}<br>
                        <strong>Motorista:</strong> {seguro(ocorr['motorista'])}<br>
                        <strong>Tipo:</strong> {seguro(ocorr['tipo_de_ocorrencia'])}<br>
                        <strong>Aberto por:</strong> {seguro(ocorr['responsavel'])}<br>
                        <strong>Finalizado por:</strong> {seguro(ocorr['finalizado_por'])}<br>
                        <strong>Data Abertura:</strong> {data_abertura_manual}<br>
                        <strong>Hora Abertura:</strong> {hora_abertura_manual}<br>
                        <strong>Data Finalização:</strong> {data_finalizacao_manual}<br>
                        <strong>Hora Finalização:</strong> {hora_finalizacao_manual}<br>
                        <strong>Permanência:</strong> {seguro(ocorr['permanencia_manual'])}<br>
                        <strong>Complementar:</strong> {seguro(ocorr['complementar'], '')}<br>
                        </div>
                        """
                        st.markdown(html_card, unsafe_allow_html=True)

                    except Exception as e:
                        st.warning(f"⚠️ Erro ao montar card de ocorrência: Ticket {ocorr.get('numero_ticket')} — {e}")
                        with st.expander(f"🔍 Ver dados da ocorrência com erro (Ticket {ocorr.get('numero_ticket')})"):
                            st.json(ocorr)
                        erros_detectados.append({
                            "ticket": ocorr.get("numero_ticket"),
                            "nf": ocorr.get("nota_fiscal"),
                            "erro": str(e),
                            "dados": ocorr
                        })




# =========================
#     ABA 4 - CONFIGURAÇÕES
# =========================
if st.session_state.aba_ativa == "aba4":
    st.header("Configurações")

    # Seção de troca de senha
    st.subheader("🔑 Alterar Senha")

    
    with st.form("form_alterar_senha"):
        senha_atual = st.text_input("Senha Atual", type="password")
        nova_senha = st.text_input("Nova Senha", type="password")
        confirmar_senha = st.text_input("Confirmar Nova Senha", type="password")
        
        alterar_senha = st.form_submit_button("Alterar Senha")
        
        if alterar_senha:
            if not senha_atual or not nova_senha or not confirmar_senha:
                st.error("❌ Todos os campos são obrigatórios.")
            elif nova_senha != confirmar_senha:
                st.error("❌ As senhas não coincidem.")
            else:
                try:
                    # Verificar senha atual
                    usuario = st.session_state.username
                    response = supabase.table("usuarios").select("*").eq("nome_usuario", usuario).execute()
                    
                    if response.data:
                        usuario_data = response.data[0]
                        if verificar_senha(senha_atual, usuario_data["senha_hash"]):
                            # Atualizar senha
                            nova_senha_hash = hash_senha(nova_senha)
                            update_response = supabase.table("usuarios").update({
                                "senha_hash": nova_senha_hash
                            }).eq("nome_usuario", usuario).execute()
                            
                            if update_response.data:
                                st.success("✅ Senha alterada com sucesso!")
                            else:
                                st.error("❌ Erro ao atualizar senha.")
                        else:
                            st.error("❌ Senha atual incorreta.")
                    else:
                        st.error("❌ Usuário não encontrado.")
                except Exception as e:
                    st.error(f"❌ Erro ao alterar senha: {e}")
    
    # Seção de administração de usuários (apenas para admin)
    if st.session_state.is_admin:
        st.subheader("Administração de Usuários")
        
        # Tabs para diferentes operações
        admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Listar Usuários", "Adicionar Usuário", "Editar/Excluir Usuário"])
        
        with admin_tab1:
            try:
                response = supabase.table("usuarios").select("*").execute()
                if response.data:
                    usuarios = response.data
                    
                    # Criar DataFrame para exibição
                    df_usuarios = pd.DataFrame([
                        {
                            "Nome de Usuário": u["nome_usuario"],
                            "Admin": "Sim" if u.get("is_admin", False) else "Não",
                            "Unidade": u.get("unidade", "Não definido"),
                            "Último Login": u.get("ultimo_login", "-")
                        }
                        for u in usuarios
                    ])
                    
                    st.dataframe(df_usuarios)
                else:
                    st.info("Nenhum usuário encontrado.")
            except Exception as e:
                st.error(f"Erro ao listar usuários: {e}")
        
        with admin_tab2:
            with st.form("form_adicionar_usuario"):
                novo_usuario = st.text_input("Nome de Usuário")
                nova_senha_usuario = st.text_input("Senha", type="password")
                confirmar_senha_usuario = st.text_input("Confirmar Senha", type="password")
                is_admin = st.checkbox("Usuário Administrador")

                # Determina a unidade a ser atribuída
                if st.session_state.is_admin:
                    unidade_novo_usuario = st.selectbox("Unidade", ["MTZ", "SMR", "PFO"])
                else:
                    # Herdar unidade do usuário logado
                    dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
                    unidade_novo_usuario = dados_usuario[0]["unidade"] if dados_usuario else "N/A"
                    st.text_input("Unidade", value=unidade_novo_usuario, disabled=True)

                adicionar_usuario = st.form_submit_button("Adicionar Usuário")

                if adicionar_usuario:
                    if not novo_usuario or not nova_senha_usuario or not confirmar_senha_usuario:
                        st.error("❌ Todos os campos são obrigatórios.")
                    elif nova_senha_usuario != confirmar_senha_usuario:
                        st.error("❌ As senhas não coincidem.")
                    else:
                        try:
                            # Verificar se usuário já existe
                            check_response = supabase.table("usuarios").select("*").eq("nome_usuario", novo_usuario).execute()

                            if check_response.data:
                                st.error("❌ Nome de usuário já existe.")
                            else:
                                # Criar novo usuário
                                senha_hash = hash_senha(nova_senha_usuario)
                                insert_response = supabase.table("usuarios").insert({
                                    "nome_usuario": novo_usuario,
                                    "senha_hash": senha_hash,
                                    "is_admin": is_admin,
                                    "unidade": unidade_novo_usuario,
                                    "criado_em": obter_data_hora_atual_brasil().isoformat()
                                }).execute()

                                if insert_response.data:
                                    st.success("✅ Usuário adicionado com sucesso!")
                                    tm.sleep(1.5)
                                else:
                                    st.error("❌ Erro ao adicionar usuário.")
                        except Exception as e:
                            st.error(f"❌ Erro ao adicionar usuário: {e}")

        
        with admin_tab3:
            try:
                response = supabase.table("usuarios").select("*").execute()
                if response.data:
                    usuarios = response.data
                    nomes_usuarios = [u["nome_usuario"] for u in usuarios]
                    
                    usuario_selecionado = st.selectbox("Selecione um usuário", nomes_usuarios)
                    
                    if usuario_selecionado:
                        usuario_data = next((u for u in usuarios if u["nome_usuario"] == usuario_selecionado), None)
                        
                        if usuario_data:
                            with st.form("form_editar_usuario"):
                                nova_senha_admin = st.text_input("Nova Senha (deixe em branco para não alterar)", type="password")
                                is_admin_edit = st.checkbox("Usuário Administrador", value=usuario_data.get("is_admin", False))
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    editar_usuario = st.form_submit_button("Atualizar Usuário")
                                with col2:
                                    excluir_usuario = st.form_submit_button("Excluir Usuário", type="primary", help="Esta ação não pode ser desfeita")
                                
                                if editar_usuario:
                                    try:
                                        update_data = {"is_admin": is_admin_edit}
                                        
                                        if nova_senha_admin:
                                            update_data["senha_hash"] = hash_senha(nova_senha_admin)
                                        
                                        update_response = supabase.table("usuarios").update(update_data).eq("nome_usuario", usuario_selecionado).execute()
                                        
                                        if update_response.data:
                                            st.success("✅ Usuário atualizado com sucesso!")
                                        else:
                                            st.error("❌ Erro ao atualizar usuário.")
                                    except Exception as e:
                                        st.error(f"❌ Erro ao atualizar usuário: {e}")
                                
                                if excluir_usuario:
                                    if usuario_selecionado == st.session_state.username:
                                        st.error("❌ Você não pode excluir seu próprio usuário.")
                                    else:
                                        try:
                                            delete_response = supabase.table("usuarios").delete().eq("nome_usuario", usuario_selecionado).execute()
                                            
                                            if delete_response.data:
                                                st.success("✅ Usuário excluído com sucesso!")
                                                tm.sleep(1.5)
                                                st.rerun()
                                            else:
                                                st.error("❌ Erro ao excluir usuário.")
                                        except Exception as e:
                                            st.error(f"❌ Erro ao excluir usuário: {e}")
                else:
                    st.info("Nenhum usuário encontrado.")
            except Exception as e:
                st.error(f"Erro ao carregar usuários: {e}")

# =========================
#     ABA 6 - NOTIFICAÇÕES POR E-MAIL (APENAS ADMIN)
# =========================
if st.session_state.aba_ativa == "aba6" and st.session_state.is_admin:
    st.header("Notificações por E-mail")
        
    st.markdown("""
    ### Sistema de Notificação Automática
    
    Este sistema envia e-mails automáticos para clientes que possuem ocorrências abertas há mais de 30 minutos.
    
    Os e-mails são enviados utilizando:
    - **Remetente:** ticket@clicklogtransportes.com.br
    - **Servidor SMTP:** smtp.kinghost.net
    
    Os destinatários são obtidos da planilha de clientes:
    - **E-mail principal:** Coluna C (enviar_para_email)
    - **E-mails em cópia (CC):** Coluna D (email_copia), separados por ponto e vírgula
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Testar Conexão SMTP")
        if st.button("Testar Conexão"):
            with st.spinner("Testando conexão com servidor SMTP..."):
                sucesso, mensagem = testar_conexao_smtp()
                if sucesso:
                    st.success(mensagem)
                else:
                    st.error(mensagem)
    
    with col2:
        st.subheader("Enviar Notificações Manualmente")
        if st.button("Enviar Notificações Agora"):
            with st.spinner("Verificando ocorrências e enviando e-mails..."):
                resultados = notificar_ocorrencias_abertas()
                
                # Exibir resultados
                for resultado in resultados:
                    if resultado.get("status") == "info":
                        st.info(resultado.get("mensagem"))
                    elif resultado.get("status") == "sucesso":
                        st.success(f"✅ E-mail enviado para {resultado.get('cliente')} - Ticket {resultado.get('ticket')} - NF {resultado.get('nota_fiscal')}")
                    else:
                        st.error(f"❌ Erro ao enviar para {resultado.get('cliente')}: {resultado.get('mensagem')}")

        # Exibir histórico de e-mails enviados
        st.subheader("Histórico de E-mails Enviados")

        # Buscar dados da tabela
        resposta = supabase.table("emails_enviados").select("*").order("data_hora", desc=True).execute()
        dados = resposta.data

        if dados:
            df_historico = pd.DataFrame(dados)
            
            # Formatar coluna de data/hora se necessário
            if "data_hora" in df_historico.columns:
                df_historico["data_hora"] = pd.to_datetime(df_historico["data_hora"]).dt.strftime("%d/%m/%Y %H:%M:%S")
            
            st.dataframe(df_historico)
        else:
            st.info("Nenhum e-mail enviado ainda.")

# Verificar e enviar e-mails para ocorrências abertas há mais de 30 minutos
ocorrencias_abertas = carregar_ocorrencias_abertas()
for ocorr in ocorrencias_abertas:
    if not ocorr.get("email_abertura_enviado", False):
        verificar_e_enviar_email_abertura(ocorr)

# =========================
#     ABA 8 - ESTATÍSTICAS
# =========================
if st.session_state.aba_ativa == "aba8":
    st.header("📊 Estatísticas de Ocorrências Finalizadas")

    ocorrencias_finalizadas = carregar_ocorrencias_finalizadas()

    if not ocorrencias_finalizadas:
        st.info("ℹ️ Nenhuma ocorrência finalizada para gerar estatísticas.")
        st.stop()

    df_finalizadas = pd.DataFrame(ocorrencias_finalizadas)

    # --- Limpeza e conversões ---
    df_finalizadas["data_hora_abertura"] = pd.to_datetime(
        df_finalizadas.get("abertura_ticket") or df_finalizadas.get("abertura_timestamp"), errors="coerce"
    )
    df_finalizadas["data_hora_finalizacao"] = pd.to_datetime(df_finalizadas["data_hora_finalizacao"], errors="coerce")
    df_finalizadas = df_finalizadas.dropna(subset=["data_hora_abertura", "data_hora_finalizacao"])

    # Calcula tempo de permanência
   # Remove timezone (caso exista)
    df_finalizadas["data_hora_abertura"] = df_finalizadas["data_hora_abertura"].dt.tz_localize(None)
    df_finalizadas["data_hora_finalizacao"] = df_finalizadas["data_hora_finalizacao"].dt.tz_localize(None)

    # Calcula permanência
    df_finalizadas["permanencia_horas"] = (
        df_finalizadas["data_hora_finalizacao"] - df_finalizadas["data_hora_abertura"]
    ).dt.total_seconds() / 3600

    # --- Estatísticas Gerais ---
    st.subheader("⏱️ Tempo Médio de Permanência")
    tempo_medio = df_finalizadas["permanencia_horas"].mean()
    st.metric("Tempo Médio de Permanência (h)", f"{tempo_medio:.2f} h")

    # --- Gráfico por Tipo de Ocorrência ---
    st.subheader("📌 Ocorrências por Tipo")
    tipo_counts = df_finalizadas["tipo_de_ocorrencia"].value_counts()
    st.bar_chart(tipo_counts)

    # --- Gráfico por Cliente ---
    st.subheader("🏢 Ocorrências por Cliente")
    cliente_counts = df_finalizadas["cliente"].value_counts()
    st.bar_chart(cliente_counts)

    # --- Gráfico de Tempo Médio por Focal ---
    st.subheader("👤 Tempo Médio por Focal")
    tempo_por_focal = df_finalizadas.groupby("focal")["permanencia_horas"].mean().sort_values(ascending=False)
    st.bar_chart(tempo_por_focal)


# =========================
#     ABA 7 - CADASTROS
# =========================
if st.session_state.aba_ativa == "aba7":
    st.header("Cadastros")

    cadastro_tab1, cadastro_tab2, cadastro_tab3, cadastro_tab4 = st.tabs(
        ["Motoristas", "Cidades", "Clientes", "Configurações de E-mail"]
    )

    
    # Aba de Cadastro de Motoristas
    with cadastro_tab1:
        st.subheader("Cadastro de Motoristas")
        
        # Formulário para cadastro de motoristas
        with st.form("form_cadastro_motorista", clear_on_submit=True):
            motorista_nome = st.text_input("Nome do Motorista (LETRAS MAIÚSCULAS)", key="motorista_nome")
            
            submit_motorista = st.form_submit_button("Cadastrar Motorista")
        
        # Processamento do formulário de motoristas
        if submit_motorista:
            if not motorista_nome:
                st.error("❌ Por favor, informe o nome do motorista.")
            elif not validar_texto_maiusculo(motorista_nome):
                st.error("❌ O nome do motorista deve estar em LETRAS MAIÚSCULAS.")
            else:
                sucesso, mensagem = inserir_motorista(motorista_nome)
                if sucesso:
                    st.success(mensagem)
                    # Recarregar a lista de motoristas
                    motoristas = carregar_motoristas_supabase()
                else:
                    st.error(mensagem)
        
        # Exibir lista de motoristas cadastrados
        st.subheader("Motoristas Cadastrados")
        motoristas_atuais = carregar_motoristas_supabase()
        if motoristas_atuais:
            for motorista in motoristas_atuais:
                st.text(motorista)
        else:
            st.info("Nenhum motorista cadastrado.")
    
    # Aba de Cadastro de Cidades
    with cadastro_tab2:
        st.subheader("Cadastro de Cidades")
        
        # Formulário para cadastro de cidades
        with st.form("form_cadastro_cidade", clear_on_submit=True):
            cidade_nome = st.text_input("Nome da Cidade", key="cidade_nome")
            
            submit_cidade = st.form_submit_button("Cadastrar Cidade")
        
        # Processamento do formulário de cidades
        if submit_cidade:
            if not cidade_nome:
                st.error("❌ Por favor, informe o nome da cidade.")
            else:
                sucesso, mensagem = inserir_cidade(cidade_nome)
                if sucesso:
                    st.success(mensagem)
                    # Recarregar a lista de cidades
                    cidades = carregar_cidades_supabase()
                else:
                    st.error(mensagem)
        
        # Exibir lista de cidades cadastradas
        st.subheader("Cidades Cadastradas")
        cidades_atuais = carregar_cidades_supabase()
        if cidades_atuais:
            for cidade in cidades_atuais:
                st.text(cidade)
        else:
            st.info("Nenhuma cidade cadastrada.")
    
    # Aba de Cadastro de Clientes
    with cadastro_tab3:
        st.subheader("Cadastro de Clientes")
        
        # Carregar lista de focais
        focal = carregar_focal_supabase()
        
        # Formulário para cadastro de clientes
        with st.form("form_cadastro_cliente", clear_on_submit=True):
            cliente_nome = st.text_input("Nome do Cliente (LETRAS MAIÚSCULAS)", key="cliente_nome")
            
            # Seleção de focal
            focal_selecionado = st.selectbox("Focal Responsável", options=focal, index=None, key="focal_cliente")
            
            # Checkbox para receber e-mails
            receber_emails = st.checkbox("Cliente deve receber e-mails de abertura/finalização", key="receber_emails")
            
            # Campos de e-mail
            email_principal = st.text_input("E-mail Principal", key="email_principal")
            email_copia = st.text_input("E-mails em Cópia (separados por ;)", key="email_copia")
            
            submit_cliente = st.form_submit_button("Cadastrar Cliente")
        
        # Processamento do formulário de clientes
        if submit_cliente:
            erros = []
            
            if not cliente_nome:
                erros.append("Por favor, informe o nome do cliente.")
            elif not validar_texto_maiusculo(cliente_nome):
                erros.append("O nome do cliente deve estar em LETRAS MAIÚSCULAS.")
            
            if not focal_selecionado:
                erros.append("Por favor, selecione um focal responsável.")
            
            if receber_emails:
                if not email_principal:
                    erros.append("Por favor, informe o e-mail principal do cliente.")
                elif not validar_email(email_principal):
                    erros.append("O e-mail principal informado não é válido.")
                
                if email_copia and not validar_emails_multiplos(email_copia):
                    erros.append("Um ou mais e-mails em cópia não são válidos.")
            
            if erros:
                for erro in erros:
                    st.error(f"❌ {erro}")
            else:
                sucesso, mensagem = inserir_cliente(
                    cliente_nome, 
                    focal_selecionado, 
                    receber_emails, 
                    email_principal if receber_emails else "", 
                    email_copia if receber_emails else ""
                )
                
                if sucesso:
                    st.success(mensagem)
                    # Recarregar a lista de clientes
                    df_clientes = carregar_clientes_supabase()
                    clientes = df_clientes["cliente"].tolist()
                else:
                    st.error(mensagem)
        
        # Exibir lista de clientes cadastrados
        st.subheader("Clientes Cadastrados")
        df_clientes_atuais = carregar_clientes_supabase()
        if not df_clientes_atuais.empty:
            st.dataframe(df_clientes_atuais)
        else:
            st.info("Nenhum cliente cadastrado.")
    
    # Aba de Configurações de E-mail
    with cadastro_tab4:
        st.subheader("Configurações de Tempo de Envio de E-mail")
        
        # Carregar configuração atual
        tempo_atual = carregar_tempo_envio_email()
        
        # Slider para configurar o tempo de envio
        tempo_envio = st.slider(
            "Tempo de envio dos e-mails (minutos)",
            min_value=1,
            max_value=60,
            value=tempo_atual,
            step=1,
            key="tempo_envio_slider"
        )
        
        # Botão para salvar configuração
        if st.button("Salvar Configuração"):
            sucesso, mensagem = atualizar_tempo_envio_email(tempo_envio)
            if sucesso:
                st.success(mensagem)
            else:
                st.error(mensagem)
        
        st.info(f"Configuração atual: E-mails serão enviados após {tempo_atual} minutos.")
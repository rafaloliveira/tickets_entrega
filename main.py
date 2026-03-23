import streamlit as st
import base64
st.set_page_config(
    page_title="F4Stay",
    page_icon="assets/Logo FA.png",  # caminho da imagem do favicon
    layout="wide"
)

import os
import re
import time as tm
import uuid
import base64
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

from streamlit_autorefresh import st_autorefresh
from streamlit_cookies_manager import EncryptedCookieManager
from supabase import create_client, Client as SupabaseClient

load_dotenv()

# ====================================================================
# 1. CONFIGURAÇÕES GLOBAIS E CHAVES (EMAIL, SUPABASE, FUSO HORÁRIO)
# ====================================================================

# --- CONFIGURAÇÕES DE E-MAIL (AGORA COM RESEND) ---
EMAIL_REMETENTE = "ticket@clicklogtransportes.com.br" 

# Credenciais do Resend
SMTP_USERNAME = "resend" 
SMTP_PASSWORD = "re_Pu2eoqr2_F79XHV2ca2YcP5qcHf6NNGzD" # <--- SUA CHAVE API DO RESEND AQUI
SMTP_HOST = "smtp.resend.com" 
SMTP_PORT = 587 

socket.setdefaulttimeout(30) 

# --- DEFINIÇÃO DO FUSO HORÁRIO BRASILEIRO ---
FUSO_HORARIO_BRASIL = pytz.timezone("America/Sao_Paulo")

# --- SETUP DO COOKIE MANAGER ---
cookies = EncryptedCookieManager(
    prefix="meu_app_", 
    password="chave-muito-secreta-para-cookies" 
)
if not cookies.ready():
    st.stop()

# --- CONEXÃO COM O SUPABASE ---
url = "https://vismjxhlsctehpvgmata.supabase.co"  
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZpc21qeGhsc2N0ZWhwdmdtYXRhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY1NzA4NTIsImV4cCI6MjA2MjE0Njg1Mn0.zTjSWenfuVJTIixq2RThSUpqcHGfZWP2xkFDU3USPb0"  
supabase = create_client(url, key)

# ====================================================================
# 2. FUNÇÕES AUXILIARES GERAIS (COOKIES, IMAGENS, SEGURANÇA)
# ====================================================================

def is_cookie_expired(expiry_time_str):
    try:
        expiry_time = datetime.strptime(expiry_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) > expiry_time

@st.cache_data
def get_base64_image_cached(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

img_base64_logo_principal = get_base64_image_cached("assets/logo_fundo_branco.jpg")
img_base64_fa = get_base64_image_cached("assets/Logo FA.png")

def hash_senha(senha):
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()

def verificar_senha(senha_fornecida, senha_hash):
    return bcrypt.checkpw(senha_fornecida.encode(), senha_hash.encode())

def limpar_nome_arquivo(nome_original):
    nome_limpo = re.sub(r'[^a-zA-Z0-9_.-]', '_', nome_original)
    return nome_limpo

# ====================================================================
# 3. FUNÇÕES AUXILIARES DE DATA E HORA COM FUSO HORÁRIO
# ====================================================================

def obter_data_hora_atual_brasil():
    return datetime.now(FUSO_HORARIO_BRASIL)

def converter_para_fuso_brasil(data_hora):
    if data_hora.tzinfo is None:
        data_hora = data_hora.replace(tzinfo=timezone.utc)
    return data_hora.astimezone(FUSO_HORARIO_BRASIL)

def calcular_diferenca_tempo(data_hora_inicial, data_hora_final=None):
    if data_hora_final is None:
        data_hora_final = obter_data_hora_atual_brasil()
    
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
    try:
        data_hora_str = f"{data_str} {hora_str}"
        data_hora = datetime.strptime(data_hora_str, "%Y-%m-%d %H:%M:%S")
        return FUSO_HORARIO_BRASIL.localize(data_hora)
    except Exception as e:
        return None

# ====================================================================
# 4. FUNÇÕES DE AUTENTICAÇÃO E USUÁRIOS
# ====================================================================

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
        st.error(f"Erro ao autenticar: {e}")
        return None

# ====================================================================
# 5. FUNÇÕES DE INTERAÇÃO COM O SUPABASE (CRUD DE DADOS)
# ====================================================================

def inserir_ocorrencia_supabase(dados):
    data_hora_manual = criar_datetime_manual(dados["data_abertura_manual"], dados["hora_abertura_manual"])
    
    if data_hora_manual:
        data_hora_str = data_hora_manual.strftime("%Y-%m-%d %H:%M:%S")
        timestamp_iso = data_hora_manual.isoformat()
        
        response = supabase.table("ocorrencias").insert([{
            "id": dados["id"],
            "numero_ticket": dados["numero_ticket"],
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
            "data_hora_abertura": data_hora_str,  
            "abertura_timestamp": timestamp_iso,  
            "permanencia": dados["permanencia"],
            "complementar": dados["complementar"],
            "data_abertura_manual": dados["data_abertura_manual"],
            "hora_abertura_manual": dados["hora_abertura_manual"],
            "alerta_1_enviado": False, 
            "alerta_2_enviado": False,
            "alerta_3_enviado": False, 
            "alerta_4_enviado": False,
            "alerta_5_enviado": False,
            "email_finalizacao_enviado": False,
            "imagem_url": dados["imagem_url"],
            "ticket_unidade": dados["ticket_unidade"]
        }]).execute()
        return response
    else:
        st.error("Erro ao criar data/hora manual para inserção no banco")
        return None



def atualizar_ocorrencia_supabase(id_ocorrencia, dados_update):
    """Atualiza os dados de um ticket aberto no Supabase."""
    try:
        response = supabase.table("ocorrencias").update(dados_update).eq("id", id_ocorrencia).execute()
        return True, "Ocorrência atualizada com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar ocorrência: {e}"

@st.cache_data(ttl=3600)
def carregar_clientes_supabase():
    try:
        response = supabase.table("clientes").select("cliente, focal, enviar_para_email, email_copia, cnpj, janela_1, janela_2, janela_3, janela_4, janela_5").execute()
        if response.data:
            df_clientes = pd.DataFrame(response.data)
            df_clientes = df_clientes.dropna(subset=["cliente"])
            return df_clientes
        else:
            return pd.DataFrame(columns=["cliente", "focal", "enviar_para_email", "email_copia", "cnpj", "janela_1", "janela_2", "janela_3", "janela_4", "janela_5"])
    except Exception as e:
        st.error(f"Erro ao carregar clientes do banco: {e}")
        return pd.DataFrame(columns=["cliente", "focal", "enviar_para_email", "email_copia", "cnpj", "janela_1", "janela_2", "janela_3", "janela_4", "janela_5"])

df_clientes = carregar_clientes_supabase() 
cliente_to_focal = dict(zip(df_clientes["cliente"], df_clientes["focal"])) if not df_clientes.empty else {}
cliente_to_emails = {
    row["cliente"]: {
        "principal": row.get("enviar_para_email", ""),
        "copia": row.get("email_copia", "")
    }
    for _, row in df_clientes.iterrows()
} if not df_clientes.empty else {}

# 🟢 1. CLIENTES ORDENADOS
clientes = sorted(df_clientes["cliente"].tolist(), key=lambda x: str(x).lower()) if not df_clientes.empty else []

@st.cache_data
def carregar_cidades_supabase():
    try:
        response = supabase.table("cidades").select("cidade, id").execute()
        if response.data:
            cidades = [item["cidade"] for item in response.data if item.get("cidade")]
            # 🟢 2. CIDADES ORDENADAS
            return sorted(set(cidades), key=lambda x: str(x).lower())
        else:
            return []
    except Exception as e:
        st.error(f"Erro ao carregar cidades do banco: {e}")
        return []

cidades = carregar_cidades_supabase()

@st.cache_data
def carregar_motoristas_supabase():
    try:
        motoristas_list = []
        pagina = 0
        pagina_tamanho = 1000 
        while True:
            resposta = supabase.table("motoristas") \
                .select("motorista, id") \
                .range(pagina * pagina_tamanho, (pagina + 1) * pagina_tamanho - 1) \
                .execute()

            dados = resposta.data
            if not dados:
                break
            motoristas_list.extend([item["motorista"].strip() for item in dados if item.get("motorista")])
            pagina += 1
        # 🟢 3. MOTORISTAS ORDENADOS
        return sorted(set(motoristas_list), key=lambda x: str(x).lower())
    except Exception as e:
        st.error(f"Erro ao carregar motoristas do banco: {e}")
        return []

motoristas = carregar_motoristas_supabase() 

@st.cache_data(ttl=3600)
def carregar_focal_supabase():
    try:
        response = supabase.table("clientes").select("focal").execute()
        if response.data:
            focais = [item["focal"] for item in response.data if item.get("focal")]
            # 🟢 4. FOCAIS ORDENADOS
            return sorted(set(focais), key=lambda x: str(x).lower())
        else:
            return []
    except Exception as e:
        st.error(f"Erro ao carregar focais do banco: {e}")
        return []

@st.cache_data(ttl=3600)
def carregar_filiais_supabase():
    try:
        response = supabase.table("filiais").select("sigla").execute()
        if response.data:
            siglas = [item["sigla"] for item in response.data if item.get("sigla")]
            # 🟢 5. FILIAIS ORDENADAS
            return sorted(set(siglas), key=lambda x: str(x).lower())
        return []
    except Exception as e:
        st.error(f"Erro ao carregar filiais do banco: {e}")
        return []

lista_filiais = carregar_filiais_supabase()

def validar_nome_cliente(texto):
    """Verifica se o nome está em maiúsculo, sem acentos, sem Ç e sem caracteres especiais."""
    # Aceita apenas letras de A a Z (sem acento), números e espaços em branco
    padrao = r'^[A-Z0-9 ]+$'
    return bool(re.match(padrao, texto))

def validar_email(email):
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None

def validar_emails_multiplos(emails):
    if not emails:
        return True
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    for email in emails.split(';'):
        email = email.strip()
        if email and not re.match(padrao, email):
            return False
    return True

def inserir_motorista(motorista):
    try:
        response = supabase.table("motoristas").insert({"motorista": motorista}).execute()
        return True, "Motorista cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar motorista: {e}"

def inserir_cidade(cidade):
    try:
        response = supabase.table("cidades").insert({"cidade": cidade}).execute()
        return True, "Cidade cadastrada com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar cidade: {e}"

def inserir_cliente(novo_cliente, focal, receber_emails, email_principal, email_copia, cnpj, j1, j2, j3, j4, j5):
    try:
        # Verifica duplicidade de Nome
        check_nome = supabase.table("clientes").select("cliente").eq("cliente", novo_cliente).execute()
        if check_nome.data and len(check_nome.data) > 0:
            return False, f"O cliente '{novo_cliente}' já está cadastrado."

        # Verifica duplicidade de CNPJ (limpa a string para ter apenas números)
        cnpj_numeros = re.sub(r'[^0-9]', '', cnpj)
        if cnpj_numeros:
            check_cnpj = supabase.table("clientes").select("cnpj").eq("cnpj", cnpj_numeros).execute()
            if check_cnpj.data and len(check_cnpj.data) > 0:
                return False, f"O CNPJ '{cnpj_numeros}' já está vinculado a outro cliente no sistema."

        dados = {
            "cliente": novo_cliente,
            "focal": focal,
            "receber_emails": receber_emails,
            "enviar_para_email": email_principal.lower(), # Força minúsculo no banco
            "email_copia": email_copia.lower() if email_copia else "", # Força minúsculo no banco
            "cnpj": cnpj_numeros,
            "janela_1": j1 if j1 > 0 else None,
            "janela_2": j2 if j2 > 0 else None,
            "janela_3": j3 if j3 > 0 else None,
            "janela_4": j4 if j4 > 0 else None,
            "janela_5": j5 if j5 > 0 else None
        }
        supabase.table("clientes").insert(dados).execute()
        return True, f"Cliente '{novo_cliente}' cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao inserir cliente: {e}"


def inserir_filial(nome, sigla):
    """Insere uma nova filial no Supabase."""
    try:
        supabase.table("filiais").insert({"filial": nome, "sigla": sigla}).execute()
        return True, "Filial cadastrada com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar filial: {e}"

def atualizar_filial(id_filial, nome, sigla):
    """Atualiza uma filial existente no Supabase."""
    try:
        supabase.table("filiais").update({"filial": nome, "sigla": sigla}).eq("id", id_filial).execute()
        return True, "Filial atualizada com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar filial: {e}"
    
def atualizar_motorista(id_motorista, novo_nome):
    try:
        supabase.table("motoristas").update({"motorista": novo_nome}).eq("id", id_motorista).execute()
        return True, "Motorista atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar: {e}"

def atualizar_cidade(id_cidade, nova_cidade):
    try:
        supabase.table("cidades").update({"cidade": nova_cidade}).eq("id", id_cidade).execute()
        return True, "Cidade atualizada com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar: {e}"

def atualizar_cliente(id_cliente, dados_update):
    try:
        supabase.table("clientes").update(dados_update).eq("id", id_cliente).execute()
        return True, "Cliente atualizado com sucesso!"
    except Exception as e:
        return False, f"Erro ao atualizar: {e}"

def atualizar_tempo_envio_email(minutos):
    try:
        st.session_state.tempo_envio_email = minutos 
        response = supabase.table("configuracoes").upsert({
            "chave": "tempo_envio_email",
            "valor": str(minutos)
        }).execute()
        return True, f"Tempo de envio de e-mail atualizado para {minutos} minutos!"
    except Exception as e:
        return False, f"Erro ao atualizar tempo de envio de e-mail: {e}"

def carregar_tempo_envio_email():
    try:
        response = supabase.table("configuracoes").select("valor").eq("chave", "tempo_envio_email").execute()
        if response.data:
            return int(response.data[0]["valor"])
        else:
            return 30  
    except Exception as e:
        st.error(f"Erro ao carregar tempo de envio de e-mail: {e}")
        return 30  

@st.cache_data(ttl=420) 
def carregar_ocorrencias_abertas():
    try:
        cols = "id, numero_ticket, nota_fiscal, cliente, focal, destinatario, cidade, motorista, tipo_de_ocorrencia, observacoes, responsavel, status, data_abertura_manual, hora_abertura_manual, alerta_1_enviado, alerta_2_enviado, alerta_3_enviado, alerta_4_enviado, alerta_5_enviado, imagem_url"
        if st.session_state.is_admin:
            response = supabase.table("ocorrencias").select(cols).eq("status", "Aberta").order("data_hora_abertura", desc=True).execute()
        else:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            response = supabase.table("ocorrencias").select(cols).eq("status", "Aberta").eq("ticket_unidade", unidade_usuario).order("data_hora_abertura", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências abertas: {e}")
        return []

def carregar_ocorrencias_por_focal(focal=None):
    try:
        cols = "id, numero_ticket, nota_fiscal, cliente, focal, destinatario, cidade, motorista, tipo_de_ocorrencia, observacoes, responsavel, status, data_abertura_manual, hora_abertura_manual, alerta_1_enviado, alerta_2_enviado, alerta_3_enviado, alerta_4_enviado, alerta_5_enviado, imagem_url"
        if st.session_state.is_admin:
            response = supabase.table("ocorrencias").select(cols).eq("status", "Aberta").eq("focal", focal).order("data_hora_abertura", desc=True).execute()
        else:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            response = supabase.table("ocorrencias").select(cols).eq("status", "Aberta").eq("focal", focal).eq("ticket_unidade", unidade_usuario).order("data_hora_abertura", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências por focal: {e}")
        return []

def obter_focais_com_contagem():
    try:
        ocorrencias = carregar_ocorrencias_abertas() 
        focais_contagem = {}
        for ocorr in ocorrencias:
            focal = ocorr.get('focal')
            if focal:
                if focal not in focais_contagem:
                    focais_contagem[focal] = 0
                focais_contagem[focal] += 1
        
        focais_ordenados = sorted(focais_contagem.items(), key=lambda x: x[1], reverse=True)
        return focais_ordenados
    except Exception as e:
        st.error(f"Erro ao obter focais com contagem: {e}")
        return []

def finalizar_ocorrencia(ocorr, complemento, data_finalizacao_manual, hora_finalizacao_manual, imagem_url_finalizacao="", observacao_final="", numero_manifesto_val=""):
    try:
        data_abertura_manual = ocorr.get("data_abertura_manual")
        hora_abertura_manual = ocorr.get("hora_abertura_manual")
        
        if not data_abertura_manual or not hora_abertura_manual:
            return False, "Data/hora de abertura manual ausente. Não é possível calcular a permanência."
        
        try:
            data_finalizacao_obj = data_finalizacao_manual
            data_hora_finalizacao = datetime.combine(data_finalizacao_obj, hora_finalizacao_manual)

            if data_hora_finalizacao.tzinfo is None:
                data_hora_finalizacao = FUSO_HORARIO_BRASIL.localize(data_hora_finalizacao)
            else:
                data_hora_finalizacao = data_hora_finalizacao.astimezone(FUSO_HORARIO_BRASIL)
            
            data_hora_abertura = criar_datetime_manual(data_abertura_manual, hora_abertura_manual)
            if not data_hora_abertura:
                return False, "Erro ao criar datetime a partir de data/hora de abertura manual."
            
            if data_hora_finalizacao < data_hora_abertura:
                return False, "Data/hora de finalização não pode ser menor que a data/hora de abertura."
            
            delta = calcular_diferenca_tempo(data_hora_abertura, data_hora_finalizacao)
            total_segundos = int(delta.total_seconds())
            horas = total_segundos // 3600
            minutos = (total_segundos % 3600) // 60
            segundos = total_segundos % 60
            permanencia_manual = f"{horas:02d}:{minutos:02d}:{segundos:02d}"

            data_finalizacao_banco = data_hora_finalizacao.strftime("%Y-%m-%d")
            hora_finalizacao_banco = data_hora_finalizacao.strftime("%H:%M:%S")

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
                "numero_manifesto": numero_manifesto_val, 
                "imagem_finalizacao_url": imagem_url_finalizacao
            }).eq("id", ocorr["id"]).execute()
            
            if response and response.data:
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

# ====================================================================
# 6. FUNÇÕES DE E-MAIL E NOVO MOTOR DINÂMICO
# ====================================================================

def enviar_email_com_backup(destinatario, copia, assunto, corpo, imagem_url=None):
    provedores = [
        {
            "nome": "Resend",
            "host": "smtp.resend.com",
            "port": 587,
            "username": "resend",
            "password": "re_Pu2eoqr2_F79XHV2ca2YcP5qcHf6NNGzD",  
            "from_email": "ClickLog Transportes <ticket@clicklogtransportes.com.br>"
        },
        {
            "nome": "Gmail",
            "host": "smtp.gmail.com",
            "port": 587,
            "username": "ticketclicklogtransportes@gmail.com",
            "password": "gpbh tjyq wyvi jibs",
            "from_email": "ClickLog Transportes <ticketclicklogtransportes@gmail.com>"
        }
    ]
    
    def processar_lista_emails(texto):
        if not texto: return []
        texto = texto.replace(',', ';')
        return [e.strip() for e in texto.split(';') if e.strip()]

    for provedor in provedores:
        try:
            print(f"🔄 Tentando enviar via {provedor['nome']}...")
            
            lista_destinatarios = processar_lista_emails(destinatario)
            lista_copia = processar_lista_emails(copia)
            
            if not lista_destinatarios:
                continue 
            
            todos_destinatarios = lista_destinatarios + lista_copia

            msg = MIMEMultipart('alternative')
            msg['From'] = provedor['from_email']
            msg['To'] = ', '.join(lista_destinatarios)
            if lista_copia: msg['Cc'] = ', '.join(lista_copia)

            msg['Subject'] = assunto
            msg['Reply-To'] = "noreply@clicklogtransportes.com.br" # <-- Força o redirecionamento
            msg.attach(MIMEText(corpo, 'html', 'utf-8'))

            if imagem_url:
                try:
                    response = requests.get(imagem_url, timeout=5) 
                    if response.status_code == 200:
                        img_data = response.content
                        image_mime = MIMEImage(img_data)
                        image_mime.add_header('Content-Disposition', 'attachment', filename="imagem_ocorrencia.jpg")
                        msg.attach(image_mime)
                except Exception as e:
                    print(f"⚠️ {provedor['nome']}: Erro ao processar imagem: {e}")

            server = smtplib.SMTP(provedor['host'], provedor['port'], timeout=15)
            server.starttls()
            server.login(provedor['username'], provedor['password'])
            server.sendmail(provedor['from_email'], todos_destinatarios, msg.as_string())
            server.quit()

            print(f"✅ E-mail enviado com sucesso via {provedor['nome']}")
            return True, f"E-mail enviado com sucesso via {provedor['nome']}", provedor['nome']

        except smtplib.SMTPAuthenticationError as e:
            print(f"❌ {provedor['nome']}: Falha na autenticação - {e}")
            if provedor['nome'] == 'Resend': print("🔄 Conta Resend pode estar suspensa, tentando Gmail...")
            continue 
            
        except smtplib.SMTPException as e:
            print(f"❌ {provedor['nome']}: Erro SMTP - {e}")
            continue 
            
        except Exception as e:
            print(f"❌ {provedor['nome']}: Erro inesperado - {e}")
            continue 

    return False, "Todos os provedores de e-mail falharam", "Nenhum"

def enviar_email(destinatario, copia, assunto, corpo, imagem_url=None):
    sucesso, mensagem, provedor = enviar_email_com_backup(destinatario, copia, assunto, corpo, imagem_url)
    return sucesso, mensagem


def carregar_regras_clientes():
    """Carrega os e-mails e as janelas de notificação personalizadas de todos os clientes."""
    try:
        response = supabase.table("clientes").select("cliente, enviar_para_email, email_copia, janela_1, janela_2, janela_3, janela_4, janela_5").execute()
        if response.data:
            return {
                item["cliente"]: {
                    "principal": item.get("enviar_para_email", ""),
                    "copia": item.get("email_copia", ""),
                    "janelas": [
                        item.get("janela_1"),
                        item.get("janela_2"),
                        item.get("janela_3"),
                        item.get("janela_4"),
                        item.get("janela_5")
                    ]
                }
                for item in response.data if item.get("enviar_para_email")
            }
        return {}
    except Exception as e:
        print(f"Erro ao carregar regras dos clientes: {e}")
        return {}

def processar_envio_automatico():
    """Verifica e envia e-mails para tickets com base nas janelas personalizadas de cada cliente."""
    try:
        print("🔄 Iniciando processamento dinâmico de e-mails...")
        
        cols = "id, numero_ticket, nota_fiscal, cliente, destinatario, cidade, motorista, tipo_de_ocorrencia, data_abertura_manual, hora_abertura_manual, imagem_url, status, alerta_1_enviado, alerta_2_enviado, alerta_3_enviado, alerta_4_enviado, alerta_5_enviado"
        
        response = supabase.table("ocorrencias").select(cols).eq("status", "Aberta").execute()
        tickets = response.data
        
        if not tickets:
            print("ℹ️ Nenhum ticket aberto para verificação.")
            return []

        regras_clientes = carregar_regras_clientes()
        agora = obter_data_hora_atual_brasil()
        resultados = []

        for ocorr in tickets:
            cliente_nome = ocorr.get("cliente")
            regra = regras_clientes.get(cliente_nome)
            
            if not regra or not regra["principal"]:
                continue 

            data_str = ocorr.get("data_abertura_manual")
            hora_str = ocorr.get("hora_abertura_manual")
            if not data_str or not hora_str:
                continue

            dt_abertura = criar_datetime_manual(data_str, hora_str)
            if not dt_abertura:
                continue
            
            diferenca = agora - dt_abertura
            minutos_decorridos = diferenca.total_seconds() / 60

            # Formatações exigidas para os E-mails (Ticket apenas 5 últimos e Data DD/MM/YYYY HH:MM)
            ticket_formatado = str(ocorr.get('numero_ticket', '-'))[-5:]
            try:
                data_abertura_formatada = datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                data_abertura_formatada = data_str
            try:
                hora_abertura_formatada = datetime.strptime(hora_str, "%H:%M:%S").strftime("%H:%M")
            except:
                hora_abertura_formatada = hora_str[:5] if hora_str else ""

            for i in range(5):
                janela_minutos = regra["janelas"][i]
                num_alerta = i + 1
                coluna_flag = f"alerta_{num_alerta}_enviado"

                if janela_minutos and minutos_decorridos >= janela_minutos and not ocorr.get(coluna_flag):
                    
                    print(f"📧 Disparando Alerta {num_alerta} ({janela_minutos}min) - Ticket {ticket_formatado}")
                    
                    assunto = f"Alerta de Permanência ({int(janela_minutos)} min) - Ticket {ticket_formatado}"
                    imagem_html = f'<tr><th>Imagem</th><td><a href="{ocorr.get("imagem_url")}">Visualizar</a></td></tr>' if ocorr.get("imagem_url") else ''

                    corpo = f"""
                    <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; font-size: 14px; color: #333; }}
                            table {{ border-collapse: collapse; width: 100%; max-width: 600px; border: 1px solid #ddd; font-size: 13px; }}
                            th, td {{ border: 1px solid #ddd; padding: 5px 8px; text-align: left; }}
                            th {{ background-color: #f2f2f2; width: 35%; color: #555; }}
                            .header {{ background-color: #d9534f; color: white; padding: 10px; max-width: 580px; border-radius: 4px 4px 0 0; }}
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h2>Notificação de Ocorrência em Aberto</h2>
                        </div>
                        <p>Prezado(a) cliente <strong>{cliente_nome}</strong>,</p>
                        <p>Informamos que o veículo encontra-se no ponto de descarga há mais de <strong>{int(janela_minutos)} minutos</strong>.</p>
                        <p>Solicitamos sua atuação imediata para regularização do processo de descarga para evitar custos adicionais de TDE.</p>
                        <table>
                            <tr><th>Ticket</th><td>{ticket_formatado}</td></tr>
                            <tr><th>Nota Fiscal</th><td>{ocorr.get('nota_fiscal', '-')}</td></tr>
                            <tr><th>Destinatário</th><td>{ocorr.get('destinatario', '-')}</td></tr>
                            <tr><th>Cidade</th><td>{ocorr.get('cidade', '-')}</td></tr>
                            <tr><th>Tipo de Ocorrência</th><td>{ocorr.get('tipo_de_ocorrencia', '-')}</td></tr>
                            <tr><th>Data/Hora de Abertura</th><td>{data_abertura_formatada} {hora_abertura_formatada}</td></tr>
                            {imagem_html}
                        </table>
                        <p style="font-size: 11px; color: gray; margin-top: 20px;">⚠️ Este é um e-mail automático. Por favor, não responda.</p>
                        <p style="margin-bottom: 5px;">Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
                        <img src="https://vismjxhlsctehpvgmata.supabase.co/storage/v1/object/public/assets/logo.png" alt="Logo ClickLog" style="width: 150px; height: auto; margin-top: 10px;">
                    </body>
                    </html>
                    """

                    enviou, msg = enviar_email(regra["principal"], regra["copia"], assunto, corpo, ocorr.get("imagem_url"))
                    
                    if enviou:
                        supabase.table("ocorrencias").update({coluna_flag: True}).eq("id", ocorr["id"]).execute()
                        supabase.table("emails_enviados").insert({
                            "data_hora": obter_data_hora_atual_brasil().isoformat(),
                            "tipo": f"Alerta {num_alerta} ({int(janela_minutos)}m)",
                            "cliente": cliente_nome,
                            "email": regra["principal"],
                            "ticket": ticket_formatado,
                            "nota_fiscal": ocorr.get('nota_fiscal', '-'),
                            "status": "Enviado"
                        }).execute()
                        resultados.append({"cliente": cliente_nome, "ticket": ticket_formatado, "status": "sucesso", "mensagem": f"Alerta {num_alerta} enviado"})
                    else:
                        resultados.append({"cliente": cliente_nome, "ticket": ticket_formatado, "status": "erro", "mensagem": msg})
                    
                    break 
        
        return resultados
    except Exception as e:
        print(f"⚠️ Erro crítico no processamento automático: {e}")
        return []

def notificar_ocorrencias_abertas():
    return processar_envio_automatico()

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

def marcar_email_como_enviado(ocorrencia_id, tipo="abertura"):
    pass

def enviar_email_finalizacao(ocorr_atualizada):
    try:
        clientes_emails = carregar_dados_clientes_email()
        cliente = ocorr_atualizada.get('cliente')
        
        if cliente in clientes_emails:
            email_info = clientes_emails[cliente]
            email_principal = email_info['principal']
            email_copia = email_info['copia']
            
            # Formatação refinada
            ticket_formatado = str(ocorr_atualizada.get('numero_ticket', '-'))[-5:]
            
            d_abertura = ocorr_atualizada.get('data_abertura_manual', '')
            h_abertura = ocorr_atualizada.get('hora_abertura_manual', '')
            try: d_abertura_fmt = datetime.strptime(d_abertura, "%Y-%m-%d").strftime("%d/%m/%Y")
            except: d_abertura_fmt = d_abertura
            try: h_abertura_fmt = datetime.strptime(h_abertura, "%H:%M:%S").strftime("%H:%M")
            except: h_abertura_fmt = h_abertura[:5] if h_abertura else ""
            
            d_fim = ocorr_atualizada.get('data_finalizacao_manual', '')
            h_fim = ocorr_atualizada.get('hora_finalizacao_manual', '')
            try: d_fim_fmt = datetime.strptime(d_fim, "%Y-%m-%d").strftime("%d/%m/%Y")
            except: d_fim_fmt = d_fim
            try: h_fim_fmt = datetime.strptime(h_fim, "%H:%M:%S").strftime("%H:%M")
            except: h_fim_fmt = h_fim[:5] if h_fim else ""

            data_abertura_email = f"{d_abertura_fmt} {h_abertura_fmt}"
            data_finalizacao_email = f"{d_fim_fmt} {h_fim_fmt}"
            
            imagem_url = ocorr_atualizada.get("imagem_finalizacao_url", "")
            if imagem_url:
                imagem_html = f"""
                <tr>
                    <th>Imagem Ticket</th>
                    <td><a href="{imagem_url}" target="_blank" style="color:#007bff;text-decoration:none;">Baixar Imagem</a></td>
                </tr>
                """
            else:
                imagem_html = "<tr><th>Imagem Ticket</th><td>Não Anexada</td></tr>"
            
            corpo_html = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; font-size: 14px; color: #333; }}
                    table {{ border-collapse: collapse; width: 100%; max-width: 600px; border: 1px solid #ddd; font-size: 13px; }}
                    th, td {{ border: 1px solid #ddd; padding: 5px 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; width: 35%; color: #555; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 10px; max-width: 580px; border-radius: 4px 4px 0 0; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>Notificação de Ocorrência Finalizada</h2>
                </div>
                <p>Prezado cliente <strong>{cliente}</strong>,</p>
                <p>Informamos que a seguinte ocorrência foi finalizada:</p>
                <table>
                    <tr><th>Ticket</th><td>{ticket_formatado}</td></tr>
                    <tr><th>Nota Fiscal</th><td>{ocorr_atualizada.get('nota_fiscal', '-')}</td></tr>
                    <tr><th>Destinatário</th><td>{ocorr_atualizada.get('destinatario', '-')}</td></tr>
                    <tr><th>Cidade</th><td>{ocorr_atualizada.get('cidade', '-')}</td></tr>
                    <tr><th>Motorista</th><td>{ocorr_atualizada.get('motorista', '-')}</td></tr>
                    <tr><th>Tipo</th><td>{ocorr_atualizada.get('tipo_de_ocorrencia', '-')}</td></tr>
                    <tr><th>Data/Hora Abertura</th><td>{data_abertura_email}</td></tr>
                    <tr><th>Data/Hora Finalização</th><td>{data_finalizacao_email}</td></tr>
                    <tr><th>Permanência</th><td>{ocorr_atualizada.get('permanencia_manual', '-')}</td></tr>
                    {imagem_html}
                </table>
                <p><strong>Complemento:</strong> {ocorr_atualizada.get('complementar', 'Sem complemento.')}</p>
                <p>Atenciosamente,<br>Equipe de Monitoramento ClikLog Transportes</p>
            </body>
            </html>
            """

            assunto = f"Notificação: Ocorrência Finalizada - {cliente} - NF {ocorr_atualizada.get('nota_fiscal', '-')}"
            sucesso, mensagem = enviar_email(email_principal, email_copia, assunto, corpo_html)
            
            if sucesso:
                supabase.table("ocorrencias").update({"email_finalizacao_enviado": True}).eq("id", ocorr_atualizada["id"]).execute()
                supabase.table("emails_enviados").insert({
                    "data_hora": obter_data_hora_atual_brasil().isoformat(),
                    "tipo": "Finalização",
                    "cliente": cliente,
                    "email": email_principal, 
                    "ticket": ticket_formatado,
                    "nota_fiscal": ocorr_atualizada.get('nota_fiscal', '-'),
                    "status": "Enviado"
                }).execute()
                return True, "E-mail de finalização enviado com sucesso"
            else:
                return False, mensagem
        else:
            return False, "Cliente não possui e-mail cadastrado"
    except Exception as e:
        return False, f"Erro ao enviar e-mail de finalização: {e}"

def registrar_envio_email_com_provedor(ocorrencia, tipo_email, provedor_usado, sucesso):
    try:
        supabase.table("emails_enviados").insert({
            "data_hora": obter_data_hora_atual_brasil().isoformat(),
            "tipo": tipo_email,
            "cliente": ocorrencia.get('cliente', '-'),
            "email": ocorrencia.get('email_destinatario', '-'),
            "ticket": ocorrencia.get('numero_ticket', '-'),
            "nota_fiscal": ocorrencia.get('nota_fiscal', '-'),
            "status": "Enviado" if sucesso else "Falhou",
            "provedor": provedor_usado
        }).execute()
    except Exception as e:
        print(f"Erro ao registrar envio: {e}")

def testar_conexao_smtp():
    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
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

# ====================================================================
# 7. FUNÇÕES AUXILIARES DE EXIBIÇÃO (UI/HTML)
# ====================================================================

def classificar_ocorrencia_por_tempo(data_str, hora_str):
    try:
        data_hora = criar_datetime_manual(data_str, hora_str)
        if not data_hora: return "Erro", "gray"
        
        agora = obter_data_hora_atual_brasil()
        diferenca = calcular_diferenca_tempo(data_hora, agora)
        
        # Converte a diferença total para horas
        total_horas = diferenca.total_seconds() / 3600
        
        # 🟢 NOVA LÓGICA DINÂMICA (12h+, 24h+, 36h+, 48h+...)
        if total_horas >= 12:
            # Calcula em qual "ciclo de 12 horas" o ticket está
            multiplo_12 = int(total_horas // 12) * 12
            return f"🚨 ALERTA {multiplo_12}H+", "#A80303" # Fundo Vermelho Escuro
            
        elif diferenca <= timedelta(minutes=15): return "Até 15min", "#2ecc71"  
        elif diferenca <= timedelta(minutes=30): return "15-30min", "#f39c12" 
        elif diferenca <= timedelta(minutes=45): return "30-45min", "#e344c8" 
        elif diferenca <= timedelta(minutes=90): return "45-90min", "#750080" 
        else: return "Acima de 90min", "#882068"  
    except Exception:
        return "Erro", "gray"

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

@st.cache_data(ttl=420)     
def carregar_ocorrencias_finalizadas(data_inicio_str, data_fim_str):
    """Carrega as ocorrências finalizadas filtrando pelo período diretamente no banco de dados."""
    try:
        cols = "id, numero_ticket, nota_fiscal, cliente, focal, destinatario, cidade, motorista, tipo_de_ocorrencia, observacoes, responsavel, status, data_abertura_manual, hora_abertura_manual, alerta_1_enviado, alerta_2_enviado, alerta_3_enviado, alerta_4_enviado, alerta_5_enviado, imagem_url, data_hora_finalizacao, finalizado_por, complementar, permanencia_manual, data_finalizacao_manual, hora_finalizacao_manual, email_finalizacao_enviado, observacao_final, numero_manifesto, imagem_finalizacao_url"
        
        # Cria a query base filtrando o status e o range de datas
        query = supabase.table("ocorrencias").select(cols).eq("status", "Finalizada")
        query = query.gte("data_hora_finalizacao", data_inicio_str).lte("data_hora_finalizacao", data_fim_str)
        
        # Aplica o filtro de unidade se não for admin
        if not st.session_state.is_admin:
            dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", st.session_state.username).execute().data
            unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else None
            query = query.eq("ticket_unidade", unidade_usuario)
            
        response = query.order("data_hora_finalizacao", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Erro ao carregar ocorrências finalizadas: {e}")
        return []



# ====================================================================
# 8. INTERFACE DE LOGIN (Fluxo inicial do aplicativo)
# ====================================================================

def login():

    login_cookie = cookies.get("login")
    username_cookie = cookies.get("username")
    is_admin_cookie = cookies.get("is_admin")
    expiry_time_cookie = cookies.get("expiry_time")
    classe_cookie = cookies.get("classe")

    if login_cookie and username_cookie and not is_cookie_expired(expiry_time_cookie):
        st.session_state.login = True
        st.session_state.username = username_cookie
        st.session_state.is_admin = is_admin_cookie == "True"
        st.session_state.classe = classe_cookie
        return


    # IMAGENS
    URL_LOGO_IMAGEM = "https://vismjxhlsctehpvgmata.supabase.co/storage/v1/object/public/assets/logo_icon.png"
    URL_LOGO_FRASE = "https://vismjxhlsctehpvgmata.supabase.co/storage/v1/object/public/assets/logo_text.png"
    URL_ESTRADA = "https://vismjxhlsctehpvgmata.supabase.co/storage/v1/object/public/assets/road_bg.png"


    st.markdown(
    f"""
    <style>

    [data-testid="stHeader"] {{display:none}}
    [data-testid="stToolbar"] {{display:none}}

    .block-container {{
        padding-top:0rem;
        max-width:100%;
    }}

    /* REMOVE O BLOCO FANTASMA DO STREAMLIT */
    [data-testid="stVerticalBlock"] > div:first-child {{
        display:none;
    }}

    [data-testid="stAppViewContainer"] {{
        background-image:url('{URL_ESTRADA}');
        background-size:cover;
        background-position:center;
    }}

    /* CARD LOGIN */

    .login-card {{

        background:rgba(25,25,25,0.72);
        backdrop-filter:blur(12px);

        padding:40px;
        border-radius:20px;

        border:1px solid rgba(255,255,255,0.08);

        box-shadow:
            0 15px 40px rgba(0,0,0,0.6),
            0 0 0 1px rgba(200,212,64,0.05);

        color:white;
    }}

    .logo-container {{
        text-align:center;
        margin-bottom:25px;
    }}

    .logo-container img {{
        display:block;
        margin:auto;
    }}

    /* INPUT */

    .stTextInput input {{
        background:#2a2a2a !important;
        color:white !important;
        border-radius:8px;
        border:1px solid #444;
        padding:12px;
    }}

    .stTextInput label {{
        color:#c8d440 !important;
        font-weight:700;
        font-size:13px;
    }}

    /* BOTÃO */

    .stButton button {{
        width:100%;
        background:#c8d440;
        color:black;
        font-weight:800;
        border-radius:8px;
        border:none;
        padding:12px;
        margin-top:10px;
    }}

    .stButton button:hover {{
        background:#d8ea3a;
    }}

    /* DIVISOR */

    .divider {{
        text-align:center;
        margin:20px 0;
        opacity:0.6;
        font-size:12px;
    }}

    /* GOOGLE */

    .google-btn {{
        border:1px solid #555;
        padding:10px;
        border-radius:8px;
        text-align:center;
        font-weight:600;
        cursor:pointer;
    }}

    .google-btn:hover {{
        background:#2c2c2c;
    }}

    .bottom-link {{
        text-align:center;
        margin-top:20px;
        font-size:13px;
    }}

    .bottom-link a {{
        color:#c8d440;
        text-decoration:none;
        font-weight:700;
    }}

    </style>
    """,
    unsafe_allow_html=True
)


    # COLUNAS LATERAIS
    col1, col2, col3 = st.columns([1.2,1,1.2])


    with col2:

        st.markdown('<div class="login-card">', unsafe_allow_html=True)

        st.markdown(
            f"""
            <div class="logo-container">
                <img src="{URL_LOGO_IMAGEM}" width="70">
                <img src="{URL_LOGO_FRASE}" width="260">
            </div>
            """,
            unsafe_allow_html=True
        )

        nome = st.text_input(
            "Login",
            key="login_username",
            placeholder="Digite seu Usuário"
        )

        senha = st.text_input(
            "Senha",
            type="password",
            key="login_password",
            placeholder="Digite sua senha"
        )

        colA, colB = st.columns([0.5,0.5])

        with colA:
            lembrar = st.checkbox("Lembrar-me")

        with colB:
            st.markdown(
                '<div style="text-align:right;font-size:13px;"><a href="#" style="color:#c8d440">Esqueci a senha</a></div>',
                unsafe_allow_html=True
            )


        if st.button("ENTRAR"):

            with st.spinner("Autenticando..."):

                usuario = autenticar_usuario(nome, senha)

                if usuario:

                    cookies["login"] = "True"
                    cookies["username"] = usuario["nome_usuario"]
                    cookies["is_admin"] = str(usuario.get("is_admin", False))
                    cookies["classe"] = usuario.get("classe", "colaborador")

                    expiry = datetime.now(timezone.utc) + timedelta(hours=24)
                    cookies["expiry_time"] = expiry.strftime("%Y-%m-%d %H:%M:%S")

                    st.session_state.login = True
                    st.session_state.username = usuario["nome_usuario"]
                    st.session_state.is_admin = usuario.get("is_admin", False)
                    st.session_state.classe = usuario.get("classe", "colaborador")

                    st.rerun()

                else:
                    st.error("Usuário ou senha incorretos")


        st.markdown('<div class="divider">OU</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="google-btn">G  Continuar com Google</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="bottom-link">Não tem conta? <a href="#">Cadastre-se aqui</a></div>',
            unsafe_allow_html=True
        )

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()
# ====================================================================
# 9. INICIALIZAÇÃO DO ESTADO DA SESSÃO (st.session_state)
# ====================================================================

login()

if "login" not in st.session_state: st.session_state.login = False
if "username" not in st.session_state: st.session_state.username = None
if "is_admin" not in st.session_state: st.session_state.is_admin = False 
if "classe" not in st.session_state: st.session_state.classe = "colaborador" 
if "unidade_usuario" not in st.session_state: st.session_state.unidade_usuario = "N/A" 
if "ocorrencias_abertas" not in st.session_state: st.session_state.ocorrencias_abertas = []
if "ocorrencias_finalizadas" not in st.session_state: st.session_state.ocorrencias_finalizadas = []

# ====================================================================
# 10. LÓGICA PRINCIPAL DO APLICATIVO (APÓS LOGIN)
# ====================================================================

if st.session_state.get("login", False):
    
    col_welcome_text, col_logout_button = st.columns([5, 0.5])
    with col_welcome_text:
        st.markdown(f"👋 **Bem-vindo, {st.session_state.get('username','Usuário')}!**")

    with col_logout_button:
        if st.button("🚪 Sair"):
            for key in ["login", "username", "is_admin", "expiry_time", "classe"]: 
                cookies[key] = ""
            st.session_state.login = False
            st.rerun()

    st.markdown("---")  

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

    current_user_abas_map = abas_admin if st.session_state.is_admin else abas_usuario

    if "aba_ativa" not in st.session_state:
        st.session_state.aba_ativa = "aba1"  

    try:
        current_tab_name = next(key for key, value in current_user_abas_map.items() if value == st.session_state.aba_ativa)
        initial_index = list(current_user_abas_map.keys()).index(current_tab_name)
    except (StopIteration, ValueError):
        initial_index = 0 

    aba_nome = st.sidebar.radio("📁 Menu", list(current_user_abas_map.keys()), key="menu_abas", index=initial_index)

    st.session_state.aba_ativa = current_user_abas_map[aba_nome]

    # ====================================================================
    # 🟢 SISTEMA DE COBRANÇA "CHATO" (POP-UP A CADA 1 HORA PARA TICKETS > 12H)
    # ====================================================================
    # ====================================================================
    # 🟢 SISTEMA DE COBRANÇA "CHATO" (POP-UP A CADA 1 HORA PARA TICKETS > 12H)
    # ====================================================================
    if "ocorrencias_abertas" not in st.session_state:
        st.session_state.ocorrencias_abertas = carregar_ocorrencias_abertas()
        
    tickets_estourados = []
    agora_brasil = obter_data_hora_atual_brasil()
    
    for ocorr in st.session_state.get("ocorrencias_abertas", []):
        # Usuário comum é cobrado apenas pelos seus; Admin é cobrado por todos
        if st.session_state.is_admin or ocorr.get("responsavel") == st.session_state.username:
            d_str = ocorr.get("data_abertura_manual")
            h_str = ocorr.get("hora_abertura_manual")
            if d_str and h_str:
                dt_ab = criar_datetime_manual(d_str, h_str)
                if dt_ab and (agora_brasil - dt_ab) >= timedelta(hours=12):
                    tickets_estourados.append(str(ocorr.get("numero_ticket", "-"))[-5:])

    # Criação do Modal
    @st.dialog("🚨 ATENÇÃO: Tickets Críticos (+12h)")
    def dialog_alerta_12h(tickets):
        st.error("Os seguintes tickets estão abertos há **mais de 12 horas** e precisam ser finalizados imediatamente:", icon="🚨")
        for t in tickets:
            st.markdown(f"- **Ticket #{t}**")
        st.markdown("---")
        st.markdown("Por favor, resolva essas pendências para mantermos nosso SLA.")
        if st.button("Estou ciente", use_container_width=True):
            st.rerun()

    # 🟢 PREPARA O ALERTA (mas só vai disparar no final do código)
    disparar_alerta_agora = False
    if tickets_estourados:
        ultima_exibicao = st.session_state.get("ultima_exibicao_alerta_12h")
        if not ultima_exibicao or (datetime.now() - ultima_exibicao) >= timedelta(hours=1):
            disparar_alerta_agora = True
   
    # =========================
    #     ABA 1 - NOVA OCORRENCIA
    # =========================
    if st.session_state.aba_ativa == "aba1":
        st.header("Nova Ocorrência")
        
        # 🟢 CONTROLADOR DE IDENTIDADE DO FORMULÁRIO (A Mágica do Reset)
        if "form_id" not in st.session_state:
            st.session_state.form_id = 0

        # --- Modal flutuante para erros ---
        @st.dialog("⚠️ Atenção: Erros na Abertura")
        def exibir_erros_aba1(erros_lista):
            st.markdown("Por favor, corrija os itens abaixo antes de abrir o ticket:")
            for erro in erros_lista:
                st.error(erro, icon="❌")
            if st.button("Voltar e Corrigir", use_container_width=True):
                st.rerun()

        # 🟢 UM ÚNICO FORMULÁRIO, USANDO A CHAVE DINÂMICA
        with st.form(key=f"form_nova_ocorr_{st.session_state.form_id}", clear_on_submit=False):
            col1, col2 = st.columns(2)

            with col1:
                nf = st.text_input("Nota Fiscal*")
                nf_invalida = nf != "" and not nf.isdigit()
                
                destinatario = st.text_input("Destinatário*")

                cliente_opcao = st.selectbox("Cliente*", options=clientes + ["Outro ()"], index=None)
                cliente = st.text_input("Digite o nome do cliente*") if cliente_opcao == "Outro ()" else cliente_opcao

                # Verifica o focal do cliente
                focal_responsavel = ""
                if cliente_opcao and cliente_opcao in cliente_to_focal:
                    focal_responsavel = cliente_to_focal[cliente_opcao]

                cidade_opcao = st.selectbox("Cidade*", options=cidades + ["Outro (digitar manualmente)"], index=None)
                cidade = st.text_input("Digite o nome da cidade*") if cidade_opcao == "Outro (digitar manualmente)" else cidade_opcao

                imagem = st.file_uploader("📎 Anexar imagem*", type=["png", "jpg", "jpeg"])

            with col2:
                opcoes_motoristas = motoristas + ["Outro (digitar manualmente)"]
                motorista_opcao = st.selectbox("Motorista*", options=opcoes_motoristas, index=None)
                motorista = st.text_input("Digite o nome do motorista*") if motorista_opcao == "Outro (digitar manualmente)" else motorista_opcao

                tipo = st.multiselect(
                    "Tipo de Ocorrência*",
                    options=["Chegada no Local", "Pedido Bloqueado", "Aguardando Descarga", "Divergência"]
                )

                obs = st.text_area("Observações")
                responsavel = st.session_state.username
                st.text_input("Quem está abrindo o ticket", value=responsavel, disabled=True)

                dados_usuario = supabase.table("usuarios").select("unidade").eq("nome_usuario", responsavel).execute().data
                unidade_usuario = dados_usuario[0]["unidade"] if dados_usuario else "N/A"
                st.text_input("Unidade", value=unidade_usuario, disabled=True)

                # 🟢 CORREÇÃO: "Congelando" a data e hora iniciais para não atualizarem sozinhas
                chave_data = f"data_ab_{st.session_state.form_id}"
                chave_hora = f"hora_ab_{st.session_state.form_id}"
                
                if chave_data not in st.session_state:
                    st.session_state[chave_data] = obter_data_hora_atual_brasil().date()
                    st.session_state[chave_hora] = obter_data_hora_atual_brasil().time()

                col_data, col_hora = st.columns(2)
                with col_data:
                    data_abertura_manual = st.date_input("Data de Abertura*", key=chave_data, format="DD/MM/YYYY")
                with col_hora:
                    hora_abertura_manual = st.time_input("Hora de Abertura*", key=chave_hora)

            enviar = st.form_submit_button("Adicionar Ocorrência", use_container_width=True)

        # 🟢 LÓGICA DE SALVAMENTO AO CLICAR EM ENVIAR
        if enviar:
            erros_abertura = []
            
            campos_obrigatorios = {
                "Nota Fiscal": nf, "Cliente": cliente, "Destinatário": destinatario, 
                "Cidade": cidade, "Motorista": motorista, "Tipo de Ocorrência": tipo
            }
            faltando = [campo for campo, valor in campos_obrigatorios.items() if not valor]

            if nf_invalida:
                erros_abertura.append("A Nota Fiscal deve conter apenas números.")
            if faltando:
                erros_abertura.append(f"Preencha todos os campos obrigatórios: {', '.join(faltando)}")
            if not imagem:
                erros_abertura.append("Anexo de imagem é obrigatório para abertura de Ticket.")

            if erros_abertura:
                exibir_erros_aba1(erros_abertura)
            else:
                with st.spinner("Salvando no banco de dados..."):
                    numero_ticket = obter_data_hora_atual_brasil().strftime("%Y%m%d%H%M%S%f")
                    data_abertura_manual_str = data_abertura_manual.strftime("%Y-%m-%d")
                    hora_abertura_manual_str = hora_abertura_manual.strftime("%H:%M:%S")

                    nova_ocorrencia = {
                        "id": str(uuid.uuid4()),
                        "numero_ticket": numero_ticket, "nota_fiscal": nf, "cliente": cliente,
                        "focal": focal_responsavel, "destinatario": destinatario,
                        "cidade": cidade, "motorista": motorista, "tipo_de_ocorrencia": ", ".join(tipo),
                        "observacoes": obs, "responsavel": responsavel,
                        "data_abertura_manual": data_abertura_manual_str, "hora_abertura_manual": hora_abertura_manual_str,
                        "ticket_unidade": unidade_usuario, "complementar": "", "permanencia": "", "imagem_url": "",
                    }

                    # Faz o upload da imagem
                    if imagem:
                        try:
                            nome_arquivo = f"{nova_ocorrencia['id']}_{limpar_nome_arquivo(imagem.name)}"
                            supabase.storage.from_("imagem-ticket").upload(
                                nome_arquivo, imagem.read(), file_options={"content-type": imagem.type}
                            )
                            nova_ocorrencia["imagem_url"] = supabase.storage.from_("imagem-ticket").get_public_url(nome_arquivo)
                        except Exception as e:
                            st.warning(f"⚠️ Falha ao enviar imagem: {e}")
                    
                    # Insere no Supabase
                    response = inserir_ocorrencia_supabase(nova_ocorrencia)

                if response and response.data:
                    # Limpa o cache da lista de ocorrências
                    carregar_ocorrencias_abertas.clear()
                    
                    # 🟢 O PULO DO GATO: Somamos 1 ao ID do formulário. Isso joga o form velho fora e cria um limpo com a hora resetada!
                    st.session_state.form_id += 1
                    
                    st.toast("✅ Ocorrência aberta com sucesso!", icon="🚀")
                    tm.sleep(0.5) 
                    st.rerun()
                else:
                    st.error("❌ Erro ao salvar a ocorrência no banco de dados. Tente novamente.")
    # =========================
    #     ABA 2 - EM ABERTO 
    # =========================
    if st.session_state.aba_ativa == "aba2":
        
        @st.dialog(" Finalizar Ocorrência")
        def dialog_finalizar_ocorrencia(ocorr):
            st.markdown(f"**Ticket #:** {str(ocorr.get('numero_ticket', '-'))[-5:]} | **Cliente:** {ocorr.get('cliente', '-')}")
            
            with st.form(f"form_fin_ocorr_{ocorr['id']}"):
                
                complemento = st.text_input("Complementar*")
                
                col_m, col_o = st.columns(2)
                with col_m: numero_manifesto = st.text_input("N° Manifesto")
                with col_o: observacao_final = st.text_input("Obs Final")

                st.markdown("##### ⏱️ Data e Hora")
                chave_data = f"data_final_{ocorr['id']}"
                chave_hora = f"hora_final_{ocorr['id']}"

                if chave_data not in st.session_state or not isinstance(st.session_state[chave_data], date):
                    st.session_state[chave_data] = obter_data_hora_atual_brasil().date()
                if chave_hora not in st.session_state or not isinstance(st.session_state[chave_hora], time):
                    st.session_state[chave_hora] = obter_data_hora_atual_brasil().time()

                col_data, col_hora = st.columns(2)
                with col_data: st.date_input("Data Final", key=chave_data, format="DD/MM/YYYY")
                with col_hora: st.time_input("Hora Final", key=chave_hora)

                imagem_finalizacao = st.file_uploader("📎 Anexar img finalização", type=["png", "jpg", "jpeg"])

                if st.form_submit_button("Concluir Finalização"):
                    if not complemento.strip():
                        st.warning("O campo Complementar é obrigatório.")
                    else:
                        st.toast("Finalizando...")
                        imagem_url_fin = ""
                        if imagem_finalizacao:
                            try:
                                nome_arquivo = f"{ocorr['id']}_final_{limpar_nome_arquivo(imagem_finalizacao.name)}"
                                supabase.storage.from_("imagens-finalizacao").upload(
                                    nome_arquivo, imagem_finalizacao.read(), file_options={"content-type": imagem_finalizacao.type}
                                )
                                imagem_url_fin = supabase.storage.from_("imagens-finalizacao").get_public_url(nome_arquivo)
                            except: pass

                        sucesso, mensagem = finalizar_ocorrencia(
                            ocorr, complemento, st.session_state[chave_data], st.session_state[chave_hora],
                            imagem_url_fin, observacao_final, numero_manifesto
                        )

                        if sucesso:
                            st.success("Ticket finalizado com sucesso!")
                            carregar_ocorrencias_abertas.clear()
                            tm.sleep(1)
                            st.rerun()
                        else: 
                            st.error(mensagem)

        @st.dialog("✏️ Editar Ocorrência")
        def dialog_editar_ocorrencia(ocorr):
            st.markdown(f"**Ticket #:** {str(ocorr.get('numero_ticket', '-'))[-5:]}")
            
            with st.form(f"form_edit_ocorr_{ocorr['id']}"):
                c1, c2 = st.columns(2)
                
                with c1:
                    resp_original = ocorr.get('responsavel', '').split(" (Editado")[0]
                    st.text_input("Aberto por", value=resp_original, disabled=True)
                    
                    nova_nf = st.text_input("Nota Fiscal", value=ocorr.get("nota_fiscal", ""))
                    novo_dest = st.text_input("Destinatário", value=ocorr.get("destinatario", ""))
                    
                    cli_atual = ocorr.get("cliente", "")
                    idx_cli = clientes.index(cli_atual) if cli_atual in clientes else None
                    novo_cli = st.selectbox("Cliente", options=clientes, index=idx_cli)
                    
                    cid_atual = ocorr.get("cidade", "")
                    idx_cid = cidades.index(cid_atual) if cid_atual in cidades else None
                    nova_cid = st.selectbox("Cidade", options=cidades, index=idx_cid)
                    
                with c2:
                    mot_atual = ocorr.get("motorista", "")
                    idx_mot = motoristas.index(mot_atual) if mot_atual in motoristas else None
                    novo_mot = st.selectbox("Motorista", options=motoristas, index=idx_mot)
                    
                    opcoes_tipo = ["Chegada no Local", "Pedido Bloqueado", "Aguardando Descarga", "Divergência"]
                    tipos_atuais = [t.strip() for t in ocorr.get("tipo_de_ocorrencia", "").split(",")] if ocorr.get("tipo_de_ocorrencia") else []
                    tipos_validos = [t for t in tipos_atuais if t in opcoes_tipo]
                    novo_tipo = st.multiselect("Tipo de Ocorrência", options=opcoes_tipo, default=tipos_validos)
                    
                    nova_obs = st.text_area("Observações", value=ocorr.get("observacoes", ""))
                    
                col_data, col_hora = st.columns(2)
                try: dt_ab = datetime.strptime(ocorr.get("data_abertura_manual"), "%Y-%m-%d").date()
                except: dt_ab = obter_data_hora_atual_brasil().date()
                
                try: hr_ab = datetime.strptime(ocorr.get("hora_abertura_manual"), "%H:%M:%S").time()
                except: hr_ab = obter_data_hora_atual_brasil().time()
                
                with col_data: nova_data = st.date_input("Data de Abertura", value=dt_ab, format="DD/MM/YYYY")
                with col_hora: nova_hora = st.time_input("Hora de Abertura", value=hr_ab)
                
                if st.form_submit_button("Salvar Alterações"):
                    if not nova_nf.isdigit():
                        st.error("Nota Fiscal deve conter apenas números.")
                    elif not novo_cli:
                        st.error("Cliente é obrigatório.")
                    else:
                        novo_focal = cliente_to_focal.get(novo_cli, "")
                        
                        usuario_edit = st.session_state.username
                        novo_responsavel = f"{resp_original} (Editado por {usuario_edit})"
                        
                        dt_str = nova_data.strftime("%Y-%m-%d")
                        hr_str = nova_hora.strftime("%H:%M:%S")
                        
                        dados_up = {
                            "nota_fiscal": nova_nf, "destinatario": novo_dest, "cliente": novo_cli,
                            "focal": novo_focal, "cidade": nova_cid, "motorista": novo_mot,
                            "tipo_de_ocorrencia": ", ".join(novo_tipo), "observacoes": nova_obs,
                            "responsavel": novo_responsavel, "data_abertura_manual": dt_str,
                            "hora_abertura_manual": hr_str
                        }
                        
                        suc, msg = atualizar_ocorrencia_supabase(ocorr["id"], dados_up)
                        if suc:
                            st.success("Ticket atualizado com sucesso!")
                            carregar_ocorrencias_abertas.clear()
                            tm.sleep(1)
                            st.rerun()
                        else:
                            st.error(msg)

        count = st_autorefresh(interval=60 * 1000, key="refresh_painel_aba2")
        
        carregar_ocorrencias_abertas.clear()
        st.session_state.ocorrencias_abertas = carregar_ocorrencias_abertas()

        agora = datetime.now()
        if "ultima_verificacao_email" not in st.session_state:
            st.session_state.ultima_verificacao_email = agora - timedelta(minutes=8) 

        if agora - st.session_state.ultima_verificacao_email >= timedelta(minutes=7):
            print(f"📢 [Background] Verificando e-mails automáticos em {agora.strftime('%H:%M:%S')}...")
            
            try:
                resultados_notificacao = notificar_ocorrencias_abertas()
                
                total_enviados = sum(1 for res in resultados_notificacao if res["status"] == "sucesso")
                if total_enviados > 0: 
                    carregar_ocorrencias_abertas.clear()
                    st.session_state.ocorrencias_abertas = carregar_ocorrencias_abertas()
                    st.toast(f"✅ {total_enviados} alerta(s) de e-mail enviados em 2º plano.", icon="📧")
                
                st.session_state.ultima_verificacao_email = agora 
                
            except Exception as e:
                print(f"❌ Erro no background job: {e}")

        col_titulo, col_botao_atualizar = st.columns([5, 1]) 
        
        with col_botao_atualizar:
            if st.button("🔄 Atualizar Dados", key="btn_atualizar_abertas_aba2", use_container_width=True):
                st.rerun()

        titulo_placeholder = col_titulo.empty()

        if "ocorrencias_abertas" not in st.session_state:
            st.session_state.ocorrencias_abertas = carregar_ocorrencias_abertas()

        ocorrencias_abertas = st.session_state.get("ocorrencias_abertas", [])
        
        lista_focais = sorted(set((ocorr.get('focal') or 'Sem Focal').strip() for ocorr in ocorrencias_abertas), key=lambda x: str(x).lower())

        focal_selecionado = st.selectbox("🔎 Filtrar por Focal:", options=["Todos"] + lista_focais, index=0)

        if focal_selecionado != "Todos":
            ocorrencias_filtradas = [ocorr for ocorr in ocorrencias_abertas if (ocorr.get('focal') or 'Sem Focal').strip() == focal_selecionado]
        else:
            ocorrencias_filtradas = ocorrencias_abertas

        qtd_exibida = len(ocorrencias_filtradas)
        titulo_placeholder.header(f"Ocorrências em Aberto ({qtd_exibida})")

        if not ocorrencias_filtradas:
            st.info("ℹ️ Nenhuma ocorrência encontrada para este filtro.")
        else:
            num_colunas = 4
            
            # 🟢 INJEÇÃO DA ANIMAÇÃO NEON NO LOCAL CORRETO
            st.markdown("""
            <style>
            @keyframes pulse-neon-red {
                0% { 
                    box-shadow: 0 0 5px rgba(168, 3, 3, 0.2); 
                    border-color: #2a2a3d; 
                }
                50% { 
                    box-shadow: 0 0 20px rgba(255, 0, 0, 0.8), 0 0 35px rgba(255, 0, 0, 0.5), inset 0 0 10px rgba(255, 0, 0, 0.2); 
                    border-color: #ff4444; 
                }
                100% { 
                    box-shadow: 0 0 5px rgba(168, 3, 3, 0.2); 
                    border-color: #2a2a3d; 
                }
            }
            .neon-critico {
                animation: pulse-neon-red 1.5s infinite alternate ease-in-out !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
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
                            abertura_manual_formatada = dt_manual.strftime("%d/%m/%Y %H:%M")
                            status, cor = classificar_ocorrencia_por_tempo(data_abertura_manual, hora_abertura_manual)
                        else: status = "Erro"
                    except Exception as e: status = "Erro"

                with colunas[idx % num_colunas]:
                    safe_idx = f"{idx}_{ocorr.get('nota_fiscal', '')}"
                    imagem_abertura_url = ocorr.get('imagem_url', '') 
                    
                    ultimo_alerta = 0
                    email_foi_enviado = False
                    for i in range(1, 6):
                        if ocorr.get(f"alerta_{i}_enviado"):
                            ultimo_alerta = i
                            email_foi_enviado = True
                            
                    # --- ESTILO PREMIUM / EXECUTIVO ---
                    bg_card = "linear-gradient(145deg, #1e1e2d, #151521)"
                    border_color = "#2a2a3d"
                    
                    # 🟢 LIGA O NEON INJETANDO DIRETO NO STYLE PARA O STREAMLIT NÃO BLOQUEAR
                    if "ALERTA" in status:
                        estilo_dinamico = "animation: pulse-neon-red 1.2s infinite alternate ease-in-out;"
                    else:
                        estilo_dinamico = f"border: 1px solid {border_color}; box-shadow: 0 8px 16px rgba(0,0,0,0.4);"
                    
                    if ultimo_alerta > 0:
                        alertas_html = f"<div style='background: linear-gradient(90deg, rgba(255,165,0,0.1) 0%, rgba(255,165,0,0.0) 100%); border-left: 3px solid orange; padding: 6px 10px; margin-bottom: 10px; border-radius: 4px; font-size: 0.85em;'>⚠️ <strong>Alertas:</strong> {ultimo_alerta} enviado(s)</div>"
                    else:
                        alertas_html = ""

                    link_abertura = f'<a href="{imagem_abertura_url}" target="_blank" style="text-decoration:none; color: #4facfe; font-size:0.85em; background:#4facfe20; padding:3px 10px; border-radius:12px;">📸 Ver Anexo</a>' if imagem_abertura_url else ''
                    
                    html_card = f"""
<div style='background: {bg_card}; border-top: 4px solid {cor}; padding:15px; border-radius:12px; color:#e2e2e2; margin-bottom:15px; height:520px; overflow-y:auto; font-family: "Segoe UI", Tahoma, sans-serif; {estilo_dinamico}'>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;'>
<div style='font-size: 1.15em; font-weight: 600; color: #ffffff;'>Ticket #{str(ocorr.get('numero_ticket', 'N/A'))[-5:]}</div>
<div style='background-color: {cor}; color: #ffffff; padding: 3px 10px; border-radius: 20px; font-size: 0.75em; font-weight: bold;'>{status}</div>
</div>
{alertas_html}
<div style='margin-bottom: 12px;'>
<div style='color: #8e8e9e; font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.5px;'>Cliente / Destinatário</div>
<div style='font-size: 1em; font-weight: 500; color: #ffffff; margin-bottom: 2px;'>{seguro(ocorr.get('cliente', '-'))}</div>
<div style='font-size: 0.9em; color: #c0c0c0;'>{seguro(ocorr.get('destinatario', '-'))}</div>
</div>
<div style='display:flex; justify-content:space-between; margin-bottom: 12px; border-bottom: 1px solid {border_color}; padding-bottom: 12px;'>
<div>
<div style='color: #8e8e9e; font-size: 0.8em;'>Nota Fiscal</div>
<div style='font-weight: 500; color: #ffffff;'>{seguro(ocorr.get('nota_fiscal', '-'))}</div>
</div>
<div style='text-align: right;'>
<div style='color: #8e8e9e; font-size: 0.8em;'>Focal</div>
<div style='font-weight: 500; color: #ffffff;'>{seguro(ocorr.get('focal', '-'))}</div>
</div>
</div>
<div style='margin-bottom: 12px;'>
<div style='color: #8e8e9e; font-size: 0.8em;'>📍 Cidade</div>
<div style='font-size: 0.9em; margin-bottom: 6px;'>{seguro(ocorr.get('cidade', '-'))}</div>
<div style='color: #8e8e9e; font-size: 0.8em;'>🚚 Motorista</div>
<div style='font-size: 0.9em;'>{seguro(ocorr.get('motorista', '-'))}</div>
</div>
<div style='background: #252538; padding: 10px; border-radius: 8px; margin-bottom: 12px;'>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 5px;'>
<div style='font-size: 0.85em; color: #a0a0b0;'>⏱️ Abertura</div>
<div style='font-size: 0.85em; font-weight: 500; color:#fff;'>{abertura_manual_formatada}</div>
</div>
<div style='display:flex; justify-content:space-between; align-items:center;'>
<div style='font-size: 0.85em; color: #a0a0b0;'>👤 Resp.</div>
<div style='font-size: 0.85em; font-weight: 500; color:#fff;'>{seguro(ocorr.get('responsavel', '-')).split(' (')[0]}</div>
</div>
</div>
<div style='display:flex; justify-content:space-between; align-items:center;'>
<div style='font-size: 0.85em; color: #8e8e9e;'><strong>Tipo:</strong> {seguro(ocorr.get('tipo_de_ocorrencia', '-'))}</div>
<div>{link_abertura}</div>
</div>
<div style='margin-top: 10px; font-size: 0.85em; color: #a0a0b0;'>
<strong>Obs:</strong> {seguro(ocorr.get('observacoes', ''))}
</div>
</div>
"""
                    st.markdown(html_card, unsafe_allow_html=True)

                    c_btn1, c_btn2 = st.columns(2)
                    with c_btn1:
                        if st.button(" Finalizar", key=f"btn_fin_{safe_idx}", use_container_width=True):
                            dialog_finalizar_ocorrencia(ocorr)
                    with c_btn2:
                        if email_foi_enviado:
                            st.button("✏️ Editar", key=f"btn_edit_{safe_idx}", disabled=True, help="Bloqueado: O primeiro alerta já foi enviado.", use_container_width=True)
                        else:
                            if st.button("✏️ Editar", key=f"btn_edit_{safe_idx}", use_container_width=True):
                                dialog_editar_ocorrencia(ocorr)


    # =========================
    #    ABA 3 - FINALIZADAS 
    # =========================   
    if st.session_state.aba_ativa == "aba3":
        st.header("Ocorrências Finalizadas")
        
        # --- 🟢 Lógica do Calendário (Primeiro dia do mês até Hoje) ---
        hoje = obter_data_hora_atual_brasil().date()
        primeiro_dia_mes = hoje.replace(day=1)
        
        col_filtros, col_botao = st.columns([4, 1])
        with col_filtros:
            datas_selecionadas = st.date_input(
                "📅 Filtrar por Data de Finalização (Início - Fim):",
                value=(primeiro_dia_mes, hoje),
                max_value=hoje,
                format="DD/MM/YYYY"
            )
        
        with col_botao:
            st.write("") # Espaçamento
            st.write("")
            atualizar = st.button("🔄 Buscar Dados", use_container_width=True)

        # O st.date_input retorna uma tupla. Precisamos garantir que o usuário escolheu as duas datas.
        if isinstance(datas_selecionadas, tuple):
            if len(datas_selecionadas) == 2:
                data_inicio, data_fim = datas_selecionadas
            else:
                data_inicio = datas_selecionadas[0]
                data_fim = datas_selecionadas[0]
        else:
            data_inicio = datas_selecionadas
            data_fim = datas_selecionadas

        # Formata para o formato Timestamp do banco (Início do dia 00:00:00 e Fim do dia 23:59:59)
        data_inicio_str = data_inicio.strftime("%Y-%m-%d 00:00:00")
        data_fim_str = data_fim.strftime("%Y-%m-%d 23:59:59")

        if atualizar:
            carregar_ocorrencias_finalizadas.clear()

        # Busca no banco APENAS os dados do período selecionado
        with st.spinner("Buscando registros no banco de dados..."):
            ocorrencias_finalizadas = carregar_ocorrencias_finalizadas(data_inicio_str, data_fim_str)

        filtro_nf = "" # 🟢 Define a variável antes para o Pylance não reclamar

        if not ocorrencias_finalizadas:
            st.info(f"ℹ️ Nenhuma ocorrência finalizada encontrada no período de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}.")
        else:
            col1, col2 = st.columns([1, 2])
            with col1:
                filtro_nf = st.text_input("🔎 Pesquisar por NF neste período:", "", max_chars=10)
            with col2:
                if st.button("📤 Exportar Excel"):
                    try:
                        df = pd.DataFrame(ocorrencias_finalizadas)
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df.to_excel(writer, index=False, sheet_name='Finalizadas')
                        st.download_button(
                            label=f"⬇️ Baixar Relatório Excel ({len(ocorrencias_finalizadas)} registros)",
                            data=output.getvalue(),
                            file_name=f"finalizadas_{data_inicio.strftime('%d%m%Y')}_a_{data_fim.strftime('%d%m%Y')}.xlsx",
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

            # --- 🟢 SOLUÇÃO PARA A TELA ROLAR LISO (PERFORMANCE DO DOM) ---
            LIMITE_CARDS = 60
            total_filtrado = len(ocorrencias_filtradas)
            
            if total_filtrado > LIMITE_CARDS:
                st.warning(f"⚠️ Encontradas {total_filtrado} ocorrências no período. Mostrando apenas as {LIMITE_CARDS} mais recentes para evitar travamentos. Exporte para Excel para ver todas.")
                ocorrencias_filtradas = ocorrencias_filtradas[:LIMITE_CARDS]
            else:
                st.success(f"Exibindo {total_filtrado} ocorrência(s).")
            
            num_colunas = 4
            for i in range(0, len(ocorrencias_filtradas), num_colunas):
                linha = ocorrencias_filtradas[i:i+num_colunas]
                colunas = st.columns(num_colunas)

                for idx, ocorr in enumerate(linha):
                    ocorr = auto_sanitizar_ocorrencia(ocorr)
                    
                    data_abertura_manual = hora_abertura_manual = "-"
                    try:
                        if ocorr.get("data_abertura_manual") and ocorr.get("hora_abertura_manual"):
                            abertura_dt = criar_datetime_manual(ocorr["data_abertura_manual"], ocorr["hora_abertura_manual"])
                            if abertura_dt:
                                data_abertura_manual = abertura_dt.strftime("%d/%m/%Y")
                                hora_abertura_manual = abertura_dt.strftime("%H:%M")
                    except: pass

                    data_finalizacao_manual = hora_finalizacao_manual = "-"
                    try:
                        if ocorr.get("data_finalizacao_manual") and ocorr.get("hora_finalizacao_manual"): 
                            finalizacao_dt = criar_datetime_manual(ocorr["data_finalizacao_manual"], ocorr["hora_finalizacao_manual"])
                            if finalizacao_dt:
                                data_finalizacao_manual = finalizacao_dt.strftime("%d/%m/%Y")
                                hora_finalizacao_manual = finalizacao_dt.strftime("%H:%M")
                    except: pass

                    with colunas[idx]:
                        try:
                            # 🟢 Exibir Apenas o Último Alerta Enviado
                            ultimo_alerta = 0
                            for num_alerta in range(1, 6):
                                if ocorr.get(f'alerta_{num_alerta}_enviado'):
                                    ultimo_alerta = num_alerta
                            # --- ESTILO PREMIUM / EXECUTIVO PARA FINALIZADOS ---
                            bg_card = "linear-gradient(145deg, #1e1e2d, #151521)"
                            border_color = "#2a2a3d"
                            
                            if ultimo_alerta > 0:
                                alertas_html = f"<div style='background: linear-gradient(90deg, rgba(255,165,0,0.1) 0%, rgba(255,165,0,0.0) 100%); border-left: 3px solid orange; padding: 4px 8px; margin-bottom: 6px; border-radius: 4px; font-size: 0.8em;'>⚠️ <strong>Alertas:</strong> {ultimo_alerta} enviado(s)</div>"
                            else:
                                alertas_html = ""

                            if ocorr.get('email_finalizacao_enviado', False):
                                email_fin_html = f"<div style='background: linear-gradient(90deg, rgba(46,204,113,0.1) 0%, rgba(46,204,113,0.0) 100%); border-left: 3px solid #2ecc71; padding: 4px 8px; margin-bottom: 10px; border-radius: 4px; font-size: 0.8em;'>✅ <strong>Notificação:</strong> Finalização enviada</div>"
                            else:
                                email_fin_html = ""

                            imagem_abertura_url = html.escape(str(ocorr.get("imagem_url", "")), quote=True)
                            imagem_finalizacao_url = html.escape(str(ocorr.get("imagem_finalizacao_url", "")), quote=True)

                            link_abertura = f'<a href="{imagem_abertura_url}" target="_blank" style="text-decoration:none; color: #4facfe; font-size:0.8em; background:#4facfe20; padding:2px 8px; border-radius:12px; margin-right:5px;">📸 Abertura</a>' if imagem_abertura_url else ''
                            link_fin = f'<a href="{imagem_finalizacao_url}" target="_blank" style="text-decoration:none; color: #2ecc71; font-size:0.8em; background:#2ecc7120; padding:2px 8px; border-radius:12px;">📸 Final</a>' if imagem_finalizacao_url else ''

                            html_card = f"""
<div style='background: {bg_card}; border: 1px solid {border_color}; border-top: 4px solid {seguro(ocorr.get('Cor', 'gray'))}; padding:15px; border-radius:12px; color:#e2e2e2; box-shadow: 0 8px 16px rgba(0,0,0,0.4); margin-bottom:15px; height:530px; overflow-y:auto; font-family: "Segoe UI", Tahoma, sans-serif;'>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;'>
<div style='font-size: 1.1em; font-weight: 600; color: #ffffff;'>Ticket #{str(ocorr.get('numero_ticket', '-'))[-5:]}</div>
<div style='background-color: {seguro(ocorr.get('Cor', 'gray'))}20; border: 1px solid {seguro(ocorr.get('Cor', 'gray'))}50; color: {seguro(ocorr.get('Cor', 'gray'))}; padding: 3px 8px; border-radius: 20px; font-size: 0.7em; font-weight: bold;'>FINALIZADO</div>
</div>
{alertas_html}
{email_fin_html}
<div style='margin-bottom: 8px;'>
<div style='color: #8e8e9e; font-size: 0.75em; text-transform: uppercase;'>Cliente / Destinatário</div>
<div style='font-size: 0.95em; font-weight: 500; color: #ffffff;'>{seguro(ocorr.get('cliente', '-'))}</div>
<div style='font-size: 0.85em; color: #c0c0c0;'>{seguro(ocorr.get('destinatario', '-'))}</div>
</div>
<div style='display:flex; justify-content:space-between; margin-bottom: 8px; border-bottom: 1px solid {border_color}; padding-bottom: 8px;'>
<div>
<div style='color: #8e8e9e; font-size: 0.75em;'>Nota Fiscal</div>
<div style='font-weight: 500; font-size: 0.9em; color: #ffffff;'>{seguro(ocorr.get('nota_fiscal', '-'))}</div>
</div>
<div style='text-align: right;'>
<div style='color: #8e8e9e; font-size: 0.75em;'>Focal</div>
<div style='font-weight: 500; font-size: 0.9em; color: #ffffff;'>{seguro(ocorr.get('focal', '-'))}</div>
</div>
</div>
<div style='background: #252538; padding: 10px; border-radius: 8px; margin-bottom: 10px;'>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;'>
<div style='font-size: 0.8em; color: #a0a0b0;'>⏱️ Abertura</div>
<div style='font-size: 0.8em; color:#fff;'>{data_abertura_manual} {hora_abertura_manual}</div>
</div>
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom: 4px;'>
<div style='font-size: 0.8em; color: #a0a0b0;'>🏁 Fim</div>
<div style='font-size: 0.8em; color:#fff;'>{data_finalizacao_manual} {hora_finalizacao_manual}</div>
</div>
<div style='display:flex; justify-content:space-between; align-items:center; margin-top: 6px; padding-top: 6px; border-top: 1px dashed #444;'>
<div style='font-size: 0.8em; color: #a0a0b0;'>⏳ Permanência</div>
<div style='font-size: 0.85em; font-weight: bold; color:#f39c12;'>{seguro(ocorr.get('permanencia_manual', '-'))}</div>
</div>
</div>
<div style='display:flex; justify-content:space-between; margin-bottom: 8px;'>
<div style='font-size: 0.8em; color: #8e8e9e;'><strong>Resp:</strong> {seguro(ocorr.get('responsavel', '-')).split(' (')[0]}</div>
<div style='font-size: 0.8em; color: #8e8e9e;'><strong>Fin:</strong> {seguro(ocorr.get('finalizado_por', '-'))}</div>
</div>
<div style='margin-bottom: 10px;'>{link_abertura}{link_fin}</div>
<div style='font-size: 0.8em; color: #a0a0b0;'>
<strong>Comp:</strong> {seguro(ocorr.get('complementar', '-'))}
</div>
</div>
"""
                            st.markdown(html_card, unsafe_allow_html=True)

                        except Exception as e:
                            st.warning(f"⚠️ Erro ao montar card de ocorrência: Ticket {ocorr.get('numero_ticket')} — {e}")

    # =========================
    #     ABA 4 - CONFIGURAÇÕES
    # =========================
    if st.session_state.aba_ativa == "aba4":
        st.header("Configurações")
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
                        usuario = st.session_state.username
                        response = supabase.table("usuarios").select("*").eq("nome_usuario", usuario).execute()
                        
                        if response.data:
                            usuario_data = response.data[0]
                            if verificar_senha(senha_atual, usuario_data["senha_hash"]):
                                nova_senha_hash = hash_senha(nova_senha)
                                update_response = supabase.table("usuarios").update({
                                    "senha_hash": nova_senha_hash
                                }).eq("nome_usuario", usuario).execute()
                                
                                if update_response.data: st.success("✅ Senha alterada com sucesso!")
                                else: st.error("❌ Erro ao atualizar senha.")
                            else: st.error("❌ Senha atual incorreta.")
                        else: st.error("❌ Usuário não encontrado.")
                    except Exception as e: st.error(f"❌ Erro ao alterar senha: {e}")
        
        if st.session_state.is_admin:
            st.subheader("Administração de Usuários")
            admin_tab1, admin_tab2, admin_tab3 = st.tabs(["Listar Usuários", "Adicionar Usuário", "Editar/Excluir Usuário"])
            
            with admin_tab1:
                try:
                    response = supabase.table("usuarios").select("*").execute()
                    if response.data:
                        usuarios = response.data
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
                    else: st.info("Nenhum usuário encontrado.")
                except Exception as e: st.error(f"Erro ao listar usuários: {e}")
            
            with admin_tab2:
                with st.form("form_adicionar_usuario"):
                    novo_usuario = st.text_input("Nome de Usuário")
                    nova_senha_usuario = st.text_input("Senha", type="password")
                    confirmar_senha_usuario = st.text_input("Confirmar Senha", type="password")
                    is_admin = st.checkbox("Usuário Administrador")

                    if st.session_state.is_admin: 
                        unidade_novo_usuario = st.selectbox("Unidade", lista_filiais)
                    else:
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
                                check_response = supabase.table("usuarios").select("*").eq("nome_usuario", novo_usuario).execute()
                                if check_response.data: st.error("❌ Nome de usuário já existe.")
                                else:
                                    senha_hash = hash_senha(nova_senha_usuario)
                                    insert_response = supabase.table("usuarios").insert({
                                        "nome_usuario": novo_usuario, "senha_hash": senha_hash,
                                        "is_admin": is_admin, "unidade": unidade_novo_usuario,
                                        "criado_em": obter_data_hora_atual_brasil().isoformat()
                                    }).execute()

                                    if insert_response.data:
                                        st.success("✅ Usuário adicionado com sucesso!")
                                        tm.sleep(1.5)
                                    else: st.error("❌ Erro ao adicionar usuário.")
                            except Exception as e: st.error(f"❌ Erro ao adicionar usuário: {e}")
            
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
                                    
                                    # --- 🟢 NOVO: Permite editar a filial puxando da tabela dinâmica ---
                                    unidade_atual = usuario_data.get("unidade", "")
                                    # Descobre a posição da unidade atual na lista (ou deixa 0 se não achar)
                                    idx_unidade = lista_filiais.index(unidade_atual) if unidade_atual in lista_filiais else 0
                                    
                                    if st.session_state.is_admin:
                                        nova_unidade_edit = st.selectbox("Unidade", options=lista_filiais, index=idx_unidade)
                                    else:
                                        nova_unidade_edit = unidade_atual
                                        st.text_input("Unidade", value=nova_unidade_edit, disabled=True)
                                    # -------------------------------------------------------------------

                                    col1, col2 = st.columns(2)
                                    with col1: editar_usuario = st.form_submit_button("Atualizar Usuário")
                                    with col2: excluir_usuario = st.form_submit_button("Excluir Usuário", type="primary")
                                    
                                    if editar_usuario:
                                        try:
                                            # Inclui a nova unidade no pacote de atualização
                                            update_data = {
                                                "is_admin": is_admin_edit,
                                                "unidade": nova_unidade_edit
                                            }
                                            if nova_senha_admin: 
                                                update_data["senha_hash"] = hash_senha(nova_senha_admin)
                                                
                                            update_response = supabase.table("usuarios").update(update_data).eq("nome_usuario", usuario_selecionado).execute()
                                            
                                            if update_response.data: 
                                                st.success("✅ Usuário atualizado com sucesso!")
                                                tm.sleep(1)
                                                st.rerun()
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
                                                    tm.sleep(1)
                                                    st.rerun()
                                                else: st.error("❌ Erro ao excluir usuário.")
                                            except Exception as e: st.error(f"❌ Erro ao excluir usuário: {e}")
                    else: st.info("Nenhum usuário encontrado.")
                except Exception as e: st.error(f"Erro ao carregar usuários: {e}")

    # =========================
    #     ABA 6 - NOTIFICAÇÕES POR E-MAIL (APENAS ADMIN)
    # =========================
    if st.session_state.aba_ativa == "aba6" and st.session_state.is_admin:
        st.header("Notificações por E-mail")
            
        st.markdown("""
        ### Sistema de Notificação Automática
        Este sistema envia e-mails automáticos para clientes baseados nas janelas de tempo cadastradas.
        Os e-mails são enviados utilizando:
        - **Remetente:** ticket@clicklogtransportes.com.br
        - **Servidor SMTP:** smtp.resend.com (Com fallback para Gmail)
        """)
        
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Testar Conexão SMTP")
            if st.button("Testar Conexão"):
                with st.spinner("Testando conexão com servidor SMTP..."):
                    sucesso, mensagem = testar_conexao_smtp()
                    if sucesso: st.success(mensagem)
                    else: st.error(mensagem)

        with col2:
            st.subheader("Enviar Notificações Manualmente")
            if st.button("Enviar Notificações Agora"):
                with st.spinner("Verificando ocorrências e enviando e-mails... isso pode levar um tempo..."):
                    resultados = notificar_ocorrencias_abertas()
                    if not resultados:
                        st.info("Nenhum e-mail pendente para envio no momento.")
                    for resultado in resultados:
                        if resultado.get("status") == "sucesso":
                            st.success(f"✅ {resultado.get('mensagem')} para {resultado.get('cliente')} - Ticket {resultado.get('ticket')}")
                        else:
                            st.error(f"❌ {resultado.get('mensagem')} para {resultado.get('cliente')} - Ticket {resultado.get('ticket')}")
            
            st.subheader("Histórico de E-mails Enviados")
            resposta = supabase.table("emails_enviados").select("*").order("data_hora", desc=True).execute()
            dados = resposta.data

            if dados:
                df_historico = pd.DataFrame(dados)
                if "data_hora" in df_historico.columns:
                    df_historico["data_hora"] = pd.to_datetime(df_historico["data_hora"], format='mixed').dt.strftime("%d/%m/%Y %H:%M:%S")
                st.dataframe(df_historico)
            else:
                st.info("Nenhum e-mail enviado ainda.")

    # =========================
    #     ABA 8 - ESTATÍSTICAS (BI DASHBOARD)
    # =========================
    # =========================
    #     ABA 8 - ESTATÍSTICAS (BI DASHBOARD)
    # =========================
    if st.session_state.aba_ativa == "aba8":
        st.markdown("## 📊 Dashboard de Performance Logística")
        
        # --- 1. Filtros de Período (Padrão: Últimos 30 dias) ---
        hoje_bi = obter_data_hora_atual_brasil().date()
        inicio_bi = hoje_bi - timedelta(days=30)
        
        st.markdown('<div style="background-color: #2b2b2b; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #444;">', unsafe_allow_html=True)
        col_filtro1, col_filtro2 = st.columns([1, 3])
        with col_filtro1:
            datas_bi = st.date_input("📅 Filtrar Período do BI:", value=(inicio_bi, hoje_bi), max_value=hoje_bi, format="DD/MM/YYYY")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Tratamento das datas selecionadas
        if isinstance(datas_bi, tuple) and len(datas_bi) == 2:
            d_ini, d_fim = datas_bi
        else:
            d_ini = d_fim = datas_bi[0] if isinstance(datas_bi, tuple) else datas_bi
            
        d_ini_str = d_ini.strftime("%Y-%m-%d 00:00:00")
        d_fim_str = d_fim.strftime("%Y-%m-%d 23:59:59")
        
        # --- 2. Carregamento dos Dados ---
        with st.spinner("Processando Cubo de Dados..."):
            dados_bi = carregar_ocorrencias_finalizadas(d_ini_str, d_fim_str)
            
        if not dados_bi:
            st.warning(f"Nenhum ticket finalizado encontrado entre {d_ini.strftime('%d/%m/%Y')} e {d_fim.strftime('%d/%m/%Y')}.")
        else:
            df_bi = pd.DataFrame(dados_bi)
            
            # --- 3. Tratamento de Dados (Cálculo Direto de Horas à prova de erros) ---
            # Junta data e hora manual e converte para formato de tempo de verdade
            df_bi["dt_abertura"] = pd.to_datetime(df_bi["data_abertura_manual"] + " " + df_bi["hora_abertura_manual"], errors="coerce")
            df_bi["dt_finalizacao"] = pd.to_datetime(df_bi["data_finalizacao_manual"] + " " + df_bi["hora_finalizacao_manual"], errors="coerce")
            
            # Calcula a diferença exata em horas
            df_bi["horas_espera"] = (df_bi["dt_finalizacao"] - df_bi["dt_abertura"]).dt.total_seconds() / 3600.0
            
            # 🟢 FILTRO DE SEGURANÇA: Remove tempos negativos ou absurdos (mais de 30 dias de espera por erro de digitação)
            df_validos = df_bi[(df_bi["horas_espera"] >= 0) & (df_bi["horas_espera"] < 720)].copy()
            
            # --- 4. KPIs (Indicadores Chave) ---
            st.markdown("### 🎯 Visão Geral do Período")
            
            total_tickets = len(df_bi)
            tempo_medio_geral = df_validos["horas_espera"].mean() if not df_validos.empty else 0
            
            # 🟢 MÉDIA DE HORAS: Agora calcula qual cliente tem a maior MÉDIA de tempo de espera
            if not df_validos.empty:
                cliente_pior_tempo = df_validos.groupby("cliente")["horas_espera"].mean().idxmax()
                pior_tempo_val = df_validos.groupby("cliente")["horas_espera"].mean().max()
            else:
                cliente_pior_tempo = "N/A"
                pior_tempo_val = 0
            
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(label="Total de Tickets", value=total_tickets)
            k2.metric(label="Média de Espera (Geral)", value=f"{tempo_medio_geral:.1f} hrs")
            k3.metric(label="Gargalo (Pior Média)", value=str(cliente_pior_tempo))
            k4.metric(label="Média do Pior Cliente", value=f"{pior_tempo_val:.1f} hrs")
            
            st.markdown("<hr style='border: 1px solid #444;'>", unsafe_allow_html=True)
            
            # --- 5. MOTOR DE GRÁFICOS COM RÓTULOS (ALTAIR) ---
            import altair as alt
            
            def plot_grafico_rotulo(serie, nome_x, nome_y, cor, is_tempo=False):
                df_plot = serie.reset_index()
                df_plot.columns = [nome_x, nome_y]
                
                formato_texto = '.1f' if is_tempo else 'd'
                if is_tempo:
                    df_plot[nome_y] = df_plot[nome_y].round(1)
                
                barras = alt.Chart(df_plot).mark_bar(color=cor, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                    x=alt.X(f'{nome_x}:N', sort='-y', axis=alt.Axis(labelAngle=-45, title="")),
                    y=alt.Y(f'{nome_y}:Q', axis=alt.Axis(grid=False, title=""))
                )
                
                textos = barras.mark_text(
                    align='center',
                    baseline='bottom',
                    dy=-5, 
                    color='white',
                    fontWeight='bold',
                    fontSize=13
                ).encode(
                    text=alt.Text(f'{nome_y}:Q', format=formato_texto)
                )
                
                grafico_final = (barras + textos).properties(height=350).configure_view(strokeWidth=0)
                return grafico_final

            # --- 6. RENDERIZAÇÃO DOS GRÁFICOS ---
            col_graf1, col_graf2 = st.columns(2)
            
            with col_graf1:
                st.markdown("#### 🏆 Clientes c/ Mais Tickets")
                st.caption("Top 10 clientes com maior volume de ocorrências.")
                vol_clientes = df_bi["cliente"].value_counts().head(10)
                if not vol_clientes.empty:
                    st.altair_chart(plot_grafico_rotulo(vol_clientes, "Cliente", "Tickets", "#A3D014"), use_container_width=True)
                
            with col_graf2:
                st.markdown("#### ⏳ Gargalos: Maior Tempo MÉDIO (Horas)")
                st.caption("Top 10 clientes com a maior média de tempo de espera.")
                # 🟢 GRAFICO DE TEMPO MÉDIO
                tempo_clientes = df_validos.groupby("cliente")["horas_espera"].mean().sort_values(ascending=False).head(10)
                if not tempo_clientes.empty:
                    st.altair_chart(plot_grafico_rotulo(tempo_clientes, "Cliente", "Horas", "#d9534f", is_tempo=True), use_container_width=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            
            col_graf3, col_graf4 = st.columns(2)
            
            with col_graf3:
                st.markdown("#### 🏷️ Frequência por Tipo")
                tipos = df_bi["tipo_de_ocorrencia"].value_counts().head(8)
                if not tipos.empty:
                    st.altair_chart(plot_grafico_rotulo(tipos, "Tipo", "Quantidade", "#4facfe"), use_container_width=True)
                
            with col_graf4:
                st.markdown("#### 🚚 Tickets por Motorista")
                mot = df_bi["motorista"].value_counts().head(10)
                if not mot.empty:
                    st.altair_chart(plot_grafico_rotulo(mot, "Motorista", "Tickets", "#f39c12"), use_container_width=True) 
    # =========================
    #     ABA 7 - CADASTROS
    # =========================
    if st.session_state.aba_ativa == "aba7":
        st.header("Cadastros Gerais")
        
        menu_cadastro = st.radio(
            "Selecione o cadastro:",
            ["Motoristas", "Cidades", "Filiais", "Clientes", "Configurações"], # <-- Adicionado 'Filiais'
            horizontal=True
        )

        def safe_int(valor):
            if pd.isna(valor) or valor is None or valor == "":
                return 0
            return int(valor)

        # =========================================================
        # 1. GERENCIAR MOTORISTAS
        # =========================================================
        if menu_cadastro == "Motoristas":
            st.subheader("Gerenciar Motoristas")
            modo_mot = st.radio("Ação:", ["Cadastrar Novo", "Editar Existente"], horizontal=True, key="radio_mot")
            
            if modo_mot == "Cadastrar Novo":
                with st.form("form_mot_novo", clear_on_submit=True):
                    nm = st.text_input("Nome do Motorista")
                    if st.form_submit_button("Salvar Novo Motorista"):
                        if nm:
                            try:
                                supabase.table("motoristas").insert({"motorista": nm}).execute()
                                st.success(f"Motorista '{nm}' cadastrado!")
                                carregar_motoristas_supabase.clear() 
                            except Exception as e: st.error(f"Erro ao cadastrar: {e}")
                        else: st.warning("Digite o nome.")
            else:
                try:
                    res = supabase.table("motoristas").select("motorista, id").range(0, 5000).execute()
                    lista_mot = res.data if res.data else []
                except Exception as e:
                    st.error(f"Erro de conexão: {e}")
                    lista_mot = []
                
                lista_mot = [m for m in lista_mot if m.get('motorista')]
                
                if not lista_mot: st.info("Nenhum motorista encontrado.")
                else:
                    lista_mot = sorted(lista_mot, key=lambda x: str(x['motorista']).lower())
                    dict_mot = {m['motorista']: m['id'] for m in lista_mot}
                    st.caption(f"Total: {len(lista_mot)} motoristas")
                    
                    nome_sel = st.selectbox("Selecione o Motorista:", options=list(dict_mot.keys()), index=None, placeholder="Selecione...", key="sel_mot_edit")
                    
                    if nome_sel:
                        with st.form("form_mot_edit"):
                            novo_nome_mot = st.text_input("Editar Nome:", value=nome_sel)
                            if st.form_submit_button("Salvar Alterações"):
                                id_alvo = dict_mot[nome_sel]
                                try:
                                    supabase.table("motoristas").update({"motorista": novo_nome_mot}).eq("id", id_alvo).execute()
                                    st.success("Motorista atualizado!")
                                    carregar_motoristas_supabase.clear()
                                    tm.sleep(1)
                                    st.rerun()
                                except Exception as e: st.error(f"Erro ao atualizar: {e}")

        # =========================================================
        # 2. GERENCIAR CIDADES
        # =========================================================
        elif menu_cadastro == "Cidades":
            st.subheader("Gerenciar Cidades")
            modo_cid = st.radio("Ação:", ["Cadastrar Nova", "Editar Existente"], horizontal=True, key="radio_cid")

            if modo_cid == "Cadastrar Nova":
                with st.form("form_cid_novo", clear_on_submit=True):
                    nc = st.text_input("Nome da Cidade")
                    if st.form_submit_button("Salvar Nova Cidade"):
                        if nc:
                            suc, msg = inserir_cidade(nc)
                            if suc: 
                                st.success(msg)
                                carregar_cidades_supabase.clear()
                            else: st.error(msg)
                        else: st.warning("Digite a cidade.")
            else:
                try:
                    res = supabase.table("cidades").select("cidade, id").execute()
                    lista_cid = sorted(res.data, key=lambda x: str(x.get('cidade', '')).lower()) if res.data else []
                except: lista_cid = []

                if not lista_cid: st.info("Nenhuma cidade cadastrada.")
                else:
                    dict_cid = {c['cidade']: c['id'] for c in lista_cid if c.get('cidade')}
                    cid_sel = st.selectbox("Selecione a Cidade:", options=list(dict_cid.keys()), index=None, placeholder="Selecione...", key="sel_cid_edit")
                    if cid_sel:
                        with st.form("form_cid_edit"):
                            nova_nome_cid = st.text_input("Editar Nome:", value=cid_sel)
                            if st.form_submit_button("Salvar Alterações"):
                                id_alvo = dict_cid[cid_sel]
                                try:
                                    suc, msg = atualizar_cidade(id_alvo, nova_nome_cid)
                                    if suc:
                                        st.success(msg)
                                        carregar_cidades_supabase.clear()
                                        tm.sleep(1)
                                        st.rerun()
                                    else: st.error(msg)
                                except Exception as e: st.error(f"Erro ao atualizar: {e}")
        # =========================================================
        # 3. GERENCIAR CLIENTES
        # =========================================================
        elif menu_cadastro == "Clientes":
            st.subheader("Gerenciar Clientes")
            
            # --- Modal flutuante (Dialog) para exibir os erros ---
            @st.dialog("⚠️ Atenção: Erros de Validação")
            def exibir_erros_dialog(erros_lista):
                st.markdown("Por favor, corrija os itens abaixo antes de salvar:")
                for erro in erros_lista:
                    st.error(erro, icon="❌")
                
                if st.button("Voltar e Corrigir", use_container_width=True):
                    st.rerun()

            # --- Modal flutuante (Dialog) para exibir o SUCESSO ---
            @st.dialog("✅ Sucesso!")
            def exibir_sucesso_dialog(mensagem):
                st.success(mensagem)
                st.markdown("Os dados foram salvos no banco de dados.")
                
                if st.button("Continuar", use_container_width=True):
                    st.rerun()
            # --------------------------------------------------------------
            
            lista_focais_disp = carregar_focal_supabase()
            opcao_gerencia = st.radio("Ação:", ["➕ Cadastrar Novo", "✏️ Editar Existente"], horizontal=True, key="radio_cli")
            st.markdown("---")

            if opcao_gerencia == "➕ Cadastrar Novo":
                with st.form("form_novo_cli", clear_on_submit=True):
                    st.markdown("##### Dados do Cliente")
                    col_n1, col_n2 = st.columns(2)
                    with col_n1:
                        nome = st.text_input("Nome do Cliente (MAIÚSCULO)*")
                        cnpj_novo = st.text_input("CNPJ (Apenas números)*")
                        focal = st.selectbox("Focal*", options=lista_focais_disp, index=None, placeholder="Selecione o Focal...")
                        rec_email = st.checkbox("Cliente irá Receber E-mail de Notificação?", value=False)
                    with col_n2:
                        email_p = st.text_input("E-mail Principal*").lower() 
                        email_c = st.text_input("Emails em Cópia (;)*").lower()
                    
                    st.markdown("##### ⏱️ Janelas de Notificação (em minutos)")
                    st.caption("Deixe como 0 as janelas que não for utilizar. Ex: 30, 60, 90, 120, 180.")
                    col_j1, col_j2, col_j3, col_j4, col_j5 = st.columns(5)
                    with col_j1: j1 = st.number_input("Janela 1", min_value=0, step=10, value=30)
                    with col_j2: j2 = st.number_input("Janela 2", min_value=0, step=10, value=60)
                    with col_j3: j3 = st.number_input("Janela 3", min_value=0, step=10, value=90)
                    with col_j4: j4 = st.number_input("Janela 4", min_value=0, step=10, value=0)
                    with col_j5: j5 = st.number_input("Janela 5", min_value=0, step=10, value=0)
                    
                    st.markdown("---")
                    if st.form_submit_button("Salvar Novo Cliente"):
                        erros = []
                        
                        # Validação de Nome
                        if not nome: 
                            erros.append("Nome do cliente é obrigatório.")
                        elif not validar_nome_cliente(nome): 
                            erros.append("Nome deve conter apenas letras MAIÚSCULAS, sem acentos, sem 'Ç' e sem caracteres especiais.")
                        else:
                            # 🟢 NOVO: Checa no banco se o NOME já existe para jogar no Dialog
                            check_nome = supabase.table("clientes").select("id").eq("cliente", nome).execute()
                            if check_nome.data:
                                erros.append(f"O cliente '{nome}' já está cadastrado no sistema.")
                        
                        # Validação de CNPJ
                        cnpj_limpo = re.sub(r'[^0-9]', '', cnpj_novo)
                        if not cnpj_limpo: 
                            erros.append("CNPJ é obrigatório.")
                        elif len(cnpj_limpo) != 14: 
                            erros.append("CNPJ inválido. Digite exatamente 14 números.")
                        else:
                            # 🟢 NOVO: Checa no banco se o CNPJ já existe para jogar no Dialog
                            check_cnpj = supabase.table("clientes").select("id").eq("cnpj", cnpj_limpo).execute()
                            if check_cnpj.data: 
                                erros.append(f"O CNPJ '{cnpj_limpo}' já está vinculado a outro cliente.")
                        
                        # Outras Validações
                        if not focal: erros.append("Selecione um Focal responsável.")
                        
                        if not email_p: erros.append("E-mail Principal é obrigatório.")
                        elif not validar_email(email_p): erros.append("Formato do E-mail Principal inválido.")
                        
                        if not email_c: erros.append("É obrigatório informar ao menos um E-mail em Cópia.")
                        elif not validar_emails_multiplos(email_c): erros.append("Formato de um ou mais E-mails em Cópia inválido.")
                        
                        # Dispara Modal de Erro se houver algum
                        if erros:
                            exibir_erros_dialog(erros)
                        else:
                            suc, msg = inserir_cliente(nome, focal, rec_email, email_p, email_c, cnpj_limpo, j1, j2, j3, j4, j5)
                            if suc:
                                carregar_clientes_supabase.clear()
                                exibir_sucesso_dialog(msg)
                            else: 
                                st.error(msg)

            elif opcao_gerencia == "✏️ Editar Existente":
                try:
                    res = supabase.table("clientes").select("cliente, id, focal, receber_emails, enviar_para_email, email_copia, cnpj, janela_1, janela_2, janela_3, janela_4, janela_5").range(0, 3000).order("cliente").execute()
                    df_edit = pd.DataFrame(res.data) if res.data else pd.DataFrame()
                except Exception as e:
                    st.error(f"Erro: {e}")
                    df_edit = pd.DataFrame()

                if df_edit.empty: st.warning("Sem clientes no banco de dados.")
                else:
                    nomes = sorted(df_edit["cliente"].tolist(), key=lambda x: str(x).lower())
                    escolha = st.selectbox("Selecione o Cliente para editar:", options=nomes, index=None, placeholder="Selecionar...")
                    
                    if escolha:
                        dados = df_edit[df_edit["cliente"] == escolha].iloc[0]
                        with st.form("form_edit"):
                            st.info(f"Editando: {escolha}")
                            c1, c2 = st.columns(2)
                            with c1:
                                n_nome = st.text_input("Nome*", value=dados.get("cliente", ""))
                                n_cnpj = st.text_input("CNPJ*", value=str(dados.get("cnpj", "") if pd.notna(dados.get("cnpj")) else ""))
                                
                                focal_atual = dados.get("focal", "")
                                idx_f = lista_focais_disp.index(focal_atual) if focal_atual in lista_focais_disp else 0
                                novo_focal = st.selectbox("Focal*", options=lista_focais_disp, index=idx_f)
                                novo_rec = st.checkbox("Cliente irá Receber E-mail de Notificação?", value=bool(dados.get("receber_emails")))
                                
                            with c2:
                                n_ep = st.text_input("E-mail Principal*", value=str(dados.get("enviar_para_email", "") if pd.notna(dados.get("enviar_para_email")) else "").lower()).lower()
                                n_ec = st.text_input("Emails em Cópia (;)*", value=str(dados.get("email_copia", "") if pd.notna(dados.get("email_copia")) else "").lower()).lower()
                            
                            st.markdown("##### ⏱️ Janelas (minutos)")
                            j1, j2, j3, j4, j5 = st.columns(5)
                            
                            with j1: v1 = st.number_input("Jan. 1", min_value=0, step=10, value=safe_int(dados.get("janela_1")))
                            with j2: v2 = st.number_input("Jan. 2", min_value=0, step=10, value=safe_int(dados.get("janela_2")))
                            with j3: v3 = st.number_input("Jan. 3", min_value=0, step=10, value=safe_int(dados.get("janela_3")))
                            with j4: v4 = st.number_input("Jan. 4", min_value=0, step=10, value=safe_int(dados.get("janela_4")))
                            with j5: v5 = st.number_input("Jan. 5", min_value=0, step=10, value=safe_int(dados.get("janela_5")))
                            
                            if st.form_submit_button("Salvar Alterações"):
                                erros_edit = []
                                
                                # Validação de Nome na Edição
                                if not n_nome: 
                                    erros_edit.append("Nome é obrigatório.")
                                elif not validar_nome_cliente(n_nome): 
                                    erros_edit.append("Nome deve conter apenas letras MAIÚSCULAS, sem acentos, sem 'Ç' e sem caracteres especiais.")
                                else:
                                    check_nome = supabase.table("clientes").select("id").eq("cliente", n_nome).neq("id", dados['id']).execute()
                                    if check_nome.data: erros_edit.append(f"O cliente '{n_nome}' já está cadastrado.")
                                
                                if not novo_focal: erros_edit.append("Focal é obrigatório.")
                                
                                # Validação de CNPJ na Edição
                                cnpj_limpo = re.sub(r'[^0-9]', '', n_cnpj)
                                if not cnpj_limpo: 
                                    erros_edit.append("CNPJ é obrigatório.")
                                elif len(cnpj_limpo) != 14: 
                                    erros_edit.append("CNPJ deve ter 14 dígitos numéricos.")
                                else:
                                    check_cnpj = supabase.table("clientes").select("id").eq("cnpj", cnpj_limpo).neq("id", dados['id']).execute()
                                    if check_cnpj.data: erros_edit.append(f"O CNPJ {cnpj_limpo} já pertence a outro cliente.")
                                
                                if not n_ep: erros_edit.append("E-mail Principal é obrigatório.")
                                elif not validar_email(n_ep): erros_edit.append("Formato do E-mail Principal inválido.")
                                
                                if not n_ec: erros_edit.append("Ao menos um E-mail em Cópia é obrigatório.")
                                elif not validar_emails_multiplos(n_ec): erros_edit.append("Formato de E-mails em Cópia inválido.")

                                if erros_edit:
                                    exibir_erros_dialog(erros_edit)
                                else:
                                    up = {
                                        "cliente": n_nome, "cnpj": cnpj_limpo, "focal": novo_focal, "receber_emails": novo_rec, 
                                        "enviar_para_email": n_ep, "email_copia": n_ec,
                                        "janela_1": v1 if v1 > 0 else None, "janela_2": v2 if v2 > 0 else None,
                                        "janela_3": v3 if v3 > 0 else None, "janela_4": v4 if v4 > 0 else None,
                                        "janela_5": v5 if v5 > 0 else None
                                    }
                                    suc, msg = atualizar_cliente(dados['id'], up)
                                    if suc:
                                        carregar_clientes_supabase.clear()
                                        exibir_sucesso_dialog("Cliente atualizado com sucesso!")
                                    else: 
                                        st.error(msg)

            # --- TABELA GERAL DE CLIENTES (GRID COMPLETO) ---
            st.markdown("### Lista de Clientes")
            df_view_res = supabase.table("clientes").select("cliente, cnpj, focal, enviar_para_email, email_copia, janela_1, janela_2, janela_3, janela_4, janela_5").execute()
            
            if df_view_res.data:
                df_view = pd.DataFrame(df_view_res.data)
                
                # Renomeia as colunas para o Grid ficar bonito e amigável
                df_view = df_view.rename(columns={
                    "cliente": "Cliente", "cnpj": "CNPJ", "focal": "Focal", 
                    "enviar_para_email": "E-mail Principal", "email_copia": "E-mail Cópia", 
                    "janela_1": "J1", "janela_2": "J2", 
                    "janela_3": "J3", "janela_4": "J4", "janela_5": "J5"
                })
                
                # Organiza a ordem das colunas para exibição na tela
                ordem_colunas = [
                    "Cliente", "CNPJ", "Focal", "E-mail Principal", "E-mail Cópia", 
                    "J1", "J2", "J3", "J4", "J5"
                ]
                df_view = df_view[ordem_colunas]
                
                st.dataframe(df_view, use_container_width=True, hide_index=True)

        # =========================================================
        # 2.5. GERENCIAR FILIAIS
        # =========================================================
        elif menu_cadastro == "Filiais":
            st.subheader("Gerenciar Filiais")
            modo_fil = st.radio("Ação:", ["Cadastrar Nova", "Editar Existente"], horizontal=True, key="radio_fil")

            if modo_fil == "Cadastrar Nova":
                with st.form("form_fil_nova", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        nome_fil = st.text_input("Nome da Filial (Ex: Matriz São Paulo)")
                    with c2:
                        sigla_fil = st.text_input("Sigla (Ex: SPO)")
                        
                    if st.form_submit_button("Salvar Nova Filial"):
                        if nome_fil and sigla_fil:
                            suc, msg = inserir_filial(nome_fil, sigla_fil)
                            if suc: 
                                st.success(msg)
                                carregar_filiais_supabase.clear() # Limpa o cache para atualizar as listas
                                tm.sleep(1)
                                st.rerun()
                            else: 
                                st.error(msg)
                        else: 
                            st.warning("⚠️ Preencha o Nome e a Sigla da filial.")
            
            else: # Ação == Editar Existente
                try:
                    res = supabase.table("filiais").select("*").execute()
                    lista_fil = sorted(res.data, key=lambda x: str(x.get('sigla', '')).lower()) if res.data else []
                except Exception as e: 
                    st.error(f"Erro ao buscar filiais: {e}")
                    lista_fil = []

                if not lista_fil: 
                    st.info("Nenhuma filial cadastrada no banco de dados.")
                else:
                    # Cria um dicionário para exibir de forma bonita: "SIGLA - NOME"
                    dict_fil = {f"{f['sigla']} - {f['filial']}": f for f in lista_fil if f.get('sigla')}
                    
                    fil_sel = st.selectbox(
                        "Selecione a Filial:", 
                        options=list(dict_fil.keys()), 
                        index=None, 
                        placeholder="Selecione...",
                        key="sel_filial_edit" 
                    )
                    
                    if fil_sel:
                        dados_filial = dict_fil[fil_sel]
                        with st.form("form_fil_edit"):
                            c1, c2 = st.columns(2)
                            with c1:
                                nova_nome_fil = st.text_input("Editar Nome:", value=dados_filial.get("filial", ""))
                            with c2:
                                nova_sigla_fil = st.text_input("Editar Sigla:", value=dados_filial.get("sigla", ""))
                                
                            if st.form_submit_button("Salvar Alterações"):
                                if nova_nome_fil and nova_sigla_fil:
                                    suc, msg = atualizar_filial(dados_filial["id"], nova_nome_fil, nova_sigla_fil)
                                    if suc:
                                        st.success(msg)
                                        carregar_filiais_supabase.clear()
                                        tm.sleep(1)
                                        st.rerun()
                                    else: 
                                        st.error(msg)
                                else:
                                    st.warning("⚠️ Preencha o Nome e a Sigla da filial.")

            # --- TABELA GERAL DE FILIAIS (GRID) ---
            st.markdown("### Lista de Filiais")
            try:
                res_view = supabase.table("filiais").select("id, sigla, filial").order("sigla").execute()
                if res_view.data:
                    df_filiais = pd.DataFrame(res_view.data)
                    # Renomeando as colunas para ficar amigável na tela
                    df_filiais = df_filiais.rename(columns={"id": "ID", "sigla": "Sigla", "filial": "Nome da Filial"})
                    st.dataframe(df_filiais, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhuma filial encontrada para exibição.")
            except Exception as e:
                st.error(f"Erro ao carregar a tabela de filiais: {e}")

        # =========================================================
        # 4. CONFIGURAÇÕES
        # =========================================================
        elif menu_cadastro == "Configurações":
            st.subheader("Configurações de Tempo de Envio")
            st.warning("Com o novo motor dinâmico, o tempo de alerta é configurado individualmente por cliente na aba 'Clientes'. Esta tela pode ser removida no futuro.")



        # ====================================================================
        # 🟢 EXECUÇÃO DE MODAIS TARDIOS (EVITA O ERRO "Only one dialog")
        # ====================================================================
        if st.session_state.get("login", False) and disparar_alerta_agora:
            from streamlit.errors import StreamlitAPIException
            try:
                # Tenta disparar o alerta de 12h por último
                dialog_alerta_12h(tickets_estourados)
                st.session_state.ultima_exibicao_alerta_12h = datetime.now() # Atualiza o relógio se abriu
            except StreamlitAPIException:
                # Se deu erro, é porque o usuário acabou de abrir o pop-up de Finalizar ou Editar.
                # O sistema ignora e deixa o usuário trabalhar em paz!
                pass
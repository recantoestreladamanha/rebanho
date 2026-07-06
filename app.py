import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
import unicodedata
import base64
from supabase import create_client, Client

# Configuração da página do Streamlit
st.set_page_config(page_title="Recanto Estrela da Manhã - Gestão", page_icon="🐑", layout="wide")

ARQUIVO_LOGO = "logo.png"

# Tentativa de importação do FPDF para geração de relatórios
FPDF_DISPONIVEL = True
try:
    from fpdf import FPDF
except ImportError:
    FPDF_DISPONIVEL = False

# ------------------------------------------------------------------------------------------
# CONEXÃO COM O SUPABASE (BANCO DE DADOS EM NUVEM SEGURO)
# ------------------------------------------------------------------------------------------
@st.cache_resource
def inicializar_supabase() -> Client:
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar com as Secrets do Supabase: {e}")
        return None

supabase = inicializar_supabase()

# Função para garantir que os dados estejam prontos (Emulador NoSQL sobre Supabase para simplicidade de migração estável)
def carregar_dados():
    if not supabase:
        return {}
    try:
        res = supabase.table("rebanho_dados").select("conteudo").eq("id", 1).execute()
        if res.data:
            return json.loads(res.data[0]["conteudo"])
        else:
            # Se a tabela estiver vazia, cria o registro inicial
            supabase.table("rebanho_dados").insert({"id": 1, "conteudo": "{}"}).execute()
            return {}
    except Exception:
        # Se a tabela não existir, tentamos criar ou apenas retornamos vazio para o fluxo
        try:
            # Criação de contingência caso use SQL Editor do Supabase posterior
            st.info("Nota: Certifique-se de criar a tabela 'rebanho_dados' com as colunas 'id' (int8, primary key) e 'conteudo' (text) no painel do Supabase se notar travamentos.")
        except:
            pass
        return {}

def salvar_dados(dados):
    if not supabase:
        return
    try:
        conteudo_json = json.dumps(dados, ensure_ascii=False)
        supabase.table("rebanho_dados").upsert({"id": 1, "conteudo": conteudo_json}).execute()
    except Exception as e:
        st.error(f"Erro ao salvar dados na nuvem: {e}")

# ------------------------------------------------------------------------------------------
# FUNÇÕES UTILITÁRIAS E MANEJO SANITÁRIO
# ------------------------------------------------------------------------------------------

def remover_acentos(texto):
    if not isinstance(texto, str):
        return str(texto)
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def calcular_idade(data_nasc_str):
    try:
        nasc = datetime.strptime(data_nasc_str, "%Y-%m-%d")
        hoje = datetime.today()
        diferenca = hoje - nasc
        dias = diferenca.days
        if dias < 30:
            return f"{dias} dias"
        meses = dias // 30
        if meses < 12:
            return f"{meses} meses"
        anos = meses // 12
        meses_restantes = meses % 12
        if meses_restantes == 0:
            return f"{anos} ano(s)"
        return f"{anos} ano(s) e {meses_restantes} mes(es)"
    except:
        return "Não informada"

def obter_nome_exibicao(id_brinco, ficha_animal):
    nome = ficha_animal.get("nome", "").strip()
    if nome:
        return f"{id_brinco} - {nome}"
    return id_brinco

def verificar_status_vacinal(ficha_animal):
    historico = ficha_animal.get("historico_saude", [])
    vacinas_pendentes = []
    hoje = date.today()
    
    for h in historico:
        if h.get("dose_tipo", "") == "Uso Contínuo":
            return "Status: 🩺 CONTÍNUO", f"Tratamento contínuo: {h.get('descricao', '')}"
            
    for h in historico:
        prox_dose_str = h.get("proxima_dose", "")
        if prox_dose_str and prox_dose_str != "Não possui":
            try:
                data_prox = datetime.strptime(prox_dose_str, "%Y-%m-%d").date()
                vacinas_pendentes.append((h.get("descricao", "Vacina"), data_prox))
            except:
                pass
                
    if not vacinas_pendentes:
        return "", ""
        
    vacinas_pendentes.sort(key=lambda x: x[1])
    nome_vacina, data_alvo = vacinas_pendentes[0]
    dias_restantes = (data_alvo - hoje).days
    
    if dias_restantes < 0:
        return "🔴 VENCIDA", f"Vacina {nome_vacina} vencida em {data_alvo.strftime('%d/%m/%Y')}"
    elif dias_restantes <= 7:
        return "🟡 CRÍTICA", f"Reforço de {nome_vacina} em {dias_restantes} dias ({data_alvo.strftime('%d/%m/%Y')})"
    else:
        return "🟢 EM DIA", f"Reforço de {nome_vacina} agendado para {data_alvo.strftime('%d/%m/%Y')}"

def verificar_status_carencia(ficha_animal):
    historico = ficha_animal.get("historico_saude", [])
    hoje = date.today()
    carencias_ativas = []

    for h in historico:
        data_car_str = h.get("carencia", "")
        if data_car_str and data_car_str != "Não possui":
            try:
                data_car = datetime.strptime(data_car_str, "%Y-%m-%d").date()
                if data_car >= hoje:
                    carencias_ativas.append((h.get("descricao", "Medicamento"), data_car))
            except:
                pass

    if not carencias_ativas:
        return "✅ LIBERADO", "Animal livre de períodos de carência médica."

    carencias_ativas.sort(key=lambda x: x[1], reverse=True)
    nome_med, data_liberacao = carencias_ativas[0]
    return "⚠️ BLOQUEADO", f"Sob efeito de {nome_med}. Liberado apenas em {data_liberacao.strftime('%d/%m/%Y')}"

# ------------------------------------------------------------------------------------------
# INJEÇÃO DE CSS - ESTILIZAÇÃO IDENTIDADE RECANTO
# ------------------------------------------------------------------------------------------
st.markdown("""
    <style>
    .stButton > button {
        width: 100% !important;
        min-height: 44px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-bottom: 5px !important;
    }
    button[kind="primary"] {
        background-color: #1D2B99 !important;
        color: white !important;
        border: 1px solid #1D2B99 !important;
    }
    button[kind="primary"]:hover {
        background-color: #121B66 !important;
    }
    button[kind="secondary"] {
        background-color: #FFA500 !important;
        color: white !important;
        border: 1px solid #FFA500 !important;
    }
    button[kind="secondary"]:hover {
        background-color: #E69500 !important;
    }
    div[data-testid="stMetricNumber"] {
        color: #FFA500 !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# Inicializar dados da nuvem
if "rebanho" not in st.session_state:
    st.session_state.rebanho = carregar_dados()

if "visualizar_brinco" not in st.session_state:
    st.session_state.visualizar_brinco = None

if "menu_atual" not in st.session_state:
    st.session_state.menu_atual = "Painel Geral (Dashboard)"

dados_rebanho = st.session_state.rebanho

# ------------------------------------------------------------------------------------------
# BARRA LATERAL
# ------------------------------------------------------------------------------------------
if os.path.exists(ARQUIVO_LOGO):
    st.sidebar.image(ARQUIVO_LOGO, use_container_width=True)

st.sidebar.markdown("<h2 style='text-align: center; color: #1D2B99; margin-top: 0;'>RECANTO ESTRELA DA MANHÃ</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("### 📋 Menu de Navegação")

if st.sidebar.button("📊 Painel Geral (Dashboard)", type="primary" if st.session_state.menu_atual == "Painel Geral (Dashboard)" else "secondary"):
    st.session_state.menu_atual = "Painel Geral (Dashboard)"; st.session_state.visualizar_brinco = None; st.rerun()

if st.sidebar.button("➕ Registrar Entrada (Cadastro)", type="primary" if st.session_state.menu_atual == "Registrar Entrada (Cadastro)" else "secondary"):
    st.session_state.menu_atual = "Registrar Entrada (Cadastro)"; st.session_state.visualizar_brinco = None; st.rerun()

if st.sidebar.button("❌ Registrar Saída (Baixa)", type="primary" if st.session_state.menu_atual == "Registrar Saída (Baixa)" else "secondary"):
    st.session_state.menu_atual = "Registrar Saída (Baixa)"; st.session_state.visualizar_brinco = None; st.rerun()

if st.sidebar.button("🏥 Controle Sanitário/Médico", type="primary" if st.session_state.menu_atual == "Controle Sanitário/Médico" else "secondary"):
    st.session_state.menu_atual = "Controle Sanitário/Médico"; st.session_state.visualizar_brinco = None; st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("⚡ *Conectado à nuvem estável Supabase*")

menu = st.session_state.menu_atual

st.markdown("<h1 style='text-align: center; color: #1D2B99;'>🏡 RECANTO ESTRELA DA MANHÃ</h1>", unsafe_allow_html=True)
st.markdown("---")

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD)
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    
    if st.session_state.visualizar_brinco:
        id_sel = st.session_state.visualizar_brinco
        ficha = dados_rebanho[id_sel]
        
        st.button("⬅️ Voltar para a Lista de Animais", on_click=lambda: st.session_state.update({"visualizar_brinco": None}))
        st.header(f"🗂️ Ficha do Animal: {obter_nome_exibicao(id_sel, ficha)}")
        
        col_foto, col_infos = st.columns([1, 2])
        
        with col_foto:
            st.subheader("📷 Foto do Animal")
            if "foto_base64" in ficha and ficha["foto_base64"]:
                st.image(base64.b64decode(ficha["foto_base64"]), use_container_width=True)
                if st.button("❌ Remover Foto"):
                    dados_rebanho[id_sel]["foto_base64"] = ""
                    salvar_dados(dados_rebanho)
                    st.rerun()
            else:
                st.info("Nenhuma foto anexada.")
                nova_foto = st.file_uploader("Adicionar Foto (Opcional)", type=["jpg", "jpeg", "png"], key=f"foto_upload_{id_sel}")
                if nova_foto:
                    encoded = base64.b64encode(nova_foto.read()).decode("utf-8")
                    dados_rebanho[id_sel]["foto_base64"] = encoded
                    salvar_dados(dados_rebanho)
                    st.success("Foto salva permanentemente!")
                    st.rerun()

        with col_infos:
            st.subheader("📋 Informações Cadastrais")
            st.markdown(f"**Identificação:** {id_sel} | **Nome:** {ficha.get('nome', 'Não informado')}")
            st.markdown(f"**Raça:** {ficha['raca']} | **Sexo:** {ficha['sexo']}")
            st.markdown(f"**Idade:** {calcular_idade(ficha['data_nascimento'])} *({ficha['data_nascimento']})*")
            
            status_v, desc_v = verificar_status_vacinal(ficha)
            status_c, desc_c = verificar_status_carencia(ficha)
            st.markdown(f"**Manejo Preventivo:** {status_v if status_v else 'Em dia'} ({desc_v})")
            st.markdown(f"**Restrição de Carência:** {status_c} ({desc_c})")
            
        st.markdown("---")
        aba_pesos, aba_saude, aba_notas = st.tabs(["⚖️ Histórico de Peso", "🏥 Histórico de Saúde", "📝 Notas de Campo"])
        
        with aba_pesos:
            st.subheader("Acompanhamento Ponderal (Controle de Peso)")
            
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                peso_nasc = st.number_input("Peso ao Nascer (kg)", value=float(ficha.get("peso_nascer", 0.0)), step=0.1)
                peso_desm = st.number_input("Peso ao Desmame (kg)", value=float(ficha.get("peso_desmame", 0.0)), step=0.1)
                if st.button("💾 Atualizar Pesos Base"):
                    dados_rebanho[id_sel]["peso_nascer"] = peso_nasc
                    dados_rebanho[id_sel]["peso_desmame"] = peso_desm
                    salvar_dados(dados_rebanho)
                    st.success("Pesos base atualizados!")
                    st.rerun()
            
            with c_p2:
                st.markdown("**Registrar Nova Pesagem Rotineira**")
                data_peso = st.date_input("Data da Pesagem", datetime.today())
                valor_peso = st.number_input("Peso Encontrado (kg)", min_value=0.0, step=0.5)
                if st.button("⚖️ Gravar Novo Peso"):
                    if "historico_pesos" not in dados_rebanho[id_sel]:
                        dados_rebanho[id_sel]["historico_pesos"] = []
                    dados_rebanho[id_sel]["historico_pesos"].append({
                        "data": str(data_peso),
                        "peso": valor_peso
                    })
                    salvar_dados(dados_rebanho)
                    st.success("Nova pesagem registrada!")
                    st.rerun()
            
            st.markdown("#### Evolução do Crescimento")
            lista_pesos = []
            if float(ficha.get("peso_nascer", 0.0)) > 0:
                lista_pesos.append({"Data": "Nascimento", "Peso (kg)": ficha["peso_nascer"]})
            if float(ficha.get("peso_desmame", 0.0)) > 0:
                lista_pesos.append({"Data": "Desmame", "Peso (kg)": ficha["peso_desmame"]})
                
            for p in ficha.get("historico_pesos", []):
                lista_pesos.append({"Data": datetime.strptime(p['data'], "%Y-%m-%d").strftime("%d/%m/%Y"), "Peso (kg)": p['peso']})
                
            if lista_pesos:
                st.table(pd.DataFrame(lista_pesos))
            else:
                st.info("Nenhum peso registrado ainda.")

        with aba_saude:
            st.subheader("Histórico de Intervenções Clínicas")
            historico = ficha.get("historico_saude", [])
            if not historico:
                st.info("Nenhum prontuário sanitário encontrado.")
            else:
                exibir_lista = []
                for h in historico:
                    exibir_lista.append({
                        "Data": datetime.strptime(h['data'], "%Y-%m-%d").strftime("%d/%m/%Y"),
                        "Evento": h['categoria'],
                        "Descrição": h['descricao'],
                        "Dose": h.get('dose_tipo', 'N/A'),
                        "Liberação Carência": h.get('carencia', 'Não possui')
                    })
                st.table(pd.DataFrame(exibir_lista))
                
        with aba_notas:
            st.subheader("Anotações Gerais")
            nova_obs = st.text_area("Observações importantes de campo:", value=ficha.get("observacoes", ""), height=150)
            if st.button("💾 Salvar Anotações"):
                dados_rebanho[id_sel]["observacoes"] = nova_obs
                salvar_dados(dados_rebanho)
                st.success("Anotações salvas!")
                st.rerun()
                
    else:
        if not dados_rebanho:
            st.info("Nenhum animal em base de dados.")
        else:
            ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
            baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
            
            st.columns(3)[0].metric("Efetivo de Animais Ativos", len(ativos))
            
            tab_ativos, tab_inativos = st.tabs(["🟢 Animais Ativos", "🔴 Inativos / Baixas"])
            
            with tab_ativos:
                st.subheader("📋 Lista de Animais Ativos")
                
                if ativos:
                    c_head = st.columns([1.5, 1.2, 1.2, 1.5, 1.2, 1.5, 1.5])
                    c_head[0].markdown("**ID / Nome**")
                    c_head[1].markdown("**Raça**")
                    c_head[2].markdown("**Sexo**")
                    c_head[3].markdown("**Idade**")
                    c_head[4].markdown("**Manejo/Vacina**")
                    c_head[5].markdown("**Carência Abate**")
                    c_head[6].markdown("**Ações**")
                    st.markdown("<hr style='margin: 4px 0;'>", unsafe_allow_html=True)
                    
                    for brinco, f_at in ativos.items():
                        c_row = st.columns([1.5, 1.2, 1.2, 1.5, 1.2, 1.5, 1.5])
                        c_row[0].write(obter_nome_exibicao(brinco, f_at))
                        c_row[1].write(f_at["raca"])
                        c_row[2].write(f_at["sexo"])
                        c_row[3].write(calcular_idade(f_at["data_nascimento"]))
                        
                        status_v, desc_v = verificar_status_vacinal(f_at)
                        c_row[4].markdown(f"{status_v if status_v else 'Em dia'}", help=desc_v)
                        
                        status_c, desc_c = verificar_status_carencia(f_at)
                        c_row[5].markdown(f"{status_c}", help=desc_c)
                            
                        if c_row[6].button("🔎 Abrir Ficha", key=f"abrir_{brinco}"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                else:
                    st.warning("Nenhum animal ativo.")

            with tab_inativos:
                st.subheader("🪵 Animais Fora do Lote")
                if baixas:
                    c_head_in = st.columns([2, 2, 1.5, 2.5, 2])
                    c_head_in[0].markdown("**Identificação / Nome**")
                    c_head_in[1].markdown("**Raça**")
                    c_head_in[2].markdown("**Sexo**")
                    c_head_in[3].markdown("**Motivo da Saída**")
                    c_head_in[4].markdown("**Ações**")
                    
                    for brinco, f_in in baixas.items():
                        c_row_in = st.columns([2, 2, 1.5, 2.5, 2])
                        c_row_in[0].write(obter_nome_exibicao(brinco, f_in))
                        c_row_in[1].write(f_in["raca"])
                        c_row_in[2].write(f_in["sexo"])
                        c_row_in[3].write(f"{f_in['status']} ({f_in.get('data_saida', 'N/I')})")
                        if c_row_in[4].button("🔎 Abrir Ficha", key=f"abrir_in_{brinco}"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                else:
                    st.info("Nenhuma baixa.")

# ------------------------------------------------------------------------------------------
# REGISTRAR ENTRADA (CADASTRO)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Entrada (Cadastro)":
    st.header("➕ Registrar Entrada de Animal")
    
    with st.form("form_entrada", clear_on_submit=True):
        col_id, col_nome = st.columns(2)
        with col_id:
            id_brinco = st.text_input("Identificação (Brinco) *")
        with col_nome:
            nome_animal = st.text_input("Nome / Alcunha (Opcional)")
            
        raca = st.selectbox("Raça", ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)"])
        sexo = st.radio("Sexo", ["Fêmea (Matriz/Borrega)", "Macho (Reprodutor/Borrego)"], horizontal=True)
        data_nascimento = st.date_input("Data de Nascimento", datetime.today())
        origem = st.selectbox("Forma de Entrada", ["Procriação (Nascimento)", "Compra", "Doação"])
        
        st.markdown("#### ⚖️ Pesagem de Entrada")
        peso_nasc_c = st.number_input("Peso ao Nascer (kg) - Deixe 0 se não souber", value=0.0, step=0.1)
        
        enviar = st.form_submit_button("Salvar Registro")
        
        if enviar:
            if not id_brinco.strip():
                st.error("Identificação obrigatória.")
            elif id_brinco in dados_rebanho:
                st.error("Animal já cadastrado.")
            else:
                dados_rebanho[id_brinco] = {
                    "nome": nome_animal.strip(),
                    "raca": raca,
                    "sexo": sexo,
                    "data_nascimento": str(data_nascimento),
                    "origem": origem,
                    "peso_nascer": peso_nasc_c,
                    "peso_desmame": 0.0,
                    "historico_pesos": [],
                    "pai": "Não Informado",
                    "mae": "Não Informado",
                    "status": "Ativo",
                    "foto_base64": "",
                    "observacoes": "",
                    "historico_saude": []
                }
                salvar_dados(dados_rebanho)
                st.success("Cadastro realizado com sucesso!")
                st.rerun()

elif menu == "Registrar Saída (Baixa)":
    st.header("❌ Registrar Saída (Baixa)")
    ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
    if not ativos:
        st.info("Nenhum animal ativo para dar baixa.")
    else:
        with st.form("form_saida", clear_on_submit=True):
            opcoes_baixa = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
            animal_selecionado = st.selectbox("Selecione o Animal", list(opcoes_baixa.keys()), format_func=lambda x: opcoes_baixa[x])
            motivo_saida = st.selectbox("Motivo da Saída", ["Morte", "Venda", "Doação"])
            data_saida = st.date_input("Data da Saída", datetime.today())
            detalhes_saida = st.text_area("Observações adicionais")
            
            if st.form_submit_button("Registrar Saída"):
                dados_rebanho[animal_selecionado]["status"] = motivo_saida
                dados_rebanho[animal_selecionado]["data_saida"] = str(data_saida)
                dados_rebanho[animal_selecionado]["motivo_saida"] = detalhes_saida
                salvar_dados(dados_rebanho)
                st.success("Baixa cadastrada!")
                st.rerun()

elif menu == "Controle Sanitário/Médico":
    st.header("🏥 Controle Sanitário")
    if not dados_rebanho:
        st.info("Nenhum animal cadastrado.")
    else:
        tipo_manejo = st.radio("Tipo de Manejo", ["Individual", "Coletivo"], horizontal=True)
        with st.form("form_saude", clear_on_submit=True):
            data_manejo = st.date_input("Data do Manejo", datetime.today())
            categoria_manejo = st.selectbox("Tipo de Evento", ["Vacinação Preventiva", "Vermifugação", "Tratamento de Doença (ex: Casco/Mastite)", "Avaliação Famacha", "Outro"])
            descricao_tratamento = st.text_input("Descrição (Medicamento/Manejo)")
            
            dose_tipo = "N/A"
            proxima_dose_data = "Não possui"
            
            if categoria_manejo == "Vacinação Preventiva":
                dose_tipo = st.selectbox("Esquema de Dose:", ["Dose Única", "1ª Dose", "2ª Dose"])
                if dose_tipo in ["1ª Dose", "2ª Dose"]:
                    proxima_dose_data = str(st.date_input("Data do Reforço", datetime.today()))
            elif categoria_manejo in ["Tratamento de Doença (ex: Casco/Mastite)", "Outro"]:
                if st.radio("Duração:", ["Ciclo Fechado", "Uso Contínuo"]) == "Uso Contínuo":
                    dose_tipo = "Uso Contínuo"
                    
            possui_carencia = st.radio("Possui carência?", ["Não", "Sim"], horizontal=True)
            carencia_salvar = str(st.date_input("Data Final", datetime.today())) if possui_carencia == "Sim" else "Não possui"
            
            if tipo_manejo == "Individual":
                opcoes_saude = {k: obter_nome_exibicao(k, v) for k, v in dados_rebanho.items()}
                animais_alvo = [st.selectbox("Selecione o Animal", list(opcoes_saude.keys()), format_func=lambda x: opcoes_saude[x])]
            else:
                animais_alvo = [k for k, v in dados_rebanho.items() if v["status"] == "Ativo"]
                
            if st.form_submit_button("Gravar Registro"):
                if not descricao_tratamento.strip():
                    st.error("Insira a descrição.")
                else:
                    registro = {
                        "data": str(data_manejo),
                        "categoria": categoria_manejo,
                        "descricao": descricao_tratamento,
                        "dose_tipo": dose_tipo,
                        "proxima_dose": proxima_dose_data,
                        "carencia": carencia_salvar
                    }
                    for brinco in animais_alvo:
                        dados_rebanho[brinco]["historico_saude"].append(registro)
                    salvar_dados(dados_rebanho)
                    st.success("Manejo registrado!")
                    st.rerun()

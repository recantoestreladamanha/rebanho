import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
import unicodedata

# Configuração da página do Streamlit - Otimizado para visualização fluida
st.set_page_config(page_title="Recanto Estrela da Manhã - Gestão", page_icon="🐑", layout="wide")

ARQUIVO_DADOS = "rebanho.json"
ARQUIVO_LOGO = "logo.png"

# Tentativa de importação do FPDF para geração de relatórios
FPDF_DISPONIVEL = True
try:
    from fpdf import FPDF
except ImportError:
    FPDF_DISPONIVEL = False

# ------------------------------------------------------------------------------------------
# FUNÇÕES UTILITÁRIAS E HIGIENIZAÇÃO PARA PDF
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

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def obter_nome_exibicao(id_brinco, ficha_animal):
    nome = ficha_animal.get("nome", "").strip()
    if nome:
        return f"{id_brinco} - {nome}"
    return id_brinco

# Função para verificar o status vacinal e de tratamentos contínuos de um animal ativo
def verificar_status_vacinal(ficha_animal):
    historico = ficha_animal.get("historico_saude", [])
    vacinas_pendentes = []
    hoje = date.today()
    
    for h in historico:
        if h.get("dose_tipo", "") == "Uso Contínuo":
            return "🩺 CONTÍNUO", f"Animal em tratamento contínuo: {h.get('descricao', 'Sem descrição')}", "#1D2B99"
            
    for h in historico:
        prox_dose_str = h.get("proxima_dose", "")
        if prox_dose_str and prox_dose_str != "Não possui":
            try:
                data_prox = datetime.strptime(prox_dose_str, "%Y-%m-%d").date()
                vacinas_pendentes.append((h.get("descricao", "Vacina"), data_prox))
            except:
                pass
                
    if not vacinas_pendentes:
        return "🟢 EM DIA", "Esquema vacinal preventivo sem pendências.", "#2E7D32"
        
    vacinas_pendentes.sort(key=lambda x: x[1])
    nome_vacina, data_alvo = vacinas_pendentes[0]
    dias_restantes = (data_alvo - hoje).days
    
    if dias_restantes < 0:
        return "🔴 VENCIDA", f"Vacina {nome_vacina} vencida em {data_alvo.strftime('%d/%m/%Y')}", "#D32F2F"
    elif dias_restantes <= 7:
        return "🟡 CRÍTICA", f"Reforço de {nome_vacina} em {dias_restantes} dias ({data_alvo.strftime('%d/%m/%Y')})", "#FBC02D"
    else:
        return "🟢 EM DIA", f"Reforço de {nome_vacina} agendado para {data_alvo.strftime('%d/%m/%Y')}", "#2E7D32"

# Função para verificar o status de carência médica de um animal ativo
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
        return "✅ LIBERADO", "Animal livre de períodos de carência médica.", "#2E7D32"

    carencias_ativas.sort(key=lambda x: x[1], reverse=True)
    nome_med, data_liberacao = carencias_ativas[0]
    return "⚠️ BLOQUEADO", f"Sob efeito de {nome_med}. Liberado apenas em {data_liberacao.strftime('%d/%m/%Y')}", "#E65100"

# ------------------------------------------------------------------------------------------
# INJEÇÃO DE CSS - DESIGN RESPONSIVO MOBILE EXTRAFLUIDO
# ------------------------------------------------------------------------------------------
st.markdown("""
    <style>
    /* Ajustes globais para telas menores (Celulares) */
    .stButton > button {
        width: 100% !important;
        min-height: 48px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        margin-bottom: 8px !important;
        font-size: 16px !important;
    }
    
    /* Cores dos botões - Identidade Visual Recanto Estrela da Manhã */
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
    
    /* Cards Mobile de Animais */
    .animal-card {
        background-color: #f9f9fb;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .animal-title {
        font-size: 18px;
        font-weight: bold;
        color: #1D2B99;
        margin-bottom: 8px;
    }
    .animal-meta {
        font-size: 14px;
        color: #4a5568;
        margin-bottom: 6px;
    }
    
    /* Badges de Alerta */
    .status-badge {
        display: inline-block;
        padding: 4px 10px;
        font-size: 12px;
        font-weight: bold;
        color: white;
        border-radius: 6px;
        margin-top: 4px;
        margin-right: 6px;
    }
    
    /* Layout de Métricas Responsivo */
    div[data-testid="stMetricNumber"] {
        color: #FFA500 !important;
        font-weight: bold !important;
        font-size: 28px !important;
    }
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------------------
# INICIALIZAÇÃO DE SESSÃO
# ------------------------------------------------------------------------------------------
if "rebanho" not in st.session_state:
    st.session_state.rebanho = carregar_dados()

if "visualizar_brinco" not in st.session_state:
    st.session_state.visualizar_brinco = None

if "menu_atual" not in st.session_state:
    st.session_state.menu_atual = "Painel Geral (Dashboard)"

dados_rebanho = st.session_state.rebanho

# ------------------------------------------------------------------------------------------
# BARRA LATERAL: LOGO E TÍTULO
# ------------------------------------------------------------------------------------------
if os.path.exists(ARQUIVO_LOGO):
    st.sidebar.image(ARQUIVO_LOGO, use_container_width=True)

st.sidebar.markdown("<h2 style='text-align: center; color: #1D2B99; margin-top: 0;'>RECANTO ESTRELA DA MANHÃ</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("### 📋 Menu de Navegação")

def ir_para_dashboard():
    st.session_state.menu_atual = "Painel Geral (Dashboard)"
    st.session_state.visualizar_brinco = None

def ir_para_cadastro():
    st.session_state.menu_atual = "Registrar Entrada (Cadastro)"
    st.session_state.visualizar_brinco = None

def ir_para_baixa():
    st.session_state.menu_atual = "Registrar Saída (Baixa)"
    st.session_state.visualizar_brinco = None

def ir_para_saude():
    st.session_state.menu_atual = "Controle Sanitário/Médico"
    st.session_state.visualizar_brinco = None

if st.sidebar.button("📊 Painel Geral (Dashboard)", key="btn_menu_dash", type="primary" if st.session_state.menu_atual == "Painel Geral (Dashboard)" else "secondary"):
    ir_para_dashboard()
    st.rerun()

if st.sidebar.button("➕ Registrar Entrada (Cadastro)", key="btn_menu_cad", type="primary" if st.session_state.menu_atual == "Registrar Entrada (Cadastro)" else "secondary"):
    ir_para_cadastro()
    st.rerun()

if st.sidebar.button("❌ Registrar Saída (Baixa)", key="btn_menu_baixa", type="primary" if st.session_state.menu_atual == "Registrar Saída (Baixa)" else "secondary"):
    ir_para_baixa()
    st.rerun()

if st.sidebar.button("🏥 Controle Sanitário/Médico", key="btn_menu_saude", type="primary" if st.session_state.menu_atual == "Controle Sanitário/Médico" else "secondary"):
    ir_para_saude()
    st.rerun()

st.sidebar.markdown("---")

if not FPDF_DISPONIVEL:
    st.sidebar.warning("⚠️ **Geração de PDF Desativada**\n\nAdicione `fpdf` ao seu arquivo `requirements.txt` no GitHub.")

menu = st.session_state.menu_atual

# Título Principal do Topo
st.markdown("<h1 style='text-align: center; color: #1D2B99; font-size: 24px; margin-bottom: 2px;'>🏡 RECANTO ESTRELA DA MANHÃ</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-style: italic; font-size: 14px;'>Gerenciamento Avançado de Ovinocultura</p>", unsafe_allow_html=True)
st.markdown("---")

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD) - OTIMIZADO PARA MOBILE EM FORMA DE CARDS
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    
    if st.session_state.visualizar_brinco:
        id_sel = st.session_state.visualizar_brinco
        ficha = dados_rebanho[id_sel]
        
        st.button("⬅️ Voltar para a Lista", on_click=lambda: st.session_state.update({"visualizar_brinco": None}))
        st.subheader(f"🗂️ Ficha: {obter_nome_exibicao(id_sel, ficha)}")
        
        if FPDF_DISPONIVEL:
            try:
                pdf_bytes_ficha = gerar_pdf_ficha_individual(id_sel, ficha, dados_rebanho)
                st.download_button(label="📥 Baixar Ficha em PDF", data=pdf_bytes_ficha, file_name=f"ficha_{id_sel}.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"Erro PDF: {e}")
        
        # Informações empilhadas (perfeito para celular)
        st.markdown(f"**Identificação:** {id_sel}")
        st.markdown(f"**Nome:** {ficha.get('nome', 'Não informado')}")
        st.markdown(f"**Raça:** {ficha['raca']}")
        st.markdown(f"**Sexo:** {ficha['sexo']}")
        st.markdown(f"**Idade:** {calcular_idade(ficha['data_nascimento'])} *({ficha['data_nascimento']})*")
        st.markdown(f"**Entrada:** {ficha['origem']}")
        
        pai_f = dados_rebanho.get(ficha["pai"], {})
        mae_f = dados_rebanho.get(ficha["mae"], {})
        st.markdown(f"**Pai:** {obter_nome_exibicao(ficha['pai'], pai_f) if ficha['pai'] != 'Não Informado' else 'Não Informado'}")
        st.markdown(f"**Mãe:** {obter_nome_exibicao(ficha['mae'], mae_f) if ficha['mae'] != 'Não Informado' else 'Não Informado'}")
        
        status_v, desc_v, _ = verificar_status_vacinal(ficha)
        status_c, desc_c, _ = verificar_status_carencia(ficha)
        st.info(f"**Manejo Sanitário:** {desc_v}\n\n**Carência:** {desc_c}")
        
        # Espaço de anotações expandido para touch
        st.subheader("📝 Notas de Campo")
        nova_obs = st.text_area("Anotações sobre o animal:", value=ficha.get("observacoes", ""), height=120)
        if st.button("💾 Salvar Notas"):
            dados_rebanho[id_sel]["observacoes"] = nova_obs
            salvar_dados(dados_rebanho)
            st.success("Salvo com sucesso!")
            st.rerun()
            
    else:
        if not dados_rebanho:
            st.info("Nenhum animal cadastrado no momento.")
        else:
            ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
            baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
            
            # Métricas empilhadas ou em colunas pequenas
            c1, c2 = st.columns(2)
            c1.metric("Ativos", len(ativos))
            c2.metric("Baixas", len(baixas))
            
            tab_ativos, tab_inativos = st.tabs(["🟢 Ativos", "🔴 Baixas"])
            
            with tab_ativos:
                # Busca rápida móvel bem destacada
                opcoes_busca = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
                busca_id = st.selectbox("🔍 Escolha um animal para abrir a Ficha:", ["Selecione..."] + list(opcoes_busca.keys()), format_func=lambda x: opcoes_busca.get(x, x))
                if busca_id != "Selecione...":
                    st.session_state.visualizar_brinco = busca_id
                    st.rerun()
                
                st.markdown("---")
                
                # Exibição em formato de CARDS MOBILE para animais ativos
                if ativos:
                    for brinco, f_at in ativos.items():
                        lbl_v, desc_v, cor_v = verificar_status_vacinal(f_at)
                        lbl_c, desc_c, cor_c = verificar_status_carencia(f_at)
                        
                        # Estrutura HTML do Card Limpo
                        st.markdown(f"""
                        <div class="animal-card">
                            <div class="animal-title">🆔 {obter_nome_exibicao(brinco, f_at)}</div>
                            <div class="animal-meta"><b>Raça:</b> {f_at['raca']} | <b>Sexo:</b> {f_at['sexo']}</div>
                            <div class="animal-meta"><b>Idade:</b> {calcular_idade(f_at['data_nascimento'])}</div>
                            <div style="margin-top: 8px;">
                                <span class="status-badge" style="background-color: {cor_v};" title="{desc_v}">{lbl_v}</span>
                                <span class="status-badge" style="background-color: {cor_c};" title="{desc_c}">{lbl_c}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Botão touch logo abaixo do card
                        if st.button(f"🔎 Abrir Ficha de {brinco}", key=f"card_btn_{brinco}", type="secondary"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                else:
                    st.warning("Não há animais ativos.")
            
            with tab_inativos:
                if baixas:
                    for brinco, f_in in baixas.items():
                        st.markdown(f"""
                        <div class="animal-card">
                            <div class="animal-title">❌ {obter_nome_exibicao(brinco, f_in)}</div>
                            <div class="animal-meta"><b>Raça:</b> {f_in['raca']}</div>
                            <div class="animal-meta"><b>Motivo da Saída:</b> {f_in['status']} ({f_in.get('data_saida', 'N/I')})</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"🔎 Ver Ficha de Inativo {brinco}", key=f"card_btn_in_{brinco}", type="secondary"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                else:
                    st.info("Nenhuma baixa registrada.")

# ------------------------------------------------------------------------------------------
# REGISTRAR ENTRADA (CADASTRO)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Entrada (Cadastro)":
    st.header("➕ Cadastrar Animal")
    
    with st.form("form_entrada", clear_on_submit=True):
        id_brinco = st.text_input("Identificação (Brinco/ID) *")
        nome_animal = st.text_input("Nome (Opcional)")
        raca = st.selectbox("Raça", ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)", "Outra"])
        sexo = st.radio("Sexo", ["Fêmea (Matriz/Borrega)", "Macho (Reprodutor/Borrego)"])
        data_nascimento = st.date_input("Data de Nascimento/Entrada", datetime.today())
        origem = st.selectbox("Forma de Entrada", ["Procriação (Nascimento)", "Compra", "Doação"])
        
        st.markdown("### 🧬 Genealogia")
        opcoes_pais = {"Não Informado": "Não Informado"}
        for k, v in dados_rebanho.items():
            opcoes_pais[k] = obter_nome_exibicao(k, v)
            
        pai = st.selectbox("Pai (Reprodutor)", list(opcoes_pais.keys()), format_func=lambda x: opcoes_pais[x])
        mae = st.selectbox("Mãe (Matriz)", list(opcoes_pais.keys()), format_func=lambda x: opcoes_pais[x])
        
        enviar = st.form_submit_button("Salvar Cadastro", type="primary")
        
        if enviar:
            if not id_brinco.strip():
                st.error("Identificação é obrigatória.")
            elif id_brinco in dados_rebanho:
                st.error(f"ID {id_brinco} já cadastrado.")
            else:
                dados_rebanho[id_brinco] = {
                    "nome": nome_animal.strip(),
                    "raca": raca,
                    "sexo": sexo,
                    "data_nascimento": str(data_nascimento),
                    "origem": origem,
                    "pai": pai,
                    "mae": mae,
                    "status": "Ativo",
                    "motivo_saida": "",
                    "data_saida": "",
                    "observacoes": "",
                    "historico_saude": []
                }
                salvar_dados(dados_rebanho)
                st.success("Cadastrado com sucesso!")
                st.rerun()

# ------------------------------------------------------------------------------------------
# REGISTRAR SAÍDA (BAIXA)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Saída (Baixa)":
    st.header("❌ Registrar Saída")
    
    ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
    if not ativos:
        st.info("Nenhum animal ativo para dar baixa.")
    else:
        with st.form("form_saida", clear_on_submit=True):
            opcoes_baixa = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
            animal_selecionado = st.selectbox("Selecione o Animal", list(opcoes_baixa.keys()), format_func=lambda x: opcoes_baixa[x])
            motivo_saida = st.selectbox("Motivo da Saída", ["Morte", "Venda", "Doação"])
            data_saida = st.date_input("Data da Saída", datetime.today())
            detalhes_saida = st.text_area("Observações da Saída")
            
            enviar_baixa = st.form_submit_button("Registrar Saída (Baixa)", type="primary")
            
            if enviar_baixa:
                dados_rebanho[animal_selecionado]["status"] = motivo_saida
                dados_rebanho[animal_selecionado]["data_saida"] = str(data_saida)
                dados_rebanho[animal_selecionado]["motivo_saida"] = detalhes_saida
                salvar_dados(dados_rebanho)
                st.success("Baixa registrada com sucesso!")
                st.rerun()

# ------------------------------------------------------------------------------------------
# CONTROLE SANITÁRIO/MÉDICO
# ------------------------------------------------------------------------------------------
elif menu == "Controle Sanitário/Médico":
    st.header("🏥 Controle Sanitário")
    
    if not dados_rebanho:
        st.info("Cadastre animais primeiro.")
    else:
        tipo_manejo = st.radio("Tipo de Manejo", ["Individual", "Coletivo (Lote Todo)"])
        
        with st.form("form_saude", clear_on_submit=True):
            data_manejo = st.date_input("Data do Manejo", datetime.today())
            categoria_manejo = st.selectbox("Tipo de Evento", ["Vacinação Preventiva", "Vermifugação", "Tratamento de Doença (ex: Casco/Mastite)", "Avaliação Famacha", "Outro"])
            descricao_tratamento = st.text_input("Descrição / Medicamento")
            
            dose_tipo = "N/A"
            proxima_dose_data = "Não possui"
            
            if categoria_manejo == "Vacinação Preventiva":
                dose_tipo = st.selectbox("Esquema de Dose:", ["Dose Única", "1ª Dose", "2ª Dose"])
                if dose_tipo in ["1ª Dose", "2ª Dose"]:
                    proxima_dose_data = str(st.date_input("Data do Reforço", datetime.today()))
            
            elif categoria_manejo in ["Tratamento de Doença (ex: Casco/Mastite)", "Outro"]:
                tipo_tratamento_opcao = st.radio("Duração:", ["Ciclo Fechado", "Uso Contínuo"])
                if tipo_tratamento_opcao == "Uso Contínuo":
                    dose_tipo = "Uso Contínuo"
            
            possui_carencia = st.radio("Possui carência de abate?", ["Não", "Sim"])
            carencia_salvar = str(st.date_input("Fim da Carência", datetime.today())) if possui_carencia == "Sim" else "Não possui"
            
            if tipo_manejo == "Individual":
                opcoes_saude = {k: obter_nome_exibicao(k, v) for k, v in dados_rebanho.items()}
                animais_alvo = [st.selectbox("Selecione o Animal", list(opcoes_saude.keys()), format_func=lambda x: opcoes_saude[x])]
            else:
                animais_alvo = [k for k, v in dados_rebanho.items() if v["status"] == "Ativo"]
            
            enviar_saude = st.form_submit_button("Gravar Registro de Saúde", type="primary")
            
            if enviar_saude:
                if not descricao_tratamento.strip():
                    st.error("Descreva o medicamento/vacina.")
                elif not animais_alvo:
                    st.error("Nenhum animal selecionado.")
                else:
                    registro = {
                        "data": str(data_manejo),
                        "categoria": categoria_manejo,
                        "descricao": descricao_tratamento.strip(),
                        "dose_tipo": dose_tipo,
                        "proxima_dose": proxima_dose_data,
                        "carencia": carencia_salvar
                    }
                    for brinco in animais_alvo:
                        dados_rebanho[brinco]["historico_saude"].append(registro)
                    salvar_dados(dados_rebanho)
                    st.success("Manejo de saúde gravado!")
                    st.rerun()

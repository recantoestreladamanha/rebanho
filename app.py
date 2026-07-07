import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
import unicodedata
import base64
import tempfile
from supabase import create_client, Client

# Configuração da página do Streamlit
st.set_page_config(page_title="Recanto Estrela da Manhã - Gestão", page_icon="🐑", layout="wide")

ARQUIVO_LOGO = "logo.png"

# Geração de relatórios PDF com FPDF
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

def carregar_dados():
    if not supabase:
        return {}
    try:
        res = supabase.table("rebanho_dados").select("conteudo").eq("id", 1).execute()
        if res.data:
            return json.loads(res.data[0]["conteudo"])
        else:
            supabase.table("rebanho_dados").insert({"id": 1, "conteudo": "{}"}).execute()
            return {}
    except Exception:
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
# FUNÇÕES UTILITÁRIAS E MANEJO SANITÁRIA / PONDERAL
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
    if not ficha_animal:
        return id_brinco
    nome = ficha_animal.get("nome", "").strip()
    if nome:
        return f"{id_brinco} - {nome}"
    return id_brinco

def obter_peso_atual(ficha_animal):
    historico = ficha_animal.get("historico_pesos", [])
    if historico:
        historico_ordenado = sorted(historico, key=lambda x: x["data"])
        ultima = historico_ordenado[-1]
        try:
            dt_form = datetime.strptime(ultima["data"], "%Y-%m-%d").date().strftime("%d/%m/%Y")
        except:
            dt_form = ultima["data"]
        return f"{float(ultima['peso']):.1f} kg ({dt_form})"
    
    if float(ficha_animal.get("peso_entrada", 0.0)) > 0:
        try:
            dt_form = datetime.strptime(ficha_animal.get("data_chegada", ficha_animal["data_nascimento"]), "%Y-%m-%d").date().strftime("%d/%m/%Y")
        except:
            dt_form = "Entrada"
        return f"{float(ficha_animal['peso_entrada']):.1f} kg ({dt_form})"
        
    if float(ficha_animal.get("peso_nascer", 0.0)) > 0:
        try:
            dt_form = datetime.strptime(ficha_animal["data_nascimento"], "%Y-%m-%d").date().strftime("%d/%m/%Y")
        except:
            dt_form = "Nasc."
        return f"{float(ficha_animal['peso_nascer']):.1f} kg ({dt_form})"
        
    return "Não pesado"

def normalizar_sexo(sexo_str):
    if not sexo_str:
        return "Não informado"
    if "f" in sexo_str.lower() or "fê" in sexo_str.lower():
        return "Fêmea"
    return "Macho"

def verificar_status_vacinal(ficha_animal):
    historico = ficha_animal.get("historico_saude", [])
    vacinas_pendentes = []
    hoje = date.today()
    
    for h in historico:
        if h.get("dose_tipo", "") == "Uso Contínuo":
            return "🩺 CONTÍNUO", f"Tratamento contínuo: {h.get('descricao', '')}"
            
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

def montar_linha_tempo_pesos(ficha):
    """Gera uma lista estruturada e ordenada cronologicamente de todas as pesagens."""
    lista_pesos = []
    dt_nasc = ficha["data_nascimento"]
    dt_chegada = ficha.get("data_chegada", dt_nasc)
    
    if float(ficha.get("peso_nascer", 0.0)) > 0:
        lista_pesos.append({"data_ordem": dt_nasc, "Fase/Data": f"Nascimento ({datetime.strptime(dt_nasc, '%Y-%m-%d').strftime('%d/%m/%Y')})", "Peso (kg)": float(ficha["peso_nascer"]), "tipo": "base"})
        
    if float(ficha.get("peso_desmame", 0.0)) > 0:
        lista_pesos.append({"data_ordem": dt_nasc, "Fase/Data": "Desmame", "Peso (kg)": float(ficha["peso_desmame"]), "tipo": "base"})
    
    if float(ficha.get("peso_entrada", 0.0)) > 0:
        origem_tipo = ficha.get("origem", "Entrada")
        try:
            dt_entrada_form = datetime.strptime(dt_chegada, "%Y-%m-%d").date().strftime("%d/%m/%Y")
            rotulo_linha_tempo = f"{origem_tipo} ({dt_entrada_form})"
        except:
            rotulo_linha_tempo = f"{origem_tipo}"
        lista_pesos.append({"data_ordem": dt_chegada, "Fase/Data": rotulo_linha_tempo, "Peso (kg)": float(ficha["peso_entrada"]), "tipo": "base"})
        
    for idx, p in enumerate(ficha.get("historico_pesos", [])):
        try:
            dt_p_form = datetime.strptime(p['data'], "%Y-%m-%d").date().strftime("%d/%m/%Y")
        except:
            dt_p_form = p['data']
        lista_pesos.append({"data_ordem": p['data'], "Fase/Data": dt_p_form, "Peso (kg)": float(p['peso']), "tipo": "rotineiro", "original_idx": idx})
        
    # Ordenação Cronológica Definitiva por Data de Ocorrência
    lista_pesos.sort(key=lambda x: x["data_ordem"])
    return lista_pesos

# ------------------------------------------------------------------------------------------
# CLASSES E GERADORES DE RELATÓRIO PDF
# ------------------------------------------------------------------------------------------

if FPDF_DISPONIVEL:
    class PDFRelatorio(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, remover_acentos('RECANTO ESTRELA DA MANHA - GESTAO DE REBANHO'), 0, 1, 'C')
            self.set_font('Arial', 'I', 8)
            self.cell(0, 5, remover_acentos(f'Relatorio emitido em: {datetime.today().strftime("%d/%m/%Y %H:%M")}'), 0, 1, 'C')
            self.line(10, 26, 200, 26)
            self.ln(6)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, remover_acentos(f'Pagina {self.page_no()}'), 0, 0, 'C')

    def gerar_pdf_ativos(ativos):
        pdf = PDFRelatorio()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, remover_acentos('RELATORIO DE ANIMAIS ATIVOS NO REBANHO'), 0, 1, 'L')
        pdf.ln(4)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(40, 8, remover_acentos('Identificacao/Nome'), 1, 0, 'C')
        pdf.cell(35, 8, remover_acentos('Raca'), 1, 0, 'C')
        pdf.cell(30, 8, remover_acentos('Sexo'), 1, 0, 'C')
        pdf.cell(45, 8, remover_acentos('Idade'), 1, 0, 'C')
        pdf.cell(40, 8, remover_acentos('Peso Atual'), 1, 1, 'C')
        
        pdf.set_font('Arial', '', 9)
        for brinco, f in ativos.items():
            pdf.cell(40, 8, remover_acentos(obter_nome_exibicao(brinco, f)), 1, 0, 'C')
            pdf.cell(35, 8, remover_acentos(f['raca']), 1, 0, 'C')
            pdf.cell(30, 8, remover_acentos(normalizar_sexo(f['sexo'])), 1, 0, 'C')
            pdf.cell(45, 8, remover_acentos(calcular_idade(f['data_nascimento'])), 1, 0, 'C')
            pdf.cell(40, 8, remover_acentos(obter_peso_atual(f).split(" (")[0]), 1, 1, 'C')
            
        return pdf.output(dest='S').encode('latin1')

    def gerar_pdf_ficha_individual(brinco, ficha, todos_dados):
        pdf = PDFRelatorio()
        pdf.add_page()
        
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, remover_acentos(f'FICHA INDIVIDUAL - ANIMAL: {obter_nome_exibicao(brinco, ficha)}'), 0, 1, 'L')
        pdf.ln(3)
        
        if "foto_base64" in ficha and ficha["foto_base64"]:
            try:
                foto_data = base64.b64decode(ficha["foto_base64"])
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    temp_img.write(foto_data)
                    temp_img_path = temp_img.name
                pdf.image(temp_img_path, x=150, y=35, w=45, h=45)
                os.unlink(temp_img_path)
            except Exception:
                pass
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('1. Informacoes Cadastrais'), 'B', 1, 'L')
        pdf.ln(2)
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(95, 6, remover_acentos(f'Identificacao: {brinco}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Nome: {ficha.get("nome", "Nao informado")}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Raca: {ficha["raca"]}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Sexo: {normalizar_sexo(ficha["sexo"])}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Nascimento: {ficha["data_nascimento"]}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Idade: {calcular_idade(ficha["data_nascimento"])}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Origem: {ficha.get("origem", "Nao informada")}'), 0, 1)
        
        if ficha.get("data_chegada"):
            pdf.cell(95, 6, remover_acentos(f'Chegada/Compra: {ficha["data_chegada"]}'), 0, 1)
            
        pai_id = ficha.get("pai", "Não Informado")
        mae_id = ficha.get("mae", "Não Informado")
        pdf.cell(95, 6, remover_acentos(f'Pai: {obter_nome_exibicao(pai_id, todos_dados.get(pai_id, {}))}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Mae: {obter_nome_exibicao(mae_id, todos_dados.get(mae_id, {}))}'), 0, 1)
        pdf.ln(5)
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('2. Historico de Pesagens (Ordem Cronologica)'), 'B', 1, 'L')
        pdf.ln(2)
        
        pdf.set_font('Arial', '', 10)
        pesos_cronologicos = montar_linha_tempo_pesos(ficha)
        if not pesos_cronologicos:
            pdf.cell(0, 6, remover_acentos('Nenhum registro de peso encontrado.'), 0, 1)
        else:
            for p in pesos_cronologicos:
                pdf.cell(0, 6, remover_acentos(f"- {p['Fase/Data']}: {p['Peso (kg)']:.1f} kg"), 0, 1)
        pdf.ln(5)
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('3. Historico Sanitario e Tratamentos Medicos'), 'B', 1, 'L')
        pdf.ln(2)
        
        historico = ficha.get("historico_saude", [])
        if not historico:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 6, remover_acentos('Nenhum registro de saude encontrado para este animal.'), 0, 1)
        else:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(25, 7, remover_acentos('Data'), 1, 0, 'C')
            pdf.cell(40, 7, remover_acentos('Tipo'), 1, 0, 'C')
            pdf.cell(75, 7, remover_acentos('Descricao'), 1, 0, 'C')
            pdf.cell(50, 7, remover_acentos('Dose/Reforco'), 1, 1, 'C')
            
            pdf.set_font('Arial', '', 9)
            for h in historico:
                pdf.cell(25, 7, remover_acentos(h['data']), 1, 0, 'C')
                pdf.cell(40, 7, remover_acentos(h['categoria']), 1, 0, 'C')
                pdf.cell(75, 7, remover_acentos(h['descricao']), 1, 0, 'C')
                detalhe_dose = h.get('dose_tipo', 'N/A')
                if h.get('proxima_dose', '') and h['proxima_dose'] != 'Não possui':
                    detalhe_dose += f" (Ref: {h['proxima_dose']})"
                pdf.cell(50, 7, remover_acentos(detalhe_dose), 1, 1, 'C')
                
        return pdf.output(dest='S').encode('latin1')

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
    .animal-card {
        background-color: #1E1E24;
        border: 2px solid #3F404C;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 5px;
        color: #EAEAEA !important;
        font-size: 14px;
        line-height: 1.6;
    }
    .animal-card strong {
        color: #FFA500 !important;
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

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD)
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    
    if st.session_state.visualizar_brinco:
        id_sel = st.session_state.visualizar_brinco
        ficha = dados_rebanho[id_sel]
        
        st.button("⬅️ Voltar para a Lista de Animais", on_click=lambda: st.session_state.update({"visualizar_brinco": None}))
        st.header(f"🗂️ Ficha do Animal: {obter_nome_exibicao(id_sel, ficha)}")
        
        if FPDF_DISPONIVEL:
            try:
                pdf_bytes_ficha = gerar_pdf_ficha_individual(id_sel, ficha, dados_rebanho)
                st.download_button(
                    label="📥 Baixar Ficha Individual em PDF",
                    data=pdf_bytes_ficha,
                    file_name=f"ficha_{id_sel}.pdf",
                    mime="application/pdf",
                    key=f"download_ficha_{id_sel}"
                )
            except Exception as e:
                st.error(f"Erro ao compilar PDF da Ficha: {e}")
                
        st.markdown("---")
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
            st.markdown(f"**Identificação (Brinco):** {id_sel} | **Nome:** {ficha.get('nome', 'Não informado')}")
            st.markdown(f"**Raça:** {ficha['raca']} | **Sexo:** {normalizar_sexo(ficha['sexo'])}")
            st.markdown(f"**Idade (Tempo de Vida):** {calcular_idade(ficha['data_nascimento'])} *({ficha['data_nascimento']})*")
            st.markdown(f"**Forma de Entrada:** {ficha.get('origem', 'Não informada')}")
            if ficha.get("data_chegada"):
                st.markdown(f"**Data de Entrada no Recanto:** {ficha['data_chegada']}")
            
            p_id = ficha.get("pai", "Não Informado")
            m_id = ficha.get("mae", "Não Informado")
            st.markdown(f"**Mãe (Matriz):** {obter_nome_exibicao(m_id, dados_rebanho.get(m_id, {}))}")
            st.markdown(f"**Pai (Reprodutor):** {obter_nome_exibicao(p_id, dados_rebanho.get(p_id, {}))}")
            
            status_v, desc_v = verificar_status_vacinal(ficha)
            st.markdown(f"**Manejo Preventivo:** {status_v if status_v else 'Em dia'} ({desc_v})")
            
        st.markdown("---")
        aba_pesos, aba_saude, aba_crias, aba_notas, aba_editar = st.tabs(["⚖️ Histórico de Peso", "🏥 Histórico de Saúde", "🧬 Crias (Descendentes)", "📝 Notas de Campo", "✏️ Editar Cadastro"])
        
        with aba_pesos:
            st.subheader("Acompanhamento Ponderal (Controle de Peso)")
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                st.markdown("**Pesos Históricos de Fase**")
                peso_nasc = st.number_input("Peso ao Nascer (kg)", value=float(ficha.get("peso_nascer", 0.0)), step=0.1)
                peso_desm = st.number_input("Peso ao Desmame (kg)", value=float(ficha.get("peso_desmame", 0.0)), step=0.1)
                peso_ent_atualizar = st.number_input("Peso de Entrada no Recanto (kg)", value=float(ficha.get("peso_entrada", 0.0)), step=0.1)
                
                if st.button("💾 Atualizar Pesos de Fase"):
                    dados_rebanho[id_sel]["peso_nascer"] = peso_nasc
                    dados_rebanho[id_sel]["peso_desmame"] = peso_desm
                    dados_rebanho[id_sel]["peso_entrada"] = peso_ent_atualizar
                    salvar_dados(dados_rebanho)
                    st.success("Pesos base atualizados!")
                    st.rerun()
            
            with c_p2:
                st.markdown("**Registrar Nova Pesagem Rotineira (Evolução)**")
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
            
            st.markdown("#### Evolução do Crescimento (Ordem Cronológica)")
            lista_pesos_cronologica = montar_linha_tempo_pesos(ficha)
                
            if lista_pesos_cronologica:
                for item in lista_pesos_cronologica:
                    with st.container():
                        c_r1, c_r2 = st.columns([4, 2])
                        c_r1.write(f"**{item['Fase/Data']}** ➔ {item['Peso (kg)']:.1f} kg")
                        
                        if item["tipo"] == "rotineiro":
                            orig_idx = item["original_idx"]
                            if c_r2.button("🗑️ Remover", key=f"del_peso_{orig_idx}"):
                                dados_rebanho[id_sel]["historico_pesos"].pop(orig_idx)
                                salvar_dados(dados_rebanho)
                                st.success("Pesagem removida!")
                                st.rerun()
                        else:
                            c_r2.markdown("<span style='color: gray; font-size: 12px;'>Fixo do Cadastro</span>", unsafe_allow_html=True)
                
                st.markdown("#### 📈 Gráfico de Curva de Crescimento")
                df_grafico = pd.DataFrame(lista_pesos_cronologica)
                df_grafico['data_datetime'] = pd.to_datetime(df_grafico['data_ordem'])
                df_grafico = df_grafico.sort_values('data_datetime')
                df_grafico = df_grafico.rename(columns={"data_datetime": "Data Real", "Peso (kg)": "Peso do Animal (kg)"})
                st.line_chart(data=df_grafico, x="Data Real", y="Peso do Animal (kg)")
            else:
                st.info("Nenhum registro de peso encontrado.")

        with aba_saude:
            st.subheader("Histórico de Intervenções Clínicas")
            historico = ficha.get("historico_saude", [])
            if not historico:
                st.info("Nenhum prontuário sanitário encontrado.")
            else:
                exibir_lista = []
                for h in historico:
                    exibir_lista.append({
                        "Data": datetime.strptime(h['data'], "%Y-%m-%d").date().strftime("%d/%m/%Y"),
                        "Evento": h['categoria'],
                        "Descrição": h['descricao'],
                        "Dose": h.get('dose_tipo', 'N/A'),
                        "Liberação Carência": h.get('carencia', 'Não possui')
                    })
                st.dataframe(pd.DataFrame(exibir_lista), use_container_width=True)
                
        with aba_crias:
            st.subheader("🧬 Genealogia - Crias Diretas Registradas")
            filhos_encontrados = []
            
            for b_id, b_info in dados_rebanho.items():
                if b_info.get("mae") == id_sel or b_info.get("pai") == id_sel:
                    filhos_encontrados.append({
                        "Identificação / Brinco": b_id,
                        "Nome": b_info.get("nome", "Não informado"),
                        "Raça": b_info["raca"],
                        "Sexo": normalizar_sexo(b_info["sexo"]),
                        "Idade Atual": calcular_idade(b_info["data_nascimento"]),
                        "Situação": b_info["status"]
                    })
                    
            if filhos_encontrados:
                st.dataframe(pd.DataFrame(filhos_encontrados), use_container_width=True)
            else:
                st.info("Nenhuma cria direta registrada vinculada a este animal.")
                
        with aba_notas:
            st.subheader("Anotações Gerais")
            nova_obs = st.text_area("Observações importantes de campo:", value=ficha.get("observacoes", ""), height=150)
            if st.button("💾 Salvar Anotações"):
                dados_rebanho[id_sel]["observacoes"] = nova_obs
                salvar_dados(dados_rebanho)
                st.success("Anotações salvas!")
                st.rerun()

        with col_infos if False else aba_editar:
            st.subheader("✏️ Alterar Dados Cadastrais Completos")
            st.warning("Atenção: Ao alterar o número do brinco, o sistema reestruturará automaticamente o histórico vinculando-o à nova numeração.")
            
            lista_racas = ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)"]
            idx_raca = lista_racas.index(ficha["raca"]) if ficha["raca"] in lista_racas else 4
            
            sexo_atual = normalizar_sexo(ficha["sexo"])
            idx_sexo = 0 if sexo_atual == "Fêmea" else 1
            
            try:
                data_cadastrada_atual = datetime.strptime(ficha["data_nascimento"], "%Y-%m-%d").date()
            except:
                data_cadastrada_atual = date.today()
                
            try:
                data_chegada_atual = datetime.strptime(ficha.get("data_chegada", ficha["data_nascimento"]), "%Y-%m-%d").date()
            except:
                data_chegada_atual = date.today()

            with st.form(f"form_edicao_avancada_{id_sel}"):
                edit_brinco = st.text_input("Identificação (Brinco) *", value=id_sel)
                edit_nome = st.text_input("Nome / Alcunha do Animal", value=ficha.get("nome", ""))
                edit_data = st.date_input("Data de Nascimento Real", value=data_cadastrada_atual)
                
                if ficha.get("origem") != "Procriação (Nascimento)":
                    edit_data_chegada = st.date_input("Data de Chegada/Entrada na Propriedade", value=data_chegada_atual)
                else:
                    edit_data_chegada = None
                    
                edit_raca = st.selectbox("Raça", lista_racas, index=idx_raca)
                edit_sexo = st.radio("Sexo", ["Fêmea", "Macho"], index=idx_sexo, horizontal=True)
                
                if st.form_submit_button("💾 Salvar Alterações"):
                    novo_brinco_limpo = edit_brinco.strip()
                    
                    if not novo_brinco_limpo:
                        st.error("O brinco não pode ficar em branco.")
                    elif novo_brinco_limpo != id_sel and novo_brinco_limpo in dados_rebanho:
                        st.error(f"Erro: O brinco {novo_brinco_limpo} já pertence a outro animal do rebanho.")
                    else:
                        dados_atualizados_animal = ficha.copy()
                        dados_atualizados_animal["nome"] = edit_nome.strip()
                        dados_atualizados_animal["raca"] = edit_raca
                        dados_atualizados_animal["sexo"] = edit_sexo
                        dados_atualizados_animal["data_nascimento"] = str(edit_data)
                        if edit_data_chegada:
                            dados_atualizados_animal["data_chegada"] = str(edit_data_chegada)
                        
                        if novo_brinco_limpo != id_sel:
                            dados_rebanho[novo_brinco_limpo] = dados_atualizados_animal
                            del dados_rebanho[id_sel]
                            st.session_state.visualizar_brinco = novo_brinco_limpo
                        else:
                            dados_rebanho[id_sel] = dados_atualizados_animal
                            
                        salvar_dados(dados_rebanho)
                        st.success("Ficha cadastral actualizada com sucesso na nuvem!")
                        st.rerun()
                
    else:
        if not dados_rebanho:
            st.info("Nenhum animal em base de dados.")
        else:
            ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
            baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
            
            col_met, col_btn_pdf = st.columns([1, 1])
            with col_met:
                st.metric("Efetivo de Animais Ativos", len(ativos))
            
            with col_btn_pdf:
                if FPDF_DISPONIVEL and ativos:
                    try:
                        pdf_ativos_bytes = gerar_pdf_ativos(ativos)
                        st.download_button(
                            label="📥 Baixar Lista (PDF)",
                            data=pdf_ativos_bytes,
                            file_name=f"lista_ativos_{datetime.today().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="btn_pdf_ativos"
                        )
                    except Exception as e:
                        st.error(f"Erro ao gerar PDF do lote: {e}")
            
            tab_ativos, tab_inativos = st.tabs(["🟢 Animais Ativos", "🔴 Inativos / Baixas"])
            
            with tab_ativos:
                st.subheader("📋 Lista de Animais Ativos")
                
                if ativos:
                    lista_brincos_ativos = list(ativos.keys())
                    for i in range(0, len(lista_brincos_ativos), 3):
                        lote_brincos = lista_brincos_ativos[i:i+3]
                        colunas_grade = st.columns(3)
                        
                        for idx_col, brinco in enumerate(lote_brincos):
                            f_at = ativos[brinco]
                            status_v, desc_v = verificar_status_vacinal(f_at)
                            status_vacina_rotulo = status_v if status_v else "🟢 EM DIA"
                            
                            with colunas_grade[idx_col]:
                                st.markdown(f"""
                                <div class="animal-card">
                                    <strong>ID / Nome:</strong> {obter_nome_exibicao(brinco, f_at)}<br>
                                    <strong>Raça:</strong> {f_at['raca']}<br>
                                    <strong>Sexo:</strong> {normalizar_sexo(f_at['sexo'])}<br>
                                    <strong>Idade:</strong> {calcular_idade(f_at['data_nascimento'])}<br>
                                    <strong>Vacina:</strong> {status_vacina_rotulo}<br>
                                    <strong>Peso:</strong> {obter_peso_atual(f_at)}
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.button(f"🔎 Abrir Ficha ({brinco})", key=f"abrir_{brinco}")
                else:
                    st.warning("Nenhum animal ativo.")

            with tab_inativos:
                st.subheader("🪵 Animais Fora do Lote")
                if baixas:
                    lista_brincos_baixas = list(baixas.keys())
                    for i in range(0, len(lista_brincos_baixas), 3):
                        lote_baixas = lista_brincos_baixas[i:i+3]
                        colunas_grade_in = st.columns(3)
                        
                        for idx_col, brinco in enumerate(lote_baixas):
                            f_in = baixas[brinco]
                            with colunas_grade_in[idx_col]:
                                st.markdown(f"""
                                <div class="animal-card">
                                    <strong>ID / Nome:</strong> {obter_nome_exibicao(brinco, f_in)}<br>
                                    <strong>Raça:</strong> {f_in['raca']}<br>
                                    <strong>Sexo:</strong> {normalizar_sexo(f_in['sexo'])}<br>
                                    <strong>Motivo da Saída:</strong> {f_in['status']} ({f_in.get('data_saida', 'Não Informada')})
                                </div>
                                """, unsafe_allow_html=True)
                                st.button(f"🔎 Abrir Ficha ({brinco})", key=f"abrir_in_{brinco}")
                else:
                    st.info("Nenhuma baixa.")

# ------------------------------------------------------------------------------------------
# REGISTRAR ENTRADA (CADASTRO) - AJUSTADO COM DATA DE NASCIMENTO E DATA DE CHEGADA INDEPENDENTES
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Entrada (Cadastro)":
    st.header("➕ Registrar Entrada de Animal")
    
    origem_temp = st.selectbox("Forma de Entrada / Origem", ["Compra", "Procriação (Nascimento)", "Doação"], key="origem_seletor_topo")
    st.markdown("---")
    
    with st.form("form_entrada", clear_on_submit=True):
        id_brinco = st.text_input("Identificação (Brinco) *")
        nome_animal = st.text_input("Nome / Alcunha (Opcional)")
        raca = st.selectbox("Raça", ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)"])
        sexo = st.radio("Sexo", ["Fêmea", "Macho"], horizontal=True)
        
        # AJUSTE SOLICITADO: Data de Nascimento agora é fixa e obrigatória para qualquer origem
        data_nascimento = st.date_input("Data de Nascimento Real (Estimada ou Exata) *", datetime.today())
        
        # Exibe um segundo campo de data de chegada apenas se o animal vier de fora (Compra/Doação)
        if origem_temp != "Procriação (Nascimento)":
            data_chegada = st.date_input("Data de Chegada / Entrada na Propriedade", datetime.today())
        else:
            data_chegada = None
        
        st.markdown("#### 🧬 Controle Parental (Genealogia)")
        opcoes_maes = {"": "Selecione a matriz..."}
        opcoes_pais = {"Não Informado": "Não Informado"}
        
        for k, v in dados_rebanho.items():
            sexo_normalizado = normalizar_sexo(v.get("sexo", ""))
            if sexo_normalizado == "Fêmea":
                opcoes_maes[k] = obter_nome_exibicao(k, v)
            elif sexo_normalizado == "Macho":
                opcoes_pais[k] = obter_nome_exibicao(k, v)
        
        mae_selecionada = st.selectbox("Mãe (Matriz) *Obrigatório para Procriação*", list(opcoes_maes.keys()), format_func=lambda x: opcoes_maes[x])
        pai_selecionado = st.selectbox("Pai (Reprodutor)", list(opcoes_pais.keys()), format_func=lambda x: opcoes_pais[x])
        
        st.markdown("#### ⚖️ Pesagem de Entrada")
        peso_informado = st.number_input("Peso do Animal no momento da Entrada (kg) *", min_value=0.0, step=0.1)
        
        enviar = st.form_submit_button("Salvar Registro")
        
        if enviar:
            if not id_brinco.strip():
                st.error("Identificação obrigatória.")
            elif id_brinco in dados_rebanho:
                st.error("Animal já cadastrado com este brinco.")
            elif peso_informado <= 0:
                st.error("Por favor, informe o peso do animal.")
            elif origem_temp == "Procriação (Nascimento)" and not mae_selecionada:
                st.error("Para animais nascidos na propriedade (Procriação), a indicação da Mãe (Matriz) é obrigatória.")
            else:
                p_nasc = peso_informado if origem_temp == "Procriação (Nascimento)" else 0.0
                p_entrada = peso_informado if origem_temp != "Procriação (Nascimento)" else 0.0
                
                salvar_mae = mae_selecionada if origem_temp == "Procriação (Nascimento)" else "Não Informado"
                salvar_pai = pai_selecionado if origem_temp == "Procriação (Nascimento)" else "Não Informado"
                
                dados_rebanho[id_brinco] = {
                    "nome": nome_animal.strip(),
                    "raca": raca,
                    "sexo": sexo,
                    "data_nascimento": str(data_nascimento),
                    "data_chegada": str(data_chegada) if data_chegada else str(data_nascimento),
                    "origem": origem_temp,
                    "peso_nascer": p_nasc,
                    "peso_desmame": 0.0,
                    "peso_entrada": p_entrada,
                    "historico_pesos": [],
                    "pai": salvar_pai,
                    "mae": salvar_mae,
                    "status": "Ativo",
                    "foto_base64": "",
                    "observacoes": "",
                    "historico_saude": []
                }
                salvar_dados(dados_rebanho)
                st.success("Cadastro realizado com sucesso na nuvem!")
                st.rerun()

elif menu == "Registrar Saída (Baixa)":
    st.header("❌ Registrar Saída (Baixa)")
    ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
    if not ativos:
        st.info("Nenhum animal ativo para dar baixa.")
    else:
        with st.form("form_saida", clear_on_submit=True):
            options_baixa = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
            animal_selecionado = st.selectbox("Selecione o Animal", list(options_baixa.keys()), format_func=lambda x: options_baixa[x])
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
                options_saude = {k: obter_nome_exibicao(k, v) for k, v in dados_rebanho.items()}
                animais_alvo = [st.selectbox("Selecione o Animal", list(options_saude.keys()), format_func=lambda x: options_saude[x])]
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

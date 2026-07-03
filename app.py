import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import unicodedata

# Configuração da página do Streamlit - Otimizado para visualização fluida
st.set_page_config(page_title="Gestão de Ovinocultura MVP", page_icon="🐑", layout="wide")

ARQUIVO_DADOS = "rebanho.json"

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
    """
    Remove acentos e caracteres especiais para evitar erros de renderização 
    em PDFs que utilizam fontes padrão do sistema (como Helvetica ou Arial).
    """
    if not isinstance(texto, str):
        return str(texto)
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

# Função para calcular a idade de forma amigável
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

# Função para carregar os dados salvos
def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        try:
            with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# Função para salvar os dados
def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

# Função auxiliar para gerar rótulo bonito do animal (ID - Nome se houver)
def obter_nome_exibicao(id_brinco, ficha_animal):
    nome = ficha_animal.get("nome", "").strip()
    if nome:
        return f"{id_brinco} - {nome}"
    return id_brinco

# ------------------------------------------------------------------------------------------
# CLASSES E GERADORES DE RELATÓRIO PDF
# ------------------------------------------------------------------------------------------

if FPDF_DISPONIVEL:
    class PDFRelatorio(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, remover_acentos('SISTEMA DE GESTAO DE REBANHO OVINOTECNICO'), 0, 1, 'C')
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
        pdf.cell(35, 8, remover_acentos('Identificacao/Nome'), 1, 0, 'C')
        pdf.cell(40, 8, remover_acentos('Raca'), 1, 0, 'C')
        pdf.cell(35, 8, remover_acentos('Sexo'), 1, 0, 'C')
        pdf.cell(45, 8, remover_acentos('Idade'), 1, 0, 'C')
        pdf.cell(35, 8, remover_acentos('Origem'), 1, 1, 'C')
        
        pdf.set_font('Arial', '', 9)
        for brinco, f in ativos.items():
            pdf.cell(35, 8, remover_acentos(obter_nome_exibicao(brinco, f)), 1, 0, 'C')
            pdf.cell(40, 8, remover_acentos(f['raca']), 1, 0, 'C')
            pdf.cell(35, 8, remover_acentos(f['sexo']), 1, 0, 'C')
            pdf.cell(45, 8, remover_acentos(calcular_idade(f['data_nascimento'])), 1, 0, 'C')
            pdf.cell(35, 8, remover_acentos(f['origem']), 1, 1, 'C')
            
        return pdf.output(dest='S').encode('latin1')

    def gerar_pdf_inativos(baixas):
        pdf = PDFRelatorio()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, remover_acentos('RELATORIO DE BAIXAS E INATIVOS'), 0, 1, 'L')
        pdf.ln(4)
        
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(35, 8, remover_acentos('Identificacao/Nome'), 1, 0, 'C')
        pdf.cell(40, 8, remover_acentos('Raca'), 1, 0, 'C')
        pdf.cell(30, 8, remover_acentos('Sexo'), 1, 0, 'C')
        pdf.cell(45, 8, remover_acentos('Motivo da Saida'), 1, 0, 'C')
        pdf.cell(40, 8, remover_acentos('Data da Saida'), 1, 1, 'C')
        
        pdf.set_font('Arial', '', 9)
        for brinco, f in baixas.items():
            pdf.cell(35, 8, remover_acentos(obter_nome_exibicao(brinco, f)), 1, 0, 'C')
            pdf.cell(40, 8, remover_acentos(f['raca']), 1, 0, 'C')
            pdf.cell(30, 8, remover_acentos(f['sexo']), 1, 0, 'C')
            pdf.cell(45, 8, remover_acentos(f['status']), 1, 0, 'C')
            pdf.cell(40, 8, remover_acentos(f.get('data_saida', 'N/I')), 1, 1, 'C')
            
        return pdf.output(dest='S').encode('latin1')

    def gerar_pdf_ficha_individual(brinco, ficha, todos_dados):
        pdf = PDFRelatorio()
        pdf.add_page()
        
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, remover_acentos(f'FICHA INDIVIDUAL - ANIMAL: {obter_nome_exibicao(brinco, ficha)}'), 0, 1, 'L')
        pdf.ln(3)
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('1. Informacoes Cadastrais'), 'B', 1, 'L')
        pdf.ln(2)
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(95, 6, remover_acentos(f'Identificacao: {brinco}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Nome: {ficha.get("nome", "Nao informado")}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Raca: {ficha["raca"]}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Sexo: {ficha["sexo"]}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Nascimento: {ficha["data_nascimento"]}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Idade: {calcular_idade(ficha["data_nascimento"])}'), 0, 1)
        pdf.cell(95, 6, remover_acentos(f'Origem: {ficha["origem"]}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Situacao Atual: {ficha["status"]}'), 0, 1)
        
        pai_ficha = todos_dados.get(ficha["pai"], {}) if ficha["pai"] in todos_dados else {}
        mae_ficha = todos_dados.get(ficha["mae"], {}) if ficha["mae"] in todos_dados else {}
        pdf.cell(95, 6, remover_acentos(f'Pai: {obter_nome_exibicao(ficha["pai"], pai_ficha) if ficha["pai"] != "Não Informado" else "Não Informado"}'), 0, 0)
        pdf.cell(95, 6, remover_acentos(f'Mae: {obter_nome_exibicao(ficha["mae"], mae_ficha) if ficha["mae"] != "Não Informado" else "Não Informado"}'), 0, 1)
        pdf.ln(5)
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('2. Observacoes e Notas de Campo'), 'B', 1, 'L')
        pdf.ln(2)
        pdf.set_font('Arial', '', 10)
        obs = ficha.get("observacoes", "")
        if not obs:
            obs = "Nenhuma observacao registrada para este animal."
        pdf.multi_cell(0, 5, remover_acentos(obs))
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
            pdf.cell(45, 7, remover_acentos('Tipo de Manejo'), 1, 0, 'C')
            pdf.cell(85, 7, remover_acentos('Descricao / Medicamento'), 1, 0, 'C')
            pdf.cell(35, 7, remover_acentos('Carencia'), 1, 1, 'C')
            
            pdf.set_font('Arial', '', 9)
            for h in historico:
                pdf.cell(25, 7, remover_acentos(h['data']), 1, 0, 'C')
                pdf.cell(45, 7, remover_acentos(h['categoria']), 1, 0, 'C')
                pdf.cell(85, 7, remover_acentos(h['descricao']), 1, 0, 'C')
                pdf.cell(35, 7, remover_acentos(h['carencia']), 1, 1, 'C')
        pdf.ln(5)
        
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, remover_acentos('4. Crias Registradas (Descendentes)'), 'B', 1, 'L')
        pdf.ln(2)
        
        filhos = []
        for b_id, b_info in todos_dados.items():
            if b_info.get("pai") == brinco or b_info.get("mae") == brinco:
                filhos.append({
                    "Identificacao": b_id,
                    "NomeExib": obter_nome_exibicao(b_id, b_info),
                    "Raca": b_info["raca"],
                    "Sexo": b_info["sexo"],
                    "Idade": calcular_idade(b_info["data_nascimento"]),
                    "Status": b_info["status"]
                })
                
        if not filhos:
            pdf.set_font('Arial', 'I', 10)
            pdf.cell(0, 6, remover_acentos('Nenhuma cria direta registrada no sistema para este animal.'), 0, 1)
        else:
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(45, 7, remover_acentos('Animal (Identificacao/Nome)'), 1, 0, 'C')
            pdf.cell(35, 7, remover_acentos('Raca'), 1, 0, 'C')
            pdf.cell(35, 7, remover_acentos('Sexo'), 1, 0, 'C')
            pdf.cell(45, 7, remover_acentos('Idade'), 1, 0, 'C')
            pdf.cell(30, 7, remover_acentos('Status'), 1, 1, 'C')
            
            pdf.set_font('Arial', '', 9)
            for f in filhos:
                pdf.cell(45, 7, remover_acentos(f['NomeExib']), 1, 0, 'C')
                pdf.cell(35, 7, remover_acentos(f['Raca']), 1, 0, 'C')
                pdf.cell(35, 7, remover_acentos(f['Sexo']), 1, 0, 'C')
                pdf.cell(45, 7, remover_acentos(f['Idade']), 1, 0, 'C')
                pdf.cell(30, 7, remover_acentos(f['Status']), 1, 1, 'C')
                
        return pdf.output(dest='S').encode('latin1')

# ------------------------------------------------------------------------------------------
# INJEÇÃO DE CSS DE ADAPTABILIDADE MOBILE
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
    div[data-testid="column"] {
        padding: 5px !important;
        min-width: 150px !important;
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

dados_rebanho = st.session_state.rebanho

st.title("🐑 Sistema de Gerenciamento de Rebanho Ovino")
st.markdown("---")

menu = st.sidebar.selectbox(
    "Navegação",
    ["Painel Geral (Dashboard)", "Registrar Entrada (Cadastro)", "Registrar Saída (Baixa)", "Controle Sanitário/Médico"]
)

if menu != "Painel Geral (Dashboard)":
    st.session_state.visualizar_brinco = None

if not FPDF_DISPONIVEL:
    st.sidebar.warning("⚠️ **Geração de PDF Desativada**\n\nAdicione `fpdf` ao seu arquivo `requirements.txt` no GitHub.")

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD)
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    
    if st.session_state.visualizar_brinco:
        id_sel = st.session_state.visualizar_brinco
        ficha = dados_rebanho[id_sel]
        
        st.button("⬅️ Voltar para a Lista de Animais", on_click=lambda: st.session_state.update({"visualizar_brinco": None}))
        st.header(f"🗂️ Ficha do Animal: {obter_nome_exibicao(id_sel, ficha)}")
        
        col_pdf_f, col_ret_f = st.columns([1, 1])
        with col_pdf_f:
            if FPDF_DISPONIVEL:
                try:
                    pdf_bytes_ficha = gerar_pdf_ficha_individual(id_sel, ficha, dados_rebanho)
                    st.download_button(
                        label="📥 Baixar Ficha em PDF",
                        data=pdf_bytes_ficha,
                        file_name=f"ficha_individual_{id_sel}.pdf",
                        mime="application/pdf",
                        key=f"download_ficha_{id_sel}"
                    )
                except Exception as e:
                    st.error(f"Erro ao compilar PDF: {e}")
        
        col_esquerda, col_direita = st.columns(2)
        
        with col_esquerda:
            st.subheader("📋 Informações Cadastrais")
            st.markdown(f"**Identificação (ID/Brinco):** {id_sel}")
            st.markdown(f"**Nome:** {ficha.get('nome', 'Não informado')}")
            st.markdown(f"**Raça:** {ficha['raca']}")
            st.markdown(f"**Sexo:** {ficha['sexo']}")
            st.markdown(f"**Data de Nascimento:** {ficha['data_nascimento']} *({calcular_idade(ficha['data_nascimento'])})*")
            st.markdown(f"**Forma de Entrada:** {ficha['origem']}")
            
            pai_f = dados_rebanho.get(ficha["pai"], {})
            mae_f = dados_rebanho.get(ficha["mae"], {})
            st.markdown(f"**Pai (Reprodutor):** {obter_nome_exibicao(ficha['pai'], pai_f) if ficha['pai'] != 'Não Informado' else 'Não Informado'}")
            st.markdown(f"**Mãe (Matriz):** {obter_nome_exibicao(ficha['mae'], mae_f) if ficha['mae'] != 'Não Informado' else 'Não Informado'}")
            st.markdown(f"**Situação Atual:** :green[{ficha['status']}]" if ficha['status'] == "Ativo" else f":red[Baixa ({ficha['status']})]")
            
            if ficha['status'] != "Ativo":
                st.warning(f"⚠️ **Este animal está inativo no rebanho.**\n\n"
                           f"**Motivo da Saída:** {ficha['status']}\n\n"
                           f"**Data da Saída:** {ficha.get('data_saida', 'Não informada')}\n\n"
                           f"**Detalhes da Saída:** {ficha.get('motivo_saida', 'Não informado')}")
                
                if st.button("🔄 Reativar este Animal (Retornar ao Rebanho)", key=f"reativar_ficha_{id_sel}"):
                    dados_rebanho[id_sel]["status"] = "Ativo"
                    dados_rebanho[id_sel]["data_saida"] = ""
                    dados_rebanho[id_sel]["motivo_saida"] = ""
                    salvar_dados(dados_rebanho)
                    st.success(f"O animal {id_sel} foi reativado com sucesso!")
                    st.rerun()
        
        with col_direita:
            st.subheader("📝 Observações e Anotações Gerais")
            obs_atual = ficha.get("observacoes", "")
            nova_obs = st.text_area("Insira aqui anotações importantes", value=obs_atual, height=150)
            
            if st.button("💾 Salvar Anotações"):
                dados_rebanho[id_sel]["observacoes"] = nova_obs
                salvar_dados(dados_rebanho)
                st.success("Anotações salvas com sucesso!")
                st.rerun()
                
        st.markdown("---")
        aba_saude, aba_crias = st.tabs(["🏥 Histórico de Saúde", "🧬 Crias (Descendentes)"])
        
        with aba_saude:
            st.subheader("Histórico Médico e Sanitário")
            historico = ficha.get("historico_saude", [])
            if not historico:
                st.info("Nenhum registro de saúde encontrado para este animal.")
            else:
                df_saude = pd.DataFrame(historico)
                df_saude.columns = ["Data", "Tipo de Evento", "Descrição / Medicamento", "Período de Carência"]
                st.table(df_saude)
                
        with aba_crias:
            st.subheader("Genealogia - Filhos Cadastrados")
            filhos = []
            for b_id, b_info in dados_rebanho.items():
                if b_info.get("pai") == id_sel or b_info.get("mae") == id_sel:
                    filhos.append({
                        "Identificação": b_id,
                        "Nome": b_info.get("nome", "Não informado"),
                        "Raça": b_info["raca"],
                        "Sexo": b_info["sexo"],
                        "Idade": calcular_idade(b_info["data_nascimento"]),
                        "Status": b_info["status"]
                    })
            if not filhos:
                st.info("Nenhum descendente direto cadastrado para este animal.")
            else:
                df_filhos = pd.DataFrame(filhos)
                st.dataframe(df_filhos, use_container_width=True, hide_index=True)
                
    else:
        st.header("📊 Painel Geral do Rebanho")
        
        if not dados_rebanho:
            st.info("Nenhum animal cadastrado no momento.")
        else:
            ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
            baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Animais Ativos", len(ativos))
            col2.metric("Baixas Registradas", len(baixas))
            col3.metric("Cadastro Histórico", len(dados_rebanho))
            
            tab_ativos, tab_inativos = st.tabs(["🟢 Animais Ativos", "🔴 Animais Inativos (Baixas)"])
            
            with tab_ativos:
                st.subheader("📋 Lista de Animais Ativos no Rebanho")
                col_busca, col_pdf_ativos = st.columns([2, 1])
                with col_busca:
                    opcoes_busca = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
                    busca_id = st.selectbox("🔍 Busca Rápida de Animal Ativo:", ["Selecione..."] + list(opcoes_busca.keys()), format_func=lambda x: opcoes_busca.get(x, x), key="busca_ativo_mobile")
                    if busca_id != "Selecione...":
                        st.session_state.visualizar_brinco = busca_id
                        st.rerun()
                
                with col_pdf_ativos:
                    if FPDF_DISPONIVEL and ativos:
                        try:
                            pdf_ativos_bytes = gerar_pdf_ativos(ativos)
                            st.download_button(
                                label="📥 Baixar Relatório (PDF)",
                                data=pdf_ativos_bytes,
                                file_name=f"animais_ativos_{datetime.today().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="btn_pdf_ativos"
                            )
                        except Exception as e:
                            st.error(f"Erro de PDF: {e}")
                
                st.markdown("---")
                if ativos:
                    c_head = st.columns([2, 2, 2, 2.5, 1.5])
                    c_head[0].markdown("**Identificação / Nome**")
                    c_head[1].markdown("**Raça**")
                    c_head[2].markdown("**Sexo**")
                    c_head[3].markdown("**Idade**")
                    c_head[4].markdown("**Ações**")
                    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                    
                    for brinco, f_at in ativos.items():
                        c_row = st.columns([2, 2, 2, 2.5, 1.5])
                        c_row[0].write(obter_nome_exibicao(brinco, f_at))
                        c_row[1].write(f_at["raca"])
                        c_row[2].write(f_at["sexo"])
                        c_row[3].write(calcular_idade(f_at["data_nascimento"]))
                        if c_row[4].button("🔎 Ficha", key=f"abrir_{brinco}"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                        st.markdown("<div style='border-bottom: 1px solid #f0f2f6; margin: 4px 0;'></div>", unsafe_allow_html=True)
                else:
                    st.warning("Não há animais ativos no momento.")
            
            with tab_inativos:
                st.subheader("🪵 Histórico de Baixas")
                col_busca_in, col_pdf_inativos = st.columns([2, 1])
                with col_busca_in:
                    opcoes_busca_in = {k: obter_nome_exibicao(k, v) for k, v in baixas.items()}
                    busca_id_in = st.selectbox("🔍 Busca Rápida de Inativo:", ["Selecione..."] + list(opcoes_busca_in.keys()), format_func=lambda x: opcoes_busca_in.get(x, x), key="busca_inativo_mobile")
                    if busca_id_in != "Selecione...":
                        st.session_state.visualizar_brinco = busca_id_in
                        st.rerun()
                
                with col_pdf_inativos:
                    if FPDF_DISPONIVEL and baixas:
                        try:
                            pdf_inativos_bytes = gerar_pdf_inativos(baixas)
                            st.download_button(
                                label="📥 Baixar Relatório (PDF)",
                                data=pdf_inativos_bytes,
                                file_name=f"animais_inativos_{datetime.today().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                key="btn_pdf_inativos"
                            )
                        except Exception as e:
                            st.error(f"Erro de PDF: {e}")
                
                st.markdown("---")
                if baixas:
                    c_head_in = st.columns([2, 2, 1.5, 2.5, 2])
                    c_head_in[0].markdown("**Identificação / Nome**")
                    c_head_in[1].markdown("**Raça**")
                    c_head_in[2].markdown("**Sexo**")
                    c_head_in[3].markdown("**Motivo/Data**")
                    c_head_in[4].markdown("**Ações**")
                    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                    
                    for brinco, f_in in baixas.items():
                        c_row_in = st.columns([2, 2, 1.5, 2.5, 2])
                        c_row_in[0].write(obter_nome_exibicao(brinco, f_in))
                        c_row_in[1].write(f_in["raca"])
                        c_row_in[2].write(f_in["sexo"])
                        motivo_data = f"{f_in['status']} ({f_in.get('data_saida', 'N/I')})"
                        c_row_in[3].write(motivo_data)
                        
                        with c_row_in[4]:
                            if st.button("🔎 Ficha", key=f"abrir_in_{brinco}"):
                                st.session_state.visualizar_brinco = brinco
                                st.rerun()
                            if st.button("🔄 Reativar", key=f"reativar_in_{brinco}"):
                                dados_rebanho[brinco]["status"] = "Ativo"
                                dados_rebanho[brinco]["data_saida"] = ""
                                dados_rebanho[brinco]["motivo_saida"] = ""
                                salvar_dados(dados_rebanho)
                                st.success(f"O animal {brinco} foi reativado com sucesso!")
                                st.rerun()
                        st.markdown("<div style='border-bottom: 1px solid #f0f2f6; margin: 4px 0;'></div>", unsafe_allow_html=True)
                else:
                    st.info("Nenhuma baixa cadastrada.")

# ------------------------------------------------------------------------------------------
# REGISTRAR ENTRADA (CADASTRO)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Entrada (Cadastro)":
    st.header("➕ Registrar Entrada de Animal")
    
    with st.form("form_entrada", clear_on_submit=True):
        col_id, col_nome = st.columns(2)
        with col_id:
            id_brinco = st.text_input("Identificação *")
        with col_nome:
            nome_animal = st.text_input("Nome (Opcional)")
            
        raca = st.selectbox("Raça", ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)", "Outra"])
        sexo = st.radio("Sexo", ["Fêmea (Matriz/Borrega)", "Macho (Reprodutor/Borrego)"], horizontal=True)
        data_nascimento = st.date_input("Data de Nascimento/Entrada", datetime.today())
        origem = st.selectbox("Forma de Entrada", ["Procriação (Nascimento)", "Compra", "Doação"])
        
        st.markdown("### 🧬 Controle Parental (Genealogia)")
        
        # Mapeamento de nomes de exibição para a seleção de pais
        opcoes_pais = {"Não Informado": "Não Informado"}
        for k, v in dados_rebanho.items():
            opcoes_pais[k] = obter_nome_exibicao(k, v)
            
        pai = st.selectbox("Pai (Reprodutor)", list(opcoes_pais.keys()), format_func=lambda x: opcoes_pais[x])
        mae = st.selectbox("Mãe (Matriz)", list(opcoes_pais.keys()), format_func=lambda x: opcoes_pais[x])
        
        enviar = st.form_submit_button("Salvar Cadastro")
        
        if enviar:
            if not id_brinco.strip():
                st.error("O campo Identificação é obrigatório.")
            elif id_brinco in dados_rebanho:
                st.error(f"Já existe um animal cadastrado com a Identificação {id_brinco}.")
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
                st.success(f"Animal {obter_nome_exibicao(id_brinco, dados_rebanho[id_brinco])} cadastrado com sucesso!")
                st.rerun()

# ------------------------------------------------------------------------------------------
# REGISTRAR SAÍDA (BAIXA)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Saída (Baixa)":
    st.header("❌ Registrar Saída do Rebanho (Baixa)")
    
    ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
    
    if not ativos:
        st.info("Não há animais ativos cadastrados para dar baixa.")
    else:
        with st.form("form_saida", clear_on_submit=True):
            opcoes_baixa = {k: obter_nome_exibicao(k, v) for k, v in ativos.items()}
            animal_selecionado = st.selectbox("Selecione o Animal", list(opcoes_baixa.keys()), format_func=lambda x: opcoes_baixa[x])
            motivo_saida = st.selectbox("Motivo da Saída", ["Morte", "Venda", "Doação"])
            data_saida = st.date_input("Data da Saída", datetime.today())
            detalhes_saida = st.text_area("Observações adicionais")
            
            enviar_baixa = st.form_submit_button("Registrar Baixa")
            
            if enviar_baixa:
                dados_rebanho[animal_selecionado]["status"] = motivo_saida
                dados_rebanho[animal_selecionado]["data_saida"] = str(data_saida)
                dados_rebanho[animal_selecionado]["motivo_saida"] = detalhes_saida
                salvar_dados(dados_rebanho)
                st.success(f"Baixa do animal {obter_nome_exibicao(animal_selecionado, dados_rebanho[animal_selecionado])} registrada com sucesso!")
                st.rerun()

# ------------------------------------------------------------------------------------------
# CONTROLE SANITÁRIO/MÉDICO
# ------------------------------------------------------------------------------------------
elif menu == "Controle Sanitário/Médico":
    st.header("🏥 Controle Sanitário e Tratamentos Médicos")
    
    if not dados_rebanho:
        st.info("Cadastre animais primeiro para poder registrar manejos de saúde.")
    else:
        tipo_manejo = st.radio("Tipo de Manejo", ["Individual (Tratamento Médico / Famacha)", "Coletivo (Vacinação / Vermifugação de todo o lote)"], horizontal=True)
        
        with st.form("form_saude", clear_on_submit=True):
            data_manejo = st.date_input("Data do Manejo", datetime.today())
            categoria_manejo = st.selectbox("Tipo de Evento", ["Vacinação Preventiva", "Vermifugação", "Tratamento de Doença (ex: Casco/Mastite)", "Avaliação Famacha", "Outro"])
            descricao_tratamento = st.text_input("Descrição")
            carencia = st.text_input("Período de Carência", value="Não possui")
            
            if tipo_manejo.startswith("Individual"):
                opcoes_saude = {k: obter_nome_exibicao(k, v) for k, v in dados_rebanho.items()}
                animais_alvo = [st.selectbox("Selecione o Animal", list(opcoes_saude.keys()), format_func=lambda x: opcoes_saude[x])]
            else:
                animais_alvo = [k for k, v in dados_rebanho.items() if v["status"] == "Ativo"]
            
            enviar_saude = st.form_submit_button("Gravar Registro de Saúde")
            
            if enviar_saude:
                os_descricao = descricao_tratamento.strip()
                if not os_descricao:
                    st.error("Por favor, descreva o tratamento ou vacina aplicado.")
                elif not animais_alvo:
                    st.error("Nenhum animal selecionado ou ativo.")
                else:
                    registro = {
                        "data": str(data_manejo),
                        "categoria": categoria_manejo,
                        "descricao": os_descricao,
                        "carencia": carencia
                    }
                    for brinco in animais_alvo:
                        dados_rebanho[brinco]["historico_saude"].append(registro)
                    salvar_dados(dados_rebanho)
                    st.success(f"Registro de saúde adicionado com sucesso!")
                    st.rerun()
                    
        st.markdown("---")
        st.subheader("🔍 Consultar Histórico de Saúde Individual")
        opcoes_consulta = {k: obter_nome_exibicao(k, v) for k, v in dados_rebanho.items()}
        animal_consulta = st.selectbox("Selecione um animal para ver a ficha médica", [""] + list(opcoes_consulta.keys()), format_func=lambda x: opcoes_consulta.get(x, "Selecione..."))
        
        if animal_consulta:
            historico = dados_rebanho[animal_consulta]["historico_saude"]
            if not historico:
                st.info("Nenhum registro de saúde encontrado para este animal.")
            else:
                df_saude = pd.DataFrame(historico)
                df_saude.columns = ["Data", "Tipo de Evento", "Descrição / Medicamento", "Período de Carência"]
                st.table(df_saude)

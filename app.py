import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# Configuração da página do Streamlit
st.set_page_config(page_title="Gestão de Ovinocultura MVP", page_icon="🐑", layout="wide")

ARQUIVO_DADOS = "rebanho.json"

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

# Inicializar dados na sessão do Streamlit
if "rebanho" not in st.session_state:
    st.session_state.rebanho = carregar_dados()

dados_rebanho = st.session_state.rebanho

# Título Principal
st.title("🐑 Sistema de Gerenciamento de Rebanho Ovino")
st.markdown("---")

# Menu Lateral para Navegação
menu = st.sidebar.selectbox(
    "Navegação",
    ["Painel Geral (Dashboard)", "Registrar Entrada (Cadastro)", "Registrar Saída (Baixa)", "Controle Sanitário/Médico"]
)

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD)
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    st.header("📊 Painel Geral do Rebanho")
    
    if not dados_rebanho:
        st.info("Nenhum animal cadastrado no momento. Vá em 'Registrar Entrada' para começar.")
    else:
        # Filtrar ativos
        ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
        baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
        
        # Métricas rápidas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Animais Ativos", len(ativos))
        col2.metric("Total de Baixas (Vendas/Mortes)", len(baixas))
        col3.metric("Total Histórico Registrado", len(dados_rebanho))
        
        st.subheader("📋 Lista de Animais Ativos no Rebanho")
        if ativos:
            df = pd.DataFrame.from_dict(ativos, orient="index")
            # Reorganizar colunas para exibição bonita
            df.index.name = "ID / Brinco"
            colunas_exibicao = ["raca", "sexo", "data_nascimento", "origem", "pai", "mae"]
            st.dataframe(df[colunas_exibicao], use_container_width=True)
        else:
            st.warning("Não há animais ativos no momento.")

# ------------------------------------------------------------------------------------------
# REGISTRAR ENTRADA (CADASTRO)
# ------------------------------------------------------------------------------------------
elif menu == "Registrar Entrada (Cadastro)":
    st.header("➕ Registrar Entrada de Animal")
    
    with st.form("form_entrada", clear_on_submit=True):
        id_brinco = st.text_input("Identificação Única (Brinco, Tatuagem ou Chip) *")
        raca = st.selectbox("Raça", ["Santa Inês", "Dorper", "Texel", "Suffolk", "Sem Raça Definida (SRD)", "Outra"])
        sexo = st.radio("Sexo", ["Fêmea (Matriz/Borrega)", "Macho (Reprodutor/Borrego)"], horizontal=True)
        data_nascimento = st.date_input("Data de Nascimento/Entrada", datetime.today())
        origem = st.selectbox("Forma de Entrada", ["Procriação (Nascimento)", "Compra", "Doação"])
        
        st.markdown("### 🧬 Controle Parental (Genealogia)")
        # Lista animais já existentes para serem pais
        lista_animais = ["Não Informado"] + list(dados_rebanho.keys())
        pai = st.selectbox("Pai (Reprodutor)", lista_animais)
        mae = st.selectbox("Mãe (Matriz)", lista_animais)
        
        enviar = st.form_submit_button("Salvar Cadastro")
        
        if enviar:
            if not id_brinco.strip():
                st.error("O campo Identificação Única (Brinco) é obrigatório.")
            elif id_brinco in dados_rebanho:
                st.error(f"Já existe um animal cadastrado com o Brinco {id_brinco}.")
            else:
                # Criar a ficha do animal
                dados_rebanho[id_brinco] = {
                    "raca": raca,
                    "sexo": sexo,
                    "data_nascimento": str(data_nascimento),
                    "origem": origem,
                    "pai": pai,
                    "mae": mae,
                    "status": "Ativo",
                    "motivo_saida": "",
                    "data_saida": "",
                    "historico_saude": []
                }
                salvar_dados(dados_rebanho)
                st.success(f"Animal {id_brinco} cadastrado com sucesso!")
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
            animal_selecionado = st.selectbox("Selecione o Animal (Brinco)", list(ativos.keys()))
            motivo_saida = st.selectbox("Motivo da Saída", ["Morte", "Venda", "Doação"])
            data_saida = st.date_input("Data da Saída", datetime.today())
            detalhes_saida = st.text_area("Observações adicionais (ex: Causa da morte ou valor da venda)")
            
            enviar_baixa = st.form_submit_button("Registrar Baixa")
            
            if enviar_baixa:
                dados_rebanho[animal_selecionado]["status"] = motivo_saida
                dados_rebanho[animal_selecionado]["data_saida"] = str(data_saida)
                dados_rebanho[animal_selecionado]["motivo_saida"] = detalhes_saida
                salvar_dados(dados_rebanho)
                st.success(f"Baixa do animal {animal_selecionado} registrada com sucesso!")
                st.rerun()

# ------------------------------------------------------------------------------------------
# CONTROLE SANITÁRIO/MÉDICO
# ------------------------------------------------------------------------------------------
elif menu == "Controle Sanitário/Médico":
    st.header("🏥 Controle Sanitário e Tratamentos Médicos")
    
    if not dados_rebanho:
        st.info("Cadastre animais primeiro para poder registrar manejos de saúde.")
    else:
        # Escolha do manejo: Individual ou Coletivo
        tipo_manejo = st.radio("Tipo de Manejo", ["Individual (Tratamento Médico / Famacha)", "Coletivo (Vacinação / Vermifugação de todo o lote)"], horizontal=True)
        
        with st.form("form_saude", clear_on_submit=True):
            data_manejo = st.date_input("Data do Manejo", datetime.today())
            categoria_manejo = st.selectbox("Tipo de Evento", ["Vacinação Preventiva", "Vermifugação", "Tratamento de Doença (ex: Casco/Mastite)", "Avaliação Famacha", "Outro"])
            descricao_tratamento = st.text_input("Descrição (ex: Vacina Clostridiose, Aplicação de Ivomec, Tratamento com Antibiótico)")
            carencia = st.text_input("Período de Carência (Tempo sem abater/consumir leite)", value="Não possui")
            
            # Se for individual, seleciona o animal
            if tipo_manejo.startswith("Individual"):
                animais_alvo = [st.selectbox("Selecione o Animal (Brinco)", list(dados_rebanho.keys()))]
            else:
                # Se for coletivo, aplica a todos os ativos
                animais_alvo = [k for k, v in dados_rebanho.items() if v["status"] == "Ativo"]
            
            enviar_saude = st.form_submit_button("Gravar Registro de Saúde")
            
            if enviar_saude:
                if not descricao_tratamento.strip():
                    st.error("Por favor, descreva o tratamento ou vacina aplicado.")
                elif not animais_alvo:
                    st.error("Nenhum animal selecionado ou ativo para receber o manejo.")
                else:
                    registro = {
                        "data": str(data_manejo),
                        "categoria": category_manejo if 'category_manejo' in locals() else categoria_manejo,
                        "descricao": descricao_tratamento,
                        "carencia": carencia
                    }
                    
                    for brinco in animais_alvo:
                        dados_rebanho[brinco]["historico_saude"].append(registro)
                        
                    salvar_dados(dados_rebanho)
                    st.success(f"Registro de saúde adicionado com sucesso para {len(animais_alvo)} animal(ais)!")
                    st.rerun()
                    
        # Seção para consultar o histórico de um animal específico
        st.markdown("---")
        st.subheader("🔍 Consultar Histórico de Saúde Individual")
        animal_consulta = st.selectbox("Selecione um animal para ver a ficha médica", [""] + list(dados_rebanho.keys()))
        
        if animal_consulta:
            historico = dados_rebanho[animal_consulta]["historico_saude"]
            if not historico:
                st.info("Nenhum registro de saúde encontrado para este animal.")
            else:
                df_saude = pd.DataFrame(historico)
                df_saude.columns = ["Data", "Tipo de Evento", "Descrição / Medicamento", "Período de Carência"]
                st.table(df_saude)

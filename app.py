import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

# Configuração da página do Streamlit
st.set_page_config(page_title="Gestão de Ovinocultura MVP", page_icon="🐑", layout="wide")

ARQUIVO_DADOS = "rebanho.json"

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
        return f"{anos} ano(s) e {meses_restantes} mês(es)"
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

# Inicializar dados na sessão do Streamlit
if "rebanho" not in st.session_state:
    st.session_state.rebanho = carregar_dados()

# Inicializar estado para controle de visualização de ficha individual
if "visualizar_brinco" not in st.session_state:
    st.session_state.visualizar_brinco = None

dados_rebanho = st.session_state.rebanho

# Título Principal
st.title("🐑 Sistema de Gerenciamento de Rebanho Ovino")
st.markdown("---")

# Menu Lateral para Navegação
menu = st.sidebar.selectbox(
    "Navegação",
    ["Painel Geral (Dashboard)", "Registrar Entrada (Cadastro)", "Registrar Saída (Baixa)", "Controle Sanitário/Médico"]
)

# Se o usuário mudar de aba, limpamos a visualização de ficha individual para não travar a tela
if menu != "Painel Geral (Dashboard)":
    st.session_state.visualizar_brinco = None

# ------------------------------------------------------------------------------------------
# PAINEL GERAL (DASHBOARD)
# ------------------------------------------------------------------------------------------
if menu == "Painel Geral (Dashboard)":
    
    # Caso um animal tenha sido selecionado para ver a Ficha
    if st.session_state.visualizar_brinco:
        id_sel = st.session_state.visualizar_brinco
        ficha = dados_rebanho[id_sel]
        
        st.button("⬅️ Voltar para a Lista de Animais", on_click=lambda: st.session_state.update({"visualizar_brinco": None}))
        
        st.header(f"🗂️ Ficha do Animal: Brinco {id_sel}")
        
        # Estrutura em colunas: Info Geral na Esquerda, Campo de Notas na Direita
        col_esquerda, col_direita = st.columns(2)
        
        with col_esquerda:
            st.subheader("📋 Informações Cadastrais")
            st.markdown(f"**Raça:** {ficha['raca']}")
            st.markdown(f"**Sexo:** {ficha['sexo']}")
            st.markdown(f"**Data de Nascimento:** {ficha['data_nascimento']} *({calcular_idade(ficha['data_nascimento'])})*")
            st.markdown(f"**Forma de Entrada:** {ficha['origem']}")
            st.markdown(f"**Pai (Reprodutor):** {ficha['pai']}")
            st.markdown(f"**Mãe (Matriz):** {ficha['mae']}")
            st.markdown(f"**Situação Atual:** :green[{ficha['status']}]" if ficha['status'] == "Ativo" else f":red[Baixa ({ficha['status']})]")
            
            # Se for um animal baixado (inativo), exibir os detalhes da saída e a opção de reativar
            if ficha['status'] != "Ativo":
                st.warning(f"⚠️ **Este animal está inativo (fora do rebanho).**\n\n"
                           f"**Motivo da Saída:** {ficha['status']}\n\n"
                           f"**Data da Saída:** {ficha.get('data_saida', 'Não informada')}\n\n"
                           f"**Detalhes/Observações da Saída:** {ficha.get('motivo_saida', 'Não informado')}")
                
                if st.button("🔄 Reativar este Animal (Retornar ao Rebanho)", key=f"reativar_ficha_{id_sel}"):
                    dados_rebanho[id_sel]["status"] = "Ativo"
                    dados_rebanho[id_sel]["data_saida"] = ""
                    dados_rebanho[id_sel]["motivo_saida"] = ""
                    salvar_dados(dados_rebanho)
                    st.success(f"O animal {id_sel} foi reativado e agora consta como Ativo no rebanho!")
                    st.rerun()
        
        with col_direita:
            st.subheader("📝 Observações e Anotações Gerais")
            # Carrega observações existentes ou inicia em branco
            obs_atual = ficha.get("observacoes", "")
            nova_obs = st.text_area("Insira aqui anotações importantes (comportamento, partos, etc.)", value=obs_atual, height=150)
            
            if st.button("💾 Salvar Anotações"):
                dados_rebanho[id_sel]["observacoes"] = nova_obs
                salvar_dados(dados_rebanho)
                st.success("Anotações salvas com sucesso!")
                st.rerun()
                
        st.markdown("---")
        
        # Abas de histórico dentro da própria ficha
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
            # Buscar todos os animais onde este animal é Pai ou Mãe
            filhos = []
            for b_id, b_info in dados_rebanho.items():
                if b_info.get("pai") == id_sel or b_info.get("mae") == id_sel:
                    filhos.append({
                        "Brinco": b_id,
                        "Raça": b_info["raca"],
                        "Sexo": b_info["sexo"],
                        "Idade": calcular_idade(b_info["data_nascimento"]),
                        "Status": b_info["status"]
                    })
            
            if not filhos:
                st.info("Nenhum descendente direto cadastrado no sistema para este animal.")
            else:
                df_filhos = pd.DataFrame(filhos)
                st.dataframe(df_filhos, use_container_width=True, hide_index=True)
                
    else:
        st.header("📊 Painel Geral do Rebanho")
        
        if not dados_rebanho:
            st.info("Nenhum animal cadastrado no momento. Vá em 'Registrar Entrada' para começar.")
        else:
            # Filtrar ativos e inativos (baixas)
            ativos = {k: v for k, v in dados_rebanho.items() if v["status"] == "Ativo"}
            baixas = {k: v for k, v in dados_rebanho.items() if v["status"] != "Ativo"}
            
            # Métricas rápidas
            col1, col2, col3 = st.columns(3)
            col1.metric("Total de Animais Ativos", len(ativos))
            col2.metric("Total de Baixas (Vendas/Mortes)", len(baixas))
            col3.metric("Total Histórico Registrado", len(dados_rebanho))
            
            # Divisão por abas no Dashboard
            tab_ativos, tab_inativos = st.tabs(["🟢 Animais Ativos", "🔴 Animais Inativos (Baixas)"])
            
            # ABA: ANIMAIS ATIVOS
            with tab_ativos:
                st.subheader("📋 Lista de Animais Ativos no Rebanho")
                if ativos:
                    st.markdown("Clique em **🔎 Abrir Ficha** para ver as informações detalhadas, histórico de saúde, crias e observações do ovino.")
                    
                    # Cabeçalho da tabela de ativos
                    c_head = st.columns([1.5, 2, 2, 2, 2])
                    c_head[0].markdown("**Brinco**")
                    c_head[1].markdown("**Raça**")
                    c_head[2].markdown("**Sexo**")
                    c_head[3].markdown("**Idade**")
                    c_head[4].markdown("**Ações**")
                    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                    
                    # Dados de cada animal ativo
                    for brinco, ficha_at in ativos.items():
                        c_row = st.columns([1.5, 2, 2, 2, 2])
                        c_row[0].write(brinco)
                        c_row[1].write(ficha_at["raca"])
                        c_row[2].write(ficha_at["sexo"])
                        c_row[3].write(calcular_idade(ficha_at["data_nascimento"]))
                        
                        # Botão para abrir a ficha do animal
                        if c_row[4].button("🔎 Abrir Ficha", key=f"abrir_{brinco}"):
                            st.session_state.visualizar_brinco = brinco
                            st.rerun()
                        
                        st.markdown("<div style='border-bottom: 1px solid #f0f2f6; margin: 4px 0;'></div>", unsafe_allow_html=True)
                else:
                    st.warning("Não há animais ativos no momento.")
            
            # ABA: ANIMAIS INATIVOS (BAIXAS)
            with tab_inativos:
                st.subheader("🪵 Histórico de Baixas e Animais Inativos")
                if baixas:
                    st.markdown("Lista de ovinos que deixaram o rebanho. Se necessário, use a opção de reativação para trazê-los de volta.")
                    
                    # Cabeçalho da tabela de inativos
                    c_head_in = st.columns([1.2, 1.8, 1.5, 1.5, 1.5, 2.5])
                    c_head_in[0].markdown("**Brinco**")
                    c_head_in[1].markdown("**Raça**")
                    c_head_in[2].markdown("**Sexo**")
                    c_head_in[3].markdown("**Motivo Saída**")
                    c_head_in[4].markdown("**Data Saída**")
                    c_head_in[5].markdown("**Ações**")
                    st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                    
                    # Dados de cada animal inativo
                    for brinco, ficha_in in baixas.items():
                        c_row_in = st.columns([1.2, 1.8, 1.5, 1.5, 1.5, 2.5])
                        c_row_in[0].write(brinco)
                        c_row_in[1].write(ficha_in["raca"])
                        c_row_in[2].write(ficha_in["sexo"])
                        c_row_in[3].write(ficha_in["status"])  # Guarda o tipo de baixa (Morte, Venda, Doação)
                        c_row_in[4].write(ficha_in.get("data_saida", "Não informada"))
                        
                        # Ações combinadas: Ficha e Reativar lado a lado
                        with c_row_in[5]:
                            col_f, col_r = st.columns(2)
                            if col_f.button("🔎 Ficha", key=f"abrir_in_{brinco}"):
                                st.session_state.visualizar_brinco = brinco
                                st.rerun()
                            if col_r.button("🔄 Reativar", key=f"reativar_in_{brinco}"):
                                dados_rebanho[brinco]["status"] = "Ativo"
                                dados_rebanho[brinco]["data_saida"] = ""
                                dados_rebanho[brinco]["motivo_saida"] = ""
                                salvar_dados(dados_rebanho)
                                st.success(f"Animal {brinco} reativado com sucesso!")
                                st.rerun()
                        
                        st.markdown("<div style='border-bottom: 1px solid #f0f2f6; margin: 4px 0;'></div>", unsafe_allow_html=True)
                else:
                    st.info("Nenhuma baixa ou animal inativo registrado no sistema.")

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
                    "observacoes": "",
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
                        "categoria": categoria_manejo,
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

import streamlit as st
import pandas as pd
from datetime import datetime

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gestão de Açaí - Custos", layout="wide")

# -----------------------------------------------------------------------------
# SIMULAÇÃO DO BANCO DE DADOS (Substitua pelas suas funções do Google Sheets)
# -----------------------------------------------------------------------------
# Nota: Quando conectar ao Google Sheets, use o formato de data DD/MM/YYYY
if 'df_lotes' not in st.session_state:
    st.session_state.df_lotes = pd.DataFrame(columns=[
        'id_lote', 'nome_lote', 'data_criacao', 'rendimento_potes', 'custo_total', 'custo_por_pote'
    ])

if 'df_compras' not in st.session_state:
    st.session_state.df_compras = pd.DataFrame(columns=[
        'id_compra', 'id_lote', 'item', 'quantidade', 'preco_unitario', 'preco_total'
    ])

# -----------------------------------------------------------------------------
# INTERFACE DO STREAMLIT
# -----------------------------------------------------------------------------
st.title("🍧 Gestão de Açaí - Módulo de Custos")
st.markdown("---")

# Criando duas colunas na tela: Esquerda para criar/gerenciar, Direita para ver os dados
col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("📦 Gerenciar Lotes")
    
    # --- PASSO A: CRIAR NOVO LOTE ---
    with st.expander("➕ Criar Novo Lote", expanded=True):
        # Sugere automaticamente o próximo número de lote
        proximo_id = len(st.session_state.df_lotes) + 1
        nome_sugerido = f"Lote {proximo_id}"
        
        nome_lote = st.text_input("Nome do Lote", value=nome_sugerido)
        # Formato de data padrão DD/MM/YYYY para exibição e salvamento
        data_atual = datetime.now().strftime("%d/%m/%Y")
        st.write(f"Data de Criação: {data_atual}")
        
        if st.button("Iniciar Lote", use_container_width=True):
            # Aqui você fará o append/insert na sua aba 'lotes' do Google Sheets
            novo_lote = pd.DataFrame([{
                'id_lote': proximo_id,
                'nome_lote': nome_lote,
                'data_criacao': data_atual,
                'rendimento_potes': 0,
                'custo_total': 0.0,
                'custo_por_pote': 0.0
            }])
            st.session_state.df_lotes = pd.concat([st.session_state.df_lotes, novo_lote], ignore_index=True)
            st.success(f"🎉 {nome_lote} criado com sucesso!")
            st.rerun()

    # --- PASSO B: LANÇAR GASTOS DO LOTE ---
    if not st.session_state.df_lotes.empty:
        with st.expander("🛒 Lançar Compras / Insumos", expanded=True):
            # Seleciona o lote que deseja trabalhar
            lotes_disponiveis = st.session_state.df_lotes['nome_lote'].tolist()
            lote_selecionado = st.selectbox("Selecione o Lote para adicionar gastos", lotes_disponiveis)
            
            # Busca o ID do lote selecionado
            id_lote_sel = st.session_state.df_lotes[st.session_state.df_lotes['nome_lote'] == lote_selecionado]['id_lote'].values[0]
            
            # Formulário de itens
            item = st.text_input("Nome do Ingrediente/Insumo", placeholder="Ex: Caixa de Açaí 10L, Pote 500ml, Leite Ninho")
            c_qtd, c_preco = st.columns(2)
            with c_qtd:
                quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
            with c_preco:
                preco_unitario = st.number_input("Preço Unitário (R$)", min_value=0.0, value=0.0, step=0.50, format="%.2f")
            
            preco_total_item = quantidade * preco_unitario
            st.info(f"Subtotal do Item: R$ {preco_total_item:.2f}")
            
            if st.button("Adicionar ao Lote", use_container_width=True):
                if item == "":
                    st.error("Por favor, digite o nome do item.")
                elif preco_unitario <= 0:
                    st.error("O preço unitário deve ser maior que zero.")
                else:
                    # Aqui você fará o append na sua aba 'compras_lote' do Google Sheets
                    nova_compra = pd.DataFrame([{
                        'id_compra': len(st.session_state.df_compras) + 1,
                        'id_lote': id_lote_sel,
                        'item': item,
                        'quantidade': quantidade,
                        'preco_unitario': preco_unitario,
                        'preco_total': preco_total_item
                    }])
                    st.session_state.df_compras = pd.concat([st.session_state.df_compras, nova_compra], ignore_index=True)
                    st.success(f"✔️ {item} adicionado ao {lote_selecionado}!")
                    st.rerun()

with col2:
    st.header("📊 Resumo e Rendimento")
    
    if st.session_state.df_lotes.empty:
        st.info("Crie um lote na coluna ao lado para começar a registrar.")
    else:
        # Mostra os detalhes do lote selecionado na barra da esquerda
        st.subheader(f"Detalhes do {lote_selecionado}")
        
        # Filtra as compras feitas APENAS para o lote selecionado
        compras_do_lote = st.session_state.df_compras[st.session_state.df_compras['id_lote'] == id_lote_sel]
        
        if compras_do_lote.empty:
            st.warning("Nenhuma compra registrada para este lote ainda.")
            custo_total_lote = 0.0
        else:
            # Exibe a tabela de itens comprados
            st.dataframe(compras_do_lote[['item', 'quantidade', 'preco_unitario', 'preco_total']], use_container_width=True, hide_index=True)
            
            custo_total_lote = compras_do_lote['preco_total'].sum()
            st.metric(label="Custo Total Acumulado", value=f"R$ {custo_total_lote:.2f}")
            
            # --- PASSO C: FECHAMENTO DO LOTE (CÁLCULO DO RENDIMENTO) ---
            st.markdown("#### 🏁 Fechamento do Lote")
            rendimento = st.number_input("Quantos potes finais renderam esse lote?", min_value=0, value=0, step=1, help="Ex: Quantos potes de 500ml você conseguiu produzir e guardar para vender?")
            
            if rendimento > 0:
                custo_por_pote = custo_total_lote / rendimento
                
                st.metric(label="Custo Real por Pote", value=f"R$ {custo_por_pote:.2f}")
                
                if st.button("Salvar Fechamento de Custo", use_container_width=True):
                    # Aqui você fará o UPDATE na linha correspondente do seu Google Sheets
                    idx = st.session_state.df_lotes[st.session_state.df_lotes['id_lote'] == id_lote_sel].index
                    st.session_state.df_lotes.loc[idx, 'rendimento_potes'] = rendimento
                    st.session_state.df_lotes.loc[idx, 'custo_total'] = custo_total_lote
                    st.session_state.df_lotes.loc[idx, 'custo_por_pote'] = custo_por_pote
                    st.success("💾 Fechamento salvo com sucesso no banco de dados!")
                    st.rerun()

# --- VISUALIZAÇÃO GERAL DOS LOTES SALVOS ---
st.markdown("---")
st.subheader("📋 Histórico Geral de Lotes")
if not st.session_state.df_lotes.empty:
    st.dataframe(st.session_state.df_lotes, use_container_width=True, hide_index=True)
else:
    st.text("Nenhum lote registrado.")

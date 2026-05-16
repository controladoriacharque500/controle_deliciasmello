import streamlit as st
import pandas as pd
from datetime import datetime
from gspread import service_account, service_account_from_dict

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gerenciamento de Custo e Vendas", layout="wide")

# CONSTANTES
PLANILHA_NOME = "Gerenciamento de custo"
CREDENTIALS_PATH = "credentials.json"  # Caso use localmente

# -----------------------------------------------------------------------------
# FUNÇÃO DE CONEXÃO AUTENTICADA
# -----------------------------------------------------------------------------
def conectar_google_sheets():
    try:
        if "gcp_service_account" in st.secrets:
            secrets_dict = dict(st.secrets["gcp_service_account"])
            private_key_corrompida = secrets_dict["private_key"]
            
            private_key_limpa = private_key_corrompida.replace('\n', '').replace(' ', '')
            private_key_limpa = private_key_limpa.replace('-----BEGINPRIVATEKEY-----', '').replace('-----ENDPRIVATEKEY-----', '')
            
            padding_necessario = len(private_key_limpa) % 4
            if padding_necessario != 0:
                private_key_limpa += '=' * (4 - padding_necessario)
            
            secrets_dict["private_key"] = f"-----BEGIN PRIVATE KEY-----\n{private_key_limpa}\n-----END PRIVATE KEY-----\n"
            gc = service_account_from_dict(secrets_dict)
        else:
            gc = service_account(filename=CREDENTIALS_PATH)
            
        return gc.open(PLANILHA_NOME)
    except Exception as e:
        st.error(f"Erro crítico na autenticação do Google Sheets: {e}")
        return None

# -----------------------------------------------------------------------------
# FUNÇÕES DE LEITURA E ESCRITA
# -----------------------------------------------------------------------------
def carregar_aba(nome_aba):
    planilha = conectar_google_sheets()
    if planilha:
        try:
            aba = planilha.worksheet(nome_aba)
            data = aba.get_all_records()
            df = pd.DataFrame(data)
            
            if df.empty:
                return df, aba
                
            # Tratamento numérico para colunas financeiras
            colunas_dinheiro = ['preco_unitario', 'preco_total', 'custo_total', 'custo_por_pote', 'preco_venda_unitario', 'faturamento_total']
            for col in colunas_dinheiro:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].str.replace('R$', '', regex=False).str.strip()
                    df[col] = df[col].str.replace(',', '.', regex=False)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            return df, aba
        except Exception as e:
            st.error(f"Erro ao carregar a aba {nome_aba}: {e}")
    return pd.DataFrame(), None

def adicionar_linha_sheets(aba, nova_linha_lista):
    try:
        linha_formatada = [
            str(item) if isinstance(item, (float, int)) else item 
            for item in nova_linha_lista
        ]
        aba.append_row(linha_formatada, value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"Erro ao salvar dados na planilha: {e}")

# Carrega todas as abas do Sheets
df_lotes, aba_lotes = carregar_aba("lotes")
df_compras, aba_compras = carregar_aba("compras_lote")
df_vendas, aba_vendas = carregar_aba("vendas")

# Garantir tipos de IDs corretos
if not df_lotes.empty:
    df_lotes['id_lote'] = pd.to_numeric(df_lotes['id_lote'], errors='coerce').fillna(0).astype(int)
if not df_compras.empty:
    df_compras['id_lote'] = pd.to_numeric(df_compras['id_lote'], errors='coerce').fillna(0).astype(int)
if not df_vendas.empty:
    df_vendas['id_lote'] = pd.to_numeric(df_vendas['id_lote'], errors='coerce').fillna(0).astype(int)

# -----------------------------------------------------------------------------
# NAVEGAÇÃO LATERAL (MENU)
# -----------------------------------------------------------------------------
st.sidebar.title("メニュー Navegação")
modulo = st.sidebar.radio("Selecione o Módulo:", ["📦 Custos do Lote", "💰 Vendas e Lucros"])

# =============================================================================
# MÓDULO 1: CUSTOS DO LOTE
# =============================================================================
if modulo == "📦 Custos do Lote":
    st.title("📦 Gerenciamento de Custo por Lotes")
    st.markdown("---")
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.header("Gerenciar Lotes")
        with st.expander("➕ Criar Novo Lote", expanded=True):
            proximo_id = int(df_lotes['id_lote'].max() + 1) if not df_lotes.empty and pd.notna(df_lotes['id_lote'].max()) else 1
            nome_sugerido = f"Lote {proximo_id}"
            
            nome_lote = st.text_input("Nome/Identificação do Lote", value=nome_sugerido)
            data_atual = datetime.now().strftime("%d/%m/%Y")
            st.write(f"Data de Criação: **{data_atual}**")
            
            if st.button("Iniciar Lote", use_container_width=True):
                if aba_lotes is not None:
                    adicionar_linha_sheets(aba_lotes, [proximo_id, nome_lote, data_atual, 0, 0.0, 0.0])
                    st.success(f"🎉 {nome_lote} criado!")
                    st.rerun()

        if not df_lotes.empty:
            with st.expander("🛒 Lançar Compras / Insumos", expanded=True):
                lotes_disponiveis = df_lotes['nome_lote'].tolist()
                lote_selecionado = st.selectbox("Selecione o Lote para adicionar gastos", lotes_disponiveis)
                id_lote_sel = int(df_lotes[df_lotes['nome_lote'] == lote_selecionado]['id_lote'].values[0])
                
                item = st.text_input("Nome do Ingrediente/Insumo", placeholder="Ex: Caixa de Açaí 10L, Pote 500ml")
                c_qtd, c_preco = st.columns(2)
                with c_qtd:
                    quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
                with c_preco:
                    preco_unitario = st.number_input("Preço Unitário (R$)", min_value=0.0, value=0.0, step=0.01, format="%.2f")
                
                preco_total_item = round(quantidade * preco_unitario, 2)
                st.info(f"Subtotal do Item: R$ {preco_total_item:.2f}")
                
                if st.button("Adicionar Compra à Planilha", use_container_width=True):
                    if item == "" or preco_unitario <= 0:
                        st.error("Verifique os campos de preenchimento.")
                    elif aba_compras is not None:
                        proximo_id_compra = len(df_compras) + 1
                        adicionar_linha_sheets(aba_compras, [proximo_id_compra, id_lote_sel, item, quantidade, preco_unitario, preco_total_item])
                        st.success(f"✔️ {item} adicionado!")
                        st.rerun()

    with col2:
        st.header("📊 Resumo e Rendimento")
        if df_lotes.empty:
            st.info("Crie um lote ao lado para começar.")
        else:
            st.subheader(f"Detalhes atuais: {lote_selecionado}")
            compras_do_lote = df_compras[df_compras['id_lote'] == id_lote_sel] if not df_compras.empty else pd.DataFrame()
            
            if compras_do_lote.empty:
                st.warning("Nenhuma compra registrada para este lote ainda.")
                custo_total_lote = 0.0
            else:
                st.dataframe(compras_do_lote[['item', 'quantidade', 'preco_unitario', 'preco_total']], use_container_width=True, hide_index=True)
                custo_total_lote = round(float(compras_do_lote['preco_total'].sum()), 2)
                st.metric(label="Custo Total do Lote", value=f"R$ {custo_total_lote:.2f}")
                
                st.markdown("#### 🏁 Fechamento do Lote")
                rendimento = st.number_input("Quantas unidades finais (potes/litros) renderam?", min_value=0, value=0, step=1)
                
                if rendimento > 0:
                    custo_por_pote = round(custo_total_lote / rendimento, 2)
                    st.metric(label="Custo Real por Unidade", value=f"R$ {custo_por_pote:.2f}")
                    
                    if st.button("Salvar Fechamento na Planilha", use_container_width=True):
                        if aba_lotes is not None:
                            lista_ids = df_lotes['id_lote'].tolist()
                            linha_sheets = lista_ids.index(id_lote_sel) + 2
                            aba_lotes.update_cell(linha_sheets, 4, int(rendimento))
                            aba_lotes.update_cell(linha_sheets, 5, str(custo_total_lote))
                            aba_lotes.update_cell(linha_sheets, 6, str(custo_por_pote))
                            st.success("💾 Dados salvos no Drive!")
                            st.rerun()

    st.markdown("---")
    st.subheader("📋 Histórico Geral de Lotes")
    st.dataframe(df_lotes, use_container_width=True, hide_index=True)

# =============================================================================
# MÓDULO 2: VENDAS E LUCROS
# =============================================================================
else:
    st.title("💰 Registro de Vendas e Balanço de Lucros")
    st.markdown("---")
    
    if df_lotes.empty:
        st.warning("Você precisa criar e fechar ao menos um lote no módulo anterior para poder vender.")
    else:
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            st.header("🛍️ Registrar Nova Venda")
            
            lotes_disponiveis = df_lotes['nome_lote'].tolist()
            lote_venda = st.selectbox("A qual Lote pertence este produto vendido?", lotes_disponiveis)
            
            # Dados do lote escolhido para a venda
            lote_info = df_lotes[df_lotes['nome_lote'] == lote_venda].iloc[0]
            id_lote_venda = int(lote_info['id_lote'])
            custo_unitario_lote = float(lote_info['custo_por_pote'])
            
            if custo_unitario_lote <= 0:
                st.warning(f"⚠️ Atenção: O {lote_venda} ainda não teve o custo por unidade fechado. O cálculo do lucro ficará zerado até você fechar o lote.")
            else:
                st.info(f"Custo de fabricação deste lote: R$ {custo_unitario_lote:.2f} por unidade")

            # Formulário da Venda
            produto = st.text_input("Produto/Tamanho vendido", placeholder="Ex: Pote Açaí 500ml Completo, Copo 300ml")
            c_q, c_v = st.columns(2)
            with c_q:
                qtd_venda = st.number_input("Quantidade Vendida", min_value=1, value=1, step=1)
            with c_v:
                preco_venda = st.number_input("Preço de Venda Unitário (R$)", min_value=0.0, value=0.0, step=0.50, format="%.2f")
                
            faturamento_total_venda = round(qtd_venda * preco_venda, 2)
            st.success(f"Faturamento Total da Venda: R$ {faturamento_total_venda:.2f}")
            
            data_venda = datetime.now().strftime("%d/%m/%Y")
            
            if st.button("Confirmar e Gravar Venda", use_container_width=True):
                if produto == "" or preco_venda <= 0:
                    st.error("Preencha o nome do produto e o preço de venda.")
                elif aba_vendas is not None:
                    proximo_id_venda = len(df_vendas) + 1
                    # id_venda, id_lote, data_venda, produto_vendido, quantidade, preco_venda_unitario, faturamento_total
                    adicionar_linha_sheets(aba_vendas, [proximo_id_venda, id_lote_venda, data_venda, produto, qtd_venda, preco_venda, faturamento_total_venda])
                    st.success("💰 Venda gravada com sucesso!")
                    st.rerun()
                    
        with col2:
            st.header("📈 Balanço Financeiro por Lote")
            
            # Caixa de seleção para analisar o lucro de um lote específico
            lote_analise = st.selectbox("Selecione um lote para ver o balanço de lucros:", lotes_disponiveis)
            lote_analise_info = df_lotes[df_lotes['nome_lote'] == lote_analise].iloc[0]
            id_lote_analise = int(lote_analise_info['id_lote'])
            custo_total_gravado = float(lote_analise_info['custo_total'])
            custo_unit_gravado = float(lote_analise_info['custo_por_pote'])
            
            # Filtra as vendas deste lote específico
            vendas_deste_lote = df_vendas[df_vendas['id_lote'] == id_lote_analise] if not df_vendas.empty else pd.DataFrame()
            
            # Métricas Gerais do Lote Comercializado
            faturamento_lote = float(vendas_deste_lote['faturamento_total'].sum()) if not vendas_deste_lote.empty else 0.0
            
            # O custo real vendido é baseado nas unidades que saíram versus o custo de fabricação delas
            qtd_total_vendida = int(vendas_deste_lote['quantidade'].sum()) if not vendas_deste_lote.empty else 0
            custo_das_unidades_vendidas = qtd_total_vendida * custo_unit_gravado
            
            lucro_real = faturamento_lote - custo_das_unidades_vendidas
            
            # Layout de cartões de resultado (Métricas)
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric(label="Investimento no Lote", value=f"R$ {custo_total_gravado:.2f}")
            with m2:
                st.metric(label="Faturamento Atual", value=f"R$ {faturamento_lote:.2f}")
            with m3:
                # Mostra o lucro e colore se está positivo ou negativo
                st.metric(label="Lucro Real Obtido", value=f"R$ {lucro_real:.2f}", delta=f"R$ {lucro_real:.2f}" if lucro_real >= 0 else f"R$ {lucro_real:.2f}", delta_color="normal")
            
            st.markdown("---")
            st.subheader(f"📋 Histórico de Vendas do {lote_analise}")
            if vendas_deste_lote.empty:
                st.text("Nenhuma venda registrada para este lote.")
            else:
                st.dataframe(vendas_deste_lote[['data_venda', 'produto_vendido', 'quantidade', 'preco_venda_unitario', 'faturamento_total']], use_container_width=True, hide_index=True)

import streamlit as st
import pandas as pd
from datetime import datetime
from gspread import service_account, service_account_from_dict

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Gerenciamento de Custo", layout="wide")

# CONSTANTES
PLANILHA_NOME = "Gerenciamento de custo"
CREDENTIALS_PATH = "credentials.json"  # Caso use localmente

# -----------------------------------------------------------------------------
# FUNÇÃO DE CONEXÃO AUTENTICADA (Baseada no seu padrão de secrets/local)
# -----------------------------------------------------------------------------
def conectar_google_sheets():
    """Garante a conexão autenticada com o Google Drive e retorna a planilha."""
    try:
        if "gcp_service_account" in st.secrets:
            secrets_dict = dict(st.secrets["gcp_service_account"])
            private_key_corrompida = secrets_dict["private_key"]
            
            # Limpeza de caracteres da chave
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
    """Carrega os dados de uma aba específica da planilha como DataFrame limpando números."""
    planilha = conectar_google_sheets()
    if planilha:
        try:
            aba = planilha.worksheet(nome_aba)
            data = aba.get_all_records()
            df = pd.DataFrame(data)
            
            # --- Tratamento para converter o padrão de vírgula do Sheets para ponto do Python ---
            colunas_dinheiro = ['preco_unitario', 'preco_total', 'custo_total', 'custo_por_pote']
            for col in colunas_dinheiro:
                if col in df.columns:
                    # Garante que é texto, troca vírgula por ponto e converte para número
                    df[col] = df[col].astype(str).str.strip()
                    df[col] = df[col].str.replace(',', '.', regex=False)
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
            return df, aba
        except Exception as e:
            st.error(f"Erro ao carregar a aba {nome_aba}: {e}")
    return pd.DataFrame(), None

# Carrega os dados das duas abas do Sheets já tratados
df_lotes, aba_lotes = carregar_aba("lotes")
df_compras, aba_compras = carregar_aba("compras_lote")

# Garantir tipos de IDs como numéricos inteiros
if not df_lotes.empty:
    df_lotes['id_lote'] = pd.to_numeric(df_lotes['id_lote'], errors='coerce').fillna(0).astype(int)
if not df_compras.empty:
    df_compras['id_lote'] = pd.to_numeric(df_compras['id_lote'], errors='coerce').fillna(0).astype(int)

# -----------------------------------------------------------------------------
# INTERFACE DO STREAMLIT
# -----------------------------------------------------------------------------
st.title("🍧 Gerenciamento de Custo por Lotes")
st.markdown("---")

col1, col2 = st.columns([1, 1.2])

with col1:
    st.header("📦 Gerenciar Lotes")
    
    # --- PASSO A: CRIAR NOVO LOTE ---
    with st.expander("➕ Criar Novo Lote", expanded=True):
        proximo_id = int(df_lotes['id_lote'].max() + 1) if not df_lotes.empty and pd.notna(df_lotes['id_lote'].max()) else 1
        nome_sugerido = f"Lote {proximo_id}"
        
        nome_lote = st.text_input("Nome/Identificação do Lote", value=nome_sugerido)
        data_atual = datetime.now().strftime("%d/%m/%Y")
        st.write(f"Data de Criação: **{data_atual}**")
        
        if st.button("Iniciar Lote", use_container_width=True):
            if aba_lotes is not None:
                # Salva direto no Google Sheets (Alinhado com as colunas da aba 'lotes')
                # id_lote, nome_lote, data_criacao, rendimento_potes, custo_total, custo_por_pote
                adicionar_linha_sheets(aba_lotes, [proximo_id, nome_lote, data_atual, 0, 0.0, 0.0])
                st.success(f"🎉 {nome_lote} criado e salvo na planilha!")
                st.rerun()

    # --- PASSO B: LANÇAR GASTOS DO LOTE ---
    if not df_lotes.empty:
        with st.expander("🛒 Lançar Compras / Insumos", expanded=True):
            lotes_disponiveis = df_lotes['nome_lote'].tolist()
            lote_selecionado = st.selectbox("Selecione o Lote para adicionar gastos", lotes_disponiveis)
            
            # Puxa o ID correto correspondente ao nome selecionado
            id_lote_sel = int(df_lotes[df_lotes['nome_lote'] == lote_selecionado]['id_lote'].values[0])
            
            item = st.text_input("Nome do Ingrediente/Insumo", placeholder="Ex: Caixa de Açaí 10L, Pote 500ml, Morango")
            c_qtd, c_preco = st.columns(2)
            with c_qtd:
                quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
            with c_preco:
                preco_unitario = st.number_input("Preço Unitário (R$)", min_value=0.0, value=0.0, step=0.50, format="%.2f")
            
            preco_total_item = quantidade * preco_unitario
            st.info(f"Subtotal do Item: R$ {preco_total_item:.2f}")
            
            if st.button("Adicionar Compra à Planilha", use_container_width=True):
                if item == "":
                    st.error("Por favor, preencha o nome do item.")
                elif preco_unitario <= 0:
                    st.error("O preço unitário deve ser maior que zero.")
                elif aba_compras is not None:
                    proximo_id_compra = len(df_compras) + 1
                    # Salva na aba 'compras_lote'
                    # id_compra, id_lote, item, quantidade, preco_unitario, preco_total
                    adicionar_linha_sheets(aba_compras, [proximo_id_compra, id_lote_sel, item, quantidade, preco_unitario, preco_total_item])
                    st.success(f"✔️ {item} adicionado ao banco de dados!")
                    st.rerun()

with col2:
    st.header("📊 Resumo e Rendimento")
    
    if df_lotes.empty:
        st.info("Crie um lote na aba ao lado para começar.")
    else:
        st.subheader(f"Detalhes atuais: {lote_selecionado}")
        
        # Filtra as compras vinculadas a este ID de lote
        compras_do_lote = df_compras[df_compras['id_lote'] == id_lote_sel] if not df_compras.empty else pd.DataFrame()
        
        if compras_do_lote.empty:
            st.warning("Nenhuma compra registrada para este lote ainda.")
            custo_total_lote = 0.0
        else:
            st.dataframe(compras_do_lote[['item', 'quantidade', 'preco_unitario', 'preco_total']], use_container_width=True, hide_index=True)
            
            custo_total_lote = float(compras_do_lote['preco_total'].sum())
            st.metric(label="Custo Total do Lote", value=f"R$ {custo_total_lote:.2f}")
            
            # --- PASSO C: FECHAMENTO DO LOTE (CÁLCULO E UPDATE) ---
            st.markdown("#### 🏁 Fechamento do Lote")
            rendimento = st.number_input("Quantas unidades finais (potes/litros) renderam?", min_value=0, value=0, step=1)
            
            if rendimento > 0:
                custo_por_pote = custo_total_lote / rendimento
                st.metric(label="Custo Real por Unidade", value=f"R$ {custo_por_pote:.2f}")
                
                if st.button("Salvar Fechamento na Planilha", use_container_width=True):
                    if aba_lotes is not None:
                        # Encontra a linha exata no Sheets para atualizar.
                        # Somamos 2 porque as linhas no gspread começam em 1 e a linha 1 são os cabeçalhos.
                        lista_ids = df_lotes['id_lote'].tolist()
                        linha_sheets = lista_ids.index(id_lote_sel) + 2
                        
                        # Atualiza as células de rendimento, custo total e custo unitário
                        aba_lotes.update_cell(linha_sheets, 4, int(rendimento))         # Coluna D: rendimento_potes
                        aba_lotes.update_cell(linha_sheets, 5, float(custo_total_lote))  # Coluna E: custo_total
                        aba_lotes.update_cell(linha_sheets, 6, float(custo_por_pote))   # Coluna F: custo_por_pote
                        
                        st.success("💾 Dados de fechamento atualizados com sucesso no Google Drive!")
                        st.rerun()

# --- HISTÓRICO COMPLETO DA PLANILHA ---
st.markdown("---")
st.subheader("📋 Dados Gravados na Planilha (Aba Lotes)")
if not df_lotes.empty:
    st.dataframe(df_lotes, use_container_width=True, hide_index=True)
else:
    st.text("Nenhum registro encontrado no Google Sheets.")

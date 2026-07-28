import datetime
import json
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
import streamlit as st

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E ESTILIZAÇÃO
# ==========================================
st.set_page_config(
    page_title="Ficha de Monitoração PME",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS Customizado
st.markdown(
    """
    <style>
    .header-bar {
        background-color: #0d233a;
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        margin-bottom: 20px;
        font-weight: bold;
        font-size: 22px;
    }
    .score-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 20px;
        text-align: center;
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .score-value {
        font-size: 32px;
        font-weight: bold;
        color: #1f2937;
    }
    .status-adequadas {
        color: #10b981;
        font-weight: bold;
        font-size: 18px;
    }
    .status-inadequado {
        color: #ef4444;
        font-weight: bold;
        font-size: 18px;
    }
    .category-header {
        background-color: #f3f4f6;
        padding: 6px 12px;
        border-radius: 4px;
        font-weight: bold;
        color: #374151;
        margin-top: 15px;
        margin-bottom: 10px;
    }
    div[data-testid="stRadio"] > label {
        font-size: 13px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize Session State Variables for state control
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "pending_data" not in st.session_state:
    st.session_state.pending_data = None
if "form_version" not in st.session_state:
    st.session_state.form_version = 0


def reset_formulario():
    """Limpa os dados pendentes, sai do modo de edição e reseta a versão dos inputs."""
    st.session_state.editing_id = None
    st.session_state.pending_data = None
    st.session_state.form_version += 1

# ==========================================
# CARREGAMENTO DE DADOS EXTERNOS (CSV REDE)
# ==========================================
@st.cache_data(ttl=3600)
def carregar_colaboradores():
    caminho_csv = r"\\172.30.100.44\sae\RELATORIOS GERENCIAIS\MIS RP\ARQUIVOS_GRACIMARA\BD_PESSOAS.csv"
    
    try:
        df_pessoas = None
        # Tenta ler testando os delimitadores e encodings mais comuns
        for sep in [";", ",", "\t"]:
            for enc in ["utf-8-sig", "latin1", "cp1252"]:
                try:
                    df_temp = pd.read_csv(caminho_csv, sep=sep, encoding=enc)
                    # Limpa espaços em branco nos nomes das colunas
                    df_temp.columns = df_temp.columns.str.strip()
                    
                    # Procura pela coluna ignorando maiúsculas/minúsculas
                    colunas_upper = [c.upper() for c in df_temp.columns]
                    if "NOME_BASE_VOLUMETRIA_POWER_BI" in colunas_upper:
                        df_pessoas = df_temp
                        # Ajusta o nome real da coluna encontrada
                        idx = colunas_upper.index("NOME_BASE_VOLUMETRIA_POWER_BI")
                        col_alvo = df_temp.columns[idx]
                        break
                except Exception:
                    continue
            if df_pessoas is not None:
                break

        if df_pessoas is not None and col_alvo in df_pessoas.columns:
            nomes = (
                df_pessoas[col_alvo]
                .dropna()
                .astype(str)
                .str.strip()
                .unique()
            )
            nomes = sorted([n for n in nomes if n != "" and n.lower() != "nan"])
            return ["Selecione..."] + nomes
        else:
            # Mostra no console/aviso quais colunas ele encontrou para ajudar no diagnóstico
            cols_encontradas = ", ".join(df_temp.columns) if 'df_temp' in locals() else "Nenhuma"
            st.warning(f"Coluna 'NOME_BASE_VOLUMETRIA_POWER_BI' não encontrada. Colunas lidas: [{cols_encontradas}]")
            return ["Selecione..."]

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo CSV: {e}")
        return ["Selecione..."]
    
# ==========================================
# CONEXÃO COM O BANCO DE DADOS POSTGRESQL
# ==========================================
def get_db_connection():
    try:
        DB_HOST = st.secrets["DB_HOST"]
        DB_PORT = st.secrets["DB_PORT"]
        DB_NAME = st.secrets["DB_NAME"]
        DB_USER = st.secrets["DB_USER"]
        DB_PASS = st.secrets["DB_PASS"]
    except Exception:
        DB_HOST = "localhost"
        DB_PORT = "5432"
        DB_NAME = "monitoria_whatsapp"
        DB_USER = "postgres"
        DB_PASS = "a1b2c4d3"

    db_url = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(db_url)


def salvar_registro(dados, id_registro=None):
    engine = get_db_connection()
    with engine.begin() as conn:
        respostas_json = json.dumps(dados["respostas"], ensure_ascii=False)
        if id_registro is None:
            query = """
                INSERT INTO monitoria_whatsapp (
                    avaliador, operacao, gestor, colaborador, data_ligacao, hora_inicio,
                    minuto_inicio, duracao, data_audicao, canal, telefone, cnpj, assunto,
                    pontuacao, status_resultado, descricao, respostas
                ) VALUES (
                    %(avaliador)s, %(operacao)s, %(gestor)s, %(colaborador)s, %(data_ligacao)s, %(hora_inicio)s,
                    %(minuto_inicio)s, %(duracao)s, %(data_audicao)s, %(canal)s, %(telefone)s, %(cnpj)s, %(assunto)s,
                    %(pontuacao)s, %(status_resultado)s, %(descricao)s, %(respostas)s
                )
            """
        else:
            query = """
                UPDATE monitoria_whatsapp SET
                    avaliador = %(avaliador)s, operacao = %(operacao)s, gestor = %(gestor)s,
                    colaborador = %(colaborador)s, data_ligacao = %(data_ligacao)s, hora_inicio = %(hora_inicio)s,
                    minuto_inicio = %(minuto_inicio)s, duracao = %(duracao)s, data_audicao = %(data_audicao)s,
                    canal = %(canal)s, telefone = %(telefone)s, cnpj = %(cnpj)s, assunto = %(assunto)s,
                    pontuacao = %(pontuacao)s, status_resultado = %(status_resultado)s,
                    descricao = %(descricao)s, respostas = %(respostas)s, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %(id_registro)s
            """
        params = {
            **dados,
            "respostas": respostas_json,
            "id_registro": id_registro,
        }
        conn.exec_driver_sql(query, params)


def buscar_registros():
    try:
        engine = get_db_connection()
        df = pd.read_sql(
            "SELECT * FROM monitoria_whatsapp ORDER BY id DESC", engine
        )
        return df
    except Exception as e:
        st.error(f"Erro ao conectar com banco PostgreSQL: {e}")
        return pd.DataFrame()


def excluir_registro(id_registro):
    engine = get_db_connection()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "DELETE FROM monitoria_whatsapp WHERE id = :id",
            {"id": id_registro},
        )


# ==========================================
# CRITÉRIOS E PESOS
# ==========================================
CRITERIOS_OBLIGATORIOS = [
    {
        "cat": "Habilidades de Comunicação",
        "desc": (
            "Operador(a) atende o cliente dentro do tempo estabelecido (3"
            " min/ 2 min/1 min)"
        ),
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": (
            "Operador(a) utiliza palavras de cordialidade (ex.: por favor, por"
            " gentileza, obrigado(a)?)"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": (
            "Operador(a) utilizou escrita clara, sem abreviações, erros graves"
            " no chat?"
        ),
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": (
            "Operador(a) conduziu o atendimento com segurança, sem demonstrar"
            " insegurança nas respostas escritas?"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) leu atentamente a solicitação do cliente, sem ignorar"
            " ou responder fora do contexto no chat?"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) demonstrou paciência e cordialidade mesmo diante de"
            " situações de insatisfação do cliente no chat?"
        ),
        "peso": 7.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) evitou respostas secas ou ríspidas durante o"
            " atendimento via chat?"
        ),
        "peso": 7.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) explicou as informações de forma simples e fácil de"
            " entender no chat?"
        ),
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) demonstrou domínio dos processos e segurança nas"
            " informações prestadas durante o atendimento via chat?"
        ),
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador(a) encerrou o atendimento de forma educada e cordial,"
            " confirmando a finalização com o cliente?"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": (
            "Operador (a) solicita novamente informações já passadas pelo"
            " cliente?"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Operador(a) orientou corretamente o cliente quanto à documentação"
            " necessária e ao envio/anexo na interação via chat?"
        ),
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Operador(a) informou o protocolo de atendimento, quando"
            " aplicável?"
        ),
        "peso": 3.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "A ligação foi classificada corretamente no sistema (Salesforce)?"
        ),
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Operador(a) utilizou corretamente os recursos do sistema para"
            " agilizar o atendimento via chat? (frases prontas)"
        ),
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Operador(a) quando solicitado cancelamento, realiza o processo"
            " corretamente?"
        ),
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Operador(a) realizou a confirmação de telefone e e-mail"
            " cadastrados?"
        ),
        "peso": 0.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": (
            "Enviou corretamente boleto e/ou outros documentos via sigo ou"
            " e-mail, quando necessário?"
        ),
        "peso": 5.0,
        "critico": False,
    },
    # ---------------- ERROS CRÍTICOS ----------------
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) realiza atendimento sem desvios de conduta?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador (a) realiza o atendimento sem concordar/realizar"
            " comentários inadequados?"
        ),
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador (a) realizou interação via Chat? ( superior a 6 minutos)"
        ),
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Quando mencionado ODC, operador se posiciona?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador(a) confirmou o responsável legal ( confirmou no site/"
            " sigo se é o mesmo)?"
        ),
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador (a) orienta o beneficiário a excluir ou esvazias as vidas"
            " no portal?"
        ),
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador (a) influência / estimula o cliente ao cancelamento?"
        ),
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) encerra chat sem consentimento do cliente?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador(a) realiza o direcionamento para o canal correto?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": (
            "Operador(a) abriu o Saccad corretamente, quando aplicável ao"
            " atendimento via chat?"
        ),
        "peso": 100.0,
        "critico": True,
    },
    # ---------------- EXPERIÊNCIA GERAL DO CLIENTE ----------------
    {
        "cat": "Experiência Geral do Cliente",
        "desc": (
            "Operador(a) orientou o cliente sobre a pesquisa de satisfação e"
            " enviou o link ao final do atendimento via chat?"
        ),
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Experiência Geral do Cliente",
        "desc": (
            "Operador(a) explicou corretamente os procedimentos de atualização"
            " de cadastro(e-mail) para envio dos relatórios conforme registro na"
            " aba endereço"
        ),
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Experiência Geral do Cliente",
        "desc": (
            "Operador(a) justificou a ausência quando houve necessidade de"
            " tempo para análise, mantendo o cliente informado no chat?"
        ),
        "peso": 5.0,
        "critico": False,
    },
]


# ==========================================
# POP-UP / MODAL DE CONFIRMAÇÃO DIALOG
# ==========================================
@st.dialog("Confirmar Gravação da Monitoria")
def modal_confirmacao():
    dados = st.session_state.pending_data

    st.warning("Verifique as informações abaixo antes de salvar no PostgreSQL:")
    st.markdown(f"**Colaborador:** {dados['colaborador']}")
    st.markdown(f"**Pontuação:** `{dados['pontuacao']} / 100`")
    st.markdown(f"**Status Final:** **{dados['status_resultado']}**")
    st.markdown(f"**Assunto:** {dados['assunto']}")

    col_sim, col_nao = st.columns(2)
    if col_sim.button("✅ Confirmar e Salvar", use_container_width=True):
        try:
            salvar_registro(dados, id_registro=st.session_state.editing_id)
            st.success("Monitoria gravada com sucesso no PostgreSQL!")
            reset_formulario()
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao gravar no banco: {e}")

    if col_nao.button("❌ Cancelar", use_container_width=True):
        st.session_state.pending_data = None
        st.rerun()


# ==========================================
# NAVEGAÇÃO DE ABAS
# ==========================================
st.markdown(
    '<div class="header-bar">Ficha de Monitoração PME</div>',
    unsafe_allow_html=True,
)
tab_formulario, tab_resultados = st.tabs(
    ["Preenchimento da Monitoria", "Acompanhamento de Resultados"]
)

# ------------------------------------------
# ABA 1: FORMULÁRIO DE MONITORIA
# ------------------------------------------
with tab_formulario:
    v = st.session_state.form_version  # Chave para forçar o reset dos inputs

    if st.session_state.editing_id:
        st.info(f"✏️ Editando registro ID: **{st.session_state.editing_id}**")
        if st.button("⬅️ Cancelar Edição", key=f"btn_cancel_edit_{v}"):
            reset_formulario()
            st.rerun()

    # Linha 1: Informações da Equipe
    l1_col1, l1_col2, l1_col3 = st.columns(3)

    avaliadores = ["Selecione...", "JEAN ROBERTO DA SILVA DOS SANTOS"]
    # Ajustado index=1 para selecionar por padrão Jean Roberto
    avaliador = l1_col1.selectbox("Avaliador *:", avaliadores, index=1, key=f"avaliador_{v}")
    operacao = l1_col2.text_input("Operação:", value="PME", key=f"operacao_{v}")
    gestor = l1_col3.text_input("Gestor:", value="DANIEL PIMENTA NEVES", key=f"gestor_{v}")

    # Linha 2: Colaborador e Dados do Horário
    l2_col1, l2_col2, l2_col3, l2_col4 = st.columns([3, 1.5, 1, 1])
    colaboradores = carregar_colaboradores()
    colaborador = l2_col1.selectbox("Colaborador *:", colaboradores, key=f"colaborador_{v}")
    duracao = l2_col2.selectbox(
        "Duração:", ["00:05", "00:10", "00:15", "00:20", "00:30"], key=f"duracao_{v}"
    )
    hr_inicio = l2_col3.selectbox(
        "Hora Início:", [f"{h:02d}" for h in range(24)], index=9, key=f"hr_inicio_{v}"
    )
    min_inicio = l2_col4.selectbox(
        "Minuto Início:", [f"{m:02d}" for m in range(60)], index=0, key=f"min_inicio_{v}"
    )

    # Linha 3: Datas e Canal
    l3_col1, l3_col2, l3_col3 = st.columns(3)
    data_ligacao = l3_col1.date_input(
        label="Data da Ligação *",
        value=datetime.date.today(),
        format="DD/MM/YYYY",
        key=f"dt_ligacao_{v}"
    )
    data_audicao = l3_col2.date_input(
        label="Data da Audição *",
        value=datetime.date.today(),
        format="DD/MM/YYYY",
        key=f"dt_audicao_{v}"
    )
    canal = l3_col3.selectbox("Canal:", ["Gravação", "Chat", "WhatsApp"], key=f"canal_{v}")

    # Linha 4: Dados do Cliente
    l4_col1, l4_col2, l4_col3 = st.columns([1.5, 1.5, 3])
    telefone = l4_col1.text_input(
        label="Telefone Chamador *", placeholder="(16) 99999-9999", key=f"tel_{v}"
    )
    cnpj = l4_col2.text_input(
        label="CNPJ *", placeholder="00.000.000/0001-00", key=f"cnpj_{v}"
    )
    assunto = l4_col3.text_input(
        label="Assunto *", placeholder="Ex: Segunda via de boleto...", key=f"assunto_{v}"
    )

    st.markdown("---")

    # Dicionário de respostas
    respostas = {}

    col_left, col_right = st.columns(2)

    # LADO ESQUERDO: Habilidade de Comunicação, Avaliação, Processos
    with col_left:
        for categoria in [
            "Habilidades de Comunicação",
            "Avaliação das Necessidades do Cliente",
            "Processos",
        ]:
            st.markdown(
                f'<div class="category-header">{categoria}</div>',
                unsafe_allow_html=True,
            )
            itens = [
                i for i in CRITERIOS_OBLIGATORIOS if i["cat"] == categoria
            ]
            for idx, item in enumerate(itens):
                key = f"q_{categoria}_{idx}_{v}"

                resp = st.radio(
                    label=item["desc"],
                    options=["Conforme", "Não Conforme", "Não se aplica"],
                    index=0,
                    horizontal=True,
                    key=key,
                )

                respostas[item["desc"]] = {
                    "resposta": resp,
                    "peso": item["peso"],
                    "critico": item["critico"],
                }

    # LADO DIREITO: Erros Críticos, Experiência Geral, Score Card
    with col_right:
        soma_pontos_obtidos = 0.0
        soma_pontos_possiveis = 0.0
        teve_erro_critico = False

        # Avaliação de todas as respostas coletadas até agora
        for categoria in ["Erros Críticos", "Experiência Geral do Cliente"]:
            st.markdown(
                f'<div class="category-header">{categoria}</div>',
                unsafe_allow_html=True,
            )

            itens = [
                i for i in CRITERIOS_OBLIGATORIOS if i["cat"] == categoria
            ]
            for idx, item in enumerate(itens):
                key = f"q_{categoria}_{idx}_{v}"

                resp = st.radio(
                    label=item["desc"],
                    options=["Conforme", "Não Conforme", "Não se aplica"],
                    index=0,
                    horizontal=True,
                    key=key,
                )

                respostas[item["desc"]] = {
                    "resposta": resp,
                    "peso": item["peso"],
                    "critico": item["critico"],
                }

        # Cálculo consolidade da Nota Final (Passando por TODAS as respostas registradas)
        for desc, det in respostas.items():
            if det["critico"] and det["resposta"] == "Não Conforme":
                teve_erro_critico = True
            elif not det["critico"]:
                if det["resposta"] == "Conforme":
                    soma_pontos_obtidos += det["peso"]
                    soma_pontos_possiveis += det["peso"]
                elif det["resposta"] == "Não Conforme":
                    soma_pontos_possiveis += det["peso"]

        # Cálculo do Score
        if teve_erro_critico or soma_pontos_possiveis == 0:
            nota_final = 0.0
        else:
            nota_final = round(
                (soma_pontos_obtidos / soma_pontos_possiveis) * 100, 2
            )

        status_resultado = "Adequado" if nota_final >= 85 else "Inadequado"
        emoji_status = "😊" if status_resultado == "Adequado" else "😞"
        class_status = (
            "status-adequadas"
            if status_resultado == "Adequado"
            else "status-inadequado"
        )

        st.markdown(
            f"""
            <div class="score-card">
                <span style="font-size: 14px; color: #6b7280; font-weight: bold;">Pontuação:</span>
                <div style="font-size: 50px; margin: 10px 0;">{emoji_status} <span class="score-value">{int(nota_final)} / 100</span></div>
                <div class="{class_status}">{status_resultado}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        descricao = st.text_area(
            label="Descrição / Observações Gerais *",
            placeholder=(
                "Descreva aqui os detalhes do atendimento, motivos e"
                " principais observações..."
            ),
            height=120,
            key=f"desc_{v}"
        )

    # BOTÕES DE AÇÃO
    st.markdown("---")
    b_col1, b_col2, b_col3 = st.columns([6, 2, 2])

    if b_col2.button("❌ Cancelar", use_container_width=True, key=f"btn_cancel_{v}"):
        reset_formulario()
        st.rerun()

    if b_col3.button("💾 Cadastrar / Salvar", use_container_width=True, key=f"btn_save_{v}"):
        if avaliador == "Selecione...":
            st.error("Por favor, selecione um Avaliador antes de salvar!")
        elif colaborador == "Selecione...":
            st.error("Por favor, selecione um Colaborador antes de salvar!")
        else:
            st.session_state.pending_data = {
                "avaliador": avaliador,
                "operacao": operacao,
                "gestor": gestor,
                "colaborador": colaborador,
                "data_ligacao": data_ligacao,
                "hora_inicio": hr_inicio,
                "minuto_inicio": min_inicio,
                "duracao": duracao,
                "data_audicao": data_audicao,
                "canal": canal,
                "telefone": telefone,
                "cnpj": cnpj,
                "assunto": assunto,
                "pontuacao": nota_final,
                "status_resultado": status_resultado,
                "descricao": descricao,
                "respostas": respostas,
            }
            modal_confirmacao()

# ------------------------------------------
# ABA 2: CONSULTA E CRUD DE RESULTADOS
# ------------------------------------------
with tab_resultados:
    st.subheader("📊 Histórico de Monitorias Preenchidas")
    df_dados = buscar_registros()  # Invocação corrigida adicionando ()

    if not df_dados.empty:
        st.dataframe(
            df_dados.drop(columns=["respostas"], errors="ignore"),
            use_container_width=True,
            hide_index=True,
        )

        # Opção para excluir registros
        with st.expander("🗑️ Excluir Registro"):
            id_excluir = st.number_input("Informe o ID para excluir:", min_value=1, step=1)
            if st.button("Confirmar Exclusão"):
                try:
                    excluir_registro(id_excluir)
                    st.success(f"Registro {id_excluir} excluído!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir: {e}")
    else:
        st.info("Nenhum registro de monitoria encontrado no banco de dados.")
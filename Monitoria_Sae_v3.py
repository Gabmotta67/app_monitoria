import datetime
import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client

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

# Inicialização dos estados da sessão
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "edit_payload" not in st.session_state:
    st.session_state.edit_payload = None
if "pending_data" not in st.session_state:
    st.session_state.pending_data = None
if "form_version" not in st.session_state:
    st.session_state.form_version = 0
if "notification" not in st.session_state:
    st.session_state.notification = None


def reset_formulario():
    """Limpa os dados pendentes, sai do modo de edição e reseta a versão dos inputs."""
    st.session_state.editing_id = None
    st.session_state.edit_payload = None
    st.session_state.pending_data = None
    st.session_state.form_version += 1


def exibir_notificacoes_pendentes():
    """Exibe notificações no formato Toast flutuante."""
    if st.session_state.notification:
        notif = st.session_state.notification
        mensagem = notif.get("message", "")
        icone = notif.get("icon", "ℹ️")
        st.toast(mensagem, icon=icone)
        st.session_state.notification = None


exibir_notificacoes_pendentes()


# ==========================================
# CONEXÃO COM O SUPABASE
# ==========================================
@st.cache_resource
def get_supabase_client() -> Client:
    try:
        url = "https://jevgwcavrxhyhmoodxyb.supabase.co"
        key = "sb_publishable_hKahILaV2iOtDid3A-tOKA_hXp8pov5"
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase: {e}")
        return None


@st.cache_data(ttl=3600)
def carregar_dados_colaboradores():
    try:
        supabase = get_supabase_client()
        if not supabase:
            return ["Selecione..."], {}

        response = (
            supabase.table("db_pessoas")
            .select("nome_base_volumetria_power_bi, supervisor")
            .execute()
        )

        data = response.data
        if not data:
            return ["Selecione..."], {}

        df_temp = pd.DataFrame(data)
        if (
            "nome_base_volumetria_power_bi" in df_temp.columns
            and "supervisor" in df_temp.columns
        ):
            df_temp = df_temp.dropna(subset=["nome_base_volumetria_power_bi"])
            df_temp["nome_clean"] = (
                df_temp["nome_base_volumetria_power_bi"].astype(str).str.strip()
            )
            df_temp["supervisor_clean"] = (
                df_temp["supervisor"].fillna("").astype(str).str.strip()
            )

            df_valid = df_temp[
                (df_temp["nome_clean"] != "")
                & (
                    ~df_temp["nome_clean"]
                    .str.lower()
                    .isin(["nan", "none", "null"])
                )
            ]

            mapa_supervisores = dict(
                zip(df_valid["nome_clean"], df_valid["supervisor_clean"])
            )
            nomes_validos = sorted(df_valid["nome_clean"].unique())

            return ["Selecione..."] + nomes_validos, mapa_supervisores
        return ["Selecione..."], {}

    except Exception as e:
        st.error(f"Erro ao buscar colaboradores no Supabase: {e}")
        return ["Selecione..."], {}


def salvar_registro(dados, id_registro=None):
    supabase = get_supabase_client()
    if not supabase:
        raise Exception("Cliente Supabase não inicializado.")

    payload = {
        "avaliador": dados["avaliador"],
        "operacao": dados["operacao"],
        "gestor": dados["gestor"],
        "colaborador": dados["colaborador"],
        "data_ligacao": str(dados["data_ligacao"]),
        "hora_inicio": dados["hora_inicio"],
        "minuto_inicio": dados["minuto_inicio"],
        "duracao": dados["duracao"],
        "data_audicao": str(dados["data_audicao"]),
        "canal": dados["canal"],
        "telefone": dados["telefone"],
        "cnpj": dados["cnpj"],
        "assunto": dados["assunto"],
        "pontuacao": dados["pontuacao"],
        "status_resultado": dados["status_resultado"],
        "descricao": dados["descricao"],
        "respostas": dados["respostas"],
    }

    if id_registro is None:
        res = supabase.table("monitoria_whatsapp").insert(payload).execute()
    else:
        res = (
            supabase.table("monitoria_whatsapp")
            .update(payload)
            .eq("id", id_registro)
            .execute()
        )

    return res


def buscar_registros():
    try:
        supabase = get_supabase_client()
        if not supabase:
            return pd.DataFrame()

        response = (
            supabase.table("monitoria_whatsapp")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        data = response.data
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao consultar o Supabase: {e}")
        return pd.DataFrame()


def excluir_registro(id_registro):
    supabase = get_supabase_client()
    if supabase:
        supabase.table("monitoria_whatsapp").delete().eq(
            "id", id_registro
        ).execute()


# ==========================================
# CRITÉRIOS E PESOS
# ==========================================
CRITERIOS_OBLIGATORIOS = [
    {
        "cat": "Habilidades de Comunicação",
        "desc": "Operador(a) atende o cliente dentro do tempo estabelecido",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": "Operador(a) utiliza palavras de cordialidade (ex.: por favor, por gentileza, obrigado(a)?)",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": "Operador(a) utilizou escrita clara, sem abreviações, erros graves no chat?",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Habilidades de Comunicação",
        "desc": "Operador(a) conduziu o atendimento com segurança, sem demonstrar insegurança nas respostas escritas?",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) leu atentamente a solicitação do cliente, sem ignorar ou responder fora do contexto no chat?",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) demonstrou paciência e cordialidade mesmo diante de situações de insatisfação do cliente no chat?",
        "peso": 7.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) evitou respostas secas ou ríspidas durante o atendimento via chat?",
        "peso": 7.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) explicou as informações de forma simples e fácil de entender no chat?",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) demonstrou domínio dos processos e segurança nas informações prestadas durante o atendimento via chat?",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador(a) encerrou o atendimento de forma educada e cordial, confirmando a finalização com o cliente?",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Avaliação das Necessidades do Cliente",
        "desc": "Operador (a) solicita novamente informações já passadas pelo cliente?",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Operador(a) orientou corretamente o cliente quanto à documentação necessária e ao envio/anexo na interação via chat?",
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Operador(a) informou o protocolo de atendimento, quando aplicável?",
        "peso": 3.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "A ligação foi classificada corretamente no sistema (Salesforce)?",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Operador(a) utilizou corretamente os recursos do sistema para agilizar o atendimento via chat? (frases prontas)",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Operador(a) quando solicitado cancelamento, realiza o processo corretamente?",
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Operador(a) realizou a confirmação de telefone e e-mail cadastrados?",
        "peso": 4.0,
        "critico": False,
    },
    {
        "cat": "Processos",
        "desc": "Enviou corretamente boleto e/ou outros documentos via sigo ou e-mail, quando necessário?",
        "peso": 5.0,
        "critico": False,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) realiza atendimento sem desvios de conduta?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) realiza o atendimento sem concordar/realizar comentários inadequados?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador(a) abandonou a interação via Chat, ocasionando envio de mensagens automáticas e finalização sistêmica da interação sem prestar atendimento?",
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
        "desc": "Operador(a) confirmou o responsável legal ( confirmou no site/ sigo se é o mesmo)?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) orienta o beneficiário a excluir ou esvazias as vidas no portal?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Erros Críticos",
        "desc": "Operador (a) influência / estimula o cliente ao cancelamento?",
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
        "desc": "Operador(a) abriu o Saccad corretamente, quando aplicável ao atendimento via chat?",
        "peso": 100.0,
        "critico": True,
    },
    {
        "cat": "Experiência Geral do Cliente",
        "desc": "Operador(a) orientou o cliente sobre a pesquisa de satisfação e enviou o link ao final do atendimento via chat?",
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Experiência Geral do Cliente",
        "desc": "Operador(a) explicou corretamente os procedimentos de atualização de cadastro(e-mail) para envio dos relatórios conforme registro na aba endereço",
        "peso": 6.0,
        "critico": False,
    },
    {
        "cat": "Experiência Geral do Cliente",
        "desc": "Operador(a) justificou a ausência quando houve necessidade de tempo para análise, mantendo o cliente informado no chat?",
        "peso": 5.0,
        "critico": False,
    },
]


# ==========================================
# MODAL DE CONFIRMAÇÃO DIALOG
# ==========================================
@st.dialog("Confirmar Gravação da Monitoria")
def modal_confirmacao():
    dados = st.session_state.pending_data

    st.warning("Verifique as informações abaixo antes de salvar:")
    st.markdown(f"**Colaborador:** {dados['colaborador']}")
    st.markdown(f"**Pontuação:** `{dados['pontuacao']} / 100`")
    st.markdown(f"**Status Final:** **{dados['status_resultado']}**")
    st.markdown(f"**Assunto:** {dados['assunto']}")

    col_sim, col_nao = st.columns(2)
    if col_sim.button("✅ Confirmar e Salvar", use_container_width=True):
        try:
            salvar_registro(dados, id_registro=st.session_state.editing_id)
            msg_sucesso = (
                f"Monitoria ID {st.session_state.editing_id} atualizada com sucesso!"
                if st.session_state.editing_id
                else f"Monitoria do colaborador '{dados['colaborador']}' salva com sucesso!"
            )
            st.session_state.notification = {
                "type": "success",
                "message": msg_sucesso,
                "icon": "🎉",
            }
            reset_formulario()
            st.rerun()
        except Exception as e:
            st.session_state.notification = {
                "type": "error",
                "message": f"Falha ao salvar a monitoria no Supabase: {str(e)}",
                "icon": "❌",
            }
            st.rerun()

    if col_nao.button("❌ Cancelar", use_container_width=True):
        st.session_state.pending_data = None
        st.session_state.notification = {
            "type": "warning",
            "message": "Gravação cancelada pelo usuário. Os dados não foram salvos.",
            "icon": "⚠️",
        }
        st.rerun()


# ==========================================
# NAVEGAÇÃO DE ABAS
# ==========================================
st.markdown(
    '<div class="header-bar">Ficha de Monitoração Chat PME</div>',
    unsafe_allow_html=True,
)
tab_formulario, tab_resultados = st.tabs(
    ["Preenchimento da Monitoria", "Acompanhamento de Resultados"]
)

# ------------------------------------------
# ABA 1: FORMULÁRIO DE MONITORIA
# ------------------------------------------
with tab_formulario:
    v = st.session_state.form_version
    payload_edicao = st.session_state.edit_payload or {}

    if st.session_state.editing_id:
        st.info(
            f"✏️ **Modo Edição Ativo:** Editando o registro **ID #{st.session_state.editing_id}**"
        )
        if st.button("⬅️ Sair da Edição e Limpar Formulário", key=f"btn_cancel_edit_{v}"):
            reset_formulario()
            st.session_state.notification = {
                "type": "info",
                "message": "Edição cancelada. Formulário reiniciado.",
                "icon": "ℹ️",
            }
            st.rerun()

    # Carrega colaboradores
    colaboradores, mapa_supervisores = carregar_dados_colaboradores()

    l1_col1, l1_col2, l1_col3 = st.columns(3)

    avaliadores = [
        "Selecione...",
        "JEAN ROBERTO DA SILVA DOS SANTOS",
        "LISANDRA OLIVEIRA LIMA DA SILVA",
        "BRUNA CAROLINE RIBEIRO DA SILVA",
        "ANA LARISSA SOARES MARTINS",
        "LAURA MARIA ZAMPIERI",
    ]

    val_avaliador = payload_edicao.get("avaliador", "JEAN ROBERTO DA SILVA DOS SANTOS")
    idx_avaliador = avaliadores.index(val_avaliador) if val_avaliador in avaliadores else 1

    avaliador = l1_col1.selectbox("Avaliador *:", avaliadores, index=idx_avaliador, key=f"avaliador_{v}")

    val_colaborador = payload_edicao.get("colaborador", "Selecione...")
    idx_colaborador = colaboradores.index(val_colaborador) if val_colaborador in colaboradores else 0

    colaborador = l1_col2.selectbox("Colaborador *:", colaboradores, index=idx_colaborador, key=f"colaborador_{v}")

    gestor_dinamico = payload_edicao.get("gestor", mapa_supervisores.get(colaborador, "DANIEL PIMENTA NEVES"))
    gestor = l1_col3.text_input("Gestor:", value=gestor_dinamico, key=f"gestor_{v}_{colaborador}")

    l2_col1, l2_col2, l2_col3, l2_col4 = st.columns([1.5, 1.5, 1, 1])

    operacao = l2_col1.text_input("Operação:", value=payload_edicao.get("operacao", "PME"), key=f"operacao_{v}")

    opcoes_duracao = ["00:01", "00:02", "00:03", "00:04", "00:05", "00:06", "00:07", "00:08", "00:09", "00:10", "00:11", "00:12", "00:13", "00:14", "00:15", "00:16", "00:17", "00:18", "00:19", "00:20", "00:21", "00:22", "00:23", "00:24", "00:25", "00:26", "00:27", "00:28", "00:29", "00:30", "00:31", "00:32", "00:33", "00:34", "00:35", "00:36", "00:37", "00:38", "00:39", "00:40", "00:41", "00:42", "00:43", "00:44", "00:45", "00:46", "00:47", "00:48", "00:49", "00:50", "00:51", "00:52", "00:53", "00:54", "00:55", "00:56", "00:57", "00:58", "00:59", "01:00"]
    val_duracao = payload_edicao.get("duracao", "00:05")
    idx_duracao = opcoes_duracao.index(val_duracao) if val_duracao in opcoes_duracao else 0

    duracao = l2_col2.selectbox("Duração (Min):", opcoes_duracao, index=idx_duracao, key=f"duracao_{v}")

    opcoes_hr = [f"{h:02d}" for h in range(24)]
    val_hr = str(payload_edicao.get("hora_inicio", "09")).zfill(2)
    idx_hr = opcoes_hr.index(val_hr) if val_hr in opcoes_hr else 9

    hr_inicio = l2_col3.selectbox("Hora Início:", opcoes_hr, index=idx_hr, key=f"hr_inicio_{v}")

    opcoes_min = [f"{m:02d}" for m in range(60)]
    val_min = str(payload_edicao.get("minuto_inicio", "00")).zfill(2)
    idx_min = opcoes_min.index(val_min) if val_min in opcoes_min else 0

    min_inicio = l2_col4.selectbox("Minuto Início:", opcoes_min, index=idx_min, key=f"min_inicio_{v}")

    l3_col1, l3_col2, l3_col3 = st.columns(3)

    dt_lig_val = (
        datetime.datetime.strptime(payload_edicao["data_ligacao"], "%Y-%m-%d").date()
        if "data_ligacao" in payload_edicao and payload_edicao["data_ligacao"]
        else datetime.date.today()
    )
    dt_aud_val = (
        datetime.datetime.strptime(payload_edicao["data_audicao"], "%Y-%m-%d").date()
        if "data_audicao" in payload_edicao and payload_edicao["data_audicao"]
        else datetime.date.today()
    )

    data_ligacao = l3_col1.date_input(
        label="Data da Interação *",
        value=dt_lig_val,
        format="DD/MM/YYYY",
        key=f"dt_ligacao_{v}",
    )
    data_audicao = l3_col2.date_input(
        label="Data da Audição *",
        value=dt_aud_val,
        format="DD/MM/YYYY",
        key=f"dt_audicao_{v}",
    )

    opcoes_canal = ["Interação WPP", "Calibração"]
    val_canal = payload_edicao.get("canal", "Interação WPP")
    idx_canal = opcoes_canal.index(val_canal) if val_canal in opcoes_canal else 0

    canal = l3_col3.selectbox("Canal:", opcoes_canal, index=idx_canal, key=f"canal_{v}")

    l4_col1, l4_col2, l4_col3 = st.columns([1.5, 1.5, 3])
    telefone = l4_col1.text_input(
        label="Telefone Chamador *",
        value=payload_edicao.get("telefone", ""),
        placeholder="(16) 99999-9999",
        key=f"tel_{v}",
    )
    cnpj = l4_col2.text_input(
        label="CNPJ *",
        value=payload_edicao.get("cnpj", ""),
        placeholder="00.000.000/0001-00",
        key=f"cnpj_{v}",
    )
    assunto = l4_col3.text_input(
        label="Assunto *",
        value=payload_edicao.get("assunto", ""),
        placeholder="Ex: Segunda via de boleto...",
        key=f"assunto_{v}",
    )

    st.markdown("---")

    respostas = {}
    respostas_salvas = payload_edicao.get("respostas", {})
    col_left, col_right = st.columns(2)

    options_radio = ["Conforme", "Não Conforme", "Não se aplica"]

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
            itens = [i for i in CRITERIOS_OBLIGATORIOS if i["cat"] == categoria]
            for idx, item in enumerate(itens):
                key = f"q_{categoria}_{idx}_{v}"

                resp_previa = respostas_salvas.get(item["desc"], {}).get("resposta", "Conforme")
                idx_radio = options_radio.index(resp_previa) if resp_previa in options_radio else 0

                resp = st.radio(
                    label=item["desc"],
                    options=options_radio,
                    index=idx_radio,
                    horizontal=True,
                    key=key,
                )

                respostas[item["desc"]] = {
                    "resposta": resp,
                    "peso": item["peso"],
                    "critico": item["critico"],
                }

    with col_right:
        soma_pontos_obtidos = 0.0
        soma_pontos_possiveis = 0.0
        teve_erro_critico = False

        for categoria in ["Erros Críticos", "Experiência Geral do Cliente"]:
            st.markdown(
                f'<div class="category-header">{categoria}</div>',
                unsafe_allow_html=True,
            )

            itens = [i for i in CRITERIOS_OBLIGATORIOS if i["cat"] == categoria]
            for idx, item in enumerate(itens):
                key = f"q_{categoria}_{idx}_{v}"

                resp_previa = respostas_salvas.get(item["desc"], {}).get("resposta", "Conforme")
                idx_radio = options_radio.index(resp_previa) if resp_previa in options_radio else 0

                resp = st.radio(
                    label=item["desc"],
                    options=options_radio,
                    index=idx_radio,
                    horizontal=True,
                    key=key,
                )

                respostas[item["desc"]] = {
                    "resposta": resp,
                    "peso": item["peso"],
                    "critico": item["critico"],
                }

        for desc, det in respostas.items():
            if det["critico"] and det["resposta"] == "Não Conforme":
                teve_erro_critico = True
            elif not det["critico"]:
                if det["resposta"] == "Conforme":
                    soma_pontos_obtidos += det["peso"]
                    soma_pontos_possiveis += det["peso"]
                elif det["resposta"] == "Não Conforme":
                    soma_pontos_possiveis += det["peso"]

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
            value=payload_edicao.get("descricao", ""),
            placeholder="Descreva aqui os detalhes do atendimento...",
            height=120,
            key=f"desc_{v}",
        )

    st.markdown("---")
    b_col1, b_col2, b_col3 = st.columns([6, 2, 2])

    if b_col2.button("❌ Limpar Form", use_container_width=True, key=f"btn_cancel_{v}"):
        reset_formulario()
        st.session_state.notification = {
            "type": "warning",
            "message": "Formulário limpo com sucesso.",
            "icon": "🧹",
        }
        st.rerun()

    lbl_salvar = "🔄 Atualizar Registro" if st.session_state.editing_id else "💾 Cadastrar / Salvar"
    if b_col3.button(lbl_salvar, use_container_width=True, key=f"btn_save_{v}"):
        if avaliador == "Selecione...":
            st.toast("Por favor, selecione um Avaliador!", icon="⚠️")
            st.error("Por favor, selecione um Avaliador antes de salvar!")
        elif colaborador == "Selecione...":
            st.toast("Por favor, selecione um Colaborador!", icon="⚠️")
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
    df_dados = buscar_registros()

    if not df_dados.empty:
        # Exibição limpa da tabela principal
        cols_visualizacao = [c for c in df_dados.columns if c != "respostas"]
        st.dataframe(
            df_dados[cols_visualizacao],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.markdown("### ⚙️ Ações nos Registros")

        col_select, col_actions = st.columns([2, 3])

        lista_ids = df_dados["id"].tolist()
        id_selecionado = col_select.selectbox(
            "Selecione um ID de Registro para gerenciar:",
            options=lista_ids,
            format_func=lambda x: f"ID #{x} - {df_dados[df_dados['id'] == x]['colaborador'].values[0]} ({df_dados[df_dados['id'] == x]['pontuacao'].values[0]} pts)",
        )

        col_btn_edit, col_btn_del, _ = col_actions.columns([1, 1, 1])

        # AÇÃO 1: EDITAR REGISTRO
        if col_btn_edit.button("✏️ Editar Registro", use_container_width=True):
            registro = df_dados[df_dados["id"] == id_selecionado].iloc[0].to_dict()

            st.session_state.editing_id = id_selecionado
            st.session_state.edit_payload = registro
            st.session_state.form_version += 1

            st.session_state.notification = {
                "type": "info",
                "message": f"Registro #{id_selecionado} carregado no formulário para edição.",
                "icon": "✏️",
            }
            st.rerun()

        # AÇÃO 2: EXCLUIR REGISTRO
        if col_btn_del.button("🗑️ Excluir Registro", use_container_width=True):
            try:
                excluir_registro(id_selecionado)
                if st.session_state.editing_id == id_selecionado:
                    reset_formulario()

                st.session_state.notification = {
                    "type": "success",
                    "message": f"Registro ID #{id_selecionado} excluído com sucesso!",
                    "icon": "🗑️",
                }
                st.rerun()
            except Exception as e:
                st.session_state.notification = {
                    "type": "error",
                    "message": f"Erro ao excluir o registro ID {id_selecionado}: {e}",
                    "icon": "❌",
                }
                st.rerun()
    else:
        st.info("Nenhum registro de monitoria encontrado no Supabase.")
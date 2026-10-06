import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
    FiSearch,
    FiCalendar,
    FiSliders,
    FiChevronDown,
    FiChevronLeft,
    FiChevronRight
} from "react-icons/fi";

import estilo from "./agendamentosadm.module.css";
import { API_URL, apiFetch, mensagemDaApi } from "../../services/api";
import MensagemCard from "../../components/MensagemCard/MensagemCard";
import Botao from "../../components/Button/Button";
import { lerUsuarioLocal } from "../../contexts/authStorage";


// =====================================================
// FORMATAÇÃO (API -> tela)
// =====================================================

function formatarData(iso) {
    if (!iso) return "-";
    const [data] = String(iso).split("T");
    const [ano, mes, dia] = data.split("-");
    return `${dia}/${mes}/${ano}`;
}

function formatarHora(iso) {
    if (!iso) return "";
    const [, hora] = String(iso).split("T");
    return (hora || "").slice(0, 5);
}

function rotuloStatus(status) {
    if (status === "cancelado") return "Cancelado";
    if (status === "concluido") return "Concluído";
    if (status === "faltou") return "Cliente faltou";
    return "Agendado";
}

function descreverHistorico(status) {
    return status === "faltou" ? "Cliente não compareceu" : "Atendimento concluído";
}


// =====================================================
// COMPONENTE: CABEÇALHO
// =====================================================

function CabecalhoAgendamentos() {

    return (
        <section className={estilo.cabecalhoPagina}>

            <h1>AGENDAMENTOS</h1>

            <p>
                Gerencie e visualize todos os atendimentos da barbearia.
            </p>

        </section>
    );
}


// =====================================================
// COMPONENTE: FILTROS
// =====================================================

function FiltrosAgendamentos({
                                 busca,
                                 setBusca,
                                 filtroStatus,
                                 setFiltroStatus,
                                 filtroData,
                                 setFiltroData
                             }) {

    const [mostrarStatus, setMostrarStatus] = useState(false);
    const [mostrarData, setMostrarData] = useState(false);

    return (
        <section className={estilo.filtros}>

            {/* BUSCA */}

            <div className={estilo.campoBusca}>

                <FiSearch />

                <input
                    type="text"
                    placeholder="Pesquisar por cliente"
                    value={busca}
                    onChange={(e) => setBusca(e.target.value)}
                />

            </div>


            {/* FILTROS DA DIREITA */}

            <div className={estilo.filtrosDireita}>

                {/* FILTRO DE DATA */}

                <div className={estilo.filtroWrapper}>

                    <button
                        className={estilo.botaoFiltro}
                        onClick={() => {
                            setMostrarData(!mostrarData);
                            setMostrarStatus(false);
                        }}
                    >
                        <FiCalendar />

                        {filtroData === "todas" ? "Filtrar por data" : filtroData === "recentes" ? "Mais recentes" : "Mais antigas"}

                        <FiChevronDown
                            className={
                                mostrarData
                                    ? estilo.iconeRotacionado
                                    : ""
                            }
                        />

                    </button>

                    {mostrarData && (

                        <div className={estilo.dropdown}>

                            <button
                                onClick={() => {
                                    setFiltroData("todas");
                                    setMostrarData(false);
                                }}
                            >
                                Todas as datas
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroData("recentes");
                                    setMostrarData(false);
                                }}
                            >
                                Mais recentes
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroData("antigas");
                                    setMostrarData(false);
                                }}
                            >
                                Mais antigas
                            </button>

                        </div>

                    )}

                </div>


                {/* FILTRO DE STATUS */}

                <div className={estilo.filtroWrapper}>

                    <button
                        className={estilo.botaoFiltro}
                        onClick={() => {
                            setMostrarStatus(!mostrarStatus);
                            setMostrarData(false);
                        }}
                    >
                        <FiSliders />

                        {filtroStatus === "Todos" ? "Status" : rotuloStatus(filtroStatus)}

                    </button>

                    {mostrarStatus && (

                        <div className={estilo.dropdown}>

                            <button
                                onClick={() => {
                                    setFiltroStatus("Todos");
                                    setMostrarStatus(false);
                                }}
                            >
                                Todos
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroStatus("agendado");
                                    setMostrarStatus(false);
                                }}
                            >
                                Agendados
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroStatus("concluido");
                                    setMostrarStatus(false);
                                }}
                            >
                                Concluídos
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroStatus("faltou");
                                    setMostrarStatus(false);
                                }}
                            >
                                Clientes que faltaram
                            </button>

                            <button
                                onClick={() => {
                                    setFiltroStatus("cancelado");
                                    setMostrarStatus(false);
                                }}
                            >
                                Cancelados
                            </button>

                        </div>

                    )}

                </div>

            </div>

        </section>
    );
}


// =====================================================
// COMPONENTE: STATUS
// =====================================================

function StatusAgendamento({ status }) {

    const classeStatus = {

        "agendado": estilo.statusPendente,
        "confirmado": estilo.statusPendente,

        "concluido": estilo.statusConcluido,

        "faltou": estilo.statusFaltou,

        "cancelado": estilo.statusCancelado

    };

    return (
        <span className={`${estilo.status} ${classeStatus[status] || ""}`}>
            {rotuloStatus(status).toUpperCase()}
        </span>
    );
}


// =====================================================
// COMPONENTE: FILTRO DE BARBEARIA (só ADM)
// =====================================================

function FiltroBarbearias({ barbearias, filtroBarbearia, setFiltroBarbearia }) {
    const nomeAtivo = filtroBarbearia === "todas"
        ? "Todas"
        : (barbearias.find((b) => String(b.id) === String(filtroBarbearia))?.nome || `#${filtroBarbearia}`);

    return (
        <section className={estilo.filtroBarbearia} aria-label="Filtrar por barbearia">
            <span>Barbearia:</span>
            <span className={estilo.filtroAtual} aria-live="polite">Filtrando: <strong>{nomeAtivo}</strong></span>
            <div className={estilo.filtroBotoes}>
                <button type="button"
                    className={`${estilo.botaoFiltro} ${filtroBarbearia === "todas" ? estilo.filtroAtivo : ""}`}
                    aria-pressed={filtroBarbearia === "todas"}
                    onClick={() => setFiltroBarbearia("todas")}>
                    Todas
                </button>
                {barbearias.map((barbearia) => {
                    const ativo = String(filtroBarbearia) === String(barbearia.id);
                    return (
                        <button type="button" key={barbearia.id}
                            className={`${estilo.botaoFiltro} ${ativo ? estilo.filtroAtivo : ""}`}
                            aria-pressed={ativo}
                            title={ativo ? `${barbearia.nome} (filtro ativo)` : `Filtrar por ${barbearia.nome}`}
                            onClick={() => setFiltroBarbearia(String(barbearia.id))}>
                            {barbearia.nome}
                        </button>
                    );
                })}
            </div>
        </section>
    );
}


// =====================================================
// COMPONENTE: CARD DE AGENDAMENTO
// =====================================================

function CardAgendamentoAdm({ agendamento, indice, onAcao, onVerImagens, agora }) {

    const cancelado = agendamento.status === "cancelado";
    const concluido = agendamento.status === "concluido";
    const faltou = agendamento.status === "faltou";
    const finalizado = cancelado || concluido || faltou;
    const atendimentoLiberado = agora && new Date(agendamento.fim_em).getTime() <= agora.getTime();
    const historico = agendamento.historico_atendimento || [];
    const temImagens = Boolean(agendamento.corte_imagem_url || agendamento.visagismo_foto_url);

    return (
        <article
            className={estilo.cardAgendamento}
            style={{ "--delay": `${indice * 0.08}s` }}
        >

            <div className={estilo.cardTopo}>
                <div>
                    <h3>{agendamento.cliente_nome}</h3>
                    <p>
                        {(agendamento.servicos_nomes || []).join(" + ") || "-"}
                        {agendamento.funcionario_nome && ` · ${agendamento.funcionario_nome}`}
                    </p>
                    <p>
                        {formatarData(agendamento.inicio_em)} · {formatarHora(agendamento.inicio_em)} - {formatarHora(agendamento.fim_em)}
                        {Number(agendamento.valor_total) > 0 && (
                            <> · R$ {Number(agendamento.valor_total).toFixed(2).replace(".", ",")}</>
                        )}
                    </p>
                </div>
                <StatusAgendamento status={agendamento.status} />
            </div>

            {temImagens && (
                <button type="button" className={estilo.botaoVerMais}
                    onClick={() => onVerImagens(agendamento)}>
                    Ver mais
                </button>
            )}

            {historico.length > 0 && (
                <div className={estilo.historicoAtendimento}>
                    <strong>Histórico de atendimento</strong>
                    {historico.map((item) => (
                        <p key={item.id_historico}>
                            {descreverHistorico(item.status)} em {formatarData(item.registrado_em)} às {formatarHora(item.registrado_em)}
                            {item.responsavel_nome && ` · ${item.responsavel_nome}`}
                        </p>
                    ))}
                </div>
            )}

            {!finalizado && (
                <div className={estilo.cardAcoes}>
                    {atendimentoLiberado ? (
                        <>
                            <button type="button" className={estilo.acaoConcluir}
                                onClick={() => onAcao(agendamento, "concluir")}>
                                Marcar concluído
                            </button>
                            <button type="button" className={estilo.acaoFaltou}
                                onClick={() => onAcao(agendamento, "faltou")}>
                                Cliente faltou
                            </button>
                        </>
                    ) : (
                        <p className={estilo.aguardandoAtendimento}>A confirmação do atendimento será liberada ao fim do horário.</p>
                    )}
                    <Botao texto="Avisar" acao={() => onAcao(agendamento, "avisar")} />
                    <Botao texto="Reagendar" acao={() => onAcao(agendamento, "reagendar")} />
                    <Botao texto="Cancelar" acao={() => onAcao(agendamento, "cancelar")} />
                </div>
            )}

        </article>
    );
}


// =====================================================
// COMPONENTE: LISTA EM CARDS
// =====================================================

function ListaAgendamentos({ agendamentos, onAcao, onVerImagens, agora }) {

    if (!agendamentos.length) {
        return <p className={estilo.semResultados}>Nenhum agendamento encontrado.</p>;
    }

    return (
        <div className={estilo.gradeCards}>
            {agendamentos.map((agendamento, indice) => (
                <CardAgendamentoAdm
                    key={agendamento.id_agendamento}
                    agendamento={agendamento}
                    indice={indice}
                    onAcao={onAcao}
                    onVerImagens={onVerImagens}
                    agora={agora}
                />
            ))}
        </div>
    );
}


// =====================================================
// COMPONENTE: PAGINAÇÃO
// =====================================================

function Paginacao({
                       paginaAtual,
                       setPaginaAtual,
                       totalPaginas,
                       totalResultados,
                       inicio,
                       fim
                   }) {

    return (
        <div className={estilo.rodapeTabela}>

            <p>
                Exibindo {totalResultados === 0 ? 0 : inicio + 1}-
                {Math.min(fim, totalResultados)} de{" "}
                {totalResultados} agendamentos
            </p>

            <div className={estilo.paginacao}>

                <button
                    disabled={paginaAtual === 1}
                    onClick={() =>
                        setPaginaAtual(paginaAtual - 1)
                    }
                    aria-label="Página anterior"
                >
                    <FiChevronLeft />
                </button>

                {Array.from(
                    { length: totalPaginas },
                    (_, indice) => indice + 1
                ).map((pagina) => (

                    <button
                        key={pagina}
                        className={
                            paginaAtual === pagina
                                ? estilo.paginaAtiva
                                : ""
                        }
                        onClick={() => setPaginaAtual(pagina)}
                    >
                        {pagina}
                    </button>

                ))}

                <button
                    disabled={paginaAtual === totalPaginas}
                    onClick={() =>
                        setPaginaAtual(paginaAtual + 1)
                    }
                    aria-label="Próxima página"
                >
                    <FiChevronRight />
                </button>

            </div>

        </div>
    );
}


// =====================================================
// PÁGINA PRINCIPAL
// =====================================================

function AgendamentosAdm() {

    const [params] = useSearchParams();

    const [busca, setBusca] = useState("");

    const [filtroStatus, setFiltroStatus] = useState("Todos");

    const [filtroData, setFiltroData] = useState("todas");

    const [paginaAtual, setPaginaAtual] = useState(1);

    const [agendamentos, setAgendamentos] = useState([]);

    const [barbearias, setBarbearias] = useState([]);

    const [filtroBarbearia, setFiltroBarbearia] = useState(() => params.get("barbearia") || "todas");

    const [souAdm] = useState(() => Number(lerUsuarioLocal()?.tipo) === 0);

    const [carregando, setCarregando] = useState(true);

    const [erro, setErro] = useState("");

    const [mensagem, setMensagem] = useState(null);

    const [acao, setAcao] = useState(null);

    const [agendamentoComImagens, setAgendamentoComImagens] = useState(null);

    const [textoAviso, setTextoAviso] = useState("");

    const [novaData, setNovaData] = useState("");

    const [novoHorario, setNovoHorario] = useState("");

    const [processando, setProcessando] = useState(false);

    const [agora, setAgora] = useState(null);

    const itensPorPagina = 15; // grade 3 x 5


    async function carregar(idBarbearia) {
        setCarregando(true);
        setErro("");
        try {
            const sufixo = (souAdm && idBarbearia && idBarbearia !== "todas")
                ? `?id_barbearia=${encodeURIComponent(idBarbearia)}`
                : "";
            const dados = await apiFetch(`/agendamentos${sufixo}`);
            setAgendamentos(dados.agendamentos || []);
        } catch (error) {
            setErro(mensagemDaApi(error));
            setAgendamentos([]);
        } finally {
            setCarregando(false);
        }
    }

    useEffect(() => {
        if (souAdm) {
            apiFetch("/barbearias-disponiveis")
                .then((dados) => setBarbearias(Array.isArray(dados) ? dados : (dados.barbearias || [])))
                .catch(() => setBarbearias([]));
        }
    }, [souAdm]);

    useEffect(() => {
        const atualizarAgora = () => setAgora(new Date());
        atualizarAgora();
        const intervalo = window.setInterval(atualizarAgora, 60_000);
        return () => window.clearInterval(intervalo);
    }, []);

    useEffect(() => {
        queueMicrotask(() => carregar(filtroBarbearia));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filtroBarbearia]);


    // =================================================
    // FILTRAGEM
    // =================================================

    const agendamentosFiltrados = agendamentos
        .filter((agendamento) => {

            const correspondeBusca =
                String(agendamento.cliente_nome || "")
                    .toLowerCase()
                    .includes(busca.toLowerCase());

            const correspondeStatus =
                filtroStatus === "Todos" ||
                agendamento.status === filtroStatus;

            return correspondeBusca && correspondeStatus;

        })
        .sort((a, b) => {

            if (filtroData === "recentes") {
                return b.id_agendamento - a.id_agendamento;
            }

            if (filtroData === "antigas") {
                return a.id_agendamento - b.id_agendamento;
            }

            // A visualização padrão sempre começa pela reserva criada por último.
            // Os filtros de data continuam permitindo inverter a ordem quando necessário.
            return b.id_agendamento - a.id_agendamento;

        });


    // =================================================
    // PAGINAÇÃO
    // =================================================

    const totalResultados = agendamentosFiltrados.length;

    const totalPaginas = Math.max(
        1,
        Math.ceil(totalResultados / itensPorPagina)
    );

    const paginaCorrigida = Math.min(
        paginaAtual,
        totalPaginas
    );

    const inicio = (paginaCorrigida - 1) * itensPorPagina;

    const fim = inicio + itensPorPagina;

    const agendamentosPagina =
        agendamentosFiltrados.slice(inicio, fim);


    function atualizarBusca(valor) {
        setBusca(valor);
        setPaginaAtual(1);
    }


    function atualizarStatus(valor) {
        setFiltroStatus(valor);
        setPaginaAtual(1);
    }


    function atualizarData(valor) {
        setFiltroData(valor);
        setPaginaAtual(1);
    }


    function abrirAcao(agendamento, tipo) {
        setAcao({ agendamento, tipo });
        setTextoAviso("");
        const [data] = String(agendamento.inicio_em).split("T");
        setNovaData(data || "");
        setNovoHorario(formatarHora(agendamento.inicio_em));
        setMensagem(null);
    }


    async function executarAcao() {
        if (!acao) return;
        const { agendamento, tipo } = acao;
        setProcessando(true);
        try {
            let resposta;
            if (tipo === "cancelar") {
                resposta = await apiFetch(`/agendamentos/${agendamento.id_agendamento}/cancelar`, { method: "PUT", body: "{}" });
            } else if (tipo === "concluir" || tipo === "faltou") {
                resposta = await apiFetch(`/agendamentos/${agendamento.id_agendamento}/status-atendimento`, {
                    method: "PUT",
                    body: JSON.stringify({ status: tipo === "concluir" ? "concluido" : "faltou" })
                });
            } else if (tipo === "reagendar") {
                if (!novaData || !novoHorario) {
                    setMensagem({ informacao: "Informe a nova data e o novo horário.", tipo: "erro" });
                    setProcessando(false);
                    return;
                }
                resposta = await apiFetch(`/agendamentos/${agendamento.id_agendamento}/reagendar`, {
                    method: "PUT",
                    body: JSON.stringify({ data: novaData, horario: novoHorario })
                });
            } else {
                if (!textoAviso.trim()) {
                    setMensagem({ informacao: "Escreva o texto do aviso.", tipo: "erro" });
                    setProcessando(false);
                    return;
                }
                resposta = await apiFetch(`/agendamentos/${agendamento.id_agendamento}/avisar`, {
                    method: "POST",
                    body: JSON.stringify({ texto: textoAviso.trim() })
                });
            }
            setMensagem(resposta.mensagem || { informacao: "Operação concluída.", tipo: "sucesso" });
            setAcao(null);
            await carregar(filtroBarbearia);
        } catch (error) {
            setMensagem({ informacao: mensagemDaApi(error), tipo: "erro" });
        } finally {
            setProcessando(false);
        }
    }


    return (

        <main className={estilo.pagina}>

            <div className={estilo.conteudo}>

                <CabecalhoAgendamentos />

                {erro && (
                    <MensagemCard mensagem={{ informacao: erro, tipo: "erro" }} fechar={() => setErro("")} />
                )}

                {mensagem && (
                    <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} />
                )}

                <FiltrosAgendamentos
                    busca={busca}
                    setBusca={atualizarBusca}
                    filtroStatus={filtroStatus}
                    setFiltroStatus={atualizarStatus}
                    filtroData={filtroData}
                    setFiltroData={atualizarData}
                />

                {souAdm && (
                    <FiltroBarbearias
                        barbearias={barbearias}
                        filtroBarbearia={filtroBarbearia}
                        setFiltroBarbearia={(valor) => { setFiltroBarbearia(valor); setPaginaAtual(1); }}
                    />
                )}

                {carregando ? (
                    <p>Carregando agendamentos…</p>
                ) : (
                    <ListaAgendamentos
                        agendamentos={agendamentosPagina}
                        onAcao={abrirAcao}
                        onVerImagens={setAgendamentoComImagens}
                        agora={agora}
                    />
                )}

                <Paginacao
                    paginaAtual={paginaCorrigida}
                    setPaginaAtual={setPaginaAtual}
                    totalPaginas={totalPaginas}
                    totalResultados={totalResultados}
                    inicio={inicio}
                    fim={fim}
                />

                {acao && (
                    <div className={estilo.overlay} onClick={() => setAcao(null)}>
                        <section className={estilo.modal} onClick={(e) => e.stopPropagation()}>
                            <h2>
                                {acao.tipo === "cancelar" && `Cancelar agendamento de ${acao.agendamento.cliente_nome}?`}
                                {acao.tipo === "reagendar" && `Reagendar ${acao.agendamento.cliente_nome}`}
                                {acao.tipo === "avisar" && `Avisar ${acao.agendamento.cliente_nome}`}
                                {acao.tipo === "concluir" && `Confirmar atendimento de ${acao.agendamento.cliente_nome}?`}
                                {acao.tipo === "faltou" && `Confirmar falta de ${acao.agendamento.cliente_nome}?`}
                            </h2>
                            <p>{(acao.tipo === "concluir" || acao.tipo === "faltou")
                                ? "Essa confirmação ficará registrada no histórico do agendamento."
                                : "O cliente será avisado por e-mail."}</p>
                            {acao.tipo === "avisar" && (
                                <textarea value={textoAviso} onChange={(e) => setTextoAviso(e.target.value)}
                                    placeholder="Ex.: Chegue com 10 minutos de antecedência." maxLength={500} rows={4} />
                            )}
                            {acao.tipo === "reagendar" && (
                                <>
                                    <label>Nova data<input type="date" value={novaData} onChange={(e) => setNovaData(e.target.value)} /></label>
                                    <label>Novo horário<input type="time" value={novoHorario} onChange={(e) => setNovoHorario(e.target.value)} /></label>
                                </>
                            )}
                            <div className={estilo.modalAcoes}>
                                <button type="button" className={estilo.secundario} onClick={() => setAcao(null)}>Voltar</button>
                                <button type="button" disabled={processando} onClick={executarAcao}>
                                    {processando ? "Enviando…" : "Confirmar"}
                                </button>
                            </div>
                        </section>
                    </div>
                )}

                {agendamentoComImagens && (
                    <div className={estilo.overlay} onClick={() => setAgendamentoComImagens(null)}>
                        <section className={`${estilo.modal} ${estilo.modalImagens}`}
                            role="dialog" aria-modal="true" aria-label="Imagens do agendamento"
                            onClick={(e) => e.stopPropagation()}>
                            <h2>Referências de {agendamentoComImagens.cliente_nome}</h2>
                            <div className={estilo.galeriaImagens}>
                                {agendamentoComImagens.corte_imagem_url && (
                                    <figure>
                                        <img src={`${API_URL}${agendamentoComImagens.corte_imagem_url}`}
                                            alt={agendamentoComImagens.corte_nome || "Corte escolhido"} />
                                        <figcaption>
                                            {String(agendamentoComImagens.corte_imagem_url).includes("/resultados/")
                                                ? `Simulação IA · ${agendamentoComImagens.corte_nome || "corte"}`
                                                : (agendamentoComImagens.corte_nome || "Corte")}
                                        </figcaption>
                                    </figure>
                                )}
                                {agendamentoComImagens.visagismo_foto_url && (
                                    <figure>
                                        <img src={`${API_URL}${agendamentoComImagens.visagismo_foto_url}`}
                                            alt="Foto do visagismo" />
                                        <figcaption>Foto do visagismo</figcaption>
                                    </figure>
                                )}
                            </div>
                            <div className={estilo.modalAcoes}>
                                <button type="button" className={estilo.btnVoltar}
                                    onClick={() => setAgendamentoComImagens(null)}>Fechar</button>
                            </div>
                        </section>
                    </div>
                )}

            </div>

        </main>

    );
}

export default AgendamentosAdm;

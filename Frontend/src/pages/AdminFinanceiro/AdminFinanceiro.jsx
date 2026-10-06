import { useState, useEffect, useCallback, useMemo } from 'react';
import { FiDownload, FiArrowUp, FiArrowDown, FiCreditCard, FiArrowDownLeft, FiArrowUpRight, FiSearch, FiChevronLeft, FiChevronRight, FiX, FiCopy } from 'react-icons/fi';
import { API_URL, apiFetch, mensagemDaApi } from '../../services/api';
import { lerUsuarioLocal } from '../../contexts/authStorage';
import { buscarSaldo, buscarResumo, buscarMovimentacoes, buscarResumoGeral, buscarMovimentacoesGerais, criarCobrancaPix, consultarCobrancaPix } from '../../services/financeiro';
import estilo from './AdminFinanceiro.module.css';

const ITENS_POR_PAGINA = 8;
const PERIODOS = [
    { id: 'mes', rotulo: 'Este mês' },
    { id: '7d', rotulo: 'Últimos 7 dias' },
    { id: '30d', rotulo: 'Últimos 30 dias' },
    { id: 'personalizado', rotulo: 'Período personalizado' }
];
const ROTULO_ORIGEM = { pix: 'PIX / ARKHÉ', pix_qrcode: 'PIX QR CODE / ARKHÉ', boleto: 'BOLETO / ARKHÉ', cartao: 'CARTÃO / ARKHÉ', na_hora: 'PAGAMENTO NA HORA' };
const dinheiro = (numero) => `R$ ${Number(numero || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
function paraISO(data) { const mes = String(data.getMonth() + 1).padStart(2, '0'); const dia = String(data.getDate()).padStart(2, '0'); return `${data.getFullYear()}-${mes}-${dia}`; }
function calcularPeriodo(id, personalizado) {
    const hoje = new Date();
    if (id === 'personalizado' && personalizado?.inicio && personalizado?.fim) {
        const ini = personalizado.inicio <= personalizado.fim ? personalizado.inicio : personalizado.fim;
        const fim = personalizado.inicio <= personalizado.fim ? personalizado.fim : personalizado.inicio;
        return { dataInicio: ini, dataFim: fim };
    }
    const inicio = new Date(hoje);
    if (id === '7d') inicio.setDate(hoje.getDate() - 6); else if (id === '30d') inicio.setDate(hoje.getDate() - 29); else inicio.setDate(1);
    return { dataInicio: paraISO(inicio), dataFim: paraISO(hoje) };
}
function formatarDataHora(texto) { const [data = '', hora = ''] = String(texto || '').split(/[ T]/); const [ano, mes, dia] = data.split('-'); if (!ano || !mes || !dia) return texto || '-'; return `${dia}/${mes}/${ano}${hora ? ` ${hora.slice(0, 5)}` : ''}`; }
function exportarCSV(movimentacoes) {
    const linhas = [['Data', 'Tipo', 'Origem', 'Contraparte', 'Valor'], ...movimentacoes.map((item) => [formatarDataHora(item.data_movimentacao), item.tipo, item.origem, item.nome_contraparte, Number(item.valor).toFixed(2).replace('.', ',')])];
    const csv = linhas.map((linha) => linha.map((c) => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\r\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' }); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `movimentacoes-${paraISO(new Date())}.csv`; link.click(); URL.revokeObjectURL(url);
}

const CardsFinanceiros = ({ resumo, periodoRotulo }) => {
    const cards = [{ id: 1, titulo: 'RECEITA TOTAL', valor: resumo?.total_receitas, tipo: 'receita', icone: <FiArrowUp /> }, { id: 2, titulo: 'DESPESAS', valor: resumo?.total_despesas, tipo: 'despesa', icone: <FiArrowDown /> }, { id: 3, titulo: 'SALDO DO PERÍODO', valor: resumo?.saldo_periodo, tipo: 'lucro', icone: <FiCreditCard /> }];
    return (
        <section className={estilo.cards}>
            {cards.map((item, index) => (
                <article key={item.id} className={`${estilo.card} ${estilo[item.tipo]}`} style={{ '--delay': `${index * 0.15}s` }}>
                    <div className={estilo.topoCard}><span className={estilo.icone}>{item.icone}</span><span className={estilo.periodo}>{periodoRotulo}</span></div>
                    <div className={estilo.informacoes}><p>{item.titulo}</p><h2>{resumo ? dinheiro(item.valor) : '...'}</h2></div>
                </article>
            ))}
        </section>
    );
};

function ControleCaixa({ movimentacoes, periodoRotulo }) {
    const recebimentos = movimentacoes.filter((item) => item.tipo === 'entrada');
    const naHora = recebimentos.filter((item) => item.origem === 'na_hora').reduce((total, item) => total + Number(item.valor || 0), 0);
    const arkhe = recebimentos.filter((item) => item.origem !== 'na_hora').reduce((total, item) => total + Number(item.valor || 0), 0);
    const total = arkhe + naHora;
    return (
        <section className={estilo.controleCaixa} aria-label="Controle de caixa">
            <div className={estilo.controleCaixaTitulo}><div><h2>CONTROLE DE CAIXA</h2><p>Valores recebidos no período: {periodoRotulo}.</p></div><span>Arkhé + presencial</span></div>
            <div className={estilo.cardsCaixa}>
                <article className={estilo.cardCaixa}><small>RECEBIDO VIA ARKHÉ</small><strong>{dinheiro(arkhe)}</strong><span>Pix, boleto e cartão confirmados</span></article>
                <article className={`${estilo.cardCaixa} ${estilo.naHora}`}><small>RECEBIDO NA HORA</small><strong>{dinheiro(naHora)}</strong><span>Pagamentos presenciais registrados</span></article>
                <article className={`${estilo.cardCaixa} ${estilo.totalCaixa}`}><small>TOTAL NO CAIXA</small><strong>{dinheiro(total)}</strong><span>{recebimentos.length} recebimento(s)</span></article>
            </div>
        </section>
    );
}

const TIPOS_GRAFICO = [
    { id: 'todos', rotulo: 'Ganhos + Custos' },
    { id: 'ganhos', rotulo: 'Só ganhos' },
    { id: 'custos', rotulo: 'Só custos' }
];

const GraficoPygal = ({ periodo, idBarbearia, geral, rotuloConta, tipo = 'todos', aoMudarTipo }) => {
    const [imagem, setImagem] = useState(null);
    const [erroGrafico, setErroGrafico] = useState('');
    const [gerando, setGerando] = useState(false);
    const inicio = periodo.dataInicio;
    const fim = periodo.dataFim;
    useEffect(() => {
        let ativo = true;
        let urlObjeto = null;
        async function carregar() {
            setGerando(true); setErroGrafico('');
            try {
                const sufixoBarbearia = idBarbearia && idBarbearia !== 'todas' ? `&id_barbearia=${encodeURIComponent(idBarbearia)}` : '';
                const baseGrafico = geral ? '/financeiro/geral/grafico' : '/financeiro/grafico';
                const resposta = await fetch(`${API_URL}${baseGrafico}?data_inicio=${encodeURIComponent(inicio)}&data_fim=${encodeURIComponent(fim)}&tipo=${tipo}${sufixoBarbearia}`, { credentials: 'include' });
                const conteudo = resposta.headers.get('content-type') || '';
                if (!resposta.ok || !conteudo.includes('svg')) {
                    let msg = 'Não foi possível carregar o gráfico.';
                    try {
                        const dados = await resposta.json();
                        msg = dados?.mensagem?.informacao || msg;
                    } catch (leitura) { if (leitura) { /* mantém mensagem padrão */ } }
                    throw new Error(msg);
                }
                urlObjeto = URL.createObjectURL(await resposta.blob());
                if (ativo) setImagem(urlObjeto);
            } catch (e) { if (ativo) { setErroGrafico(e.message); setImagem(null); } }
            finally { if (ativo) setGerando(false); }
        }
        carregar();
        return () => { ativo = false; if (urlObjeto) URL.revokeObjectURL(urlObjeto); };
    }, [inicio, fim, tipo, idBarbearia, geral]);
    const rotulo = (iso) => { const [a, m, d] = String(iso).split('-'); return `${d}/${m}/${a}`; };
    return (
        <section className={estilo.graficoContainer}>
            <div className={estilo.graficoCabecalho}>
                <div><h2>DESEMPENHO</h2><p>Gráfico do servidor — {rotulo(inicio)} a {rotulo(fim)}{rotuloConta ? ` · ${rotuloConta}` : ''}</p></div>
                <div className={estilo.filtrosGrafico}>
                    <div className={estilo.tiposGrafico} role="group" aria-label="Tipo de valores">
                        {TIPOS_GRAFICO.map((t) => (
                            <button key={t.id} type="button" aria-pressed={tipo === t.id}
                                className={tipo === t.id ? estilo.tipoAtivo : ''} onClick={() => aoMudarTipo && aoMudarTipo(t.id)}>
                                {t.rotulo}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            <div className={estilo.areaGrafico}>
                {gerando && <p>Gerando gráfico…</p>}
                {!gerando && erroGrafico && <p className={estilo.erroTexto}>{erroGrafico}</p>}
                {!gerando && !erroGrafico && imagem && <img src={imagem} alt="Gráfico financeiro de ganhos e custos" className={estilo.imagemGrafico} />}
            </div>
        </section>
    );
};

function PorBarbearia({ dados }) {
    if (!dados?.length) return null;
    return (
        <section className={estilo.movimentacoes}>
            <div className={estilo.movimentacoesCabecalho}>
                <h2>POR BARBEARIA — ANÁLISE GERAL</h2>
            </div>
            <div className={estilo.tabelaWrapper}>
                <table><thead><tr><th>BARBEARIA</th><th>GANHOS</th><th>CUSTOS</th><th>SALDO</th></tr></thead><tbody>
                    {dados.map((item) => (
                        <tr key={item.id_barbearia}>
                            <td><strong>{item.nome}</strong></td>
                            <td className={estilo.valorEntrada}>{dinheiro(item.total_receitas)}</td>
                            <td className={estilo.valorSaida}>- {dinheiro(item.total_despesas)}</td>
                            <td className={estilo.valor}>{dinheiro(item.saldo_periodo)}</td>
                        </tr>
                    ))}
                </tbody></table>
            </div>
        </section>
    );
}

function Movimentacoes({ movimentacoes, carregando, mostrarBarbearia }) {
    const [busca, setBusca] = useState(''); const [pagina, setPagina] = useState(1);
    const filtradas = useMemo(() => { const termo = busca.toLowerCase(); return movimentacoes.filter((item) => `${item.nome_contraparte} ${item.tipo} ${item.origem}`.toLowerCase().includes(termo)); }, [movimentacoes, busca]);
    const totalPaginas = Math.max(1, Math.ceil(filtradas.length / ITENS_POR_PAGINA));
    const paginaAtual = Math.min(pagina, totalPaginas);
    const visiveis = filtradas.slice((paginaAtual - 1) * ITENS_POR_PAGINA, paginaAtual * ITENS_POR_PAGINA);
    function alterarBusca(valor) { setBusca(valor); setPagina(1); }
    return (
        <section className={estilo.movimentacoes}>
            <div className={estilo.movimentacoesCabecalho}>
                <h2>ÚLTIMAS MOVIMENTAÇÕES</h2>
                <div className={estilo.busca}><FiSearch /><input type="text" placeholder="Filtrar transações..." value={busca} onChange={(e) => alterarBusca(e.target.value)} /></div>
            </div>
            <div className={estilo.tabelaWrapper}>
                <table><thead><tr><th>DESCRIÇÃO</th><th>CATEGORIA</th><th>DATA</th><th>VALOR</th></tr></thead><tbody>
                    {visiveis.map((item, index) => {
                        const entrada = item.tipo === 'entrada';
                        return (
                            <tr key={item.id_movimentacao} style={{ '--delay': `${index * 0.08}s` }}>
                                <td><div className={estilo.descricao}><span className={estilo.iconeTransacao}>{entrada ? <FiArrowDownLeft /> : <FiArrowUpRight />}</span><div><strong>{item.nome_contraparte || '—'}</strong><small>{ROTULO_ORIGEM[item.origem] || String(item.origem || '').toUpperCase()}</small>{mostrarBarbearia && item.barbearia_nome && <small>{item.barbearia_nome}</small>}</div></div></td>
                                <td><span className={`${estilo.tag} ${entrada ? estilo.tagEntrada : estilo.tagSaida}`}>{entrada ? 'ENTRADA' : 'SAÍDA'}</span></td>
                                <td className={estilo.data}>{formatarDataHora(item.data_movimentacao)}</td>
                                <td className={`${estilo.valor} ${entrada ? estilo.valorEntrada : estilo.valorSaida}`}>{entrada ? '' : '- '}{dinheiro(item.valor)}</td>
                            </tr>
                        );
                    })}
                    {visiveis.length === 0 && (<tr><td colSpan="4" className={estilo.semResultados}>{carregando ? 'Carregando movimentações...' : 'Nenhuma transação encontrada.'}</td></tr>)}
                </tbody></table>
            </div>
            <div className={estilo.paginacao}>
                <button aria-label="Página anterior" disabled={paginaAtual === 1} onClick={() => setPagina(paginaAtual - 1)}><FiChevronLeft /></button>
                <button className={estilo.paginaAtiva} disabled>{paginaAtual} / {totalPaginas}</button>
                <button aria-label="Próxima página" disabled={paginaAtual === totalPaginas} onClick={() => setPagina(paginaAtual + 1)}><FiChevronRight /></button>
            </div>
        </section>
    );
};

function ModalCobrancaPix({ aoFechar, aoPagar }) {
    const [valor, setValor] = useState(''); const [cobranca, setCobranca] = useState(null); const [carregando, setCarregando] = useState(false); const [erro, setErro] = useState(''); const [copiado, setCopiado] = useState(false);
    const pago = cobranca?.status === 1; const idCobranca = cobranca?.id_cobranca;
    useEffect(() => {
        if (!idCobranca || pago) return undefined;
        let ativo = true;
        const timer = setInterval(async () => {
            try {
                const atual = await consultarCobrancaPix(idCobranca);
                if (ativo && atual.status === 1) {
                    setCobranca((anterior) => ({ ...anterior, ...atual }));
                    if (aoPagar) aoPagar();
                }
            } catch (erroVerificacao) {
                if (erroVerificacao) { /* tenta de novo em 4s */ }
            }
        }, 4000);
        return () => { clearInterval(timer); };
    }, [idCobranca, pago, aoPagar]);
    async function gerar(evento) { evento.preventDefault(); setErro(''); const numero = Number(valor.replace(/\./g, '').replace(',', '.')); if (!Number.isFinite(numero) || numero <= 0) { setErro('Informe um valor maior que zero.'); return; } setCarregando(true); try { setCobranca(await criarCobrancaPix(numero)); } catch (e) { setErro(e?.dados?.mensagem?.informacao || 'Erro ao gerar cobrança'); } finally { setCarregando(false); } }
    async function copiarCodigo() { try { await navigator.clipboard.writeText(cobranca.codigo_pagamento); setCopiado(true); setTimeout(() => setCopiado(false), 2000); } catch { setErro('Não foi possível copiar. Selecione o código manualmente.'); } }
    return (
        <div className={estilo.modalFundo} onClick={aoFechar} role="presentation">
            <div className={estilo.modal} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Nova cobrança Pix">
                <button type="button" className={estilo.modalFechar} onClick={aoFechar} aria-label="Fechar"><FiX /></button>
                <h2>NOVA COBRANÇA PIX</h2>
                {!cobranca && <form onSubmit={gerar} className={estilo.modalForm}><label htmlFor="valorCobranca">Valor (R$)</label><input id="valorCobranca" type="text" inputMode="decimal" placeholder="0,00" value={valor} onChange={(e) => setValor(e.target.value.replace(/[^\d.,]/g, ''))} autoFocus />{erro && <p className={estilo.erroTexto}>{erro}</p>}<button type="submit" className={estilo.botaoModal} disabled={carregando}>{carregando ? 'Gerando...' : 'Gerar cobrança'}</button></form>}
                {cobranca && !cobranca.status && <div className={estilo.modalCobranca}><p className={estilo.modalValor}>R$ {Number(cobranca.valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}</p><div className={estilo.qrCode}><img src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(cobranca.codigo_pagamento)}`} alt="QR Code Pix" /></div><code className={estilo.codigoPix}>{cobranca.codigo_pagamento}</code><button type="button" className={estilo.botaoModal} onClick={copiarCodigo}><FiCopy /> {copiado ? 'Copiado!' : 'Copiar código'}</button><p className={estilo.aguardando}>Aguardando pagamento...</p>{erro && <p className={estilo.erroTexto}>{erro}</p>}</div>}
                {cobranca?.status === 1 && <div className={estilo.modalCobranca}><span className={estilo.iconeSucesso}>✓</span><p className={estilo.modalValor}>Pagamento confirmado</p><button type="button" className={estilo.botaoModal} onClick={aoFechar}>Concluir</button></div>}
            </div>
        </div>
    );
}

function AdminFinaceiro() {
    const [periodoId, setPeriodoId] = useState('mes'); const [saldo, setSaldo] = useState(null); const [resumo, setResumo] = useState(null); const [movimentacoes, setMovimentacoes] = useState([]); const [carregando, setCarregando] = useState(true); const [erro, setErro] = useState(''); const [modalAberto, setModalAberto] = useState(false);
    const [souAdm] = useState(() => Number(lerUsuarioLocal()?.tipo) === 0);
    const [barbearias, setBarbearias] = useState([]);
    const [filtroBarbearia, setFiltroBarbearia] = useState('todas');
    const [dataIni, setDataIni] = useState(() => { const h = new Date(); h.setDate(1); return paraISO(h); });
    const [dataFim, setDataFim] = useState(() => paraISO(new Date()));
    const periodo = useMemo(() => calcularPeriodo(periodoId, { inicio: dataIni, fim: dataFim }), [periodoId, dataIni, dataFim]); const periodoRotulo = periodoId === 'personalizado' ? 'Período personalizado' : PERIODOS.find((p) => p.id === periodoId).rotulo; const [versao, setVersao] = useState(0);
    const [filtroTipo, setFiltroTipo] = useState('todos'); // 'todos' | 'custos' | 'receitas'
    // Tipo do filtro usado no gráfico (mesma regra do filtro global)
    const tipoGrafico = filtroTipo === 'custos' ? 'custos' : filtroTipo === 'receitas' ? 'ganhos' : 'todos';
    // Filtra as movimentações por tempo (período, já aplicado na API) e por tipo
    const movimentacoesFiltradas = useMemo(() => {
        if (filtroTipo === 'todos') return movimentacoes;
        return movimentacoes.filter((item) => (filtroTipo === 'receitas' ? item.tipo === 'entrada' : item.tipo === 'saida'));
    }, [movimentacoes, filtroTipo]);
    // Resumo (cards) coerente com o filtro de tipo aplicado
    const resumoVisivel = useMemo(() => {
        if (filtroTipo === 'todos' || !resumo) return resumo;
        const receitas = movimentacoesFiltradas.filter((i) => i.tipo === 'entrada').reduce((total, i) => total + Number(i.valor || 0), 0);
        const despesas = movimentacoesFiltradas.filter((i) => i.tipo === 'saida').reduce((total, i) => total + Number(i.valor || 0), 0);
        if (filtroTipo === 'receitas') return { ...resumo, total_receitas: receitas, total_despesas: 0, saldo_periodo: receitas };
        return { ...resumo, total_receitas: 0, total_despesas: despesas, saldo_periodo: -despesas };
    }, [resumo, filtroTipo, movimentacoesFiltradas]);
    const geral = souAdm && filtroBarbearia === 'todas';
    const rotuloConta = geral ? 'Todas as barbearias' : (souAdm ? (barbearias.find((b) => String(b.id) === String(filtroBarbearia))?.nome || '') : (lerUsuarioLocal()?.nome ? 'Sua barbearia' : ''));
    const recarregar = useCallback(() => { setCarregando(true); setVersao((v) => v + 1); }, []);
    useEffect(() => {
        if (!souAdm) return undefined;
        let ativo = true;
        apiFetch('/barbearias-disponiveis').then((dados) => { if (ativo) setBarbearias(dados.barbearias || []); }).catch(() => { if (ativo) setBarbearias([]); });
        return () => { ativo = false; };
    }, [souAdm]);
    useEffect(() => { let cancelado = false; async function carregar() { try { const [dadosSaldo, dadosResumo, dadosMov] = geral ? await Promise.all([Promise.resolve({ saldo: null }), buscarResumoGeral(periodo), buscarMovimentacoesGerais(periodo)]) : await Promise.all([buscarSaldo(filtroBarbearia), buscarResumo(periodo, filtroBarbearia), buscarMovimentacoes(periodo, filtroBarbearia)]); if (cancelado) return; setSaldo(dadosSaldo.saldo); setResumo(dadosResumo); setMovimentacoes(dadosMov.movimentacoes || []); setErro(''); } catch (e) { if (!cancelado) setErro(mensagemDaApi(e)); } finally { if (!cancelado) setCarregando(false); } } carregar(); return () => { cancelado = true; }; }, [periodo, versao, filtroBarbearia, geral]);
    return (
        <div className={estilo.pagina}>
            <main className={estilo.conteudo}>
                <div className={estilo.cabecalho}><h1>PAINEL FINANCEIRO</h1><p>Acompanhe o desempenho financeiro da sua barbearia em tempo real.</p><p className={estilo.saldoConta}>Saldo em conta: <strong>{geral ? 'Análise geral de todas as barbearias' : (saldo === null ? '...' : dinheiro(saldo))}</strong></p><div className={estilo.acoes}><select className={estilo.seletorPeriodo} value={periodoId} onChange={(e) => { setPeriodoId(e.target.value); setCarregando(true); setTimeout(() => setVersao(v => v + 1), 0); }} aria-label="Período">{PERIODOS.map((p) => (<option key={p.id} value={p.id}>{p.rotulo}</option>))}</select>{periodoId === 'personalizado' && (<span className={estilo.datasPersonalizadas}><label>De <input type="date" value={dataIni} max={dataFim} onChange={(e) => e.target.value && setDataIni(e.target.value)} /></label><label>Até <input type="date" value={dataFim} min={dataIni} onChange={(e) => e.target.value && setDataFim(e.target.value)} /></label></span>)}<span className={estilo.filtroTipoGroup} role="group" aria-label="Filtrar por tipo"><button type="button" className={filtroTipo === 'todos' ? estilo.filtroAtivo : ''} onClick={() => setFiltroTipo('todos')}>Tudo</button><button type="button" className={filtroTipo === 'receitas' ? estilo.filtroAtivo : ''} onClick={() => setFiltroTipo('receitas')}>Só receitas</button><button type="button" className={filtroTipo === 'custos' ? estilo.filtroAtivo : ''} onClick={() => setFiltroTipo('custos')}>Só custos</button></span><button className={estilo.botaoExportar} onClick={() => exportarCSV(movimentacoesFiltradas)} disabled={movimentacoesFiltradas.length === 0}><FiDownload /> Exportar Relatório</button><button className={estilo.botaoNova} onClick={() => setModalAberto(true)}>Nova Cobrança Pix</button></div></div>
                {erro && <div className={estilo.erroBanner} role="alert"><span>{erro}</span><button onClick={() => { setVersao(v => v + 1); }}>Tentar novamente</button></div>}
                {souAdm && (
                    <div className={estilo.filtroBarbeariaFin}>
                        <label>Barbearia
                            <select value={filtroBarbearia} onChange={(e) => { setFiltroBarbearia(e.target.value); setCarregando(true); setVersao((v) => v + 1); }} aria-label="Filtrar por barbearia">
                                <option value="todas">Todas</option>
                                {barbearias.map((b) => (<option key={b.id} value={b.id}>{b.nome}</option>))}
                            </select>
                        </label>
                        {String(filtroBarbearia) !== 'todas' && (
                            <span>Filtrando: <strong>{barbearias.find((b) => String(b.id) === String(filtroBarbearia))?.nome || `#${filtroBarbearia}`}</strong></span>
                        )}
                    </div>
                )}
                {resumo?.origem_dados === 'arkhe+local' && (
                    <p className={estilo.avisoArkhe}>Dados combinados: extrato da Arkhé e pagamentos presenciais registrados no caixa.</p>
                )}
                {resumo?.origem_dados === 'financeiro_local' && (
                    <p className={estilo.avisoLocal}>Exibindo dados locais do sistema (conta Arkhé da barbearia não configurada ou indisponível).</p>
                )}
                <CardsFinanceiros resumo={resumoVisivel} periodoRotulo={periodoRotulo} />
                {!geral && <ControleCaixa movimentacoes={movimentacoes} periodoRotulo={periodoRotulo} />}
                {geral && <PorBarbearia dados={resumo?.por_barbearia} />}
                <GraficoPygal periodo={periodo} idBarbearia={filtroBarbearia} geral={geral} rotuloConta={rotuloConta} tipo={tipoGrafico} aoMudarTipo={(novo) => setFiltroTipo(novo === 'custos' ? 'custos' : novo === 'ganhos' ? 'receitas' : 'todos')} />
                <Movimentacoes movimentacoes={movimentacoesFiltradas} carregando={carregando} mostrarBarbearia={geral} />
            </main>
            {modalAberto && <ModalCobrancaPix aoFechar={() => setModalAberto(false)} aoPagar={recarregar} />}
        </div>
    );
};

export default AdminFinaceiro;

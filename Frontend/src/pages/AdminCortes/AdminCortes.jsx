import { useEffect, useState } from 'react';
import { FiEdit2, FiImage, FiPlus, FiTrash2 } from 'react-icons/fi';
import { API_URL, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import ModalConfirmacao from '../../components/ModalConfirmacao/ModalConfirmacao';
import styles from './AdminCortes.module.css';

const FORM_INICIAL = { nome: '', descricao: '', categoria: 'cabelo', genero: '', imagem: null };
const categoriaLabel = { cabelo: 'Cabelo', barba: 'Barba', barba_cabelo: 'Cabelo e barba', corte_pintura: 'Corte e Pintura', pintura: 'Pintura' };
const generoLabel = { masculino: 'Masculino', feminino: 'Feminino', unissex: 'Unissex' };

export default function AdminCortes() {
    const [cortes, setCortes] = useState([]);
    const [form, setForm] = useState(FORM_INICIAL);
    const [editando, setEditando] = useState(null);
    const [erro, setErro] = useState('');
    const [mensagem, setMensagem] = useState('');
    const [salvando, setSalvando] = useState(false);
    const [pagina, setPagina] = useState(1);
    const [corteRemovendo, setCorteRemovendo] = useState(null);
    const [removendo, setRemovendo] = useState(false);
    const ITENS_POR_PAGINA = 15; // grade 3 x 5

    const totalPaginas = Math.max(1, Math.ceil(cortes.length / ITENS_POR_PAGINA));
    const paginaSegura = Math.min(pagina, totalPaginas);
    const cortesPagina = cortes.slice((paginaSegura - 1) * ITENS_POR_PAGINA, paginaSegura * ITENS_POR_PAGINA);

    async function carregar() {
        try {
            const dados = await apiFetch('/visagismo/cortes');
            setCortes(dados.cortes || []);
            setPagina(1);
        } catch (error) { setErro(mensagemDaApi(error)); }
    }
    useEffect(() => {
        queueMicrotask(carregar);
    }, []);

    function editar(corte) {
        setEditando(corte.id_corte);
        setForm({ nome: corte.nome || '', descricao: corte.descricao || '', categoria: corte.categoria || 'cabelo', genero: corte.genero || '', imagem: null });
        setErro('');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function cancelar() { setEditando(null); setForm(FORM_INICIAL); }
    function atualizar(campo, valor) { setForm((atual) => ({ ...atual, [campo]: valor })); }

    async function salvar(event) {
        event.preventDefault();
        if (!form.nome.trim()) return setErro('Informe o nome do corte.');
        if (!editando && !form.imagem) return setErro('Envie uma imagem de referência para o corte.');
        setSalvando(true); setErro(''); setMensagem('');
        try {
            const dados = new FormData();
            dados.append('nome', form.nome.trim());
            dados.append('descricao', form.descricao.trim());
            dados.append('categoria', form.categoria);
            dados.append('genero', form.genero || 'unissex');
            if (form.imagem) dados.append('imagem', form.imagem);
            const resposta = await apiFetch(editando ? `/visagismo/cortes/${editando}` : '/visagismo/cortes', { method: editando ? 'PUT' : 'POST', body: dados });
            setMensagem(resposta.mensagem?.informacao || 'Corte salvo com sucesso.');
            cancelar();
            await carregar();
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setSalvando(false); }
    }
    function remover(corte) {
        // Abre o modal de confirmação (substitui o window.confirm nativo)
        setCorteRemovendo(corte);
    }
    async function confirmarRemocao() {
        if (!corteRemovendo) return;
        setRemovendo(true);
        try {
            const resposta = await apiFetch(`/visagismo/cortes/${corteRemovendo.id_corte}`, { method: 'DELETE' });
            setMensagem(resposta.mensagem?.informacao || 'Corte removido.');
            setCorteRemovendo(null);
            await carregar();
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setRemovendo(false); }
    }

    return <main className={styles.page}>
        <header className={styles.header}><div><p className={styles.eyebrow}>ADMINISTRAÇÃO</p><h1>Catálogo de cortes</h1><p>Cadastre as referências que serão usadas no visagismo e exibidas aos clientes.</p></div></header>
        {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
        {mensagem && <MensagemCard mensagem={{ informacao: mensagem, tipo: 'sucesso' }} fechar={() => setMensagem('')} />}
        <section className={styles.formCard}>
            <div className={styles.sectionTitle}><FiPlus /> {editando ? 'Editar tipo de corte' : 'Adicionar tipo de corte'}</div>
            <form onSubmit={salvar} className={styles.form}>
                <label>Nome do corte<input value={form.nome} onChange={(e) => atualizar('nome', e.target.value)} placeholder="Ex.: Corte degradê" /></label>
                <label>Categoria<select value={form.categoria} onChange={(e) => atualizar('categoria', e.target.value)}><option value="cabelo">Cabelo</option><option value="barba">Barba</option><option value="barba_cabelo">Cabelo e barba</option><option value="corte_pintura">Corte e Pintura</option><option value="pintura">Pintura</option></select></label>
                <label>Gênero<select value={form.genero} onChange={(e) => atualizar('genero', e.target.value)}><option value="">Unissex</option><option value="masculino">Masculino</option><option value="feminino">Feminino</option></select></label>
                <label className={styles.full}>Descrição breve<textarea value={form.descricao} onChange={(e) => atualizar('descricao', e.target.value)} placeholder="Descreva a referência para orientar a recomendação." /></label>
                <label className={styles.upload}><FiImage /> {form.imagem ? form.imagem.name : editando ? 'Trocar imagem (opcional)' : 'Enviar imagem de referência'}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => atualizar('imagem', e.target.files?.[0] || null)} /></label>
                <div className={styles.actions}><button className={styles.primary} disabled={salvando}>{salvando ? 'Salvando…' : editando ? 'Salvar alterações' : 'Adicionar corte'}</button>{editando && <button type="button" className={styles.secondary} onClick={cancelar}>Cancelar</button>}</div>
            </form>
        </section>
        <section><div className={styles.listTitle}><h2>Cortes cadastrados</h2><span>{cortes.length} item(ns) · página {paginaSegura} de {totalPaginas}</span></div><div className={styles.grid}>{cortesPagina.map((corte) => <article className={styles.card} key={corte.id_corte}><img src={corte.imagem_url ? (corte.imagem_url.startsWith('http') ? corte.imagem_url : `${API_URL}${corte.imagem_url}`) : ''} alt={corte.nome} /><div className={styles.cardBody}><span className={styles.badge}>{categoriaLabel[corte.categoria] || corte.categoria}</span><span className={styles.badge}>{generoLabel[corte.genero] || 'Unissex'}</span><h3>{corte.nome}</h3><p>{corte.descricao || 'Sem descrição cadastrada.'}</p><div className={styles.cardActions}><button onClick={() => editar(corte)}><FiEdit2 /> Editar</button><button onClick={() => remover(corte)}><FiTrash2 /> Remover</button></div></div></article>)}</div>{!cortes.length && <p className={styles.empty}>Nenhum corte cadastrado ainda.</p>}
            {totalPaginas > 1 && <div className={styles.paginacao}>
                <button type="button" disabled={paginaSegura === 1} onClick={() => setPagina(paginaSegura - 1)} aria-label="Página anterior">‹</button>
                {Array.from({ length: totalPaginas }, (_, i) => i + 1).map((p) => <button type="button" key={p} className={p === paginaSegura ? styles.paginaAtiva : ''} onClick={() => setPagina(p)} aria-current={p === paginaSegura ? 'page' : undefined}>{p}</button>)}
                <button type="button" disabled={paginaSegura === totalPaginas} onClick={() => setPagina(paginaSegura + 1)} aria-label="Próxima página">›</button>
            </div>}
        </section>

        <ModalConfirmacao
            aberto={!!corteRemovendo}
            titulo="Remover do catálogo"
            mensagem={`Deseja remover “${corteRemovendo?.nome || ''}” do catálogo de cortes?`}
            detalhe="O corte deixará de aparecer nas recomendações do visagismo."
            textoConfirmar="Remover"
            textoCancelar="Voltar"
            perigo
            processando={removendo}
            aoConfirmar={confirmarRemocao}
            aoCancelar={() => setCorteRemovendo(null)}
        />
    </main>;
}

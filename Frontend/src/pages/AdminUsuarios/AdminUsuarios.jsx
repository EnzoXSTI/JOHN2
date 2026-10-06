import { useEffect, useState } from 'react';
import { FiEdit2, FiPlus, FiSearch, FiUser } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { API_URL, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import Botao from '../../components/Button/Button';
import styles from './AdminUsuarios.module.css';

export default function AdminUsuarios() {
    const navigate = useNavigate();
    const [usuarios, setUsuarios] = useState([]);
    const [busca, setBusca] = useState('');
    const [tipo, setTipo] = useState('');
    const [erro, setErro] = useState('');
    const [usuarioStatus, setUsuarioStatus] = useState(null);
    const [motivo, setMotivo] = useState('');
    const [processando, setProcessando] = useState(false);

    async function carregar() {
        try {
            setErro('');
            setUsuarios(await apiFetch(`/listar_usuarios${tipo === '' ? '' : `?tipo=${tipo}`}`));
        } catch (error) { setErro(mensagemDaApi(error)); }
    }
    useEffect(() => {
        // A lista é carregada após a montagem e sempre que o filtro mudar.
        queueMicrotask(carregar);
        // carregar usa somente o filtro atual e setters estáveis do React.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tipo]);

    async function confirmarStatus() {
        if (!usuarioStatus) return;
        if (usuarioStatus.ativo && !motivo.trim()) return setErro('Informe o motivo antes de desativar o usuário.');
        setProcessando(true);
        try {
            await apiFetch(`/usuarios/${usuarioStatus.id}/status`, { method: 'PUT', body: JSON.stringify({ ativo: !usuarioStatus.ativo, motivo: motivo.trim() }) });
            setUsuarioStatus(null); setMotivo(''); await carregar();
        } catch (error) { setErro(mensagemDaApi(error)); } finally { setProcessando(false); }
    }

    const filtrados = usuarios.filter((usuario) => `${usuario.nome} ${usuario.email}`.toLowerCase().includes(busca.toLowerCase()));
    return <main className={styles.page}>
        <header className={styles.cabecalho}><div><p className={styles.eyebrow}>ADMINISTRAÇÃO</p><h1>Usuários cadastrados</h1><p>Gerencie perfis de clientes, barbearias e administradores.</p></div><button className={styles.adicionar} onClick={() => navigate('/cadastrobarbearia?origem=admin')}><FiPlus /> Adicionar usuário</button></header>
        <section className={styles.filtros}><label><FiSearch /><input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar por nome ou e-mail" /></label><select value={tipo} onChange={(e) => setTipo(e.target.value)}><option value="">Todos os tipos</option><option value="0">Administradores</option><option value="1">Clientes</option><option value="2">Barbearias</option></select></section>
        {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
        <section className={styles.grid}>{filtrados.map((usuario) => <article className={styles.card} key={usuario.id}><div className={styles.avatar}>{usuario.foto_perfil ? <img src={`${API_URL}${usuario.foto_perfil}`} alt="" /> : <FiUser />}</div><span className={`${styles.badge} ${styles[`tipo${usuario.tipo}`]}`}>{usuario.tipo_nome}</span><span className={`${styles.status} ${usuario.ativo ? styles.ativo : styles.inativo}`}>{usuario.ativo ? 'Ativo' : 'Desativado'}</span><h2>{usuario.nome}</h2><p>{usuario.email}</p><p>{usuario.telefone || 'Telefone não informado'}</p><div className={styles.acoes}><button onClick={() => navigate(`/editarusuario/${usuario.id}`)}><FiEdit2 /> Editar usuário</button>{usuario.ativo ? <button className={styles.desativar} onClick={() => setUsuarioStatus(usuario)}>Desativar</button> : (usuario.ja_foi_bloqueado ? <button className={styles.ativar} onClick={() => setUsuarioStatus(usuario)}>Reativar</button> : <button className={styles.ativar} onClick={() => setUsuarioStatus(usuario)}>Ativar</button>)}{usuario.tipo === 2 && <><Botao texto="Ver barbearia" pagina={`/estabelecimento?usuario=${usuario.id}`} /><Botao texto="Agendamentos" pagina={`/agendamentosadm?barbearia=${usuario.id}`} /><button className={styles.secundario} onClick={() => navigate(`/editarbarbearia?usuario=${usuario.id}`)}>Editar barbearia</button></>}</div></article>)}</section>
        {usuarioStatus && <div className={styles.overlay}><section className={styles.modal}><h2>{usuarioStatus.ativo ? 'Desativar usuário' : (usuarioStatus.ja_foi_bloqueado ? 'Reativar usuário' : 'Ativar usuário')}</h2><p>{usuarioStatus.ativo ? `Um e-mail será enviado para ${usuarioStatus.email} explicando o motivo antes da desativação.` : (usuarioStatus.ja_foi_bloqueado ? `Deseja reativar ${usuarioStatus.nome}?` : `Deseja ativar ${usuarioStatus.nome}?`)}</p>{usuarioStatus.ativo && <textarea value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo da desativação" />}<div className={styles.modalAcoes}><button className={styles.secundario} onClick={() => { setUsuarioStatus(null); setMotivo(''); }}>Cancelar</button><button className={usuarioStatus.ativo ? styles.desativar : styles.ativar} disabled={processando} onClick={confirmarStatus}>{processando ? 'Processando…' : 'Confirmar'}</button></div></section></div>}
    </main>;
}

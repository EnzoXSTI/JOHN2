import { useEffect } from 'react';
import { FiAlertTriangle, FiHelpCircle, FiX } from 'react-icons/fi';
import styles from './ModalConfirmacao.module.css';

/**
 * Modal de confirmação padrão do projeto.
 *
 * Substitui os `window.confirm()` nativos por um diálogo estilizado,
 * acessível (role=dialog, fecha com Esc) e com animações de entrada.
 *
 * @param {boolean} aberto        controla a visibilidade
 * @param {string}  titulo        título do modal
 * @param {string}  mensagem      pergunta/aviso principal
 * @param {string}  detalhe       linha de destaque opcional (ex.: nome do item)
 * @param {string}  textoConfirmar rótulo do botão de confirmação
 * @param {string}  textoCancelar  rótulo do botão de cancelamento
 * @param {boolean} perigo        true = botão de confirmação vermelho
 * @param {boolean} processando   desabilita os botões durante a requisição
 * @param {function} aoConfirmar  chamado ao confirmar
 * @param {function} aoCancelar   chamado ao cancelar (Esc, overlay ou botão)
 */
export default function ModalConfirmacao({
    aberto,
    titulo,
    mensagem,
    detalhe = '',
    textoConfirmar = 'Confirmar',
    textoCancelar = 'Voltar',
    perigo = false,
    processando = false,
    aoConfirmar,
    aoCancelar
}) {
    useEffect(() => {
        if (!aberto) return undefined;
        const aoTeclar = (evento) => {
            if (evento.key === 'Escape' && !processando) aoCancelar?.();
        };
        window.addEventListener('keydown', aoTeclar);
        return () => window.removeEventListener('keydown', aoTeclar);
    }, [aberto, processando, aoCancelar]);

    if (!aberto) return null;

    return (
        <div
            className={styles.overlay}
            role="dialog"
            aria-modal="true"
            aria-label={titulo}
            onClick={() => !processando && aoCancelar?.()}
        >
            <section className={styles.modal} onClick={(evento) => evento.stopPropagation()}>
                <button
                    type="button"
                    className={styles.fechar}
                    aria-label="Fechar"
                    disabled={processando}
                    onClick={() => aoCancelar?.()}
                >
                    <FiX size={18} />
                </button>

                <span className={`${styles.icone} ${perigo ? styles.iconePerigo : styles.iconeNeutro}`}>
                    {perigo ? <FiAlertTriangle size={24} /> : <FiHelpCircle size={24} />}
                </span>

                <h2 className={styles.titulo}>{titulo}</h2>
                <p className={styles.mensagem}>{mensagem}</p>
                {detalhe && <div className={styles.detalhe}>{detalhe}</div>}

                <div className={styles.acoes}>
                    <button
                        type="button"
                        className={`${styles.btn} ${styles.btnVoltar}`}
                        disabled={processando}
                        onClick={() => aoCancelar?.()}
                    >
                        {textoCancelar}
                    </button>
                    <button
                        type="button"
                        className={`${styles.btn} ${perigo ? styles.btnPerigo : styles.btnConfirmar}`}
                        disabled={processando}
                        onClick={aoConfirmar}
                    >
                        {processando ? 'Aguarde…' : textoConfirmar}
                    </button>
                </div>
            </section>
        </div>
    );
}
